"""Geokodowanie przez Usługę Uproszczonego Geokodowania GUGiK (dane z Państwowego Rejestru Granic / EMUiA).

Urzędowe źródło adresów: zwraca współrzędne WGS84 + kody TERYT (TERC gminy, SIMC, ULIC) i jednostki podziału.
Wyniki trzymamy w pamięci podręcznej, żeby nie obciążać usługi.
"""
import json
import math
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from .siec import UA, KATALOG

URL = "https://services.gugik.gov.pl/uug/"
CACHE_PLIK = KATALOG / "_cache_geokoder_gugik.json"
_cache: dict | None = None
_ostatnie = 0.0


def _wczytaj():
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE_PLIK.read_text()) if CACHE_PLIK.exists() else {}
    return _cache


def zapisz_cache():
    if _cache is not None:
        KATALOG.mkdir(exist_ok=True)
        CACHE_PLIK.write_text(json.dumps(_cache, ensure_ascii=False, indent=0))


ODSTEP_S = 1.0          # nie więcej niż 1 zapytanie na sekundę – usługa publiczna, nie obciążamy jej
PRZERWA_BLOKADA_S = 60  # po odpowiedzi "blocked for abuse" czekamy i zwalniamy


TYLKO_CACHE = os.environ.get("AED_GEOKODER") == "cache"   # bez zapytań sieciowych – tylko wyniki zapamiętane
POMINIETE = 0


def _zapytanie(params: dict) -> dict:
    global _ostatnie, ODSTEP_S, POMINIETE
    klucz = json.dumps(params, sort_keys=True, ensure_ascii=False)
    c = _wczytaj()
    if klucz in c and "notice" not in c[klucz]:
        return c[klucz]
    if TYLKO_CACHE:
        POMINIETE += 1
        return {"_pominieto": True}
    for proba in range(4):
        odstep = time.time() - _ostatnie
        if odstep < ODSTEP_S:
            time.sleep(ODSTEP_S - odstep)
        _ostatnie = time.time()
        try:
            req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                wynik = json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 – błąd sieci: nie zapisujemy w cache
            time.sleep(3 * (proba + 1))
            continue
        if "notice" in wynik:   # limit usługi – czekamy i zwalniamy tempo
            print(f"    (GUGiK: {wynik['notice']} – przerwa {PRZERWA_BLOKADA_S} s)", flush=True)
            time.sleep(PRZERWA_BLOKADA_S)
            ODSTEP_S = min(ODSTEP_S * 1.5, 3.0)
            continue
        c[klucz] = wynik
        if len(c) % 50 == 0:
            zapisz_cache()
        return wynik
    return {}


def bez_ogonkow(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)).replace("ł", "l").replace("Ł", "L")


_PREFIKSY = r"\b(ul|ulica|al|aleja|aleje|pl|plac|os|osiedle|im|kpt|kapitana|gen|generala|ks|ksiedza|sw|swietego|swietej|dr|prof|marsz|marszalka|rondo|skwer|bulwar|wybrzeze|trakt)\b\.?"


def rdzen_ulicy(s: str) -> str:
    """Najdłuższe słowo nazwy ulicy bez prefiksów – do porównania zapytania z wynikiem."""
    s = bez_ogonkow(s.lower())
    s = re.sub(_PREFIKSY, " ", s)
    slowa = [w for w in re.split(r"[^a-z0-9]+", s) if len(w) > 2 and not w.isdigit()]
    return max(slowa, key=len) if slowa else ""


def _jednostka(j: str | None):
    """'{Polska,łódzkie,Łódź,Łódź}' -> (województwo, powiat, gmina). Inne formaty (np. dla ulic) – puste."""
    czesci = (j or "").strip("{}").split(",")
    if len(czesci) < 4 or czesci[0] != "Polska":
        return "", "", ""
    return czesci[1], czesci[2], czesci[3]


def _wynik(f: dict, rodzaj: str) -> dict:
    woj, pow_, gm = _jednostka(f.get("jednostka"))
    if f.get("x"):
        lon, lat = float(f["x"]), float(f["y"])
    else:  # ulica/obszar – środek geometrii
        pkt = [tuple(map(float, p.split())) for p in re.findall(r"-?\d+\.\d+ -?\d+\.\d+", f.get("geometry_wkt", ""))]
        if not pkt:
            return {}
        lon = sum(p[0] for p in pkt) / len(pkt)
        lat = sum(p[1] for p in pkt) / len(pkt)
    return {
        "lat": round(lat, 6), "lon": round(lon, 6), "rodzaj": rodzaj,
        "miejscowosc": f.get("city") or "", "ulica_prg": (f.get("street") or "").strip(), "nr": f.get("number") or "",
        "kod_pocztowy": f.get("code") or "", "teryt_gmina": f.get("teryt") or "", "simc": f.get("simc") or "",
        "ulic": f.get("ulic") or "", "wojewodztwo": woj, "powiat": pow_, "gmina": gm,
        "dokladnosc": float(f.get("accuracy") or 0),
    }


def normalizuj_numer(nr: str) -> str:
    nr = (nr or "").strip().replace(" ", "")
    return nr.upper()


def geokoduj_adres(miejscowosc: str, ulica: str, nr: str) -> dict:
    """Zwraca wynik dla dokładnego adresu, w razie porażki – środek ulicy (rodzaj='ulica'). {} gdy nic."""
    miejscowosc = (miejscowosc or "").strip()
    ulica_czysta = re.sub(r"^\s*(ul\.|ulica)\s*", "", (ulica or "").strip(), flags=re.I)
    nr = normalizuj_numer(nr)
    rdzen = rdzen_ulicy(ulica_czysta)
    warianty = []
    if ulica_czysta and nr:
        warianty.append(f"{miejscowosc}, {ulica_czysta} {nr}")
        m = re.match(r"^(\d+)[A-Z]$", nr)
        if m:
            warianty.append(f"{miejscowosc}, {ulica_czysta} {m.group(1)}")
        if rdzen and rdzen != bez_ogonkow(ulica_czysta.lower()):
            warianty.append(f"{miejscowosc}, {rdzen} {nr}")
    elif not ulica_czysta and nr:  # miejscowości bez ulic
        warianty.append(f"{miejscowosc} {nr}")
    pominieto = False
    for adres in warianty:
        d = _zapytanie({"request": "GetAddress", "address": adres, "srid": "4326"})
        pominieto |= bool(d.get("_pominieto"))
        f = (d.get("results") or {}).get("1")
        if not f or d.get("type") != "address":
            continue
        zgodna = (not rdzen) or rdzen in bez_ogonkow((f.get("street") or "").lower()) or rdzen in bez_ogonkow((f.get("city") or "").lower())
        if zgodna and float(f.get("accuracy") or 0) >= 0.5:
            return _wynik(f, "adres")
    if ulica_czysta:
        d = _zapytanie({"request": "GetAddress", "address": f"{miejscowosc}, {ulica_czysta}", "srid": "4326"})
        f = (d.get("results") or {}).get("1")
        pominieto |= bool(d.get("_pominieto"))
        if f and rdzen and rdzen in bez_ogonkow(((f.get("street") or "") + " " + (f.get("city") or "")).lower()):
            return _wynik(f, "ulica")
    return {"_pominieto": True} if pominieto else {}


def odwrotne(lat: float, lon: float, promien: int = 100) -> dict:
    d = _zapytanie({"request": "GetAddressReverse", "location": f"POINT({lon} {lat})", "srid": "4326", "radius": str(promien)})
    if d.get("_pominieto"):
        return {"_pominieto": True}
    f = (d.get("results") or {}).get("1")
    if not f:
        return {}
    w = _wynik(f, "adres")
    w["odleglosc_m"] = float(f.get("distance") or 0)
    w["lat"], w["lon"] = lat, lon   # nie przesuwamy punktu
    return w


def odleglosc_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
