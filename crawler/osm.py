"""Porównanie z OpenStreetMap (ODbL) – WYŁĄCZNIE analiza luk. Danych OSM nie łączymy ze zbiorem zbiorczym (licencja share-alike).

Dla każdego źródła: ile punktów OSM jest w obszarze miasta (prostokąt wokół punktów źródła + 1 km) i ile rekordów
źródła ma punkt OSM w promieniu 50/150 m. Wynik: analiza/porownanie_osm.csv
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

from .geokoder import odleglosc_m
from .siec import pobierz as pobierz_plik

KORZEN = Path(__file__).resolve().parent.parent
OSM_URL = "https://aed.openstreetmap.org.pl/aed_poland.geojson"
LOKALNY = [Path.home() / "Downloads" / "PL.geojson"]


def wczytaj_osm() -> list[tuple[float, float]]:
    for p in LOKALNY:
        if p.exists():
            src = p
            break
    else:
        src = pobierz_plik(OSM_URL, "osm/aed_poland.geojson", timeout=180)
    d = json.loads(Path(src).read_text(encoding="utf-8"))
    return [(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]) for f in d["features"] if f.get("geometry")]


def porownaj(rekordy: list[dict]) -> list[dict]:
    osm = wczytaj_osm()
    siatka = defaultdict(list)
    for lat, lon in osm:
        siatka[(int(lat * 100), int(lon * 100))].append((lat, lon))

    def najblizszy(lat, lon):
        best = 1e9
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for p in siatka.get((int(lat * 100) + dy, int(lon * 100) + dx), []):
                    best = min(best, odleglosc_m(lat, lon, *p))
        return best

    wg = defaultdict(list)
    for r in rekordy:
        if r["szerokosc_geograficzna"] != "":
            wg[(r["zrodlo_id"], r["dostawca_danych"])].append(r)
    wynik = []
    for (zid, dost), rs in wg.items():
        lats = [r["szerokosc_geograficzna"] for r in rs]
        lons = [r["dlugosc_geograficzna"] for r in rs]
        m_lat, m_lon = 0.009, 0.015   # ~1 km
        w_obszarze = sum(min(lats) - m_lat <= a <= max(lats) + m_lat and min(lons) - m_lon <= b <= max(lons) + m_lon for a, b in osm)
        odl = [najblizszy(r["szerokosc_geograficzna"], r["dlugosc_geograficzna"]) for r in rs]
        wynik.append({"zrodlo_id": zid, "dostawca_danych": dost, "rekordow_zrodla_z_wsp": len(rs), "punktow_osm_w_obszarze": w_obszarze,
                      "rekordy_z_osm_do_50m": sum(d <= 50 for d in odl), "rekordy_z_osm_do_150m": sum(d <= 150 for d in odl),
                      "rekordy_bez_osm_w_150m": sum(d > 150 for d in odl)})
    (KORZEN / "analiza").mkdir(exist_ok=True)
    with open(KORZEN / "analiza" / "porownanie_osm.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(wynik[0]))
        w.writeheader()
        w.writerows(wynik)
    return wynik
