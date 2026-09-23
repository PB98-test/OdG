// Comandi di gestione: creare e modificare tipi di riunione e riunioni.
// Caricato solo per chi ha il permesso "riunioni" (i punti dell'OdG e le
// proposte stanno in riunione.js).

function mostraErrore(id, testo) {
  const el = document.getElementById(id);
  if (el) el.textContent = testo || "";
}

// ------------------------------------------------------------ tipi di riunione

let tipoInModifica = null;   // null = sto creando un tipo nuovo

function apriDialogTipo(tipo = null) {
  tipoInModifica = tipo;
  const dlg = document.getElementById("dlg-tipo");
  const f = dlg.querySelector("form");
  f.reset();
  document.getElementById("dlg-tipo-titolo").textContent = tipo ? "Modifica tipo di riunione" : "Nuovo tipo di riunione";
  document.getElementById("riga-archivia").style.display = tipo ? "" : "none";
  if (tipo) {
    for (const campo of ["nome", "sottotitolo", "luogo_abituale", "ora_abituale", "durata_abituale"]) {
      f[campo].value = tipo[campo] ?? "";
    }
    f.archiviato.checked = !!tipo.archiviato;
  }
  mostraErrore("dlg-tipo-errore");
  dlg.showModal();
}

async function salvaTipo(evento) {
  evento.preventDefault();
  const f = evento.target;
  const corpo = {
    nome: f.nome.value, sottotitolo: f.sottotitolo.value, luogo_abituale: f.luogo_abituale.value,
    ora_abituale: f.ora_abituale.value, durata_abituale: f.durata_abituale.value,
    archiviato: f.archiviato.checked,
  };
  const r = tipoInModifica
    ? await api("PATCH", `/api/tipi/${tipoInModifica.id}`, corpo)
    : await api("POST", "/api/tipi", corpo);
  if (!r.ok) return mostraErrore("dlg-tipo-errore", r.data.errore || "Salvataggio non riuscito");
  if (tipoInModifica) location.reload();
  else location.href = `/t/${r.data.codice}`;   // appena creato: vai alla sua pagina
}

// ------------------------------------------------------------ riunioni

let riunioneInModifica = null;   // null = sto fissando una riunione nuova
let tipoDellaRiunione = null;

/**
 * Apre la finestra della riunione.
 *   { tipo }            -> nuova riunione, con luogo e orario abituali del tipo
 *   { tipo, dopo }      -> "Fissa la prossima": luogo e orari ripresi dalla riunione "dopo"
 *   { tipo, riunione }  -> modifica di una riunione esistente
 */
function apriDialogRiunione({ tipo, riunione = null, dopo = null }) {
  riunioneInModifica = riunione;
  tipoDellaRiunione = tipo;
  const dlg = document.getElementById("dlg-riunione");
  const f = dlg.querySelector("form");
  f.reset();
  document.getElementById("dlg-riunione-titolo").textContent =
    riunione ? "Modifica riunione" : (dopo ? "Prossima riunione" : "Nuova riunione");
  document.getElementById("btn-elimina-riunione").style.display = riunione ? "" : "none";

  const base = riunione || dopo;
  f.data.value = riunione ? riunione.data : "";
  f.ora_inizio.value = base ? base.ora_inizio : (tipo.ora_abituale || "");
  f.ora_fine.value = base ? (base.ora_fine || "") : "";
  f.luogo.value = base ? (base.luogo || "") : (tipo.luogo_abituale || "");
  f.link_online.value = base ? (base.link_online || "") : "";
  f.note.value = riunione ? (riunione.note || "") : "";
  mostraErrore("dlg-riunione-errore");
  dlg.showModal();
}

async function salvaRiunione(evento) {
  evento.preventDefault();
  const f = evento.target;
  const corpo = {
    tipo_id: tipoDellaRiunione.id, data: f.data.value, ora_inizio: f.ora_inizio.value,
    ora_fine: f.ora_fine.value, luogo: f.luogo.value, link_online: f.link_online.value, note: f.note.value,
  };
  const r = riunioneInModifica
    ? await api("PATCH", `/api/riunioni/${riunioneInModifica.id}`, corpo)
    : await api("POST", "/api/riunioni", corpo);
  if (!r.ok) return mostraErrore("dlg-riunione-errore", r.data.errore || "Salvataggio non riuscito");
  if (riunioneInModifica) location.reload();
  else location.href = `/r/${r.data.codice}`;
}

async function eliminaRiunione() {
  if (!confirm("Eliminare questa riunione e il suo ordine del giorno? Non si può annullare.")) return;
  const r = await api("DELETE", `/api/riunioni/${riunioneInModifica.id}`);
  if (!r.ok) return mostraErrore("dlg-riunione-errore", r.data.errore || "Eliminazione non riuscita");
  location.href = `/t/${r.data.codice_tipo}`;
}

// ------------------------------------------------------------ contatori di caratteri
// I campi con "data-conta" (nome, sottotitolo, luogo) hanno un limite di lettere
// pensato per l'immagine di anteprima: sotto il campo compare "12/34".

function aggiornaContatore(campo) {
  let contatore = campo.nextElementSibling;
  if (!contatore || !contatore.classList.contains("contatore")) {
    contatore = document.createElement("span");
    contatore.className = "contatore";
    campo.after(contatore);
  }
  const usati = campo.value.length, massimo = campo.maxLength;
  contatore.textContent = `${usati}/${massimo}`;
  contatore.classList.toggle("pieno", usati >= massimo);
}

document.addEventListener("input", e => {
  if (e.target.matches("[data-conta]")) aggiornaContatore(e.target);
});
// All'apertura di una finestra i campi vengono riempiti dal codice (che non
// genera l'evento "input"): aggiorno i contatori appena la finestra compare.
for (const dlg of document.querySelectorAll("dialog")) {
  new MutationObserver(() => {
    if (dlg.open) dlg.querySelectorAll("[data-conta]").forEach(aggiornaContatore);
  }).observe(dlg, { attributes: true, attributeFilter: ["open"] });
}

