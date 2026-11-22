"""Lokalne geokodowanie z Państwowego Rejestru Granic (punkty adresowe, GUGiK, dane otwarte).

Źródło: https://opendata.geoportal.gov.pl/prg/adresy/PunktyAdresowe/POLSKA.zip (shapefile, EPSG:2180).
`python -m crawler prg` buduje indeks SQLite (dane_surowe/prg/adresy.sqlite) – jednorazowo, kilka minut.
Wyszukiwanie: w obrębie TERYT gminy/powiatu/województwa lub nazwy miejscowości; ulica dopasowywana po rdzeniu
(odporne na odmianę: 'ul. Sudeckiej' ~ 'Sudecka'), miejscowości bez ulic – po nazwie miejscowości i numerze.
"""
import math
import re
import sqlite3
import struct
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent / "dane_surowe" / "prg"
ZIP = KATALOG / "POLSKA.zip"
BAZA = KATALOG / "adresy.sqlite"

# ------------------------------------------------------------------ EPSG:2180 -> WGS84 (odwrotne Gaussa-Krügera, GRS80)
_A, _F = 6378137.0, 1 / 298.257222101
_E2 = _F * (2 - _F)
_K0, _LON0, _FE, _FN = 0.9993, math.radians(19.0), 500000.0, -5300000.0
_N = _F / (2 - _F)
_AH = _A / (1 + _N) * (1 + _N ** 2 / 4 + _N ** 4 / 64)
_BETA = [_N / 2 - 2 * _N ** 2 / 3 + 37 * _N ** 3 / 96, _N ** 2 / 48 + _N ** 3 / 15, 17 * _N ** 3 / 480]
_DELTA = [2 * _N - 2 * _N ** 2 / 3 - 2 * _N ** 3, 7 * _N ** 2 / 3 - 8 * _N ** 3 / 5, 56 * _N ** 3 / 15]


def puwg92_na_wgs84(x: float, y: float) -> tuple[float, float]:
    """x = easting, y = northing (jak w shapefile) -> (lat, lon)."""
    xi = (y - _FN) / (_K0 * _AH)
    eta = (x - _FE) / (_K0 * _AH)
    xi_p, eta_p = xi, eta
    for j, b in enumerate(_BETA, 1):
        xi_p -= b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        eta_p -= b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    lat = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(_DELTA, 1))
    lon = _LON0 + math.atan2(math.sinh(eta_p), math.cos(xi_p))
    return round(math.degrees(lat), 6), round(math.degrees(lon), 6)


# ------------------------------------------------------------------ normalizacja nazw
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower().replace("ł", "l"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_PREF = {"ul", "ulica", "al", "aleja", "aleje", "pl", "plac", "os", "osiedle", "im", "imienia", "sw", "swietego", "swietej", "ks",
         "ksiedza", "gen", "generala", "kpt", "kapitana", "dr", "prof", "marsz", "marszalka", "rondo", "skwer", "bulwar", "rynek", "kard", "bp", "abp"}


def rdzenie(nazwa: str) -> list[str]:
    """Znaczące słowa nazwy ulicy, skrócone do 5 znaków (odporność na odmianę przez przypadki)."""
    return [w[:5] for w in norm(nazwa).split() if w not in _PREF and len(w) > 2 and not w.isdigit()]


def norm_nr(nr: str) -> str:
    return re.sub(r"\s+", "", (nr or "").upper())


# ------------------------------------------------------------------ budowa indeksu
def zbuduj(postep_co: int = 500000):
    KATALOG.mkdir(parents=True, exist_ok=True)
    tmp = BAZA.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.execute("""CREATE TABLE adr (teryt TEXT, gmina TEXT, msc TEXT, msc_n TEXT, simc TEXT, ulica TEXT, ulica_n TEXT, ulic TEXT,
                  nr TEXT, kod TEXT, lat REAL, lon REAL)""")
    dbf = subprocess.Popen(["unzip", "-p", str(ZIP), "PRG_PunktyAdresowe_POLSKA.dbf"], stdout=subprocess.PIPE, bufsize=1 << 20).stdout
    shp = subprocess.Popen(["unzip", "-p", str(ZIP), "PRG_PunktyAdresowe_POLSKA.shp"], stdout=subprocess.PIPE, bufsize=1 << 20).stdout
    h = dbf.read(32)
    n, hl, rl = struct.unpack("<IHH", h[4:12])
    reszta = dbf.read(hl - 32)
    pola, poz = {}, 1
    for i in range(0, len(reszta) - 1, 32):
        d = reszta[i:i + 32]
        if d[0] == 0x0D:
            break
        nazwa, dl = d[:11].split(b"\0")[0].decode(), d[16]
        pola[nazwa] = (poz, poz + dl)
        poz += dl
    shp.read(100)

    def pole(r, k):
        a, b = pola[k]
        return r[a:b].decode("utf-8", "replace").strip()

    partia = []
    for i in range(n):
        r = dbf.read(rl)
        num, clen = struct.unpack(">ii", shp.read(8))
        body = shp.read(clen * 2)
        if len(r) < rl:
            break
        if r[0:1] == b"*" or struct.unpack("<i", body[:4])[0] != 1:
            continue
        x, y = struct.unpack("<dd", body[4:20])
        lat, lon = puwg92_na_wgs84(x, y)
        ul, msc = pole(r, "NAZWA_ULC"), pole(r, "NAZWA_MSC")
        partia.append((pole(r, "TERYT_GMI"), pole(r, "NAZWA_GMI"), msc, norm(msc), pole(r, "ID_SIMC"), ul, " ".join(rdzenie(ul)),
                       pole(r, "ID_ULIC"), norm_nr(pole(r, "NUMER_PORZ")), pole(r, "KOD_POCZT"), lat, lon))
        if len(partia) >= 100000:
            db.executemany("INSERT INTO adr VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", partia)
            partia = []
        if i and i % postep_co == 0:
            print(f"  PRG: {i:,}/{n:,}", flush=True)
    if partia:
        db.executemany("INSERT INTO adr VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", partia)
    db.execute("CREATE INDEX i_msc ON adr(msc_n, nr)")
    db.execute("CREATE INDEX i_ter ON adr(teryt, nr)")
    db.execute("CREATE INDEX i_lat ON adr(lat)")
    db.execute("CREATE TABLE gminy AS SELECT DISTINCT teryt, gmina FROM adr")
    db.commit()
    db.close()
    tmp.replace(BAZA)
    print(f"  PRG: indeks gotowy ({BAZA})")


# ------------------------------------------------------------------ wyszukiwanie
import threading
_lokalne = threading.local()
WOJ = {"02": "dolnośląskie", "04": "kujawsko-pomorskie", "06": "lubelskie", "08": "lubuskie", "10": "łódzkie", "12": "małopolskie",
       "14": "mazowieckie", "16": "opolskie", "18": "podkarpackie", "20": "podlaskie", "22": "pomorskie", "24": "śląskie",
       "26": "świętokrzyskie", "28": "warmińsko-mazurskie", "30": "wielkopolskie", "32": "zachodniopomorskie"}
WOJ_ODWR = {v: k for k, v in WOJ.items()}


def dostepny() -> bool:
    return BAZA.exists()


def _baza():
    """Osobne połączenie na wątek (crawler gmin działa wielowątkowo)."""
    if getattr(_lokalne, "db", None) is None:
        _lokalne.db = sqlite3.connect(f"file:{BAZA}?mode=ro", uri=True)
    return _lokalne.db


@lru_cache(maxsize=None)
def teryty_obszaru(gmina: str = "", teryt_prefiks: str = "", wojewodztwo: str = "") -> tuple[str, ...]:
    """Kody TERYT gmin (7 znaków): po nazwie gminy (opcjonalnie w województwie) albo po prefiksie TERYT (powiat '2213', woj. '32')."""
    db = _baza()
    pref = teryt_prefiks or WOJ_ODWR.get(wojewodztwo, "")
    if gmina:
        rows = db.execute("SELECT DISTINCT teryt FROM gminy WHERE gmina = ? AND teryt LIKE ?", (gmina, pref + "%")).fetchall()
    elif pref:
        rows = db.execute("SELECT DISTINCT teryt FROM gminy WHERE teryt LIKE ?", (pref + "%",)).fetchall()
    else:
        rows = []
    return tuple(r[0] for r in rows)


@lru_cache(maxsize=None)
def _miasto_teryt(miejscowosc: str) -> tuple[str, ...]:
    rows = _baza().execute("SELECT DISTINCT teryt FROM adr WHERE msc_n = ? LIMIT 50", (norm(miejscowosc),)).fetchall()
    return tuple(r[0] for r in rows)


def _wynik(row, rodzaj):
    teryt, gmina, msc, _, simc, ul, _, ulic, nr, kod, lat, lon = row
    return {"lat": lat, "lon": lon, "rodzaj": rodzaj, "miejscowosc": msc, "ulica_prg": ul, "nr": nr, "kod_pocztowy": kod,
            "teryt_gmina": teryt[:6], "teryt_gmina_pelny": teryt, "simc": simc, "ulic": ulic, "wojewodztwo": WOJ.get(teryt[:2], ""),
            "powiat": "", "gmina": gmina, "dokladnosc": 1.0}


def geokoduj(miejscowosc: str, ulica: str, nr: str, teryty: tuple[str, ...] = ()) -> dict:
    """Adres -> punkt PRG. teryty – zawężenie do gmin (np. z konfiguracji źródła). {} gdy brak dopasowania."""
    if not dostepny():
        return {}
    db = _baza()
    nr = norm_nr(nr)
    msc_n = norm(miejscowosc)
    rdz = rdzenie(re.sub(r"(?i)^\s*(ul\.|ulica)\s*", "", ulica or ""))
    if not teryty and miejscowosc:
        teryty = _miasto_teryt(miejscowosc)
    if not teryty:
        return {}
    q_ter = ",".join("?" * len(teryty))
    kandydaci = []
    if nr:
        kandydaci = db.execute(f"SELECT * FROM adr WHERE teryt IN ({q_ter}) AND nr IN (?, ?)", (*teryty, nr, re.sub(r"[A-Z]$", "", nr))).fetchall()
    if rdz:
        def pasuje(row):
            return all(any(r == w or w.startswith(r[:4]) for w in row[6].split()) for r in rdz)
        dopas = [k for k in kandydaci if pasuje(k)]
        # ulica bez cechy może być też nazwą miejscowości (wsie: 'Rudnik Wielki 182')
        if not dopas:
            dopas = [k for k in kandydaci if not k[5] and k[3].startswith(" ".join(norm(ulica).split()[:1]))]
        if dopas:
            dok = [k for k in dopas if k[8] == nr] or dopas
            pref = [k for k in dok if k[3] == msc_n] or dok
            return _wynik(pref[0], "adres" if pref[0][8] == nr else "adres_przyblizony")
        # środek ulicy
        ul_rows = db.execute(f"SELECT * FROM adr WHERE teryt IN ({q_ter}) AND ulica_n LIKE ? LIMIT 2000", (*teryty, f"%{rdz[0]}%")).fetchall()
        ul_rows = [k for k in ul_rows if pasuje(k)]
        if ul_rows:
            pref = [k for k in ul_rows if k[3] == msc_n] or ul_rows
            lat = sum(k[10] for k in pref) / len(pref)
            lon = sum(k[11] for k in pref) / len(pref)
            w = _wynik(pref[0], "ulica")
            w.update(lat=round(lat, 6), lon=round(lon, 6), nr="")
            return w
        return {}
    # brak ulicy: miejscowość + numer
    dopas = [k for k in kandydaci if k[3] == msc_n and k[8] == nr] or [k for k in kandydaci if k[3] == msc_n]
    if dopas:
        return _wynik(dopas[0], "adres" if dopas[0][8] == nr else "adres_przyblizony")
    return {}


def odwrotne(lat: float, lon: float, promien_m: float = 100) -> dict:
    if not dostepny():
        return {}
    d = promien_m / 111000
    rows = _baza().execute("SELECT * FROM adr WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
                           (lat - d, lat + d, lon - d * 1.6, lon + d * 1.6)).fetchall()
    if not rows:
        return {}
    best = min(rows, key=lambda k: (k[10] - lat) ** 2 + ((k[11] - lon) * math.cos(math.radians(lat))) ** 2)
    w = _wynik(best, "adres")
    w["odleglosc_m"] = math.hypot((best[10] - lat) * 111000, (best[11] - lon) * 111000 * math.cos(math.radians(lat)))
    w["lat"], w["lon"] = lat, lon
    return w
