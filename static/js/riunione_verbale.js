// Pagina di una riunione: il verbale (dopo la conclusione).
// Lo stesso link che annunciava la riunione ora mostra questo riassunto.

/** Ora locale "21:05" da un orario del server in UTC ("2026-12-10 20:05:00"). */
function oraDaUtc(testo) {
  if (!testo) return "";
  return oraHHMM(new Date(testo.replace(" ", "T") + "Z"));
}

function durataMinuti() {
  const r = DATI.riunione;
  if (!r.iniziata_il || !r.conclusa_il) return null;
  return Math.round((new Date(r.conclusa_il.replace(" ", "T") + "Z") - new Date(r.iniziata_il.replace(" ", "T") + "Z")) / 60000);
}

function disegnaVerbale() {
  document.getElementById("barra-riunione").innerHTML = "";
  document.getElementById("compiti-precedenti").innerHTML = "";
  document.getElementById("form-punto").innerHTML = "";
  document.getElementById("proposte").innerHTML = "";
  const trattati = DATI.punti.filter(p => p.spuntato_da);
  const nonTrattati = DATI.punti.filter(p => !p.spuntato_da && !p.fisso);
  const varie = DATI.punti.find(p => p.fisso);
  const durata = durataMinuti();
  document.getElementById("totale-minuti").textContent = "";

  let html = `<li class="scheda riepilogo">
    ${icona("clock")} Dalle ${oraDaUtc(DATI.riunione.iniziata_il)} alle ${oraDaUtc(DATI.riunione.conclusa_il)}
    ${durata !== null ? `· ${durata} min (previsti ${minutiPrevisti()})` : ""}
  </li>`;
  html += trattati.filter(p => !p.fisso).map((p, i) => voceVerbale(p, i + 1)).join("");
  if (varie && (varie.spuntato_da || DATI.varie.length || varie.decisioni)) {
    html += voceVerbale(varie, trattati.filter(p => !p.fisso).length + 1);
  }
  if (nonTrattati.length) {
    html += `<li class="titolo-proposte">Non trattati</li>` + nonTrattati.map(p => {
      const d = p.destino;
      const dove = d && d.codice ? `riportato alla riunione del&nbsp;<a href="/r/${d.codice}">${dataBreve(d.data)}</a>`
        : d && d.in_attesa ? "riportato alla prossima riunione (ancora da fissare)"
        : "non riportato";
      return `<li class="punto non-trattato">${icona("arrow-back-up")}
        <span class="titolo">${esc(p.titolo)}<span class="firma">${dove}</span></span></li>`;
    }).join("");
  }
  document.getElementById("punti").innerHTML = html;
  disegnaProssimaDopo();
}

function voceVerbale(p, n) {
  const minuti = Math.round(p.trascorsi / 60);
  const compiti = DATI.compiti.filter(c => c.punto_id === p.id);
  const decisioni = PUO().verbale
    ? `<textarea class="decisioni" data-punto="${p.id}" placeholder="Decisioni prese" rows="2">${esc(p.decisioni || "")}</textarea>`
    : (p.decisioni ? `<div class="decisioni-testo"><b>Decisioni:</b> ${esc(p.decisioni)}</div>` : "");
  return `<li class="punto verbale">
    <span class="num">${n}</span>
    <span class="titolo">${esc(p.titolo)}
      <span class="firma">${p.spuntato_da ? `${minuti ? `${minuti} min · ` : ""}<span style="color:${esc(p.spuntato_da_colore)}">spuntato da ${esc(p.spuntato_da_nome)}</span>` : ""}</span>
    </span>
    <div class="dettagli-punto">
      ${p.fisso ? vociVarie(true) : ""}
      ${decisioni}
      ${compiti.length ? listaCompiti(compiti, PUO().verbale) : ""}
      ${PUO().verbale ? `<button class="btn-icona testo" onclick="apriCompito(${p.id})">${icona("plus")} Aggiungi un compito</button>` : ""}
    </div>
  </li>`;
}

function disegnaProssimaDopo() {
  const s = DATI.successiva;
  document.getElementById("prossima").innerHTML = s
    ? `<a class="collegamento" href="/r/${s.codice}">${icona("calendar-event")}
        <span class="corpo">Prossima riunione: <b style="font-weight: 500">${dataEstesa(s.data)}, ore ${s.ora_inizio}</b></span>${icona("chevron-right")}</a>`
    : "";
}

// ------------------------------------------------------------ testo del verbale

/** Il verbale come testo semplice, da incollare su WhatsApp o in un'email. */
function testoVerbale() {
  const r = DATI.riunione;
  const righe = [`VERBALE - ${DATI.tipo.nome}`, `${dataEstesa(r.data, true)}`];
  const durata = durataMinuti();
  if (r.iniziata_il) righe.push(`Dalle ${oraDaUtc(r.iniziata_il)} alle ${oraDaUtc(r.conclusa_il)}${durata !== null ? ` (${durata} min)` : ""}`);
  if (DATI.presenti.length) righe.push(`Presenti: ${DATI.presenti.map(p => p.nome).join(", ")}`);
  righe.push("");
  let n = 0;
  for (const p of DATI.punti.filter(x => x.spuntato_da || (x.fisso && DATI.varie.length))) {
    righe.push(`${++n}. ${p.titolo}`);
    if (p.fisso) DATI.varie.forEach(v => righe.push(`   - ${v.testo}${v.persona_nome ? ` (${v.persona_nome})` : ""}`));
    if (p.decisioni) righe.push(`   Decisioni: ${p.decisioni}`);
    DATI.compiti.filter(c => c.punto_id === p.id)
      .forEach(c => righe.push(`   Compito: ${c.persona_nome ? c.persona_nome + " - " : ""}${c.testo}`));
  }
  const nonTrattati = DATI.punti.filter(p => !p.spuntato_da && !p.fisso);
  if (nonTrattati.length) {
    righe.push("", "Non trattati (riportati alla prossima riunione):");
    nonTrattati.forEach(p => righe.push(`- ${p.titolo}`));
  }
  if (DATI.successiva) righe.push("", `Prossima riunione: ${dataEstesa(DATI.successiva.data)}, ore ${DATI.successiva.ora_inizio}`);
  righe.push("", DATI.url);
  return righe.join("\n");
}

async function condividiVerbale() {
  const testo = testoVerbale();
  if (navigator.share) {
    try { await navigator.share({ title: DATI.titolo_condivisione, text: testo }); return; }
    catch (e) { if (e.name === "AbortError") return; }
  }
  window.open("https://wa.me/?text=" + encodeURIComponent(testo), "_blank");
}

async function copiaVerbale() {
  try {
    await navigator.clipboard.writeText(testoVerbale());
    toast("Verbale copiato");
  } catch (e) {
    prompt("Copia il verbale:", testoVerbale());
  }
}
