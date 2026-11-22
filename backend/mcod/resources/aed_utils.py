# MISJA AED
#
# Narzędzia do walidacji zasobów zawierających wykaz AED (flaga
# `Resource.contains_aed_list`) oraz do tworzenia zbiorczego wykazu AED
# ("Wykaz zbiorczy AED") publikowanego w portalu. Moduł jest wzorowany na
# `dga_utils.py` (wykaz zbiorczy chronionych danych DGA).
import csv

from celery import states  # MISJA AED
import datetime
import json
import logging
import os
import re
from io import BytesIO, StringIO
from mimetypes import guess_extension
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import pandas as pd
import requests
import sentry_sdk
from cache_memoize import cache_memoize
from chardet import detect as detect_encoding
from django.apps import apps
from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from mcod.core.utils import save_df_to_xlsx
from mcod.resources.aed_constants import (
    AED_ALL_COLUMNS,
    AED_DATE_COLUMNS,
    AED_DATE_FORMAT,
    AED_ENUM_DICTIONARIES,
    AED_ERROR_DATE,
    AED_ERROR_ENUM,
    AED_ERROR_MISSING_VALUE,
    AED_ERROR_NUMBER,
    AED_ERROR_PATTERN,
    AED_ERROR_RANGE,
    AED_ID_COLUMN,
    AED_LATITUDE_COLUMN,
    AED_LONGITUDE_COLUMN,
    AED_NUMERIC_RANGES,
    AED_PATTERNS,
    AED_REQUIRED_COLUMNS,
    AED_REQUIRED_VALUE_COLUMNS,
    AED_RESOURCE_EXTENSIONS,
    AED_VALIDATION_REPORT_MAX_ERRORS_PER_RESOURCE,
    MAIN_AED_COLUMNS,
    MAIN_AED_ID_PREFIX_TEMPLATE,
    MAIN_AED_ORGANIZATION_COLUMN,
    MAIN_AED_PROVENANCE_COLUMNS,
    MAIN_AED_SOURCE_MODIFIED_COLUMN,
    MAIN_AED_SOURCE_URL_COLUMN,
)

if TYPE_CHECKING:
    from mcod.resources.models import AggregatedAEDInfo, Dataset, Resource

logger = logging.getLogger("mcod")

MAIN_AED_CSV: str = "csv"
MAIN_AED_XLSX: str = "xlsx"
MAIN_AED_GEOJSON: str = "geojson"
MAIN_AED_FORMATS: Tuple[str, ...] = (MAIN_AED_CSV, MAIN_AED_XLSX, MAIN_AED_GEOJSON)
MAIN_AED_MIMETYPES: Dict[str, str] = {
    MAIN_AED_CSV: "text/csv",
    MAIN_AED_XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    MAIN_AED_GEOJSON: "application/geo+json",
}
MAIN_AED_TASK_LOCK_KEY: str = "main_aed_task_lock"


class MainAEDMissingRequiredColumnError(Exception):
    """Raised when a required (poziom "W") AED source column is missing."""

    def __init__(self, column_names: Union[str, List[str]]):
        if isinstance(column_names, str):
            column_names = [column_names]
        self.column_names = column_names
        message = ", ".join(column_names)

        super().__init__(f"Missing required column(s): {message}")


class MainAEDResourceReadError(Exception):
    """Raised when a Main AED source resource cannot be read."""


class AEDValidationResult(NamedTuple):
    # Lista błędów: {"row": <nr wiersza w pliku>, "id_aed": ..., "column": ..., "error": ...}
    errors: List[Dict[str, Any]]
    # Indeksy (DataFrame) wierszy z co najmniej jednym błędem.
    invalid_rows: Set[int]


# ---------------------------------------------------------------------------
# Main AED Resource / Dataset / AggregatedAEDInfo
# ---------------------------------------------------------------------------


def get_aed_info() -> Optional["AggregatedAEDInfo"]:
    from mcod.resources.models import AggregatedAEDInfo

    return AggregatedAEDInfo.objects.last()


def get_main_aed_resource() -> Optional["Resource"]:
    aed_info: Optional["AggregatedAEDInfo"] = get_aed_info()
    return aed_info.main_aed_resource if aed_info else None


def get_main_aed_dataset() -> Optional["Dataset"]:
    aed_info: Optional["AggregatedAEDInfo"] = get_aed_info()
    return aed_info.main_aed_dataset if aed_info else None


def get_main_aed_resources_ids() -> List[int]:
    aed_info: Optional["AggregatedAEDInfo"] = get_aed_info()
    return aed_info.main_aed_resources_ids if aed_info else []


# ---------------------------------------------------------------------------
# Reading and validation of a single AED file
# ---------------------------------------------------------------------------


def normalize_aed_column_name(column_name: Any) -> str:
    """Strips whitespace / BOM and lowercases column name (np. ' ID_AED' -> 'id_aed')."""
    return str(column_name).replace("﻿", "").strip().lower()


def detect_aed_csv_delimiter(content: str) -> str:
    """
    Returns CSV delimiter (comma, semicolon or tab). The header line is checked
    first (column names of the AED schema never contain delimiters), then
    csv.Sniffer is used as a fallback.
    """
    sample: str = content[:65536]
    header: str = sample.splitlines()[0] if sample else ""
    candidates: List[str] = [",", ";", "\t"]
    best: str = max(candidates, key=header.count)
    if header.count(best) > 0:
        return best
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(candidates)).delimiter
    except csv.Error:
        return ","


def create_df_from_aed_file(
    file: Union[InMemoryUploadedFile, BytesIO],
    extension: Optional[str],
) -> Optional[pd.DataFrame]:
    """
    Returns DataFrame (all values as stripped strings, empty values as "") for
    given file and extension or None if extension is not one of: `csv`, `xls`,
    `xlsx`. CSV files can be comma or semicolon separated.
    """
    extension = extension.lower().lstrip(".") if extension else extension
    if extension in ("xls", "xlsx"):
        df: pd.DataFrame = pd.read_excel(file, dtype=str)
    elif extension == "csv":
        raw_data: bytes = file.read()
        file.seek(0)
        result = detect_encoding(raw_data)
        encoding: Optional[str] = result["encoding"]
        if encoding is None:
            logger.error("Could not detect AED file encoding")
            return None
        if encoding.lower() in ("ascii", "utf-8"):
            encoding = "utf-8-sig"
        content: str = raw_data.decode(encoding)
        delimiter: str = detect_aed_csv_delimiter(content)
        df = pd.read_csv(StringIO(content), sep=delimiter, dtype=str, keep_default_na=False)
    else:
        return None

    df.columns = [normalize_aed_column_name(column) for column in df.columns]
    df = df.fillna("")
    for column in df.columns:
        df[column] = df[column].map(lambda value: str(value).strip())
    return df


def get_missing_aed_required_columns(df: pd.DataFrame) -> List[str]:
    """Returns required (poziom "W") AED columns missing in the DataFrame."""
    columns: Set[str] = {normalize_aed_column_name(column) for column in df.columns}
    return [column for column in AED_REQUIRED_COLUMNS if column not in columns]


def validate_aed_df_columns(df: pd.DataFrame) -> bool:
    """Returns True if DataFrame contains all required AED columns (order does not matter)."""
    return not get_missing_aed_required_columns(df)


def get_missing_aed_required_columns_in_file(
    file: Union[InMemoryUploadedFile, BytesIO],
    extension: Optional[str],
) -> Optional[List[str]]:
    """
    Returns list of missing required AED columns for given file (empty list if
    file structure is correct) or None if file cannot be read.
    """
    try:
        df: Optional[pd.DataFrame] = create_df_from_aed_file(file, extension)
    except Exception as e:
        logger.exception(f"Error reading AED file: {e}")
        return None
    finally:
        try:
            file.seek(0)
        except Exception:
            pass

    if df is None:
        return None
    return get_missing_aed_required_columns(df)


def validate_aed_file_columns(
    file: Union[InMemoryUploadedFile, BytesIO],
    extension: Optional[str],
) -> bool:
    """Returns True if file contains all required AED columns, False otherwise."""
    missing_columns: Optional[List[str]] = get_missing_aed_required_columns_in_file(file, extension)
    return missing_columns is not None and not missing_columns


def normalize_aed_source_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes AED source DataFrame to the standard structure (AED_ALL_COLUMNS):

    - unknown columns are dropped (also aggregator-only "A" columns),
    - missing optional/recommended columns are added with empty values,
    - all values are stripped strings, empty values are "",
    - values of dictionary (enum) columns are lowercased,
    - decimal comma in coordinates is replaced with a dot.
    """
    df = df.copy()
    df.columns = [normalize_aed_column_name(column) for column in df.columns]
    # Usuń zduplikowane kolumny (zostaw pierwszą).
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]
    df = df.reindex(columns=AED_ALL_COLUMNS, fill_value="")
    df = df.fillna("")
    for column in AED_ALL_COLUMNS:
        df[column] = df[column].map(lambda value: str(value).strip())

    for column in AED_ENUM_DICTIONARIES:
        df[column] = df[column].str.lower()

    for column in AED_NUMERIC_RANGES:
        df[column] = df[column].str.replace(",", ".", regex=False)

    # Daty z plików XLSX/XLS są odczytywane jako "RRRR-MM-DD 00:00:00".
    for column in AED_DATE_COLUMNS:
        df[column] = df[column].str.replace(r"^(\d{4}-\d{2}-\d{2})[ T]00:00:00$", r"\1", regex=True)

    return df.reset_index(drop=True)


def get_valid_aed_coordinates_mask(df: pd.DataFrame) -> pd.Series:
    """Returns boolean Series - True for rows with numeric coordinates inside allowed range (Poland)."""
    mask = pd.Series(True, index=df.index)
    for column in (AED_LATITUDE_COLUMN, AED_LONGITUDE_COLUMN):
        values = pd.to_numeric(df[column], errors="coerce")
        minimum, maximum = AED_NUMERIC_RANGES.get(column, (None, None))
        column_mask = values.notna()
        if minimum is not None:
            column_mask &= values >= minimum
        if maximum is not None:
            column_mask &= values <= maximum
        mask &= column_mask
    return mask


def validate_aed_rows(df: pd.DataFrame) -> AEDValidationResult:
    """
    Validates rows of normalized AED DataFrame against the AED tableschema:
    required values, dictionaries (enum), patterns, numeric ranges
    (coordinates) and dates. Invalid rows are NOT removed - they are only
    reported.

    Row numbers in errors are line numbers in the source file (header = 1).
    """
    errors: List[Dict[str, Any]] = []

    def _add_errors(mask: pd.Series, column: str, message: str) -> None:
        for index in df.index[mask]:
            errors.append(
                {
                    "row": int(index) + 2,
                    AED_ID_COLUMN: df.at[index, AED_ID_COLUMN],
                    "column": column,
                    "error": message,
                    "_index": int(index),
                }
            )

    is_empty = df.eq("")

    for column in AED_REQUIRED_VALUE_COLUMNS:
        _add_errors(is_empty[column], column, AED_ERROR_MISSING_VALUE)

    for column, allowed_values in AED_ENUM_DICTIONARIES.items():
        _add_errors(~is_empty[column] & ~df[column].isin(allowed_values), column, AED_ERROR_ENUM)

    for column, pattern in AED_PATTERNS.items():
        regex = re.compile(pattern)
        matches = df[column].map(lambda value, _regex=regex: bool(_regex.fullmatch(value)))
        _add_errors(~is_empty[column] & ~matches, column, AED_ERROR_PATTERN)

    for column, (minimum, maximum) in AED_NUMERIC_RANGES.items():
        values = pd.to_numeric(df[column], errors="coerce")
        _add_errors(~is_empty[column] & values.isna(), column, AED_ERROR_NUMBER)
        out_of_range = pd.Series(False, index=df.index)
        if minimum is not None:
            out_of_range |= values < minimum
        if maximum is not None:
            out_of_range |= values > maximum
        _add_errors(values.notna() & out_of_range, column, AED_ERROR_RANGE)

    for column in AED_DATE_COLUMNS:
        dates = pd.to_datetime(df[column], format=AED_DATE_FORMAT, errors="coerce")
        _add_errors(~is_empty[column] & dates.isna(), column, AED_ERROR_DATE)

    errors.sort(key=lambda error: (error["_index"], AED_ALL_COLUMNS.index(error["column"])))
    invalid_rows: Set[int] = {error.pop("_index") for error in errors}
    return AEDValidationResult(errors=errors, invalid_rows=invalid_rows)


# ---------------------------------------------------------------------------
# Source AED resources
# ---------------------------------------------------------------------------


def get_all_aed_resources_sorted_by_organizations() -> QuerySet:
    """
    Returns published resources marked as AED lists (`contains_aed_list`),
    excluding the resources of the current Main AED (aggregated list).
    """
    Resource = apps.get_model("resources", "Resource")

    aed_resources: QuerySet = (
        Resource.objects.filter(
            contains_aed_list=True,
            status="published",
        )
        .exclude(id__in=get_main_aed_resources_ids())
        .select_related("dataset__organization")
        .order_by("dataset__organization__title", "id")
    )
    return aed_resources


def request_remote_aed(url: str) -> requests.models.Response:
    """
    Returns the response from the GET request to the remote AED file URL.
    Raises requests.exceptions.RequestException on timeout / connection error.
    """
    return requests.get(url, verify=False, timeout=(3.0, 30.0))


def get_remote_aed_extension(response: requests.models.Response, url: str) -> Optional[str]:
    """Returns AED extension (csv, xls, xlsx) based on URL suffix or Content-Type header."""
    url_extension: str = os.path.splitext(urlparse(url).path)[1].lower().lstrip(".")
    if url_extension in AED_RESOURCE_EXTENSIONS:
        return url_extension

    content_type: str = response.headers.get("Content-Type", "").split(";")[0].strip()
    extension: Optional[str] = guess_extension(content_type) if content_type else None
    if extension and extension[1:] in AED_RESOURCE_EXTENSIONS:
        return extension[1:]
    return None


def _read_aed_main_file(resource: "Resource") -> Tuple[BytesIO, Optional[str]]:
    main_file = resource.main_file
    if not main_file:
        raise MainAEDResourceReadError(f"Resource {resource.pk} has no main file")
    try:
        with open(main_file.path, "rb") as source_file:
            content: bytes = source_file.read()
    except (FileNotFoundError, ValueError) as exc:
        raise MainAEDResourceReadError(f"Cannot read main file of resource {resource.pk}") from exc
    extension: str = os.path.splitext(main_file.name)[1].lower().lstrip(".")
    return BytesIO(content), extension


def _read_aed_remote_link(resource: "Resource", url: str) -> Tuple[BytesIO, Optional[str]]:
    try:
        response: requests.models.Response = request_remote_aed(url)
    except requests.exceptions.RequestException as exc:
        raise MainAEDResourceReadError(f"Site not responding. Resource id: {resource.pk}; url: {url}") from exc
    if response.status_code != 200:
        raise MainAEDResourceReadError(
            f"Status code not 200: {response.status_code}. Resource id: {resource.pk}; url: {url}"
        )
    return BytesIO(response.content), get_remote_aed_extension(response, url)


def get_aed_source_file(resource: "Resource") -> Tuple[BytesIO, Optional[str]]:
    """
    Returns content of AED source resource and file extension.

    MISJA AED: portal pobiera plik zasobu-linku tylko przy dodaniu/rewalidacji i przechowuje kopię. Żeby dysponent mógł
    po prostu podmieniać plik w BIP, wykaz zbiorczy przy każdym przebiegu pobiera zasób-link NA ŚWIEŻO, a lokalnej
    kopii używa tylko wtedy, gdy link nie odpowiada. Zasoby z wgranym plikiem czytane są z pliku.
    """
    url: Optional[str] = resource.link
    is_remote: bool = bool(url) and getattr(resource, "availability", "") == "remote" or (bool(url) and not resource.main_file)
    if is_remote:
        try:
            return _read_aed_remote_link(resource, url)
        except MainAEDResourceReadError:
            if not resource.main_file:
                raise
            logger.warning(f"AED: link zasobu {resource.pk} nie odpowiada – używam ostatniej kopii z portalu.")
    if resource.main_file:
        return _read_aed_main_file(resource)
    raise MainAEDResourceReadError(f"Resource {resource.pk} has neither file nor link")


def get_aed_source_df(resource: "Resource") -> pd.DataFrame:
    """
    Reads AED source resource, validates required columns and returns
    DataFrame normalized to AED_ALL_COLUMNS.
    """
    file, extension = get_aed_source_file(resource)
    if extension not in AED_RESOURCE_EXTENSIONS:
        raise MainAEDResourceReadError(f"Incorrect file extension ({extension}) of resource {resource.pk}")

    try:
        df: Optional[pd.DataFrame] = create_df_from_aed_file(file, extension)
    except Exception as exc:
        raise MainAEDResourceReadError(f"Cannot parse data of resource {resource.pk}: {exc}") from exc
    if df is None:
        raise MainAEDResourceReadError(f"Cannot parse data of resource {resource.pk}")

    missing_columns: List[str] = get_missing_aed_required_columns(df)
    if missing_columns:
        raise MainAEDMissingRequiredColumnError(missing_columns)

    return normalize_aed_source_df(df)


def get_aed_resource_provenance(resource: "Resource") -> Dict[str, str]:
    """Returns provenance columns values (organization, resource URL, resource modified date)."""
    modified: Optional[Union[datetime.datetime, datetime.date]] = resource.modified or resource.created
    if isinstance(modified, datetime.datetime):
        modified = modified.date()
    return {
        MAIN_AED_ORGANIZATION_COLUMN: resource.institution.title,
        MAIN_AED_SOURCE_URL_COLUMN: resource.frontend_absolute_url,
        MAIN_AED_SOURCE_MODIFIED_COLUMN: modified.isoformat() if modified else "",
    }


def add_aed_provenance_to_df(df: pd.DataFrame, resource_id: int, provenance: Dict[str, str]) -> pd.DataFrame:
    """
    Prepends provenance columns and prefixes `id_aed` with the source code,
    so the identifier is unique in the aggregated list.
    """
    df = df.copy()
    prefix: str = MAIN_AED_ID_PREFIX_TEMPLATE.format(resource_id=resource_id)
    has_id = df[AED_ID_COLUMN].ne("")
    df.loc[has_id, AED_ID_COLUMN] = prefix + df.loc[has_id, AED_ID_COLUMN]
    for column in MAIN_AED_PROVENANCE_COLUMNS:
        df[column] = provenance.get(column, "")
    return df.reindex(columns=MAIN_AED_COLUMNS, fill_value="")


def create_main_aed_df(resources: Iterable["Resource"]) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Creates the aggregated AED DataFrame (MAIN_AED_COLUMNS) and the validation
    report (one entry per source resource).

    Resources which cannot be read or miss required columns are skipped (and
    reported). Rows with invalid values (e.g. coordinates, missing required
    values, values out of dictionary) are kept, but listed in the report.
    """
    frames: List[pd.DataFrame] = []
    report: List[Dict[str, Any]] = []

    resources = list(resources)
    for resource in resources:
        entry: Dict[str, Any] = {
            "resource_id": resource.pk,
            "resource_title": str(resource.title),
            "organization": "",
            "resource_url": "",
            "status": "ok",
            "reason": "",
            "missing_columns": [],
            "rows_count": 0,
            "invalid_rows_count": 0,
            "errors_count": 0,
            "errors": [],
        }
        report.append(entry)
        try:
            provenance: Dict[str, str] = get_aed_resource_provenance(resource)
            entry["organization"] = provenance[MAIN_AED_ORGANIZATION_COLUMN]
            entry["resource_url"] = provenance[MAIN_AED_SOURCE_URL_COLUMN]
            df: pd.DataFrame = get_aed_source_df(resource)
        except MainAEDResourceReadError as exc:
            sentry_sdk.api.capture_exception(exc)
            logger.error("Skipping Main AED source resource %s because it cannot be read: %s", resource.pk, exc)
            entry.update(status="skipped", reason=f"nie można odczytać zasobu: {exc}")
            continue
        except MainAEDMissingRequiredColumnError as exc:
            logger.error(
                "Skipping Main AED source resource %s because it is missing required column(s): %s.",
                resource.pk,
                ", ".join(exc.column_names),
            )
            entry.update(
                status="skipped",
                reason="brak wymaganych kolumn: " + ", ".join(exc.column_names),
                missing_columns=exc.column_names,
            )
            continue
        except Exception as exc:  # noqa: B902 - nie przerywaj agregacji z powodu jednego zasobu
            sentry_sdk.api.capture_exception(exc)
            logger.exception("Skipping Main AED source resource %s due to unexpected error: %s", resource.pk, exc)
            entry.update(status="skipped", reason=f"nieoczekiwany błąd: {exc}")
            continue

        validation: AEDValidationResult = validate_aed_rows(df)
        entry.update(
            rows_count=len(df),
            invalid_rows_count=len(validation.invalid_rows),
            errors_count=len(validation.errors),
            errors=validation.errors[:AED_VALIDATION_REPORT_MAX_ERRORS_PER_RESOURCE],
        )

        if df.empty:
            continue
        frames.append(add_aed_provenance_to_df(df, resource.pk, provenance))

    aggregated_count: int = sum(1 for entry in report if entry["status"] == "ok")
    logger.info(f"Successful AED Resources read: {aggregated_count}/{len(resources)}.")

    if frames:
        main_df: pd.DataFrame = pd.concat(frames, ignore_index=True)
    else:
        logger.warning("Empty main AED file.")
        main_df = pd.DataFrame(columns=MAIN_AED_COLUMNS)

    return main_df, report


def get_main_aed_stats(main_df: pd.DataFrame, report: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "source_resources_count": len(report),
        "aggregated_resources_count": sum(1 for entry in report if entry["status"] == "ok"),
        "rows_count": len(main_df),
        "invalid_rows_count": sum(entry["invalid_rows_count"] for entry in report),
        "geo_rows_count": int(get_valid_aed_coordinates_mask(main_df).sum()) if not main_df.empty else 0,
    }


# ---------------------------------------------------------------------------
# Main AED files (CSV, XLSX, GeoJSON)
# ---------------------------------------------------------------------------


def main_aed_df_to_geojson(main_df: pd.DataFrame) -> Dict[str, Any]:
    """Returns GeoJSON FeatureCollection with AED points (only rows with valid coordinates)."""
    features: List[Dict[str, Any]] = []
    if not main_df.empty:
        geo_df: pd.DataFrame = main_df[get_valid_aed_coordinates_mask(main_df)]
        for record in geo_df.to_dict(orient="records"):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(record[AED_LONGITUDE_COLUMN]), float(record[AED_LATITUDE_COLUMN])],
                    },
                    "properties": {key: value for key, value in record.items()},
                }
            )
    return {"type": "FeatureCollection", "features": features}


def get_or_create_main_aed_paths() -> Dict[str, Path]:
    directory: Path = Path(settings.MAIN_AED_RESOURCE_FILES_CREATION_ROOT)
    if not os.path.exists(directory):
        os.makedirs(directory)

    today_date: str = datetime.datetime.now().strftime("%Y%m%d")
    base_name: str = f"{settings.MAIN_AED_FILE_NAME_PREFIX} {today_date}"
    return {file_format: directory / f"{base_name}.{file_format}" for file_format in MAIN_AED_FORMATS}


def save_main_aed_files(main_df: pd.DataFrame, paths: Dict[str, Path]) -> None:
    main_df.to_csv(paths[MAIN_AED_CSV], index=False, encoding="utf-8")
    save_df_to_xlsx(df=main_df, file_path=paths[MAIN_AED_XLSX], sheet_name=settings.MAIN_AED_XLSX_WORKSHEET_NAME)
    with open(paths[MAIN_AED_GEOJSON], "w", encoding="utf-8") as geojson_file:
        json.dump(main_aed_df_to_geojson(main_df), geojson_file, ensure_ascii=False)


def key_generator_for_create_main_aed_files(*args, **kwargs) -> str:
    return "main_aed_files_to_clean"


@cache_memoize(
    timeout=settings.MAIN_AED_RESOURCE_FILES_CREATION_CACHE_TIMEOUT,
    hit_callable=lambda *args, **kwargs: logger.info("Using cache for main AED files."),
    key_generator_callable=key_generator_for_create_main_aed_files,
)
def create_main_aed_files() -> Dict[str, Any]:
    """
    Creates the main AED files (CSV, XLSX, GeoJSON) based on all AED resources.

    Returns:
        dict: {"paths": {format: path}, "stats": {...}, "validation_report": [...]}
    """
    paths: Dict[str, Path] = get_or_create_main_aed_paths()
    aed_resources: QuerySet = get_all_aed_resources_sorted_by_organizations()
    main_df, report = create_main_aed_df(aed_resources)
    save_main_aed_files(main_df, paths)
    return {
        "paths": {file_format: str(path) for file_format, path in paths.items()},
        "stats": get_main_aed_stats(main_df, report),
        "validation_report": report,
    }


# ---------------------------------------------------------------------------
# Main AED Dataset and Resources
# ---------------------------------------------------------------------------


def get_default_main_aed_dataset_categories() -> List["Category"]:  # noqa: F821
    """Retrieves the main AED dataset categories (e.g. "Zdrowie") by titles from the settings."""
    Category = apps.get_model("categories", "Category")
    categories_titles: List[str] = settings.MAIN_AED_DATASET_CATEGORIES_TITLES

    found_categories: QuerySet = Category.objects.filter(title__in=categories_titles)
    found_titles: Set[str] = set(category.title for category in found_categories)

    for missing_title in set(categories_titles) - found_titles:
        logger.warning(f"No category with title {missing_title} found.")

    return list(found_categories)


def get_or_create_default_main_aed_dataset_tags() -> List["Tag"]:  # noqa: F821
    """Retrieves or creates the main AED dataset tags ("AED", "defibrylator", "misja-aed")."""
    Tag = apps.get_model("tags", "Tag")
    pl_lang = settings.LANGUAGES[0][0]

    tags = []
    for tag_name in settings.MAIN_AED_DATASET_TAGS_NAMES:
        tag, created = Tag.objects.get_or_create(name=tag_name, language=pl_lang)
        if created:
            logger.info(f"Created Tag with name {tag_name}.")
        tags.append(tag)
    return tags


def create_main_aed_dataset() -> int:
    """
    Creates the main AED Dataset ("Wykaz zbiorczy defibrylatorów AED") owned by
    the institution configured in MAIN_AED_DATASET_OWNER_ORGANIZATION_PK.
    """
    Organization = apps.get_model("organizations", "Organization")
    Dataset = apps.get_model("datasets", "Dataset")

    organization_pk: int = settings.MAIN_AED_DATASET_OWNER_ORGANIZATION_PK
    try:
        institution = Organization.objects.get(pk=organization_pk)
    except Organization.DoesNotExist:
        logger.error(f"Can't create main AED dataset. Institution with pk {organization_pk} not found.")
        raise ObjectDoesNotExist("Main AED Owner Institution not found.")

    dataset_params = {
        "title": settings.MAIN_AED_DATASET_DEFAULT_TITLE,
        "notes": settings.MAIN_AED_DATASET_DEFAULT_DESC,
        "organization": institution,
        "update_notification_recipient_email": settings.MAIN_AED_DATASET_UPDATE_NOTIFICATION_EMAIL,
        "has_dynamic_data": False,
        "has_high_value_data": False,
        "has_high_value_data_from_ec_list": False,
        "has_research_data": False,
        "update_frequency": "daily",
        "status": "published",
    }

    with transaction.atomic():
        dataset = Dataset.objects.create(**dataset_params)
        dataset.categories.set(get_default_main_aed_dataset_categories())
        dataset.tags.set(get_or_create_default_main_aed_dataset_tags())
        dataset.save()

    logger.info(f"Created main AED dataset {dataset.pk}.")
    return dataset.pk


def key_generator_for_create_main_aed_resources(*args, **kwargs) -> str:
    return "main_aed_to_clean"


def _get_main_aed_resource_metadata(file_format: str, old_resource: Optional["Resource"]) -> Tuple[str, str]:
    if old_resource:
        return old_resource.title, old_resource.description
    if file_format == MAIN_AED_XLSX:
        return settings.MAIN_AED_XLSX_RESOURCE_DEFAULT_TITLE, settings.MAIN_AED_RESOURCE_DEFAULT_DESC
    if file_format == MAIN_AED_GEOJSON:
        return settings.MAIN_AED_GEOJSON_RESOURCE_DEFAULT_TITLE, settings.MAIN_AED_GEOJSON_RESOURCE_DEFAULT_DESC
    return settings.MAIN_AED_RESOURCE_DEFAULT_TITLE, settings.MAIN_AED_RESOURCE_DEFAULT_DESC


@cache_memoize(
    timeout=settings.MAIN_AED_RESOURCE_CREATION_CACHE_TIMEOUT,
    hit_callable=lambda *args, **kwargs: logger.info("AED objects get from cache."),
    key_generator_callable=key_generator_for_create_main_aed_resources,
)
def create_main_aed_resources_with_dataset(files_info: Dict[str, Any]) -> Tuple[Dict[str, int], Optional[int]]:
    """
    Creates the main AED Resources (CSV - main, XLSX, GeoJSON) with related
    ResourceFile objects and the main AED Dataset if it does not exist yet.

    Returns:
        Dict[str, int]: created Resources primary keys by format.
        Optional[int]: The Dataset primary key if created.
    """
    Resource = apps.get_model("resources", "Resource")
    ResourceFile = apps.get_model("resources", "ResourceFile")
    Dataset = apps.get_model("datasets", "Dataset")

    aed_info = get_aed_info()
    old_resources: Dict[str, Optional["Resource"]] = {
        MAIN_AED_CSV: aed_info.resource if aed_info else None,
        MAIN_AED_XLSX: aed_info.xlsx_resource if aed_info else None,
        MAIN_AED_GEOJSON: aed_info.geojson_resource if aed_info else None,
    }
    main_aed_dataset: Optional[Dataset] = get_main_aed_dataset()

    # Recover from a stale cached file paths left behind after cleanup.
    paths: Dict[str, str] = files_info["paths"]
    if not all(os.path.exists(path) for path in paths.values()):
        caches["default"].delete(key_generator_for_create_main_aed_files())
        logger.warning("Main AED files do not exist anymore. Regenerating them before resource creation.")
        files_info = create_main_aed_files()
        paths = files_info["paths"]

    for path in paths.values():
        if not os.path.exists(path):
            raise FileNotFoundError(path)

    new_main_aed_dataset_created: bool = False
    created_resources: Dict[str, int] = {}
    with transaction.atomic():
        if main_aed_dataset is None:
            main_aed_dataset_pk: int = create_main_aed_dataset()
            new_main_aed_dataset_created = True
            main_aed_dataset = Dataset.objects.get(pk=main_aed_dataset_pk)

        for file_format in MAIN_AED_FORMATS:
            title, description = _get_main_aed_resource_metadata(file_format, old_resources[file_format])
            resource_params = {
                "title": title,
                "description": description,
                "dataset": main_aed_dataset,
                "has_dynamic_data": False,
                "has_high_value_data": False,
                "has_high_value_data_from_ec_list": False,
                "has_research_data": False,
                "contains_protected_data": False,
                # Wykaz zbiorczy nie jest źródłem dla kolejnej agregacji.
                "contains_aed_list": False,
                # MISJA AED: jawny schemat tabeli (jak wzorzec) – portal nie zgaduje typów z pierwszych wierszy,
                # dzięki czemu walidacja i indeksowanie danych tabelarycznych przechodzą, a wykaz wyświetla się jako tabela.
                "tabular_data_schema": get_main_aed_tabular_schema() if file_format in ("csv", "xlsx") else None,
                "status": "published",
                "data_date": datetime.datetime.today(),
            }
            with open(paths[file_format], "rb") as file:
                file_name = os.path.basename(file.name)
                django_file = SimpleUploadedFile(
                    name=file_name,
                    content=file.read(),
                    content_type=MAIN_AED_MIMETYPES[file_format],
                )
                resource = Resource.objects.create(**resource_params)
                logger.debug(f"Created Main AED {file_format} resource {resource.pk}")

                # this will run post_save signal which runs all validation tasks
                resource_file = ResourceFile.objects.create(resource=resource, is_main=True, file=django_file)
                logger.debug(f"Created Main AED {file_format} resource file {resource_file.pk}")
            created_resources[file_format] = resource.pk

    return created_resources, main_aed_dataset.pk if new_main_aed_dataset_created else None


def update_or_create_aggr_aed_info_and_delete_old_main_aed(
    new_resources: Dict[str, "Resource"],
    files_info: Dict[str, Any],
) -> "AggregatedAEDInfo":
    """
    Updates or creates the AggregatedAEDInfo entry with the new main AED
    Resources and statistics, and deletes the old main AED Resources.
    """
    AggregatedAEDInfo = apps.get_model("resources", "AggregatedAEDInfo")
    aed_info: Optional[AggregatedAEDInfo] = AggregatedAEDInfo.objects.last()
    old_resources: List["Resource"] = []
    if aed_info:
        old_resources = [res for res in (aed_info.resource, aed_info.xlsx_resource, aed_info.geojson_resource) if res]

    stats: Dict[str, int] = files_info.get("stats", {})
    info_params: Dict[str, Any] = {
        "resource": new_resources[MAIN_AED_CSV],
        "xlsx_resource": new_resources.get(MAIN_AED_XLSX),
        "geojson_resource": new_resources.get(MAIN_AED_GEOJSON),
        "last_run_date": timezone.now(),
        "validation_report": files_info.get("validation_report", []),
        **stats,
    }

    new_resources_ids: Set[int] = {res.pk for res in new_resources.values() if res}
    with transaction.atomic():
        if aed_info:
            for field, value in info_params.items():
                setattr(aed_info, field, value)
            aed_info.save()
            logger.info(f"Updated AggregatedAEDInfo: {aed_info.pk} with resource: {aed_info.resource_id}.")
        else:
            aed_info = AggregatedAEDInfo.objects.create(**info_params)
            logger.info(f"Created AggregatedAEDInfo: {aed_info.pk} with resource: {aed_info.resource_id}.")

        for old_resource in old_resources:
            if old_resource.pk in new_resources_ids:
                continue
            old_resource.delete()
            logger.info(f"Previous Main AED Resource {old_resource.pk} deleted.")

    return aed_info


def clean_up_after_main_aed_resource_creation(exception_occurred: bool) -> None:
    """
    Cleans up objects created by the main AED task when it fails (Resources,
    ResourceFiles, Dataset) and always removes temporary files and releases
    the task cache.
    """
    logger.info("Starting clean up process after main AED Resources creation.")

    cache = caches["default"]
    clean_objects_key: str = key_generator_for_create_main_aed_resources()
    clean_files_key: str = key_generator_for_create_main_aed_files()

    resources_created: Optional[Dict[str, int]]
    dataset_created: Optional[int]
    resources_created, dataset_created = cache.get(clean_objects_key, (None, None))
    files_info: Optional[Dict[str, Any]] = cache.get(clean_files_key, None)

    try:
        if exception_occurred and resources_created:
            Resource = apps.get_model("resources", "Resource")
            Resource.raw.filter(pk__in=list(resources_created.values())).delete()

        if exception_occurred and dataset_created:
            Dataset = apps.get_model("datasets", "Dataset")
            Dataset.raw.filter(pk=dataset_created).delete()

        cache.delete(clean_objects_key)

    except Exception as exc:
        logger.error(f"Clean up failed. Reason: {exc}")
        sentry_sdk.api.capture_exception(exc)

    try:
        for file_path in (files_info or {}).get("paths", {}).values():
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"File {file_path} has been deleted successfully.")
            else:
                logger.warning(f"Main AED temp file {file_path} was already missing during cleanup.")
    except Exception as e:
        logger.error(f"An error occurred while deleting main AED files: {e}")
    finally:
        cache.delete(clean_files_key)

    logger.info("Clean up completed.")


def acquire_main_aed_task_lock() -> bool:
    """Prevents concurrent runs of the main AED task (beat + manual trigger)."""
    return caches["default"].add(MAIN_AED_TASK_LOCK_KEY, True, timeout=settings.MAIN_AED_TASK_LOCK_TIMEOUT)


def release_main_aed_task_lock() -> None:
    caches["default"].delete(MAIN_AED_TASK_LOCK_KEY)



# MISJA AED
def check_aed_resource_validations_status(resource: "Resource") -> None:  # noqa: F821
    """
    Wariant check_all_resource_validations_status dla wykazu zbiorczego AED.

    Ogólna walidacja danych tabelarycznych portalu zgaduje typy kolumn z pierwszych wierszy (np. „nr_budynku” jako
    liczba całkowita), więc puste komórki lub numery typu „28A” kończą ją błędem typu. Wykaz AED ma własną walidację
    według wzorcowego zakresu danych (validate_aed_rows), dlatego porażka walidacji typów NIE blokuje publikacji
    wykazu. Wymagamy jedynie zakończenia walidacji i poprawnej walidacji pliku oraz linku.
    """
    from mcod.resources.dga_utils import FailedValidationException, PendingValidationException

    resource.refresh_from_db()
    statuses = {"data": resource.data_tasks_last_status, "file": resource.file_tasks_last_status,
                "link": resource.link_tasks_last_status}
    if any(status == states.FAILURE for status in (statuses["file"], statuses["link"])):
        logger.error(f"AED: walidacja pliku/linku zasobu {resource.pk} nie powiodła się: {statuses}")
        raise FailedValidationException
    if all(status in (states.SUCCESS, states.FAILURE) for status in statuses.values()):
        if statuses["data"] == states.FAILURE:
            logger.warning(f"AED: walidacja typów danych zasobu {resource.pk} zgłosiła błędy – pomijam (walidacja AED wg wzorca).")
        return
    logger.info(f"AED: oczekiwanie na walidację zasobu {resource.pk}: {statuses}")
    raise PendingValidationException


# MISJA AED
def get_main_aed_tabular_schema() -> Dict[str, Any]:
    """
    Table Schema wykazu zbiorczego AED – wszystkie kolumny tekstowe.

    process_resource_file_data_task zachowuje podany schemat tylko, gdy jego "missingValues" jest równe
    resource.special_signs_symbols_list (dla nowego zasobu: []), w przeciwnym razie zgaduje typy na nowo.
    """
    return {
        "fields": [{"name": col, "type": "string", "format": "default"} for col in MAIN_AED_COLUMNS],
        "missingValues": [],
    }
