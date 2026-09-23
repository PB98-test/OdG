"""Entry point dell'app Flask: pagine, file per il calendario, immagine di anteprima."""
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Legge le variabili dal file .env (SECRET_KEY, chiave di gestione) e le mette
# in os.environ. Va fatto prima di tutto il resto. Il percorso è indicato per
# esteso perché su PythonAnywhere l'app viene avviata da un'altra cartella.
# override=True: i valori del file vincono sempre. Senza, al riavvio PythonAnywhere
# si portava dietro le chiavi già caricate e ignorava quelle nuove del file.
load_dotenv(Path(__file__).parent / ".env", override=True)

from flask import (Flask, Response, abort, redirect, render_template,  # noqa: E402
                   send_file, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

import anteprima  # noqa: E402
import api  # noqa: E402
import calendario  # noqa: E402
import database  # noqa: E402
from database import get_db  # noqa: E402

database.assicura_db()   # crea il database se manca, aggiunge le tabelle nuove

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
# Il "ricordami" della gestione dura un anno: non serve rientrare ogni volta
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)
# Su PythonAnywhere l'app sta dietro un "proxy" che riceve le richieste in HTTPS
# e le passa a Flask. ProxyFix fa sì che Flask sappia che il visitatore è
# arrivato in HTTPS: serve per costruire link assoluti corretti (anteprima WhatsApp).
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.teardown_appcontext(database.close_db)
app.register_blueprint(api.bp)


@app.after_request
def niente_motori_di_ricerca(risposta):
    # Chiede a Google & co. di non mettere le pagine nei risultati di ricerca.
    # Non si usa robots.txt apposta: bloccherebbe anche WhatsApp, che allora
    # non riuscirebbe più a leggere la pagina per costruire l'anteprima.
    risposta.headers["X-Robots-Tag"] = "noindex, nofollow"
    return risposta


@app.context_processor
def variabili_comuni():
    """Variabili disponibili in tutti i template."""
    return {"gestione": bool(session.get("gestione"))}


# Funzioni usabili ovunque nei template, anche dentro i "mattoncini" di _macro.html
# (che non vedono le variabili della pagina, ma solo queste "globali")
app.jinja_env.globals["data_estesa"] = calendario.data_estesa


def oggi():
    return datetime.now(calendario.ROMA).strftime("%Y-%m-%d")


@app.route("/api/ping")
def ping():
    return {"ok": True}


# ---------------------------------------------------------------- gestione
# Finché non costruiamo persone e ruoli (tappa 3), chi gestisce entra con un
# link segreto: /entra/<chiave>, con la chiave scritta nel file .env.
# Il browser se lo ricorda per un anno.

@app.route("/entra/<chiave>")
def entra(chiave):
    attesa = os.environ.get("ODG_CHIAVE_GESTIONE", "")
    # compare_digest confronta in tempo costante: non lascia indizi sulla chiave
    if not attesa or not secrets.compare_digest(chiave, attesa):
        abort(404)
    session.permanent = True
    session["gestione"] = True
    return redirect(url_for("home"))


@app.route("/esci")
def esci():
    session.pop("gestione", None)
    return redirect(url_for("home"))


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
    return render_template("home.html", tipi=tipi, prossime=prossime)


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
    riunione, tipo, punti = carica_riunione(codice)
    db = get_db()
    url = url_for("pagina_riunione", codice=codice, _external=True)
    # Riunione successiva dello stesso tipo, per il collegamento in fondo alla pagina
    successiva = db.execute(
        """SELECT * FROM riunioni WHERE tipo_id=? AND (data>? OR (data=? AND ora_inizio>?))
           ORDER BY data, ora_inizio LIMIT 1""",
        (tipo["id"], riunione["data"], riunione["data"], riunione["ora_inizio"]),
    ).fetchone()

    # Testi dell'anteprima WhatsApp (tag Open Graph nel template)
    minuti = sum(p["minuti"] for p in punti)
    anteprima_titolo = f"{tipo['nome']} - {calendario.data_estesa(riunione['data'])}, ore {riunione['ora_inizio']}"
    # Solo il numero di punti: luogo, data e associazione sono già nell'immagine
    if punti:
        anteprima_testo = f"{len(punti)} punt{'o' if len(punti) == 1 else 'i'} all'ordine del giorno"
    else:
        anteprima_testo = "Ordine del giorno in preparazione"
    return render_template(
        "riunione.html",
        riunione=riunione, tipo=tipo, punti=punti, successiva=successiva,
        passata=riunione["data"] < oggi(), minuti=minuti, url=url,
        anteprima_titolo=anteprima_titolo, anteprima_testo=anteprima_testo,
        # "?v=" cambia a ogni modifica: così l'immagine non resta quella vecchia in cache
        anteprima_img=url_for("immagine_anteprima", codice=codice, _external=True,
                              v=riunione["modificata_il"].replace(" ", "").replace(":", "")),
        link_google=calendario.link_google(riunione, tipo, punti, url),
        # Dati per il JavaScript della pagina (nel template passano dal filtro
        # "tojson", che li protegge anche se un titolo contiene caratteri strani)
        dati={
            "riunione": dict(riunione), "tipo": dict(tipo),
            "punti": [dict(p) for p in punti], "url": url, "titolo_condivisione": anteprima_titolo,
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


@app.errorhandler(404)
def non_trovata(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    # debug=True: mostra gli errori in modo leggibile invece di una pagina bianca.
    # use_reloader=False: un solo processo stabile (come in Presenze).
    # Porta 5002: la 5000 è di Scrivania, la 5001 di Presenze.
    app.run(debug=True, use_reloader=False, port=5002)
