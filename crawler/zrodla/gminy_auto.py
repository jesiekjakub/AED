"""Wyniki automatycznego przeszukania stron wszystkich gmin (crawler/odkrywanie_gmin.py) jako źródła danych."""
import json
from pathlib import Path

WYNIK = Path(__file__).resolve().parent.parent.parent / "dane_surowe" / "gminy" / "odkryte.json"
POMIN = {"Słupsk", "Sopot", "Czerwonak", "Kamienica Polska", "Pielgrzymka", "Radłów", "Tarnów Opolski", "Wiązowna", "Pawłowice",
         "Miasteczko Śląskie", "Doruchów", "Kołczygłowy", "Gorzyce", "Jelenia Góra", "Leszno", "Świętochłowice", "Nowy Sącz", "Chełm",
         "Łódź", "Kraków", "Lublin", "Gdańsk", "Olsztyn", "Koszalin", "Krosno", "Przemyśl", "Marki", "Legionowo", "Siemianowice Śląskie",
         "Piotrków Trybunalski", "Wrocław"}   # gminy obsługiwane dedykowanymi adapterami / ręczną konfiguracją


def pobierz():
    if not WYNIK.exists():
        print("  (brak wyników przeszukania gmin – uruchom: python -m crawler gminy)")
        return []
    wynik = []
    for g in json.loads(WYNIK.read_text(encoding="utf-8")):
        if not g.get("rekordy") or g["nazwa"] in POMIN:
            continue
        rekordy = []
        for i, r in enumerate(g["rekordy"], 1):
            rek = {k: v for k, v in r.items() if not k.startswith("_")}
            rek.update(id_zrodlowe=str(i), _tekst_opisowy=r.get("_tekst_opisowy", ""), _obszar={"teryt_prefiks": g["teryt"]},
                       _odrzuc_bez_prg=True, _flagi=["pozyskano_automatycznie_ze_strony_gminy"])
            rekordy.append(rek)
        meta = {"zrodlo_id": f"GMINA-{g['teryt']}", "dostawca_danych": f"Gmina {g['nazwa']} (strona www urzędu)",
                "zrodlo_url": g["strony_z_lista"][0], "zbior_url": g["strony_z_lista"][0],
                "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": "", "miejscowosc": g["nazwa"],
                "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
        wynik.append((meta, rekordy))
    print(f"  Przeszukanie gmin: {len(wynik)} gmin z wykazem AED, {sum(len(r) for _, r in wynik)} rekordów")
    return wynik
