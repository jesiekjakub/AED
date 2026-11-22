"""Generator logotypu akcji „AED na ratunek” (SVG). Napisy zamieniane na krzywe z fontu Roboto (OFL) – plik nie zależy od fontów systemowych.

Konstrukcja nawiązuje do znaku Otwarte Dane (dane.gov.pl): sygnet (serce z linią EKG) + ukośnik + dwuwierszowy napis wersalikami.
Uruchom: python kampania/logo.py  -> kampania/logo/*.svg
"""
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

KAT = Path(__file__).resolve().parent
OUT = KAT / "logo"
FONT = TTFont(KAT / "fonty" / "Roboto-Bold.ttf")

GOV = "#0052A5"      # niebieski gov / dane.gov.pl
GRANAT = "#0F2648"   # granat portalu
CZERWONY = "#D40043" # czerwień portalu
CZARNY = "#1B1B1B"

SERCE = "M50 88 C22 68 7 52 7 33 C7 19 18 9 31 9 C40 9 46 14 50 21 C54 14 60 9 69 9 C82 9 93 19 93 33 C93 52 78 68 50 88 Z"
BLYSK = "M56 22 L37 53 L49 53 L44 77 L65 44 L53 44 L59 22 Z"
UKOSNIK = "M113 6 L124 6 L105 94 L94 94 Z"


def tekst_na_sciezke(tekst: str, x: float, baseline: float, wys_wersalika: float, odstep: float = 0.0) -> tuple[str, float]:
    gs = FONT.getGlyphSet()
    cmap = FONT.getBestCmap()
    cap = FONT["OS/2"].sCapHeight or 1456
    skala = wys_wersalika / cap
    pen = SVGPathPen(gs)
    kursor = 0.0
    for ch in tekst:
        g = cmap.get(ord(ch))
        if g is None:
            continue
        tp = TransformPen(pen, (skala, 0, 0, -skala, x + kursor, baseline))
        gs[g].draw(tp)
        kursor += gs[g].width * skala + odstep
    return pen.getCommands(), kursor


EKG = "M2 52 H30 L37 38 L46 68 L55 26 L62 52 H96"
UKOSNIK_B = "M112 8 L119 8 L104 92 L97 92 Z"


def svg(kolor_sygnet=GOV, kolor_blysk=CZERWONY, kolor_ukosnik=GOV, kolor_tekst=GRANAT, tlo=None, tylko_sygnet=False, kolor_aed=None) -> str:
    """Wariant B „Puls”: serce (kontur) przecięte linią EKG + ukośnik + „AED” / „NA RATUNEK”.
    kolor_blysk = kolor linii EKG (nazwa parametru zachowana dla zgodności)."""
    kolor_aed = kolor_aed or kolor_sygnet
    l1, w1 = tekst_na_sciezke("AED", 132, 48, 38, 2.0)
    l2, w2 = tekst_na_sciezke("NA RATUNEK", 133, 86, 19, 3.2)
    szer = 100 if tylko_sygnet else int(133 + max(w1, w2) + 6)
    tlo_el = f'<rect width="100%" height="100%" fill="{tlo}"/>' if tlo else ""
    tresc = (f'<path d="{SERCE}" fill="none" stroke="{kolor_sygnet}" stroke-width="6.5" stroke-linejoin="round"/>'
             f'<path d="{EKG}" fill="none" stroke="{kolor_blysk}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>')
    if not tylko_sygnet:
        tresc += (f'<path d="{UKOSNIK_B}" fill="{kolor_ukosnik}"/>'
                  f'<path d="{l1}" fill="{kolor_aed}"/><path d="{l2}" fill="{kolor_tekst}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szer} 100" width="{szer * 4}" height="400" role="img" aria-label="AED na ratunek">'
            f'<title>AED na ratunek</title>{tlo_el}{tresc}</svg>')


WARIANTY = {
    "logo_aed_na_ratunek": dict(),
    "logo_aed_na_ratunek_granat": dict(kolor_sygnet=GRANAT, kolor_ukosnik=GRANAT, kolor_tekst=GRANAT),
    "logo_aed_na_ratunek_mono": dict(kolor_sygnet="#000", kolor_blysk="#000", kolor_ukosnik="#000", kolor_tekst="#000"),
    "logo_aed_na_ratunek_negatyw": dict(kolor_sygnet="#FFF", kolor_blysk="#FFF", kolor_ukosnik="#FFF", kolor_tekst="#FFF", tlo=GRANAT),
    "logo_aed_na_ratunek_negatyw_kolor": dict(kolor_sygnet="#FFF", kolor_blysk=CZERWONY, kolor_ukosnik="#FFF", kolor_tekst="#FFF", tlo=GOV),
    "sygnet_aed_na_ratunek": dict(tylko_sygnet=True),
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for nazwa, kw in WARIANTY.items():
        (OUT / f"{nazwa}.svg").write_text(svg(**kw), encoding="utf-8")
    print("zapisano", len(WARIANTY), "wariantów w", OUT)
