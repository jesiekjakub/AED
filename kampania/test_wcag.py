"""Test dostępności strony AED (axe-core, WCAG 2.0/2.1/2.2 A+AA) + zrzut z podsumowaniem do prezentacji."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

KORZEN = Path(__file__).resolve().parent.parent
AXE = (KORZEN / ".tmp" / "axe" / "node_modules" / "axe-core" / "axe.min.js").read_text()
OUT = Path(__file__).resolve().parent / "zrzuty"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    wyniki = {}
    for nazwa, vp in [("komputer 1440 px", {"width": 1440, "height": 1000}), ("telefon 390 px", {"width": 390, "height": 844})]:
        pg = b.new_page(viewport=vp)
        pg.goto("http://localhost:4300/pl/aed", wait_until="load", timeout=90000)
        pg.wait_for_timeout(7000)
        pg.add_script_tag(content=AXE)
        wyniki[nazwa] = pg.evaluate("""async()=>{const r=await axe.run(document.querySelector('.aed'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});
          return {wersja:axe.version,naruszenia:r.violations.map(v=>v.id+' ('+v.impact+')'),zaliczone:r.passes.length,do_recznej:r.incomplete.length}}""")
        pg.close()
    (OUT / "wcag_axe.json").write_text(json.dumps(wyniki, ensure_ascii=False, indent=1))
    wiersze = "".join(f"<tr><td>{k}</td><td><b style='color:{'#00703c' if not v['naruszenia'] else '#b3261e'}'>{len(v['naruszenia'])}</b></td><td>{v['zaliczone']}</td><td>{v['do_recznej']}</td></tr>" for k, v in wyniki.items())
    v = next(iter(wyniki.values()))["wersja"]
    html = f"""<html><body style="font-family:Roboto,Arial;padding:24px;width:640px"><h2 style="color:#0f2648;margin:0 0 6px">Test dostępności – strona /pl/aed</h2>
<p style="color:#555;margin:0 0 14px">axe-core {v} · reguły WCAG 2.0, 2.1, 2.2 – poziom A i AA</p>
<table style="border-collapse:collapse;font-size:16px" cellpadding="8" border="1"><tr style="background:#eef4fb"><th>Widok</th><th>Naruszenia</th><th>Reguły spełnione</th><th>Do weryfikacji ręcznej</th></tr>{wiersze}</table>
<p style="margin-top:14px;font-size:14px">Kontrast kolorów ≥ 4,5:1 · pełna obsługa klawiaturą · lista jako alternatywa mapy · przyciski ≥ 44 px · role ARIA zakładek i regionów</p></body></html>"""
    pg = b.new_page(viewport={"width": 700, "height": 330})
    pg.set_content(html)
    pg.screenshot(path=str(OUT / "wcag_axe.png"), full_page=True)
    b.close()
print(json.dumps(wyniki, ensure_ascii=False))
