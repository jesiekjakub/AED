# MISJA AED - testy walidacji i agregacji wykazów AED (wzorowane na test_dga_utils.py)
import datetime
import json
from io import BytesIO
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from django.conf import settings

from mcod.resources.aed_constants import (
    AED_ALL_COLUMNS,
    AED_ERROR_DATE,
    AED_ERROR_ENUM,
    AED_ERROR_MISSING_VALUE,
    AED_ERROR_RANGE,
    AED_REQUIRED_COLUMNS,
    AED_TABLESCHEMA,
    MAIN_AED_COLUMNS,
    MAIN_AED_ORGANIZATION_COLUMN,
    MAIN_AED_PROVENANCE_COLUMNS,
    MAIN_AED_SOURCE_MODIFIED_COLUMN,
    MAIN_AED_SOURCE_URL_COLUMN,
)
from mcod.resources.aed_utils import (
    MAIN_AED_CSV,
    MAIN_AED_GEOJSON,
    MAIN_AED_XLSX,
    create_df_from_aed_file,
    create_main_aed_df,
    get_main_aed_stats,
    get_missing_aed_required_columns,
    get_missing_aed_required_columns_in_file,
    main_aed_df_to_geojson,
    normalize_aed_source_df,
    save_main_aed_files,
    validate_aed_df_columns,
    validate_aed_file_columns,
    validate_aed_rows,
)

COMMA_SAMPLE = "aed_gmina_przykladowo_comma.csv"
SEMICOLON_SAMPLE = "aed_powiat_przykladowy_semicolon.csv"


def aed_sample_path(file_name: str) -> Path:
    return Path(settings.TEST_SAMPLES_PATH) / "aed" / file_name


def read_aed_sample(file_name: str) -> BytesIO:
    with open(aed_sample_path(file_name), "rb") as sample:
        return BytesIO(sample.read())


def mock_aed_resource(pk: int, file_name: str, organization_title: str) -> MagicMock:
    resource = MagicMock()
    resource.pk = pk
    resource.title = f"Wykaz AED {organization_title}"
    resource.main_file.path = str(aed_sample_path(file_name))
    resource.main_file.name = f"resources/20261122/{file_name}"
    resource.institution.title = organization_title
    resource.frontend_absolute_url = f"https://dane.gov.pl/pl/dataset/1/resource/{pk}"
    resource.modified = datetime.datetime(2026, 11, 20, 10, 30)
    return resource


@pytest.mark.feat_main_aed
def test_aed_required_columns_are_w_level_fields_of_tableschema():
    expected: List[str] = [field["name"] for field in AED_TABLESCHEMA["fields"] if field["poziom"] == "W"]
    assert AED_REQUIRED_COLUMNS == expected
    assert "id_aed" in AED_REQUIRED_COLUMNS
    assert "szerokosc_geograficzna" in AED_REQUIRED_COLUMNS
    # optional / recommended columns are not required
    assert "numer_seryjny" not in AED_REQUIRED_COLUMNS
    assert "typ_obiektu" not in AED_REQUIRED_COLUMNS


@pytest.mark.feat_main_aed
def test_main_aed_columns_structure():
    aggregator_columns = [field["name"] for field in AED_TABLESCHEMA["fields"] if field["poziom"] == "A"]
    assert MAIN_AED_COLUMNS[:3] == ["Nazwa dysponenta", "Link do zasobu źródłowego", "Data aktualizacji zasobu"]
    assert MAIN_AED_COLUMNS[3:] == AED_ALL_COLUMNS
    assert not set(aggregator_columns) & set(AED_ALL_COLUMNS)


@pytest.mark.feat_main_aed
@pytest.mark.parametrize("file_name", [COMMA_SAMPLE, SEMICOLON_SAMPLE])
def test_create_df_from_aed_csv_file_comma_and_semicolon(file_name: str):
    df = create_df_from_aed_file(read_aed_sample(file_name), "csv")

    assert df is not None
    assert len(df) in (2, 3)
    assert validate_aed_df_columns(df)
    assert df.loc[0, "nazwa_obiektu"]


@pytest.mark.feat_main_aed
@pytest.mark.parametrize("file_name", [COMMA_SAMPLE, SEMICOLON_SAMPLE])
def test_validate_aed_file_columns_for_sample_files(file_name: str):
    assert validate_aed_file_columns(read_aed_sample(file_name), "csv") is True


@pytest.mark.feat_main_aed
def test_validate_aed_file_columns_xlsx():
    df = create_df_from_aed_file(read_aed_sample(SEMICOLON_SAMPLE), "csv")
    xlsx_file = BytesIO()
    df.to_excel(xlsx_file, index=False, engine="openpyxl")
    xlsx_file.seek(0)

    assert validate_aed_file_columns(xlsx_file, "xlsx") is True


@pytest.mark.feat_main_aed
def test_get_missing_aed_required_columns_in_file():
    content = "id_aed;nazwa_obiektu;miejscowosc;uwagi\nA-1;Szkoła;Łódź;\n".encode("utf-8")

    missing_columns = get_missing_aed_required_columns_in_file(BytesIO(content), "csv")

    assert missing_columns == [column for column in AED_REQUIRED_COLUMNS if column not in ("id_aed", "nazwa_obiektu", "miejscowosc")]
    assert validate_aed_file_columns(BytesIO(content), "csv") is False


@pytest.mark.feat_main_aed
def test_get_missing_aed_required_columns_ignores_case_and_whitespace():
    df = pd.DataFrame(columns=[f" {column.upper()} " for column in AED_REQUIRED_COLUMNS])
    assert get_missing_aed_required_columns(df) == []


@pytest.mark.feat_main_aed
@pytest.mark.parametrize("extension", ["json", "txt", None])
def test_validate_aed_file_columns_unsupported_extension(extension):
    assert get_missing_aed_required_columns_in_file(read_aed_sample(COMMA_SAMPLE), extension) is None
    assert validate_aed_file_columns(read_aed_sample(COMMA_SAMPLE), extension) is False


@pytest.mark.feat_main_aed
def test_normalize_aed_source_df_drops_unknown_and_adds_missing_columns():
    df = create_df_from_aed_file(read_aed_sample(SEMICOLON_SAMPLE), "csv")
    assert "notatka_wewnetrzna" in df.columns

    normalized = normalize_aed_source_df(df)

    assert normalized.columns.to_list() == AED_ALL_COLUMNS
    assert "notatka_wewnetrzna" not in normalized.columns
    # missing optional column added with empty values
    assert normalized["numer_seryjny"].eq("").all()
    # decimal comma in coordinates replaced with dot
    assert normalized.loc[0, "szerokosc_geograficzna"] == "53.123456"
    assert normalized.loc[0, "dlugosc_geograficzna"] == "20.654321"


@pytest.mark.feat_main_aed
def test_validate_aed_rows_reports_invalid_rows_but_keeps_them():
    df = normalize_aed_source_df(create_df_from_aed_file(read_aed_sample(COMMA_SAMPLE), "csv"))

    result = validate_aed_rows(df)

    # all rows are kept
    assert len(df) == 3
    # row 0 (SP3-001) is valid; "Aktywny" in row 1 is normalized to "aktywny"
    assert df.loc[1, "status"] == "aktywny"
    assert result.invalid_rows == {1, 2}

    errors = {(error["id_aed"], error["column"], error["error"]) for error in result.errors}
    assert ("UM-014", "szerokosc_geograficzna", AED_ERROR_RANGE) in errors
    assert ("OSIR-2", "opis_lokalizacji", AED_ERROR_MISSING_VALUE) in errors
    assert ("OSIR-2", "dostep", AED_ERROR_ENUM) in errors
    assert ("OSIR-2", "data_weryfikacji", AED_ERROR_DATE) in errors
    # row numbers are line numbers in the source file (header = 1)
    assert {error["row"] for error in result.errors} == {3, 4}


@pytest.mark.feat_main_aed
def test_validate_aed_rows_allows_empty_street_and_building_number():
    df = normalize_aed_source_df(create_df_from_aed_file(read_aed_sample(SEMICOLON_SAMPLE), "csv"))
    assert df.loc[1, "ulica"] == ""

    result = validate_aed_rows(df)

    assert result.errors == []
    assert result.invalid_rows == set()


@pytest.mark.feat_main_aed
def test_create_main_aed_df_aggregates_two_resources_with_provenance():
    # GIVEN
    resources = [
        mock_aed_resource(11, COMMA_SAMPLE, "Gmina Przykładowo"),
        mock_aed_resource(22, SEMICOLON_SAMPLE, "Powiat Przykładowy"),
    ]

    # WHEN
    main_df, report = create_main_aed_df(resources)

    # THEN
    assert main_df.columns.to_list() == MAIN_AED_COLUMNS
    assert len(main_df) == 5
    assert main_df[MAIN_AED_ORGANIZATION_COLUMN].to_list() == ["Gmina Przykładowo"] * 3 + ["Powiat Przykładowy"] * 2
    assert main_df[MAIN_AED_SOURCE_URL_COLUMN].to_list() == [resources[0].frontend_absolute_url] * 3 + [
        resources[1].frontend_absolute_url
    ] * 2
    assert main_df[MAIN_AED_SOURCE_MODIFIED_COLUMN].unique().tolist() == ["2026-11-20"]
    # id_aed is prefixed with source code
    assert main_df["id_aed"].to_list() == ["R11-SP3-001", "R11-UM-014", "R11-OSIR-2", "R22-SP-01", "R22-SP-02"]
    # unknown column dropped
    assert "notatka_wewnetrzna" not in main_df.columns

    assert [entry["resource_id"] for entry in report] == [11, 22]
    assert [entry["status"] for entry in report] == ["ok", "ok"]
    assert report[0]["rows_count"] == 3
    assert report[0]["invalid_rows_count"] == 2
    assert report[1]["invalid_rows_count"] == 0

    stats = get_main_aed_stats(main_df, report)
    assert stats == {
        "source_resources_count": 2,
        "aggregated_resources_count": 2,
        "rows_count": 5,
        "invalid_rows_count": 2,
        "geo_rows_count": 4,
    }


@pytest.mark.feat_main_aed
def test_create_main_aed_df_skips_resource_with_missing_required_columns(tmp_path: Path):
    invalid_file = tmp_path / "invalid_aed.csv"
    invalid_file.write_text("id_aed,nazwa_obiektu\nX-1,Szkoła\n", encoding="utf-8")
    invalid_resource = mock_aed_resource(33, COMMA_SAMPLE, "Gmina Bez Kolumn")
    invalid_resource.main_file.path = str(invalid_file)
    invalid_resource.main_file.name = "resources/invalid_aed.csv"

    main_df, report = create_main_aed_df([invalid_resource, mock_aed_resource(22, SEMICOLON_SAMPLE, "Powiat Przykładowy")])

    assert len(main_df) == 2
    assert report[0]["status"] == "skipped"
    assert "status" in report[0]["missing_columns"]
    assert report[1]["status"] == "ok"


@pytest.mark.feat_main_aed
def test_create_main_aed_df_skips_unreadable_resource():
    resource = mock_aed_resource(44, COMMA_SAMPLE, "Gmina")
    resource.main_file.path = "/not/existing/file.csv"

    with patch("mcod.resources.aed_utils.sentry_sdk"):
        main_df, report = create_main_aed_df([resource])

    assert main_df.empty
    assert main_df.columns.to_list() == MAIN_AED_COLUMNS
    assert report[0]["status"] == "skipped"


@pytest.mark.feat_main_aed
def test_main_aed_df_to_geojson_contains_only_valid_coordinates():
    main_df, _ = create_main_aed_df([mock_aed_resource(11, COMMA_SAMPLE, "Gmina Przykładowo")])

    geojson = main_aed_df_to_geojson(main_df)

    assert geojson["type"] == "FeatureCollection"
    # UM-014 has latitude out of range (61.22)
    assert [feature["properties"]["id_aed"] for feature in geojson["features"]] == ["R11-SP3-001", "R11-OSIR-2"]
    assert geojson["features"][0]["geometry"] == {"type": "Point", "coordinates": [19.4805, 51.709489]}


@pytest.mark.feat_main_aed
def test_save_main_aed_files(tmp_path: Path):
    main_df, _ = create_main_aed_df(
        [
            mock_aed_resource(11, COMMA_SAMPLE, "Gmina Przykładowo"),
            mock_aed_resource(22, SEMICOLON_SAMPLE, "Powiat Przykładowy"),
        ]
    )
    paths = {
        MAIN_AED_CSV: tmp_path / "aed.csv",
        MAIN_AED_XLSX: tmp_path / "aed.xlsx",
        MAIN_AED_GEOJSON: tmp_path / "aed.geojson",
    }

    save_main_aed_files(main_df, paths)

    csv_df = pd.read_csv(paths[MAIN_AED_CSV], dtype=str, keep_default_na=False)
    assert csv_df.columns.to_list() == MAIN_AED_COLUMNS
    assert len(csv_df) == 5
    xlsx_df = pd.read_excel(paths[MAIN_AED_XLSX], dtype=str)
    assert xlsx_df.columns.to_list() == MAIN_AED_COLUMNS
    assert len(xlsx_df) == 5
    with open(paths[MAIN_AED_GEOJSON], encoding="utf-8") as geojson_file:
        assert len(json.load(geojson_file)["features"]) == 4
    assert set(MAIN_AED_PROVENANCE_COLUMNS) <= set(csv_df.columns)
