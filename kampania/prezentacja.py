"""Prezentacja „AED na ratunek” – HTML (16:9) -> PDF. Liczby z wyników crawlera, zrzuty z kampania/zrzuty/.

Uruchom: python kampania/prezentacja.py -> kampania/prezentacja_AED_na_ratunek.pdf
"""
import base64
import csv
import json
from collections import Counter
from pathlib import Path

from ksiega import HASLO, chrome, data_uri, qr_svg
from logo import CZERWONY, GOV, GRANAT, WARIANTY, svg
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crawler.schemat import POLA  # noqa: E402
POLA_D = [p for p in POLA if p.poziom != 'A']
POLA_A = [p for p in POLA if p.poziom == 'A']

KAT = Path(__file__).resolve().parent
KORZEN = KAT.parent
ZRZUTY = KAT / "zrzuty"


def img(nazwa: str, styl: str = "") -> str:
    p = ZRZUTY / nazwa
    if not p.exists():
        return f'<div class="brak" style="{styl}">[zrzut: {nazwa}]</div>'
    return f'<img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}" style="{styl}">'



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


def dane():
    r = json.loads((KORZEN / "dane" / "raport_jakosci.json").read_text(encoding="utf-8"))
    g = json.loads((KORZEN / "dane_surowe" / "gminy" / "odkryte.json").read_text(encoding="utf-8"))
    rej = json.loads((KORZEN / "zrodla" / "rejestr_zrodel.json").read_text(encoding="utf-8"))["zrodla"]
    m = list(csv.DictReader(open(KORZEN / "zrodla" / "miasta_na_prawach_powiatu.csv", encoding="utf-8")))
    cg = Counter(x["status"] for x in g)
    return {
        "aed": r["stacjonarne"], "mob": r["mobilne"], "wsp": r["stacjonarne_z_wspolrzednymi"], "h24": r["dostepne_24_7"],
        "zrodel": r["liczba_zrodel"], "kompl": r["srednia_kompletnosc_proc"], "woj": len([k for k in r["wg_wojewodztw"] if k != "nieustalone"]),
        **{"pg_" + k: v for k, v in przeglad_gmin(g).items()},
        "gminy": len(g), "g_lista": cg["lista_adresow"], "g_bez": cg["podstrona_bez_listy"], "g_brak": cg["brak_podstrony_aed"], "g_nied": cg["strona_niedostepna"],
        "rej": len(rej), "rej_st": Counter(x["status_udostepniania"] for x in rej),
        "m_st": Counter(x["status_udostepniania"] for x in m), "dgp": sum(1 for z in r["zrodla"] if z["zrodlo_id"].startswith("DGP-")),
        "pokrycie": r["pokrycie_pol_proc"],
    }


_NR = [1]


def slajd(tytul: str, tresc: str, _nr_ignorowany: int = 0) -> str:
    _NR[0] += 1
    nr = _NR[0]
    return (f'<section class="s"><header><h2>{tytul}</h2><img src="{data_uri(svg())}" class="mini"></header>'
            f'<div class="c">{tresc}</div><footer>AED na ratunek · Misja AED · HackNation 2026<span>{nr}</span></footer></section>')


def main():
    d = dane()
    logo = data_uri(svg())
    s = []

    def sl(kicker, tytul, tresc, klasa=""):
        _NR[0] += 1
        return (f'<section class="s {klasa}"><div class="kicker">{kicker}</div><h2>{tytul}</h2>'
                f'<img src="{logo}" class="mini"><div class="c">{tresc}</div>'
                f'<footer>AED na ratunek · HackNation 2026<span>{_NR[0]}</span></footer></section>')

    def tel(nazwa, h="112mm"):
        return f'<div class="tel">{img(nazwa, f"height:{h};display:block")}</div>'

    def shot(nazwa, styl="width:100%"):
        return f'<div class="shot">{img(nazwa, styl + ";display:block")}</div>'

    # 1. TYTUŁ
    s.append(f"""<section class="s tytul"><div class="tl">
<img src="{logo}" style="height:34mm">
<h1>Pokaż, gdzie jest AED.<br><span>Każda minuta się liczy.</span></h1>
<p class="lead">Jeden wykaz wszystkich defibrylatorów w Polsce –<br>prosto w portalu dane.gov.pl.</p>
<p class="meta">Misja AED – Dane na ratunek · Ministerstwo Cyfryzacji · HackNation 2026</p></div>
<div class="tr">{tel('aed_telefon_najblizszy.png', '138mm')}</div></section>""")

    # 2. PROBLEM
    s.append(sl("Problem", "Dane o AED istnieją. Tylko nikt ich nie znajdzie na czas.", f"""
<div class="probl"><div class="liczby2">
<div><b>{d['pg_lista']}<small> z {d['pg_przejrzane']}</small></b><span>gmin ma na stronie listę adresów AED<i>przejrzeliśmy automatycznie {d['pg_proc']}% gmin w Polsce</i></span></div>
<div><b>{d['m_st']['D'] + d['m_st']['F']}<small> z 66</small></b><span>dużych miast nie publikuje żadnej listy</span></div>
<div><b>3<small> z 18 297</small></b><span>punktów AED w OpenStreetMap mówi, czy szafka jest zamknięta na klucz</span></div>
<div><b>tylko {d['dgp']}</b><span>instytucji publikuje AED w dane.gov.pl – każda w innym układzie kolumn</span></div>
</div>
<div class="pdfy"><div class="p1">{shot('dzis_pdf_krakow.png')}<span>Kraków: tabela w PDF</span></div>
<div class="p2">{shot('dzis_pdf_lublin.png')}<span>Lublin: lista w PDF, bez współrzędnych</span></div></div></div>"""))

    # 3. POMYSŁ
    s.append(sl("Rozwiązanie", "Każdy publikuje swoje AED. Portal sam łączy je w jedną listę.", f"""
<div class="kroki3">
<div><em>1</em><b>Gmina, szkoła albo firma publikuje listę swoich AED</b>tak jak każdy inny zbiór w dane.gov.pl</div><span>→</span>
<div><em>2</em><b>Portal sprawdza, czy plik jest zgodny ze wzorem</b>i pokazuje, co poprawić</div><span>→</span>
<div class="hl"><em>3</em><b>Co noc wszystko trafia do jednego wykazu AED</b>przy każdym urządzeniu widać, kto je dodał</div>
</div>
<p class="duzy" style="text-align:center;margin-top:12mm">Działa tak samo jak wykaz DGA, który portal już ma.</p>""", "srodek"))

    # 4. EFEKT – tabela
    s.append(sl("Efekt", "Jeden wykaz AED w portalu – z podpisem pod każdym wierszem", f"""
<div class="g64"><div>{shot('wykaz_tabela_w_portalu.png')}</div>
<div class="fakty">
<p><b>318 AED od 5 urzędów</b> scalonych w lokalnym portalu dane.gov.pl</p>
<p><b>Każdy wiersz</b> mówi, kto go opublikował, gdzie jest źródło i z kiedy są dane</p>
<p><b>Ta sama tabela</b> co w wykazie DGA – sortowanie, stronicowanie, API</p>
<p><b>Do pobrania</b>: CSV, XLSX, GeoJSON</p></div></div>"""))

    # 5. ZASILANIE
    s.append(sl("Zasilanie", "Dwie drogi do wykazu: ręcznie albo automatycznie", f"""
<h3>Ręcznie – jedno pole w panelu dostawcy</h3>
<div class="g64" style="grid-template-columns:2.2fr 1fr;align-items:center">{shot('admin_checkbox_kadr.png')}
<p class="podpis" style="margin:0">Nasze pole stoi tuż pod polem wykazu DGA i działa tak samo: zaznaczasz – zasób trafia do wykazu.</p></div>
<h3 style="margin-top:6mm">Automatycznie – harwester XML</h3>
<div class="g64" style="grid-template-columns:2.2fr 1fr;align-items:center"><pre>&lt;resource status="published"&gt;
  &lt;url&gt;https://bip.gmina.pl/aed.csv&lt;/url&gt;  ...
  <mark>&lt;containsAedList&gt;true&lt;/containsAedList&gt;</mark>
&lt;/resource&gt;</pre>
<p class="podpis" style="margin:0">Duże miasto czy firma z setkami AED ustawia to raz. Nowy element dodaliśmy do schematu XSD portalu (wersja 1.14).</p></div>"""))

    # 6. MIESZKANIEC
    s.append(sl("Kroki użytkownika · mieszkaniec", "Od wejścia na stronę do trasy do AED – trzy kroki", f"""
<div class="mies">
<div>{tel('aed_telefon_start.png', '92mm')}<p><em>1</em>Wchodzi w „Mapa AED” w menu portalu</p></div>
<div>{tel('aed_telefon_najblizszy.png', '92mm')}<p><em>2</em>Klika „Pokaż najbliższy AED”</p></div>
<div class="szer">{shot('aed_mapa_szczegoly.png', 'width:100%;max-height:80mm;object-fit:cover;object-position:top right')}<p><em>3</em>Widzi, czy AED jest teraz dostępny i czy nie jest zamknięty – i wyznacza trasę</p>
<div class="znaczek">WCAG 2.2 AA · 0 błędów <small>(test axe-core, komputer i telefon)</small></div></div>
</div>"""))

    # 7. DYSPONENT
    s.append(sl("Kroki użytkownika · dysponent", "Urzędnik nie musi znać się na danych", f"""
<div class="dwie">
<div>{shot('formularz_dysponenta.png', 'width:100%;max-height:78mm;object-fit:cover;object-position:top')}
<p class="podpis"><b>Kilka AED?</b> Formularz sam robi poprawny plik CSV, położenie klika się na mapie. <i>(Nasza propozycja – portal nie ma takiego kreatora.)</i></p></div>
<div>{shot('walidator.png', 'width:100%;max-height:78mm;object-fit:cover;object-position:top')}
<p class="podpis"><b>Ma już arkusz?</b> Walidator mówi po polsku, co poprawić. Plik nie wychodzi z komputera.</p></div>
</div>
<div class="pasek"><span><em>1</em>Przygotuj plik</span><span><em>2</em>Sprawdź walidatorem</span><span><em>3</em>Dodaj zasób i zaznacz „wykaz AED”</span><span class="hl">Gotowe – reszta dzieje się sama</span></div>"""))

    # 8. WZORZEC
    s.append(sl("Wzorcowy zakres danych", "Każdy AED opisany tak samo – w całej Polsce", f"""
<div class="pytania">
<div><b>Gdzie dokładnie?</b>współrzędne, adres, opis miejsca: „przy wejściu, na lewo”</div>
<div><b>Czy jest dostępny teraz?</b>godziny, 24/7, sezonowość</div>
<div class="hl"><b>Czy otworzę go bez klucza?</b>nowe pole <code>zabezpieczenie</code>: brak, szafka z alarmem, kod, klucz, u personelu</div>
<div><b>Kto za to ręczy?</b>dysponent, źródło, data sprawdzenia</div>
</div>
<p class="duzy">{len(POLA_D)} pól dla dysponenta (wymagane, zalecane, opcjonalne) + {len(POLA_A)} pól pochodzenia, które portal dopisuje sam.
<span class="szary">Pliki: XLSX, Table Schema, szablon CSV.</span></p>"""))

    # 8b. PLIK XLSX
    s.append(sl("Wzorcowy zakres danych · plik XLSX", "Tak wygląda wzór, który dostaje każdy dysponent", f"""
{shot('xlsx_pola.png', 'width:100%;max-height:100mm;object-fit:cover;object-position:top left')}
<p class="podpis">Fragment arkusza „Pola”. <b>Pełny plik w repozytorium</b> (<code>schemat/wzorcowy_zakres_danych_AED.xlsx</code>): {len(POLA)} pól – {sum(x.poziom == 'W' for x in POLA)} wymaganych, {sum(x.poziom == 'Z' for x in POLA)} zalecanych, {sum(x.poziom == 'O' for x in POLA)} opcjonalnych i {sum(x.poziom == 'A' for x in POLA)} dopisywanych przez portal – oraz słowniki, przykład wypełnienia i metadane zbioru.</p>"""))

    # 9. DANE JUŻ DZIŚ
    s.append(sl("Dane na start", f"Zebraliśmy już {d['aed']} AED z {d['zrodel']} źródeł", f"""
<div class="g64"><div>{shot('aed_desktop_start.png', 'width:100%;max-height:112mm;object-fit:cover;object-position:top')}</div>
<div class="fakty">
<p><b>Crawler</b> czyta CSV, XLS, PDF, mapy KML i strony urzędów gmin</p>
<p><b>{d['mob']} AED w pojazdach</b> – m.in. w tramwajach i autobusach ZTM Gdańsk, wyszukane automatycznie w API dane.gov.pl</p>
<p><b>97% z dokładnym położeniem</b> z urzędowego rejestru adresów (PRG). Geokoder GUGiK ma limity, więc zbudowaliśmy własny indeks offline</p>
<p><b>Tylko oficjalne źródła:</b> urzędy i instytucje. Dane z OpenStreetMap nie trafiają do wykazu. Każdy rekord ma źródło, datę i flagi jakości</p></div></div>"""))

    # 10. KAMPANIA
    s.append(sl("Kampania", "„AED na ratunek” – jak przekonamy dysponentów", f"""
<div class="kamp">
<div class="logo-duze"><img src="{logo}"><p class="szary">Logo zbudowane tak jak znak Otwarte Dane – ta sama konstrukcja, kolory i czcionka. Pełna księga znaku jest w repozytorium.</p></div>
<div class="fakty">
<p><b>Do kogo mówimy:</b> do gmin, które właśnie kupują AED z Programu Ochrony Ludności 2025–2026, oraz do dużych dysponentów, takich jak Poczta Polska, PKP i przewoźnicy miejscy.</p>
<p><b>Jak do nich dotrzemy:</b> Ministerstwo Cyfryzacji wysyła pismo do każdej gminy przez e-Doręczenia, a portal dane.gov.pl wysyła maila do wszystkich swoich dostawców danych. Temat trafia też do szkoleń, które ministerstwo już prowadzi dla samorządów („Samorząd otwarty na dane”, Akademia Danych).</p>
<p><b>Co dostaje dysponent:</b> prosty formularz albo szablon, walidator i dwustronicową instrukcję.</p></div>
<div><div class="naklejka"><img src="{logo}" style="width:100%"><div style="display:flex;gap:3mm;align-items:center;margin-top:3mm"><img src="{data_uri(qr_svg('https://dane.gov.pl/pl/aed'))}" style="width:22mm"><small>Ten AED jest na mapie<br><b>dane.gov.pl/pl/aed</b><br>Dzwoń <b>112</b></small></div></div>
<p class="podpis" style="text-align:center;margin-top:6mm"><b>Naklejka na szafkę AED</b> (nasza propozycja): kod QR prowadzi do mapy.</p></div>
</div>"""))

    # 10b. WDROŻENIE
    s.append(sl("Wdrożenie", "Gotowe do włączenia w prawdziwym dane.gov.pl", f"""
<div class="dwie"><div class="fakty">
<p><b>To nie jest makieta.</b> Zmiany są w oficjalnym kodzie portalu, oznaczone <code># MISJA AED</code>, w osobnych commitach – łatwe do przejrzenia i scalenia.</p>
<p><b>Sprawdzony wzór.</b> Kopiujemy mechanizm wykazu DGA, który już działa na produkcji: jedna migracja bazy, jedno zadanie nocne.</p>
<p><b>Nic nowego dla urzędników.</b> Ten sam panel dostawcy i ten sam harwester, które już znają.</p>
<p><b>Start z danymi.</b> Od pierwszego dnia w wykazie może być {d['aed']} AED.</p></div>
<div class="droga">
<div><em>1</em>Przegląd i wdrożenie kodu w portalu</div>
<div><em>2</em>Pismo do każdej gminy przez e-Doręczenia i mail do dostawców danych</div>
<div><em>3</em>Szkolenia dla gmin i kampania „AED na ratunek”</div>
<div class="hl"><em>4</em>Wszystkie AED w Polsce w jednym wykazie</div></div></div>"""))

    # 11. OGRANICZENIA
    s.append(sl("Ograniczenia", "Czego nasze rozwiązanie jeszcze nie robi", """
<div class="dwie"><div><h3>Ograniczenia</h3><ul>
<li>Dane, które zebraliśmy ze stron urzędów, to tylko start. Najlepsze dane da sam właściciel AED.</li>
<li>Gdy urząd nie napisał, czy AED jest zamknięty, zgadujemy to z opisu i oznaczamy jako niepewne.</li>
<li>Niektóre strony blokują automatyczne pobieranie. Nie obchodzimy tych blokad.</li>
<li>Dane z OpenStreetMap nie trafiają do wykazu. Można je tylko włączyć na mapie jako niesprawdzone.</li></ul></div>
<div><h3>Co dalej</h3><ul>
<li>Włączyć pole „wykaz AED” w prawdziwym dane.gov.pl.</li>
<li>Dać wykaz dyspozytorom numeru 112.</li>
<li>Przypominać dysponentom o przeglądach i wymianie elektrod.</li></ul>
<p class="szary" style="margin-top:6mm">Przy kodzie i materiałach pomagał nam asystent AI (Claude). Decyzje i sprawdzanie – zespół.</p></div></div>"""))

    # 1b. CO ODDAJEMY
    s.append(sl("Co oddajemy", "Zrobiliśmy więcej, niż wymagało zadanie", f"""
<div class="oddaj"><div class="wym"><h3>Wymagane w zadaniu</h3>
<p>✔ Wzorcowy zakres danych (XLSX)</p><p>✔ Prototyp rozwiązania</p><p>✔ Kod źródłowy</p><p>✔ Logo i księga znaku</p><p>✔ Opis kampanii</p><p>✔ Prezentacja</p></div>
<div class="extra"><h3>Ponad wymagania</h3><div class="kafle4">
<div><b>działa w dane.gov.pl</b>wykaz zbiorczy wbudowany w prawdziwy kod portalu: panel, API, harwester, zadanie nocne</div>
<div><b>{d['aed']} AED</b>prawdziwe dane z {d['zrodel']} źródeł, gotowe na start wykazu</div>
<div><b>{d['pg_przejrzane']} gmin</b>stron urzędów przejrzanych automatycznie</div>
<div><b>własny geokoder</b>offline, z urzędowego rejestru adresów PRG</div>
<div><b>mapa /pl/aed</b>„pokaż najbliższy AED”, WCAG 2.2 AA bez błędów</div>
<div><b>formularz i walidator</b>dysponent robi poprawny plik bez Excela</div>
<div><b>{d['rej']} partnerów</b>rejestr podmiotów, które mają dane o AED</div>
<div><b>naklejka z QR</b>na szafkę AED – prowadzi prosto do mapy</div>
</div></div></div>"""))

    # 12. KONIEC
    s.append(f"""<section class="s koniec"><img src="{logo}" style="height:40mm"><h1>Pokaż, gdzie jest AED.<br><span>Każda minuta się liczy.</span></h1>
<p class="meta">Dziękujemy · Misja AED – Dane na ratunek · HackNation 2026</p></section>""")

    G = GOV
    html = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>AED na ratunek – prezentacja</title><style>
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Regular.ttf").as_uri()}');font-weight:400}}
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Bold.ttf").as_uri()}');font-weight:700}}
@page{{size:297mm 167mm;margin:0}} body{{margin:0;font-family:Roboto,Arial,sans-serif;color:#1b1b1b}}
.s{{width:297mm;height:167mm;box-sizing:border-box;padding:10mm 14mm 0;page-break-after:always;position:relative;overflow:hidden;background:#fff}}
.s::before{{content:"";position:absolute;left:0;top:0;bottom:0;width:4mm;background:{G}}}
.kicker{{text-transform:uppercase;letter-spacing:.12em;font-size:9.5pt;font-weight:700;color:{CZERWONY}}}
h2{{margin:1.5mm 0 0;font-size:22pt;line-height:1.15;color:{GRANAT};max-width:205mm}}
.mini{{position:absolute;top:9mm;right:14mm;height:11mm}}
.c{{padding-top:6mm;font-size:12.5pt;line-height:1.4}}
footer{{position:absolute;bottom:4mm;left:14mm;right:14mm;font-size:8pt;color:#8a8a8a;display:flex;justify-content:space-between}}
.shot{{border-radius:2.5mm;overflow:hidden;box-shadow:0 1.5mm 5mm rgba(15,38,72,.22);border:1px solid #d5dde8;background:#fff}}
.tel{{display:inline-block;border:2.2mm solid {GRANAT};border-radius:7mm;overflow:hidden;box-shadow:0 2mm 6mm rgba(15,38,72,.3);background:#fff}}
.podpis{{font-size:12pt;color:#444;margin:3mm 0 0}} .szary{{color:#666;font-size:10.5pt}}
.tytul{{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(115deg,#fff 55%,#e6eef8 55%)}}
.tytul h1,.koniec h1{{font-size:34pt;line-height:1.1;color:{GRANAT};margin:8mm 0 4mm}} .tytul h1 span,.koniec h1 span{{color:{G}}}
.lead{{font-size:15pt;margin:0 0 8mm}} .meta{{color:#666;font-size:10pt}} .tr{{padding-right:8mm;transform:rotate(3deg)}}
.koniec{{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:#f2f6fb}}
.liczby{{display:grid;grid-template-columns:repeat(3,1fr);gap:6mm;margin-top:4mm}}
.liczby div{{background:#f2f6fb;border-radius:3mm;padding:9mm 7mm 8mm;font-size:15pt;line-height:1.3}}
.liczby b{{display:block;font-size:52pt;color:{G};line-height:1;margin-bottom:3mm}} .liczby small{{font-size:16pt;color:{GRANAT}}}
.liczby i{{display:block;font-style:normal;font-size:10.5pt;color:#666;margin-top:2mm}}
.duzy{{font-size:16pt;margin-top:10mm;line-height:1.4}}
.kroki3{{display:flex;align-items:stretch;gap:3mm;margin-top:8mm}} .kroki3>span{{align-self:center;font-size:22pt;color:{G}}}
.kroki3 div{{flex:1;border:2px solid {G};border-radius:3mm;padding:8mm 7mm;font-size:13.5pt;color:#333}}
.kroki3 b{{display:block;font-size:17pt;color:{GRANAT};margin:2mm 0 1.5mm}} .kroki3 .hl{{background:{G};color:#fff}} .kroki3 .hl b{{color:#fff}}
em{{font-style:normal;display:inline-flex;width:8mm;height:8mm;border-radius:50%;background:{CZERWONY};color:#fff;font-weight:700;align-items:center;justify-content:center;font-size:11pt;margin-right:2mm}}
.ramka{{margin-top:12mm;background:#f2f6fb;border-left:4mm solid {CZERWONY};padding:7mm 8mm;font-size:14.5pt}}
.g64{{display:grid;grid-template-columns:1.75fr 1fr;gap:8mm;align-items:start}}
.fakty p{{margin:0 0 5mm;padding-left:4mm;border-left:1.2mm solid {G};font-size:13pt}} .fakty b{{color:{GRANAT}}}
.dwie{{display:grid;grid-template-columns:1fr 1fr;gap:10mm;align-items:start}} h3{{color:{G};margin:0 0 4mm;font-size:16pt}}
pre{{background:{GRANAT};color:#e6eef8;border-radius:2.5mm;padding:8mm 7mm;font-size:13pt;line-height:1.5;margin:0}} pre mark{{background:#ffc605;color:#111;padding:0 1mm}}
.mies{{display:grid;grid-template-columns:auto auto minmax(0,1fr);gap:8mm;align-items:start}} .mies p{{font-size:11.5pt;max-width:56mm;margin:3mm 0 0}} .mies .szer p{{max-width:none}}
.znaczek{{margin-top:3mm;display:inline-block;background:#e7f4ec;border:1.5px solid #00703c;color:#00532c;border-radius:2mm;padding:2.5mm 4mm;font-weight:700;font-size:11pt}} .znaczek small{{font-weight:400}}
.pasek{{display:flex;gap:3mm;margin-top:5mm}} .pasek span{{flex:1;background:#f2f6fb;border-radius:2mm;padding:2.5mm 3mm;font-size:10.5pt;display:flex;align-items:center}} .pasek .hl{{background:{G};color:#fff;font-weight:700}}
.pytania{{display:grid;grid-template-columns:1fr 1fr;gap:5mm;margin-top:2mm}} .pytania div{{background:#f2f6fb;border-radius:3mm;padding:8mm 8mm;font-size:13.5pt;color:#333}}
.pytania b{{display:block;font-size:20pt;color:{GRANAT};margin-bottom:1.5mm}} .pytania .hl{{background:#fdeef3;border:2px solid {CZERWONY}}}
.kamp{{display:grid;grid-template-columns:.9fr 1.3fr .8fr;gap:9mm;align-items:center;margin-top:6mm}} .logo-duze img{{width:100%}}
.naklejka{{border:2mm solid {G};border-radius:4mm;padding:5mm;background:#fff;transform:rotate(-3deg)}}
ul{{margin-top:0;padding-left:5mm;font-size:14pt}} li{{margin-bottom:4mm}} code{{font-size:10.5pt}}
.srodek .c{{height:118mm;display:flex;flex-direction:column;justify-content:center;padding-top:0}}
.probl{{display:grid;grid-template-columns:1.15fr 1fr;gap:8mm;margin-top:1mm}}
.liczby2 div{{display:flex;align-items:center;gap:5mm;background:#f2f6fb;border-radius:3mm;padding:3mm 6mm;margin-bottom:3mm;font-size:13pt;line-height:1.25}}
.liczby2 b{{font-size:32pt;color:{G};min-width:52mm;line-height:1}} .liczby2 small{{font-size:14pt;color:{GRANAT}}}
.liczby2 i{{display:block;font-style:normal;font-size:10pt;color:#666;margin-top:1mm}}
.pdfy{{display:grid;grid-template-columns:1fr 1fr;gap:6mm;align-items:start;padding-top:4mm}} .pdfy>div{{}} .pdfy span{{display:block;font-size:10.5pt;font-weight:700;color:{CZERWONY};margin-top:2mm;text-align:center}}
.pdfy .p1{{transform:rotate(-2deg)}} .pdfy .p2{{transform:rotate(2deg);margin-top:14mm}}
.oddaj{{display:grid;grid-template-columns:.75fr 2fr;gap:8mm;margin-top:1mm}}
.wym{{background:#f2f6fb;border-radius:3mm;padding:5mm 6mm}} .wym p{{margin:0 0 3.2mm;font-size:12.5pt}}
.kafle4{{display:grid;grid-template-columns:repeat(4,1fr);gap:3.5mm}} .kafle4 div{{border:1.5px solid #c9d6e6;border-radius:3mm;padding:3.5mm 4mm;font-size:10.5pt;color:#333;line-height:1.3}}
.kafle4 b{{display:block;font-size:14.5pt;color:{G};margin-bottom:1.5mm;line-height:1.15}}
.droga div{{display:flex;align-items:center;background:#f2f6fb;border-radius:3mm;padding:4.5mm 5mm;margin-bottom:3.5mm;font-size:13pt;font-weight:700;color:{GRANAT}}}
.droga .hl{{background:{G};color:#fff}}
.xl{{display:grid;grid-template-columns:.8fr 1.9fr;gap:6mm;align-items:start}}
.siatka{{columns:3;column-gap:4mm}} .grp{{break-inside:avoid;margin-bottom:3mm}} .grp h4{{margin:0 0 1mm;font-size:9.5pt;color:{GRANAT}}}
.ch{{display:inline-block;font-size:7.2pt;padding:.4mm 1.4mm;margin:0 .8mm .8mm 0;border-radius:1.2mm;font-family:monospace}}
.ch.W{{background:#fde2e8;color:#8a0030}} .ch.Z{{background:#fff1cc;color:#6b4b00}} .ch.O{{background:#e6eef8;color:#0b3f7a}} .ch.A{{background:#e3f2e8;color:#00532c}}
.leg{{margin-bottom:3mm}} .leg .ch{{font-family:Roboto,Arial;font-size:9pt;font-weight:700}}
.brak{{border:2px dashed #bbb;color:#999;display:flex;align-items:center;justify-content:center;height:60mm}}
</style></head><body>{''.join(s)}</body></html>"""
    p = KAT / "prezentacja.html"
    p.write_text(html, encoding="utf-8")
    chrome(["--allow-file-access-from-files", f"--print-to-pdf={KAT / 'prezentacja_AED_na_ratunek.pdf'}", "--no-pdf-header-footer", p.as_uri()])
    print("prezentacja:", (KAT / "prezentacja_AED_na_ratunek.pdf").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
