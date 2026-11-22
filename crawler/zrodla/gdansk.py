"""Gdańsk: tabela HTML w artykule gdansk.pl (adres | opis lokalizacji | na zewnątrz? | godziny)."""
import html
import re

from ..normalizacja import tekst
from ..siec import KATALOG, pobierz as pobierz_plik

STRONA = "https://www.gdansk.pl/wiadomosci/Defibrylatory,a,216952"


def _komorki(tr):
    return [tekst(html.unescape(re.sub(r"<[^>]+>", " ", c))) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]


def _rozbierz(adres: str):
    """'Osowa, ul. Balcerskiego 35 ( IX komisariat policji)' -> obiekt, adres, dzielnica."""
    obiekt = ""
    naw = re.search(r"\(\s*([^)]*?)\s*\)", adres)
    if naw:
        obiekt = naw.group(1)
        adres = tekst(adres[:naw.start()] + adres[naw.end():])
    adres = re.sub(r"(\d+\s?[A-Za-z]?)-\s*$", r"\1", adres).strip(" -")
    dzielnica = ""
    m = re.match(r"^([^,]+?),\s*((?:ul\.|al\.|pl\.|os\.).*)$", adres)
    if m:
        dzielnica, adres = m.group(1), m.group(2)
    else:
        m = re.search(r"\b(ul\.|al\.|pl\.)\s", adres)
        if m and m.start() > 0:
            obiekt = obiekt or adres[:m.start()].strip(" ,")
            adres = adres[m.start():]
    if not obiekt:
        obiekt = adres
    return tekst(obiekt), tekst(adres), dzielnica


def pobierz():
    t = pobierz_plik(STRONA, "gdansk/strona.html", kopia_zapasowa=KATALOG / "_probki_recznie" / "gdansk_strona.html").read_text(encoding="utf-8", errors="ignore")
    tabela = re.search(r"<table.*?</table>", t, re.S).group(0)
    rekordy = []
    for tr in re.findall(r"<tr.*?</tr>", tabela, re.S)[1:]:
        k = _komorki(tr)
        if len(k) < 5 or not k[1]:
            continue
        lp, adres_raw, opis, zewn, godz = k[:5]
        obiekt, adres, dzielnica = _rozbierz(adres_raw)
        r = {"id_zrodlowe": lp, "nazwa_obiektu": obiekt, "opis_lokalizacji": opis, "godziny_opis": godz,
             "_adres": adres if re.search(r"\b(ul|al|pl|os)\.", adres) else "", "_tekst_opisowy": f"{adres_raw} {opis} {zewn}", "_flagi": []}
        z = zewn.lower()
        if "pojeździe" in z or "pojeździe" in opis.lower():
            r.update(mobilny="tak", typ_montazu="pojazd", wewnatrz_budynku="nie", nazwa_obiektu=f"Pojazd – {obiekt}", _adres="")
            r["_flagi"].append("urzadzenie_mobilne_bez_stalej_lokalizacji")
        elif "zewnątrz" in z:
            r["wewnatrz_budynku"] = "nie"
        elif "wewnątrz" in z:
            r["wewnatrz_budynku"] = "tak"
        if dzielnica and dzielnica.lower() != "gdańsk":
            r["uwagi"] = f"Dzielnica: {dzielnica}"
        rekordy.append(r)
    print(f"  Gdańsk: {len(rekordy)} rekordów z tabeli HTML")
    meta = {"zrodlo_id": "JST-GDA", "dostawca_danych": "Urząd Miejski w Gdańsku", "zrodlo_url": STRONA, "zbior_url": STRONA,
            "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": "", "miejscowosc": "Gdańsk",
            "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
    return [(meta, rekordy)]
