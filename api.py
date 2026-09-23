"""Route API (restituiscono JSON): riunioni, punti dell'OdG e proposte.

Un Blueprint è un "gruppo di route" che si registra in app.py: tiene
app.py corto e tutte le API nello stesso posto, con prefisso /api.
Ogni azione è protetta dal decoratore @richiede (identita.py): serve una
persona riconosciuta e, quasi sempre, un permesso del suo ruolo.
"""
import re
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from calendario import ROMA
from database import get_db, nuovo_codice
from identita import richiede

bp = Blueprint("api", __name__, url_prefix="/api")

RE_ORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def errore(messaggio, codice=400):
    return jsonify(errore=messaggio), codice


def testo(dati, campo, obbligatorio=False, massimo=200):
    """Legge un campo di testo ripulito dagli spazi. None se vuoto."""
    valore = str(dati.get(campo) or "").strip()[:massimo]
    if obbligatorio and not valore:
        raise ValueError(f"Il campo «{campo.replace('_', ' ')}» è obbligatorio")
    return valore or None


def ora(dati, campo, obbligatorio=False):
    valore = testo(dati, campo, obbligatorio)
    if valore and not RE_ORA.match(valore):
        raise ValueError("Orario non valido (formato 21:00)")
    return valore


def data(dati, campo):
    valore = testo(dati, campo, obbligatorio=True)
    try:
        datetime.strptime(valore, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Data non valida") from None
    return valore


def minuti(dati, campo, predefinito):
    try:
        valore = int(dati.get(campo) or predefinito)
    except (TypeError, ValueError):
        raise ValueError("I minuti devono essere un numero") from None
    if not 1 <= valore <= 600:
        raise ValueError("I minuti devono essere tra 1 e 600")
    return valore


def toccata(db, riunione_id):
    """Segna che la riunione è cambiata (serve per rinnovare l'immagine di anteprima)."""
    db.execute("UPDATE riunioni SET modificata_il=datetime('now') WHERE id=?", (riunione_id,))


# ---------------------------------------------------------------- tipi di riunione

def campi_tipo(dati):
    return {
        "nome": testo(dati, "nome", obbligatorio=True, massimo=34),
        "sottotitolo": testo(dati, "sottotitolo", massimo=40),
        "luogo_abituale": testo(dati, "luogo_abituale", massimo=60),
        "ora_abituale": ora(dati, "ora_abituale"),
        "durata_abituale": minuti(dati, "durata_abituale", 90),
    }


@bp.post("/tipi")
@richiede("riunioni")
def crea_tipo():
    try:
        campi = campi_tipo(request.get_json(silent=True) or {})
    except ValueError as e:
        return errore(str(e))
    db = get_db()
    campi["codice"] = nuovo_codice(db, "tipi_riunione")
    db.execute(f"INSERT INTO tipi_riunione ({', '.join(campi)}) VALUES ({', '.join('?' * len(campi))})",
               tuple(campi.values()))
    db.commit()
    return {"codice": campi["codice"]}, 201


@bp.patch("/tipi/<int:tipo_id>")
@richiede("riunioni")
def modifica_tipo(tipo_id):
    dati = request.get_json(silent=True) or {}
    try:
        campi = campi_tipo(dati)
    except ValueError as e:
        return errore(str(e))
    campi["archiviato"] = 1 if dati.get("archiviato") else 0
    db = get_db()
    db.execute(f"UPDATE tipi_riunione SET {', '.join(f'{c}=?' for c in campi)} WHERE id=?",
               (*campi.values(), tipo_id))
    # Il nome del tipo compare nell'immagine di anteprima: vanno rinnovate tutte
    db.execute("UPDATE riunioni SET modificata_il=datetime('now') WHERE tipo_id=?", (tipo_id,))
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- riunioni

def campi_riunione(dati):
    return {
        "data": data(dati, "data"),
        "ora_inizio": ora(dati, "ora_inizio", obbligatorio=True),
        "ora_fine": ora(dati, "ora_fine"),
        "luogo": testo(dati, "luogo", massimo=60),
        "link_online": testo(dati, "link_online", massimo=500),
        "note": testo(dati, "note", massimo=1000),
    }


@bp.post("/riunioni")
@richiede("riunioni")
def crea_riunione():
    dati = request.get_json(silent=True) or {}
    try:
        campi = campi_riunione(dati)
    except ValueError as e:
        return errore(str(e))
    db = get_db()
    tipo = db.execute("SELECT id FROM tipi_riunione WHERE id=?", (dati.get("tipo_id"),)).fetchone()
    if not tipo:
        return errore("Tipo di riunione non trovato", 404)
    campi["tipo_id"] = tipo["id"]
    campi["codice"] = nuovo_codice(db, "riunioni")
    db.execute(f"INSERT INTO riunioni ({', '.join(campi)}) VALUES ({', '.join('?' * len(campi))})",
               tuple(campi.values()))
    db.commit()
    return {"codice": campi["codice"]}, 201


@bp.patch("/riunioni/<int:riunione_id>")
@richiede("riunioni")
def modifica_riunione(riunione_id):
    try:
        campi = campi_riunione(request.get_json(silent=True) or {})
    except ValueError as e:
        return errore(str(e))
    db = get_db()
    db.execute(f"UPDATE riunioni SET {', '.join(f'{c}=?' for c in campi)} WHERE id=?",
               (*campi.values(), riunione_id))
    toccata(db, riunione_id)
    db.commit()
    return {"ok": True}


@bp.delete("/riunioni/<int:riunione_id>")
@richiede("riunioni")
def elimina_riunione(riunione_id):
    db = get_db()
    riga = db.execute("SELECT t.codice FROM riunioni r JOIN tipi_riunione t ON t.id=r.tipo_id WHERE r.id=?",
                      (riunione_id,)).fetchone()
    if not riga:
        return errore("Riunione non trovata", 404)
    db.execute("DELETE FROM riunioni WHERE id=?", (riunione_id,))   # punti e proposte se ne vanno in cascata
    db.commit()
    return {"codice_tipo": riga["codice"]}


# ---------------------------------------------------------------- stato dell'OdG
# Dopo ogni azione su punti o proposte il server restituisce lo "stato" completo
# della riunione (punti + proposte in attesa): la pagina lo ridisegna tutto.

def stato(db, riunione_id):
    punti = db.execute(
        """SELECT pu.*, pe.nome AS proposto_da_nome, pe.colore AS proposto_da_colore
           FROM punti pu LEFT JOIN persone pe ON pe.id = pu.proposto_da
           WHERE pu.riunione_id=? ORDER BY pu.ordine""",
        (riunione_id,),
    ).fetchall()
    proposte = db.execute(
        """SELECT pr.id, pr.tipo, pr.punto_id, pr.titolo, pr.minuti, pr.persona_id,
                  pe.nome AS persona_nome, pe.colore AS persona_colore,
                  pu.titolo AS punto_titolo, pu.minuti AS punto_minuti
           FROM proposte pr JOIN persone pe ON pe.id = pr.persona_id
           LEFT JOIN punti pu ON pu.id = pr.punto_id
           WHERE pr.riunione_id=? AND pr.stato='in_attesa' ORDER BY pr.creata_il, pr.id""",
        (riunione_id,),
    ).fetchall()
    return {"punti": [dict(p) for p in punti], "proposte": [dict(p) for p in proposte]}


@bp.get("/riunioni/<int:riunione_id>/stato")
def leggi_stato(riunione_id):
    return stato(get_db(), riunione_id)


# ---------------------------------------------------------------- punti (modifica diretta)

@bp.post("/riunioni/<int:riunione_id>/punti")
@richiede("odg")
def aggiungi_punto(riunione_id):
    dati = request.get_json(silent=True) or {}
    try:
        titolo = testo(dati, "titolo", obbligatorio=True)
        durata = minuti(dati, "minuti", 10)
    except ValueError as e:
        return errore(str(e))
    db = get_db()
    if not db.execute("SELECT 1 FROM riunioni WHERE id=?", (riunione_id,)).fetchone():
        return errore("Riunione non trovata", 404)
    inserisci_punto(db, riunione_id, titolo, durata)
    db.commit()
    return stato(db, riunione_id), 201


def inserisci_punto(db, riunione_id, titolo, durata, proposto_da=None):
    ultimo = db.execute("SELECT COALESCE(MAX(ordine), 0) FROM punti WHERE riunione_id=?",
                        (riunione_id,)).fetchone()[0]
    db.execute("INSERT INTO punti (riunione_id, ordine, titolo, minuti, proposto_da) VALUES (?,?,?,?,?)",
               (riunione_id, ultimo + 1, titolo, durata, proposto_da))
    toccata(db, riunione_id)


@bp.patch("/punti/<int:punto_id>")
@richiede("odg")
def modifica_punto(punto_id):
    dati = request.get_json(silent=True) or {}
    try:
        titolo = testo(dati, "titolo", obbligatorio=True)
        durata = minuti(dati, "minuti", 10)
    except ValueError as e:
        return errore(str(e))
    db = get_db()
    punto = db.execute("SELECT riunione_id FROM punti WHERE id=?", (punto_id,)).fetchone()
    if not punto:
        return errore("Punto non trovato", 404)
    db.execute("UPDATE punti SET titolo=?, minuti=? WHERE id=?", (titolo, durata, punto_id))
    toccata(db, punto["riunione_id"])
    db.commit()
    return stato(db, punto["riunione_id"])


@bp.delete("/punti/<int:punto_id>")
@richiede("odg")
def elimina_punto(punto_id):
    db = get_db()
    punto = db.execute("SELECT riunione_id FROM punti WHERE id=?", (punto_id,)).fetchone()
    if not punto:
        return errore("Punto non trovato", 404)
    togli_punto(db, punto_id, punto["riunione_id"])
    db.commit()
    return stato(db, punto["riunione_id"])


def togli_punto(db, punto_id, riunione_id):
    # Le proposte in attesa su questo punto spariscono con lui (ON DELETE CASCADE)
    db.execute("DELETE FROM punti WHERE id=?", (punto_id,))
    rinumera(db, riunione_id)
    toccata(db, riunione_id)


@bp.post("/punti/<int:punto_id>/sposta")
@richiede("odg")
def sposta_punto(punto_id):
    """Sposta un punto di una posizione in su (-1) o in giù (+1)."""
    direzione = (request.get_json(silent=True) or {}).get("direzione")
    if direzione not in (-1, 1):
        return errore("Direzione non valida")
    db = get_db()
    punto = db.execute("SELECT * FROM punti WHERE id=?", (punto_id,)).fetchone()
    if not punto:
        return errore("Punto non trovato", 404)
    vicino = db.execute(
        f"""SELECT * FROM punti WHERE riunione_id=? AND ordine {'<' if direzione < 0 else '>'} ?
            ORDER BY ordine {'DESC' if direzione < 0 else 'ASC'} LIMIT 1""",
        (punto["riunione_id"], punto["ordine"]),
    ).fetchone()
    if vicino:   # scambia le due posizioni
        db.execute("UPDATE punti SET ordine=? WHERE id=?", (vicino["ordine"], punto["id"]))
        db.execute("UPDATE punti SET ordine=? WHERE id=?", (punto["ordine"], vicino["id"]))
        toccata(db, punto["riunione_id"])
        db.commit()
    return stato(db, punto["riunione_id"])


def rinumera(db, riunione_id):
    """Dopo un'eliminazione riporta l'ordine a 1, 2, 3... senza buchi."""
    ids = [r["id"] for r in db.execute("SELECT id FROM punti WHERE riunione_id=? ORDER BY ordine",
                                       (riunione_id,))]
    db.executemany("UPDATE punti SET ordine=? WHERE id=?", [(i, pid) for i, pid in enumerate(ids, 1)])


# ---------------------------------------------------------------- proposte

@bp.post("/riunioni/<int:riunione_id>/proposte")
@richiede()      # basta essersi presentati: proporre è aperto a tutti
def crea_proposta(riunione_id):
    dati = request.get_json(silent=True) or {}
    db = get_db()
    riunione = db.execute("SELECT * FROM riunioni WHERE id=?", (riunione_id,)).fetchone()
    if not riunione:
        return errore("Riunione non trovata", 404)
    if riunione["data"] < datetime.now(ROMA).strftime("%Y-%m-%d"):
        return errore("La riunione è passata: non si possono più proporre modifiche")
    tipo = dati.get("tipo")
    if tipo not in ("aggiungi", "modifica", "togli"):
        return errore("Tipo di proposta non valido")

    punto_id = titolo = durata = None
    try:
        if tipo in ("modifica", "togli"):
            punto = db.execute("SELECT * FROM punti WHERE id=? AND riunione_id=?",
                               (dati.get("punto_id"), riunione_id)).fetchone()
            if not punto:
                return errore("Punto non trovato", 404)
            punto_id = punto["id"]
        if tipo in ("aggiungi", "modifica"):
            titolo = testo(dati, "titolo", obbligatorio=True)
            durata = minuti(dati, "minuti", 10)
            if tipo == "modifica" and (titolo, durata) == (punto["titolo"], punto["minuti"]):
                return errore("Non hai cambiato niente rispetto al punto attuale")
    except ValueError as e:
        return errore(str(e))

    db.execute("INSERT INTO proposte (riunione_id, persona_id, tipo, punto_id, titolo, minuti) VALUES (?,?,?,?,?,?)",
               (riunione_id, g.io["id"], tipo, punto_id, titolo, durata))
    db.commit()
    return stato(db, riunione_id), 201


def proposta_in_attesa(db, proposta_id):
    return db.execute("SELECT * FROM proposte WHERE id=? AND stato='in_attesa'", (proposta_id,)).fetchone()


def decidi(db, proposta, esito):
    db.execute("UPDATE proposte SET stato=?, decisa_da=?, decisa_il=datetime('now') WHERE id=?",
               (esito, g.io["id"], proposta["id"]))


@bp.post("/proposte/<int:proposta_id>/approva")
@richiede("odg")
def approva_proposta(proposta_id):
    db = get_db()
    p = proposta_in_attesa(db, proposta_id)
    if not p:
        return errore("Questa proposta è già stata decisa o ritirata", 404)
    if p["tipo"] == "aggiungi":
        inserisci_punto(db, p["riunione_id"], p["titolo"], p["minuti"], proposto_da=p["persona_id"])
    elif p["tipo"] == "modifica":
        db.execute("UPDATE punti SET titolo=?, minuti=? WHERE id=?", (p["titolo"], p["minuti"], p["punto_id"]))
        toccata(db, p["riunione_id"])
    else:
        # Prima segno la decisione: togliendo il punto, la proposta (legata al
        # punto) verrebbe cancellata in cascata. Per non perderla dallo storico
        # la stacco dal punto.
        db.execute("UPDATE proposte SET punto_id=NULL WHERE id=?", (p["id"],))
        togli_punto(db, p["punto_id"], p["riunione_id"])
    decidi(db, p, "approvata")
    db.commit()
    return stato(db, p["riunione_id"])


@bp.post("/proposte/<int:proposta_id>/rifiuta")
@richiede("odg")
def rifiuta_proposta(proposta_id):
    db = get_db()
    p = proposta_in_attesa(db, proposta_id)
    if not p:
        return errore("Questa proposta è già stata decisa o ritirata", 404)
    decidi(db, p, "rifiutata")
    db.commit()
    return stato(db, p["riunione_id"])


@bp.post("/proposte/<int:proposta_id>/ritira")
@richiede()
def ritira_proposta(proposta_id):
    db = get_db()
    p = proposta_in_attesa(db, proposta_id)
    if not p:
        return errore("Questa proposta è già stata decisa o ritirata", 404)
    if p["persona_id"] != g.io["id"]:
        return errore("Puoi ritirare solo le tue proposte", 403)
    decidi(db, p, "ritirata")
    db.commit()
    return stato(db, p["riunione_id"])
