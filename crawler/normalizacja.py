"""Reguły ujednolicania: adresy, godziny dostępności, klasyfikacje słownikowe wywnioskowane z tekstu."""
import re

from .geokoder import bez_ogonkow


def tekst(s) -> str:
    if s is None:
        return ""
    s = str(s).replace("\xa0", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip(" ,;")


# ---------------------------------------------------------------- adresy
_NR = r"(\d+[A-Za-z]?(?:\s?[/-]\s?\d+[A-Za-z]?)?)"


def rozbij_adres(adres: str, domyslna_miejscowosc: str = "") -> dict:
    """'ul. Paradna 36, 93-345 Łódź' -> {miejscowosc, ulica, nr_budynku, kod_pocztowy}."""
    a = tekst(adres).replace("Al..", "al.").replace("..", ".")
    wynik = {"miejscowosc": domyslna_miejscowosc, "ulica": "", "nr_budynku": "", "kod_pocztowy": ""}
    m = re.search(r"(\d{2}-\d{3})\s*([^\d,]*)", a)
    if m:
        wynik["kod_pocztowy"] = m.group(1)
        if m.group(2).strip():
            wynik["miejscowosc"] = m.group(2).strip()
        a = (a[:m.start()] + a[m.end():]).strip(" ,")
    czesci = [c.strip() for c in a.split(",") if c.strip()]
    ulica_czesc = ""
    for c in czesci:
        if re.search(r"\d", c) or re.match(r"(?i)(ul\.|al\.|pl\.|os\.|plac|aleja|rondo|osiedle)", c):
            if not ulica_czesc:
                ulica_czesc = c
        elif not m and c and ulica_czesc:      # 'ul. X 1, Balice' – miejscowość po przecinku
            wynik["miejscowosc"] = c
    if not ulica_czesc and czesci:
        ulica_czesc = czesci[0]
    mm = re.match(r"^(.*?)\s+" + _NR + r"\s*$", ulica_czesc)
    if mm:
        wynik["ulica"], wynik["nr_budynku"] = mm.group(1).strip(), mm.group(2).replace(" ", "")
    else:
        wynik["ulica"] = ulica_czesc
    return wynik


def ulica_z_prg(nazwa_prg: str) -> str:
    """Nazwa ulicy z PRG ('Paradna', 'Aleja Kościuszki') -> forma z cechą ('ul. Paradna', 'al. Kościuszki')."""
    n = (nazwa_prg or "").strip()
    if not n:
        return ""
    zamiany = [("Aleja ", "al. "), ("Aleje ", "al. "), ("Plac ", "pl. "), ("Osiedle ", "os. "), ("Rondo ", "rondo "), ("Bulwar ", "bulw. ")]
    for a, b in zamiany:
        if n.startswith(a):
            return b + n[len(a):]
    if re.match(r"(?i)(al\.|pl\.|os\.|ul\.|rondo|skwer|bulw|wybrzeże|park|droga)", n):
        return n
    return "ul. " + n


# ---------------------------------------------------------------- godziny
_DNI = [("pon", "Mo"), ("pn", "Mo"), ("wt", "Tu"), ("śr", "We"), ("sr", "We"), ("czw", "Th"), ("pt", "Fr"), ("piąt", "Fr"),
        ("piat", "Fr"), ("sob", "Sa"), ("niedz", "Su"), ("nd", "Su")]
_MIES = [("stycz", "Jan"), ("lut", "Feb"), ("mar", "Mar"), ("kwie", "Apr"), ("maj", "May"), ("czerw", "Jun"), ("lip", "Jul"),
         ("sierp", "Aug"), ("wrze", "Sep"), ("paźdz", "Oct"), ("pazdz", "Oct"), ("listop", "Nov"), ("grud", "Dec")]


def _dzien(s):
    s = s.lower()
    for p, k in _DNI:
        if s.startswith(p):
            return k
    return None


def _mies(s):
    s = s.lower()
    for p, k in _MIES:
        if s.startswith(p):
            return k
    return None


def _hh(h, m):
    return f"{int(h):02d}:{int(m or 0):02d}"


def godziny(opis: str) -> dict:
    """Tekst -> {godziny_dostepnosci (opening_hours), dostepny_24_7, sezonowy}. Pusty opening_hours, gdy nie da się ustalić."""
    t = tekst(opis)
    tl = t.lower()
    w = {"godziny_dostepnosci": "", "dostepny_24_7": "nieznane", "sezonowy": "nieznane"}
    if not t:
        return w
    if re.search(r"całodob|calodob|24\s*h|24/7|24 godz|całą dobę|cala dobe|przez całą dobę|non[- ]?stop", tl):
        w.update(godziny_dostepnosci="24/7", dostepny_24_7="tak", sezonowy="nie")
        return w
    w["dostepny_24_7"] = "nie"
    sezon = ""
    ms = re.search(r"od\s+(\w+)\s+do\s+(\w+)", tl)
    if "sezon" in tl or (ms and _mies(ms.group(1)) and _mies(ms.group(2))):
        w["sezonowy"] = "tak"
        if ms and _mies(ms.group(1)) and _mies(ms.group(2)):
            sezon = f"{_mies(ms.group(1))}-{_mies(ms.group(2))} "
    czasy = re.findall(r"(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})|(?<![\d:])(\d{1,2})\s*[-–]\s*(\d{1,2})(?![\d:])", tl)
    if not czasy:
        return w
    c = czasy[0]
    if c[0]:
        zakres = f"{_hh(c[0], c[1])}-{_hh(c[2], c[3])}"
    else:
        if not (0 <= int(c[4]) <= 24 and 0 <= int(c[5]) <= 24):
            return w
        zakres = f"{_hh(c[4], 0)}-{_hh(c[5], 0)}"
    dni = ""
    md = re.search(r"(pon\w*|pn\.?|wt\w*|śr\w*|czw\w*|pt\.?|piąt\w*|sob\w*|niedz\w*)\s*(?:-|–|do)\s*(pon\w*|pn\.?|wt\w*|śr\w*|czw\w*|pt\.?|piąt\w*|piat\w*|sob\w*|niedz\w*|nd\.?)", tl)
    if md and _dzien(md.group(1)) and _dzien(md.group(2)):
        dni = f"{_dzien(md.group(1))}-{_dzien(md.group(2))} "
    elif "codziennie" in tl or "7 dni" in tl:
        dni = "Mo-Su "
    if not dni and "weekend" not in tl:
        dni = ""
    if dni or sezon or re.fullmatch(r"[\d:.\s–-]+", t):
        w["godziny_dostepnosci"] = f"{sezon}{dni}{zakres}".strip()
    return w


# ---------------------------------------------------------------- klasyfikacje z tekstu
_TYP_OBIEKTU = [
    ("pojazd", r"(w pojeździe|w pojezdzie|na wyposażeniu radiow|radiowóz|radiowoz|na wyposażeniu taboru|w autobusach|w tramwajach)"),
    ("szkola_przedszkole", r"\b(szkoł|szkol|\bsp\b|sp nr|przedszkol|liceum|\blo\b|gimnaz|zesp[oó]ł szk|technikum|bursa|oświat)"),
    ("uczelnia", r"(uniwersyt|politechn|akademi|uczelni|kampus|collegium|wydział|umcs|\buw\b|\bum\b)"),
    ("ochrona_zdrowia", r"(przychodn|szpital|klinik|pogotow|medyczn|zdrowi|apteka|nzoz|lecznic|stacja dializ|szpz)"),
    ("pomoc_spoleczna", r"(dom pomocy|\bdps\b|mops|mopr|pomocy społ|pomocy rodzin|środowiskow|noclegown|ośrodek wsparcia)"),
    ("sluzby_ratownicze", r"(straż|straz|\bosp\b|\bpsp\b|policj|komisariat|komend|wopr|ratownict|jednostka ratown)"),
    ("transport", r"(dworzec|dworca|lotnisk|port lotn|pętl|petl|przystan|\bpkp\b|\bmpk\b|zajezdni|\bskm\b|stacja|metro|marina|przystań)"),
    ("sport_rekreacja", r"(basen|pływaln|plywaln|hala|stadion|sport|kąpielis|kapielis|lodowisk|aquapark|orlik|boisk|park|siłown|\bmosir\b|\bosir\b|rekreac|plaż)"),
    ("kultura", r"(muzeum|teatr|bibliotek|kultur|kino|filharm|opera|galeria sztuki|\bdk\b|ośrodek kult|centrum kult)"),
    ("obiekt_sakralny", r"(kości|kosci|parafi|bazylik|sanktuar|klasztor|katedr|zakrysti|cerkiew)"),
    ("urzad_administracja", r"(urząd|urzad|starostw|sąd|sad okr|prokurat|\bzus\b|skarbow|ratusz|delegatur|magistrat|wojewódz|marszałk|izba|gmina\b)"),
    ("handel_uslugi", r"(centrum handl|galeri|sklep|market|hotel|bank|poczt|restaur|\bbar\b|pawilon|biedronk|lidl|kaufland|auchan|carrefour|stacja paliw|orlen)"),
    ("budynek_mieszkalny", r"(wspólnota|wspolnota|spółdzielni|spoldzielni|osiedl)"),
    ("zaklad_pracy", r"(sp\. z o\.o|s\.a\.|zakład|zaklad|przedsiębior|wodociąg|mpwik|ciepłown|elektrown|fabryk|gddkia|pgnig)"),
    ("przestrzen_publiczna", r"(deptak|skwer|plac\b|rynek|bulwar|postument|wolnostoj|skrzyżowan|ulica)"),
]


def typ_obiektu(*teksty) -> str:
    t = bez_ogonkow(" ".join(tekst(x) for x in teksty).lower())
    for typ, wz in _TYP_OBIEKTU:
        if re.search(bez_ogonkow(wz), t):
            return "inny" if typ == "pojazd" else typ
    return "inny"


def wewnatrz(*teksty) -> str:
    t = " ".join(tekst(x) for x in teksty).lower()
    if re.search(r"na zewnątrz|zewnętrz|elewacj|ścian[aie] budynku|na budynku|kapsu|postument|wolnostoj|przystan|pętl|przy wejściu do budynku od zewn|na słupie|na murze|wiata", t):
        return "nie"
    if re.search(r"wewnątrz|wewnatrz|\bhol|holu|korytarz|portier|recepcj|pomieszcz|dyżurk|parter|piętr|sekretaria|kancelari|szatni|w budynku|biuro|kasa|zakrysti|furta|poczekaln|lobby", t):
        return "tak"
    return "nieznane"


def typ_montazu(*teksty) -> str:
    t = " ".join(tekst(x) for x in teksty).lower()
    if re.search(r"w pojeździe|w pojezdzie|radiowóz|radiowoz|na wyposażeniu radiow|na wyposażeniu taboru|w autobusach|w tramwajach|\bmobilny\b", t):
        return "pojazd"
    if re.search(r"wolnostoj|postument|słup|slup|stojak", t):
        return "wolnostojacy"
    if re.search(r"elewacj|ścian[aie] budynku|na budynku|na zewnętrznej ścian|zewnątrz budynku", t):
        return "elewacja"
    if wewnatrz(t) == "tak":
        return "wewnatrz_budynku"
    return "nieznany"


def zabezpieczenie(*teksty) -> str:
    t = " ".join(tekst(x) for x in teksty).lower()
    if re.search(r"na klucz|zamknięt|zamkniet", t):
        return "zamkniete_na_klucz"
    if re.search(r"\bkod\b|szyfr", t):
        return "szafka_z_kodem"
    if re.search(r"alarm|powiadomi|czujnik", t):
        return "szafka_z_alarmem"
    if re.search(r"ochron|portier|recepcj|dyżurk|dyzurk|sekretaria|kancelari|na wyposażeniu|na wysposażeniu|ratownik|kierowc|motorni|personel|informacj|kasa\b|biuro|punkt info|furta", t):
        return "u_personelu"
    return "nieznane"


def dysponent_typ(nazwa: str) -> str:
    t = bez_ogonkow(tekst(nazwa).lower())
    if not t:
        return "nieznany"
    reguly = [
        ("jst", r"^(urzad (miasta|miejski|gminy)|gmina|miasto|starostwo|urzad marsz)"),
        ("administracja_rzadowa", r"(wojewod|komend|policj|panstwowa straz|\bpsp\b|sad |prokurat|urzad skarbow|izba administracji|\bzus\b|gddkia|urzad wojewodzki)"),
        ("podmiot_leczniczy", r"(szpital|przychodn|pogotow|klinik|nzoz|spzoz|centrum medyczn|osrodek medyczn)"),
        ("uczelnia", r"(uniwersyt|politechn|akademi|uczelni)"),
        ("spolka_skarbu_panstwa", r"(\bpkp\b|poczta polska|polskie koleje|\bpge\b|orlen|lotos|pgnig|port lotniczy)"),
        ("ngo", r"(fundacj|stowarzysz|ochotnicza straz|\bosp\b|wopr|pck)"),
        ("wspolnota_spoldzielnia", r"(wspolnota|spoldzielni)"),
        ("kosciol_zwiazek_wyznaniowy", r"(parafi|bazylik|sanktuar|klasztor|kosciol|zakon)"),
        ("jednostka_jst", r"(szkol|przedszkol|zespol szkol|liceum|dom pomocy|mops|mopr|miejski|miejsk|gminn|zarzad (drog|infrastruktury|zieleni)|osrodek sportu|\bmosir\b|\bosir\b|biblioteka|dom kultury|centrum kultury|straz miejska|\bmpk\b|\bzdm\b|\bzim\b)"),
        ("firma", r"(sp\. ?z o\.? ?o|s\.a\.|sp\. ?j\.|sp\. ?k\.|spolka|\bsklep|hotel|bank)"),
    ]
    for typ, wz in reguly:
        if re.search(wz, t):
            return typ
    return "inny"
