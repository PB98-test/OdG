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
    segnaOffline(true);
    return { ok: false, status: 0, data: { errore: "Connessione assente: riprova tra poco" } };
  }
  segnaOffline(false);
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

// ------------------------------------------------------------ senza rete

/** Mostra o nasconde la striscia "Sei senza rete" in cima alla pagina. */
function segnaOffline(offline) {
  document.body.classList.toggle("offline", offline);
}
window.addEventListener("offline", () => segnaOffline(true));
window.addEventListener("online", () => segnaOffline(false));
if (!navigator.onLine) segnaOffline(true);

// ------------------------------------------------------------ installare l'app

/**
 * Su Android (Chrome, Edge, Samsung) il browser offre un evento per mostrare
 * il suo "Installa app": lo teniamo da parte per il nostro pulsante.
 * Su iPhone non esiste: lì si spiega come fare da Safari.
 */
let _richiestaInstallazione = null;
const giaInstallata = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
const suIphone = () => /iphone|ipad|ipod/i.test(navigator.userAgent);

window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  _richiestaInstallazione = e;
  mostraInstalla();
});

/** Riempie il riquadro #installa (se la pagina ce l'ha) con il modo giusto per questo telefono. */
function mostraInstalla() {
  const box = document.getElementById("installa");
  if (!box || giaInstallata()) return;
  try { if (box.dataset.chiudibile && localStorage.getItem("odg_installa_chiuso")) return; } catch (e) { /* niente */ }
  const chiudi = box.dataset.chiudibile
    ? `<button class="btn btn-tenue btn-piccolo" onclick="chiudiInstalla()">Non ora</button>` : "";
  if (_richiestaInstallazione) {
    box.innerHTML = `<div class="scheda installa">
      <b>Installa OdG sul telefono</b>
      <span class="nota" style="margin: 0">Avrai l'icona nella schermata Home, come un'app, e le pagine già viste anche senza rete.</span>
      <div class="azioni"><button class="btn btn-blu" onclick="installa()">${icona("download")} Installa</button>${chiudi}</div>
    </div>`;
  } else if (suIphone()) {
    box.innerHTML = `<div class="scheda installa">
      <b>Installa OdG sull'iPhone</b>
      <ol class="passi">
        <li>Apri questa pagina con <b>Safari</b></li>
        <li>Tocca il pulsante <b>Condividi</b> (il quadrato con la freccia in su)</li>
        <li>Scegli <b>Aggiungi alla schermata Home</b></li>
      </ol>
      ${chiudi ? `<div class="azioni">${chiudi}</div>` : ""}
    </div>`;
  }
}

async function installa() {
  if (!_richiestaInstallazione) return;
  _richiestaInstallazione.prompt();
  const { outcome } = await _richiestaInstallazione.userChoice;
  _richiestaInstallazione = null;
  if (outcome === "accepted") { document.getElementById("installa").innerHTML = ""; toast("OdG installata"); }
}

function chiudiInstalla() {
  try { localStorage.setItem("odg_installa_chiuso", "1"); } catch (e) { /* niente */ }
  document.getElementById("installa").innerHTML = "";
}

document.addEventListener("DOMContentLoaded", mostraInstalla);

// ------------------------------------------------------------ notifiche

/** La chiave pubblica arriva come testo; il browser la vuole come sequenza di byte. */
function base64UrlABytes(base64) {
  const riempimento = "=".repeat((4 - (base64.length % 4)) % 4);
  const testo = atob((base64 + riempimento).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...testo].map(c => c.charCodeAt(0)));
}

function notificheSupportate() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** L'iscrizione alle notifiche di questo dispositivo (o null). */
async function iscrizioneAttuale() {
  if (!notificheSupportate()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

/** Prima di tutto bisogna sapere chi sei (le notifiche sono personali). */
async function assicuraIdentita() {
  if (IO_ID) return true;
  return chiediNome();
}

/**
 * Attiva le notifiche su questo dispositivo: chiede il permesso al telefono,
 * iscrive il dispositivo e fa arrivare subito una notifica di prova.
 * Restituisce true se tutto è andato bene.
 */
async function attivaNotifiche() {
  if (suIphone() && !giaInstallata()) {
    alert("Su iPhone le notifiche funzionano solo con OdG installata nella schermata Home.\n\n" +
          "Da Safari: tocca Condividi (il quadrato con la freccia) e poi \"Aggiungi alla schermata Home\". " +
          "Poi apri OdG dall'icona e riprova.");
    return false;
  }
  if (!notificheSupportate()) { toast("Questo browser non supporta le notifiche"); return false; }
  if (!(await assicuraIdentita())) return false;
  const permesso = await Notification.requestPermission();
  if (permesso !== "granted") {
    toast("Notifiche non permesse: si possono riattivare dalle impostazioni del telefono");
    return false;
  }
  const chiave = await api("GET", "/api/notifiche/chiave");
  if (!chiave.ok) { toast(chiave.data.errore || "Notifiche non disponibili"); return false; }
  const reg = await navigator.serviceWorker.ready;
  let iscrizione;
  try {
    iscrizione = await reg.pushManager.subscribe({
      userVisibleOnly: true,   // obbligatorio: ogni messaggio deve diventare una notifica visibile
      applicationServerKey: base64UrlABytes(chiave.data.chiave),
    });
  } catch (e) {
    toast("Il telefono non ha permesso l'iscrizione alle notifiche");
    return false;
  }
  const r = await api("POST", "/api/notifiche/iscrivi", iscrizione.toJSON(), true);
  if (!r.ok) { toast(r.data.errore || "Non è andata: riprova"); return false; }
  toast(r.data.test_riuscito ? "Notifiche attive: dovrebbe arrivarti una prova"
                             : "Iscrizione salvata, ma la prova non è partita: avvisa l'amministratore");
  return true;
}

async function disattivaNotifiche() {
  const iscrizione = await iscrizioneAttuale();
  if (iscrizione) {
    await api("POST", "/api/notifiche/disiscrivi", { endpoint: iscrizione.endpoint }, true);
    await iscrizione.unsubscribe();
  }
  toast("Notifiche disattivate su questo dispositivo");
}

/**
 * "Avvisami il giorno prima" per un tipo di riunione. Se il dispositivo non
 * ha ancora le notifiche attive, le attiva prima.
 * Restituisce il nuovo stato (true = seguito), o null se non è cambiato.
 */
async function seguiTipo(tipoId, segui) {
  if (segui) {
    if (!(await assicuraIdentita())) return null;
    if (!(await iscrizioneAttuale()) && !(await attivaNotifiche())) return null;
  }
  const r = await api("POST", "/api/notifiche/segui", { tipo_id: tipoId, segui }, true);
  if (!r.ok) { toast(r.data.errore || "Non è andata: riprova"); return null; }
  if (!segui) toast("Promemoria tolto");
  else toast("Promemoria attivo: ti avviseremo il giorno prima");
  return r.data.seguito;
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
