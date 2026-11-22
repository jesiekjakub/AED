"""Eksport zbioru zbiorczego (CSV/GeoJSON/XLSX), raportu jakości, metadanych XML dla harwestera dane.gov.pl
oraz artefaktów wzorcowego zakresu danych (xlsx, Table Schema, szablon CSV)."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .schemat import KOLUMNY, KOLUMNY_DYSPONENTA, POLA, POLE, SLOWNIKI, WARTOSCI_PUSTE, WYMAGANE, table_schema

KORZEN = Path(__file__).resolve().parent.parent
DANE = KORZEN / "dane"
SCHEMAT = KORZEN / "schemat"
NAZWA = "aed_zbiorczy"

KOLOR_POZIOMU = {"W": "F4CCCC", "Z": "FFF2CC", "O": "D9EAD3", "A": "CFE2F3"}


# ------------------------------------------------------------------ zbiór zbiorczy
def zapisz_zbior(rekordy: list[dict]):
    """Zbiór główny = urządzenia stacjonarne. AED w pojazdach (bez stałej lokalizacji) -> osobny plik aed_mobilne.csv."""
    DANE.mkdir(exist_ok=True)
    mobilne = [r for r in rekordy if r.get("mobilny") == "tak"]
    rekordy = [r for r in rekordy if r.get("mobilny") != "tak"]
    with open(DANE / "aed_mobilne.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLUMNY, extrasaction="ignore")
        w.writeheader()
        w.writerows(mobilne)
    with open(DANE / f"{NAZWA}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLUMNY, extrasaction="ignore")
        w.writeheader()
        w.writerows(rekordy)
    cechy = []
    for r in rekordy:
        if r["szerokosc_geograficzna"] == "":
            continue
        props = {k: r[k] for k in KOLUMNY if k not in ("szerokosc_geograficzna", "dlugosc_geograficzna")}
        cechy.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["dlugosc_geograficzna"], r["szerokosc_geograficzna"]]},
                      "properties": props})
    (DANE / f"{NAZWA}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": cechy}, ensure_ascii=False), encoding="utf-8")
    wb = Workbook()
    ws = wb.active
    ws.title = "AED"
    ws.append(KOLUMNY)
    for r in rekordy:
        ws.append([r.get(k, "") for k in KOLUMNY])
    for i, k in enumerate(KOLUMNY, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=KOLOR_POZIOMU[POLE[k].poziom])
        ws.column_dimensions[get_column_letter(i)].width = 18
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(DANE / f"{NAZWA}.xlsx")
    return len(rekordy), len(cechy), len(mobilne)


# ------------------------------------------------------------------ dane dla strony (portal)
POLA_APP = ["id_aed", "nazwa_obiektu", "typ_obiektu", "miejscowosc", "ulica", "nr_budynku", "kod_pocztowy", "wojewodztwo",
            "szerokosc_geograficzna", "dlugosc_geograficzna", "zrodlo_wspolrzednych", "wewnatrz_budynku", "opis_lokalizacji",
            "dostep", "godziny_dostepnosci", "godziny_opis", "dostepny_24_7", "zabezpieczenie", "instrukcja_dostepu", "typ_montazu",
            "dysponent_nazwa", "zrodlo_id", "dostawca_danych", "zrodlo_url", "data_stanu_zrodla", "flagi_jakosci", "kompletnosc_proc"]


def zapisz_dla_portalu(rekordy: list[dict], cel: Path):
    """Kopiuje wyniki do assets portalu (portal/src/assets/aed) – strona AED czyta je statycznie."""
    import shutil
    cel.mkdir(parents=True, exist_ok=True)
    stac = [{k: r.get(k, "") for k in POLA_APP} for r in rekordy if r.get("mobilny") != "tak"]
    (cel / "aed_app.json").write_text(json.dumps(stac, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for plik in ["aed_zbiorczy.csv", "aed_zbiorczy.geojson", "aed_zbiorczy.xlsx", "aed_mobilne.csv", "raport_jakosci.json",
                 "metadane_dane_gov_pl.xml", "pokrycie_pol.csv"]:
        if (DANE / plik).exists():
            shutil.copy(DANE / plik, cel / plik)
    for plik in ["wzorcowy_zakres_danych_AED.xlsx", "tableschema_aed.json", "szablon_aed_dla_dysponenta.csv"]:
        if (SCHEMAT / plik).exists():
            shutil.copy(SCHEMAT / plik, cel / plik)
    rej = KORZEN / "zrodla" / "rejestr_zrodel.json"
    if rej.exists():
        shutil.copy(rej, cel / "rejestr_zrodel.json")


# ------------------------------------------------------------------ raport jakości
def raport(rekordy: list[dict], zrodla_meta: list[dict], zablokowane: list[str] = ()) -> dict:
    wg_zr = defaultdict(list)
    for r in rekordy:
        wg_zr[r["zrodlo_id"]].append(r)
    zrodla = []
    for m in zrodla_meta:
        rs = wg_zr.get(m["zrodlo_id"], [])
        if not rs:
            continue
        flagi = Counter(f.split(":")[0].split("(")[0].rstrip("_0123456789m") or f for r in rs for f in r["flagi_jakosci"].split(";") if f)
        zrodla.append({
            "zrodlo_id": m["zrodlo_id"], "dostawca_danych": m["dostawca_danych"], "zrodlo_url": m.get("zbior_url") or m["zrodlo_url"],
            "licencja": m.get("licencja_zrodla", ""), "data_stanu": m.get("data_stanu_zrodla", ""), "liczba_rekordow": len(rs),
            "z_wspolrzednymi": sum(r["szerokosc_geograficzna"] != "" for r in rs),
            "wspolrzedne_ze_zrodla": sum(r["zrodlo_wspolrzednych"] in ("mapa_dysponenta", "pomiar_gps") for r in rs),
            "wspolrzedne_z_geokodowania": sum(str(r["zrodlo_wspolrzednych"]).startswith("geokodowanie") for r in rs),
            "z_teryt": sum(bool(r["teryt_gmina"]) for r in rs),
            "srednia_kompletnosc_proc": round(sum(r["kompletnosc_proc"] for r in rs) / len(rs)),
            "flagi": dict(flagi.most_common()),
        })
    pokrycie = {}
    for p in POLA:
        if p.poziom == "A":
            continue
        pokrycie[p.nazwa] = {"poziom": p.poziom, **{z: round(100 * sum(r.get(p.nazwa) not in WARTOSCI_PUSTE for r in rs) / len(rs))
                                                   for z, rs in wg_zr.items()}}
    calosc = {
        "wygenerowano": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "liczba_rekordow": len(rekordy), "liczba_zrodel": len(zrodla),
        "stacjonarne": sum(r["mobilny"] != "tak" for r in rekordy), "mobilne": sum(r["mobilny"] == "tak" for r in rekordy),
        "zrodla_blokujace_pobieranie_automatyczne": list(zablokowane),
        "stacjonarne_z_wspolrzednymi": sum(r["szerokosc_geograficzna"] != "" and r["mobilny"] != "tak" for r in rekordy),
        "dostepne_24_7": sum(r["dostepny_24_7"] == "tak" for r in rekordy),
        "zabezpieczenie_znane": sum(r["zabezpieczenie"] not in WARTOSCI_PUSTE for r in rekordy),
        "z_dysponentem": sum(bool(r["dysponent_nazwa"]) for r in rekordy),
        "srednia_kompletnosc_proc": round(sum(r["kompletnosc_proc"] for r in rekordy) / max(len(rekordy), 1)),
        "wg_wojewodztw": dict(Counter(r["wojewodztwo"] or "nieustalone" for r in rekordy).most_common()),
        "zrodla": zrodla, "pokrycie_pol_proc": pokrycie,
    }
    (DANE / "raport_jakosci.json").write_text(json.dumps(calosc, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(DANE / "raport_jakosci_zrodla.csv", "w", newline="", encoding="utf-8") as f:
        kol = [k for k in zrodla[0] if k != "flagi"] + ["flagi"] if zrodla else []
        w = csv.DictWriter(f, fieldnames=kol)
        w.writeheader()
        for z in zrodla:
            w.writerow({**z, "flagi": "; ".join(f"{k}={v}" for k, v in z["flagi"].items())})
    with open(DANE / "pokrycie_pol.csv", "w", newline="", encoding="utf-8") as f:
        zr = list(wg_zr)
        w = csv.writer(f)
        w.writerow(["pole", "poziom"] + zr)
        for pole, d in pokrycie.items():
            w.writerow([pole, d["poziom"]] + [d[z] for z in zr])
    return calosc


# ------------------------------------------------------------------ metadane XML (harwester dane.gov.pl, schemat 1.13)
def metadane_xml(rekordy: list[dict], baza_url: str, data_stanu: str) -> Path:
    from xml.sax.saxutils import escape as e
    teraz = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    teryt = sorted({r["teryt_gmina"][:2] for r in rekordy if r["teryt_gmina"]})
    regiony = f"<regions>{''.join(f'<terytIdent>{t}</terytIdent>' for t in teryt)}</regions>" if teryt else ""
    data_el = f"<dataDate>{data_stanu}</dataDate>" if data_stanu else ""

    def zasob(ext_id, plik, tytul_pl, tytul_en, opis_pl, opis_en):
        return f"""
      <resource status="published">
        <extIdent>{ext_id}</extIdent>
        <url>{e(baza_url.rstrip('/') + '/' + plik)}</url>
        <title><polish>{e(tytul_pl)}</polish><english>{e(tytul_en)}</english></title>
        <description><polish>{e(opis_pl)}</polish><english>{e(opis_en)}</english></description>
        <availability>remote</availability>
        {data_el}
        <lastUpdateDate>{teraz}</lastUpdateDate>
        <hasDynamicData>false</hasDynamicData>
        <hasHighValueData>false</hasHighValueData>
        <hasHighValueDataFromEuropeanCommissionList>false</hasHighValueDataFromEuropeanCommissionList>
        <hasResearchData>false</hasResearchData>
        <containsProtectedData>false</containsProtectedData>
        {regiony}
      </resource>"""

    opis_pl = ("Zbiorczy wykaz automatycznych defibrylatorów zewnętrznych (AED) zebrany z danych publikowanych przez dysponentów "
               "(gminy, miasta i inne instytucje), ujednolicony do wzorcowego zakresu danych Misji AED. Każdy rekord wskazuje dostawcę danych, "
               "adres źródła, datę stanu oraz flagi jakości. Współrzędne w WGS84 (EPSG:4326); kody TERYT wg usługi geokodowania GUGiK.")
    opis_en = ("Aggregated list of automated external defibrillators (AED) collected from data published by their holders (municipalities and other "
               "institutions), harmonised to the Misja AED reference schema. Each record states the data provider, source URL, reference date and quality flags.")
    xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<ns2:datasets xmlns:ns2="urn:otwarte-dane:harvester:1.13" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dataset status="published">
    <extIdent>misja-aed-defibrylatory-aed</extIdent>
    <title><polish>Defibrylatory AED – wykaz zbiorczy (Misja AED)</polish><english>AED defibrillators – aggregated list (Misja AED)</english></title>
    <description><polish>{e(opis_pl)}</polish><english>{e(opis_en)}</english></description>
    <updateFrequency>weekly</updateFrequency>
    <hasDynamicData>false</hasDynamicData>
    <hasHighValueData>false</hasHighValueData>
    <hasHighValueDataFromEuropeanCommissionList>false</hasHighValueDataFromEuropeanCommissionList>
    <hasResearchData>false</hasResearchData>
    <categories><category>HEAL</category><category>REGI</category></categories>
    <conditions>
      <source>true</source>
      <modification>true</modification>
      <dbOrCopyrighted>Warunek wymagany</dbOrCopyrighted>
      <dbOrCopyrightedLicenseChosen>CC BY 4.0</dbOrCopyrightedLicenseChosen>
    </conditions>
    <resources>{zasob('misja-aed-csv', NAZWA + '.csv', 'Defibrylatory AED – CSV', 'AED defibrillators – CSV', 'Plik CSV (UTF-8, separator przecinek) zgodny ze wzorcowym zakresem danych.', 'CSV file (UTF-8, comma) following the reference schema.')}{zasob('misja-aed-geojson', NAZWA + '.geojson', 'Defibrylatory AED – GeoJSON', 'AED defibrillators – GeoJSON', 'Warstwa punktowa GeoJSON (EPSG:4326).', 'GeoJSON point layer (EPSG:4326).')}{zasob('misja-aed-raport', 'raport_jakosci.json', 'Raport jakości danych AED', 'AED data quality report', 'Kompletność pól i wykryte problemy w podziale na źródła.', 'Field completeness and detected issues per source.')}
    </resources>
    <tags>
      <tag lang="pl">AED</tag><tag lang="pl">defibrylator</tag><tag lang="pl">ratownictwo</tag><tag lang="pl">pierwsza pomoc</tag><tag lang="pl">zdrowie</tag>
      <tag lang="en">AED</tag><tag lang="en">defibrillator</tag>
    </tags>
    <lastUpdateDate>{teraz}</lastUpdateDate>
  </dataset>
</ns2:datasets>
"""
    p = DANE / "metadane_dane_gov_pl.xml"
    p.write_text(xml, encoding="utf-8")
    return p


def waliduj_xml(p: Path) -> list[str]:
    from lxml import etree
    xsd = etree.XMLSchema(etree.parse(str(SCHEMAT / "xml_import_otwarte_dane_1_13.xsd")))
    doc = etree.parse(str(p))
    return [] if xsd.validate(doc) else [str(x) for x in xsd.error_log]


# ------------------------------------------------------------------ wzorcowy zakres danych
def artefakty_schematu(pokrycie: dict | None = None):
    SCHEMAT.mkdir(exist_ok=True)
    (SCHEMAT / "tableschema_aed.json").write_text(json.dumps(table_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
    przyklady = [
        {"id_aed": "SP3-001", "status": "aktywny", "nazwa_obiektu": "Szkoła Podstawowa nr 3", "typ_obiektu": "szkola_przedszkole",
         "wojewodztwo": "łódzkie", "powiat": "Łódź", "gmina": "Łódź", "teryt_gmina": "106101", "simc": "0957650", "ulic": "15676",
         "miejscowosc": "Łódź", "ulica": "ul. Paradna", "nr_budynku": "36", "kod_pocztowy": "93-345",
         "szerokosc_geograficzna": "51.709489", "dlugosc_geograficzna": "19.480500", "zrodlo_wspolrzednych": "pomiar_gps",
         "wewnatrz_budynku": "nie", "kondygnacja": "0", "opis_lokalizacji": "Na elewacji przy wejściu głównym, w zielonej kapsule",
         "opis_lokalizacji_en": "On the facade next to the main entrance, green cabinet", "dostep": "publiczny", "godziny_dostepnosci": "24/7",
         "dostepny_24_7": "tak", "zabezpieczenie": "szafka_z_alarmem", "instrukcja_dostepu": "Otwórz szafkę – włączy się alarm i powiadomienie do szkoły",
         "typ_montazu": "elewacja", "mobilny": "nie", "sezonowy": "nie", "producent": "Philips", "model": "HeartStart FRx", "tryb_pediatryczny": "tak",
         "data_instalacji": "2023-05-12", "stan_techniczny": "sprawny", "data_ostatniego_przegladu": "2026-06-01", "data_waznosci_elektrod": "2027-03-31",
         "data_waznosci_baterii": "2029-01-31", "data_weryfikacji": "2026-11-01", "sposob_weryfikacji": "kontrola_na_miejscu",
         "dysponent_nazwa": "Szkoła Podstawowa nr 3 w Łodzi", "dysponent_typ": "jednostka_jst", "dysponent_regon": "000123456",
         "kontakt": "sekretariat@sp3.example.pl"},
        {"id_aed": "UM-014", "status": "aktywny", "nazwa_obiektu": "Urząd Miasta – Biuro Obsługi Mieszkańców", "typ_obiektu": "urzad_administracja",
         "miejscowosc": "Przykładowo", "ulica": "pl. Wolności", "nr_budynku": "1", "kod_pocztowy": "00-001",
         "szerokosc_geograficzna": "52.229676", "dlugosc_geograficzna": "21.012229", "zrodlo_wspolrzednych": "mapa_dysponenta",
         "wewnatrz_budynku": "tak", "kondygnacja": "0", "opis_lokalizacji": "Hol główny, przy stanowisku ochrony", "dostep": "publiczny",
         "godziny_dostepnosci": "Mo-Fr 07:30-15:30", "dostepny_24_7": "nie", "zabezpieczenie": "u_personelu",
         "instrukcja_dostepu": "Poproś pracownika ochrony", "typ_montazu": "wewnatrz_budynku", "mobilny": "nie", "sezonowy": "nie",
         "tryb_pediatryczny": "nieznane", "stan_techniczny": "sprawny", "data_weryfikacji": "2026-10-15", "sposob_weryfikacji": "deklaracja_dysponenta",
         "dysponent_nazwa": "Urząd Miasta Przykładowo", "dysponent_typ": "jst"},
    ]
    with open(SCHEMAT / "szablon_aed_dla_dysponenta.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLUMNY_DYSPONENTA, extrasaction="ignore")
        w.writeheader()
        for p in przyklady:
            w.writerow({k: p.get(k, "") for k in KOLUMNY_DYSPONENTA})

    wb = Workbook()
    ws = wb.active
    ws.title = "Instrukcja"
    for linia in [
        "Wzorcowy zakres danych o defibrylatorach AED – Misja AED (HackNation 2026)",
        "",
        "Cel: jednolity sposób udostępniania danych o AED w portalu dane.gov.pl przez wszystkich dysponentów (gminy, instytucje, firmy).",
        "Format publikacji: CSV, kodowanie UTF-8, separator przecinek, pierwszy wiersz = nazwy pól z arkusza 'Pola'. Jeden wiersz = jedno urządzenie.",
        "Poziomy pól: W – wymagane, Z – zalecane, O – opcjonalne, A – dodawane wyłącznie przez agregator (dysponent ich nie wypełnia).",
        "Wartości słownikowe – wyłącznie z arkusza 'Słowniki'. Daty: RRRR-MM-DD. Godziny dostępności: składnia opening_hours (np. 24/7, Mo-Fr 08:00-16:00).",
        "Współrzędne: WGS84 (EPSG:4326), stopnie dziesiętne, kropka jako separator, min. 5 miejsc po przecinku – punkt przy urządzeniu, nie środek działki.",
        "Dane osobowe: nie publikujemy imion, nazwisk ani prywatnych telefonów opiekunów urządzeń – wyłącznie kontakt instytucjonalny.",
        "Metadane zbioru na dane.gov.pl – patrz arkusz 'Metadane zbioru'. Gotowy szablon: szablon_aed_dla_dysponenta.csv. Walidacja: python -m crawler waliduj plik.csv",
        "Pole 'zabezpieczenie' jest wymagane, bo AED zamknięty na klucz nie pomoże świadkowi zdarzenia – a dziś niemal żadne źródło tej informacji nie podaje.",
    ]:
        ws.append([linia])
    ws.column_dimensions["A"].width = 160
    ws["A1"].font = Font(bold=True, size=14)

    ws = wb.create_sheet("Pola")
    nagl = ["Lp.", "Pole", "Grupa", "Poziom", "Typ", "Opis", "Słownik / format", "Przykład", "Odpowiednik w OpenStreetMap", "Uwagi"]
    if pokrycie:
        nagl.append("Wypełnienie w zebranych źródłach (śr. %)")
    ws.append(nagl)
    for i, p in enumerate(POLA, 1):
        fmt = p.slownik and f"słownik: {p.slownik}" or (p.wzorzec and f"wzorzec: {p.wzorzec}") or ("RRRR-MM-DD" if p.typ == "date" else "")
        if p.min is not None:
            fmt = f"liczba {p.min}–{p.max}"
        wiersz = [i, p.nazwa, p.grupa, p.poziom, p.typ, p.opis, fmt, p.przyklad, p.osm, p.uwagi]
        if pokrycie:
            d = pokrycie.get(p.nazwa)
            wiersz.append(round(sum(v for k, v in d.items() if k != "poziom") / max(len(d) - 1, 1)) if d else "")
        ws.append(wiersz)
        ws.cell(row=i + 1, column=4).fill = PatternFill("solid", fgColor=KOLOR_POZIOMU[p.poziom])
    for c, w in zip("ABCDEFGHIJK", [5, 28, 22, 8, 9, 70, 26, 34, 26, 40, 16]):
        ws.column_dimensions[c].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Słowniki")
    ws.append(["Słownik", "Wartość", "Znaczenie", "Używany w polach"])
    for nazwa, wart in SLOWNIKI.items():
        pola = ", ".join(p.nazwa for p in POLA if p.slownik == nazwa)
        for k, v in wart.items():
            ws.append([nazwa, k, v, pola])
    for c, w in zip("ABCD", [22, 26, 80, 50]):
        ws.column_dimensions[c].width = w
    for c in ws[1]:
        c.font = Font(bold=True)

    ws = wb.create_sheet("Przykład")
    ws.append(KOLUMNY_DYSPONENTA)
    for p in przyklady:
        ws.append([p.get(k, "") for k in KOLUMNY_DYSPONENTA])
    for i, k in enumerate(KOLUMNY_DYSPONENTA, 1):
        ws.cell(row=1, column=i).font = Font(bold=True)
        ws.cell(row=1, column=i).fill = PatternFill("solid", fgColor=KOLOR_POZIOMU[POLE[k].poziom])
        ws.column_dimensions[get_column_letter(i)].width = 20

    ws = wb.create_sheet("Metadane zbioru")
    ws.append(["Metadana (dane.gov.pl)", "Zalecana wartość", "Uwagi"])
    for w in [
        ["Tytuł", "Defibrylatory AED – [nazwa dysponenta]", "Stały wzorzec tytułu ułatwia wyszukiwanie"],
        ["Opis", "Wykaz automatycznych defibrylatorów zewnętrznych (AED) … zgodny ze wzorcowym zakresem Misji AED", ""],
        ["Kategoria", "HEAL (Zdrowie); dodatkowo REGI (Regiony i miasta)", "Kody kategorii z harwestera XML"],
        ["Słowa kluczowe", "AED, defibrylator, ratownictwo, pierwsza pomoc, misja-aed", "Tag 'misja-aed' pozwala zebrać wszystkie zbiory"],
        ["Licencja", "CC0 1.0 (zalecana) lub CC BY 4.0", "Bez ograniczeń ponownego wykorzystania"],
        ["Częstotliwość aktualizacji", "Co miesiąc lub przy każdej zmianie (dodanie/usunięcie AED)", "updateFrequency: monthly"],
        ["Format zasobu", "CSV (UTF-8) + opcjonalnie GeoJSON", "Format odczytywalny maszynowo – nie PDF/DOC"],
        ["Data danych", "Data stanu wykazu", "Uzupełniać przy każdej aktualizacji"],
        ["Zasięg terytorialny (regions)", "Kod TERYT gminy/powiatu", "Pole terytIdent w XML"],
        ["Publikacja automatyczna", "Harwester XML dane.gov.pl (schemat 1.13) – plik metadane_dane_gov_pl.xml", "Raz skonfigurowany – aktualizuje się sam"],
    ]:
        ws.append(w)
    for c, w in zip("ABC", [30, 80, 60]):
        ws.column_dimensions[c].width = w
    for c in ws[1]:
        c.font = Font(bold=True)

    if pokrycie:
        ws = wb.create_sheet("Pokrycie w źródłach")
        zr = [k for k in next(iter(pokrycie.values())) if k != "poziom"]
        ws.append(["Pole", "Poziom"] + zr)
        for pole, d in pokrycie.items():
            ws.append([pole, d["poziom"]] + [d[z] for z in zr])
        ws.column_dimensions["A"].width = 28
        for c in ws[1]:
            c.font = Font(bold=True)
    wb.save(SCHEMAT / "wzorcowy_zakres_danych_AED.xlsx")
