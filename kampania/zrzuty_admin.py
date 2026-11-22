"""Zrzuty z lokalnego portalu dane.gov.pl (panel administracyjny + API) – dowody działania wykazu zbiorczego AED."""
import json
import urllib.request
import ssl
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "zrzuty"
HOSTY = "MAP *.mcod.local 127.0.0.1, MAP mcod.local 127.0.0.1"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", f"--host-resolver-rules={HOSTY}"])
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, ignore_https_errors=True, locale="pl-PL")
    pg = ctx.new_page()
    pg.goto("https://admin.mcod.local/", wait_until="load", timeout=90000)
    pg.fill("input[name=username]", "admin@mcod.local")
    pg.fill("input[name=password]", "testadmin123!")
    pg.click("[type=submit]")
    pg.wait_for_timeout(3000)
    # lista zasobów oznaczonych jako wykaz AED
    pg.goto("https://admin.mcod.local/resources/resource/?q=Wykaz+AED", wait_until="load")
    pg.wait_for_timeout(2000)
    pg.screenshot(path=str(OUT / "admin_lista_zasobow_aed.png"))
    # formularz zasobu dysponenta z zaznaczoną flagą
    pg.goto("https://admin.mcod.local/resources/resource/?q=Siemianowice", wait_until="load")
    pg.locator("table#result_list tbody tr a").first.click()
    pg.wait_for_timeout(3000)
    flag = pg.locator("[name=contains_aed_list]").first
    flag.scroll_into_view_if_needed()
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "admin_zasob_aed.png"))
    # zbiór wykazu zbiorczego
    pg.goto("https://admin.mcod.local/datasets/dataset/?q=Wykaz+zbiorczy", wait_until="load")
    pg.wait_for_timeout(2000)
    pg.screenshot(path=str(OUT / "admin_wykaz_zbiorczy.png"))
    # API – sformatowany JSON
    ctx_ssl = ssl._create_unverified_context()
    req = urllib.request.Request("https://127.0.0.1/aggregated-aed-info", headers={"Host": "api.mcod.local"})
    dane = json.loads(urllib.request.urlopen(req, context=ctx_ssl, timeout=30).read())
    raport = dane.pop("validation_report", [])
    tabela = "".join(f"<tr><td>{r['organization']}</td><td>{r['status']}</td><td>{r['rows_count']}</td><td>{r['invalid_rows_count']}</td></tr>" for r in raport)
    html = f"""<html><body style="font-family:Roboto,Arial;padding:20px;width:900px"><h3 style="margin:0 0 8px;color:#0f2648">GET https://api.mcod.local/aggregated-aed-info</h3>
<pre style="background:#0f2648;color:#e8f0ff;padding:12px;border-radius:6px;font-size:13px">{json.dumps(dane, ensure_ascii=False, indent=1)}</pre>
<table border="1" cellpadding="6" style="border-collapse:collapse;font-size:14px"><tr style="background:#eef4fb"><th>Dysponent</th><th>Status</th><th>Wiersze</th><th>Z brakami pól W</th></tr>{tabela}</table></body></html>"""
    api = ctx.new_page()
    api.set_viewport_size({"width": 960, "height": 700})
    api.set_content(html)
    api.screenshot(path=str(OUT / "api_aggregated_aed_info.png"), full_page=True)
    b.close()
print("zrzuty admin/API w", OUT)
