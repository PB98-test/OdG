"""API per persone, ruoli e identità ("chi sono io").

- /api/presentati: la persona si presenta (nome nuovo o scelto dall'elenco)
- /api/io/...: il proprio profilo (altro dispositivo, uscita)
- /api/persone, /api/ruoli: gestione, per chi ha il permesso "persone"
"""
import re
from datetime import timedelta
from io import BytesIO

import segno
from flask import Blueprint, g, jsonify, request, session, url_for

import identita
from database import get_db
from identita import PERMESSI, richiede

bp = Blueprint("api_persone", __name__, url_prefix="/api")

RE_COLORE = re.compile(r"^#[0-9A-Fa-f]{6}$")
DURATA_ALTRO_DISPOSITIVO = timedelta(minutes=15)
DURATA_ATTIVAZIONE = timedelta(days=7)


def errore(messaggio, codice=400):
    return jsonify(errore=messaggio), codice


def pulisci_nome(valore):
    """Spazi doppi via; tra 2 e 30 caratteri."""
    nome = " ".join(str(valore or "").split())
    if not 2 <= len(nome) <= 30:
        raise ValueError("Il nome deve avere tra 2 e 30 caratteri")
    return nome


def link_invito(gettone):
    return url_for("usa_link_invito", gettone=gettone, _external=True)


def qr_svg(testo):
    """QR code in formato SVG (un disegno vettoriale), da inserire nella pagina."""
    buffer = BytesIO()
    segno.make(testo, error="m").save(buffer, kind="svg", scale=5, border=2, dark="#114D8A", xmldecl=False)
    return buffer.getvalue().decode()


def c_e_un_gestore(db):
    """Deve sempre esistere almeno una persona che può gestire persone e ruoli,
    altrimenti nessuno potrebbe più rimediare."""
    return db.execute(
        "SELECT 1 FROM persone p JOIN ruoli r ON r.id=p.ruolo_id WHERE r.perm_persone=1 LIMIT 1"
    ).fetchone() is not None


SENZA_GESTORE = "Deve restare almeno una persona che gestisce persone e ruoli"


def sceglibili(db):
    """Profili che si possono "prendere" dall'elenco al primo accesso: creati in
    anticipo, senza nessun dispositivo collegato e con un ruolo SENZA permessi.
    Quelli con permessi si attivano solo con il link personale."""
    return db.execute(
        """SELECT p.id, p.nome, p.colore FROM persone p JOIN ruoli r ON r.id=p.ruolo_id
           WHERE NOT EXISTS (SELECT 1 FROM dispositivi d WHERE d.persona_id=p.id)
             AND r.perm_riunioni=0 AND r.perm_odg=0 AND r.perm_conclude=0
             AND r.perm_verbale=0 AND r.perm_persone=0
           ORDER BY p.nome COLLATE NOCASE"""
    ).fetchall()


# ---------------------------------------------------------------- presentarsi

@bp.get("/presentati")
def elenco_sceglibili():
    return {"persone": [dict(r) for r in sceglibili(get_db())]}


@bp.post("/presentati")
def presentati():
    dati = request.get_json(silent=True) or {}
    db = get_db()
    persona_id = dati.get("persona_id")
    if persona_id:   # scelta dall'elenco dei profili creati in anticipo
        if persona_id not in [r["id"] for r in sceglibili(db)]:
            return errore("Questo profilo non è disponibile: chiedi il link a un amministratore")
    else:            # nome nuovo
        try:
            nome = pulisci_nome(dati.get("nome"))
        except ValueError as e:
            return errore(str(e))
        uguale = db.execute("SELECT id FROM persone WHERE nome=? COLLATE NOCASE", (nome,)).fetchone()
        if uguale:
            if uguale["id"] in [r["id"] for r in sceglibili(db)]:
                persona_id = uguale["id"]      # è un profilo creato in anticipo: lo prende
            else:
                return errore("Questo nome è già usato. Aggiungi l'iniziale del cognome, "
                              "oppure chiedi a un amministratore il link per entrare", 409)
        else:
            persona_id = db.execute(
                "INSERT INTO persone (nome, colore, ruolo_id) VALUES (?,?,2)",
                (nome, identita.colore_libero(db)),
            ).lastrowid
    # Chi è arrivato dal link d'emergenza (/entra/<chiave>) diventa amministratore
    if session.pop("promuovi", False):
        db.execute("UPDATE persone SET ruolo_id=1 WHERE id=?", (persona_id,))
    identita.lega_dispositivo(db, persona_id)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- il mio profilo

@bp.post("/io/esci")
@richiede()
def esci_da_questo_dispositivo():
    db = get_db()
    db.execute("DELETE FROM dispositivi WHERE id=?", (g.io["dispositivo_id"],))
    db.commit()
    g.togli_cookie = True
    return {"ok": True}


@bp.post("/io/altro-dispositivo")
@richiede()
def link_altro_dispositivo():
    db = get_db()
    link = link_invito(identita.crea_invito(db, g.io["id"], DURATA_ALTRO_DISPOSITIVO))
    db.commit()
    return {"link": link, "qr": qr_svg(link), "minuti": 15}


# ---------------------------------------------------------------- persone (gestione)

def elenco_persone(db):
    righe = db.execute(
        """SELECT p.*, r.nome AS ruolo_nome,
                  (SELECT COUNT(*) FROM dispositivi d WHERE d.persona_id=p.id) AS dispositivi
           FROM persone p JOIN ruoli r ON r.id=p.ruolo_id ORDER BY p.nome COLLATE NOCASE"""
    ).fetchall()
    return [dict(r) for r in righe]


@bp.get("/persone")
@richiede("persone")
def lista_persone():
    db = get_db()
    return {"persone": elenco_persone(db), "ruoli": lista_ruoli_dati(db), "colori": identita.COLORI,
            "io": g.io["id"]}


@bp.post("/persone")
@richiede("persone")
def crea_persona():
    """Crea un profilo in anticipo. Se il ruolo ha permessi, restituisce subito
    il link di attivazione da mandare alla persona."""
    dati = request.get_json(silent=True) or {}
    db = get_db()
    try:
        nome = pulisci_nome(dati.get("nome"))
    except ValueError as e:
        return errore(str(e))
    ruolo = db.execute("SELECT * FROM ruoli WHERE id=?", (dati.get("ruolo_id"),)).fetchone()
    if not ruolo:
        return errore("Ruolo non trovato")
    if db.execute("SELECT 1 FROM persone WHERE nome=? COLLATE NOCASE", (nome,)).fetchone():
        return errore("Esiste già una persona con questo nome", 409)
    persona_id = db.execute("INSERT INTO persone (nome, colore, ruolo_id) VALUES (?,?,?)",
                            (nome, identita.colore_libero(db), ruolo["id"])).lastrowid
    risposta = {"persone": elenco_persone(db)}
    if identita.ha_permessi(ruolo):
        risposta["attivazione"] = attivazione(db, persona_id, nome)
    db.commit()
    return risposta, 201


def attivazione(db, persona_id, nome):
    link = link_invito(identita.crea_invito(db, persona_id, DURATA_ATTIVAZIONE))
    return {"link": link, "qr": qr_svg(link), "nome": nome, "giorni": DURATA_ATTIVAZIONE.days}


@bp.patch("/persone/<int:persona_id>")
@richiede("persone")
def modifica_persona(persona_id):
    dati = request.get_json(silent=True) or {}
    db = get_db()
    try:
        nome = pulisci_nome(dati.get("nome"))
    except ValueError as e:
        return errore(str(e))
    colore = dati.get("colore")
    if not RE_COLORE.match(str(colore or "")):
        return errore("Colore non valido")
    if not db.execute("SELECT 1 FROM ruoli WHERE id=?", (dati.get("ruolo_id"),)).fetchone():
        return errore("Ruolo non trovato")
    if db.execute("SELECT 1 FROM persone WHERE nome=? COLLATE NOCASE AND id<>?", (nome, persona_id)).fetchone():
        return errore("Esiste già una persona con questo nome", 409)
    db.execute("UPDATE persone SET nome=?, colore=?, ruolo_id=? WHERE id=?",
               (nome, colore, dati["ruolo_id"], persona_id))
    if not c_e_un_gestore(db):
        db.rollback()
        return errore(SENZA_GESTORE)
    db.commit()
    return {"persone": elenco_persone(db)}


@bp.post("/persone/<int:persona_id>/attivazione")
@richiede("persone")
def nuovo_link_attivazione(persona_id):
    """Link per entrare come quella persona (primo accesso, telefono nuovo,
    cookie perso). Annulla i link precedenti non ancora usati."""
    db = get_db()
    persona = db.execute("SELECT nome FROM persone WHERE id=?", (persona_id,)).fetchone()
    if not persona:
        return errore("Persona non trovata", 404)
    risposta = attivazione(db, persona_id, persona["nome"])
    db.commit()
    return risposta


@bp.delete("/persone/<int:persona_id>/dispositivi")
@richiede("persone")
def scollega_dispositivi(persona_id):
    """Scollega tutti i dispositivi della persona (es. telefono perso)."""
    db = get_db()
    db.execute("DELETE FROM dispositivi WHERE persona_id=?", (persona_id,))
    db.commit()
    return {"persone": elenco_persone(db)}


@bp.post("/persone/<int:persona_id>/unisci")
@richiede("persone")
def unisci_persone(persona_id):
    """Unisce un profilo doppio ("Anna B." creata due volte) in quello giusto:
    dispositivi, proposte e punti passano al profilo che resta."""
    destinazione = (request.get_json(silent=True) or {}).get("in")
    db = get_db()
    if destinazione == persona_id or not db.execute("SELECT 1 FROM persone WHERE id=?", (destinazione,)).fetchone():
        return errore("Scegli un'altra persona")
    for sql in ("UPDATE dispositivi SET persona_id=? WHERE persona_id=?",
                "UPDATE proposte SET persona_id=? WHERE persona_id=?",
                "UPDATE proposte SET decisa_da=? WHERE decisa_da=?",
                "UPDATE punti SET proposto_da=? WHERE proposto_da=?"):
        db.execute(sql, (destinazione, persona_id))
    db.execute("DELETE FROM persone WHERE id=?", (persona_id,))
    if not c_e_un_gestore(db):
        db.rollback()
        return errore(SENZA_GESTORE)
    db.commit()
    return {"persone": elenco_persone(db)}


@bp.delete("/persone/<int:persona_id>")
@richiede("persone")
def elimina_persona(persona_id):
    db = get_db()
    db.execute("DELETE FROM persone WHERE id=?", (persona_id,))
    if not c_e_un_gestore(db):
        db.rollback()
        return errore(SENZA_GESTORE)
    db.commit()
    return {"persone": elenco_persone(db)}


# ---------------------------------------------------------------- ruoli

def lista_ruoli_dati(db):
    righe = db.execute(
        """SELECT r.*, (SELECT COUNT(*) FROM persone p WHERE p.ruolo_id=r.id) AS persone
           FROM ruoli r ORDER BY r.id"""
    ).fetchall()
    return [{"id": r["id"], "nome": r["nome"], "di_base": r["di_base"], "persone": r["persone"],
             "permessi": {p: bool(r[f"perm_{p}"]) for p in PERMESSI}} for r in righe]


@bp.post("/ruoli")
@richiede("persone")
def crea_ruolo():
    db = get_db()
    db.execute("INSERT INTO ruoli (nome) VALUES ('Nuovo ruolo')")
    db.commit()
    return {"ruoli": lista_ruoli_dati(db)}, 201


@bp.patch("/ruoli/<int:ruolo_id>")
@richiede("persone")
def modifica_ruolo(ruolo_id):
    dati = request.get_json(silent=True) or {}
    nome = " ".join(str(dati.get("nome") or "").split())[:40]
    if not nome:
        return errore("Il ruolo deve avere un nome")
    permessi = dati.get("permessi") or {}
    db = get_db()
    db.execute(
        f"UPDATE ruoli SET nome=?, {', '.join(f'perm_{p}=?' for p in PERMESSI)} WHERE id=?",
        (nome, *[1 if permessi.get(p) else 0 for p in PERMESSI], ruolo_id),
    )
    if not c_e_un_gestore(db):
        db.rollback()
        return errore(SENZA_GESTORE)
    db.commit()
    return {"ruoli": lista_ruoli_dati(db)}


@bp.delete("/ruoli/<int:ruolo_id>")
@richiede("persone")
def elimina_ruolo(ruolo_id):
    db = get_db()
    ruolo = db.execute("SELECT di_base FROM ruoli WHERE id=?", (ruolo_id,)).fetchone()
    if not ruolo:
        return errore("Ruolo non trovato", 404)
    if ruolo["di_base"]:
        return errore("Amministratore e Partecipante non si possono eliminare (ma si possono rinominare)")
    if db.execute("SELECT 1 FROM persone WHERE ruolo_id=?", (ruolo_id,)).fetchone():
        return errore("Prima assegna un altro ruolo alle persone che hanno questo")
    db.execute("DELETE FROM ruoli WHERE id=?", (ruolo_id,))
    db.commit()
    return {"ruoli": lista_ruoli_dati(db)}
