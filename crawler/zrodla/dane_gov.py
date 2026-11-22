"""dane.gov.pl – automatyczne wykrywanie zbiorów i zasobów o AED przez API portalu oraz uniwersalne mapowanie kolumn.

Nowy zbiór AED opublikowany na portalu zostanie wciągnięty bez zmian w kodzie, o ile ma zasób CSV/GeoJSON.
"""
import csv
import io
import json
import re
import urllib.parse

from ..geokoder import bez_ogonkow
from ..normalizacja import tekst
from ..siec import pobierz as pobierz_plik

API = "https://api.dane.gov.pl/1.4"
ZAPYTANIA = ["defibrylator", "defibrylatory", "defibrylatorów", "AED", "automatyczny defibrylator zewnętrzny"]
WZORZEC = re.compile(r"defibr|\bAED\b", re.I)
# znane zbiory -> kody z rejestru źródeł
# zbiory obsługiwane osobnym adapterem (np. API z tokenem)
POMIN = {"39512": "Warszawa – osobny adapter (API z tokenem)"}
KODY = {"39512": "DGP-WAW", "4581": "DGP-PRZ", "3624": "DGP-KRO", "4955": "DGP-MAR", "40593": "DGP-LEG", "1803": "DGP-ZTMGDA"}


def _json(url: str, nazwa: str) -> dict:
    p = pobierz_plik(url, nazwa, naglowki={"Accept": "application/json"})
    return json.loads(p.read_text(encoding="utf-8"))


def _czysc(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def odkryj_zasoby() -> list[dict]:
    """Zwraca listę zasobów: {dataset_id, dataset_tytul, instytucja, licencja, zmodyfikowano, resource_id, tytul, format, url}."""
    zbiory = {}
    for q in ZAPYTANIA:
        for typ in ("datasets", "resources"):
            url = f"{API}/{typ}?" + urllib.parse.urlencode({"q": q, "per_page": 100})
            d = _json(url, f"dane_gov/szukaj_{typ}_{bez_ogonkow(q).replace(' ', '_')}.json")
            for it in d.get("data", []):
                a = it["attributes"]
                if not WZORZEC.search(_czysc(a.get("title")) + " " + _czysc(a.get("description") or a.get("notes"))):
                    continue
                if typ == "datasets":
                    zbiory.setdefault(it["id"], set())
                else:
                    ds = (it.get("relationships", {}).get("dataset", {}).get("data") or {}).get("id")
                    if ds:
                        zbiory.setdefault(ds, set()).add(it["id"])
    zasoby = []
    for ds_id, tylko in zbiory.items():
        d = _json(f"{API}/datasets/{ds_id}?include=institution", f"dane_gov/zbior_{ds_id}.json")
        a = d["data"]["attributes"]
        inst = next((x["attributes"]["title"] for x in d.get("included", []) if x["type"] == "institution"), "")
        r = _json(f"{API}/datasets/{ds_id}/resources?per_page=100", f"dane_gov/zasoby_{ds_id}.json")
        for it in r.get("data", []):
            ra = it["attributes"]
            if tylko and it["id"] not in tylko:      # zbiór ogólny (np. 'Zdrowie') – bierzemy tylko zasoby o AED
                continue
            zasoby.append({
                "dataset_id": ds_id, "dataset_tytul": _czysc(a.get("title")), "instytucja": inst,
                "licencja": a.get("license_name") or a.get("license_chosen") or "", "zmodyfikowano": (ra.get("data_date") or a.get("modified") or "")[:10],
                "resource_id": it["id"], "tytul": _czysc(ra.get("title")), "format": (ra.get("format") or "").lower(),
                "url": ra.get("link") or ra.get("file_url") or "", "dataset_url": f"https://dane.gov.pl/pl/dataset/{ds_id}",
            })
    return zasoby


# ------------------------------------------------------------------ mapowanie kolumn
def _klucz(nazwa: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", bez_ogonkow(nazwa.strip().lower())).strip("_")


ALIASY = {
    "dlugosc": {"dlugosc_geograficzna", "dlugosc", "lon", "lng", "longitude", "x", "wsp_x"},
    "szerokosc": {"szerokosc_geograficzna", "szerokosc", "lat", "latitude", "y", "wsp_y"},
    "geometria": {"geometry", "geometria", "geom"},
    "lokalizacja": {"lokalizacja", "obiekt", "location_object_name", "nazwa_obiektu"},
    "nazwa": {"nazwa", "name", "title"},
    "adres": {"adres", "address"},
    "cecha": {"cecha_ulicy", "cecha"},
    "ulica": {"nazwa_ulicy", "ulica", "street", "location_street"},
    "nr": {"nr_budynku", "numer_budynku", "home_number", "nr_domu", "location_building"},
    "kod": {"kod_pocztowy", "postcode", "kod", "location_postcode"},
    "miejscowosc": {"miejscowosc", "city", "miasto", "location_city"},
    "terc": {"kod_terc", "teryt", "terc"},
    "simc": {"kod_simc", "simc"},
    "id": {"numer_id", "id", "lp", "identyfikator"},
    "opis": {"description", "opis", "location_description"},
    "zdjecia": {"gallery", "zdjecie", "foto"},
    "telefon": {"phone", "telefon"},
    "email": {"email", "e_mail"},
}


def _mapuj_naglowki(naglowki):
    mapa = {}
    for h in naglowki:
        k = _klucz(h)
        for cel, al in ALIASY.items():
            if k in al and cel not in mapa:
                mapa[cel] = h
    return mapa


def _wczytaj_csv(sciezka) -> tuple[list[dict], list[str]]:
    raw = sciezka.read_bytes()
    for kod in ("utf-8-sig", "cp1250"):
        try:
            txt = raw.decode(kod)
            break
        except UnicodeDecodeError:
            continue
    flagi = []
    linie = txt.splitlines()
    # naprawa: cały wiersz opakowany w cudzysłów z podwojonymi cudzysłowami w środku (przypadek Marek)
    if linie and all(l.startswith('"') and l.endswith('"') for l in linie if l.strip()) and sum('""' in l for l in linie) > len(linie) / 2:
        linie = [l[1:-1].replace('""', '"') for l in linie]
        flagi.append("csv_blednie_zacytowany_naprawiono")
    txt = "\n".join(linie)
    dialekt = csv.Sniffer().sniff(linie[0], delimiters=",;\t|")
    wiersze = list(csv.DictReader(io.StringIO(txt), dialect=dialekt, skipinitialspace=True))
    return [{(k or "").strip(): tekst(v) for k, v in w.items()} for w in wiersze], flagi


def _wiersz_na_rekord(w: dict, m: dict) -> dict:
    g = lambda k: w.get(m[k], "") if k in m else ""  # noqa: E731
    r = {"_flagi": []}
    lat, lon = g("szerokosc"), g("dlugosc")
    if not (lat and lon) and g("geometria"):
        try:
            geo = json.loads(g("geometria"))
            c = geo["coordinates"]
            while isinstance(c[0], list):
                c = c[0]
            lon, lat = c[0], c[1]
        except Exception:  # noqa: BLE001
            pass
    try:
        r["szerokosc_geograficzna"], r["dlugosc_geograficzna"] = float(str(lat).replace(",", ".")), float(str(lon).replace(",", "."))
    except ValueError:
        pass
    nazwa, lok = g("nazwa"), g("lokalizacja")
    if nazwa.lower() in ("defibrylator", "aed", "defibrylator aed"):
        nazwa = ""
    obiekt = lok or nazwa
    m_aed = re.match(r"(?i)defibrylator\s*\((AED\s*\d+)\)\s*[-–]?\s*(?:w\s+)?(.*)", obiekt)   # Przemyśl
    if m_aed:
        r["uwagi"] = f"Oznaczenie urządzenia w źródle: {m_aed.group(1)}"
        obiekt = m_aed.group(2)
    # 'Kampus X, portiernia' -> obiekt + opis miejsca
    if lok and "," in lok:
        obiekt, opis_m = lok.rsplit(",", 1)
        r["opis_lokalizacji"] = opis_m.strip()
    nawias = re.search(r"\(([^)]+)\)\s*$", obiekt)
    if nawias and re.match(r"(?i)(ul\.|al\.|plac|aleje|rynek|\d|[A-ZŁŚŻŹ][a-ząęółśżźćń]+ \d)", obiekt):  # 'ul. Wodna 11 (Budynek Urzędu)'
        r["_adres"] = obiekt[:nawias.start()].strip()
        obiekt = nawias.group(1)
    r["nazwa_obiektu"] = tekst(obiekt)
    opis = g("opis")
    if opis and not (len(opis) > 300 and "Automated External" in opis):
        r["opis_lokalizacji"] = opis
    if g("ulica"):
        cecha = g("cecha")
        cecha = {"ulica": "ul.", "aleja": "al.", "plac": "pl.", "osiedle": "os."}.get(cecha.lower(), cecha)
        r["ulica"] = f"{cecha} {g('ulica')}".strip()
        r["nr_budynku"] = g("nr")
        r["kod_pocztowy"] = g("kod")
        r["miejscowosc"] = g("miejscowosc")
    elif g("adres"):
        r["_adres"] = g("adres")
    if g("terc"):
        r["teryt_gmina"] = g("terc")
    if g("simc"):
        r["simc"] = g("simc").zfill(7)
    r["id_zrodlowe"] = g("id")
    zd = re.search(r"https?://[^\s\]\[]+", g("zdjecia"))
    if zd:
        r["zdjecie_url"] = zd.group(0)
    kontakt = "; ".join(x for x in (g("telefon"), g("email")) if x)
    if kontakt:
        r["kontakt"] = kontakt
    r["_tekst_opisowy"] = " ".join(x for x in (obiekt, r.get("opis_lokalizacji", ""), lok, nazwa) if x)
    return r


PRIORYTET_FORMATU = ["csv", "geojson", "json", "xlsx"]


def pobierz() -> list[tuple[dict, list[dict]]]:
    zasoby = odkryj_zasoby()
    print(f"  dane.gov.pl: wykryto {len({z['dataset_id'] for z in zasoby})} zbiorów, {len(zasoby)} zasobów")
    wynik = []
    for ds_id in sorted({z["dataset_id"] for z in zasoby}, key=int):
        if ds_id in POMIN:
            print(f"  dane.gov.pl #{ds_id}: {POMIN[ds_id]}")
            continue
        try:
            wynik.extend(_przetworz_zbior(ds_id, zasoby))
        except Exception as e:  # noqa: BLE001 – jeden zepsuty zbiór nie zatrzymuje całości
            print(f"  ! dane.gov.pl #{ds_id}: błąd przetwarzania: {e}")
    return wynik


def _przetworz_zbior(ds_id, zasoby):
    kandydaci = [z for z in zasoby if z["dataset_id"] == ds_id and z["format"] in PRIORYTET_FORMATU and z["url"]]
    kandydaci.sort(key=lambda z: PRIORYTET_FORMATU.index(z["format"]))
    if not kandydaci:
        print(f"  dane.gov.pl #{ds_id}: brak zasobu CSV/GeoJSON – pominięto (np. API z tokenem)")
        return []
    z = kandydaci[0]
    kod = KODY.get(ds_id, f"DGP-{ds_id}")
    sciezka = pobierz_plik(z["url"], f"dane_gov/{kod}_{z['resource_id']}.{z['format']}")
    if z["format"] == "csv":
        wiersze, flagi_pliku = _wczytaj_csv(sciezka)
    else:
        geo = json.loads(sciezka.read_text(encoding="utf-8-sig"))
        if isinstance(geo, dict) and isinstance(geo.get("results"), list) and geo["results"] and "aed" in geo["results"][0]:
            return _pojazdy_z_aed(geo, z, kod)
        if not (isinstance(geo, dict) and geo.get("type") == "FeatureCollection"):
            print(f"  dane.gov.pl #{ds_id}: zasób JSON w nieobsługiwanej strukturze – pominięto")
            return []
        wiersze = [{**f.get("properties", {}), "geometry": json.dumps(f.get("geometry"))} for f in geo.get("features", [])]
        flagi_pliku = []
    m = _mapuj_naglowki(list(wiersze[0].keys()) if wiersze else [])
    miasto = re.sub(r"^Urząd (Miasta|Miejski w|m\.st\.)\s*", "", z["instytucja"]).strip()
    miasto = {"Krosna": "Krosno", "Przemyślu": "Przemyśl", "Warszawy": "Warszawa"}.get(miasto, miasto)
    meta = {
        "zrodlo_id": kod, "dostawca_danych": z["instytucja"], "zrodlo_url": z["url"], "zbior_url": z["dataset_url"],
        "licencja_zrodla": z["licencja"], "data_stanu_zrodla": z["zmodyfikowano"], "miejscowosc": miasto,
        "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta",
    }
    rekordy = []
    for w in wiersze:
        r = _wiersz_na_rekord(w, m)
        r["_flagi"] += flagi_pliku
        rekordy.append(r)
    print(f"  dane.gov.pl #{ds_id} ({z['instytucja']}): {len(rekordy)} rekordów z {z['format'].upper()}")
    return [(meta, rekordy)]


def _pojazdy_z_aed(dane: dict, z: dict, kod: str):
    """Baza pojazdów komunikacji miejskiej z polem 'aed' (np. ZTM Gdańsk) -> AED mobilne (bez stałej lokalizacji)."""
    meta = {"zrodlo_id": kod, "dostawca_danych": z["instytucja"], "zrodlo_url": z["url"], "zbior_url": z["dataset_url"],
            "licencja_zrodla": z["licencja"], "data_stanu_zrodla": (dane.get("metadata", {}).get("sourceDate") or z["zmodyfikowano"])[:10],
            "miejscowosc": "Gdańsk" if "Gdańsk" in z["dataset_tytul"] + z["instytucja"] else "", "dostep_domyslny": "dla_klientow_pracownikow",
            "sposob_weryfikacji": "deklaracja_dysponenta"}
    rekordy = []
    for v in dane["results"]:
        if v.get("aed") is not True:
            continue
        rekordy.append({
            "id_zrodlowe": f"pojazd-{v.get('vehicleCode')}",
            "nazwa_obiektu": f"{v.get('transportationType', 'Pojazd')} nr {v.get('vehicleCode')} ({v.get('brand', '')} {v.get('model', '')})".replace("  ", " "),
            "dysponent_nazwa": v.get("carrirer", ""), "mobilny": "tak", "typ_montazu": "pojazd", "wewnatrz_budynku": "nie",
            "opis_lokalizacji": "W kabinie kierującego – o AED poproś kierowcę/motorniczego", "zabezpieczenie": "u_personelu",
            "instrukcja_dostepu": "Poproś kierującego pojazdem", "_tekst_opisowy": "pojazd", "_flagi": ["urzadzenie_mobilne_bez_stalej_lokalizacji"],
        })
    print(f"  dane.gov.pl #{z['dataset_id']} ({z['dataset_tytul']}): {len(rekordy)} pojazdów z AED (mobilne)")
    return [(meta, rekordy)]
