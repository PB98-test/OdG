// Pagina "Persone e ruoli" (solo per chi ha il permesso "persone").

let PERSONE = [], RUOLI = [], COLORI = [], IO_ID = null;
let aperta = null;   // persona di cui è aperta la scheda di modifica

async function carica() {
  const r = await api("GET", "/api/persone");
  if (!r.ok) return toast(r.data.errore || "Caricamento non riuscito");
  ({ persone: PERSONE, ruoli: RUOLI, colori: COLORI, io: IO_ID } = r.data);
  disegna();
}

function disegna() {
  disegnaPersone();
  disegnaRuoli();
  document.getElementById("scelta-ruolo-nuova").innerHTML = opzioniRuoli(2);
}

function opzioniRuoli(scelto) {
  return RUOLI.map(r => `<option value="${r.id}" ${r.id === scelto ? "selected" : ""}>${esc(r.nome)}</option>`).join("");
}

// ------------------------------------------------------------ persone

function disegnaPersone() {
  document.getElementById("conta-persone").textContent = PERSONE.length || "";
  const box = document.getElementById("elenco-persone");
  if (!PERSONE.length) { box.innerHTML = `<div class="scheda vuoto">Nessuna persona.</div>`; return; }
  box.innerHTML = PERSONE.map(p => {
    const stato = p.dispositivi
      ? `${p.dispositivi} dispositiv${p.dispositivi === 1 ? "o" : "i"}`
      : `<span class="in-attesa">non ancora attiva</span>`;
    const riga = `<button class="voce persona" onclick="apri(${p.id})">
        ${pallino(p.colore)}
        <span class="corpo">
          <span class="principale">${esc(p.nome)}${p.id === IO_ID ? " <span class='tu'>(tu)</span>" : ""}</span>
          <span class="secondaria">${esc(p.ruolo_nome)} · ${stato}</span>
        </span>
        ${icona(p.id === aperta ? "chevron-down" : "chevron-right")}
      </button>`;
    return p.id === aperta ? riga + schedaModifica(p) : riga;
  }).join("");
}

function schedaModifica(p) {
  const altre = PERSONE.filter(x => x.id !== p.id);
  return `<form class="scheda scheda-persona" onsubmit="salvaPersona(event, ${p.id})">
    <label>Nome<input class="campo" name="nome" maxlength="30" value="${esc(p.nome)}"></label>
    <label>Ruolo<select class="campo" name="ruolo_id">${opzioniRuoli(p.ruolo_id)}</select></label>
    <div class="etichetta-form">Colore</div>
    <div class="colori">${COLORI.map(c => `<label class="colore" style="background:${c}">
        <input type="radio" name="colore" value="${c}" ${c === p.colore ? "checked" : ""} aria-label="Colore ${c}"></label>`).join("")}</div>
    <div class="errore-form" id="errore-${p.id}"></div>
    <button class="btn btn-blu btn-largo">Salva</button>
    <div class="azioni-persona">
      <button type="button" class="btn btn-contorno btn-piccolo" onclick="linkAttivazione(${p.id})">${icona("link")} Link per entrare</button>
      ${p.dispositivi ? `<button type="button" class="btn btn-tenue btn-piccolo" onclick="scollega(${p.id})">${icona("logout")} Scollega dispositivi</button>` : ""}
      <button type="button" class="btn btn-pericolo btn-piccolo" onclick="eliminaPersona(${p.id})">${icona("trash")} Elimina</button>
    </div>
    ${altre.length ? `<div class="unisci">
      <span>${icona("git-merge")} È un doppione di</span>
      <select class="campo" id="unisci-${p.id}"><option value="">scegli…</option>
        ${altre.map(x => `<option value="${x.id}">${esc(x.nome)}</option>`).join("")}</select>
      <button type="button" class="btn btn-tenue btn-piccolo" onclick="unisci(${p.id})">Unisci</button>
    </div>` : ""}
  </form>`;
}

function apri(id) {
  aperta = aperta === id ? null : id;
  disegnaPersone();
}

function errorePersona(id, r) {
  const box = document.getElementById(`errore-${id}`);
  if (box) box.textContent = r.data.errore || "Non è andata: riprova";
}

async function salvaPersona(evento, id) {
  evento.preventDefault();
  const f = evento.target;
  const r = await api("PATCH", `/api/persone/${id}`,
                      { nome: f.nome.value, ruolo_id: Number(f.ruolo_id.value), colore: f.colore.value });
  if (!r.ok) return errorePersona(id, r);
  PERSONE = r.data.persone;
  aperta = null;
  toast("Salvato");
  // Il numero di persone per ruolo può essere cambiato: ricarico anche i ruoli
  carica();
}

async function linkAttivazione(id) {
  const persona = PERSONE.find(p => p.id === id);
  if (persona.dispositivi && !confirm(`${persona.nome} è già attiva. Creare comunque un nuovo link (es. per un telefono nuovo)?`)) return;
  const r = await api("POST", `/api/persone/${id}/attivazione`);
  if (!r.ok) return errorePersona(id, r);
  mostraAttivazione(r.data);
}

function mostraAttivazione(dati) {
  mostraLink(`Link per ${dati.nome}`,
    `Mandalo a ${dati.nome} in privato (es. su WhatsApp). Vale ${dati.giorni} giorni e una sola volta: ` +
    `aprendolo, entrerà in OdG con il suo ruolo.`, dati);
}

async function scollega(id) {
  const persona = PERSONE.find(p => p.id === id);
  if (!confirm(`Scollegare tutti i dispositivi di ${persona.nome}? Per rientrare le servirà un nuovo link.`)) return;
  const r = await api("DELETE", `/api/persone/${id}/dispositivi`);
  if (!r.ok) return errorePersona(id, r);
  toast("Dispositivi scollegati");
  carica();
}

async function unisci(id) {
  const destinazione = Number(document.getElementById(`unisci-${id}`).value);
  if (!destinazione) return errorePersona(id, { data: { errore: "Scegli la persona giusta dall'elenco" } });
  const da = PERSONE.find(p => p.id === id), a = PERSONE.find(p => p.id === destinazione);
  if (!confirm(`Unire "${da.nome}" in "${a.nome}"? Dispositivi e proposte di "${da.nome}" passeranno a "${a.nome}", ` +
               `e "${da.nome}" sparirà.`)) return;
  const r = await api("POST", `/api/persone/${id}/unisci`, { in: destinazione });
  if (!r.ok) return errorePersona(id, r);
  aperta = null;
  toast("Profili uniti");
  carica();
}

async function eliminaPersona(id) {
  const persona = PERSONE.find(p => p.id === id);
  if (!confirm(`Eliminare ${persona.nome}? Spariranno anche le sue proposte in attesa.`)) return;
  const r = await api("DELETE", `/api/persone/${id}`);
  if (!r.ok) return errorePersona(id, r);
  aperta = null;
  toast("Persona eliminata");
  carica();
}

async function aggiungiPersona(evento) {
  evento.preventDefault();
  const f = evento.target;
  const errore = document.getElementById("errore-persona");
  if (f.nome.value.trim().length < 2) { errore.textContent = "Scrivi nome e iniziale del cognome"; return; }
  const r = await api("POST", "/api/persone", { nome: f.nome.value, ruolo_id: Number(f.ruolo_id.value) });
  if (!r.ok) { errore.textContent = r.data.errore || "Non è andata: riprova"; return; }
  errore.textContent = "";
  f.nome.value = "";
  await carica();
  if (r.data.attivazione) mostraAttivazione(r.data.attivazione);
  else toast("Aggiunta: la troverà nell'elenco al primo accesso");
}

// ------------------------------------------------------------ ruoli

function disegnaRuoli() {
  document.getElementById("elenco-ruoli").innerHTML = RUOLI.map(r => `
    <div class="scheda scheda-ruolo">
      <div class="testa-ruolo">
        <input class="campo" value="${esc(r.nome)}" maxlength="40" aria-label="Nome del ruolo"
               onchange="salvaRuolo(${r.id}, this.closest('.scheda-ruolo'))">
        <span class="meta">${r.persone} ${r.persone === 1 ? "persona" : "persone"}</span>
        ${!r.di_base && !r.persone ? `<button class="btn-icona pericolo" aria-label="Elimina ruolo" onclick="eliminaRuolo(${r.id})">${icona("trash")}</button>` : ""}
      </div>
      ${PERMESSI.map(([chiave, descrizione]) => `
        <label class="permesso"><input type="checkbox" data-permesso="${chiave}" ${r.permessi[chiave] ? "checked" : ""}
               onchange="salvaRuolo(${r.id}, this.closest('.scheda-ruolo'))"> ${esc(descrizione)}</label>`).join("")}
    </div>`).join("");
}

async function salvaRuolo(id, scheda) {
  const permessi = {};
  scheda.querySelectorAll("[data-permesso]").forEach(c => { permessi[c.dataset.permesso] = c.checked; });
  const nome = scheda.querySelector("input.campo").value;
  const r = await api("PATCH", `/api/ruoli/${id}`, { nome, permessi });
  const errore = document.getElementById("errore-ruolo");
  if (!r.ok) {
    errore.textContent = r.data.errore || "Non è andata: riprova";
    carica();   // rimetto le spunte com'erano
    return;
  }
  errore.textContent = "";
  RUOLI = r.data.ruoli;
  toast("Ruolo aggiornato");
  carica();   // i nomi dei ruoli compaiono anche nell'elenco delle persone
}

async function nuovoRuolo() {
  const r = await api("POST", "/api/ruoli");
  if (!r.ok) return toast(r.data.errore || "Non è andata: riprova");
  RUOLI = r.data.ruoli;
  disegna();
  // metto subito il cursore sul nome del nuovo ruolo, pronto da riscrivere
  const campi = document.querySelectorAll(".scheda-ruolo input.campo");
  campi[campi.length - 1].select();
}

async function eliminaRuolo(id) {
  const ruolo = RUOLI.find(r => r.id === id);
  if (!confirm(`Eliminare il ruolo "${ruolo.nome}"?`)) return;
  const r = await api("DELETE", `/api/ruoli/${id}`);
  if (!r.ok) return (document.getElementById("errore-ruolo").textContent = r.data.errore);
  carica();
}

carica();
