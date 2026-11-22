"""Lublin: lista AED w PDF na lublin.eu ('N. Obiekt, ul. Adres')."""
import re
import subprocess

from ..normalizacja import tekst
from ..siec import KATALOG, pobierz as pobierz_plik

STRONA = "https://lublin.eu/mieszkancy/zdrowie/aktualnosci/aed-w-lublinie,748,1345,1.html"


def pobierz():
    try:
        strona = pobierz_plik(STRONA, "lublin/strona.html").read_text(encoding="utf-8", errors="ignore")
    except RuntimeError:
        strona = ""
    m = re.search(r'href="([^"]+aed[^"]*\.pdf)"', strona, re.I)
    pdf_url = ("https://lublin.eu" + m.group(1)) if m and m.group(1).startswith("/") else (m.group(1) if m else
              "https://lublin.eu/download/gfx/lublin/userfiles/_public/mieszkancy/zdrowie/aktualnosci/2026/aed_lublin_stan_17.03.2026.pdf")
    pdf = pobierz_plik(pdf_url, "lublin/wykaz.pdf", kopia_zapasowa=KATALOG / "_probki_recznie" / "lublin_aed_stan_17.03.2026.pdf")
    txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    stan = re.search(r"stan na (\d{2})\.(\d{2})\.(\d{4})", txt)
    data_stanu = f"{stan.group(3)}-{stan.group(2)}-{stan.group(1)}" if stan else ""
    pozycje = re.split(r"\n\s*(\d+)\.\s+", "\n" + txt)
    rekordy = []
    for lp, tresc in zip(pozycje[1::2], pozycje[2::2]):
        t = tekst(tresc)
        # adres = ostatni fragment po przecinku zaczynający się od cechy ulicy lub zawierający numer
        m = re.search(r",\s*((?:ul\.|al\.|pl\.|Al\.|Pl\.|os\.|Plac|Aleja|Aleje)[^,]*(?:,[^,]*\d[^,]*)?)\s*$", t) or re.search(r",\s*([^,]*\d+[A-Za-z]?)\s*$", t)
        obiekt, adres = (t[:m.start()], m.group(1)) if m else (t, "")
        rekordy.append({"id_zrodlowe": lp, "nazwa_obiektu": tekst(obiekt), "_adres": adres, "_tekst_opisowy": t, "_flagi": []})
    print(f"  Lublin: {len(rekordy)} rekordów z PDF (stan {data_stanu})")
    meta = {"zrodlo_id": "JST-LUB", "dostawca_danych": "Urząd Miasta Lublin", "zrodlo_url": pdf_url, "zbior_url": STRONA,
            "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": data_stanu, "miejscowosc": "Lublin",
            "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
    return [(meta, rekordy)]
