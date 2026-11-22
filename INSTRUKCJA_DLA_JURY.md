# Instrukcja dla jury – „AED na ratunek”

Każdy krok wskazuje, co otworzyć i gdzie sprawdzić jedno wymaganie z treści zadania. Kroki 1–9 da się wykonać na samych plikach, bez uruchamiania czegokolwiek. Krok 10 to przejście całego procesu w prototypie.

**Repozytorium:** https://github.com/jesiekjakub/AED

## Wymagania formalne

**1. Tytuł i opis projektu**
Otwórz `README.md`, czyli stronę główną repozytorium. Opis projektu jest na górze, a pod nim „Spis najważniejszych rzeczy”.

**2. Prezentacja (min. 5 slajdów ze zrzutami, kroki użytkownika, ograniczenia)**
Otwórz `kampania/prezentacja_AED_na_ratunek.pdf` (15 slajdów).
- Zrzuty ekranu jako dowody: slajdy 4, 5, 6, 7, 9 i 10.
- Kroki użytkownika: slajd 6 (mieszkaniec) i slajd 7 (dysponent).
- Ograniczenia: slajd 13.

**3. Plik z wzorcowym zakresem danych (XLSX)**
Otwórz `schemat/wzorcowy_zakres_danych_AED.xlsx`.
- Arkusz „Pola”: 58 pól. Kolumna „Poziom” mówi, czy pole jest wymagane (W), zalecane (Z), opcjonalne (O), czy dopisuje je portal (A).
- Arkusz „Słowniki”: dozwolone wartości, np. pole `zabezpieczenie` (czy AED jest zamknięty na klucz).
- Arkusz „Przykład”: wypełnione wiersze.
- Arkusz „Metadane zbioru”: jak opisać zbiór w dane.gov.pl.

**4. Kod źródłowy**
Otwórz historię commitów repozytorium.
- Pierwszy commit po „Initial commit” to rozpakowany, niezmieniony kod dane.gov.pl z https://dane.gov.pl/source-code/.
- Kolejne commity to nasze zmiany: backend, frontend, wzorzec i crawler, kampania.
- W kodzie portalu nasze zmiany są oznaczone komentarzem `# MISJA AED`.

**5. Logotyp (JPG, PNG, PDF i format otwarty)**
Otwórz katalog `kampania/logo/`. Wersja podstawowa to `logo_aed_na_ratunek` w czterech formatach: `.jpg`, `.png`, `.pdf` i `.svg` (format otwarty). Pozostałe pliki to warianty kolorystyczne.

**6. Księga znaku (PDF)**
Otwórz `kampania/ksiega_znaku_AED_na_ratunek.pdf`.
- Koncepcja (4 zdania): rozdział 1.
- Pole ochronne: rozdział 2.
- Minimalna wielkość: rozdział 3.
- Kolorystyka: rozdział 4.
- Niedozwolone użycie znaku: rozdział 6.
- Hasło akcji: „Pokaż, gdzie jest AED. Każda minuta się liczy.”

## Wymagania techniczne

**7. Format odczytywalny maszynowo**
Wykaz zbiorczy AED portal publikuje w CSV, XLSX, GeoJSON i przez API. Przykład gotowego pliku: `dane/aed_zbiorczy.csv` (1279 AED). PDF jest użyty tylko w logo, księdze znaku i materiałach kampanii.

**8. Zgodność z zasadami działania portalu dane.gov.pl**
Odtworzyliśmy w kodzie portalu logikę istniejącego wykazu DGA.
- Zasilanie ręczne: pole „Zasób zawiera wykaz AED” w panelu dostawcy. Zrzut: `kampania/zrzuty/admin_zasob_aed.png`. Nasze pole jest tuż pod polem wykazu DGA.
- Zasilanie automatyczne: harwester XML z nowym elementem `containsAedList`. Schemat: `backend/data/harvester/xml_import_otwarte_dane_1_14.xsd`.
- Scalanie: co noc portal łączy wszystkie zasoby z tą flagą w jeden zasób „Wykaz zbiorczy AED”. Kod: `backend/mcod/resources/aed_utils.py` i `backend/mcod/resources/tasks/aed.py`.
- Tabela w portalu, wyglądająca tak samo jak wykaz DGA: `kampania/zrzuty/wykaz_tabela_w_portalu.png`.
- Raport scalania w API: `kampania/zrzuty/api_aggregated_aed_info.png`.

**9. WCAG, responsywność, UX**
- Wynik testu axe-core (WCAG 2.2 AA, 0 naruszeń na komputerze i telefonie): `kampania/zrzuty/wcag_axe.json`.
- Widok na telefonie: `kampania/zrzuty/aed_telefon_start.png` i `aed_telefon_najblizszy.png`.

## Prototyp – przejście całego procesu

**10. W prototypie (portal dane.gov.pl z naszymi zmianami)**
1. W menu portalu kliknij „Mapa AED”.
2. Pierwsza zakładka pod mapą, „Wykaz zbiorczy AED (tabela)”, to tabela wykazu osadzona w portalu, z kolumnami: dysponent, link do zasobu źródłowego i data aktualizacji. Możesz ją sortować i stronicować.
3. Kliknij „Pokaż najbliższy AED” i zezwól na lokalizację. Zobaczysz najbliższe urządzenie, jego godziny i to, czy nie jest zamknięte na klucz.
4. Zakładka „Dla dysponenta”, przycisk „Mam kilka AED”: wypełnij formularz i pobierz gotowy plik CSV.
5. Zakładka „Dla dysponenta”, przycisk „Mam plik lub arkusz”: wgraj plik do walidatora. Plik z błędami do testu jest w repozytorium: `backend/data/aed/demo/aed_marki_niezgodny.csv`.
6. W menu „Dane” wyszukaj „Wykaz zbiorczy defibrylatorów AED”. Wykaz to zwykły zbiór w portalu, który można pobrać jako CSV, XLSX lub GeoJSON.

Jeśli prototyp jest niedostępny, ten sam przebieg pokazują slajdy 4–7 prezentacji i zrzuty w `kampania/zrzuty/`. Instrukcja uruchomienia portalu u siebie jest w `README.md`, w sekcji „Uruchomienie”.

## Użycie AI

Przy kodzie i materiałach pomagał nam asystent AI (Claude). Decyzje i sprawdzanie należały do zespołu. Więcej w `README.md`, w sekcji „Użycie AI”.
