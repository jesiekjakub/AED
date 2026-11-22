// Proxy dla demo na Renderze: przekazuje zapytania frontendu do produkcyjnego dane.gov.pl.
//
// Robi to samo co portal/proxy.aed.conf.json przy `ng serve --configuration aed`.
// Jest potrzebne, bo reguły rewrite strony statycznej na Renderze doklejają nagłówek
// X-Forwarded-Host, a dane.gov.pl odpowiada na niego przekierowaniem 301 na swoją domenę.
// To proxy wysyła zapytanie bez nagłówków przekazywania, więc API odpowiada normalnie.
//
// Bez zależności: tylko moduły wbudowane w Node.js. Przepuszcza wyłącznie odczyt (GET, HEAD).
import http from 'node:http';
import https from 'node:https';

const PORT = Number(process.env.PORT || 10000);

// Kolejność jak w portal/proxy.aed.conf.json: prefiks ścieżki -> adres docelowy.
const TARGETS = [
  ['/api/', 'https://api.dane.gov.pl/1.4/'],
  ['/media/', 'https://api.dane.gov.pl/media/'],
  ['/flags/', 'https://dane.gov.pl/flags/'],
  ['/cms/', 'https://cms.dane.gov.pl/'],
];

// Nagłówki, których nie wolno przenosić między połączeniami, oraz te, które zdradzają
// pośrednika (to one powodują przekierowanie 301 po stronie dane.gov.pl).
const DROPPED_REQUEST_HEADERS =
  /^(host|connection|keep-alive|transfer-encoding|upgrade|te|trailer|proxy-.*|forwarded|x-forwarded-.*|x-real-ip|true-client-ip|cf-.*|cdn-loop|rndr-.*|render-.*|x-render-.*|x-request-start|cookie|origin|referer)$/i;
const DROPPED_RESPONSE_HEADERS =
  /^(connection|keep-alive|transfer-encoding|upgrade|trailer|set-cookie|access-control-.*|strict-transport-security)$/i;

function filterHeaders(headers, dropped) {
  const out = {};
  for (const [name, value] of Object.entries(headers)) {
    if (value !== undefined && !dropped.test(name)) out[name] = value;
  }
  return out;
}

function sendText(res, status, text) {
  res.writeHead(status, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' });
  res.end(text);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');

  if (url.pathname === '/healthz') return sendText(res, 200, 'ok');

  const target = TARGETS.find(([prefix]) => url.pathname.startsWith(prefix));
  if (!target) return sendText(res, 404, 'Nieznana ścieżka. Obsługiwane: /api/, /media/, /flags/, /cms/.');

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.setHeader('allow', 'GET, HEAD');
    return sendText(res, 405, 'To demo udostępnia dane.gov.pl tylko do odczytu.');
  }

  const [prefix, base] = target;
  const destination = new URL(base + url.pathname.slice(prefix.length) + url.search);

  const upstream = https.request(
    destination,
    { method: req.method, headers: filterHeaders(req.headers, DROPPED_REQUEST_HEADERS), timeout: 30000 },
    (upstreamRes) => {
      res.writeHead(upstreamRes.statusCode, filterHeaders(upstreamRes.headers, DROPPED_RESPONSE_HEADERS));
      upstreamRes.pipe(res);
    },
  );
  upstream.on('timeout', () => upstream.destroy(new Error('przekroczono czas oczekiwania')));
  upstream.on('error', (error) => {
    console.error(`${req.method} ${url.pathname} -> ${destination.host}: ${error.message}`);
    if (!res.headersSent) sendText(res, 502, 'dane.gov.pl nie odpowiada.');
    else res.destroy();
  });
  res.on('close', () => upstream.destroy());
  upstream.end();
});

server.listen(PORT, '0.0.0.0', () => console.log(`Proxy dane.gov.pl nasłuchuje na porcie ${PORT}`));
