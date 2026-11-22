"""Ujednolicenie rekordów do wzorcowego zakresu: adresy, geokodowanie (GUGiK), walidacja współrzędnych, wnioskowanie, kompletność."""
import re
from datetime import date

from . import geokoder as gk
from . import prg
from . import normalizacja as nz
from .schemat import KOLUMNY, POLE, SLOWNIKI, WARTOSCI_PUSTE, WYMAGANE

DZIS = date.today().isoformat()
PROG_ROZBIEZNOSCI_M = 1000   # współrzędne vs adres
PROG_DUPLIKATU_M = 30

# miasta na prawach powiatu (gmina = miasto) – jednostki wg TERYT, gdy geokoder niedostępny
MIASTA_TERYT = {
    "Łódź": ("łódzkie", "Łódź", "Łódź", "106101"),
    "Kraków": ("małopolskie", "Kraków", "Kraków", "126101"),
    "Lublin": ("lubelskie", "Lublin", "Lublin", "066301"),
    "Gdańsk": ("pomorskie", "Gdańsk", "Gdańsk", "226101"),
    "Olsztyn": ("warmińsko-mazurskie", "Olsztyn", "Olsztyn", "286201"),
    "Koszalin": ("zachodniopomorskie", "Koszalin", "Koszalin", "326101"),
    "Krosno": ("podkarpackie", "Krosno", "Krosno", "186101"),
    "Przemyśl": ("podkarpackie", "Przemyśl", "Przemyśl", "186201"),
}


def _w_polsce(lat, lon):
    return 49.0 <= lat <= 54.9 and 14.1 <= lon <= 24.2


def _ustaw_adres_z_geo(r: dict, g: dict, nadpisz_ulice: bool):
    """Uzupełnia pola administracyjne i (opcjonalnie) ulicę/kod z wyniku GUGiK."""
    for k_rek, k_geo in (("wojewodztwo", "wojewodztwo"), ("powiat", "powiat"), ("gmina", "gmina"),
                         ("teryt_gmina", "teryt_gmina"), ("simc", "simc")):
        if not r.get(k_rek) and g.get(k_geo):
            r[k_rek] = g[k_geo]
    if str(g.get("rodzaj", "")).startswith("adres") and nadpisz_ulice:
        if g.get("ulica_prg"):
            r["ulica"] = nz.ulica_z_prg(g["ulica_prg"])
            r["ulic"] = g.get("ulic", "")
        if g.get("nr"):
            r["nr_budynku"] = g["nr"]
        if g.get("kod_pocztowy"):
            r["kod_pocztowy"] = g["kod_pocztowy"]
        if g.get("miejscowosc"):
            r["miejscowosc"] = g["miejscowosc"]


def _geokoduj(r: dict, src: dict) -> dict:
    """Najpierw lokalny PRG (w obrębie obszaru źródła), potem usługa GUGiK (cache/sieć)."""
    if prg.dostepny():
        obszar = src.get("_obszar") or {}
        teryty = prg.teryty_obszaru(**obszar) if obszar else ()
        g = prg.geokoduj(r.get("miejscowosc", ""), r.get("ulica", ""), r.get("nr_budynku", ""), teryty)
        if not g and teryty and r.get("miejscowosc"):
            g = prg.geokoduj(r.get("miejscowosc", ""), r.get("ulica", ""), r.get("nr_budynku", ""), ())
        if g:
            return g
        if src.get("_odrzuc_bez_prg"):
            return {}
    return gk.geokoduj_adres(r.get("miejscowosc", ""), r.get("ulica", ""), r.get("nr_budynku", ""))


def przetworz(meta: dict, rekordy: list[dict]) -> list[dict]:
    import time
    t0 = time.time()
    wynik = []
    for i, src in enumerate(rekordy, 1):
        if i % 25 == 0:
            print(f"    {meta['zrodlo_id']}: {i}/{len(rekordy)} ({time.time() - t0:.0f} s)", flush=True)
        r = {k: v for k, v in src.items() if not k.startswith("_")}
        r["_kandydat"] = bool(src.get("_kandydat_duplikatu"))
        flagi = list(src.get("_flagi", []))
        opis_txt = src.get("_tekst_opisowy", "")

        # --- pochodzenie
        r.update(zrodlo_id=meta["zrodlo_id"], dostawca_danych=meta["dostawca_danych"], zrodlo_url=meta.get("zbior_url") or meta["zrodlo_url"],
                 licencja_zrodla=meta.get("licencja_zrodla", ""), data_stanu_zrodla=meta.get("data_stanu_zrodla", ""), data_pobrania=DZIS)
        r["id_zrodlowe"] = str(r.get("id_zrodlowe") or i)
        r["id_aed"] = f"{meta['zrodlo_id']}-{r['id_zrodlowe']}"

        # --- adres z tekstu
        if src.get("_adres"):
            r["adres_oryginalny"] = src["_adres"]
            a = nz.rozbij_adres(src["_adres"], r.get("miejscowosc") or meta.get("miejscowosc", ""))
            for k, v in a.items():
                if v and not r.get(k):
                    r[k] = v
        r.setdefault("miejscowosc", meta.get("miejscowosc", ""))
        if not r.get("miejscowosc"):
            r["miejscowosc"] = meta.get("miejscowosc", "")
        if not r.get("adres_oryginalny") and (r.get("ulica") or r.get("nr_budynku")):
            r["adres_oryginalny"] = " ".join(x for x in (r.get("ulica", ""), r.get("nr_budynku", ""), r.get("kod_pocztowy", ""), r.get("miejscowosc", "")) if x)

        lat, lon = r.get("szerokosc_geograficzna"), r.get("dlugosc_geograficzna")
        ma_adres = bool(r.get("ulica") or r.get("nr_budynku"))
        mobilny = r.get("mobilny") == "tak"

        # --- współrzędne: zamiana kolejności
        if lat is not None and lon is not None:
            if not _w_polsce(lat, lon) and _w_polsce(lon, lat):
                lat, lon = lon, lat
                flagi.append("zamienione_wspolrzedne_naprawiono")
            if not _w_polsce(lat, lon):
                flagi.append("wspolrzedne_poza_polska_usunieto")
                lat = lon = None

        geo_adres = _geokoduj(r, src) if ma_adres and not mobilny else {}
        odlozone = bool(geo_adres.pop("_pominieto", False)) if geo_adres else False

        if lat is not None:
            r.setdefault("zrodlo_wspolrzednych", "mapa_dysponenta")
            odw = prg.odwrotne(lat, lon) if prg.dostepny() else gk.odwrotne(lat, lon)
            if odw.pop("_pominieto", False):
                odlozone = True
            miasto_rek = gk.bez_ogonkow((r.get("miejscowosc") or "").lower())
            miasto_odw = gk.bez_ogonkow((odw.get("miejscowosc") or odw.get("gmina") or "").lower())
            if geo_adres and geo_adres["rodzaj"].startswith("adres"):
                d = gk.odleglosc_m(lat, lon, geo_adres["lat"], geo_adres["lon"])
                if odw and miasto_rek and miasto_odw and miasto_rek not in miasto_odw and miasto_odw not in miasto_rek and d > 5000:
                    flagi.append(f"wspolrzedne_w_innej_miejscowosci({odw.get('miejscowosc')})_zastapiono_geokodowaniem")
                    lat, lon = geo_adres["lat"], geo_adres["lon"]
                    r["zrodlo_wspolrzednych"] = "geokodowanie_adresu"
                    odw = {}
                elif d > PROG_ROZBIEZNOSCI_M:
                    flagi.append(f"rozbieznosc_wspolrzedne_adres_{int(d)}m")
            _ustaw_adres_z_geo(r, geo_adres or odw, nadpisz_ulice=bool(geo_adres))
            if not ma_adres and odw:
                r.update(ulica=nz.ulica_z_prg(odw.get("ulica_prg", "")), nr_budynku=odw.get("nr", ""), kod_pocztowy=odw.get("kod_pocztowy", ""),
                         ulic=odw.get("ulic", ""), miejscowosc=odw.get("miejscowosc") or r.get("miejscowosc"))
                flagi.append(f"adres_z_geokodowania_odwrotnego_{int(odw.get('odleglosc_m', 0))}m")
            elif ma_adres and not geo_adres and not odlozone:
                flagi.append("adres_nieznaleziony_w_prg")
        elif geo_adres:
            lat, lon = geo_adres["lat"], geo_adres["lon"]
            r["zrodlo_wspolrzednych"] = "geokodowanie_adresu" if geo_adres["rodzaj"].startswith("adres") else "geokodowanie_ulicy"
            if geo_adres["rodzaj"] == "adres_przyblizony":
                flagi.append("numer_budynku_przyblizony")
            if geo_adres["rodzaj"] == "ulica":
                flagi.append("wspolrzedne_przyblizone_srodek_ulicy")
            _ustaw_adres_z_geo(r, geo_adres, nadpisz_ulice=True)
        elif mobilny:
            r["zrodlo_wspolrzednych"] = "nieznane"
        else:
            r["zrodlo_wspolrzednych"] = "nieznane"
            flagi.append("brak_wspolrzednych_geokodowanie_odlozone" if odlozone else
                         ("brak_wspolrzednych_adres_nieznaleziony" if ma_adres else "brak_wspolrzednych_i_adresu"))
        if src.get("_odrzuc_bez_prg") and lat is None:
            continue   # linia ze strony www, której adresu nie ma w PRG – najpewniej nie jest pozycją wykazu
        if lat is not None:
            r["szerokosc_geograficzna"], r["dlugosc_geograficzna"] = round(float(lat), 6), round(float(lon), 6)
        else:
            r["szerokosc_geograficzna"] = r["dlugosc_geograficzna"] = ""

        if not r.get("wojewodztwo") and r.get("miejscowosc") in MIASTA_TERYT:
            woj, pow_, gm, terc = MIASTA_TERYT[r["miejscowosc"]]
            r.update(wojewodztwo=woj, powiat=pow_, gmina=gm, teryt_gmina=r.get("teryt_gmina") or terc)
            flagi.append("jednostka_terytorialna_z_nazwy_miasta")

        # --- wnioskowanie słownikowe (oznaczane flagą)
        tekst_all = " ".join(str(x) for x in (r.get("nazwa_obiektu", ""), r.get("opis_lokalizacji", ""), opis_txt))
        if not r.get("typ_obiektu"):
            r["typ_obiektu"] = nz.typ_obiektu(r.get("nazwa_obiektu", ""), opis_txt)
        if not r.get("wewnatrz_budynku") or r["wewnatrz_budynku"] == "nieznane":
            r["wewnatrz_budynku"] = nz.wewnatrz(r.get("opis_lokalizacji", ""), opis_txt)
            if r["wewnatrz_budynku"] != "nieznane":
                flagi.append("wewnatrz_budynku_wywnioskowane")
        if not r.get("typ_montazu"):
            r["typ_montazu"] = nz.typ_montazu(r.get("opis_lokalizacji", ""), opis_txt)
            if r["typ_montazu"] != "nieznany" and r["typ_montazu"] == "wewnatrz_budynku" and r["wewnatrz_budynku"] == "nie":
                r["typ_montazu"] = "nieznany"
        if not r.get("zabezpieczenie"):
            r["zabezpieczenie"] = nz.zabezpieczenie(tekst_all)
            if r["zabezpieczenie"] != "nieznane":
                flagi.append("zabezpieczenie_wywnioskowane")
        if not r.get("godziny_dostepnosci"):
            g = nz.godziny(r.get("godziny_opis", ""))
            r["godziny_dostepnosci"] = g["godziny_dostepnosci"]
            if not r.get("dostepny_24_7") or r["dostepny_24_7"] == "nieznane":
                r["dostepny_24_7"] = g["dostepny_24_7"]
            if not r.get("sezonowy"):
                r["sezonowy"] = g["sezonowy"]
        r.setdefault("dostepny_24_7", "nieznane")
        r.setdefault("sezonowy", "nieznane")
        if r["godziny_dostepnosci"] == "24/7":
            r["dostepny_24_7"] = "tak"
        if not r.get("dostep"):
            r["dostep"] = meta.get("dostep_domyslny", "nieznany")
            if r["dostep"] != "nieznany":
                flagi.append("dostep_z_deklaracji_zrodla")
        if not r.get("mobilny"):
            r["mobilny"] = "tak" if r.get("typ_montazu") == "pojazd" else "nie"
        if r.get("dysponent_nazwa") and not r.get("dysponent_typ"):
            r["dysponent_typ"] = nz.dysponent_typ(r["dysponent_nazwa"])
        if not r.get("dysponent_nazwa"):
            flagi.append("brak_dysponenta_urzadzenia")
            r.setdefault("dysponent_typ", "nieznany")

        # --- status i weryfikacja
        r.setdefault("status", "aktywny")
        r.setdefault("sposob_weryfikacji", meta.get("sposob_weryfikacji", "nieznany"))
        if not r.get("data_weryfikacji"):
            r["data_weryfikacji"] = meta.get("data_stanu_zrodla", "")
        for k in ("tryb_pediatryczny",):
            r.setdefault(k, "nieznane")
        r.setdefault("stan_techniczny", "nieznany")

        if odlozone:
            flagi.append("geokodowanie_odlozone")
        r["_flagi"] = flagi
        wynik.append(r)

    _oznacz_duplikaty(wynik, rekordy)
    for r in wynik:
        # słowniki – wartości spoza słownika zamieniamy na 'nieznane' z flagą
        for p in KOLUMNY:
            pole = POLE[p]
            if pole.slownik and r.get(p) not in (None, "") and r[p] not in SLOWNIKI[pole.slownik]:
                r["_flagi"].append(f"wartosc_spoza_slownika_{p}")
                r[p] = "nieznane" if "nieznane" in SLOWNIKI[pole.slownik] else "nieznany"
        braki = [p for p in WYMAGANE if r.get(p) in WARTOSCI_PUSTE and not (p in ("ulica", "nr_budynku") and r.get("mobilny") == "tak")]
        r["kompletnosc_proc"] = round(100 * (len(WYMAGANE) - len(braki)) / len(WYMAGANE))
        if braki:
            r["_flagi"].append("braki_wymaganych:" + ",".join(braki))
        r["flagi_jakosci"] = ";".join(dict.fromkeys(r.pop("_flagi")))
        r.pop("_kandydat", None)
        for k in KOLUMNY:
            r.setdefault(k, "")
    return wynik


def _oznacz_duplikaty(wynik, zrodlowe):
    """W obrębie jednego źródła: (1) punkty 'tylko z mapy' dublujące rekord wykazu – usuwamy; (2) identyczne współrzędne – flaga."""
    usun = set()
    for i, r in enumerate(wynik):
        if not r["_kandydat"] or r["szerokosc_geograficzna"] == "":
            continue
        for j, q in enumerate(wynik):
            if j != i and not q["_kandydat"] and q["szerokosc_geograficzna"] != "":
                if gk.odleglosc_m(r["szerokosc_geograficzna"], r["dlugosc_geograficzna"], q["szerokosc_geograficzna"], q["dlugosc_geograficzna"]) < 60:
                    usun.add(i)
                    break
    for i in sorted(usun, reverse=True):
        del wynik[i]
    wsp = {}
    for r in wynik:
        if r["szerokosc_geograficzna"] == "" or r.get("zrodlo_wspolrzednych", "").startswith("geokodowanie"):
            continue
        wsp.setdefault((round(r["szerokosc_geograficzna"], 5), round(r["dlugosc_geograficzna"], 5)), []).append(r)
    for grupa in wsp.values():
        if len(grupa) > 1 and len({g.get("nazwa_obiektu") for g in grupa}) > 1:
            for g in grupa:
                g["_flagi"].append("te_same_wspolrzedne_co_inny_obiekt")
