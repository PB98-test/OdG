"""API della riunione "dal vivo": inizio, spunte, timer, verbale, compiti,
Varie e conclusione.

Regole principali (decise con Pietro):
- inizia e conclude chi ha il permesso "conclude"; "Inizia" solo da 3 ore prima;
- spuntare e usare il timer: chiunque si sia presentato; la spunta la toglie
  chi l'ha messa o chi ha il permesso "odg";
- decisioni e compiti: permesso "verbale" (di base lo hanno tutti);
- Varie: chiunque aggiunge le sue voci direttamente, fino alla conclusione.
"""
from flask import Blueprint, g, jsonify, request

import identita
import odg
from api import campi_riunione, testo
from api_persone import pulisci_nome
from database import get_db
from identita import puo, richiede
from odg import adesso_utc, ferma_timer, stato, testo_utc

bp = Blueprint("api_riunione", __name__, url_prefix="/api")


def errore(messaggio, codice=400):
    return jsonify(errore=messaggio), codice


NON_IN_CORSO = "La riunione non è in corso"


def punto_e_riunione(db, punto_id):
    return db.execute(
        "SELECT p.*, r.stato AS stato_riunione FROM punti p JOIN riunioni r ON r.id=p.riunione_id WHERE p.id=?",
        (punto_id,),
    ).fetchone()


# ---------------------------------------------------------------- inizio e conclusione

@bp.post("/riunioni/<int:riunione_id>/inizia")
@richiede("conclude")
def inizia(riunione_id):
    db = get_db()
    riunione = db.execute("SELECT * FROM riunioni WHERE id=?", (riunione_id,)).fetchone()
    if not riunione:
        return errore("Riunione non trovata", 404)
    tipo = db.execute("SELECT * FROM tipi_riunione WHERE id=?", (riunione["tipo_id"],)).fetchone()
    if not odg.si_puo_iniziare(riunione, tipo):
        return errore(f"La riunione si può iniziare da {odg.ORE_PRIMA_DI_INIZIARE} ore prima dell'orario fissato")
    db.execute("UPDATE riunioni SET stato='in_corso', iniziata_il=? WHERE id=?",
               (testo_utc(adesso_utc()), riunione_id))
    # Chi fa partire la riunione è sicuramente presente
    db.execute("INSERT OR IGNORE INTO presenze (riunione_id, persona_id, segnato_da) VALUES (?,?,?)",
               (riunione_id, g.io["id"], g.io["id"]))
    db.commit()
    return stato(db, riunione_id)


@bp.post("/riunioni/<int:riunione_id>/concludi")
@richiede("conclude")
def concludi(riunione_id):
    """Conclude la riunione:
    - i punti non trattati scelti vanno nella riunione successiva (se è già
      fissata) oppure restano "in attesa" della prossima che verrà creata;
    - se indicata, fissa la prossima riunione ("Quando ci vediamo?")."""
    dati = request.get_json(silent=True) or {}
    db = get_db()
    riunione = db.execute("SELECT * FROM riunioni WHERE id=?", (riunione_id,)).fetchone()
    if not riunione:
        return errore("Riunione non trovata", 404)
    if riunione["stato"] != "in_corso":
        return errore(NON_IN_CORSO)
    prossima = None
    if dati.get("prossima"):
        try:
            prossima = campi_riunione(dati["prossima"])
        except ValueError as e:
            return errore(str(e))

    ferma_timer(db, riunione_id)
    succ = odg.successiva(db, riunione)
    da_riportare = [int(i) for i in dati.get("riporta") or []]
    for p in db.execute("SELECT * FROM punti WHERE riunione_id=? AND fisso=0 AND spuntato_da IS NULL ORDER BY ordine",
                        (riunione_id,)).fetchall():
        if p["id"] not in da_riportare:
            continue
        if succ:
            odg.inserisci_punto(db, succ["id"], p["titolo"], p["minuti"], p["proposto_da"], p["id"])
        else:
            db.execute("INSERT INTO da_riportare (tipo_id, punto_id, titolo, minuti, proposto_da) VALUES (?,?,?,?,?)",
                       (riunione["tipo_id"], p["id"], p["titolo"], p["minuti"], p["proposto_da"]))

    codice_prossima = succ["codice"] if succ else None
    if prossima and not succ:
        # La nuova riunione si porta dentro da sola i punti appena messi "in attesa"
        codice_prossima = odg.crea_riunione(db, riunione["tipo_id"], prossima)

    db.execute("UPDATE riunioni SET stato='conclusa', conclusa_il=? WHERE id=?",
               (testo_utc(adesso_utc()), riunione_id))
    odg.toccata(db, riunione_id)
    db.commit()
    return dict(stato(db, riunione_id), codice_prossima=codice_prossima)


# ---------------------------------------------------------------- spunte e timer

@bp.post("/punti/<int:punto_id>/spunta")
@richiede()
def spunta(punto_id):
    vuole = bool((request.get_json(silent=True) or {}).get("spuntato"))
    db = get_db()
    p = punto_e_riunione(db, punto_id)
    if not p:
        return errore("Punto non trovato", 404)
    if p["stato_riunione"] != "in_corso":
        return errore(NON_IN_CORSO)
    if vuole and not p["spuntato_da"]:
        if p["timer_dal"]:      # spuntando un punto il suo timer si ferma
            ferma_timer(db, p["riunione_id"])
        db.execute("UPDATE punti SET spuntato_da=?, spuntato_il=datetime('now') WHERE id=?", (g.io["id"], punto_id))
    elif not vuole and p["spuntato_da"]:
        if p["spuntato_da"] != g.io["id"] and not puo("odg"):
            return errore("La spunta la può togliere chi l'ha messa", 403)
        db.execute("UPDATE punti SET spuntato_da=NULL, spuntato_il=NULL WHERE id=?", (punto_id,))
    db.commit()
    return stato(db, p["riunione_id"])


@bp.post("/punti/<int:punto_id>/timer")
@richiede()
def timer(punto_id):
    """azione "avvia" (mette in pausa l'eventuale altro timer acceso) o "pausa"."""
    azione = (request.get_json(silent=True) or {}).get("azione")
    db = get_db()
    p = punto_e_riunione(db, punto_id)
    if not p:
        return errore("Punto non trovato", 404)
    if p["stato_riunione"] != "in_corso":
        return errore(NON_IN_CORSO)
    ferma_timer(db, p["riunione_id"])     # un solo timer acceso alla volta
    if azione == "avvia":
        if p["spuntato_da"]:
            return errore("Il punto è già spuntato")
        db.execute("UPDATE punti SET timer_dal=? WHERE id=?", (testo_utc(adesso_utc()), punto_id))
    db.commit()
    return stato(db, p["riunione_id"])


# ---------------------------------------------------------------- verbale

@bp.patch("/punti/<int:punto_id>/decisioni")
@richiede("verbale")
def decisioni(punto_id):
    """Salvataggio automatico mentre si scrive: risponde solo "ok", così la
    pagina non viene ridisegnata sotto le dita di chi sta scrivendo."""
    db = get_db()
    p = punto_e_riunione(db, punto_id)
    if not p:
        return errore("Punto non trovato", 404)
    if p["stato_riunione"] == "in_programma":
        return errore(NON_IN_CORSO)
    db.execute("UPDATE punti SET decisioni=? WHERE id=?",
               (testo(request.get_json(silent=True) or {}, "testo", massimo=4000), punto_id))
    db.commit()
    return {"ok": True}


@bp.post("/punti/<int:punto_id>/compiti")
@richiede("verbale")
def aggiungi_compito(punto_id):
    dati = request.get_json(silent=True) or {}
    db = get_db()
    p = punto_e_riunione(db, punto_id)
    if not p:
        return errore("Punto non trovato", 404)
    if p["stato_riunione"] == "in_programma":
        return errore(NON_IN_CORSO)
    try:
        descrizione = testo(dati, "testo", obbligatorio=True, massimo=300)
    except ValueError:
        return errore("Scrivi che cosa c'è da fare")
    persona_id = dati.get("persona_id") or None
    if persona_id and not db.execute("SELECT 1 FROM persone WHERE id=?", (persona_id,)).fetchone():
        return errore("Persona non trovata")
    db.execute("INSERT INTO compiti (riunione_id, punto_id, testo, persona_id, creato_da) VALUES (?,?,?,?,?)",
               (p["riunione_id"], punto_id, descrizione, persona_id, g.io["id"]))
    db.commit()
    return stato(db, p["riunione_id"])


@bp.delete("/compiti/<int:compito_id>")
@richiede("verbale")
def elimina_compito(compito_id):
    db = get_db()
    c = db.execute("SELECT riunione_id FROM compiti WHERE id=?", (compito_id,)).fetchone()
    if not c:
        return errore("Compito non trovato", 404)
    db.execute("DELETE FROM compiti WHERE id=?", (compito_id,))
    db.commit()
    return stato(db, c["riunione_id"])


@bp.post("/compiti/<int:compito_id>/fatto")
@richiede()
def compito_fatto(compito_id):
    """Segna un compito come fatto (o di nuovo da fare): chi l'ha ricevuto,
    oppure chi può scrivere il verbale."""
    fatto = bool((request.get_json(silent=True) or {}).get("fatto"))
    db = get_db()
    c = db.execute("SELECT * FROM compiti WHERE id=?", (compito_id,)).fetchone()
    if not c:
        return errore("Compito non trovato", 404)
    if c["persona_id"] != g.io["id"] and not puo("verbale"):
        return errore("Solo chi ha ricevuto il compito può segnarlo come fatto", 403)
    if fatto:
        db.execute("UPDATE compiti SET fatto_il=datetime('now'), fatto_da=? WHERE id=?", (g.io["id"], compito_id))
    else:
        db.execute("UPDATE compiti SET fatto_il=NULL, fatto_da=NULL WHERE id=?", (compito_id,))
    db.commit()
    return {"ok": True}


@bp.get("/persone/nomi")
@richiede()
def nomi_persone():
    """Elenco dei nomi per scegliere a chi assegnare un compito o chi è presente.
    "attiva" = ha già fatto l'accesso almeno da un dispositivo."""
    righe = get_db().execute(
        """SELECT p.id, p.nome, p.colore,
                  EXISTS (SELECT 1 FROM dispositivi d WHERE d.persona_id=p.id) AS attiva
           FROM persone p ORDER BY p.nome COLLATE NOCASE"""
    ).fetchall()
    return {"persone": [dict(r) for r in righe]}


# ---------------------------------------------------------------- presenti

def riunione_per_presenti(db, riunione_id):
    """La riunione, se l'elenco dei presenti si può modificare (dall'inizio in poi)."""
    riunione = db.execute("SELECT * FROM riunioni WHERE id=?", (riunione_id,)).fetchone()
    if not riunione:
        return None, errore("Riunione non trovata", 404)
    if riunione["stato"] == "in_programma":
        return None, errore("I presenti si segnano quando la riunione è iniziata")
    return riunione, None


@bp.put("/riunioni/<int:riunione_id>/presenti")
@richiede("verbale")
def imposta_presenti(riunione_id):
    """Sostituisce l'elenco dei presenti con quello scelto nella finestra."""
    ids = {int(i) for i in (request.get_json(silent=True) or {}).get("persone") or []}
    db = get_db()
    _, problema = riunione_per_presenti(db, riunione_id)
    if problema:
        return problema
    esistenti = {r["id"] for r in db.execute("SELECT id FROM persone")}
    db.execute("DELETE FROM presenze WHERE riunione_id=?", (riunione_id,))
    db.executemany("INSERT INTO presenze (riunione_id, persona_id, segnato_da) VALUES (?,?,?)",
                   [(riunione_id, pid, g.io["id"]) for pid in ids & esistenti])
    db.commit()
    return stato(db, riunione_id)


@bp.post("/riunioni/<int:riunione_id>/presenti/io")
@richiede()
def ci_sono_anch_io(riunione_id):
    db = get_db()
    _, problema = riunione_per_presenti(db, riunione_id)
    if problema:
        return problema
    db.execute("INSERT OR IGNORE INTO presenze (riunione_id, persona_id, segnato_da) VALUES (?,?,?)",
               (riunione_id, g.io["id"], g.io["id"]))
    db.commit()
    return stato(db, riunione_id)


@bp.post("/riunioni/<int:riunione_id>/presenti/nuova")
@richiede("verbale")
def nuova_persona_presente(riunione_id):
    """Presente che non ha mai usato OdG: si crea la persona (Partecipante) e la
    si segna presente. Al suo primo accesso la troverà nell'elenco "Sei una di
    queste persone?", come i profili creati in anticipo dagli amministratori."""
    db = get_db()
    _, problema = riunione_per_presenti(db, riunione_id)
    if problema:
        return problema
    try:
        nome = pulisci_nome((request.get_json(silent=True) or {}).get("nome"))
    except ValueError as e:
        return errore(str(e))
    if db.execute("SELECT 1 FROM persone WHERE nome=? COLLATE NOCASE", (nome,)).fetchone():
        return errore("Questa persona c'è già: cercala nell'elenco", 409)
    persona_id = db.execute("INSERT INTO persone (nome, colore, ruolo_id) VALUES (?,?,2)",
                            (nome, identita.colore_libero(db))).lastrowid
    db.execute("INSERT INTO presenze (riunione_id, persona_id, segnato_da) VALUES (?,?,?)",
               (riunione_id, persona_id, g.io["id"]))
    db.commit()
    return dict(stato(db, riunione_id), nuova={"id": persona_id, "nome": nome}), 201


# ---------------------------------------------------------------- Varie

@bp.post("/riunioni/<int:riunione_id>/varie")
@richiede()
def aggiungi_varia(riunione_id):
    db = get_db()
    riunione = db.execute("SELECT * FROM riunioni WHERE id=?", (riunione_id,)).fetchone()
    if not riunione:
        return errore("Riunione non trovata", 404)
    if not odg.si_puo_proporre(riunione):
        return errore("Le Varie di questa riunione sono chiuse")
    try:
        voce = testo(request.get_json(silent=True) or {}, "testo", obbligatorio=True, massimo=200)
    except ValueError:
        return errore("Scrivi la tua voce")
    db.execute("INSERT INTO voci_varie (riunione_id, persona_id, testo) VALUES (?,?,?)",
               (riunione_id, g.io["id"], voce))
    db.commit()
    return stato(db, riunione_id), 201


@bp.delete("/varie/<int:voce_id>")
@richiede()
def elimina_varia(voce_id):
    db = get_db()
    v = db.execute("SELECT v.*, r.stato FROM voci_varie v JOIN riunioni r ON r.id=v.riunione_id WHERE v.id=?",
                   (voce_id,)).fetchone()
    if not v:
        return errore("Voce non trovata", 404)
    if v["stato"] == "conclusa":
        return errore("La riunione è conclusa")
    if v["persona_id"] != g.io["id"] and not puo("odg"):
        return errore("Puoi togliere solo le tue voci", 403)
    db.execute("DELETE FROM voci_varie WHERE id=?", (voce_id,))
    db.commit()
    return stato(db, v["riunione_id"])
