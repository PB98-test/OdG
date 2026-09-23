// Funzioni condivise da tutte le pagine: chiamate al server, avvisi, utilità.

/**
 * Chiama un'API di Flask. Restituisce sempre { ok, status, data }:
 * così il codice che la usa non deve gestire le eccezioni di fetch.
 *   api("POST", "/api/riunioni/3/punti", { titolo: "Bilancio", minuti: 15 })
 */
async function api(metodo, url, corpo) {
  try {
    const risposta = await fetch(url, {
      method: metodo,
      headers: corpo ? { "Content-Type": "application/json" } : {},
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
    const data = await risposta.json().catch(() => ({}));
    return { ok: risposta.ok, status: risposta.status, data };
  } catch (e) {
    return { ok: false, status: 0, data: { errore: "Connessione assente: riprova tra poco" } };
  }
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

// Chiude i "fogli" (Salva la data, Condividi) toccando lo sfondo scuro intorno
document.addEventListener("click", e => {
  if (e.target.tagName === "DIALOG" && e.target.classList.contains("foglio")) e.target.close();
});
