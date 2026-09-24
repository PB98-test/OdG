"""Promemoria del giorno prima: da lanciare UNA volta al giorno.

Su PythonAnywhere è un'"attività pianificata" (scheda Tasks), che il piano
gratuito permette una volta al giorno. Per ogni riunione in programma DOMANI
avvisa chi segue quel tipo di riunione, con un solo messaggio che contiene:
- orario e luogo;
- i compiti ancora da fare della volta precedente, se ne ha;
- le proposte da approvare, se ha il permesso di modificare l'OdG.

Si può lanciare anche a mano per una prova:
    python invia_promemoria.py
Non manda mai due volte lo stesso promemoria (tabella promemoria_inviati).
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

import database  # noqa: E402
import notifiche  # noqa: E402
from calendario import ROMA  # noqa: E402


def plurale(n, uno, tanti):
    return f"{n} {uno if n == 1 else tanti}"


def messaggio(db, riunione, tipo, persona):
    """Testo del promemoria per UNA persona (cambia in base a compiti e permessi)."""
    righe = [f"Domani alle {riunione['ora_inizio']}" + (f", {riunione['luogo']}" if riunione["luogo"] else "")]
    precedente = db.execute(
        """SELECT id FROM riunioni WHERE tipo_id=? AND stato='conclusa' AND data<?
           ORDER BY data DESC, ora_inizio DESC LIMIT 1""",
        (tipo["id"], riunione["data"]),
    ).fetchone()
    if precedente:
        compiti = db.execute("SELECT COUNT(*) FROM compiti WHERE riunione_id=? AND persona_id=? AND fatto_il IS NULL",
                             (precedente["id"], persona["id"])).fetchone()[0]
        if compiti:
            righe.append(f"Hai {plurale(compiti, 'compito', 'compiti')} dalla volta scorsa")
    if persona["perm_odg"]:
        proposte = db.execute("SELECT COUNT(*) FROM proposte WHERE riunione_id=? AND stato='in_attesa'",
                              (riunione["id"],)).fetchone()[0]
        if proposte:
            righe.append(f"{plurale(proposte, 'proposta', 'proposte')} da approvare")
    return f"Domani: {tipo['nome']}", " · ".join(righe)


def main():
    if not notifiche.attive():
        print("Notifiche non configurate: lancia prima genera_vapid.py")
        return
    database.assicura_db()   # nel caso le tabelle delle notifiche non esistano ancora
    db = sqlite3.connect(database.DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    domani = (datetime.now(ROMA) + timedelta(days=1)).strftime("%Y-%m-%d")
    riunioni = db.execute("SELECT * FROM riunioni WHERE data=? AND stato='in_programma'", (domani,)).fetchall()
    if not riunioni:
        print(f"{domani}: nessuna riunione domani, niente da mandare.")
        return
    for r in riunioni:
        tipo = db.execute("SELECT * FROM tipi_riunione WHERE id=?", (r["tipo_id"],)).fetchone()
        persone = db.execute(
            """SELECT p.*, ru.perm_odg FROM seguiti s JOIN persone p ON p.id=s.persona_id
               JOIN ruoli ru ON ru.id=p.ruolo_id
               WHERE s.tipo_id=? AND NOT EXISTS
                 (SELECT 1 FROM promemoria_inviati pi WHERE pi.riunione_id=? AND pi.persona_id=p.id)""",
            (tipo["id"], r["id"]),
        ).fetchall()
        for p in persone:
            titolo, corpo = messaggio(db, r, tipo, p)
            ricevute = notifiche.invia_a_persona(db, p["id"], titolo, corpo, f"/r/{r['codice']}")
            if ricevute:
                db.execute("INSERT INTO promemoria_inviati (riunione_id, persona_id) VALUES (?,?)", (r["id"], p["id"]))
                db.commit()
            print(f"{tipo['nome']} {r['data']} -> {p['nome']}: {ricevute} dispositivi ({corpo})")


if __name__ == "__main__":
    main()
