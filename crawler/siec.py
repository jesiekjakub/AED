"""Pobieranie plików ze źródeł z lokalną kopią (dane_surowe/). Tryb offline używa ostatniej kopii."""
import os
import time
import urllib.request
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent / "dane_surowe"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
OFFLINE = os.environ.get("AED_OFFLINE") == "1"


ODRZUCONE = (b"Request Rejected", b"The requested URL was rejected", b"Access Denied</title>")
ZABLOKOWANE: set[str] = set()   # adresy, które odmówiły automatycznego pobrania (do raportu)


def pobierz(url: str, nazwa: str, *, metoda: str = "GET", dane: bytes | None = None,
            naglowki: dict | None = None, timeout: int = 60, kopia_zapasowa: Path | None = None) -> Path:
    """Zapisuje odpowiedź do dane_surowe/<nazwa> i zwraca ścieżkę.

    Przy błędzie sieci lub odmowie serwera używa ostatniej kopii albo kopii zapasowej (pobranej ręcznie).
    Nie próbujemy obchodzić zabezpieczeń serwisów – odmowa jest odnotowywana w raporcie."""
    KATALOG.mkdir(exist_ok=True)
    cel = KATALOG / nazwa
    cel.parent.mkdir(parents=True, exist_ok=True)
    if OFFLINE and cel.exists():
        return cel
    req = urllib.request.Request(url, data=dane, method=metoda, headers={"User-Agent": UA, **(naglowki or {})})
    for proba in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                tresc = r.read()
            if any(x in tresc[:2000] for x in ODRZUCONE):
                ZABLOKOWANE.add(url)
                blad = RuntimeError("serwer odrzucił automatyczne pobranie")
                break
            tmp = cel.with_suffix(cel.suffix + ".tmp")
            tmp.write_bytes(tresc)
            tmp.replace(cel)
            return cel
        except Exception as e:  # noqa: BLE001
            blad = e
            time.sleep(2 * (proba + 1))
    if cel.exists():
        print(f"  ! {url}: {blad} – używam ostatniej kopii {cel.name}")
        return cel
    if kopia_zapasowa and kopia_zapasowa.exists():
        print(f"  ! {url}: {blad} – używam kopii pobranej ręcznie ({kopia_zapasowa.name})")
        return kopia_zapasowa
    raise RuntimeError(f"Nie udało się pobrać {url}: {blad}")
