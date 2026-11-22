/**
 * „AED na ratunek” – rozszerzenie portalu dane.gov.pl (HackNation 2026, Misja AED).
 * Strona /pl/aed: mapa AED (główny widok) z filtrami, listą i panelem szczegółów; zakładki: źródła, dla dysponenta (walidator), jakość.
 * Kod dodany przez zespół; pozostała część portalu bez zmian (licencja GPL-3.0 jak całość projektu).
 */
import { isPlatformBrowser, NgClass, NgFor, NgIf } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { AfterViewInit, Component, ElementRef, Inject, OnDestroy, OnInit, PLATFORM_ID, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { LocalizeRouterPipe } from '@gilsdav/ngx-translate-router';
import { forkJoin } from 'rxjs';

import { AedFormularzComponent } from './aed-formularz.component';
import { ResourceTableNoFiltersComponent } from '@app/shared/resource-table-no-filters/resource-table-no-filters.component';

export interface Aed {
  id_aed: string;
  nazwa_obiektu: string;
  typ_obiektu: string;
  miejscowosc: string;
  ulica: string;
  nr_budynku: string;
  kod_pocztowy: string;
  wojewodztwo: string;
  szerokosc_geograficzna: number | '';
  dlugosc_geograficzna: number | '';
  zrodlo_wspolrzednych: string;
  wewnatrz_budynku: string;
  opis_lokalizacji: string;
  dostep: string;
  godziny_dostepnosci: string;
  godziny_opis: string;
  dostepny_24_7: string;
  zabezpieczenie: string;
  instrukcja_dostepu: string;
  typ_montazu: string;
  dysponent_nazwa: string;
  zrodlo_id: string;
  dostawca_danych: string;
  zrodlo_url: string;
  data_stanu_zrodla: string;
  flagi_jakosci: string;
  kompletnosc_proc: number;
  _odl?: number;
}

interface ZbiorPortalu {
  id: string;
  tytul: string;
  formaty: string[];
  licencja: string;
  zmodyfikowano: string;
}

interface WynikWalidacji {
  poziom: 'blad' | 'uwaga';
  tekst: string;
}

type Zakladka = 'wykaz' | 'zrodla' | 'dysponent' | 'jakosc';

export const ZABEZPIECZENIE: Record<string, string> = {
  brak: 'Bez szafki – od razu do wzięcia',
  szafka_otwarta: 'Szafka bez zamka',
  szafka_z_alarmem: 'Szafka z alarmem – otwórz śmiało',
  szafka_z_kodem: 'Szafka na kod (poda go 112)',
  zamkniete_na_klucz: 'Zamknięty na klucz',
  u_personelu: 'U personelu – poproś obsługę',
  nieznane: 'Brak informacji o zabezpieczeniu',
};

const SWOBODNY = ['brak', 'szafka_otwarta', 'szafka_z_alarmem'];

@Component({
  selector: 'app-aed',
  templateUrl: './aed.component.html',
  styleUrls: ['./aed.component.scss'],
  standalone: true,
  imports: [NgIf, NgFor, NgClass, FormsModule, RouterLink, LocalizeRouterPipe, AedFormularzComponent, ResourceTableNoFiltersComponent],
})
export class AedComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('mapa') mapaEl: ElementRef<HTMLDivElement>;
  @ViewChild('szczegoly') szczegolyEl: ElementRef<HTMLElement>;

  readonly assets = 'assets/aed/';
  readonly zabezpieczenie = ZABEZPIECZENIE;

  aed: Aed[] = [];
  widoczne: Aed[] = [];
  wybrany: Aed | null = null;
  limitListy = 30;
  raport: any;
  rejestr: any[] = [];
  zrodlaRaportu: any[] = [];
  pokrycie: { pole: string; poziom: string; srednio: number }[] = [];
  statusy: { kod: string; opis: string; liczba: number }[] = [];
  zbioryPortalu: ZbiorPortalu[] = [];
  bladPortalu = false;
  ladowanie = true;

  // filtry
  fraza = '';
  wojewodztwo = '';
  tylko247 = false;
  tylkoSwobodny = false;
  pokazOsm = false;
  sciezka: 'formularz' | 'plik' | 'system' = 'formularz';
  wojewodztwa: string[] = [];

  // widok mobilny i zakładki
  widokMobilny: 'mapa' | 'lista' = 'mapa';
  zakladka: Zakladka = 'wykaz';
  wykaz: any = null; // AggregatedAEDInfo z API portalu (/aggregated-aed-info) – jak /dga-aggregated dla DGA
  readonly zakladki: { id: Zakladka; nazwa: string }[] = [
    { id: 'wykaz', nazwa: 'Wykaz zbiorczy AED (tabela)' },
    { id: 'zrodla', nazwa: 'Źródła danych' },
    { id: 'dysponent', nazwa: 'Dla dysponenta' },
    { id: 'jakosc', nazwa: 'Jakość danych' },
  ];

  pozycja: { lat: number; lon: number } | null = null;
  komunikatGeo = '';

  wynikiWalidacji: WynikWalidacji[] = [];
  podsumowanieWalidacji = '';
  private schemat: any;

  private L: any;
  private map: any;
  private klaster: any;
  private warstwaOsm: any;
  private przegladarka: boolean;

  constructor(
    private http: HttpClient,
    @Inject(PLATFORM_ID) platformId: object,
  ) {
    this.przegladarka = isPlatformBrowser(platformId);
  }

  ngOnInit(): void {
    forkJoin({
      aed: this.http.get<Aed[]>(this.assets + 'aed_app.json'),
      raport: this.http.get<any>(this.assets + 'raport_jakosci.json'),
      rejestr: this.http.get<any>(this.assets + 'rejestr_zrodel.json'),
      schemat: this.http.get<any>(this.assets + 'tableschema_aed.json'),
    }).subscribe(({ aed, raport, rejestr, schemat }) => {
      this.aed = aed;
      this.raport = raport;
      this.schemat = schemat;
      this.rejestr = rejestr.zrodla || [];
      this.zrodlaRaportu = (raport.zrodla || []).slice().sort((a: any, b: any) => b.liczba_rekordow - a.liczba_rekordow);
      this.wojewodztwa = [...new Set(aed.map((a) => a.wojewodztwo).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pl'));
      this.pokrycie = Object.entries(raport.pokrycie_pol_proc || {}).map(([pole, d]: [string, any]) => {
        const w = Object.entries(d).filter(([k]) => k !== 'poziom').map(([, v]) => v as number);
        return { pole, poziom: d.poziom, srednio: Math.round(w.reduce((s, v) => s + v, 0) / Math.max(w.length, 1)) };
      });
      const legenda = rejestr.legenda?.status_udostepniania || {};
      this.statusy = Object.keys(legenda).map((k) => ({
        kod: k,
        opis: legenda[k],
        liczba: this.rejestr.filter((r) => r.status_udostepniania === k).length,
      }));
      this.ladowanie = false;
      this.filtruj();
    });
    // MISJA AED: wykaz zbiorczy publikowany przez portal (zasób) – identyfikator z endpointu backendu, jak w punkcie DGA
    this.http.get<any>('/api/aggregated-aed-info').subscribe({
      next: (d) => (this.wykaz = d && d.resource_id ? d : null),
      error: () => (this.wykaz = null),
    });
    this.http.get<any>('/api/datasets', { params: { q: 'defibrylator', per_page: '50' } }).subscribe({
      next: (d) =>
        (this.zbioryPortalu = (d.data || [])
          .map((it: any) => ({
            id: it.id,
            tytul: (it.attributes.title || '').replace(/<[^>]+>/g, ''),
            formaty: it.attributes.formats || [],
            licencja: it.attributes.license_name || it.attributes.license_chosen || '',
            zmodyfikowano: (it.attributes.modified || '').slice(0, 10),
          }))
          .filter((z: ZbiorPortalu) => /defibr|AED/i.test(z.tytul))),
      error: () => (this.bladPortalu = true),
    });
  }

  async ngAfterViewInit(): Promise<void> {
    if (!this.przegladarka || !this.mapaEl) {
      return;
    }
    const mod: any = await import('leaflet');
    this.L = mod.default || mod;
    (window as any).L = this.L;
    await import('leaflet.markercluster');
    this.map = this.L.map(this.mapaEl.nativeElement, { center: [52.1, 19.4], zoom: 6, preferCanvas: true });
    this.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: 'Podkład mapy &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.map);
    this.klaster = this.L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 80, chunkedLoading: true });
    this.map.addLayer(this.klaster);
    this.rysujMape(true);
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

  // ---------------------------------------------------------------- filtry, lista, mapa
  filtruj(dopasuj = false): void {
    const f = this.fraza.trim().toLowerCase();
    let lista = this.aed.filter(
      (a) =>
        (!this.wojewodztwo || a.wojewodztwo === this.wojewodztwo) &&
        (!this.tylko247 || a.dostepny_24_7 === 'tak') &&
        (!this.tylkoSwobodny || SWOBODNY.includes(a.zabezpieczenie)) &&
        (!f || `${a.nazwa_obiektu} ${a.ulica} ${a.miejscowosc} ${a.opis_lokalizacji}`.toLowerCase().includes(f)),
    );
    if (this.pozycja) {
      lista = lista
        .map((a) => ({ ...a, _odl: a.szerokosc_geograficzna === '' ? Infinity : this.odleglosc(a) }))
        .sort((x, y) => x._odl - y._odl);
    }
    this.widoczne = lista;
    this.limitListy = 30;
    this.rysujMape(dopasuj);
  }

  wyczysc(): void {
    this.fraza = '';
    this.wojewodztwo = '';
    this.tylko247 = this.tylkoSwobodny = false;
    this.filtruj(true);
  }

  najblizszy(): void {
    if (!this.przegladarka || !navigator.geolocation) {
      this.komunikatGeo = 'Przeglądarka nie udostępnia lokalizacji. Wpisz miejscowość w wyszukiwarce.';
      return;
    }
    this.komunikatGeo = 'Ustalam Twoją lokalizację…';
    navigator.geolocation.getCurrentPosition(
      (p) => {
        this.pozycja = { lat: p.coords.latitude, lon: p.coords.longitude };
        this.filtruj();
        const n = this.widoczne[0];
        if (n && n._odl !== Infinity) {
          this.komunikatGeo = `Najbliższy AED: ${n.nazwa_obiektu} – ok. ${this.formatujOdl(n._odl)}. Dzwoń 112.`;
          this.wybierz(n);
        } else {
          this.komunikatGeo = 'Brak AED w bazie w Twojej okolicy. Dzwoń 112 – dyspozytor wskaże najbliższy.';
        }
      },
      () => (this.komunikatGeo = 'Nie udało się ustalić lokalizacji. Wpisz miejscowość lub dzwoń 112.'),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  wybierz(a: Aed): void {
    this.wybrany = a;
    if (this.map && a.szerokosc_geograficzna !== '') {
      this.map.setView([a.szerokosc_geograficzna, a.dlugosc_geograficzna], 17);
    }
    setTimeout(() => this.szczegolyEl?.nativeElement.focus());
  }

  zamknijSzczegoly(): void {
    this.wybrany = null;
  }

  przelaczOsm(): void {
    if (!this.map) {
      return;
    }
    if (this.pokazOsm && !this.warstwaOsm) {
      this.http.get<any>(this.assets + 'osm_aed_punkty.json').subscribe((d) => {
        this.warstwaOsm = this.L.layerGroup(
          d.punkty.map((p: number[]) =>
            this.L.circleMarker(p, { radius: 3, weight: 0, fillColor: '#6b6b6b', fillOpacity: 0.55, interactive: false }),
          ),
        );
        this.warstwaOsm.addTo(this.map);
        this.map.attributionControl.addAttribution('Punkty społecznościowe AED: &copy; współtwórcy OpenStreetMap (ODbL)');
        this.warstwaOsm.bringToBack?.();
      });
    } else if (this.warstwaOsm) {
      this.pokazOsm ? this.warstwaOsm.addTo(this.map) : this.map.removeLayer(this.warstwaOsm);
    }
  }

  ustawZakladke(z: Zakladka, ev?: KeyboardEvent): void {
    if (ev) {
      const i = this.zakladki.findIndex((t) => t.id === this.zakladka);
      const n = ev.key === 'ArrowRight' ? (i + 1) % this.zakladki.length : ev.key === 'ArrowLeft' ? (i + this.zakladki.length - 1) % this.zakladki.length : -1;
      if (n < 0) {
        return;
      }
      z = this.zakladki[n].id;
      setTimeout(() => document.getElementById('tab-' + z)?.focus());
    }
    this.zakladka = z;
  }

  adres(a: Aed): string {
    return [[a.ulica, a.nr_budynku].filter(Boolean).join(' '), a.miejscowosc].filter(Boolean).join(', ');
  }

  godziny(a: Aed): string {
    return a.dostepny_24_7 === 'tak' ? 'Dostępny 24/7' : a.godziny_dostepnosci || a.godziny_opis || 'Godziny: brak informacji';
  }

  swobodny(a: Aed): boolean {
    return SWOBODNY.includes(a.zabezpieczenie);
  }

  formatujOdl(m: number): string {
    return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
  }

  liczba(n: number | undefined): string {
    return (n ?? 0).toLocaleString('pl-PL');
  }

  trasa(a: Aed): string {
    const od = this.pozycja ? `${this.pozycja.lat},${this.pozycja.lon}` : '';
    return `https://www.openstreetmap.org/directions?route=${od};${a.szerokosc_geograficzna},${a.dlugosc_geograficzna}`;
  }

  get naMapie(): number {
    return this.aed.filter((a) => a.szerokosc_geograficzna !== '').length;
  }

  get calodobowe(): number {
    return this.aed.filter((a) => a.dostepny_24_7 === 'tak').length;
  }

  get swobodne(): number {
    return this.aed.filter((a) => this.swobodny(a)).length;
  }

  rejestrInfo(id: string): any {
    return this.rejestr.find((r) => r.id === id) || {};
  }

  private odleglosc(a: Aed): number {
    const rad = Math.PI / 180;
    const la = a.szerokosc_geograficzna as number;
    const lo = a.dlugosc_geograficzna as number;
    const x = Math.sin(((la - this.pozycja.lat) * rad) / 2) ** 2 +
      Math.cos(this.pozycja.lat * rad) * Math.cos(la * rad) * Math.sin(((lo - this.pozycja.lon) * rad) / 2) ** 2;
    return 2 * 6371000 * Math.asin(Math.sqrt(x));
  }

  private rysujMape(dopasuj = false): void {
    if (!this.map || !this.klaster) {
      return;
    }
    this.klaster.clearLayers();
    const markery = [];
    const punkty: [number, number][] = [];
    for (const a of this.widoczne) {
      if (a.szerokosc_geograficzna === '') {
        continue;
      }
      const ll: [number, number] = [a.szerokosc_geograficzna as number, a.dlugosc_geograficzna as number];
      punkty.push(ll);
      const m = this.L.circleMarker(ll, {
        radius: 9,
        weight: 2,
        color: '#ffffff',
        fillColor: a.dostepny_24_7 === 'tak' ? '#00703c' : '#0052a5',
        fillOpacity: 1,
      });
      m.on('click', () => this.wybierz(a));
      m.bindTooltip(this.esc(a.nazwa_obiektu));
      markery.push(m);
    }
    this.klaster.addLayers(markery);
    if (dopasuj && punkty.length) {
      this.map.fitBounds(punkty, { padding: [24, 24], maxZoom: 14 });
    }
  }

  private esc(s: string): string {
    return (s || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  }

  // ---------------------------------------------------------------- walidator pliku dysponenta (w przeglądarce)
  wczytajPlik(ev: Event): void {
    const plik = (ev.target as HTMLInputElement).files?.[0];
    if (!plik) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => this.waliduj(String(reader.result), plik.name);
    reader.readAsText(plik, 'utf-8');
  }

  private waliduj(tresc: string, nazwa: string): void {
    const wyniki: WynikWalidacji[] = [];
    const tekst = tresc.replace(/^﻿/, '');
    const pierwsza = tekst.split(/\r?\n/)[0] || '';
    const sep = [',', ';', '\t'].sort((a, b) => pierwsza.split(b).length - pierwsza.split(a).length)[0];
    if (sep !== ',') {
      wyniki.push({ poziom: 'uwaga', tekst: `Separator „${sep === '\t' ? 'tabulator' : sep}” – zalecany przecinek.` });
    }
    const wiersze = this.parsujCsv(tekst, sep).filter((w) => w.some((c) => c.trim()));
    const naglowki = (wiersze.shift() || []).map((h) => h.trim());
    const pola: any[] = this.schemat?.fields || [];
    const poPolu: Record<string, any> = Object.fromEntries(pola.map((p) => [p.name, p]));
    const wymagane = pola.filter((p) => p.poziom === 'W').map((p) => p.name);
    const brak = wymagane.filter((p) => !naglowki.includes(p));
    if (brak.length) {
      wyniki.push({ poziom: 'blad', tekst: `Brak wymaganych kolumn: ${brak.join(', ')}.` });
    }
    const obce = naglowki.filter((h) => !poPolu[h]);
    if (obce.length) {
      wyniki.push({ poziom: 'uwaga', tekst: `Kolumny spoza wzorca (zostaną pominięte): ${obce.join(', ')}.` });
    }
    const idki = new Set<string>();
    wiersze.forEach((w, i) => {
      const nr = i + 2;
      const rek: Record<string, string> = Object.fromEntries(naglowki.map((h, k) => [h, (w[k] || '').trim()]));
      for (const p of wymagane) {
        if (p in rek && ['', 'nieznane', 'nieznany'].includes(rek[p]) && !((p === 'ulica' || p === 'nr_budynku') && rek['mobilny'] === 'tak')) {
          wyniki.push({ poziom: 'uwaga', tekst: `Wiersz ${nr}: puste pole wymagane „${p}”.` });
        }
      }
      if (rek['id_aed']) {
        if (idki.has(rek['id_aed'])) {
          wyniki.push({ poziom: 'blad', tekst: `Wiersz ${nr}: zdublowany id_aed „${rek['id_aed']}”.` });
        }
        idki.add(rek['id_aed']);
      }
      for (const [k, v] of Object.entries(rek)) {
        const p = poPolu[k];
        if (!p || !v) {
          continue;
        }
        const c = p.constraints || {};
        if (c.enum && !c.enum.includes(v)) {
          wyniki.push({ poziom: 'blad', tekst: `Wiersz ${nr}: „${k}” = „${v}” spoza słownika (dozwolone: ${c.enum.join(', ')}).` });
        }
        if (c.pattern && !new RegExp(c.pattern).test(v)) {
          wyniki.push({ poziom: 'blad', tekst: `Wiersz ${nr}: „${k}” = „${v}” ma niepoprawny format.` });
        }
        if (p.type === 'number') {
          const x = Number(v);
          if (isNaN(x)) {
            wyniki.push({ poziom: 'blad', tekst: `Wiersz ${nr}: „${k}” = „${v}” nie jest liczbą (separator dziesiętny: kropka).` });
          } else if (c.minimum !== undefined && (x < c.minimum || x > c.maximum)) {
            wyniki.push({ poziom: 'blad', tekst: `Wiersz ${nr}: „${k}” = ${v} poza zakresem dla Polski.` });
          }
        }
        if (p.type === 'date' && !/^\d{4}-\d{2}-\d{2}$/.test(v)) {
          wyniki.push({ poziom: 'blad', tekst: `Wiersz ${nr}: „${k}” = „${v}” – oczekiwano daty RRRR-MM-DD.` });
        }
      }
      const lat = Number(rek['szerokosc_geograficzna']);
      const lon = Number(rek['dlugosc_geograficzna']);
      if (!isNaN(lat) && !isNaN(lon) && (lat < 49 || lat > 54.9) && lon >= 49 && lon <= 54.9) {
        wyniki.push({ poziom: 'blad', tekst: `Wiersz ${nr}: szerokość i długość geograficzna są zamienione miejscami.` });
      }
      if (rek['zabezpieczenie'] === 'zamkniete_na_klucz' && !rek['instrukcja_dostepu']) {
        wyniki.push({ poziom: 'uwaga', tekst: `Wiersz ${nr}: AED zamknięty na klucz bez instrukcji dostępu.` });
      }
    });
    const bledy = wyniki.filter((w) => w.poziom === 'blad').length;
    this.podsumowanieWalidacji =
      `Plik „${nazwa}”: ${wiersze.length} urządzeń, ${bledy} błędów, ${wyniki.length - bledy} uwag. ` +
      (bledy ? 'Popraw błędy przed publikacją.' : 'Plik zgodny ze wzorcem – można publikować w dane.gov.pl.');
    this.wynikiWalidacji = wyniki.slice(0, 200);
  }

  private parsujCsv(t: string, sep: string): string[][] {
    const wynik: string[][] = [];
    let wiersz: string[] = [];
    let pole = '';
    let q = false;
    for (let i = 0; i < t.length; i++) {
      const ch = t[i];
      if (q) {
        if (ch === '"' && t[i + 1] === '"') {
          pole += '"';
          i++;
        } else if (ch === '"') {
          q = false;
        } else {
          pole += ch;
        }
      } else if (ch === '"') {
        q = true;
      } else if (ch === sep) {
        wiersz.push(pole);
        pole = '';
      } else if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && t[i + 1] === '\n') {
          i++;
        }
        wiersz.push(pole);
        wynik.push(wiersz);
        wiersz = [];
        pole = '';
      } else {
        pole += ch;
      }
    }
    if (pole || wiersz.length) {
      wiersz.push(pole);
      wynik.push(wiersz);
    }
    return wynik;
  }
}
