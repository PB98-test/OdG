// Pagina di una riunione: ordine del giorno, proposte, condivisione.
// L'elenco dei punti viene ridisegnato qui con i comandi adatti a chi guarda:
// - chi ha il permesso "odg" modifica direttamente (sposta, modifica, elimina)
//   e approva o rifiuta le proposte;
// - tutti gli altri possono proporre: aggiungere, modificare o togliere un punto.

const PUO_ODG = !!(DATI.io && DATI.io.permessi.odg);
const PUO_PROPORRE = !DATI.passata;   // le proposte hanno senso solo prima della riunione

// ------------------------------------------------------------ disegno

let puntoInModifica = null;   // id del punto in modifica diretta (uno alla volta)

function disegna() {
  disegnaPunti();
  disegnaProposte();
}

function disegnaPunti() {
  const elenco = document.getElementById("punti");
  const punti = DATI.punti;
  const totale = punti.reduce((somma, p) => somma + p.minuti, 0);
  document.getElementById("totale-minuti").textContent = totale ? `${totale} min previsti` : "";
  if (!punti.length) {
    elenco.innerHTML = `<li class="scheda vuoto">${PUO_ODG ? "Aggiungi il primo punto qui sotto."
      : "L'ordine del giorno non è ancora stato scritto."}</li>`;
    return;
  }
  elenco.innerHTML = punti.map((p, i) => {
    if (p.id === puntoInModifica) return rigaInModifica(p);
    const firma = p.proposto_da_nome
      ? `<span class="firma" style="color:${esc(p.proposto_da_colore)}">${pallino(p.proposto_da_colore)}proposto da ${esc(p.proposto_da_nome)}</span>`
      : "";
    return `<li class="punto${comandi(p, i) ? " gestibile" : ""}">
      <span class="num">${i + 1}</span>
      <span class="titolo">${esc(p.titolo)}${firma}</span>
      <span class="pillola">${p.minuti} min</span>
      ${comandi(p, i)}
    </li>`;
  }).join("");
}

function comandi(p, i) {
  if (PUO_ODG) {
    const ultimo = i === DATI.punti.length - 1;
    return `<span class="comandi-punto">
      <button class="btn-icona" aria-label="Sposta su" onclick="spostaPunto(${p.id}, -1)" ${i === 0 ? "disabled" : ""}>${icona("arrow-up")}</button>
      <button class="btn-icona" aria-label="Sposta giù" onclick="spostaPunto(${p.id}, 1)" ${ultimo ? "disabled" : ""}>${icona("arrow-down")}</button>
      <button class="btn-icona" aria-label="Modifica" onclick="modificaPunto(${p.id})">${icona("pencil")}</button>
      <button class="btn-icona pericolo" aria-label="Elimina" onclick="eliminaPunto(${p.id})">${icona("trash")}</button>
    </span>`;
  }
  if (PUO_PROPORRE) {
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
      <input type="text" name="titolo" maxlength="200" value="${esc(p.titolo)}" aria-label="Titolo">
      <input type="number" name="minuti" min="1" max="600" value="${p.minuti}" style="width: 72px" aria-label="Minuti">
      <button class="btn btn-blu" aria-label="Salva">${icona("check")}</button>
      <button type="button" class="btn btn-tenue" aria-label="Annulla" onclick="modificaPunto(null)">${icona("x")}</button>
    </form>
  </li>`;
}

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
      let azioni;
      if (PUO_ODG) {
        azioni = `<div class="azioni-proposta">
          <button class="btn btn-blu btn-piccolo" onclick="decidi(${p.id}, 'approva')">${icona("check")} Approva</button>
          <button class="btn btn-tenue btn-piccolo" onclick="decidi(${p.id}, 'rifiuta')">Rifiuta</button>
          ${mia(p) ? `<button class="btn btn-tenue btn-piccolo" onclick="decidi(${p.id}, 'ritira')">Ritira</button>` : ""}
        </div>`;
      } else if (mia(p)) {
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

function mia(p) {
  return DATI.io && p.persona_id === DATI.io.id;
}

// ------------------------------------------------------------ azioni

/** Dopo ogni azione il server restituisce lo stato aggiornato: lo ridisegno. */
function aggiorna(r, idErrore = "errore-punto") {
  const box = document.getElementById(idErrore);
  if (!r.ok) {
    if (box) box.textContent = r.data.errore || "Non è andata: riprova";
    else toast(r.data.errore || "Non è andata: riprova");
    return false;
  }
  if (box) box.textContent = "";
  DATI.punti = r.data.punti;
  DATI.proposte = r.data.proposte;
  disegna();
  return true;
}

async function aggiungiPunto(evento) {
  evento.preventDefault();
  const f = evento.target;
  if (!f.titolo.value.trim()) {
    document.getElementById("errore-punto").textContent = "Scrivi il titolo del punto";
    return;
  }
  const corpo = { titolo: f.titolo.value, minuti: f.minuti.value };
  const r = PUO_ODG
    ? await api("POST", `/api/riunioni/${DATI.riunione.id}/punti`, corpo)
    : await api("POST", `/api/riunioni/${DATI.riunione.id}/proposte`, { tipo: "aggiungi", ...corpo });
  if (aggiorna(r)) {
    f.titolo.value = "";
    if (PUO_ODG) f.titolo.focus();   // pronto per scrivere subito il punto successivo
    else toast("Proposta inviata: la vedi qui sotto");
  }
}

// Modifica diretta (permesso "odg")
function modificaPunto(id) {
  puntoInModifica = id;
  disegnaPunti();
  if (id) document.querySelector("#punti input[name=titolo]").focus();
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

// Proposte (tutti)
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

// Cancella l'avviso di errore appena si ricomincia a scrivere
document.addEventListener("input", e => {
  if (e.target.closest(".nuovo-punto")) document.getElementById("errore-punto").textContent = "";
});

// ------------------------------------------------------------ condivisione

const testoCondivisione = `${DATI.titolo_condivisione}\n${DATI.url}`;

// Sul computer: il link "wa.me/?text=..." apre WhatsApp Web (o l'app del computer)
// con il messaggio già scritto, lasciando scegliere la chat o il gruppo.
document.getElementById("condividi-whatsapp").href =
  "https://wa.me/?text=" + encodeURIComponent(testoCondivisione);

/**
 * Sui telefoni si apre il menu di condivisione del sistema (quello con le icone
 * di WhatsApp, Telegram, email...). È la strada più sicura: se sul telefono ci
 * sono sia WhatsApp sia WhatsApp Business, il menu le mostra entrambe e la
 * persona sceglie; il link wa.me invece apre quella che decide il telefono.
 * Dove il menu non esiste (computer) si apre il nostro foglio "Condividi".
 */
async function condividi() {
  if (navigator.share) {
    try {
      await navigator.share({ title: DATI.titolo_condivisione, text: DATI.titolo_condivisione, url: DATI.url });
      return;
    } catch (e) {
      if (e.name === "AbortError") return;   // la persona ha chiuso il menu: va bene così
      // qualunque altro problema: si ripiega sul nostro foglio
    }
  }
  document.getElementById("foglio-condividi").showModal();
}

async function copiaLink() {
  try {
    await navigator.clipboard.writeText(DATI.url);
    toast("Link copiato");
  } catch (e) {
    // Alcuni browser non permettono di copiare: mostro il link da copiare a mano
    prompt("Copia il link:", DATI.url);
  }
  document.getElementById("foglio-condividi").close();
}

disegna();
