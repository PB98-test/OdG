"""API delle notifiche: attivarle su un dispositivo e scegliere per quali
tipi di riunione ricevere il promemoria del giorno prima."""
import json

from flask import Blueprint, g, jsonify, request

import notifiche
from database import get_db
from identita import richiede

bp = Blueprint("api_notifiche", __name__, url_prefix="/api/notifiche")


def errore(messaggio, codice=400):
    return jsonify(errore=messaggio), codice


@bp.get("/chiave")
def chiave_pubblica():
    """La chiave pubblica VAPID: il telefono la usa per iscriversi."""
    if not notifiche.attive():
        return errore("Le notifiche non sono ancora configurate sul server (manca genera_vapid.py)", 503)
    return {"chiave": notifiche.CHIAVE_PUBBLICA}


@bp.post("/iscrivi")
@richiede()
def iscrivi():
    """Salva il dispositivo e gli manda SUBITO una notifica di prova: così chi
    attiva sa con certezza se funziona, senza aspettare la prima riunione."""
    dati = request.get_json(silent=True) or {}
    if not dati.get("endpoint") or not dati.get("keys"):
        return errore("Iscrizione non valida")
    if not notifiche.attive():
        return errore("Le notifiche non sono ancora configurate sul server", 503)
    db = get_db()
    db.execute(
        """INSERT INTO iscrizioni_push (persona_id, endpoint, chiavi) VALUES (?,?,?)
           ON CONFLICT(endpoint) DO UPDATE SET persona_id=excluded.persona_id, chiavi=excluded.chiavi""",
        (g.io["id"], dati["endpoint"], json.dumps(dati["keys"])),
    )
    db.commit()
    riga = db.execute("SELECT * FROM iscrizioni_push WHERE endpoint=?", (dati["endpoint"],)).fetchone()
    riuscito = notifiche.invia(db, riga, "Notifiche attive",
                               "Se vedi questo messaggio funziona: il giorno prima delle riunioni che segui riceverai un promemoria.")
    return {"ok": True, "test_riuscito": riuscito}, 201


@bp.post("/disiscrivi")
@richiede()
def disiscrivi():
    endpoint = (request.get_json(silent=True) or {}).get("endpoint")
    if endpoint:
        db = get_db()
        db.execute("DELETE FROM iscrizioni_push WHERE endpoint=? AND persona_id=?", (endpoint, g.io["id"]))
        db.commit()
    return {"ok": True}


@bp.post("/segui")
@richiede()
def segui():
    """Attiva o toglie il promemoria per un tipo di riunione."""
    dati = request.get_json(silent=True) or {}
    db = get_db()
    tipo = db.execute("SELECT id FROM tipi_riunione WHERE id=?", (dati.get("tipo_id"),)).fetchone()
    if not tipo:
        return errore("Tipo di riunione non trovato", 404)
    if dati.get("segui"):
        db.execute("INSERT OR IGNORE INTO seguiti (persona_id, tipo_id) VALUES (?,?)", (g.io["id"], tipo["id"]))
    else:
        db.execute("DELETE FROM seguiti WHERE persona_id=? AND tipo_id=?", (g.io["id"], tipo["id"]))
    db.commit()
    return {"ok": True, "seguito": bool(dati.get("segui"))}


@bp.post("/prova")
@richiede()
def prova():
    db = get_db()
    ricevute = notifiche.invia_a_persona(db, g.io["id"], "Prova di OdG", "Le notifiche arrivano su questo dispositivo.")
    return {"ok": True, "dispositivi": ricevute}
