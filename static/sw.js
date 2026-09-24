// Service worker di OdG: un piccolo programma che il telefono tiene installato
// insieme all'app e che si mette "in mezzo" tra l'app e la rete.
//
// Regole (pensate per non mostrare mai versioni vecchie quando c'è la rete):
// - PAGINE: prima si chiede alla rete; se risponde, se ne salva una copia.
//   Senza rete si mostra l'ultima copia salvata di quella pagina, oppure la
//   pagina "Sei offline".
// - FILE (stili, JavaScript, icone): hanno nell'indirizzo il numero di
//   versione (?v=...), quindi una copia salvata è sempre quella giusta: si
//   usano dalla memoria, e sono istantanei. I file senza versione (i font,
//   richiamati dal foglio di stile) si chiedono prima alla rete.
// - AZIONI e DATI (/api/...), link di accesso, calendario: sempre e solo dalla
//   rete, mai da copie salvate.

const VERSIONE = "odg-1";   // cambiandola, le copie salvate vengono buttate
const CACHE_FILE = `${VERSIONE}-file`;
const CACHE_PAGINE = `${VERSIONE}-pagine`;
const MAX_PAGINE = 30;      // quante pagine visitate tenere per l'uso senza rete

self.addEventListener("install", evento => {
  evento.waitUntil(caches.open(CACHE_PAGINE).then(c => c.add("/offline")));
  self.skipWaiting();         // la versione nuova entra subito in funzione
});

self.addEventListener("activate", evento => {
  evento.waitUntil((async () => {
    for (const nome of await caches.keys()) {
      if (![CACHE_FILE, CACHE_PAGINE].includes(nome)) await caches.delete(nome);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", evento => {
  const richiesta = evento.request;
  const url = new URL(richiesta.url);
  if (richiesta.method !== "GET" || url.origin !== self.location.origin) return;
  if (/^\/(api|entra|i)\//.test(url.pathname) || url.pathname.endsWith(".ics") || url.pathname === "/sw.js") return;

  if (url.pathname.startsWith("/static/") && url.searchParams.has("v")) {
    evento.respondWith(daMemoriaOppureRete(richiesta));       // file con numero di versione
  } else if (url.pathname.startsWith("/static/")) {
    evento.respondWith(daReteOppureMemoria(richiesta, CACHE_FILE));   // senza versione (es. i font)
  } else if (richiesta.mode === "navigate") {
    evento.respondWith(pagina(richiesta));
  }
});

async function daReteOppureMemoria(richiesta, nomeCache) {
  const cache = await caches.open(nomeCache);
  try {
    const risposta = await fetch(richiesta);
    if (risposta.ok) cache.put(richiesta, risposta.clone());
    return risposta;
  } catch (e) {
    return (await cache.match(richiesta)) || Response.error();
  }
}

async function daMemoriaOppureRete(richiesta) {
  const cache = await caches.open(CACHE_FILE);
  const salvata = await cache.match(richiesta);
  if (salvata) return salvata;
  const risposta = await fetch(richiesta);
  if (risposta.ok) cache.put(richiesta, risposta.clone());
  return risposta;
}

async function pagina(richiesta) {
  const cache = await caches.open(CACHE_PAGINE);
  try {
    const risposta = await fetch(richiesta);
    if (risposta.ok && risposta.type === "basic") {
      await cache.put(richiesta, risposta.clone());
      potaPagine(cache);
    }
    return risposta;
  } catch (e) {
    return (await cache.match(richiesta)) || (await cache.match("/offline"));
  }
}

// ------------------------------------------------------------ notifiche

// Arriva una notifica (dal server, attraverso Google/Apple/Mozilla): la mostro
self.addEventListener("push", evento => {
  let dati = { titolo: "OdG", corpo: "", url: "/" };
  try { dati = { ...dati, ...evento.data.json() }; } catch (e) { /* messaggio non in JSON: valori di base */ }
  evento.waitUntil(self.registration.showNotification(dati.titolo, {
    body: dati.corpo,
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    data: { url: dati.url },
  }));
});

// Tocco sulla notifica: apre la pagina indicata (o la porta davanti se è già aperta)
self.addEventListener("notificationclick", evento => {
  evento.notification.close();
  const url = evento.notification.data?.url || "/";
  evento.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(finestre => {
    const aperta = finestre.find(f => new URL(f.url).pathname === url);
    return aperta ? aperta.focus() : self.clients.openWindow(url);
  }));
});

/** Tiene solo le pagine visitate più di recente (la pagina offline resta sempre). */
async function potaPagine(cache) {
  const chiavi = (await cache.keys()).filter(r => new URL(r.url).pathname !== "/offline");
  for (const vecchia of chiavi.slice(0, Math.max(chiavi.length - MAX_PAGINE, 0))) await cache.delete(vecchia);
}
