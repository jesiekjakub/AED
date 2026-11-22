"""Uniwersalny adapter list AED publikowanych na stronach gmin, powiatów i instytucji (HTML).

Strona -> linie tekstu -> linie wyglądające na pozycję wykazu (adres) -> (obiekt, adres, miejscowość).
Adresy dopasowywane są potem do punktów adresowych PRG w obrębie wskazanego obszaru (TERYT gminy/powiatu),
co działa także dla wsi bez nazw ulic ("Czaple 29").

Konfiguracja źródeł: crawler/zrodla/strony_urzedow.json (dopisanie nowej gminy nie wymaga kodu).
"""
import html
import json
import re
from pathlib import Path

from ..normalizacja import tekst
from ..siec import pobierz as pobierz_plik

KONFIG = Path(__file__).with_name("strony_urzedow.json")

_NR = r"\d+[A-Za-z]?(?:\s?/\s?\d+[A-Za-z]?)?"
_CECHA = r"(?:ul\.|ul |al\.|al |pl\.|plac|os\.|osiedle|aleja|aleje|rynek|skwer)"
RE_ULICA = re.compile(rf"(?i)({_CECHA}\s*[^,;–\-()]*?\s{_NR}|{_CECHA}\s*[^,;–\-()]+?(?=,|\s[–-]\s|$))")
RE_MIEJSC_NR = re.compile(rf"\b([A-ZŁŚŻŹĆ][a-ząęółśżźćń]+(?:[ -][A-ZŁŚŻŹĆa-ząęółśżźćń][a-ząęółśżźćń]+){{0,2}})\s({_NR})\b")
RE_KOD = re.compile(r"(\d{2}-\d{3})\s+([A-ZŁŚŻŹĆ][^\d,;]+)")
SMIECI = re.compile(r"(?i)(cennik|eDoręczenia|data publikacji|tel\.|telefon|e-mail|nip|regon|godz\. otwarcia urzędu|copyright|strategia|©|\bwww\.|https?://|zdjęci|kliknij|czytaj|udostępnij)")


def linie_tekstu(html_txt: str) -> list[str]:
    t = re.sub(r"(?is)<(script|style|nav|header|footer|form|noscript)[^>]*>.*?</\1>", " ", html_txt)
    t = re.sub(r"(?i)<br\s*/?>|</(p|li|tr|div|h\d|td|th|dd|dt)>", "\n", t)
    t = re.sub(r"(?i)</t[dh]>\s*<t[dh][^>]*>", " | ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return [re.sub(r"\s+", " ", l).strip(" \t•·-–📍✅▪►*|") for l in t.split("\n") if l.strip()]


def rozbierz_linie(linia: str, domyslna: str) -> dict | None:
    """Pozycja wykazu -> {nazwa_obiektu, miejscowosc, ulica, nr_budynku, kod_pocztowy, godziny_opis} albo None."""
    l = tekst(linia)
    if len(l) < 6 or len(l) > 300 or SMIECI.search(l) or not re.search(r"\d", l):
        return None
    godziny = ""
    mg = re.search(r"(?i)(ogólnodostępn\w*\s*24\s*h[^,;]*|24\s*h\s*/\s*dobę|24/7|całodobow\w*|ograniczona dostępność[^,;]*|w godzinach [^,;]+)", l)
    if mg:
        godziny = mg.group(1)
    praca = l.replace(godziny, " ") if godziny else l
    miejscowosc, kod_p = domyslna, ""
    kod = RE_KOD.search(praca)
    if kod:
        kod_p, miejscowosc = kod.group(1), kod.group(2).strip(" ,.")
        praca = (praca[:kod.start()] + praca[kod.end():])
    ulica, nr = "", ""
    m = RE_ULICA.search(praca)
    if m:
        frag = m.group(1).strip(" ,.")
        mn = re.match(rf"(.*?)\s({_NR})$", frag)
        ulica, nr = (mn.group(1), mn.group(2)) if mn else (frag, "")
        przed, po = praca[:m.start()], praca[m.end():]
        mm = re.search(r"([A-ZŁŚŻŹĆ][\wąęółśżźćń\- ]{2,40}),\s*$", przed)
        if mm and not kod and len(mm.group(1).split()) <= 3 and not re.search(r"(?i)\b(osp|szkoł|urząd|ośrodek|budynk|hala|remiz|świetlic|centrum|dom)", mm.group(1)):
            miejscowosc = mm.group(1).strip()
            przed = przed[:mm.start()]
        obiekt = przed.strip(" ,–-:") or po.strip(" ,–-:.")
    else:
        m = RE_MIEJSC_NR.search(praca)
        if not m or re.match(r"(?i)(godz|tel|nr|lp|rok|stan|dnia)", m.group(1)):
            return None
        miejscowosc, nr = m.group(1), m.group(2)
        obiekt = (praca[:m.start()] + " " + praca[m.end():]).strip(" ,–-:.")
    obiekt = re.sub(r"(?i)^(na budynku|przy budynku|przy|w budynku|na ścianie|na bramie wjazdowej( do)?|budynek)\s+", "", tekst(obiekt)).strip(" ,–-:.")
    if not (ulica or nr):
        return None
    return {"nazwa_obiektu": obiekt or f"AED – {ulica} {nr}".strip(), "miejscowosc": miejscowosc, "ulica": ulica, "nr_budynku": nr.replace(" ", ""),
            "kod_pocztowy": kod_p, "godziny_opis": godziny, "adres_oryginalny": l, "_tekst_opisowy": l}


def pobierz():
    if not KONFIG.exists():
        return []
    wynik = []
    for cfg in json.loads(KONFIG.read_text(encoding="utf-8")):
        try:
            p = pobierz_plik(cfg["url"], f"strony_urzedow/{cfg['zrodlo_id']}.html")
        except RuntimeError as e:
            print(f"  ! {cfg['zrodlo_id']}: {e}")
            continue
        linie = linie_tekstu(p.read_text(encoding="utf-8", errors="ignore"))
        if cfg.get("od"):
            i = next((k for k, l in enumerate(linie) if cfg["od"].lower() in l.lower()), 0)
            linie = linie[i:]
        if cfg.get("do"):
            i = next((k for k, l in enumerate(linie) if cfg["do"].lower() in l.lower()), len(linie))
            linie = linie[:i]
        rekordy = []
        for l in linie:
            r = rozbierz_linie(l, cfg.get("miejscowosc", ""))
            if not r:
                continue
            r["id_zrodlowe"] = str(len(rekordy) + 1)
            r["_flagi"] = ["pozyskano_ze_strony_www_ekstrakcja_automatyczna"]
            r["_obszar"] = cfg.get("obszar", {})
            r["_odrzuc_bez_prg"] = True
            r.update(cfg.get("domyslne", {}))
            rekordy.append(r)
        if cfg.get("limit"):
            rekordy = rekordy[:cfg["limit"]]
        print(f"  {cfg['dostawca_danych']}: {len(rekordy)} pozycji ze strony")
        meta = {"zrodlo_id": cfg["zrodlo_id"], "dostawca_danych": cfg["dostawca_danych"], "zrodlo_url": cfg["url"], "zbior_url": cfg["url"],
                "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": cfg.get("data_stanu", ""),
                "miejscowosc": cfg.get("miejscowosc", ""), "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
        wynik.append((meta, rekordy))
    return wynik
