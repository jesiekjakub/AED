"""Misja AED – crawler i walidator.

  python -m crawler                 pełny przebieg: pobranie źródeł → ujednolicenie → eksport → raport → XML → schemat → porównanie z OSM
  python -m crawler gminy [--limit N]   przeszukanie stron wszystkich gmin (Wikidata + sitemap + PRG)
  python -m crawler prg             zbudowanie lokalnego indeksu adresów PRG (geokodowanie bez limitów usług)
  python -m crawler schemat         tylko artefakty wzorcowego zakresu danych (schemat/)
  python -m crawler waliduj PLIK    walidacja pliku CSV dysponenta (dodaj --geo, by sprawdzić adresy w GUGiK)

Zmienne: AED_OFFLINE=1 (użyj kopii z dane_surowe/), AED_WARSZAWA_TOKEN, AED_BAZA_URL (adres publikacji plików w XML).
"""
import json
import os
import sys

from . import eksport, geokoder, osm, przetwarzanie, siec
from .zrodla import ADAPTERY


def pelny_przebieg():
    wszystkie, metas = [], []
    for nazwa, fn in ADAPTERY:
        print(f"[{nazwa}]")
        try:
            paczki = fn()
        except Exception as e:  # noqa: BLE001
            print(f"  ! błąd adaptera: {e}")
            continue
        for meta, rek in paczki:
            if not rek:
                continue
            przetworzone = przetwarzanie.przetworz(meta, rek)
            geokoder.zapisz_cache()
            wszystkie.extend(przetworzone)
            metas.append(meta)
    wszystkie.sort(key=lambda r: (r["wojewodztwo"], r["miejscowosc"], r["id_aed"]))
    n_stac, n_geo, n_mob = eksport.zapisz_zbior(wszystkie)
    rap = eksport.raport(wszystkie, metas, sorted(siec.ZABLOKOWANE))
    daty = sorted(m.get("data_stanu_zrodla") for m in metas if m.get("data_stanu_zrodla"))
    xml = eksport.metadane_xml([r for r in wszystkie if r["mobilny"] != "tak"], os.environ.get("AED_BAZA_URL", "https://raw.githubusercontent.com/jesiekjakub/AED/main/dane"), daty[-1] if daty else "")
    bledy = eksport.waliduj_xml(xml)
    eksport.artefakty_schematu(rap["pokrycie_pol_proc"])
    portal = eksport.KORZEN / "portal" / "src" / "assets" / "aed"
    if portal.parent.exists():
        eksport.zapisz_dla_portalu(wszystkie, portal)
        print(f"Skopiowano dane do portalu: {portal}")
    print(f"\nZbiór zbiorczy: {n_stac} AED stacjonarnych ({n_geo} ze współrzędnymi) + {n_mob} mobilnych z {len(metas)} źródeł -> dane/")
    print(f"Metadane XML (harwester dane.gov.pl 1.13): {'zgodne z XSD' if not bledy else 'BŁĘDY: ' + '; '.join(bledy)}")
    print(json.dumps({k: v for k, v in rap.items() if k not in ("zrodla", "pokrycie_pol_proc")}, ensure_ascii=False, indent=1))
    try:
        for w in osm.porownaj([r for r in wszystkie if r["mobilny"] != "tak"]):
            print("  OSM:", w)
    except Exception as e:  # noqa: BLE001
        print(f"  ! porównanie z OSM pominięte: {e}")


def main(argv):
    if not argv:
        pelny_przebieg()
    elif argv[0] == "gminy":
        from .odkrywanie_gmin import ponow_niedostepne, uruchom
        if "--ponow" in argv:
            ponow_niedostepne()
        else:
            uruchom(int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None)
    elif argv[0] == "prg":
        from .prg import zbuduj
        zbuduj()
    elif argv[0] == "schemat":
        eksport.artefakty_schematu()
        print("Zapisano schemat/")
    elif argv[0] == "waliduj" and len(argv) > 1:
        from .walidator import waliduj
        return waliduj(argv[1], "--geo" in argv)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
