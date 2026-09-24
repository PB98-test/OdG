"""Connessione al database SQLite e funzioni di utilità."""
import secrets
import sqlite3
from pathlib import Path

from flask import g

BASE_DIR = Path(__file__).parent
DATABASE = BASE_DIR / "odg.db"
SCHEMA = BASE_DIR / "schema.sql"

# Caratteri per i codici dei link: minuscole e cifre, senza quelli che si
# confondono tra loro (0/o, 1/l/i). 7 caratteri = circa 17 miliardi di
# combinazioni: impossibile "indovinare" il link di una riunione.
ALFABETO_CODICI = "abcdefghjkmnpqrstuvwxyz23456789"


def get_db():
    """Restituisce la connessione al DB per la richiesta corrente.

    `g` è un "cassetto" di Flask che vive quanto una singola richiesta:
    la connessione si apre alla prima chiamata e si riusa fino a fine richiesta.
    """
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        # Con row_factory le righe si leggono per nome: riga["nome"], non riga[0]
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    """Chiude la connessione a fine richiesta (registrata in app.py)."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Colonne aggiunte a tabelle che esistevano già: (tabella, colonna, definizione).
# SQLite non ha "ADD COLUMN IF NOT EXISTS", quindi si controlla a mano.
COLONNE_AGGIUNTE = [
    ("punti", "proposto_da", "INTEGER REFERENCES persone(id) ON DELETE SET NULL"),
    # tappa 4
    ("punti", "fisso", "INTEGER NOT NULL DEFAULT 0"),        # 1 = le "Varie", sempre ultime
    ("punti", "spuntato_da", "INTEGER REFERENCES persone(id) ON DELETE SET NULL"),
    ("punti", "secondi", "INTEGER NOT NULL DEFAULT 0"),      # tempo già trascorso (timer in pausa)
    ("punti", "timer_dal", "TEXT"),                          # ora (UTC) di partenza del timer acceso
    ("riunioni", "iniziata_il", "TEXT"),
    ("riunioni", "conclusa_il", "TEXT"),
]

TITOLO_VARIE = "Varie ed eventuali"


def assicura_db():
    """A ogni avvio: crea il database se manca e aggiunge tabelle e colonne nuove.
    Grazie a "IF NOT EXISTS" nello schema non tocca mai i dati esistenti."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    for tabella, colonna, definizione in COLONNE_AGGIUNTE:
        esistenti = [r[1] for r in conn.execute(f"PRAGMA table_info({tabella})")]
        if colonna not in esistenti:
            conn.execute(f"ALTER TABLE {tabella} ADD COLUMN {colonna} {definizione}")
    for nome, funzione in MIGRAZIONI:
        if not conn.execute("SELECT 1 FROM migrazioni WHERE nome=?", (nome,)).fetchone():
            funzione(conn)
            conn.execute("INSERT INTO migrazioni (nome) VALUES (?)", (nome,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- le "Varie"

def rinumera(db, riunione_id):
    """Riporta l'ordine dei punti a 1, 2, 3... senza buchi, con le Varie sempre in fondo."""
    ids = [r[0] for r in db.execute(
        "SELECT id FROM punti WHERE riunione_id=? ORDER BY fisso, ordine", (riunione_id,))]
    db.executemany("UPDATE punti SET ordine=? WHERE id=?", [(i, pid) for i, pid in enumerate(ids, 1)])


def aggiungi_varie(db, riunione_id):
    """Ogni OdG ha come ultimo punto le Varie. Se c'è già un punto scritto a mano
    che si chiama "Varie..." diventa lui il contenitore, così non si duplica."""
    if db.execute("SELECT 1 FROM punti WHERE riunione_id=? AND fisso=1", (riunione_id,)).fetchone():
        return
    esistente = db.execute(
        "SELECT id FROM punti WHERE riunione_id=? AND lower(titolo) LIKE 'varie%' ORDER BY ordine DESC LIMIT 1",
        (riunione_id,),
    ).fetchone()
    if esistente:
        db.execute("UPDATE punti SET fisso=1 WHERE id=?", (esistente[0],))
    else:
        db.execute("INSERT INTO punti (riunione_id, ordine, titolo, minuti, fisso) VALUES (?, 9999, ?, 10, 1)",
                   (riunione_id, TITOLO_VARIE))
    rinumera(db, riunione_id)


# ---------------------------------------------------------------- migrazioni una tantum

def _verbale_ai_partecipanti(db):
    # Decisione di Pietro (tappa 4): il verbale lo possono scrivere tutti
    db.execute("UPDATE ruoli SET perm_verbale=1 WHERE id=2")


def _varie_nelle_riunioni_esistenti(db):
    for riga in db.execute("SELECT id FROM riunioni").fetchall():
        aggiungi_varie(db, riga[0])


MIGRAZIONI = [
    ("tappa4_verbale_partecipanti", _verbale_ai_partecipanti),
    ("tappa4_varie", _varie_nelle_riunioni_esistenti),
]


def nuovo_codice(db, tabella):
    """Genera un codice casuale per un link, controllando che non sia già usato."""
    while True:
        codice = "".join(secrets.choice(ALFABETO_CODICI) for _ in range(7))
        if not db.execute(f"SELECT 1 FROM {tabella} WHERE codice=?", (codice,)).fetchone():
            return codice
