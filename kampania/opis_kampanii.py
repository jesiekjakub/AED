"""Opis kampanii „AED na ratunek” (pół strony A4, styl gov) – HTML -> PDF. Statystyki z wyników crawlera.

Uruchom: python kampania/opis_kampanii.py  -> kampania/opis_kampanii_AED_na_ratunek.pdf
"""
import csv
import json
from collections import Counter
from pathlib import Path

from ksiega import HASLO, chrome, data_uri
from logo import GOV, GRANAT, svg

KAT = Path(__file__).resolve().parent
KORZEN = KAT.parent



def przeglad_gmin(w):
    """Liczby z przeglądu stron gmin: przejrzane = gminy (6 cyfr TERYT), których strona odpowiedziała."""
    from collections import defaultdict
    by = defaultdict(set)
    for g in w:
        by[g["teryt"][:6]].add(g["status"])
    przejrzane = {k for k, v in by.items() if v - {"strona_niedostepna"}}
    lista = {k for k, v in by.items() if "lista_adresow" in v}
    bez = {k for k, v in by.items() if "podstrona_bez_listy" in v} - lista
    return {"przejrzane": len(przejrzane), "lista": len(lista), "bez_listy": len(bez), "wszystkie": 2479,
            "proc": round(100 * len(przejrzane) / 2479)}


def statystyki():
    s = {}
    g = KORZEN / "dane_surowe" / "gminy" / "odkryte.json"
    if g.exists():
        w = json.loads(g.read_text(encoding="utf-8"))
        c = Counter(x["status"] for x in w)
        s.update({"pg_" + k: v for k, v in przeglad_gmin(w).items()})
        s["gminy"] = len(w)
        s["gminy_lista"] = c["lista_adresow"]
        s["gminy_bez_listy"] = c["podstrona_bez_listy"]
    m = list(csv.DictReader(open(KORZEN / "zrodla" / "miasta_na_prawach_powiatu.csv", encoding="utf-8")))
    cm = Counter(x["status_udostepniania"] for x in m)
    s["miasta"] = len(m)
    s["miasta_maszynowo"] = cm["A"] + cm["B"]
    s["miasta_brak_listy"] = cm["D"] + cm["F"]
    r = json.loads((KORZEN / "dane" / "raport_jakosci.json").read_text(encoding="utf-8"))
    s["aed"] = r.get("stacjonarne", r.get("liczba_rekordow"))
    s["dgp"] = sum(1 for z in r["zrodla"] if z["zrodlo_id"].startswith("DGP-"))
    return s


def main():
    s = statystyki()
    html = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Kampania AED na ratunek</title><style>
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Regular.ttf").as_uri()}');font-weight:400}}
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Bold.ttf").as_uri()}');font-weight:700}}
@page{{size:A4;margin:12mm}} body{{font-family:Roboto,Arial,sans-serif;font-size:9.6pt;line-height:1.38;color:#1b1b1b;margin:0}}
.top{{display:flex;justify-content:space-between;align-items:center;border-bottom:4px solid {GOV};padding-bottom:3mm}}
.top img{{height:17mm}} .haslo{{font-size:15pt;font-weight:700;color:{GRANAT};text-align:right;max-width:95mm}}
h2{{font-size:10.5pt;color:{GOV};margin:3mm 0 1mm}} .kol{{display:grid;grid-template-columns:1fr 1fr;gap:6mm}} ul{{margin:0;padding-left:4.5mm}} li{{margin:0.6mm 0}}
.fakty{{display:flex;gap:3mm;margin-top:3mm}} .fakty div{{flex:1;background:#eef4fb;border-left:4px solid {GOV};padding:2mm 3mm}} .fakty b{{display:block;font-size:14pt;color:{GOV}}}
.stopka{{margin-top:3mm;font-size:8pt;color:#5e5e5e}}
</style></head><body>
<div class="top"><img src="{data_uri(svg())}" alt="AED na ratunek"><div class="haslo">{HASLO}</div></div>
<div class="fakty">
<div><b>{s.get('dgp', 5)}</b>instytucji publikuje dziś dane o AED w dane.gov.pl – każda w innym układzie kolumn</div>
<div><b>{s.get('pg_lista', '–')} z {s.get('pg_przejrzane', '–')}</b>przejrzanych stron gmin ({s.get('pg_proc', '–')}% wszystkich) ma wykaz adresów AED; kolejne {s.get('pg_bez_listy', '–')} pisze o AED bez wykazu</div>
<div><b>{s.get('miasta_brak_listy', '–')} z {s.get('miasta', 66)}</b>miast na prawach powiatu nie publikuje żadnej listy AED</div>
</div>
<div class="kol"><div>
<h2>Cel</h2><p style="margin:0">W 12 miesięcy wszystkie publicznie dostępne AED w Polsce w jednym, aktualnym <b>Wykazie zbiorczym AED</b> w dane.gov.pl – zasilanym automatycznie przez samych dysponentów, z informacją, czy urządzenie jest dostępne teraz i czy nie jest zamknięte na klucz.</p>
<h2>Do kogo</h2><ul>
<li><b>Gminy i powiaty</b> – zwłaszcza kupujące AED z Programu Ochrony Ludności i Obrony Cywilnej 2025–2026.</li>
<li><b>Duzi dysponenci</b>: InPost, Poczta Polska, PKP, przewoźnicy miejscy, lotniska, sieci handlowe, uczelnie.</li>
<li><b>Partnerzy</b>: OSP RP (Pierwszy Ratownik), Fundacja Ratuj Życie, OpenStreetMap Polska, WOPR, pogotowia.</li></ul>
</div><div>
<h2>Jak</h2><ul>
<li>Moduł AED w istniejących szkoleniach MC: „Samorząd otwarty na dane” (2000 samorządowców) i Akademia Danych.</li>
<li>Pismo Ministerstwa Cyfryzacji do każdej gminy przez e-Doręczenia i mail z portalu dane.gov.pl do wszystkich dostawców danych.</li>
<li><i>Nasza propozycja:</i> naklejka „AED na ratunek” z kodem QR na szafkę AED dla dysponentów, którzy opublikowali dane.</li>
<li>Strona dane.gov.pl/pl/aed: wykaz zbiorczy, szablon, walidator; portal przypomina dostawcom o aktualizacji.</li></ul>
<h2>Mierniki</h2><ul>
<li>liczba dysponentów publikujących zasób z flagą „wykaz AED”,</li>
<li>% AED z polami dostępność 24/7 i zabezpieczenie, aktualność danych (data weryfikacji).</li></ul>
</div></div>
<p class="stopka">Statystyki: automatyczny przegląd stron gmin (lista stron z Wikidaty, adresy weryfikowane w PRG; wynik to dolna granica) oraz 66 miast na prawach powiatu, listopad 2026 – Misja AED, HackNation 2026.</p>
</body></html>"""
    p = KAT / "opis_kampanii.html"
    p.write_text(html, encoding="utf-8")
    chrome(["--allow-file-access-from-files", f"--print-to-pdf={KAT / 'opis_kampanii_AED_na_ratunek.pdf'}", "--no-pdf-header-footer", p.as_uri()])
    print(s)


if __name__ == "__main__":
    main()
