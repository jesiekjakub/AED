# MISJA AED
#
# Stałe dla mechanizmu "Wykaz zbiorczy AED" – wzorowane na `dga_constants.py`.
#
# Wzorcowy zakres danych (Table Schema) jest przechowywany w pliku
# `data/aed/tableschema_aed.json`. Każde pole posiada atrybut "poziom":
#   W - wymagane (kolumna musi wystąpić w zasobie dostawcy),
#   Z - zalecane,
#   O - opcjonalne,
#   A - dodawane wyłącznie przez agregator (nie przez dostawcę danych).
#
# Pojedynczy zasób AED dostawcy i zbiorczy wykaz AED nie mają identycznej
# struktury: wykaz zbiorczy zawiera dodatkowo kolumny pochodzenia danych
# (MAIN_AED_PROVENANCE_COLUMNS), dlatego listy są rozdzielone (tak jak w DGA).
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AED_RESOURCE_EXTENSIONS: List[str] = ["csv", "xlsx", "xls"]

AED_TABLESCHEMA_PATH: Path = Path(__file__).resolve().parents[2] / "data" / "aed" / "tableschema_aed.json"

AED_LEVEL_REQUIRED: str = "W"
AED_LEVEL_RECOMMENDED: str = "Z"
AED_LEVEL_OPTIONAL: str = "O"
AED_LEVEL_AGGREGATOR: str = "A"


def load_aed_tableschema(path: Path = AED_TABLESCHEMA_PATH) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as schema_file:
        return json.load(schema_file)


AED_TABLESCHEMA: Dict[str, Any] = load_aed_tableschema()
AED_SCHEMA_FIELDS: List[Dict[str, Any]] = AED_TABLESCHEMA["fields"]

# Kolumny wymagane (poziom "W") - muszą wystąpić w nagłówku zasobu dostawcy.
AED_REQUIRED_COLUMNS: List[str] = [field["name"] for field in AED_SCHEMA_FIELDS if field.get("poziom") == AED_LEVEL_REQUIRED]

# Kolumny, w których wartość nie może być pusta (constraints.required == true).
# Uwaga: np. `ulica` i `nr_budynku` są kolumnami wymaganymi (W), ale mogą
# mieć pustą wartość (miejscowości bez nazw ulic).
AED_REQUIRED_VALUE_COLUMNS: List[str] = [
    field["name"] for field in AED_SCHEMA_FIELDS if field.get("constraints", {}).get("required") is True
]

# Wszystkie kolumny, które może dostarczyć dostawca danych (bez poziomu "A").
AED_ALL_COLUMNS: List[str] = [field["name"] for field in AED_SCHEMA_FIELDS if field.get("poziom") != AED_LEVEL_AGGREGATOR]

# Kolumny wypełniane wyłącznie przez agregator.
AED_AGGREGATOR_COLUMNS: List[str] = [
    field["name"] for field in AED_SCHEMA_FIELDS if field.get("poziom") == AED_LEVEL_AGGREGATOR
]

# Słowniki wartości (constraints.enum), wzorce (constraints.pattern),
# zakresy liczbowe (constraints.minimum / maximum) oraz kolumny dat.
AED_ENUM_DICTIONARIES: Dict[str, List[str]] = {
    field["name"]: field["constraints"]["enum"]
    for field in AED_SCHEMA_FIELDS
    if field.get("poziom") != AED_LEVEL_AGGREGATOR and "enum" in field.get("constraints", {})
}
AED_PATTERNS: Dict[str, str] = {
    field["name"]: field["constraints"]["pattern"]
    for field in AED_SCHEMA_FIELDS
    if field.get("poziom") != AED_LEVEL_AGGREGATOR and "pattern" in field.get("constraints", {})
}
AED_NUMERIC_RANGES: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    field["name"]: (field["constraints"].get("minimum"), field["constraints"].get("maximum"))
    for field in AED_SCHEMA_FIELDS
    if field.get("poziom") != AED_LEVEL_AGGREGATOR
    and field.get("type") in ("number", "integer")
    and ({"minimum", "maximum"} & set(field.get("constraints", {}).keys()))
}
AED_DATE_COLUMNS: List[str] = [
    field["name"] for field in AED_SCHEMA_FIELDS if field.get("poziom") != AED_LEVEL_AGGREGATOR and field.get("type") == "date"
]
AED_DATE_FORMAT: str = "%Y-%m-%d"

AED_ID_COLUMN: str = "id_aed"
AED_LATITUDE_COLUMN: str = "szerokosc_geograficzna"
AED_LONGITUDE_COLUMN: str = "dlugosc_geograficzna"

# Kolumny pochodzenia danych dodawane przez agregator na początku wykazu.
MAIN_AED_ORGANIZATION_COLUMN: str = "Nazwa dysponenta"
MAIN_AED_SOURCE_URL_COLUMN: str = "Link do zasobu źródłowego"
MAIN_AED_SOURCE_MODIFIED_COLUMN: str = "Data aktualizacji zasobu"
MAIN_AED_PROVENANCE_COLUMNS: List[str] = [
    MAIN_AED_ORGANIZATION_COLUMN,
    MAIN_AED_SOURCE_URL_COLUMN,
    MAIN_AED_SOURCE_MODIFIED_COLUMN,
]

MAIN_AED_COLUMNS: List[str] = MAIN_AED_PROVENANCE_COLUMNS + AED_ALL_COLUMNS

# Identyfikator urządzenia w wykazie zbiorczym jest poprzedzany kodem źródła
# (zgodnie z opisem pola `id_aed` w schemacie), aby był unikalny w skali kraju.
MAIN_AED_ID_PREFIX_TEMPLATE: str = "R{resource_id}-"

# Kolumny raportu walidacji (wiersze błędne nie są usuwane z wykazu, ale są
# wymieniane w raporcie).
AED_VALIDATION_REPORT_COLUMNS: List[str] = [
    "resource_id",
    "organization",
    "row",
    "id_aed",
    "column",
    "error",
]

# Maksymalna liczba szczegółowych błędów przechowywanych w AggregatedAEDInfo
# dla jednego zasobu źródłowego (liczniki błędów są zawsze pełne).
AED_VALIDATION_REPORT_MAX_ERRORS_PER_RESOURCE: int = 100

AED_ERROR_MISSING_VALUE: str = "brak wymaganej wartości"
AED_ERROR_ENUM: str = "wartość spoza słownika"
AED_ERROR_PATTERN: str = "niepoprawny format wartości"
AED_ERROR_NUMBER: str = "wartość nie jest liczbą"
AED_ERROR_RANGE: str = "wartość poza dopuszczalnym zakresem"
AED_ERROR_DATE: str = "niepoprawna data (wymagany format RRRR-MM-DD)"
