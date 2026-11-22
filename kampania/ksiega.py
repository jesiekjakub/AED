"""Księga znaku „AED na ratunek” (HTML -> PDF przez Chrome) oraz eksport logo do PNG/JPG/PDF.

Uruchom: python kampania/ksiega.py
Wynik: kampania/ksiega_znaku_AED_na_ratunek.pdf, kampania/logo/*.png|jpg|pdf
"""
import base64
import io
import subprocess
import tempfile
from pathlib import Path

import qrcode
import qrcode.image.svg
from PIL import Image

from logo import CZARNY, CZERWONY, GOV, GRANAT, OUT, WARIANTY, svg

KAT = Path(__file__).resolve().parent
CHROME = "google-chrome"
URL_AKCJI = "https://dane.gov.pl/pl/aed"
HASLO = "Pokaż, gdzie jest AED. Każda minuta się liczy."


def kontrast(a: str, b: str) -> float:
    def lum(h):
        h = h.lstrip("#")
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    l1, l2 = sorted((lum(a), lum(b)), reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 1)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def cmyk(h):
    r, g, b = (x / 255 for x in rgb(h))
    k = 1 - max(r, g, b)
    if k == 1:
        return (0, 0, 0, 100)
    return tuple(round(100 * x) for x in ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k))


def data_uri(svg_txt: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg_txt.encode()).decode()


def chrome(args: list[str]):
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={prof}", *args],
                       capture_output=True, timeout=120, check=False)


def eksport_logo():
    for nazwa in WARIANTY:
        s = (OUT / f"{nazwa}.svg").read_text(encoding="utf-8")
        szer = int(s.split('width="')[1].split('"')[0])
        wys = int(s.split('height="')[1].split('"')[0])
        html = KAT / "_tmp_logo.html"
        html.write_text(f'<html><body style="margin:0;background:transparent"><img src="{data_uri(s)}" width="{szer}" height="{wys}"></body></html>')
        png = OUT / f"{nazwa}.png"
        chrome(["--default-background-color=00000000", "--hide-scrollbars", f"--window-size={szer},{wys}", f"--screenshot={png}", html.as_uri()])
        if png.exists():
            im = Image.open(png).convert("RGBA")
            tlo = Image.new("RGB", im.size, (255, 255, 255) if "negatyw" not in nazwa else rgb(GRANAT))
            tlo.paste(im, mask=im.split()[3])
            tlo.save(OUT / f"{nazwa}.jpg", quality=95)
        html.write_text(f'<html><head><style>@page{{size:{szer / 4}mm {wys / 4}mm;margin:0}}body{{margin:0}}</style></head>'
                        f'<body><img src="{data_uri(s)}" style="width:{szer / 4}mm;height:{wys / 4}mm;display:block"></body></html>')
        chrome([f"--print-to-pdf={OUT / f'{nazwa}.pdf'}", "--no-pdf-header-footer", html.as_uri()])
        html.unlink(missing_ok=True)


def qr_svg(url: str) -> str:
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


def ksiega():
    logo = data_uri(svg())
    warianty_html = "".join(
        f'<figure class="wariant" style="background:{"#0F2648" if "negatyw" in n and "kolor" not in n else ("#0052A5" if "kolor" in n else "#fff")}">'
        f'<img src="{data_uri(svg(**kw))}"><figcaption>{opis}</figcaption></figure>'
        for n, kw, opis in [
            ("podst", WARIANTY["logo_aed_na_ratunek"], "Wersja podstawowa"),
            ("gran", WARIANTY["logo_aed_na_ratunek_granat"], "Wersja jednobarwna – granat"),
            ("mono", WARIANTY["logo_aed_na_ratunek_mono"], "Wersja monochromatyczna (czerń)"),
            ("negatyw", {**WARIANTY["logo_aed_na_ratunek_negatyw"], "tlo": None}, "Negatyw na granacie"),
            ("negatyw_kolor", {**WARIANTY["logo_aed_na_ratunek_negatyw_kolor"], "tlo": None}, "Negatyw na niebieskim gov"),
            ("syg", WARIANTY["sygnet_aed_na_ratunek"], "Sygnet – ikona aplikacji, favicon, media społecznościowe"),
        ])
    kolory = [("Niebieski gov", GOV, "sygnet, ukośnik, przyciski"), ("Czerwień ratunkowa", CZERWONY, "linia EKG – akcent"),
              ("Granat", GRANAT, "tła, wersja jednobarwna"), ("Czerń tekstu", CZARNY, "napis")]
    kolory_html = "".join(
        f'<div class="kolor"><div class="probka" style="background:{h}"></div><strong>{n}</strong><br>HEX {h}<br>RGB {"/".join(map(str, rgb(h)))}<br>'
        f'CMYK {"/".join(map(str, cmyk(h)))}<br>kontrast z bielą {kontrast(h, "#FFFFFF")}:1<br><small>{z}</small></div>' for n, h, z in kolory)
    zle = [("transform:scaleX(1.45);width:30mm", "Nie rozciągaj ani nie ściskaj znaku"),
           ("filter:hue-rotate(120deg)", "Nie zmieniaj kolorów"),
           ("opacity:.35", "Nie umieszczaj na tle o niskim kontraście"),
           ("transform:scaleY(-1)", "Nie przestawiaj ani nie odbijaj elementów")]
    zle_html = "".join(f'<figure class="zle"><div class="ramka" style="{"background:#7fb3e6;" if "kontrast" in t else ""}">'
                       f'<img src="{logo}" style="{s}"></div><figcaption>✕ {t}</figcaption></figure>' for s, t in zle)
    qr = data_uri(qr_svg(URL_AKCJI))
    html = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Księga znaku – AED na ratunek</title>
<style>
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Regular.ttf").as_uri()}');font-weight:400}}
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Bold.ttf").as_uri()}');font-weight:700}}
@page{{size:A4;margin:16mm}}
body{{font-family:Roboto,Arial,sans-serif;color:#1b1b1b;font-size:10.5pt;line-height:1.45}}
h1{{font-size:26pt;margin:0 0 4mm}} h2{{font-size:16pt;color:{GOV};border-bottom:3px solid {GOV};padding-bottom:2mm;margin-top:0}}
section{{page-break-after:always}} section:last-child{{page-break-after:auto}}
.okladka{{display:flex;flex-direction:column;justify-content:center;height:250mm}}
.okladka img{{width:150mm}} .pas{{height:6mm;background:{GOV};margin:10mm 0 4mm}}
.konstrukcja{{position:relative;display:inline-block;padding:14mm;border:1px dashed {CZERWONY};margin:6mm 0}}
.konstrukcja img{{width:120mm;display:block;outline:1px solid #bbb}}
.x{{position:absolute;background:{CZERWONY};color:#fff;font-size:8pt;padding:0 1.5mm}}
.wariant{{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;width:84mm;height:44mm;margin:2mm;border:1px solid #ddd;vertical-align:top}}
.wariant img{{max-width:72mm;max-height:24mm}} .wariant figcaption{{font-size:8.5pt;margin-top:3mm;background:#fff;padding:0 2mm}}
.kolor{{display:inline-block;width:40mm;margin:0 3mm 4mm 0;vertical-align:top;font-size:9pt}} .probka{{height:22mm;border-radius:2mm;margin-bottom:2mm;border:1px solid #ccc}}
.zle{{display:inline-block;width:54mm;margin:2mm;vertical-align:top;font-size:8.5pt;color:{CZERWONY}}}
.zle .ramka{{height:28mm;display:flex;align-items:center;justify-content:center;border:1px solid #ddd;overflow:hidden}} .zle img{{width:44mm}}
.min{{display:flex;gap:10mm;align-items:flex-end}} .min div{{text-align:center;font-size:9pt}}
.naklejka{{width:85mm;height:120mm;border:2mm solid {GOV};border-radius:4mm;padding:6mm;display:inline-flex;flex-direction:column;justify-content:space-between;vertical-align:top;margin-right:6mm}}
.naklejka .hasło{{font-size:15pt;font-weight:700;color:{GRANAT}}} .baner{{display:inline-flex;align-items:center;gap:6mm;background:{GOV};color:#fff;padding:5mm 7mm;border-radius:2mm;width:150mm;margin-top:6mm}}
.baner img{{height:16mm}} .baner span{{font-size:13pt;font-weight:700}} table{{border-collapse:collapse}} td{{padding:1mm 3mm;border-bottom:1px solid #ddd}}
</style></head><body>

<section class="okladka"><img src="{logo}" alt="Logotyp AED na ratunek"><div class="pas"></div>
<h1>Księga znaku</h1><p style="font-size:14pt">Akcja <strong>„AED na ratunek”</strong> – udostępniamy dane o defibrylatorach w portalu dane.gov.pl<br>
Hasło: <strong>„{HASLO}”</strong></p><p style="color:#5e5e5e">Wersja 1.0 · listopad 2026 · HackNation 2026 – Misja AED</p></section>

<section><h2>1. Koncepcja</h2>
<p>Znak łączy serce przecięte linią EKG – zapis pracy serca, którą defibrylator przywraca – z konstrukcją logotypu portalu Otwarte Dane: sygnet, ukośnik i dwuwierszowy napis wersalikami. Dzięki temu akcja jest od razu rozpoznawalna jako inicjatywa dane.gov.pl, a symbol mówi, czego dotyczy, bez czytania napisu. Niebieski gov i krój Roboto to barwy i typografia portalu; czerwona linia pulsu to jedyny akcent – „impuls”, który ratuje życie. Ukośnik symbolizuje drogę od danych do pomocy: dane o AED trafiają na mapę, a z mapy do świadka zdarzenia.</p>
<h2>2. Budowa znaku i pole ochronne</h2>
<p>Pole ochronne <strong>x</strong> = wysokość wersalika „A” w napisie. Wokół znaku zachowujemy wolną przestrzeń co najmniej <strong>1x</strong> z każdej strony – nie umieszczamy w niej tekstu, krawędzi ani innych znaków.</p>
<div class="konstrukcja"><span class="x" style="top:4mm;left:50%">x</span><span class="x" style="bottom:4mm;left:50%">x</span>
<span class="x" style="left:3mm;top:45%">x</span><span class="x" style="right:3mm;top:45%">x</span><img src="{logo}"></div>
<p>Proporcje: sygnet (serce) zajmuje pełną wysokość znaku; ukośnik ma kąt jak w znaku Otwarte Dane; napis w Roboto Bold: „AED” – wysokość wersalików 38% wysokości znaku, „NA RATUNEK” – 19%, ze zwiększonym odstępem liter.</p>
<h2>3. Minimalna wielkość</h2>
<div class="min"><div><img src="{logo}" style="width:30mm"><br>druk: min. 30 mm szerokości</div>
<div><img src="{logo}" style="width:42mm"><br>ekran: min. 160 px szerokości</div>
<div><img src="{data_uri(svg(tylko_sygnet=True))}" style="width:8mm"><br>sygnet: min. 8 mm / 24 px<br>(favicon 16 px)</div></div>
</section>

<section><h2>4. Kolorystyka</h2>{kolory_html}
<p>Wszystkie barwy główne spełniają wymaganie kontrastu WCAG 2.2 AA (min. 4,5:1 dla tekstu) na białym tle. Na tłach o niskim kontraście stosuj negatyw.</p>
<h2>5. Warianty znaku</h2>{warianty_html}</section>

<section><h2>6. Niedozwolone użycie znaku</h2>{zle_html}
<p>Znak stosujemy wyłącznie z plików źródłowych (SVG/PDF/PNG). Nie przerysowujemy go, nie zmieniamy kroju pisma ani proporcji, nie zamieniamy linii EKG na inny symbol.</p>
<h2>7. Typografia</h2>
<table><tr><td style="font-weight:700;font-size:14pt">Roboto Bold</td><td>nagłówki, napis w znaku, hasło</td></tr>
<tr><td style="font-size:14pt">Roboto Regular</td><td>teksty, materiały informacyjne</td></tr></table>
<p>Roboto (licencja SIL Open Font License) – ten sam krój, którego używa portal dane.gov.pl.</p></section>

<section><h2>8. Przykłady zastosowań</h2>
<div class="naklejka"><img src="{logo}" style="width:100%"><div class="hasło">{HASLO}</div>
<div style="display:flex;gap:4mm;align-items:center"><img src="{qr}" style="width:28mm"><span style="font-size:9pt">Ten AED jest na mapie<br><strong>dane.gov.pl/pl/aed</strong><br>W nagłym wypadku dzwoń <strong>112</strong></span></div></div>
<div style="display:inline-block;width:80mm;vertical-align:top;font-size:10pt"><strong>Naklejka na szafkę AED</strong> (85×120 mm) – dla dysponentów, którzy opublikowali dane w dane.gov.pl. Kod QR prowadzi do mapy AED w portalu.<br><br>
<strong>Baner dla stron gmin i instytucji</strong> – link do instrukcji publikacji danych i walidatora.</div>
<div class="baner"><img src="{data_uri(svg(**WARIANTY['logo_aed_na_ratunek_negatyw_kolor'] | {'tlo': None}))}"><span>Masz AED? Pokaż go na mapie – opublikuj dane w dane.gov.pl</span></div>
</section></body></html>"""
    p = KAT / "ksiega_znaku.html"
    p.write_text(html, encoding="utf-8")
    chrome(["--allow-file-access-from-files", f"--print-to-pdf={KAT / 'ksiega_znaku_AED_na_ratunek.pdf'}", "--no-pdf-header-footer", p.as_uri()])


if __name__ == "__main__":
    eksport_logo()
    ksiega()
    print("gotowe:", sorted(x.name for x in OUT.iterdir()), (KAT / "ksiega_znaku_AED_na_ratunek.pdf").exists())
