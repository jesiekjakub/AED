"""Łódź: wykaz XLS (dysponent, obiekt, adres, miejsce w obiekcie, godziny) + mapa Google My Maps (współrzędne).

Łączymy po ulicy i numerze. Punkty z mapy bez pary w XLS dodajemy osobno (jeśli nie dublują rekordu z XLS)."""
import re

import xlrd

from ..geokoder import bez_ogonkow, rdzen_ulicy
from ..normalizacja import rozbij_adres, tekst
from ..siec import KATALOG, pobierz as pobierz_plik
from .mapy_kml import placemarki

STRONA = "https://uml.lodz.pl/dla-mieszkancow/zdrowie/mapa-defibrylatorow-aed/"
XLS = "https://uml.lodz.pl/files/public/dla_mieszkanca/Defibrylatory2026.xls"
MID_DOMYSLNY = "1FMKFbebKJPYqD4C87pXWPqNjEHuEswE"


def _klucz(ulica, nr):
    return f"{rdzen_ulicy(ulica)}|{(nr or '').upper().replace(' ', '')}"


def pobierz():
    try:
        strona = pobierz_plik(STRONA, "lodz/strona.html").read_text(encoding="utf-8", errors="ignore")
    except RuntimeError as e:
        print(f"  ! Łódź: strona niedostępna ({e}) – używam znanych adresów plików")
        strona = ""
    xls_url = XLS
    m = re.search(r'href="([^"]+Defibrylatory[^"]*\.xlsx?)"', strona)
    if m:
        xls_url = m.group(1) if m.group(1).startswith("http") else "https://uml.lodz.pl" + m.group(1)
    mid = (re.search(r"mid=([A-Za-z0-9_-]{20,})", strona) or [None, MID_DOMYSLNY])[1]
    kml_url = f"https://www.google.com/maps/d/kml?mid={mid}&forcekml=1"

    wb = xlrd.open_workbook(str(pobierz_plik(xls_url, "lodz/defibrylatory.xls",
                                             kopia_zapasowa=KATALOG / "_probki_recznie" / "lodz_Defibrylatory2026.xls")))
    sh = wb.sheet_by_index(0)
    nagl = [tekst(x).lower() for x in sh.row_values(0)]
    idx = {k: next(i for i, h in enumerate(nagl) if h.startswith(k)) for k in ("podmiot", "obiekt", "adres", "lokalizacja", "godz")}
    rekordy, wg_klucza = [], {}
    for r in range(1, sh.nrows):
        w = sh.row_values(r)
        adres = tekst(w[idx["adres"]])
        if not adres and not tekst(w[idx["podmiot"]]):
            continue
        lp = tekst(w[0]).split(".")[0] or str(r)
        a = rozbij_adres(adres, "Łódź")
        podmiot, obiekt = tekst(w[idx["podmiot"]]), tekst(w[idx["obiekt"]])
        lok = tekst(w[idx["lokalizacja"]])
        rek = {
            "id_zrodlowe": lp, "dysponent_nazwa": podmiot,
            "nazwa_obiektu": obiekt if obiekt and not obiekt.lower().startswith("siedziba") else (f"{podmiot} – {obiekt}" if obiekt else podmiot),
            "opis_lokalizacji": lok, "godziny_opis": tekst(w[idx["godz"]]), "_adres": adres,
            "_tekst_opisowy": f"{podmiot} {obiekt} {lok}", "_flagi": [],
        }
        rekordy.append(rek)
        wg_klucza.setdefault(_klucz(a["ulica"], a["nr_budynku"]), []).append(rek)

    def _norm(s):
        return re.sub(r"[^a-z0-9]+", " ", bez_ogonkow((s or "").lower())).strip()

    dopasowane, niedopasowane, tylko_mapa = 0, [], []
    pms = placemarki(pobierz_plik(kml_url, "lodz/mapa.kml"))
    # przebieg 1: ulica + numer
    for pm in pms:
        adres = re.sub(r"(?i)^defibrylator\s*-\s*", "", pm["nazwa"])
        a = rozbij_adres(adres, "Łódź")
        kandydaci = [x for x in wg_klucza.get(_klucz(a["ulica"], a["nr_budynku"]), []) if "szerokosc_geograficzna" not in x]
        if kandydaci:
            kandydaci[0].update(szerokosc_geograficzna=pm["lat"], dlugosc_geograficzna=pm["lon"], zrodlo_wspolrzednych="mapa_dysponenta")
            dopasowane += 1
        else:
            niedopasowane.append((pm, adres, a))
    # przebieg 2: opis punktu na mapie zaczyna się od nazwy podmiotu z wykazu (+ zgodny rdzeń ulicy, jeśli jest)
    for pm, adres, a in niedopasowane:
        pierwsza = _norm(pm["opis"].split("\n")[0])
        kandydaci = [x for x in rekordy if "szerokosc_geograficzna" not in x and _norm(x["dysponent_nazwa"]) == pierwsza]
        if len(kandydaci) > 1:
            rdzen = rdzen_ulicy(a["ulica"])
            kandydaci = [x for x in kandydaci if rdzen and rdzen in bez_ogonkow(x["_adres"].lower())] or []
        if len(kandydaci) == 1:
            kandydaci[0].update(szerokosc_geograficzna=pm["lat"], dlugosc_geograficzna=pm["lon"], zrodlo_wspolrzednych="mapa_dysponenta")
            dopasowane += 1
        else:
            opis = pm["opis"].split("\n")
            tylko_mapa.append({
                "id_zrodlowe": f"mapa-{len(tylko_mapa) + 1}", "nazwa_obiektu": opis[0] if opis else adres,
                "opis_lokalizacji": " ".join(opis[1:]), "_adres": adres, "szerokosc_geograficzna": pm["lat"],
                "dlugosc_geograficzna": pm["lon"], "zrodlo_wspolrzednych": "mapa_dysponenta",
                "_tekst_opisowy": pm["opis"], "_flagi": ["tylko_na_mapie_brak_w_wykazie"], "_kandydat_duplikatu": True,
            })
    print(f"  Łódź: {len(rekordy)} rekordów z XLS, {dopasowane} połączonych z mapą, {len(tylko_mapa)} punktów tylko na mapie")
    meta = {"zrodlo_id": "JST-LDZ", "dostawca_danych": "Urząd Miasta Łodzi", "zrodlo_url": xls_url, "zbior_url": STRONA,
            "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": _data_xls(wb) or "",
            "miejscowosc": "Łódź", "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
    return [(meta, rekordy + tylko_mapa)]


def _data_xls(wb):
    # xlrd nie czyta metadanych pliku; data stanu z nazwy pliku (rok) – dokładna data zapisu: 2026-08-13 (sprawdzone ręcznie)
    return "2026-08-13"
