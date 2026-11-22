"""Automatyczne przeszukanie stron WSZYSTKICH gmin w Polsce w poszukiwaniu wykazów AED.

Lista gmin i ich oficjalnych stron: Wikidata (CC0) – kod TERYT (P1653) + oficjalna strona (P856).
Dla każdej gminy: robots.txt -> strona główna + sitemap.xml -> podstrony z 'defibrylator'/'AED' w adresie lub opisie linku
-> ekstrakcja linii z adresami -> weryfikacja adresów w PRG w granicach TEJ gminy (odsiewa szum).
Kulturalnie: 1 zapytanie naraz na serwis, limit podstron, timeouty; respektuje robots.txt.

Wynik: dane_surowe/gminy/odkryte.json (status każdej gminy + znalezione rekordy) – czyta go adapter zrodla/gminy_auto.py.
Uruchomienie: python -m crawler gminy [--limit N]
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import prg
from .siec import UA
from .zrodla.strony_urzedow import linie_tekstu, rozbierz_linie

KAT = Path(__file__).resolve().parent.parent / "dane_surowe" / "gminy"
WIKIDATA = KAT / "wikidata_gminy_www.csv"
WYNIK = KAT / "odkryte.json"
RE_AED = re.compile(r"(?i)defibr|\baed\b|automatyczn\w* defibr")
TIMEOUT = 20
MAX_PODSTRON = 4


def _get(url: str, limit: int = 3_000_000) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.5"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        ct = r.headers.get("Content-Type", "")
        if "pdf" in ct or url.lower().endswith(".pdf"):
            return r.geturl(), ""
        dane = r.read(limit)
        enc = r.headers.get_content_charset() or "utf-8"
        return r.geturl(), dane.decode(enc, errors="ignore")


def _linki(html_txt: str, baza: str) -> list[str]:
    wynik = []
    for m in re.finditer(r'<a\s[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html_txt, re.I | re.S):
        href, tekst_linku = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        if RE_AED.search(href) or RE_AED.search(tekst_linku):
            u = urllib.parse.urljoin(baza, href)
            if u.startswith("http") and not u.lower().endswith((".jpg", ".png", ".gif", ".doc", ".docx", ".mp4")):
                wynik.append(u)
    return wynik


def _sitemap(baza: str, rp) -> list[str]:
    znalezione, do_odwiedzenia, odwiedzone = [], [urllib.parse.urljoin(baza, "/sitemap.xml")], 0
    while do_odwiedzenia and odwiedzone < 6:
        sm = do_odwiedzenia.pop(0)
        odwiedzone += 1
        try:
            _, xml = _get(sm, limit=8_000_000)
        except Exception:  # noqa: BLE001
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
        if "<sitemapindex" in xml:
            pod = [l for l in locs if RE_AED.search(l)] + [l for l in locs if re.search(r"(?i)artyk|aktual|news|page|strony|post", l)]
            do_odwiedzenia += pod[:5]
        else:
            znalezione += [l for l in locs if RE_AED.search(l)]
    return znalezione


def sprawdz_gmine(g: dict) -> dict:
    wynik = {**g, "status": "", "kandydaci": [], "strony_z_lista": [], "rekordy": []}
    baza = glowna = None
    for www in g.get("www_lista") or [g["www"]]:
        www = www.strip() if www.strip().startswith("http") else "http://" + www.strip()
        for proba in range(2):     # druga próba tylko przy chwilowych błędach (timeout, DNS)
            try:
                baza, glowna = _get(www)
                break
            except Exception as e:  # noqa: BLE001
                wynik["blad"] = str(e)[:120]
                if not re.search(r"timed out|Temporary failure", str(e)):
                    break
                time.sleep(3)
        if glowna is not None:
            wynik["www"] = www
            break
    if glowna is None:
        wynik["status"] = "strona_niedostepna"
        return wynik
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(urllib.parse.urljoin(baza, "/robots.txt"))
        rp.read()
    except Exception:  # noqa: BLE001
        rp = None
    kandydaci = list(dict.fromkeys(_linki(glowna, baza) + _sitemap(baza, rp)))
    kandydaci = [k for k in kandydaci if not rp or rp.can_fetch(UA, k)]
    wynik["kandydaci"] = kandydaci[:20]
    if not kandydaci:
        wynik["status"] = "brak_podstrony_aed"
        return wynik
    teryty = (g["teryt"],)
    nazwa = g["nazwa"]
    widziane = set()
    for url in kandydaci[:MAX_PODSTRON]:
        time.sleep(0.5)
        try:
            u, html_txt = _get(url)
        except Exception:  # noqa: BLE001
            continue
        if not html_txt:
            continue
        # podstrony prowadzące dalej (np. strona 'Defibrylatory' z linkiem do wykazu)
        rek_strony = []
        for linia in linie_tekstu(html_txt):
            r = rozbierz_linie(linia, nazwa)
            if not r:
                continue
            geo = prg.geokoduj(r["miejscowosc"], r["ulica"], r["nr_budynku"], teryty)
            if not geo:
                continue
            klucz = (geo["lat"], geo["lon"], r["nazwa_obiektu"])
            if klucz in widziane:
                continue
            widziane.add(klucz)
            r.update(_url=u, _lat=geo["lat"], _lon=geo["lon"])
            rek_strony.append(r)
        if len(rek_strony) >= 2:      # pojedyncza linia z adresem to zwykle stopka/kontakt urzędu
            wynik["strony_z_lista"].append(u)
            wynik["rekordy"] += rek_strony
    wynik["status"] = "lista_adresow" if wynik["rekordy"] else "podstrona_bez_listy"
    return wynik


def uruchom(limit: int | None = None, watki: int = 12):
    gminy, po_teryt = [], {}
    for w in csv.DictReader(open(WIKIDATA, encoding="utf-8")):
        if w["teryt"] not in po_teryt:
            po_teryt[w["teryt"]] = {"teryt": w["teryt"], "nazwa": w["nazwa"], "www": w["www"], "www_lista": []}
            gminy.append(po_teryt[w["teryt"]])
        if w["www"] not in po_teryt[w["teryt"]]["www_lista"]:
            po_teryt[w["teryt"]]["www_lista"].append(w["www"])
    if limit:
        gminy = gminy[:limit]
    print(f"Gmin do sprawdzenia: {len(gminy)}", flush=True)
    wyniki, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=watki) as ex:
        fut = {ex.submit(sprawdz_gmine, g): g for g in gminy}
        for i, f in enumerate(as_completed(fut), 1):
            try:
                wyniki.append(f.result())
            except Exception as e:  # noqa: BLE001
                g = fut[f]
                wyniki.append({**g, "status": "blad", "blad": str(e)[:120], "rekordy": []})
            if i % 100 == 0:
                ile = sum(1 for w in wyniki if w["status"] == "lista_adresow")
                print(f"  {i}/{len(gminy)} gmin, z listą AED: {ile}, rekordów: {sum(len(w['rekordy']) for w in wyniki)} ({time.time() - t0:.0f} s)", flush=True)
                WYNIK.write_text(json.dumps(wyniki, ensure_ascii=False), encoding="utf-8")
    WYNIK.write_text(json.dumps(wyniki, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("Statusy:", dict(Counter(w["status"] for w in wyniki)))
    print("Rekordów:", sum(len(w["rekordy"]) for w in wyniki))


def ponow_niedostepne(watki: int = 8):
    """Druga runda dla gmin, których strony nie odpowiedziały (np. chwilowy brak sieci) – mniej wątków, dłuższy timeout."""
    global TIMEOUT
    TIMEOUT = 30
    wyniki = json.loads(WYNIK.read_text(encoding="utf-8"))
    do_ponowienia = [w for w in wyniki if w["status"] in ("strona_niedostepna", "blad")]
    print(f"Ponawiam {len(do_ponowienia)} gmin", flush=True)
    po_teryt = {w["teryt"]: i for i, w in enumerate(wyniki)}
    with ThreadPoolExecutor(max_workers=watki) as ex:
        for nowy in ex.map(sprawdz_gmine, [{k: w[k] for k in ("teryt", "nazwa", "www", "www_lista") if k in w} for w in do_ponowienia]):
            wyniki[po_teryt[nowy["teryt"]]] = nowy
    WYNIK.write_text(json.dumps(wyniki, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("Statusy po ponowieniu:", dict(Counter(w["status"] for w in wyniki)), "rekordów:", sum(len(w["rekordy"]) for w in wyniki))


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    uruchom(lim)
