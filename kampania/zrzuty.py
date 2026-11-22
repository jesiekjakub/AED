"""Zrzuty ekranu strony AED (desktop + telefon) do prezentacji i weryfikacji. Zamyka okno polityki prywatności portalu.

Użycie: python kampania/zrzuty.py [url] [katalog]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4200/pl/aed"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent / "zrzuty")
OUT.mkdir(parents=True, exist_ok=True)


def zamknij_modal(page):
    for sel in ["button[aria-label='Zamknij']", ".modal button.close", ".modal .btn-close", "button:has-text('Zamknij')"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click()
                page.wait_for_timeout(500)
        except Exception:  # noqa: BLE001
            pass


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for nazwa, opcje in [("desktop", dict(viewport={"width": 1440, "height": 1000})),
                         ("telefon", dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True))]:
        ctx = b.new_context(**opcje, locale="pl-PL", geolocation={"latitude": 51.7592, "longitude": 19.4560}, permissions=["geolocation"])
        page = ctx.new_page()
        page.goto(URL, wait_until="load", timeout=90000)
        page.wait_for_timeout(6000)
        zamknij_modal(page)
        page.screenshot(path=str(OUT / f"aed_{nazwa}_start.png"))
        # najbliższy AED (geolokalizacja: Łódź, centrum)
        page.get_by_role("button", name="Pokaż najbliższy AED").click()
        page.wait_for_timeout(2500)
        if nazwa == "telefon":
            page.get_by_role("button", name="Mapa").click()
            page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / f"aed_{nazwa}_najblizszy.png"))
        page.screenshot(path=str(OUT / f"aed_{nazwa}_cala.png"), full_page=True)
        if nazwa == "desktop":
            page.locator(".aed-kolumna-mapa").screenshot(path=str(OUT / "aed_mapa_szczegoly.png"))
            page.get_by_role("tab", name="Dla dysponenta").click()
            page.wait_for_timeout(500)
            page.get_by_role("radio", name="Mam kilka AED").click()
            page.wait_for_timeout(800)
            page.locator("#panel-dysponent").screenshot(path=str(OUT / "formularz_dysponenta.png"))
            page.get_by_role("radio", name="Mam plik lub arkusz").click()
            page.wait_for_timeout(500)
            page.set_input_files("#aed-plik", str(Path(__file__).resolve().parent.parent / "dane_surowe" / "_probki_recznie" / "marki.csv"))
            page.wait_for_timeout(1500)
            page.locator("#panel-dysponent").screenshot(path=str(OUT / "walidator.png"))
        ctx.close()
    b.close()
print("zrzuty w", OUT)
