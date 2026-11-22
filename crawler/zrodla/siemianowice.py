"""Siemianowice Śląskie: aed.siemianowice.pl publikuje plik aed-dane.csv (dane mapy miejskiej) – współrzędne, dostęp, godziny."""
import csv
import io

from ..normalizacja import tekst
from ..siec import pobierz as pobierz_plik

STRONA = "https://aed.siemianowice.pl/"
CSV = "https://aed.siemianowice.pl/aed-dane.csv"


def pobierz():
    t = pobierz_plik(CSV, "siemianowice/aed-dane.csv").read_text(encoding="utf-8-sig")
    rekordy = []
    for i, w in enumerate(csv.DictReader(io.StringIO(t)), 1):
        w = {k: tekst(v) for k, v in w.items()}
        r = {"id_zrodlowe": str(i), "nazwa_obiektu": w.get("Obiekt", ""), "_adres": w.get("Adres", ""), "opis_lokalizacji": w.get("Miejsce_AED", ""),
             "godziny_opis": w.get("Godziny", ""), "zrodlo_wspolrzednych": "mapa_dysponenta", "_flagi": [],
             "_tekst_opisowy": f"{w.get('Kategoria', '')} {w.get('Obiekt', '')} {w.get('Miejsce_AED', '')} {w.get('Godziny', '')}"}
        try:
            r["szerokosc_geograficzna"], r["dlugosc_geograficzna"] = float(w["Szerokosc_geogr"]), float(w["Dlugosc_geogr"])
        except (KeyError, ValueError):
            pass
        dp = w.get("Dostep_publiczny", "").lower()
        r["dostep"] = "publiczny" if dp == "tak" else ("dla_klientow_pracownikow" if dp == "nie" else "")
        if w.get("Tryb_dostepnosci", "").lower() == "24h":
            r.update(godziny_dostepnosci="24/7", dostepny_24_7="tak")
        rekordy.append({k: v for k, v in r.items() if v != ""})
    print(f"  Siemianowice Śląskie: {len(rekordy)} rekordów z CSV")
    meta = {"zrodlo_id": "JST-SIEMIANOWICE", "dostawca_danych": "Urząd Miasta Siemianowice Śląskie", "zrodlo_url": CSV, "zbior_url": STRONA,
            "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": "", "miejscowosc": "Siemianowice Śląskie",
            "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
    return [(meta, rekordy)]
