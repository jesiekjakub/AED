/**
 * „AED na ratunek” – prosty formularz dla małych dysponentów (gmin): dodaj AED po kolei → pobierz CSV zgodny ze wzorcem.
 * Działa w całości w przeglądarce (nic nie jest wysyłane). Pola i słowniki pochodzą z tableschema_aed.json.
 */
import { isPlatformBrowser, NgFor, NgIf } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { AfterViewInit, Component, ElementRef, Inject, OnDestroy, OnInit, PLATFORM_ID, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

const ETYKIETY: Record<string, string> = {
  aktywny: 'aktywny', tymczasowo_niedostepny: 'tymczasowo niedostępny', wycofany: 'wycofany',
  tak: 'tak', nie: 'nie', nieznane: 'nie wiem',
  publiczny: 'publiczny – każdy może skorzystać', dla_klientow_pracownikow: 'dla osób w obiekcie', prywatny: 'prywatny',
  brak: 'bez szafki', szafka_otwarta: 'szafka bez zamka', szafka_z_alarmem: 'szafka z alarmem', szafka_z_kodem: 'szafka na kod',
  zamkniete_na_klucz: 'zamknięty na klucz', u_personelu: 'u personelu (ochrona, recepcja)',
  deklaracja_dysponenta: 'deklaracja dysponenta', kontrola_na_miejscu: 'sprawdzone na miejscu', zgloszenie_spoleczne: 'zgłoszenie mieszkańca',
};

@Component({
  selector: 'app-aed-formularz',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule],
  template: `
  <form class="aed-form" (submit)="$event.preventDefault(); dodaj()" aria-describedby="aed-form-opis">
    <p id="aed-form-opis" class="form-text">Pola oznaczone * są wymagane. Współrzędne: kliknij miejsce na mapie albo użyj „Moja lokalizacja”, stojąc przy urządzeniu.</p>
    <div class="row g-2">
      <div class="col-md-6"><label class="form-label" for="f-obiekt">Nazwa obiektu *</label>
        <input id="f-obiekt" class="form-control" name="nazwa_obiektu" [(ngModel)]="r.nazwa_obiektu" required /></div>
      <div class="col-md-6"><label class="form-label" for="f-dysp">Dysponent urządzenia (właściciel/zarządca) *</label>
        <input id="f-dysp" class="form-control" name="dysponent_nazwa" [(ngModel)]="r.dysponent_nazwa" required /></div>
      <div class="col-md-4"><label class="form-label" for="f-msc">Miejscowość *</label>
        <input id="f-msc" class="form-control" name="miejscowosc" [(ngModel)]="r.miejscowosc" required /></div>
      <div class="col-md-4"><label class="form-label" for="f-ul">Ulica (z cechą, np. ul. Szkolna)</label>
        <input id="f-ul" class="form-control" name="ulica" [(ngModel)]="r.ulica" /></div>
      <div class="col-md-2"><label class="form-label" for="f-nr">Nr budynku *</label>
        <input id="f-nr" class="form-control" name="nr_budynku" [(ngModel)]="r.nr_budynku" required /></div>
      <div class="col-md-2"><label class="form-label" for="f-kod">Kod pocztowy</label>
        <input id="f-kod" class="form-control" name="kod_pocztowy" [(ngModel)]="r.kod_pocztowy" pattern="\\d{2}-\\d{3}" placeholder="00-000" /></div>
      <div class="col-12"><label class="form-label" for="f-opis">Gdzie dokładnie jest AED? *</label>
        <input id="f-opis" class="form-control" name="opis_lokalizacji" [(ngModel)]="r.opis_lokalizacji" required placeholder="np. na elewacji przy wejściu głównym" /></div>
      <div class="col-md-4" *ngFor="let pole of listy">
        <label class="form-label" [for]="'f-' + pole.nazwa">{{ pole.etykieta }} *</label>
        <select class="form-select" [id]="'f-' + pole.nazwa" [name]="pole.nazwa" [(ngModel)]="r[pole.nazwa]" required>
          <option *ngFor="let w of slownik(pole.nazwa)" [value]="w">{{ etykieta(w) }}</option>
        </select></div>
      <div class="col-md-4"><label class="form-label" for="f-godz">Godziny dostępności *</label>
        <input id="f-godz" class="form-control" name="godziny_dostepnosci" [(ngModel)]="r.godziny_dostepnosci" required placeholder="24/7 lub Mo-Fr 08:00-16:00" />
        <div class="mt-1"><button type="button" class="btn btn-sm btn-outline-primary me-1" (click)="r.godziny_dostepnosci = '24/7'">24/7</button>
        <button type="button" class="btn btn-sm btn-outline-primary" (click)="r.godziny_dostepnosci = 'Mo-Fr 08:00-16:00'">Pn–Pt 8–16</button></div></div>
      <div class="col-md-4"><label class="form-label" for="f-instr">Instrukcja dostępu (gdy zamknięty)</label>
        <input id="f-instr" class="form-control" name="instrukcja_dostepu" [(ngModel)]="r.instrukcja_dostepu" placeholder="np. kod podaje dyspozytor 112" /></div>
      <div class="col-md-4"><label class="form-label" for="f-data">Data sprawdzenia urządzenia *</label>
        <input id="f-data" class="form-control" type="date" name="data_weryfikacji" [(ngModel)]="r.data_weryfikacji" required /></div>
    </div>
    <div class="aed-form-mapa-pasek">
      <button type="button" class="btn btn-outline-primary" (click)="mojaLokalizacja()">Moja lokalizacja</button>
      <span role="status" aria-live="polite">{{ r.szerokosc_geograficzna ? 'Współrzędne: ' + r.szerokosc_geograficzna + ', ' + r.dlugosc_geograficzna : 'Kliknij na mapie miejsce urządzenia.' }}</span>
    </div>
    <div #mapa class="aed-form-mapa" role="application" aria-label="Mapa do wskazania lokalizacji AED – kliknij, aby ustawić punkt"></div>
    <p class="text-danger fw-bold" role="alert" *ngIf="blad">{{ blad }}</p>
    <button type="submit" class="btn btn-primary">Dodaj AED do listy</button>
  </form>

  <div *ngIf="lista.length" class="mt-3">
    <h4 class="h6">Twoja lista: {{ lista.length }} AED</h4>
    <ul class="aed-form-lista">
      <li *ngFor="let a of lista; let i = index">{{ a.id_aed }} – {{ a.nazwa_obiektu }}, {{ a.ulica }} {{ a.nr_budynku }}, {{ a.miejscowosc }} ({{ etykieta(a.zabezpieczenie) }})
        <button type="button" class="btn btn-link btn-sm" (click)="usun(i)" [attr.aria-label]="'Usuń ' + a.nazwa_obiektu">usuń</button></li>
    </ul>
    <button type="button" class="btn btn-success" (click)="pobierz()">Pobierz CSV (zgodny ze wzorcem)</button>
    <p class="form-text">Wgraj plik w panelu dostawcy dane.gov.pl i zaznacz „Zasób zawiera wykaz AED” – albo umieść go na stronie gminy i podaj link.</p>
  </div>`,
  styles: [`
    .aed-form { background:#f5f7fa; padding:1rem; border-radius:6px; }
    .aed-form .form-control, .aed-form .form-select { min-height:44px; }
    .aed-form-mapa { height:300px; border:1px solid #c9c9c9; border-radius:6px; margin:.5rem 0 1rem; }
    .aed-form-mapa-pasek { display:flex; gap:1rem; align-items:center; margin-top:1rem; }
    .aed-form-lista { padding-left:1.2rem; }
  `],
})
export class AedFormularzComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('mapa') mapaEl: ElementRef<HTMLDivElement>;
  readonly listy = [
    { nazwa: 'wewnatrz_budynku', etykieta: 'Wewnątrz budynku?' },
    { nazwa: 'dostep', etykieta: 'Kto może skorzystać' },
    { nazwa: 'zabezpieczenie', etykieta: 'Zabezpieczenie' },
    { nazwa: 'status', etykieta: 'Status' },
    { nazwa: 'sposob_weryfikacji', etykieta: 'Jak potwierdzono' },
  ];
  r: Record<string, any> = {};
  lista: Record<string, any>[] = [];
  blad = '';
  private pola: any[] = [];
  private L: any;
  private map: any;
  private marker: any;
  private przegladarka: boolean;

  constructor(private http: HttpClient, @Inject(PLATFORM_ID) platformId: object) {
    this.przegladarka = isPlatformBrowser(platformId);
  }

  ngOnInit(): void {
    this.nowy();
    this.http.get<any>('assets/aed/tableschema_aed.json').subscribe((s) => (this.pola = s.fields.filter((f: any) => f.poziom !== 'A')));
  }

  async ngAfterViewInit(): Promise<void> {
    if (!this.przegladarka) {
      return;
    }
    const mod: any = await import('leaflet');
    this.L = mod.default || mod;
    this.map = this.L.map(this.mapaEl.nativeElement, { center: [52.1, 19.4], zoom: 6 });
    this.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(this.map);
    this.map.on('click', (e: any) => this.ustaw(e.latlng.lat, e.latlng.lng));
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

  slownik(pole: string): string[] {
    return this.pola.find((p) => p.name === pole)?.constraints?.enum || [];
  }

  etykieta(w: string): string {
    return ETYKIETY[w] || w;
  }

  mojaLokalizacja(): void {
    navigator.geolocation?.getCurrentPosition((p) => this.ustaw(p.coords.latitude, p.coords.longitude, 18));
  }

  dodaj(): void {
    const brak = ['nazwa_obiektu', 'dysponent_nazwa', 'miejscowosc', 'nr_budynku', 'opis_lokalizacji', 'godziny_dostepnosci', 'data_weryfikacji'].filter((k) => !String(this.r[k] || '').trim());
    if (brak.length || !this.r.szerokosc_geograficzna) {
      this.blad = brak.length ? 'Uzupełnij pola wymagane (*).' : 'Wskaż położenie urządzenia na mapie.';
      return;
    }
    this.blad = '';
    this.r.id_aed = `AED-${String(this.lista.length + 1).padStart(3, '0')}`;
    this.r.zrodlo_wspolrzednych = 'mapa_dysponenta';
    this.r.dostepny_24_7 = this.r.godziny_dostepnosci === '24/7' ? 'tak' : 'nie';
    this.lista.push({ ...this.r });
    const zachowaj = { dysponent_nazwa: this.r.dysponent_nazwa, miejscowosc: this.r.miejscowosc, data_weryfikacji: this.r.data_weryfikacji };
    this.nowy();
    Object.assign(this.r, zachowaj);
    this.marker?.remove();
    this.marker = null;
  }

  usun(i: number): void {
    this.lista.splice(i, 1);
  }

  pobierz(): void {
    const kol = this.pola.map((p) => p.name);
    const esc = (v: any) => {
      const s = v === undefined || v === null ? '' : String(v);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const csv = [kol.join(','), ...this.lista.map((a) => kol.map((k) => esc(a[k])).join(','))].join('\r\n');
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'wykaz_aed.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  private ustaw(lat: number, lon: number, zoom?: number): void {
    this.r.szerokosc_geograficzna = lat.toFixed(6);
    this.r.dlugosc_geograficzna = lon.toFixed(6);
    if (this.map) {
      this.marker?.remove();
      this.marker = this.L.circleMarker([lat, lon], { radius: 9, color: '#fff', weight: 2, fillColor: '#0052a5', fillOpacity: 1 }).addTo(this.map);
      if (zoom) {
        this.map.setView([lat, lon], zoom);
      }
    }
  }

  private nowy(): void {
    this.r = {
      status: 'aktywny', wewnatrz_budynku: 'nie', dostep: 'publiczny', zabezpieczenie: 'szafka_z_alarmem',
      sposob_weryfikacji: 'kontrola_na_miejscu', data_weryfikacji: new Date().toISOString().slice(0, 10), mobilny: 'nie',
    };
  }
}
