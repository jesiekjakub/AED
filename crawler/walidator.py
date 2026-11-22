"""Walidator pliku CSV dysponenta względem wzorcowego zakresu danych (narzędzie dla gmin przed publikacją na dane.gov.pl).

Użycie: python -m crawler waliduj plik.csv [--geo]
  --geo  dodatkowo sprawdza w GUGiK, czy współrzędne zgadzają się z adresem (wymaga internetu)
"""
import csv
import re
import sys
from datetime import date

from . import geokoder as gk
from .schemat import KOLUMNY_DYSPONENTA, POLE, SLOWNIKI, WARTOSCI_PUSTE, WYMAGANE


def waliduj(sciezka: str, geo: bool = False) -> int:
    with open(sciezka, encoding="utf-8-sig", newline="") as f:
        probka = f.read(4096)
        f.seek(0)
        dialekt = csv.Sniffer().sniff(probka.splitlines()[0], delimiters=",;\t")
        wiersze = list(csv.DictReader(f, dialect=dialekt))
    bledy, ostrzezenia = [], []
    kolumny = list(wiersze[0].keys()) if wiersze else []
    if dialekt.delimiter != ",":
        ostrzezenia.append(f"Separator '{dialekt.delimiter}' – zalecany przecinek")
    brak_kol = [k for k in WYMAGANE if k not in kolumny]
    if brak_kol:
        bledy.append(f"Brak wymaganych kolumn: {', '.join(brak_kol)}")
    nieznane = [k for k in kolumny if k not in POLE]
    if nieznane:
        ostrzezenia.append(f"Kolumny spoza wzorca (zostaną pominięte): {', '.join(nieznane)}")
    ids = set()
    for n, w in enumerate(wiersze, 2):
        def B(msg):
            bledy.append(f"wiersz {n}: {msg}")

        def O(msg):
            ostrzezenia.append(f"wiersz {n}: {msg}")
        for k in WYMAGANE:
            if k in kolumny and (w.get(k) or "").strip() in WARTOSCI_PUSTE:
                if k in ("ulica", "nr_budynku") and (w.get("mobilny") == "tak"):
                    continue
                (B if k in ("id_aed", "szerokosc_geograficzna", "dlugosc_geograficzna", "nazwa_obiektu", "miejscowosc") else O)(f"puste pole wymagane '{k}'")
        if w.get("id_aed"):
            if w["id_aed"] in ids:
                B(f"zdublowany id_aed '{w['id_aed']}'")
            ids.add(w["id_aed"])
        for k, v in w.items():
            if k not in POLE or not v:
                continue
            p = POLE[k]
            if p.slownik and v not in SLOWNIKI[p.slownik]:
                B(f"'{k}' = '{v}' spoza słownika ({', '.join(SLOWNIKI[p.slownik])})")
            if p.wzorzec and not re.match(p.wzorzec, v):
                B(f"'{k}' = '{v}' nie pasuje do wzorca {p.wzorzec}")
            if p.typ == "date":
                try:
                    d = date.fromisoformat(v)
                    if k == "data_weryfikacji" and (date.today() - d).days > 365:
                        O(f"data_weryfikacji {v} starsza niż rok – potwierdź obecność urządzenia")
                    if k == "data_waznosci_elektrod" and d < date.today():
                        O(f"elektrody przeterminowane ({v})")
                except ValueError:
                    B(f"'{k}' = '{v}' – oczekiwano RRRR-MM-DD")
            if p.typ == "number":
                try:
                    x = float(v)
                    if p.min is not None and not (p.min <= x <= p.max):
                        B(f"'{k}' = {v} poza zakresem dla Polski ({p.min}–{p.max})")
                except ValueError:
                    B(f"'{k}' = '{v}' nie jest liczbą (separator dziesiętny: kropka)")
        try:
            lat, lon = float(w.get("szerokosc_geograficzna") or "x"), float(w.get("dlugosc_geograficzna") or "x")
            if not (49 <= lat <= 54.9) and 49 <= lon <= 54.9:
                B("szerokość i długość geograficzna są zamienione miejscami")
            if len((w.get("szerokosc_geograficzna") or "").split(".")[-1]) < 5:
                O("mniej niż 5 miejsc po przecinku we współrzędnych – dokładność gorsza niż ~1 m")
            if geo and w.get("ulica") and w.get("nr_budynku"):
                g = gk.geokoduj_adres(w.get("miejscowosc", ""), w["ulica"], w["nr_budynku"])
                if g and g["rodzaj"] == "adres":
                    d = gk.odleglosc_m(lat, lon, g["lat"], g["lon"])
                    if d > 300:
                        O(f"współrzędne {int(d)} m od adresu {w['ulica']} {w['nr_budynku']} wg GUGiK")
                elif not g:
                    O("adres nie znaleziony w Państwowym Rejestrze Granic (GUGiK)")
        except ValueError:
            pass
        if w.get("zabezpieczenie") == "zamkniete_na_klucz" and not w.get("instrukcja_dostepu"):
            O("AED zamknięty na klucz bez instrukcji dostępu – świadek zdarzenia nie skorzysta z urządzenia")
        if re.search(r"\b[A-ZŁŚŻ][a-ząęółśżźćń]+ [A-ZŁŚŻ][a-ząęółśżźćń]+\b.*\b\d{3}[ -]?\d{3}[ -]?\d{3}\b", w.get("kontakt", "")):
            O("pole 'kontakt' wygląda na dane osobowe (imię, nazwisko, telefon) – publikuj tylko kontakt instytucji")
    if geo:
        gk.zapisz_cache()
    print(f"Plik: {sciezka}\nWierszy: {len(wiersze)}  Błędy: {len(bledy)}  Ostrzeżenia: {len(ostrzezenia)}\n")
    for b in bledy[:200]:
        print("BŁĄD     ", b)
    for o in ostrzezenia[:200]:
        print("UWAGA    ", o)
    if not bledy:
        print("\nPlik zgodny ze wzorcowym zakresem danych – można publikować na dane.gov.pl.")
    return 1 if bledy else 0


if __name__ == "__main__":
    sys.exit(waliduj(sys.argv[1], "--geo" in sys.argv))
