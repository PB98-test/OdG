// Funzioni condivise da tutte le pagine: chiamate al server, "Come ti chiami?",
// avvisi, utilità.

/**
 * Chiama un'API di Flask. Restituisce sempre { ok, status, data }:
 * così il codice che la usa non deve gestire le eccezioni di fetch.
 *   api("POST", "/api/riunioni/3/proposte", { tipo: "aggiungi", titolo: "Bilancio" })
 * Se il server risponde "prima dicci come ti chiami", apre la finestra del nome
 * e, appena la persona si è presentata, ripete l'azione e ricarica la pagina.
 */
async function api(metodo, url, corpo, giaRiprovato = false) {
  let risposta, data;
  try {
    risposta = await fetch(url, {
      method: metodo,
      // Le azioni che modificano qualcosa viaggiano sempre come JSON: il server
      // rifiuta le altre (è una protezione contro le pagine trappola).
      headers: metodo !== "GET" ? { "Content-Type": "application/json" } : {},
      body: metodo !== "GET" ? JSON.stringify(corpo || {}) : undefined,
    });
    data = await risposta.json().catch(() => ({}));
  } catch (e) {
    return { ok: false, status: 0, data: { errore: "Connessione assente: riprova tra poco" } };
  }
  if (risposta.status === 401 && data.chi_sei && !giaRiprovato) {
    if (await chiediNome()) {
      const seconda = await api(metodo, url, corpo, true);
      location.reload();   // la pagina ora deve sapere chi sei (colori, "ritira"...)
      return seconda;
    }
  }
  return { ok: risposta.ok, status: risposta.status, data };
}

let _timerToast;
function toast(messaggio) {
  const t = document.getElementById("toast");
  t.textContent = messaggio;
  t.style.display = "block";
  clearTimeout(_timerToast);
  _timerToast = setTimeout(() => { t.style.display = "none"; }, 2800);
}

/** Protegge il testo prima di inserirlo nell'HTML (evita che un titolo con < > rompa la pagina). */
function esc(testo) {
  return String(testo ?? "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** Icona dal file delle icone, come la macro ic() dei template. */
function icona(nome) {
  return `<svg class="ic" aria-hidden="true"><use href="${ICONE}#${nome}"></use></svg>`;
}

/** Pallino colorato di una persona. */
function pallino(colore) {
  return `<span class="pallino" style="background:${esc(colore)}"></span>`;
}

// Chiude i "fogli" (Salva la data, Condividi) toccando lo sfondo scuro intorno
document.addEventListener("click", e => {
  if (e.target.tagName === "DIALOG" && e.target.classList.contains("foglio")) e.target.close();
});

// ------------------------------------------------------------ "Come ti chiami?"

let _risolviNome = null;   // la "promessa" in attesa che la persona si presenti

/**
 * Apre la finestra del nome. Restituisce una promessa che vale true quando la
 * persona si è presentata, false se ha annullato.
 */
async function chiediNome() {
  const dlg = document.getElementById("dlg-presentati");
  const f = dlg.querySelector("form");
  f.reset();
  document.getElementById("presentati-errore").textContent = "";
  // Profili creati in anticipo dagli amministratori, tra cui scegliere
  const r = await api("GET", "/api/presentati");
  const persone = r.ok ? r.data.persone : [];
  document.getElementById("presentati-elenco-box").style.display = persone.length ? "" : "none";
  document.getElementById("presentati-elenco").innerHTML = persone.map(p =>
    `<button type="button" class="scelta-persona" onclick="presentati({persona_id: ${p.id}})">
       ${pallino(p.colore)} ${esc(p.nome)}</button>`).join("");
  dlg.showModal();
  return new Promise(risolvi => { _risolviNome = risolvi; });
}

async function presentati(corpo) {
  const r = await api("POST", "/api/presentati", corpo, true);
  if (!r.ok) {
    document.getElementById("presentati-errore").textContent = r.data.errore || "Non è andata: riprova";
    return;
  }
  const risolvi = _risolviNome;
  _risolviNome = null;
  document.getElementById("dlg-presentati").close();
  if (risolvi) risolvi(true);
  else location.reload();
}

function inviaNome(evento) {
  evento.preventDefault();
  const nome = evento.target.nome.value.trim();
  if (nome.length < 2) {
    document.getElementById("presentati-errore").textContent = "Scrivi il tuo nome e l'iniziale del cognome";
    return;
  }
  presentati({ nome });
}

function annullaNome() {
  document.getElementById("dlg-presentati").close();
  if (_risolviNome) _risolviNome(false);
  _risolviNome = null;
}

// ------------------------------------------------------------ i miei compiti

/** Casella "fatto" nell'elenco dei propri compiti (Home e profilo). */
async function fattoMio(id, fatto) {
  const r = await api("POST", `/api/compiti/${id}/fatto`, { fatto });
  if (!r.ok) return toast(r.data.errore || "Non è andata: riprova");
  toast(fatto ? "Compito fatto" : "Compito di nuovo da fare");
  setTimeout(() => location.reload(), 600);   // aggiorna il pallino sull'avatar
}

// ------------------------------------------------------------ link monouso

/** Mostra la finestra con QR code e link (vedi _dialog_link.html). */
function mostraLink(titolo, testo, dati) {
  document.getElementById("dlg-link-titolo").textContent = titolo;
  document.getElementById("dlg-link-testo").textContent = testo;
  // Il QR è un disegno SVG prodotto dal nostro server a partire dal link
  document.getElementById("dlg-link-qr").innerHTML = dati.qr;
  document.getElementById("dlg-link-url").value = dati.link;
  document.getElementById("dlg-link").showModal();
}

async function condividiLinkMonouso() {
  const link = document.getElementById("dlg-link-url").value;
  if (navigator.share) {
    try { await navigator.share({ title: "OdG", text: "Il tuo link per entrare in OdG:", url: link }); return; }
    catch (e) { if (e.name === "AbortError") return; }
  }
  window.open("https://wa.me/?text=" + encodeURIComponent("Il tuo link per entrare in OdG:\n" + link), "_blank");
}

async function copiaLinkMonouso() {
  const campo = document.getElementById("dlg-link-url");
  try { await navigator.clipboard.writeText(campo.value); toast("Link copiato"); }
  catch (e) { campo.select(); }
}

// Messaggi e aperture automatiche indicati nell'indirizzo (?presentati=1, ?benvenuto=...)
(function () {
  const q = new URLSearchParams(location.search);
  const benvenuto = { amministratore: "Ora sei amministratore", collegato: "Fatto: questo dispositivo ora è collegato a te" };
  if (benvenuto[q.get("benvenuto")]) toast(benvenuto[q.get("benvenuto")]);
  if (q.has("presentati")) chiediNome().then(ok => { if (ok) location.replace(location.pathname); });
  // Tolgo i parametri dall'indirizzo, così ricaricando non si ripetono
  if (q.has("benvenuto")) history.replaceState(null, "", location.pathname);
})();
