// Pagina di una riunione: condivisione e copia del link.
// (I comandi per modificare l'OdG stanno in gestione.js, caricato solo in gestione.)

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
