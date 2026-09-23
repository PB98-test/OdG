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


def assicura_db():
    """A ogni avvio: crea il database se manca e aggiunge le tabelle nuove.
    Grazie a "IF NOT EXISTS" nello schema non tocca mai i dati esistenti."""
    conn = sqlite3.connect(DATABASE)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def nuovo_codice(db, tabella):
    """Genera un codice casuale per un link, controllando che non sia già usato."""
    while True:
        codice = "".join(secrets.choice(ALFABETO_CODICI) for _ in range(7))
        if not db.execute(f"SELECT 1 FROM {tabella} WHERE codice=?", (codice,)).fetchone():
            return codice
