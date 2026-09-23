// Pagina di una riunione: condivisione e copia del link.
// (I comandi per modificare l'OdG stanno in gestione.js, caricato solo in gestione.)

const testoCondivisione = `${DATI.titolo_condivisione}\n${DATI.url}`;

// WhatsApp: il link "wa.me/?text=..." apre WhatsApp con il messaggio già scritto
// e lascia scegliere la chat o il gruppo a cui mandarlo.
document.getElementById("condividi-whatsapp").href =
  "https://wa.me/?text=" + encodeURIComponent(testoCondivisione);

// "Altre app": il menu di condivisione del telefono (esiste solo su telefoni e
// alcuni browser, per questo il pulsante compare solo se disponibile).
if (navigator.share) document.getElementById("condividi-altro").style.display = "";

async function condividiAltro() {
  try {
    await navigator.share({ title: DATI.titolo_condivisione, text: DATI.titolo_condivisione, url: DATI.url });
    document.getElementById("foglio-condividi").close();
  } catch (e) { /* condivisione annullata: non c'è niente da fare */ }
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
