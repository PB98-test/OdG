// Comandi di gestione: creare e modificare tipi di riunione, riunioni e punti.
// Questo file viene caricato solo quando il browser è entrato in gestione.

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

// ------------------------------------------------------------ punti dell'OdG
// Solo nella pagina della riunione (dove esiste DATI): l'elenco viene ridisegnato
// con i comandi per modificare, spostare ed eliminare ogni punto.

let puntoInModifica = null;   // id del punto che si sta modificando (uno alla volta)

function disegnaPunti() {
  const elenco = document.getElementById("punti");
  const punti = DATI.punti;
  const totale = punti.reduce((somma, p) => somma + p.minuti, 0);
  document.getElementById("totale-minuti").textContent = totale ? `${totale} min previsti` : "";
  if (!punti.length) {
    elenco.innerHTML = `<li class="scheda vuoto">Aggiungi il primo punto qui sotto.</li>`;
    return;
  }
  elenco.innerHTML = punti.map((p, i) => {
    if (p.id === puntoInModifica) {
      return `<li class="punto gestibile">
        <form class="nuovo-punto" style="margin: 0; flex: 1" onsubmit="salvaPunto(event, ${p.id})">
          <input type="text" name="titolo" maxlength="200" value="${esc(p.titolo)}" aria-label="Titolo">
          <input type="number" name="minuti" min="1" max="600" value="${p.minuti}" style="width: 72px" aria-label="Minuti">
          <button class="btn btn-blu" aria-label="Salva">${icona("check")}</button>
          <button type="button" class="btn btn-tenue" aria-label="Annulla" onclick="modificaPunto(null)">${icona("x")}</button>
        </form>
      </li>`;
    }
    return `<li class="punto gestibile">
      <span class="num">${i + 1}</span>
      <span class="titolo">${esc(p.titolo)}</span>
      <span class="pillola">${p.minuti} min</span>
      <span class="comandi-punto">
        <button class="btn-icona" aria-label="Sposta su" onclick="spostaPunto(${p.id}, -1)" ${i === 0 ? "disabled style='opacity:.3'" : ""}>${icona("arrow-up")}</button>
        <button class="btn-icona" aria-label="Sposta giù" onclick="spostaPunto(${p.id}, 1)" ${i === punti.length - 1 ? "disabled style='opacity:.3'" : ""}>${icona("arrow-down")}</button>
        <button class="btn-icona" aria-label="Modifica" onclick="modificaPunto(${p.id})">${icona("pencil")}</button>
        <button class="btn-icona pericolo" aria-label="Elimina" onclick="eliminaPunto(${p.id})">${icona("trash")}</button>
      </span>
    </li>`;
  }).join("");
}

/** Dopo ogni modifica il server restituisce l'elenco aggiornato: lo ridisegno. */
function aggiorna(r) {
  if (!r.ok) {
    mostraErrore("errore-punto", r.data.errore || "Modifica non riuscita");
    return false;
  }
  mostraErrore("errore-punto");
  DATI.punti = r.data.punti;
  disegnaPunti();
  return true;
}

async function aggiungiPunto(evento) {
  evento.preventDefault();
  const f = evento.target;
  if (!f.titolo.value.trim()) return mostraErrore("errore-punto", "Scrivi il titolo del punto");
  const r = await api("POST", `/api/riunioni/${DATI.riunione.id}/punti`,
                      { titolo: f.titolo.value, minuti: f.minuti.value });
  if (aggiorna(r)) {
    f.titolo.value = "";
    f.titolo.focus();   // pronto per scrivere subito il punto successivo
  }
}

function modificaPunto(id) {
  puntoInModifica = id;
  disegnaPunti();
  if (id) document.querySelector("#punti input[name=titolo]").focus();
}

async function salvaPunto(evento, id) {
  evento.preventDefault();
  const f = evento.target;
  if (!f.titolo.value.trim()) return mostraErrore("errore-punto", "Il titolo non può essere vuoto");
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

// Cancella l'avviso di errore appena si ricomincia a scrivere
document.addEventListener("input", e => {
  if (e.target.closest(".nuovo-punto")) mostraErrore("errore-punto");
});

if (typeof DATI !== "undefined" && document.getElementById("punti")) disegnaPunti();
