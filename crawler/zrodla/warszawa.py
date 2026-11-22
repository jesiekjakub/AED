"""Warszawa: API dane.um.warszawa.pl (zbiór dane.gov.pl #39512). Wymaga darmowego tokenu – zmienna AED_WARSZAWA_TOKEN."""
import json
import os

from ..siec import pobierz as pobierz_plik

API = "https://dane.um.warszawa.pl/api/action/get_scb_lokalizacja_defibrylatorow"

MAPA_DOSTEP = {"publiczny": "publiczny", "ograniczony": "dla_klientow_pracownikow", "prywatny": "prywatny"}


def pobierz():
    token = os.environ.get("AED_WARSZAWA_TOKEN")
    if not token:
        print("  Warszawa: pominięto – brak tokenu (ustaw AED_WARSZAWA_TOKEN; rejestracja na dane.um.warszawa.pl)")
        return []
    p = pobierz_plik(API, "warszawa/api.json", metoda="POST", naglowki={"Authorization": token})
    dane = json.loads(p.read_text(encoding="utf-8-sig"))
    if isinstance(dane, dict):
        dane = dane.get("result") or dane.get("data") or dane.get("features") or []
    rekordy = []
    for f in dane:
        pr = f.get("properties", {})
        c = f.get("geometry", {}).get("coordinates") or []
        while c and isinstance(c[0], list):
            c = c[0]
        r = {"id_zrodlowe": str(pr.get("defibrillator_id", "")), "nazwa_obiektu": pr.get("location_object_name", ""),
             "ulica": pr.get("location_street", ""), "nr_budynku": pr.get("location_building", ""),
             "kod_pocztowy": pr.get("location_postcode", ""), "miejscowosc": pr.get("location_city", "Warszawa"),
             "opis_lokalizacji": pr.get("location_description", ""), "godziny_opis": pr.get("device_access_description", ""),
             "producent": pr.get("device_manufacturer", ""), "zrodlo_wspolrzednych": "mapa_dysponenta",
             "_tekst_opisowy": f"{pr.get('location_object_name', '')} {pr.get('location_description', '')} {pr.get('device_location', '')}",
             "_flagi": []}
        if c:
            r["dlugosc_geograficzna"], r["szerokosc_geograficzna"] = float(c[0]), float(c[1])
        loc = (pr.get("device_location") or "").lower()
        r["wewnatrz_budynku"] = "tak" if "wewn" in loc else ("nie" if "zewn" in loc else "nieznane")
        dost = (pr.get("device_public_access") or "").lower()
        if dost in MAPA_DOSTEP:
            r["dostep"] = MAPA_DOSTEP[dost]
        av = (pr.get("device_availability") or "").lower()
        if "24" in av or "całodob" in av:
            r.update(dostepny_24_7="tak", godziny_dostepnosci="24/7")
        elif av:
            r["dostepny_24_7"] = "nie"
        rekordy.append(r)
    print(f"  Warszawa: {len(rekordy)} rekordów z API")
    meta = {"zrodlo_id": "DGP-WAW", "dostawca_danych": "Urząd m.st. Warszawy", "zrodlo_url": API, "zbior_url": "https://dane.gov.pl/pl/dataset/39512",
            "licencja_zrodla": "CC BY 4.0", "data_stanu_zrodla": "", "miejscowosc": "Warszawa",
            "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
    return [(meta, rekordy)]
