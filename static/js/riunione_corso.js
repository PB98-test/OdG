// Pagina di una riunione: la modalità "durante".
// Spunte colorate, timer per punto, decisioni e compiti (verbale leggero),
// compiti dalla volta scorsa, conclusione in due passi.

// ------------------------------------------------------------ barra in alto

function disegnaBarra() {
  const box = document.getElementById("barra-riunione");
  if (STATO() === "in_programma") {
    box.innerHTML = PUO().iniziare
      ? `<div class="scheda barra-inizio">
           <span class="corpo">Ci siamo quasi: quando siete pronti, fate partire la riunione.</span>
           <button class="btn btn-blu" onclick="iniziaRiunione()">${icona("player-play")} Inizia la riunione</button>
         </div>` : "";
    return;
  }
  // In corso: tempo trascorso, fine prevista, barra di avanzamento
  box.innerHTML = `<div class="scheda barra-tempi">
    <div class="righe-tempi">
      <span>Trascorsi <b id="tempo-totale">-</b> di ${minutiPrevisti()} min</span>
      <span>Fine prevista <b id="fine-prevista">-</b></span>
    </div>
    <div class="progresso"><div id="progresso"></div></div>
  </div>`;
  aggiornaTempi();
}

function minutiPrevisti() {
  return DATI.punti.reduce((s, p) => s + p.minuti, 0);
}

/** Secondi trascorsi su un punto, contando anche il timer acceso in questo momento. */
function tempoVivo(p) {
  return p.trascorsi + (p.timer_acceso ? Math.floor((Date.now() - ricevutoIl) / 1000) : 0);
}

function mmss(secondi) {
  const m = Math.floor(secondi / 60), s = secondi % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function oraHHMM(d) {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Ora di fine fissata (ora di fine, oppure inizio + durata abituale del tipo). */
function fineFissata() {
  const [a, m, g] = DATI.riunione.data.split("-").map(Number);
  const [hi, mi] = DATI.riunione.ora_inizio.split(":").map(Number);
  const inizio = new Date(a, m - 1, g, hi, mi);
  if (DATI.riunione.ora_fine) {
    const [hf, mf] = DATI.riunione.ora_fine.split(":").map(Number);
    const fine = new Date(a, m - 1, g, hf, mf);
    if (fine <= inizio) fine.setDate(fine.getDate() + 1);
    return fine;
  }
  return new Date(inizio.getTime() + DATI.tipo.durata_abituale * 60000);
}

/** Ogni secondo: i timer dei punti e la barra in alto. */
function aggiornaTempi() {
  let totale = 0, restano = 0;
  for (const p of DATI.punti) {
    const vivo = tempoVivo(p);
    totale += vivo;
    if (!p.spuntato_da) restano += Math.max(p.minuti * 60 - vivo, 0);
    const el = document.querySelector(`[data-timer="${p.id}"]`);
    if (el) {
      el.textContent = vivo ? `${mmss(vivo)} di ${p.minuti} min` : `${p.minuti} min`;
      el.classList.toggle("sforato", vivo > p.minuti * 60);
    }
  }
  const t = document.getElementById("tempo-totale");
  if (!t) return;
  t.textContent = `${Math.floor(totale / 60)} min`;
  const fine = new Date(Date.now() + restano * 1000);
  const f = document.getElementById("fine-prevista");
  f.textContent = oraHHMM(fine);
  f.classList.toggle("sforato", fine > fineFissata());
  f.title = `Fine fissata: ${oraHHMM(fineFissata())}`;
  document.getElementById("progresso").style.width = `${Math.min(100, Math.round(totale / 60 / Math.max(minutiPrevisti(), 1) * 100))}%`;
}

// ------------------------------------------------------------ punti durante la riunione

function rigaInCorso(p, i) {
  const spuntato = !!p.spuntato_da;
  const aperto = espansi.has(p.id) || p.timer_acceso || p.fisso;
  const colore = spuntato ? esc(p.spuntato_da_colore) : "";
  const firmaSpunta = spuntato
    ? `<span class="firma" style="color:${colore}">${pallino(p.spuntato_da_colore)}spuntato da ${esc(p.spuntato_da_nome)}</span>` : "";
  const bottoneTimer = spuntato ? "" :
    `<button class="btn-timer${p.timer_acceso ? " acceso" : ""}" aria-label="${p.timer_acceso ? "Pausa" : "Avvia il timer"}"
       onclick="timer(${p.id}, '${p.timer_acceso ? "pausa" : "avvia"}')">${icona(p.timer_acceso ? "player-pause" : "player-play")}</button>`;
  return `<li class="punto in-corso${spuntato ? " spuntato" : ""}${p.timer_acceso ? " acceso" : ""}${p.fisso ? " varie" : ""}">
    <button class="spunta" aria-label="${spuntato ? "Togli la spunta" : "Spunta"}" onclick="spunta(${p.id}, ${!spuntato})"
      style="${spuntato ? `background:${colore};border-color:${colore}` : ""}">${icona("check")}</button>
    <span class="titolo" onclick="espandi(${p.id})">${esc(p.titolo)}${firme(p)}${firmaSpunta}</span>
    <span class="tempo" data-timer="${p.id}"></span>
    ${bottoneTimer}
    ${p.fisso ? "" : `<button class="btn-icona" aria-label="${aperto ? "Chiudi" : "Apri"}" onclick="espandi(${p.id})">${icona(aperto ? "chevron-down" : "chevron-right")}</button>`}
    ${aperto ? dettagliPunto(p, i) : ""}
  </li>`;
}

/** La parte che si apre sotto un punto: decisioni, compiti, comandi. */
function dettagliPunto(p, i) {
  const decisioni = PUO().verbale
    ? `<textarea class="decisioni" data-punto="${p.id}" placeholder="Decisioni prese" rows="2">${esc(p.decisioni || "")}</textarea>`
    : (p.decisioni ? `<div class="decisioni-testo"><b>Decisioni:</b> ${esc(p.decisioni)}</div>` : "");
  const compiti = DATI.compiti.filter(c => c.punto_id === p.id);
  return `<div class="dettagli-punto">
    ${p.fisso ? vociVarie() : ""}
    ${decisioni}
    ${compiti.length ? listaCompiti(compiti, PUO().verbale) : ""}
    ${PUO().verbale ? `<button class="btn-icona testo" onclick="apriCompito(${p.id})">${icona("plus")} Aggiungi un compito</button>` : ""}
    ${comandiPunto(p, i)}
  </div>`;
}

function espandi(id) {
  if (espansi.has(id)) espansi.delete(id); else espansi.add(id);
  disegnaPunti();
}

async function iniziaRiunione() {
  if (!confirm("Iniziare la riunione? Da quel momento si potranno spuntare i punti e usare i timer.")) return;
  aggiorna(await api("POST", `/api/riunioni/${DATI.riunione.id}/inizia`), null);
}

async function spunta(id, spuntato) {
  aggiorna(await api("POST", `/api/punti/${id}/spunta`, { spuntato }), null);
}

async function timer(id, azione) {
  if (azione === "avvia") espansi.add(id);   // il punto di cui si parla si apre da solo
  aggiorna(await api("POST", `/api/punti/${id}/timer`, { azione }), null);
}

// Decisioni: si salvano da sole mentre si scrive (dopo una breve pausa)
const _timerDecisioni = {};
document.addEventListener("input", e => {
  if (!e.target.matches("textarea.decisioni")) return;
  const id = Number(e.target.dataset.punto);
  const testo = e.target.value;
  const punto = DATI.punti.find(p => p.id === id);
  if (punto) punto.decisioni = testo;     // così un ridisegno non perde quanto scritto
  clearTimeout(_timerDecisioni[id]);
  _timerDecisioni[id] = setTimeout(async () => {
    const r = await api("PATCH", `/api/punti/${id}/decisioni`, { testo });
    if (!r.ok) toast(r.data.errore || "Decisioni non salvate: riprova");
  }, 700);
});

// ------------------------------------------------------------ compiti

/** Elenco di compiti con la casella "fatto". */
function listaCompiti(compiti, eliminabili) {
  return `<ul class="compiti">${compiti.map(c => {
    const mio = DATI.io_id && c.persona_id === DATI.io_id;
    const spuntabile = mio || PUO().verbale;
    const chi = c.persona_nome
      ? `<span class="chi-compito" style="color:${esc(c.persona_colore)}">${pallino(c.persona_colore)}${esc(c.persona_nome)}</span>` : "";
    return `<li class="${c.fatto_il ? "fatto" : ""}">
      <input type="checkbox" ${c.fatto_il ? "checked" : ""} ${spuntabile ? "" : "disabled"}
             aria-label="Fatto" onchange="fattoCompito(${c.id}, this.checked)">
      <span class="corpo">${chi}${esc(c.testo)}</span>
      ${eliminabili ? `<button class="btn-icona" aria-label="Elimina il compito" onclick="eliminaCompito(${c.id})">${icona("x")}</button>` : ""}
    </li>`;
  }).join("")}</ul>`;
}

let _puntoDelCompito = null;

async function apriCompito(puntoId) {
  _puntoDelCompito = puntoId;
  const dlg = document.getElementById("dlg-compito");
  const f = dlg.querySelector("form");
  f.reset();
  document.getElementById("compito-punto").textContent = `Punto: ${DATI.punti.find(p => p.id === puntoId).titolo}`;
  document.getElementById("compito-errore").textContent = "";
  // L'elenco si ricarica ogni volta: nel frattempo potrebbero esserci persone nuove
  const r = await api("GET", "/api/persone/nomi");
  if (r.ok) {
    f.persona_id.innerHTML = `<option value="">Nessuno in particolare</option>` +
      r.data.persone.map(p => `<option value="${p.id}">${esc(p.nome)}</option>`).join("") +
      `<option value="nuova">+ Persona nuova…</option>`;
  }
  sceltaPersonaCompito("");
  dlg.showModal();
}

/** "+ Persona nuova…": compare il campo per scriverne il nome. */
function sceltaPersonaCompito(valore) {
  const riga = document.getElementById("riga-nuova-persona");
  riga.style.display = valore === "nuova" ? "" : "none";
  if (valore === "nuova") riga.querySelector("input").focus();
}

async function salvaCompito(evento) {
  evento.preventDefault();
  const f = evento.target;
  const errore = document.getElementById("compito-errore");
  if (!f.testo.value.trim()) { errore.textContent = "Scrivi che cosa c'è da fare"; return; }
  const corpo = { testo: f.testo.value };
  if (f.persona_id.value === "nuova") {
    if (f.nuova_persona.value.trim().length < 2) { errore.textContent = "Scrivi nome e iniziale del cognome"; return; }
    corpo.nuova_persona = f.nuova_persona.value;   // la persona viene creata come Partecipante
  } else {
    corpo.persona_id = Number(f.persona_id.value) || null;
  }
  const r = await api("POST", `/api/punti/${_puntoDelCompito}/compiti`, corpo);
  if (aggiorna(r, "compito-errore")) {
    document.getElementById("dlg-compito").close();
    toast("Compito aggiunto");
  }
}

async function fattoCompito(id, fatto) {
  const r = await api("POST", `/api/compiti/${id}/fatto`, { fatto });
  if (!r.ok) { toast(r.data.errore || "Non è andata: riprova"); disegna(); return; }
  for (const elenco of [DATI.compiti, DATI.compiti_precedenti]) {
    const c = elenco.find(x => x.id === id);
    if (c) c.fatto_il = fatto ? "ora" : null;
  }
  disegna();
}

async function eliminaCompito(id) {
  if (!confirm("Eliminare questo compito?")) return;
  aggiorna(await api("DELETE", `/api/compiti/${id}`), null);
}

/** In cima: i compiti decisi nella riunione precedente dello stesso tipo. */
function disegnaCompitiPrecedenti() {
  const box = document.getElementById("compiti-precedenti");
  if (!DATI.compiti_precedenti.length) { box.innerHTML = ""; return; }
  const aperti = DATI.compiti_precedenti.filter(c => !c.fatto_il).length;
  box.innerHTML = `<section class="sezione">
    <div class="titolo-sezione"><h2>Compiti dalla volta scorsa</h2>
      <span class="meta">${aperti ? `${aperti} da fare` : "tutti fatti"}</span></div>
    <div class="scheda riquadro-compiti">
      ${listaCompiti(DATI.compiti_precedenti, false)}
      <a class="link-verbale" href="/r/${DATI.precedente.codice}">Verbale del ${dataBreve(DATI.precedente.data)} ${icona("chevron-right")}</a>
    </div>
  </section>`;
}

// ------------------------------------------------------------ presenti

/** Sezione "Presenti": compare quando la riunione è iniziata (e resta nel verbale). */
function disegnaPresenti() {
  const box = document.getElementById("presenti");
  if (STATO() === "in_programma") { box.innerHTML = ""; return; }
  const presenti = DATI.presenti;
  const ciSono = DATI.io_id && presenti.some(p => p.id === DATI.io_id);
  const nomi = presenti.map(p =>
    `<span class="chip-persona">${pallino(p.colore)}${esc(p.nome)}</span>`).join("");
  const bottoni = [
    !ciSono && STATO() === "in_corso"
      ? `<button class="btn btn-tenue btn-piccolo" onclick="ciSonoAnchIo()">${icona("check")} Ci sono anch'io</button>` : "",
    PUO().verbale
      ? `<button class="btn btn-contorno btn-piccolo" onclick="apriPresenti()">${icona("users")} ${presenti.length ? "Modifica" : "Segna i presenti"}</button>` : "",
  ].join("");
  box.innerHTML = `<section class="sezione">
    <div class="titolo-sezione"><h2>Presenti</h2><span class="meta">${presenti.length || ""}</span></div>
    <div class="scheda riquadro-presenti">
      ${nomi ? `<div class="chips">${nomi}</div>` : `<div class="nota" style="margin: 0 0 8px">Nessuno segnato, per ora.</div>`}
      ${bottoni ? `<div class="azioni-presenti">${bottoni}</div>` : ""}
    </div>
  </section>`;
}

async function ciSonoAnchIo() {
  if (aggiorna(await api("POST", `/api/riunioni/${DATI.riunione.id}/presenti/io`), null)) toast("Segnato tra i presenti");
}

let _persone = [];                 // tutte le persone note (per la finestra)
let _sceltiPresenti = new Set();   // spunte nella finestra, non ancora salvate

async function apriPresenti() {
  _sceltiPresenti = new Set(DATI.presenti.map(p => p.id));
  document.getElementById("presenti-errore").textContent = "";
  document.getElementById("cerca-presenti").value = "";
  document.querySelector("#dlg-presenti .nuova-persona").reset();
  await caricaPersone();
  document.getElementById("dlg-presenti").showModal();
}

async function caricaPersone() {
  const r = await api("GET", "/api/persone/nomi");
  if (!r.ok) { document.getElementById("presenti-errore").textContent = r.data.errore || "Elenco non disponibile"; return; }
  _persone = r.data.persone;
  disegnaElencoPresenti();
}

function disegnaElencoPresenti(filtro = "") {
  const f = filtro.trim().toLowerCase();
  document.getElementById("elenco-presenti").innerHTML = _persone
    .filter(p => !f || p.nome.toLowerCase().includes(f))
    .map(p => `<label class="permesso">
      <input type="checkbox" ${_sceltiPresenti.has(p.id) ? "checked" : ""}
             onchange="this.checked ? _sceltiPresenti.add(${p.id}) : _sceltiPresenti.delete(${p.id})">
      ${pallino(p.colore)}${esc(p.nome)}${p.attiva ? "" : ` <span class="nota-inline">non ha ancora usato OdG</span>`}
    </label>`).join("") || `<div class="nota">Nessun nome trovato: aggiungilo qui sotto.</div>`;
}

function filtraPresenti(testo) {
  disegnaElencoPresenti(testo);
}

async function nuovoPresente(evento) {
  evento.preventDefault();
  const campo = evento.target.nome;
  const errore = document.getElementById("presenti-errore");
  if (campo.value.trim().length < 2) { errore.textContent = "Scrivi nome e iniziale del cognome"; return; }
  const r = await api("POST", `/api/riunioni/${DATI.riunione.id}/presenti/nuova`, { nome: campo.value });
  if (!r.ok) { errore.textContent = r.data.errore || "Non è andata: riprova"; return; }
  errore.textContent = "";
  campo.value = "";
  _sceltiPresenti.add(r.data.nuova.id);   // la persona nuova è già segnata presente
  await caricaPersone();
  toast(`${r.data.nuova.nome} aggiunta`);
}

async function salvaPresenti() {
  const r = await api("PUT", `/api/riunioni/${DATI.riunione.id}/presenti`, { persone: [..._sceltiPresenti] });
  if (aggiorna(r, "presenti-errore")) {
    document.getElementById("dlg-presenti").close();
    toast("Presenti aggiornati");
  }
}

// ------------------------------------------------------------ conclusione

function apriConclusione() {
  const nonTrattati = DATI.punti.filter(p => !p.spuntato_da && !p.fisso);
  document.getElementById("concludi-punti").innerHTML = nonTrattati.map(p =>
    `<label class="permesso"><input type="checkbox" value="${p.id}" checked> ${esc(p.titolo)}</label>`).join("");
  // "Quando ci vediamo?": proposto con orario e luogo abituali
  const f = document.getElementById("concludi-passo-2");
  f.reset();
  f.ora_inizio.value = DATI.tipo.ora_abituale || DATI.riunione.ora_inizio;
  f.luogo.value = DATI.tipo.luogo_abituale || DATI.riunione.luogo || "";
  const s = DATI.successiva;
  document.getElementById("concludi-gia-fissata").innerHTML = s
    ? `<p class="spiega">La prossima riunione è già fissata: <b>${dataEstesa(s.data)}, ore ${s.ora_inizio}</b>.</p>` : "";
  document.getElementById("concludi-campi").style.display = s ? "none" : "";
  document.getElementById("btn-salta").style.display = s ? "none" : "";
  document.getElementById("btn-concludi").textContent = s ? "Concludi" : "Fissa e concludi";
  document.getElementById("concludi-errore").textContent = "";
  passoConclusione(nonTrattati.length ? 1 : 2);
  document.getElementById("dlg-concludi").showModal();
}

function passoConclusione(n) {
  document.getElementById("concludi-passo-1").style.display = n === 1 ? "" : "none";
  document.getElementById("concludi-passo-2").style.display = n === 2 ? "" : "none";
}

/** fissa = true: crea anche la prossima riunione ("Quando ci vediamo?"). */
async function concludi(evento, fissa) {
  evento.preventDefault();
  const f = document.getElementById("concludi-passo-2");
  const errore = document.getElementById("concludi-errore");
  const corpo = {
    riporta: [...document.querySelectorAll("#concludi-punti input:checked")].map(c => Number(c.value)),
  };
  if (fissa && !DATI.successiva) {
    if (!f.data.value) { errore.textContent = "Scegli la data, oppure premi Salta"; return; }
    corpo.prossima = { data: f.data.value, ora_inizio: f.ora_inizio.value, luogo: f.luogo.value };
  }
  const r = await api("POST", `/api/riunioni/${DATI.riunione.id}/concludi`, corpo);
  if (!r.ok) { errore.textContent = r.data.errore || "Non è andata: riprova"; return; }
  location.reload();   // la pagina diventa il verbale
}
