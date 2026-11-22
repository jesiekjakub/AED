"""Kraków: wykaz AED (Krakowska Sieć Impuls Życia) – PDF w BIP. Tabela: Lp | Miejsce | Adres | Liczba AED."""
import re
import subprocess

from ..normalizacja import tekst
from ..siec import KATALOG, pobierz as pobierz_plik

KARTA_BIP = "https://www.bip.krakow.pl/zalaczniki/dokumenty/n/663586/karta"
PDF = "https://www.bip.krakow.pl/plik.php?zid=663586&wer=0&new=t&mode=shw"
WIERSZ = re.compile(r"^\s*(\d+)\.\s+(.*?)\s{2,}(\S.*?)\s{2,}(\d+)\s*$")


def pobierz():
    pdf = pobierz_plik(PDF, "krakow/wykaz.pdf", kopia_zapasowa=KATALOG / "_probki_recznie" / "krakow_wykaz_AED_BIP_2026_03.pdf")
    txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    stan = re.search(r"stanu na (\d{2})\.(\d{2})\.(\d{4})", txt)
    data_stanu = f"{stan.group(3)}-{stan.group(2)}-{stan.group(1)}" if stan else ""
    razem = None
    # 1) rozbiór linii: wiersze numerowane i fragmenty (komórki zawinięte w kilku liniach, wyśrodkowane w pionie)
    wiersze, fragmenty_przed = [], []
    for linia in txt.splitlines():
        if not linia.strip() or re.search(r"WYKAZ|NA TERENIE KRAKOWA W|stanu na|LP\.|^\s*AED\s*$", linia):
            continue
        if "RAZEM" in linia:
            razem = re.search(r"(\d+)\s*$", linia)
            continue
        m = WIERSZ.match(linia) or re.match(r"^\s*(\d+)\.\s+()()(\d+)\s*$", linia)
        if m:
            lp, miejsce, adres, liczba = m.groups()
            w = {"lp": lp, "miejsce": [*(f[0] for f in fragmenty_przed if f[0])], "adres": [*(f[1] for f in fragmenty_przed if f[1])],
                 "liczba": int(liczba), "pusty": not miejsce}
            if miejsce:
                w["miejsce"].append(miejsce)
            if adres:
                w["adres"].append(adres)
            fragmenty_przed = []
            wiersze.append(w)
            continue
        wciecie = len(linia) - len(linia.lstrip())
        czesci = re.split(r"\s{2,}", linia.strip())
        frag = ("", czesci[0]) if wciecie >= 40 else (czesci[0], czesci[1] if len(czesci) > 1 else "")
        # fragment zaraz po wierszu z pustą komórką 'miejsce' należy do niego (komórka wyśrodkowana w pionie)
        if wiersze and wiersze[-1]["pusty"] and not fragmenty_przed and not wiersze[-1].get("domkniety"):
            wiersze[-1]["miejsce"] += [frag[0]] if frag[0] else []
            wiersze[-1]["adres"] += [frag[1]] if frag[1] else []
            wiersze[-1]["domkniety"] = True
        else:
            fragmenty_przed.append(frag)

    # 2) rekordy – jeden na urządzenie
    rekordy = []
    for w in wiersze:
        lp, miejsce, adres, n = w["lp"], tekst(" ".join(w["miejsce"])), tekst(" ".join(w["adres"])), w["liczba"]
        calodobowy = bool(re.search(r"\b24\s*h\b", miejsce))
        miejsce = tekst(re.sub(r"\b24\s*h\b", "", miejsce))
        czesci = re.split(r"\s+[–-]\s+", miejsce, maxsplit=1)
        obiekt = czesci[0]
        opis = czesci[1] if len(czesci) > 1 else ""
        if "ogólnodostępne" in obiekt:
            obiekt = tekst(obiekt.replace("ogólnodostępne", ""))
            opis = tekst(f"{opis} ogólnodostępne")
        for k in range(1, n + 1):
            r = {"id_zrodlowe": lp if n == 1 else f"{lp}-{k}", "nazwa_obiektu": obiekt, "opis_lokalizacji": opis,
                 "_adres": adres, "_tekst_opisowy": miejsce, "_flagi": ["wiele_urzadzen_w_lokalizacji"] if n > 1 else []}
            if calodobowy:
                r.update(godziny_dostepnosci="24/7", dostepny_24_7="tak", godziny_opis="24h")
            if re.search(r"radiowoz|taboru|pojazd", miejsce, re.I):
                r.update(mobilny="tak", typ_montazu="pojazd", _adres="")
                r["_flagi"].append("urzadzenie_mobilne_bez_stalej_lokalizacji")
            rekordy.append(r)
    if razem and int(razem.group(1)) != len(rekordy):
        print(f"  ! Kraków: suma w PDF {razem.group(1)} ≠ odczytane {len(rekordy)}")
    print(f"  Kraków: {len(rekordy)} urządzeń z PDF (stan {data_stanu})")
    meta = {"zrodlo_id": "JST-KRK", "dostawca_danych": "Urząd Miasta Krakowa", "zrodlo_url": PDF, "zbior_url": KARTA_BIP,
            "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": data_stanu, "miejscowosc": "Kraków",
            "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
    return [(meta, rekordy)]
