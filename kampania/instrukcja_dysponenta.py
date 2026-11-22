"""Instrukcja dla dysponenta „Jak udostępnić dane o AED w dane.gov.pl” (2 strony A4) – HTML -> PDF.

Uruchom: python kampania/instrukcja_dysponenta.py -> kampania/instrukcja_dla_dysponenta_AED.pdf
"""
import sys
from pathlib import Path

from ksiega import HASLO, chrome, data_uri
from logo import CZERWONY, GOV, GRANAT, svg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crawler.schemat import POLA, SLOWNIKI  # noqa: E402

KAT = Path(__file__).resolve().parent


def main():
    wymagane = [p for p in POLA if p.poziom == "W"]
    zalecane = [p for p in POLA if p.poziom == "Z"]
    tab = "".join(f"<tr><td><code>{p.nazwa}</code></td><td>{p.opis.split('.')[0]}</td><td><code>{p.przyklad}</code></td></tr>" for p in wymagane)
    zab = ", ".join(f"<code>{k}</code>" for k in SLOWNIKI["zabezpieczenie"])
    html = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Instrukcja dla dysponenta – AED na ratunek</title><style>
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Regular.ttf").as_uri()}');font-weight:400}}
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Bold.ttf").as_uri()}');font-weight:700}}
@page{{size:A4;margin:13mm 14mm}} body{{font-family:Roboto,Arial,sans-serif;font-size:9.4pt;line-height:1.38;color:#1b1b1b}}
.top{{display:flex;justify-content:space-between;align-items:center;border-bottom:4px solid {GOV};padding-bottom:3mm;margin-bottom:3mm}} .top img{{height:15mm}}
h1{{font-size:15pt;color:{GRANAT};margin:0;text-align:right}} h2{{font-size:11pt;color:{GOV};margin:4mm 0 1.5mm}}
table{{border-collapse:collapse;width:100%;font-size:8.4pt}} td,th{{border:1px solid #ccc;padding:1mm 2mm;vertical-align:top;text-align:left}} th{{background:#eef4fb}}
.kroki{{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm}} .kroki div{{border:1.5px solid {GOV};border-radius:2mm;padding:2.5mm}} .kroki b{{color:{GOV}}}
.uwaga{{border-left:5px solid {CZERWONY};background:#fdf1f0;padding:2mm 3mm}} ul{{margin:0;padding-left:5mm}} li{{margin:0.5mm 0}} code{{font-size:8.4pt}}
.lista li{{list-style:'☐  '}}
</style></head><body>
<div class="top"><img src="{data_uri(svg())}" alt="AED na ratunek"><h1>Jak udostępnić dane o AED<br>w dane.gov.pl – instrukcja dla dysponenta</h1></div>
<p><b>Dla kogo:</b> gminy, powiaty i ich jednostki, instytucje publiczne, spółki i firmy, które mają lub finansują defibrylatory AED dostępne dla mieszkańców.
<b>Po co:</b> Twoje AED trafią do <b>Wykazu zbiorczego AED</b> w dane.gov.pl i na mapę <b>dane.gov.pl/pl/aed</b> – z Twoją nazwą jako źródłem danych. „{HASLO}”</p>

<h2>3 kroki (ok. 30 minut)</h2>
<div class="kroki">
<div><b>1. Przygotuj plik</b><br><b>Kilka AED:</b> wypełnij formularz na dane.gov.pl/pl/aed („Dla dysponenta” → „Mam kilka AED”) i pobierz gotowy CSV. <b>Więcej:</b> pobierz szablon CSV – jeden wiersz = jedno urządzenie. Kodowanie UTF-8, separator przecinek, daty RRRR-MM-DD, współrzędne WGS84 z kropką.</div>
<div><b>2. Sprawdź walidatorem</b><br>Wgraj plik do walidatora na tej samej stronie – plik nie opuszcza komputera. Popraw błędy (brak kolumny, wartość spoza słownika, zamienione współrzędne).</div>
<div><b>3. Opublikuj</b><br><b>Masz konto dostawcy:</b> dodaj zasób w panelu dane.gov.pl (wgraj plik albo podaj link do pliku w BIP) i zaznacz „Zasób zawiera wykaz AED”. <b>Duży zbiór lub system:</b> harwester XML (element <code>containsAedList</code>) – portal sam pobiera aktualizacje. <b>Nie masz konta dostawcy:</b> skontaktuj się z redakcją portalu dane.gov.pl.</div>
</div>

<h2>Pola wymagane (pełny opis 48 pól i słowniki: plik „wzorcowy_zakres_danych_AED.xlsx”)</h2>
<table><tr><th>Pole</th><th>Co wpisać</th><th>Przykład</th></tr>{tab}</table>
<p style="margin-top:1.5mm">Pola zalecane ({len(zalecane)}): m.in. kody TERYT, typ obiektu, producent i model, tryb pediatryczny, data ostatniego przeglądu, REGON dysponenta.</p>

<div class="uwaga"><b>Najważniejsze pole: <code>zabezpieczenie</code>.</b> Świadek zdarzenia musi wiedzieć, czy otworzy AED bez pomocy. Wartości: {zab}.
Jeśli AED jest zamknięty na klucz lub szyfr – wypełnij <code>instrukcja_dostepu</code> (np. „kod podaje dyspozytor 112”).</div>

<h2>Utrzymanie danych</h2>
<ul><li><b>Aktualizuj od razu</b> przy każdej zmianie: nowy AED, demontaż (<code>status = wycofany</code>), serwis (<code>tymczasowo_niedostepny</code>), zmiana godzin.</li>
<li><b>Co najmniej raz na kwartał</b> potwierdź, że urządzenia są na miejscu i sprawne – zaktualizuj <code>data_weryfikacji</code>.</li>
<li>Zachowaj stały <code>id_aed</code> – dzięki temu historia urządzenia nie ginie przy aktualizacjach.</li>
<li>Wykaz zbiorczy przelicza się automatycznie każdej nocy – nie trzeba nikogo powiadamiać.</li>
<li>Portal przypomina mailem o aktualizacji zbioru zgodnie z zadeklarowaną częstotliwością.</li></ul>

<h2>Lista kontrolna przed publikacją</h2>
<ul class="lista"><li>Licencja zbioru: CC0 1.0 lub CC BY 4.0; tytuł „Defibrylatory AED – [nazwa dysponenta]”; kategoria Zdrowie; tag <code>misja-aed</code>.</li>
<li>Współrzędne wskazują urządzenie (wejście, ściana), a nie środek działki; min. 5 miejsc po przecinku.</li>
<li>Godziny w formacie <code>24/7</code> lub <code>Mo-Fr 08:00-16:00</code>; sezonowe – zaznacz <code>sezonowy = tak</code>.</li>
<li><b>Bez danych osobowych</b> – tylko kontakt instytucji (sekretariat, recepcja), bez imion i prywatnych telefonów.</li>
<li>Walidator nie zgłasza błędów.</li></ul>

<h2>Wsparcie</h2>
<p>Szablon, opis pól, walidator i przykładowy plik XML: <b>dane.gov.pl/pl/aed</b> → „Dla dysponenta”. Przewodnik dla dostawców: dane.gov.pl/article/1226. Szkolenia dla samorządów: projekt „Samorząd otwarty na dane” i Akademia Danych (Ministerstwo Cyfryzacji).</p>
</body></html>"""
    p = KAT / "instrukcja_dysponenta.html"
    p.write_text(html, encoding="utf-8")
    chrome(["--allow-file-access-from-files", f"--print-to-pdf={KAT / 'instrukcja_dla_dysponenta_AED.pdf'}", "--no-pdf-header-footer", p.as_uri()])


if __name__ == "__main__":
    main()
