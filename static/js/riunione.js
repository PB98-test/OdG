// Pagina di una riunione, parte comune: stato, aggiornamenti automatici,
// ordine del giorno (prima della riunione), proposte, Varie, condivisione.
// La modalità "durante" sta in riunione_corso.js, il verbale in riunione_verbale.js.
//
// DATI arriva dal server (vedi odg.stato) e viene sostituito a ogni aggiornamento.

let espansi = new Set();          // punti aperti (decisioni e compiti) durante la riunione
let puntoInModifica = null;       // punto in modifica diretta (uno alla volta)
let ricevutoIl = Date.now();      // quando sono arrivati i dati: serve per far correre i timer
let ridisegnoInSospeso = false;   // aggiornamento arrivato mentre qualcuno scriveva

const STATO = () => DATI.riunione.stato;
const PUO = () => DATI.puo;
const ODG_MODIFICABILE = () => PUO().odg;

// ------------------------------------------------------------ disegno

function disegna() {
  disegnaAzioniAlto();
  disegnaPresenti();                  // riunione_corso.js (dall'inizio in poi)
  if (STATO() === "conclusa") {
    disegnaVerbale();                 // riunione_verbale.js
  } else {
    disegnaBarra();                   // riunione_corso.js ("Inizia", tempi, "Concludi")
    disegnaCompitiPrecedenti();       // riunione_corso.js
    disegnaPunti();
    disegnaFormPunto();
    disegnaProposte();
    disegnaProssima();
  }
}

/** Salva la data e Condividi (prima), condivisione del verbale (dopo). */
function disegnaAzioniAlto() {
  const box = document.getElementById("azioni-alto");
  if (STATO() === "conclusa") {
    box.innerHTML = `<div class="azioni">
      <button class="btn btn-giallo" onclick="condividiVerbale()">${icona("share")} Condividi</button>
      <button class="btn btn-contorno" onclick="copiaVerbale()">${icona("copy")} Copia testo</button>
    </div>`;
  } else if (!DATI.passata || STATO() === "in_corso") {
    box.innerHTML = `<div class="azioni">
      <button class="btn btn-giallo" onclick="document.getElementById('foglio-data').showModal()">${icona("calendar-plus")} Salva la data</button>
      <button class="btn btn-contorno" onclick="condividi()">${icona("share")} Condividi</button>
    </div>`;
  } else {
    box.innerHTML = "";
  }
}

function disegnaPunti() {
  const elenco = document.getElementById("punti");
  const punti = DATI.punti;
  const totale = punti.reduce((somma, p) => somma + p.minuti, 0);
  document.getElementById("totale-minuti").textContent = totale ? `${totale} min previsti` : "";
  const inCorso = STATO() === "in_corso";
  elenco.innerHTML = punti.map((p, i) => {
    if (p.id === puntoInModifica) return rigaInModifica(p);
    return inCorso ? rigaInCorso(p, i) : rigaPrima(p, i);   // rigaInCorso: riunione_corso.js
  }).join("");
  if (inCorso) aggiornaTempi();   // riempie subito i tempi, senza aspettare il secondo dopo
}

/** Firme sotto il titolo: "proposto da", "riportato dal". */
function firme(p) {
  let html = "";
  if (p.proposto_da_nome) {
    html += `<span class="firma" style="color:${esc(p.proposto_da_colore)}">${pallino(p.proposto_da_colore)}proposto da ${esc(p.proposto_da_nome)}</span>`;
  }
  if (p.riportato_dal) {
    html += `<span class="firma riportato">${icona("arrow-back-up")} riportato dal ${dataBreve(p.riportato_dal)}</span>`;
  }
  return html;
}

function rigaPrima(p, i) {
  const cmd = comandiPunto(p, i);
  return `<li class="punto${cmd ? " gestibile" : ""}${p.fisso ? " varie" : ""}">
    <span class="num">${i + 1}</span>
    <span class="titolo">${esc(p.titolo)}${firme(p)}</span>
    <span class="pillola">${p.minuti} min</span>
    ${cmd}
    ${p.fisso ? vociVarie() : ""}
  </li>`;
}

/** Comandi su un punto: modifica diretta (permesso "odg") o proposte (tutti). */
function comandiPunto(p, i) {
  if (ODG_MODIFICABILE()) {
    if (p.fisso) {   // delle Varie si cambiano solo i minuti
      return `<span class="comandi-punto">
        <button class="btn-icona" aria-label="Modifica i minuti" onclick="modificaPunto(${p.id})">${icona("pencil")}</button>
      </span>`;
    }
    const ultimoNonFisso = !DATI.punti[i + 1] || DATI.punti[i + 1].fisso;
    return `<span class="comandi-punto">
      <button class="btn-icona" aria-label="Sposta su" onclick="spostaPunto(${p.id}, -1)" ${i === 0 ? "disabled" : ""}>${icona("arrow-up")}</button>
      <button class="btn-icona" aria-label="Sposta giù" onclick="spostaPunto(${p.id}, 1)" ${ultimoNonFisso ? "disabled" : ""}>${icona("arrow-down")}</button>
      <button class="btn-icona" aria-label="Modifica" onclick="modificaPunto(${p.id})">${icona("pencil")}</button>
      <button class="btn-icona pericolo" aria-label="Elimina" onclick="eliminaPunto(${p.id})">${icona("trash")}</button>
    </span>`;
  }
  if (PUO().proporre && !p.fisso) {
    return `<span class="comandi-punto">
      <button class="btn-icona testo" onclick="apriProposta(${p.id})">${icona("pencil")} Proponi modifica</button>
      <button class="btn-icona testo" onclick="proponiTogli(${p.id})">${icona("x")} Proponi di togliere</button>
    </span>`;
  }
  return "";
}

function rigaInModifica(p) {
  return `<li class="punto gestibile">
    <form class="nuovo-punto" style="margin: 0; flex: 1" onsubmit="salvaPunto(event, ${p.id})">
      <input type="text" name="titolo" maxlength="200" value="${esc(p.titolo)}" aria-label="Titolo" ${p.fisso ? "readonly" : ""}>
      <input type="number" name="minuti" min="1" max="600" value="${p.minuti}" style="width: 72px" aria-label="Minuti">
      <button class="btn btn-blu" aria-label="Salva">${icona("check")}</button>
      <button type="button" class="btn btn-tenue" aria-label="Annulla" onclick="modificaPunto(null)">${icona("x")}</button>
    </form>
  </li>`;
}

/** Il campo per aggiungere (o proporre) un punto nuovo. */
function disegnaFormPunto() {
  const box = document.getElementById("form-punto");
  if (!ODG_MODIFICABILE() && !PUO().proporre) { box.innerHTML = ""; return; }
  if (box.querySelector("form")) return;   // già disegnato: non cancello quello che si sta scrivendo
  const odg = ODG_MODIFICABILE();
  box.innerHTML = `<div class="etichetta-form">${odg ? "Aggiungi un punto" : "Proponi un punto"}</div>
    <form class="nuovo-punto" style="margin-top: 4px" onsubmit="aggiungiPunto(event)">
      <input type="text" name="titolo" maxlength="200" placeholder="${odg ? "Titolo del punto" : "Titolo del punto da proporre"}" aria-label="Titolo del punto">
      <select name="minuti" aria-label="Minuti previsti">
        ${[5, 10, 15, 20, 25, 30, 45, 60].map(m => `<option value="${m}" ${m === 10 ? "selected" : ""}>${m} min</option>`).join("")}
      </select>
      <button class="btn btn-blu" aria-label="${odg ? "Aggiungi" : "Invia proposta"}">${icona(odg ? "plus" : "send")}</button>
    </form>`;
}

function disegnaProssima() {
  const box = document.getElementById("prossima");
  const s = DATI.successiva;
  if (STATO() === "in_corso") {
    // Durante la riunione qui c'è solo "Concludi" (la prossima data si fissa concludendo)
    box.innerHTML = PUO().concludere
      ? `<button class="btn btn-blu btn-largo" onclick="apriConclusione()">${icona("check")} Concludi la riunione</button>` : "";
  } else if (s) {
    box.innerHTML = `<a class="collegamento" href="/r/${s.codice}">${icona("calendar-event")}
      <span class="corpo">Riunione successiva: <b style="font-weight: 500">${dataEstesa(s.data)}</b></span>${icona("chevron-right")}</a>`;
  } else if (typeof apriDialogRiunione === "function") {   // c'è solo per chi può creare riunioni
    box.innerHTML = `<button class="btn btn-giallo btn-largo" onclick="apriDialogRiunione({tipo: DATI.tipo, dopo: DATI.riunione})">
      ${icona("calendar-plus")} Fissa la prossima riunione</button>`;
  } else {
    box.innerHTML = "";
  }
}

// ------------------------------------------------------------ Varie

/** Le voci delle Varie, dentro l'ultimo punto: chiunque aggiunge la sua, subito. */
function vociVarie(solaLettura = false) {
  const voci = DATI.varie.map(v => {
    const mia = DATI.io_id && v.persona_id === DATI.io_id;
    const togli = !solaLettura && PUO().proporre && (mia || PUO().odg)
      ? `<button class="btn-icona" aria-label="Togli" onclick="togliVaria(${v.id})">${icona("x")}</button>` : "";
    return `<li><span class="corpo">${esc(v.testo)}
      ${v.persona_nome ? `<span class="firma" style="color:${esc(v.persona_colore)}">${pallino(v.persona_colore)}${esc(v.persona_nome)}</span>` : ""}</span>${togli}</li>`;
  }).join("");
  const form = !solaLettura && PUO().proporre ? `<form class="nuova-varia" onsubmit="aggiungiVaria(event)">
      <input class="campo" name="testo" maxlength="200" placeholder="Una voce per le Varie" aria-label="Nuova voce delle Varie">
      <button class="btn btn-tenue" aria-label="Aggiungi">${icona("plus")}</button>
    </form>` : "";
  if (!voci && !form) return "";
  return `<div class="varie-box">${voci ? `<ul class="voci-varie">${voci}</ul>` : ""}${form}</div>`;
}

async function aggiungiVaria(evento) {
  evento.preventDefault();
  const campo = evento.target.testo;
  if (!campo.value.trim()) return;
  if (aggiorna(await api("POST", `/api/riunioni/${DATI.riunione.id}/varie`, { testo: campo.value }), null)) {
    toast("Aggiunta alle Varie");
  }
}

async function togliVaria(id) {
  if (!confirm("Togliere questa voce dalle Varie?")) return;
  aggiorna(await api("DELETE", `/api/varie/${id}`), null);
}

// ------------------------------------------------------------ proposte

function disegnaProposte() {
  const box = document.getElementById("proposte");
  const proposte = DATI.proposte;
  if (!proposte.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="titolo-proposte">Proposte in attesa (${proposte.length})</div>` +
    proposte.map(p => {
      const c = esc(p.persona_colore);
      const minuti = m => `<span class="pillola">${m} min</span>`;
      let cosa, testo;
      if (p.tipo === "aggiungi") {
        cosa = "propone di aggiungere";
        testo = `${esc(p.titolo)} ${minuti(p.minuti)}`;
      } else if (p.tipo === "modifica") {
        cosa = "propone di modificare";
        testo = `<s class="vecchio">${esc(p.punto_titolo)} (${p.punto_minuti} min)</s><br>→ ${esc(p.titolo)} ${minuti(p.minuti)}`;
      } else {
        cosa = "propone di togliere";
        testo = `<s class="vecchio">${esc(p.punto_titolo)}</s>`;
      }
      const mia = DATI.io_id && p.persona_id === DATI.io_id;
      let azioni;
      if (PUO().odg) {
        azioni = `<div class="azioni-proposta">
          <button class="btn btn-blu btn-piccolo" onclick="decidi(${p.id}, 'approva')">${icona("check")} Approva</button>
          <button class="btn btn-tenue btn-piccolo" onclick="decidi(${p.id}, 'rifiuta')">Rifiuta</button>
          ${mia ? `<button class="btn btn-tenue btn-piccolo" onclick="decidi(${p.id}, 'ritira')">Ritira</button>` : ""}
        </div>`;
      } else if (mia) {
        azioni = `<div class="azioni-proposta"><span class="attesa">In attesa di approvazione</span>
          <button class="btn btn-tenue btn-piccolo" onclick="decidi(${p.id}, 'ritira')">Ritira</button></div>`;
      } else {
        azioni = `<div class="attesa">In attesa di approvazione</div>`;
      }
      return `<div class="proposta" style="border-color:${c}">
        <div class="chi" style="color:${c}">${pallino(p.persona_colore)}${esc(p.persona_nome)} ${cosa}</div>
        <div class="cosa">${testo}</div>
        ${azioni}
      </div>`;
    }).join("");
}

// ------------------------------------------------------------ aggiornamenti

/**
 * Dopo ogni azione il server restituisce lo stato aggiornato: lo ridisegno.
 * Se è cambiata la "fase" (iniziata o conclusa) ricarico tutta la pagina,
 * così anche l'intestazione si aggiorna.
 */
function aggiorna(r, idErrore = "errore-punto") {
  const box = idErrore && document.getElementById(idErrore);
  if (!r.ok) {
    if (box) box.textContent = r.data.errore || "Non è andata: riprova";
    else toast(r.data.errore || "Non è andata: riprova");
    return false;
  }
  if (box) box.textContent = "";
  applica(r.data);
  return true;
}

function applica(nuovo) {
  const faseCambiata = nuovo.riunione.stato !== DATI.riunione.stato;
  Object.assign(DATI, nuovo);
  ricevutoIl = Date.now();
  if (faseCambiata) { location.reload(); return; }
  disegna();
}

/** C'è qualcuno che sta scrivendo in un campo della pagina? */
function staScrivendo() {
  const el = document.activeElement;
  return el && (el.tagName === "TEXTAREA" || el.tagName === "INPUT") && el.closest(".pagina");
}

// Durante la riunione chiedo le novità ogni 3 secondi; il giorno della riunione
// (prima che inizi) ogni 20, per accorgermi se qualcuno la fa partire.
// Negli altri casi nessuna richiesta: si risparmiano batteria e traffico.
let ultimaImpronta = "";
function impronta(d) {
  const { adesso_ms, ...resto } = d;   // l'ora cambia sempre: non conta come novità
  resto.punti = resto.punti.map(({ trascorsi, ...p }) => p);
  return JSON.stringify(resto);
}

async function controllaNovita() {
  if (document.hidden) return;   // app in secondo piano: niente richieste
  const r = await api("GET", `/api/riunioni/${DATI.riunione.id}/stato`);
  if (!r.ok) return;
  const nuova = impronta(r.data);
  if (nuova === ultimaImpronta) {   // niente di nuovo: riallineo solo i timer
    DATI.punti = r.data.punti;
    ricevutoIl = Date.now();
    return;
  }
  ultimaImpronta = nuova;
  if (staScrivendo()) {             // non ridisegno sotto le dita di chi scrive
    Object.assign(DATI, r.data);
    ricevutoIl = Date.now();
    ridisegnoInSospeso = true;
    if (r.data.riunione.stato !== STATO()) location.reload();
    return;
  }
  applica(r.data);
}

document.addEventListener("focusout", () => {
  setTimeout(() => {
    if (ridisegnoInSospeso && !staScrivendo()) { ridisegnoInSospeso = false; disegna(); }
  }, 200);
});

function avvia() {
  ultimaImpronta = impronta(DATI);
  disegna();
  const d = new Date();   // data di oggi sul telefono, nel formato "2026-12-10"
  const oggi = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (STATO() === "in_corso") setInterval(controllaNovita, 3000);
  else if (STATO() === "in_programma" && DATI.riunione.data <= oggi) setInterval(controllaNovita, 20000);
  if (STATO() === "in_corso") setInterval(aggiornaTempi, 1000);   // riunione_corso.js
}

// ------------------------------------------------------------ azioni sui punti

async function aggiungiPunto(evento) {
  evento.preventDefault();
  const f = evento.target;
  if (!f.titolo.value.trim()) {
    document.getElementById("errore-punto").textContent = "Scrivi il titolo del punto";
    return;
  }
  const corpo = { titolo: f.titolo.value, minuti: f.minuti.value };
  const r = ODG_MODIFICABILE()
    ? await api("POST", `/api/riunioni/${DATI.riunione.id}/punti`, corpo)
    : await api("POST", `/api/riunioni/${DATI.riunione.id}/proposte`, { tipo: "aggiungi", ...corpo });
  if (aggiorna(r)) {
    f.titolo.value = "";
    if (ODG_MODIFICABILE()) f.titolo.focus();   // pronto per il punto successivo
    else toast("Proposta inviata: la vedi qui sotto");
  }
}

function modificaPunto(id) {
  puntoInModifica = id;
  disegnaPunti();
  if (id) document.querySelector("#punti input[name=minuti]").focus();
}

async function salvaPunto(evento, id) {
  evento.preventDefault();
  const f = evento.target;
  if (!f.titolo.value.trim()) {
    document.getElementById("errore-punto").textContent = "Il titolo non può essere vuoto";
    return;
  }
  const r = await api("PATCH", `/api/punti/${id}`, { titolo: f.titolo.value, minuti: f.minuti.value });
  if (r.ok) puntoInModifica = null;
  aggiorna(r);
}

async function spostaPunto(id, direzione) {
  aggiorna(await api("POST", `/api/punti/${id}/sposta`, { direzione }));
}

async function eliminaPunto(id) {
  const punto = DATI.punti.find(p => p.id === id);
  if (!confirm(`Eliminare il punto "${punto.titolo}"?`)) return;
  aggiorna(await api("DELETE", `/api/punti/${id}`));
}

// ------------------------------------------------------------ proposte (azioni)

let puntoDaProporre = null;

function apriProposta(id) {
  puntoDaProporre = DATI.punti.find(p => p.id === id);
  const dlg = document.getElementById("dlg-proposta");
  const f = dlg.querySelector("form");
  f.titolo.value = puntoDaProporre.titolo;
  f.minuti.value = puntoDaProporre.minuti;
  document.getElementById("proposta-originale").textContent =
    `Punto attuale: "${puntoDaProporre.titolo}" (${puntoDaProporre.minuti} min). Cambia quello che vuoi.`;
  document.getElementById("proposta-errore").textContent = "";
  dlg.showModal();
}

async function inviaProposta(evento) {
  evento.preventDefault();
  const f = evento.target;
  const r = await api("POST", `/api/riunioni/${DATI.riunione.id}/proposte`,
                      { tipo: "modifica", punto_id: puntoDaProporre.id, titolo: f.titolo.value, minuti: f.minuti.value });
  if (aggiorna(r, "proposta-errore")) {
    document.getElementById("dlg-proposta").close();
    toast("Proposta inviata");
  }
}

async function proponiTogli(id) {
  const punto = DATI.punti.find(p => p.id === id);
  if (!confirm(`Proporre di togliere "${punto.titolo}" dall'ordine del giorno?`)) return;
  if (aggiorna(await api("POST", `/api/riunioni/${DATI.riunione.id}/proposte`, { tipo: "togli", punto_id: id }), null)) {
    toast("Proposta inviata");
  }
}

async function decidi(id, azione) {
  const messaggi = { approva: "Proposta approvata", rifiuta: "Proposta rifiutata", ritira: "Proposta ritirata" };
  if (aggiorna(await api("POST", `/api/proposte/${id}/${azione}`), null)) toast(messaggi[azione]);
}

document.addEventListener("input", e => {
  if (e.target.closest(".nuovo-punto")) document.getElementById("errore-punto").textContent = "";
});

// ------------------------------------------------------------ date

const GIORNI = ["domenica", "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato"];
const MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
              "settembre", "ottobre", "novembre", "dicembre"];

/** "2026-12-10" -> "giovedì 10 dicembre" (senza passare dal fuso orario). */
function dataEstesa(iso, conAnno = false) {
  const [a, m, g] = iso.split("-").map(Number);
  const d = new Date(a, m - 1, g);
  return `${GIORNI[d.getDay()]} ${g} ${MESI[m - 1]}${conAnno ? " " + a : ""}`;
}
function dataBreve(iso) {
  const [, m, g] = iso.split("-").map(Number);
  return `${g} ${MESI[m - 1]}`;
}

// ------------------------------------------------------------ condivisione

/**
 * Sui telefoni si apre il menu di condivisione del sistema (quello con le icone
 * di WhatsApp, Telegram, email...): se ci sono sia WhatsApp sia WhatsApp
 * Business, il menu le mostra entrambe e la persona sceglie. Dove il menu non
 * esiste (computer) si apre il nostro foglio "Condividi".
 */
async function condividi() {
  if (navigator.share) {
    try {
      await navigator.share({ title: DATI.titolo_condivisione, text: DATI.titolo_condivisione, url: DATI.url });
      return;
    } catch (e) {
      if (e.name === "AbortError") return;   // la persona ha chiuso il menu: va bene così
    }
  }
  // Sul computer: "wa.me/?text=..." apre WhatsApp Web con il messaggio già scritto
  document.getElementById("condividi-whatsapp").href =
    "https://wa.me/?text=" + encodeURIComponent(`${DATI.titolo_condivisione}\n${DATI.url}`);
  document.getElementById("foglio-condividi").showModal();
}

async function copiaLink() {
  try {
    await navigator.clipboard.writeText(DATI.url);
    toast("Link copiato");
  } catch (e) {
    prompt("Copia il link:", DATI.url);   // alcuni browser non permettono di copiare
  }
  document.getElementById("foglio-condividi").close();
}
