"""Adaptery źródeł. Każdy zwraca listę (meta, rekordy).

meta: zrodlo_id, dostawca_danych, zrodlo_url, licencja_zrodla, data_stanu_zrodla, miejscowosc (domyślna),
      dostep_domyslny, sposob_weryfikacji, uwagi_zrodla
rekordy: słowniki z polami schematu (częściowo) + pola techniczne z prefiksem '_':
      _adres (tekst adresu do rozbicia), _tekst_opisowy (tekst do wnioskowania klasyfikacji)
"""
from . import dane_gov, lodz, mapy_kml, krakow, lublin, gdansk, warszawa, siemianowice, strony_urzedow, gminy_auto

ADAPTERY = [
    ("dane.gov.pl (auto-wykrywanie)", dane_gov.pobierz),
    ("Łódź", lodz.pobierz),
    ("Mapy KML (Olsztyn, Koszalin, Piotrków)", mapy_kml.pobierz),
    ("Kraków (PDF)", krakow.pobierz),
    ("Lublin (PDF)", lublin.pobierz),
    ("Gdańsk (HTML)", gdansk.pobierz),
    ("Siemianowice Śląskie (CSV)", siemianowice.pobierz),
    ("Strony urzędów (ekstrakcja list adresów)", strony_urzedow.pobierz),
    ("Przeszukanie stron wszystkich gmin", gminy_auto.pobierz),
    ("Warszawa (API, token)", warszawa.pobierz),
]
