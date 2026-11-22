"""Wzorcowy zakres danych o defibrylatorach AED – jedno źródło prawdy.

Z tej definicji generowane są: arkusz xlsx (wzorcowy zakres), Table Schema (JSON),
szablon CSV dla dysponentów oraz reguły walidatora.

Poziomy:
  W – wymagane, Z – zalecane, O – opcjonalne,
  A – pola dodawane tylko przez agregator (pochodzenie i jakość rekordu; dysponent ich nie wypełnia).
"""
from dataclasses import dataclass, field

TAK_NIE = ["tak", "nie", "nieznane"]

SLOWNIKI = {
    "status": {
        "aktywny": "Urządzenie jest zainstalowane i dostępne zgodnie z opisem",
        "tymczasowo_niedostepny": "Np. serwis, remont budynku, kradzież – planowany powrót",
        "wycofany": "Urządzenie zdemontowane – rekord zostaje dla historii",
        "nieznany": "Brak informacji",
    },
    "typ_obiektu": {
        "urzad_administracja": "Urząd, sąd, prokuratura, ZUS, US",
        "szkola_przedszkole": "Szkoła, przedszkole, placówka oświatowa",
        "uczelnia": "Szkoła wyższa, kampus",
        "ochrona_zdrowia": "Przychodnia, szpital, pogotowie, apteka",
        "pomoc_spoleczna": "DPS, MOPS/MOPR, ośrodek wsparcia",
        "sport_rekreacja": "Hala, basen, stadion, kąpielisko, park",
        "kultura": "Muzeum, teatr, biblioteka, dom kultury",
        "transport": "Dworzec, lotnisko, pętla, przystanek, port",
        "handel_uslugi": "Centrum handlowe, sklep, bank, poczta, hotel",
        "sluzby_ratownicze": "Straż pożarna (PSP/OSP), policja, straż miejska, WOPR",
        "obiekt_sakralny": "Kościół, sanktuarium, parafia",
        "zaklad_pracy": "Zakład, biuro firmy, przedsiębiorstwo komunalne",
        "budynek_mieszkalny": "Osiedle, wspólnota, spółdzielnia",
        "przestrzen_publiczna": "Ulica, plac, deptak – urządzenie wolnostojące",
        "inny": "Inny obiekt",
    },
    "tak_nie": {"tak": "Tak", "nie": "Nie", "nieznane": "Brak informacji"},
    "dostep": {
        "publiczny": "Każdy może skorzystać bez pytania o zgodę",
        "dla_klientow_pracownikow": "Dostępny dla osób przebywających w obiekcie (klienci, pracownicy, uczniowie)",
        "prywatny": "Tylko dla właściciela/personelu – nie należy kierować do niego świadków zdarzenia",
        "nieznany": "Brak informacji",
    },
    "zabezpieczenie": {
        "brak": "AED wisi bez szafki, można go od razu zdjąć",
        "szafka_otwarta": "Szafka/kapsuła bez zamka i bez alarmu",
        "szafka_z_alarmem": "Szafka otwierana swobodnie, otwarcie uruchamia alarm/powiadomienie",
        "szafka_z_kodem": "Szafka zamknięta na kod – kod podaje dyspozytor 112 lub jest na tabliczce",
        "zamkniete_na_klucz": "Szafka/pomieszczenie zamknięte na klucz – wymaga osoby z kluczem",
        "u_personelu": "AED u ochrony/portiera/recepcji – trzeba poprosić personel",
        "nieznane": "Brak informacji",
    },
    "typ_montazu": {
        "wolnostojacy": "Słupek/postument w przestrzeni publicznej",
        "elewacja": "Na zewnętrznej ścianie budynku",
        "wewnatrz_budynku": "W budynku",
        "pojazd": "W pojeździe (autobus, tramwaj, radiowóz) – lokalizacja zmienna",
        "nieznany": "Brak informacji",
    },
    "zrodlo_wspolrzednych": {
        "pomiar_gps": "Pomiar w terenie (GPS) przy urządzeniu",
        "mapa_dysponenta": "Punkt naniesiony przez dysponenta na mapie",
        "geokodowanie_adresu": "Wyliczone z adresu budynku (dokładność do budynku)",
        "geokodowanie_ulicy": "Wyliczone ze środka ulicy/obszaru (dokładność niska)",
        "nieznane": "Brak informacji",
    },
    "stan_techniczny": {
        "sprawny": "Sprawny wg ostatniej kontroli",
        "niesprawny": "Niesprawny – nie kierować do niego",
        "w_serwisie": "W serwisie",
        "nieznany": "Brak informacji",
    },
    "sposob_weryfikacji": {
        "deklaracja_dysponenta": "Dane podane przez właściciela/zarządcę lub urząd",
        "kontrola_na_miejscu": "Osoba sprawdziła urządzenie na miejscu",
        "zgloszenie_spoleczne": "Zgłoszenie mieszkańca/wolontariusza, niepotwierdzone przez dysponenta",
        "nieznany": "Brak informacji",
    },
    "dysponent_typ": {
        "jst": "Gmina, powiat, województwo (urząd)",
        "jednostka_jst": "Jednostka organizacyjna samorządu (szkoła, MOPS, spółka komunalna)",
        "administracja_rzadowa": "Urząd i służba państwowa (wojewoda, PSP, policja, sądy)",
        "podmiot_leczniczy": "Szpital, przychodnia, pogotowie",
        "uczelnia": "Szkoła wyższa",
        "spolka_skarbu_panstwa": "Np. PKP, Poczta Polska",
        "firma": "Przedsiębiorca prywatny",
        "ngo": "Fundacja, stowarzyszenie, OSP",
        "wspolnota_spoldzielnia": "Wspólnota lub spółdzielnia mieszkaniowa",
        "kosciol_zwiazek_wyznaniowy": "Parafia, zakon, związek wyznaniowy",
        "inny": "Inny",
        "nieznany": "Brak informacji",
    },
}


@dataclass
class Pole:
    nazwa: str
    grupa: str
    poziom: str          # W/Z/O/A
    typ: str             # string/number/integer/date/boolean-ish via slownik
    opis: str
    przyklad: str = ""
    slownik: str | None = None
    wzorzec: str | None = None     # regex
    osm: str = ""
    min: float | None = None
    max: float | None = None
    uwagi: str = ""


POLA: list[Pole] = [
    # --- A. Identyfikacja ---
    Pole("id_aed", "Identyfikacja", "W", "string", "Stały identyfikator urządzenia nadany przez dysponenta (nie zmienia się przy aktualizacjach). W zbiorze zbiorczym poprzedzony kodem źródła.", "LDZ-0001"),
    Pole("status", "Identyfikacja", "W", "string", "Stan obecności urządzenia w lokalizacji.", "aktywny", "status"),
    Pole("numer_seryjny", "Identyfikacja", "O", "string", "Numer seryjny urządzenia – pozwala powiadomić dysponenta przy wycofaniu wadliwej partii przez producenta.", "B21K-04567"),
    Pole("osm_id", "Identyfikacja", "O", "string", "Identyfikator obiektu w OpenStreetMap (np. node/123), jeśli urządzenie jest tam naniesione.", "node/1446347184", osm="@osm_id"),
    # --- B. Lokalizacja ---
    Pole("nazwa_obiektu", "Lokalizacja", "W", "string", "Nazwa budynku lub miejsca, w którym jest AED.", "Szkoła Podstawowa nr 3", osm="name"),
    Pole("typ_obiektu", "Lokalizacja", "Z", "string", "Rodzaj obiektu (słownik).", "szkola_przedszkole", "typ_obiektu"),
    Pole("wojewodztwo", "Lokalizacja", "Z", "string", "Województwo.", "łódzkie"),
    Pole("powiat", "Lokalizacja", "Z", "string", "Powiat.", "Łódź"),
    Pole("gmina", "Lokalizacja", "Z", "string", "Gmina.", "Łódź"),
    Pole("teryt_gmina", "Lokalizacja", "Z", "string", "Identyfikator gminy z rejestru TERYT (TERC, 6 cyfr WWPPGG – jak zwraca usługa GUGiK).", "106101", wzorzec=r"^\d{6,7}$"),
    Pole("simc", "Lokalizacja", "Z", "string", "Identyfikator miejscowości z rejestru TERYT-SIMC.", "0957650", wzorzec=r"^\d{7}$", osm="addr:city:simc"),
    Pole("ulic", "Lokalizacja", "O", "string", "Identyfikator ulicy z rejestru TERYT-ULIC.", "15676", wzorzec=r"^\d{5}$"),
    Pole("miejscowosc", "Lokalizacja", "W", "string", "Miejscowość.", "Łódź", osm="addr:city"),
    Pole("ulica", "Lokalizacja", "W", "string", "Ulica wraz z cechą (ul., al., pl., os.). Wymagane, jeśli adres ma ulicę.", "ul. Paradna", osm="addr:street"),
    Pole("nr_budynku", "Lokalizacja", "W", "string", "Numer porządkowy budynku.", "36", osm="addr:housenumber"),
    Pole("kod_pocztowy", "Lokalizacja", "Z", "string", "Kod pocztowy.", "93-345", wzorzec=r"^\d{2}-\d{3}$", osm="addr:postcode"),
    Pole("szerokosc_geograficzna", "Lokalizacja", "W", "number", "Szerokość geograficzna urządzenia, WGS84 (EPSG:4326), stopnie dziesiętne, min. 5 miejsc po przecinku.", "51.709489", min=49.0, max=54.9),
    Pole("dlugosc_geograficzna", "Lokalizacja", "W", "number", "Długość geograficzna urządzenia, WGS84 (EPSG:4326), stopnie dziesiętne.", "19.480500", min=14.1, max=24.2),
    Pole("zrodlo_wspolrzednych", "Lokalizacja", "Z", "string", "Skąd pochodzą współrzędne – informuje o dokładności.", "pomiar_gps", "zrodlo_wspolrzednych"),
    Pole("wewnatrz_budynku", "Lokalizacja", "W", "string", "Czy urządzenie jest wewnątrz budynku.", "tak", "tak_nie", osm="indoor"),
    Pole("kondygnacja", "Lokalizacja", "O", "string", "Kondygnacja (0 = parter, -1 = piwnica).", "0", osm="level"),
    Pole("opis_lokalizacji", "Lokalizacja", "W", "string", "Gdzie dokładnie jest AED – tak, by obca osoba trafiła w stresie.", "Parter, przy wejściu głównym, na lewo od portierni", osm="defibrillator:location"),
    Pole("opis_lokalizacji_en", "Lokalizacja", "O", "string", "Opis lokalizacji po angielsku.", "Ground floor, left of the main entrance", osm="defibrillator:location:en"),
    # --- C. Dostępność ---
    Pole("dostep", "Dostępność", "W", "string", "Kto może skorzystać z urządzenia.", "publiczny", "dostep", osm="access"),
    Pole("godziny_dostepnosci", "Dostępność", "W", "string", "Godziny, w których AED jest fizycznie dostępny – składnia opening_hours (OSM), np. 24/7, Mo-Fr 08:00-16:00, Jun-Sep 09:30-17:30.", "Mo-Fr 07:30-15:30", osm="opening_hours"),
    Pole("dostepny_24_7", "Dostępność", "Z", "string", "Skrót: czy dostępny całą dobę przez cały rok.", "nie", "tak_nie"),
    Pole("godziny_opis", "Dostępność", "O", "string", "Godziny opisowo (gdy nie da się ich zapisać w składni opening_hours).", "w godzinach pracy szkoły"),
    Pole("zabezpieczenie", "Dostępność", "W", "string", "Jak zabezpieczone jest urządzenie – czy świadek zdarzenia otworzy je bez pomocy.", "szafka_z_alarmem", "zabezpieczenie", osm="locked", uwagi="Pole nowe – kluczowe przy zdarzeniu z 3 marca (AED zamknięte na klucz). W OSM wypełnione w 3 na 18 297 rekordów."),
    Pole("instrukcja_dostepu", "Dostępność", "Z", "string", "Co zrobić, by dostać się do AED (kod, klucz, osoba).", "Kod do szafki podaje dyspozytor 112"),
    Pole("typ_montazu", "Dostępność", "O", "string", "Sposób montażu.", "elewacja", "typ_montazu", osm="support"),
    Pole("mobilny", "Dostępność", "O", "string", "Czy urządzenie jest przenośne/w pojeździe (lokalizacja zmienna).", "nie", "tak_nie", osm="portable"),
    Pole("sezonowy", "Dostępność", "O", "string", "Czy dostępny tylko sezonowo (np. kąpielisko).", "nie", "tak_nie", osm="seasonal"),
    # --- D. Urządzenie ---
    Pole("producent", "Urządzenie", "Z", "string", "Producent.", "Philips", osm="manufacturer"),
    Pole("model", "Urządzenie", "Z", "string", "Model.", "HeartStart FRx", osm="model"),
    Pole("tryb_pediatryczny", "Urządzenie", "Z", "string", "Czy są elektrody pediatryczne lub tryb dziecięcy.", "tak", "tak_nie"),
    Pole("data_instalacji", "Urządzenie", "O", "date", "Data instalacji (RRRR-MM-DD).", "2023-05-12", osm="start_date"),
    # --- E. Stan i weryfikacja ---
    Pole("stan_techniczny", "Stan i weryfikacja", "Z", "string", "Stan techniczny wg ostatniej kontroli.", "sprawny", "stan_techniczny"),
    Pole("data_ostatniego_przegladu", "Stan i weryfikacja", "Z", "date", "Data ostatniego przeglądu serwisowego.", "2026-06-01"),
    Pole("data_waznosci_elektrod", "Stan i weryfikacja", "O", "date", "Data ważności elektrod.", "2027-03-31"),
    Pole("data_waznosci_baterii", "Stan i weryfikacja", "O", "date", "Data ważności baterii.", "2029-01-31"),
    Pole("data_weryfikacji", "Stan i weryfikacja", "W", "date", "Kiedy ostatnio potwierdzono, że urządzenie jest na miejscu.", "2026-11-01", osm="check_date"),
    Pole("sposob_weryfikacji", "Stan i weryfikacja", "W", "string", "Jak potwierdzono obecność urządzenia.", "deklaracja_dysponenta", "sposob_weryfikacji"),
    # --- F. Dysponent ---
    Pole("dysponent_nazwa", "Dysponent", "W", "string", "Właściciel lub zarządca urządzenia (odpowiada za jego sprawność).", "Szkoła Podstawowa nr 3 w Łodzi", osm="operator"),
    Pole("dysponent_typ", "Dysponent", "Z", "string", "Rodzaj dysponenta.", "jednostka_jst", "dysponent_typ", osm="operator:type"),
    Pole("dysponent_regon", "Dysponent", "Z", "string", "REGON dysponenta (tylko podmioty – nie dotyczy osób fizycznych).", "000123456", wzorzec=r"^(\d{9}|\d{14})$"),
    Pole("kontakt", "Dysponent", "O", "string", "Kontakt instytucjonalny (telefon/e-mail instytucji). Bez danych osobowych pracowników (RODO).", "sekretariat@sp3.lodz.pl", osm="phone"),
    Pole("zdjecie_url", "Dysponent", "O", "string", "Adres URL zdjęcia urządzenia/oznakowania.", "https://…/aed.jpg", osm="image"),
    Pole("uwagi", "Dysponent", "O", "string", "Dodatkowe informacje.", ""),
    # --- G. Pochodzenie (agregator) ---
    Pole("zrodlo_id", "Pochodzenie (agregator)", "A", "string", "Kod źródła w rejestrze źródeł (zrodla/rejestr_zrodel.csv).", "JST-LDZ"),
    Pole("dostawca_danych", "Pochodzenie (agregator)", "A", "string", "Instytucja, która opublikowała rekord i za niego ręczy.", "Urząd Miasta Łodzi"),
    Pole("zrodlo_url", "Pochodzenie (agregator)", "A", "string", "Adres, z którego pobrano dane.", "https://uml.lodz.pl/…/Defibrylatory2026.xls"),
    Pole("licencja_zrodla", "Pochodzenie (agregator)", "A", "string", "Licencja źródła lub informacja o jej braku.", "CC0 1.0"),
    Pole("data_stanu_zrodla", "Pochodzenie (agregator)", "A", "date", "Data stanu danych deklarowana przez źródło.", "2026-03-17"),
    Pole("data_pobrania", "Pochodzenie (agregator)", "A", "date", "Kiedy agregator pobrał dane.", "2026-11-21"),
    Pole("id_zrodlowe", "Pochodzenie (agregator)", "A", "string", "Identyfikator/numer pozycji w źródle.", "12"),
    Pole("adres_oryginalny", "Pochodzenie (agregator)", "A", "string", "Adres w postaci podanej przez źródło (przed normalizacją).", "ul. Paradna 36, 93-345 Łódź"),
    Pole("flagi_jakosci", "Pochodzenie (agregator)", "A", "string", "Wykryte problemy i wartości wywnioskowane – oddzielone średnikiem.", "zabezpieczenie_wywnioskowane;brak_dysponenta"),
    Pole("kompletnosc_proc", "Pochodzenie (agregator)", "A", "integer", "Procent wypełnionych pól wymaganych (W).", "82"),
]

KOLUMNY = [p.nazwa for p in POLA]
KOLUMNY_DYSPONENTA = [p.nazwa for p in POLA if p.poziom != "A"]
WYMAGANE = [p.nazwa for p in POLA if p.poziom == "W"]
POLE = {p.nazwa: p for p in POLA}

# wartość "nieznane/nieznany" nie liczy się jako wypełnienie pola wymaganego
WARTOSCI_PUSTE = {"", None, "nieznane", "nieznany"}


def table_schema() -> dict:
    """Frictionless Table Schema (https://specs.frictionlessdata.io/table-schema/)."""
    fields = []
    for p in POLA:
        f = {"name": p.nazwa, "title": p.nazwa, "description": p.opis, "type": p.typ if p.typ != "date" else "date"}
        c = {}
        if p.poziom == "W" and p.nazwa not in ("ulica", "nr_budynku"):
            c["required"] = True
        if p.slownik:
            c["enum"] = list(SLOWNIKI[p.slownik])
        if p.wzorzec:
            c["pattern"] = p.wzorzec
        if p.min is not None:
            c["minimum"] = p.min
        if p.max is not None:
            c["maximum"] = p.max
        if c:
            f["constraints"] = c
        f["poziom"] = p.poziom
        fields.append(f)
    return {"fields": fields, "primaryKey": ["id_aed"], "missingValues": [""]}
