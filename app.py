"""Entry point dell'app Flask: pagine, file per il calendario, immagine di anteprima."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# Legge le variabili dal file .env (SECRET_KEY, chiave di gestione) e le mette
# in os.environ. Va fatto prima di tutto il resto. Il percorso è indicato per
# esteso perché su PythonAnywhere l'app viene avviata da un'altra cartella.
# override=True: i valori del file vincono sempre. Senza, al riavvio PythonAnywhere
# si portava dietro le chiavi già caricate e ignorava quelle nuove del file.
load_dotenv(Path(__file__).parent / ".env", override=True)

from flask import (Flask, Response, abort, g, jsonify, redirect,  # noqa: E402
                   render_template, request, send_file, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

import anteprima  # noqa: E402
import api  # noqa: E402
import api_persone  # noqa: E402
import api_riunione  # noqa: E402
import calendario  # noqa: E402
import database  # noqa: E402
import identita  # noqa: E402
import odg  # noqa: E402
from database import get_db  # noqa: E402

database.assicura_db()   # crea il database se manca, aggiunge le tabelle nuove

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
# Su PythonAnywhere l'app sta dietro un "proxy" che riceve le richieste in HTTPS
# e le passa a Flask. ProxyFix fa sì che Flask sappia che il visitatore è
# arrivato in HTTPS: serve per costruire link assoluti corretti (anteprima WhatsApp).
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.teardown_appcontext(database.close_db)
app.register_blueprint(api.bp)
app.register_blueprint(api_persone.bp)
app.register_blueprint(api_riunione.bp)


@app.before_request
def prima_di_ogni_richiesta():
    # Le azioni che modificano qualcosa devono arrivare come JSON dalle nostre
    # pagine. Un sito estraneo non può mandare JSON al nostro senza un permesso
    # esplicito del browser: così nessuno può far compiere azioni a chi è
    # riconosciuto da OdG facendogli aprire una pagina trappola.
    if request.path.startswith("/api/") and request.method != "GET" and not request.is_json:
        return jsonify(errore="Richiesta non valida"), 415
    identita.riconosci()   # chi sta usando l'app? (mette la persona in g.io)


@app.after_request
def niente_motori_di_ricerca(risposta):
    # Chiede a Google & co. di non mettere le pagine nei risultati di ricerca.
    # Non si usa robots.txt apposta: bloccherebbe anche WhatsApp, che allora
    # non riuscirebbe più a leggere la pagina per costruire l'anteprima.
    risposta.headers["X-Robots-Tag"] = "noindex, nofollow"
    return identita.scrivi_cookie(risposta)


@app.url_defaults
def versione_dei_file_statici(endpoint, valori):
    """Aggiunge a ogni file statico (JavaScript, stili, icone) un numero di
    versione: la data della sua ultima modifica, es. riunione.js?v=1758708575.
    Quando il file cambia cambia anche l'indirizzo, così i telefoni non
    continuano a usare la vecchia copia tenuta in memoria (cache)."""
    if endpoint == "static" and "filename" in valori:
        percorso = Path(app.static_folder) / valori["filename"]
        if percorso.is_file():
            valori["v"] = int(percorso.stat().st_mtime)


@app.context_processor
def variabili_comuni():
    """Variabili disponibili in tutti i template."""
    return {"io": g.get("io"), "puo": identita.puo, "compiti_aperti": len(miei_compiti())}


def miei_compiti(anche_fatti=False):
    """I compiti assegnati a chi sta usando l'app (per il pallino sull'avatar,
    la Home e il profilo). Calcolati una volta sola per richiesta."""
    if not g.get("io"):
        return []
    chiave = "compiti_tutti" if anche_fatti else "compiti_aperti"
    if chiave not in g:
        righe = get_db().execute(
            f"""SELECT c.*, r.codice AS riunione_codice, r.data AS riunione_data, t.nome AS tipo_nome
                FROM compiti c JOIN riunioni r ON r.id=c.riunione_id JOIN tipi_riunione t ON t.id=r.tipo_id
                WHERE c.persona_id=? {'' if anche_fatti else 'AND c.fatto_il IS NULL'}
                ORDER BY c.fatto_il IS NOT NULL, r.data DESC, c.id""",
            (g.io["id"],),
        ).fetchall()
        g.setdefault(chiave, [dict(r) for r in righe])
    return g.get(chiave)


# Funzioni usabili ovunque nei template, anche dentro i "mattoncini" di _macro.html
# (che non vedono le variabili della pagina, ma solo queste "globali")
app.jinja_env.globals["data_estesa"] = calendario.data_estesa


oggi = odg.oggi


@app.route("/api/ping")
def ping():
    return {"ok": True}


# ---------------------------------------------------------------- accessi speciali

@app.route("/entra/<chiave>")
def entra(chiave):
    """Link d'EMERGENZA: rende amministratore chi lo apre. Serve per il primo
    amministratore, o se tutti gli amministratori perdessero l'accesso.
    La chiave è nel file .env del server."""
    attesa = os.environ.get("ODG_CHIAVE_GESTIONE", "")
    # compare_digest confronta in tempo costante: non lascia indizi sulla chiave
    if not attesa or not secrets.compare_digest(chiave, attesa):
        abort(404)
    if g.io:   # dispositivo già riconosciuto: diventa subito amministratore
        db = get_db()
        db.execute("UPDATE persone SET ruolo_id=1 WHERE id=?", (g.io["id"],))
        db.commit()
        return redirect(url_for("home", benvenuto="amministratore"))
    # Non ancora riconosciuto: gli chiediamo il nome, e alla risposta diventa
    # amministratore (vedi "promuovi" in api_persone.presentati)
    session["promuovi"] = True
    return redirect(url_for("home", presentati=1))


@app.route("/i/<gettone>", methods=["GET", "POST"])
def usa_link_invito(gettone):
    """Link monouso: attivazione mandata da un amministratore, o "usa OdG anche
    su un altro dispositivo"."""
    db = get_db()
    persona_id = identita.invito_valido(db, gettone)
    if not persona_id:
        return render_template("link_scaduto.html"), 410
    if g.io and g.io["id"] == persona_id:          # questo dispositivo è già suo
        return redirect(url_for("home"))
    if g.io and request.method == "GET":
        # Il dispositivo appartiene a un'altra persona (es. l'amministratore apre
        # per sbaglio il link destinato a qualcun altro): chiedo conferma prima
        # di cambiare, e il link resta valido finché non si conferma.
        destinatario = db.execute("SELECT nome FROM persone WHERE id=?", (persona_id,)).fetchone()
        return render_template("conferma_cambio.html", destinatario=destinatario["nome"])
    identita.usa_invito(db, gettone)
    identita.lega_dispositivo(db, persona_id)
    db.commit()
    return redirect(url_for("home", benvenuto="collegato"))


# ---------------------------------------------------------------- pagine

@app.route("/")
def home():
    db = get_db()
    tipi = db.execute("SELECT * FROM tipi_riunione WHERE archiviato=0 ORDER BY nome").fetchall()
    # Per ogni tipo, la prossima riunione (la prima da oggi in avanti)
    prossime = {}
    for t in tipi:
        prossime[t["id"]] = db.execute(
            "SELECT * FROM riunioni WHERE tipo_id=? AND data>=? ORDER BY data, ora_inizio LIMIT 1",
            (t["id"], oggi()),
        ).fetchone()
    return render_template("home.html", tipi=tipi, prossime=prossime, compiti=miei_compiti())


@app.route("/t/<codice>")
def pagina_tipo(codice):
    db = get_db()
    tipo = db.execute("SELECT * FROM tipi_riunione WHERE codice=?", (codice,)).fetchone()
    if not tipo:
        abort(404)
    prossime = db.execute(
        "SELECT * FROM riunioni WHERE tipo_id=? AND data>=? ORDER BY data, ora_inizio",
        (tipo["id"], oggi()),
    ).fetchall()
    passate = db.execute(
        "SELECT * FROM riunioni WHERE tipo_id=? AND data<? ORDER BY data DESC, ora_inizio DESC",
        (tipo["id"], oggi()),
    ).fetchall()
    return render_template("tipo.html", tipo=tipo, prossime=prossime, passate=passate,
                           tipo_dati=dict(tipo))


def carica_riunione(codice):
    db = get_db()
    riunione = db.execute("SELECT * FROM riunioni WHERE codice=?", (codice,)).fetchone()
    if not riunione:
        abort(404)
    tipo = db.execute("SELECT * FROM tipi_riunione WHERE id=?", (riunione["tipo_id"],)).fetchone()
    punti = db.execute("SELECT * FROM punti WHERE riunione_id=? ORDER BY ordine",
                       (riunione["id"],)).fetchall()
    return riunione, tipo, punti


@app.route("/r/<codice>")
def pagina_riunione(codice):
    """La stessa pagina (e lo stesso link) cambia con la riunione: prima mostra
    l'ordine del giorno, durante la modalità riunione, dopo il verbale."""
    riunione, tipo, punti = carica_riunione(codice)
    db = get_db()
    url = url_for("pagina_riunione", codice=codice, _external=True)
    conclusa = riunione["stato"] == "conclusa"

    # Testi dell'anteprima WhatsApp (tag Open Graph nel template)
    minuti = sum(p["minuti"] for p in punti)
    quando = f"{calendario.data_estesa(riunione['data'])}, ore {riunione['ora_inizio']}"
    if conclusa:
        anteprima_titolo = f"Verbale: {tipo['nome']} - {calendario.data_estesa(riunione['data'])}"
        trattati = sum(1 for p in punti if p["spuntato_da"])
        anteprima_testo = f"{trattati} punt{'o' if trattati == 1 else 'i'} trattat{'o' if trattati == 1 else 'i'}"
    else:
        anteprima_titolo = f"{tipo['nome']} - {quando}"
        # Solo il numero di punti: luogo, data e associazione sono già nell'immagine
        anteprima_testo = (f"{len(punti)} punt{'o' if len(punti) == 1 else 'i'} all'ordine del giorno"
                           if punti else "Ordine del giorno in preparazione")
    return render_template(
        "riunione.html",
        riunione=riunione, tipo=tipo, punti=punti,
        passata=riunione["data"] < oggi(), minuti=minuti, url=url,
        anteprima_titolo=anteprima_titolo, anteprima_testo=anteprima_testo,
        # "?v=" cambia a ogni modifica: così l'immagine non resta quella vecchia in cache
        anteprima_img=url_for("immagine_anteprima", codice=codice, _external=True,
                              v=riunione["modificata_il"].replace(" ", "").replace(":", "")),
        link_google=calendario.link_google(riunione, tipo, punti, url),
        # Dati per il JavaScript della pagina (nel template passano dal filtro
        # "tojson", che li protegge anche se un titolo contiene caratteri strani)
        dati={
            **odg.stato(db, riunione["id"]), "tipo": dict(tipo),
            "url": url, "titolo_condivisione": anteprima_titolo, "passata": riunione["data"] < oggi(),
            "io": g.io,
        },
    )


@app.route("/r/<codice>/calendario.ics")
def ics_riunione(codice):
    riunione, tipo, punti = carica_riunione(codice)
    url = url_for("pagina_riunione", codice=codice, _external=True)
    return Response(
        calendario.file_ics(riunione, tipo, punti, url),
        mimetype="text/calendar",
        # "inline" (e non "attachment"): su iPhone apre direttamente la schermata
        # "Aggiungi al calendario" invece di scaricare un file da cercare poi.
        headers={"Content-Disposition": f'inline; filename="riunione-{codice}.ics"'},
    )


@app.route("/r/<codice>/anteprima.png")
def immagine_anteprima(codice):
    riunione, tipo, _ = carica_riunione(codice)
    risposta = send_file(anteprima.disegna(riunione, tipo), mimetype="image/png")
    risposta.headers["Cache-Control"] = "public, max-age=86400"
    return risposta


@app.route("/profilo")
def pagina_profilo():
    if not g.io:
        return redirect(url_for("home", presentati=1))
    return render_template("profilo.html", compiti=miei_compiti(anche_fatti=True))


@app.route("/persone")
def pagina_persone():
    if not identita.puo("persone"):
        abort(404)
    # Elenco di coppie (e non dizionario): passando alla pagina, Flask metterebbe
    # le chiavi di un dizionario in ordine alfabetico, mescolando i permessi
    return render_template("persone.html", permessi=list(identita.PERMESSI.items()))


@app.errorhandler(404)
def non_trovata(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    # debug=True: mostra gli errori in modo leggibile invece di una pagina bianca.
    # use_reloader=False: un solo processo stabile (come in Presenze).
    # Porta 5002: la 5000 è di Scrivania, la 5001 di Presenze.
    app.run(debug=True, use_reloader=False, port=5002)
