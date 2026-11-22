"""Mapy Google My Maps publikowane przez urzędy (eksport KML) – Olsztyn, Koszalin."""
import html
import re

from ..normalizacja import tekst
from ..siec import pobierz as pobierz_plik


def placemarki(sciezka) -> list[dict]:
    t = sciezka.read_text(encoding="utf-8", errors="ignore")
    wynik = []
    for p in re.findall(r"<Placemark>(.*?)</Placemark>", t, re.S):
        c = re.search(r"<coordinates>\s*([-\d.]+),([-\d.]+)", p)
        if not c:
            continue
        nazwa = re.search(r"<name>(.*?)</name>", p, re.S)
        opis = re.search(r"<description>(.*?)</description>", p, re.S)
        o = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", opis.group(1))) if opis else ""
        o = re.sub(r"<br\s*/?>", "\n", o)
        o = re.sub(r"<[^>]+>", " ", o)
        wynik.append({"nazwa": tekst(html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", nazwa.group(1))) if nazwa else ""),
                      "opis": "\n".join(tekst(x) for x in o.split("\n") if tekst(x)),
                      "lon": round(float(c.group(1)), 7), "lat": round(float(c.group(2)), 7)})
    return wynik


MAPY = [
    {"zrodlo_id": "JST-OLS", "dostawca_danych": "Urząd Miasta Olsztyna", "miejscowosc": "Olsztyn",
     "strona": "https://olsztyn.eu/urzad-miasta/zdrowie/defibrylatory-na-terenie-olsztyna.html", "mid": "1J5zJj9kL49uq8799g5qNgfl21NoztwzK",
     "uklad": "nazwa_z_adresem"},
    {"zrodlo_id": "JST-KOS", "dostawca_danych": "Urząd Miejski w Koszalinie", "miejscowosc": "Koszalin",
     "strona": "https://koszalin.pl/pl/page/punkty-zycia-defibrylatory-aed", "mid": "1AQwJAfeZsGGB7fhz0-yBSxab83DwyIw",
     "uklad": "opis_z_adresem",
     # informacja ze strony miasta: szafki z systemem powiadamiania o otwarciu, dostęp całodobowy
     "domyslne": {"zabezpieczenie": "szafka_z_alarmem", "godziny_dostepnosci": "24/7", "dostepny_24_7": "tak", "dostep": "publiczny"},
     "uwagi_zrodla": "Wg strony miasta: szafki z czujnikiem otwarcia powiadamiającym służby, dostęp 24/7."},
    {"zrodlo_id": "JST-PIOTRKOW", "dostawca_danych": "Urząd Miasta Piotrkowa Trybunalskiego", "miejscowosc": "Piotrków Trybunalski",
     "strona": "https://karta.piotrkow.pl/dla-mieszkanca", "mid": "1igR1CfvpzSnhCUiPBGQdGAXcSlf_gpk", "uklad": "opis_obiekt_adres"},
]


def _rozdziel_nazwe_adres(s: str):
    """'Urząd Miasta Olsztyna, Plac Jana Pawła II 1' -> ('Urząd Miasta Olsztyna', 'Plac Jana Pawła II 1')."""
    m = re.search(r",\s*((?:ul\.|al\.|pl\.|plac|aleja|os\.|osiedle)?\s*[^,]*\d+[a-zA-Z]?(?:/\d+)?)\s*$", s, re.I)
    if m:
        return s[:m.start()].strip(), m.group(1).strip()
    m = re.search(r"((?:ul\.|al\.|pl\.)\s*.*)$", s, re.I)
    if m:
        return s[:m.start()].strip(" ,–-"), m.group(1).strip()
    return s, ""


def pobierz():
    wynik = []
    for cfg in MAPY:
        mid = cfg["mid"]
        try:  # jeśli urząd podmieni mapę – weź aktualny identyfikator ze strony
            strona = pobierz_plik(cfg["strona"], f"{cfg['zrodlo_id']}/strona.html").read_text(encoding="utf-8", errors="ignore")
            mid = (re.search(r"mid=([A-Za-z0-9_-]{20,})", strona) or [None, mid])[1]
        except RuntimeError:
            pass
        url = f"https://www.google.com/maps/d/kml?mid={mid}&forcekml=1"
        rekordy = []
        for i, pm in enumerate(placemarki(pobierz_plik(url, f"{cfg['zrodlo_id']}/mapa.kml")), 1):
            r = {"id_zrodlowe": str(i), "szerokosc_geograficzna": pm["lat"], "dlugosc_geograficzna": pm["lon"],
                 "zrodlo_wspolrzednych": "mapa_dysponenta", "_flagi": [], "_tekst_opisowy": f"{pm['nazwa']} {pm['opis']}"}
            if cfg["uklad"] == "opis_obiekt_adres":   # Piotrków: nazwa 'Defibrylator wewnętrzny', opis 'Obiekt, ul. X 1 (…)'
                o = re.sub(r"\([^)]*\)", "", pm["opis"]).strip()
                obiekt, adres = _rozdziel_nazwe_adres(o)
                r.update(nazwa_obiektu=obiekt, _adres=adres,
                         wewnatrz_budynku="tak" if "wewnętrzny" in pm["nazwa"].lower() else ("nie" if "zewnętrzny" in pm["nazwa"].lower() else "nieznane"))
            elif cfg["uklad"] == "nazwa_z_adresem":
                obiekt, adres = _rozdziel_nazwe_adres(pm["nazwa"])
                r.update(nazwa_obiektu=obiekt, _adres=adres, opis_lokalizacji=pm["opis"])
            else:   # Koszalin: nazwa 'Punkt Życia #1', opis 'Obiekt (miejsce) – ul. X'
                r["uwagi"] = pm["nazwa"]
                o = pm["opis"]
                nawias = re.findall(r"\(([^)]+)\)", o)
                bez_naw = re.sub(r"\([^)]*\)", "", o)
                czesci = re.split(r"\s+[–-]\s+", bez_naw, maxsplit=1)
                obiekt = czesci[0].strip(" ,")
                adres_m = re.search(r"((?:ul\.|al\.|pl\.)\s*[^,()–]+)", o)
                r.update(nazwa_obiektu=obiekt, opis_lokalizacji="; ".join(nawias), _adres=adres_m.group(1).strip() if adres_m else "")
            r.update(cfg.get("domyslne", {}))
            rekordy.append(r)
        print(f"  {cfg['miejscowosc']}: {len(rekordy)} punktów z mapy")
        meta = {"zrodlo_id": cfg["zrodlo_id"], "dostawca_danych": cfg["dostawca_danych"], "zrodlo_url": url, "zbior_url": cfg["strona"],
                "licencja_zrodla": "brak informacji (informacja publiczna)", "data_stanu_zrodla": "", "miejscowosc": cfg["miejscowosc"],
                "dostep_domyslny": "publiczny", "sposob_weryfikacji": "deklaracja_dysponenta"}
        wynik.append((meta, rekordy))
    return wynik
