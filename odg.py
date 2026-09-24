"""Logica comune dell'ordine del giorno, usata da più file di API.

- inserire e togliere punti (con le Varie sempre in fondo)
- creare una riunione (con le Varie e i punti rimasti "in attesa")
- lo "stato" completo di una riunione, che le pagine ridisegnano
"""
from datetime import datetime, timedelta, timezone

from flask import g

from calendario import ROMA, inizio_fine
from database import aggiungi_varie, nuovo_codice, rinumera
from identita import puo

# "Inizia la riunione" compare da questo numero di ore prima dell'inizio fissato
ORE_PRIMA_DI_INIZIARE = 3


def adesso_utc():
    return datetime.now(timezone.utc)


def testo_utc(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def da_testo_utc(testo):
    return datetime.strptime(testo, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def oggi():
    return datetime.now(ROMA).strftime("%Y-%m-%d")


def toccata(db, riunione_id):
    """Segna che la riunione è cambiata (serve per rinnovare l'immagine di anteprima)."""
    db.execute("UPDATE riunioni SET modificata_il=datetime('now') WHERE id=?", (riunione_id,))


# ---------------------------------------------------------------- punti

def inserisci_punto(db, riunione_id, titolo, durata, proposto_da=None, spostato_da=None):
    """Aggiunge un punto in fondo all'OdG, ma sempre prima delle Varie."""
    db.execute(
        "INSERT INTO punti (riunione_id, ordine, titolo, minuti, proposto_da, spostato_da) VALUES (?, 9998, ?, ?, ?, ?)",
        (riunione_id, titolo, durata, proposto_da, spostato_da),
    )
    rinumera(db, riunione_id)
    toccata(db, riunione_id)


def togli_punto(db, punto_id, riunione_id):
    # Le proposte in attesa su questo punto spariscono con lui (ON DELETE CASCADE)
    db.execute("DELETE FROM punti WHERE id=?", (punto_id,))
    rinumera(db, riunione_id)
    toccata(db, riunione_id)


def ferma_timer(db, riunione_id):
    """Mette in pausa il timer acceso (se c'è), sommando il tempo trascorso."""
    for p in db.execute("SELECT id, secondi, timer_dal FROM punti WHERE riunione_id=? AND timer_dal IS NOT NULL",
                        (riunione_id,)).fetchall():
        trascorsi = int((adesso_utc() - da_testo_utc(p["timer_dal"])).total_seconds())
        db.execute("UPDATE punti SET secondi=?, timer_dal=NULL WHERE id=?", (p["secondi"] + max(trascorsi, 0), p["id"]))


# ---------------------------------------------------------------- riunioni

def crea_riunione(db, tipo_id, campi):
    """Crea una riunione con le Varie in fondo e ci porta dentro i punti rimasti
    "in attesa" dalla riunione precedente dello stesso tipo. Restituisce il codice."""
    campi = dict(campi, tipo_id=tipo_id, codice=nuovo_codice(db, "riunioni"))
    riunione_id = db.execute(
        f"INSERT INTO riunioni ({', '.join(campi)}) VALUES ({', '.join('?' * len(campi))})",
        tuple(campi.values()),
    ).lastrowid
    for p in db.execute("SELECT * FROM da_riportare WHERE tipo_id=? ORDER BY id", (tipo_id,)).fetchall():
        inserisci_punto(db, riunione_id, p["titolo"], p["minuti"], p["proposto_da"], p["punto_id"])
    db.execute("DELETE FROM da_riportare WHERE tipo_id=?", (tipo_id,))
    aggiungi_varie(db, riunione_id)
    return campi["codice"]


def successiva(db, riunione):
    """La riunione successiva dello stesso tipo, se è già fissata."""
    return db.execute(
        """SELECT * FROM riunioni WHERE tipo_id=? AND id<>? AND (data>? OR (data=? AND ora_inizio>?))
           ORDER BY data, ora_inizio LIMIT 1""",
        (riunione["tipo_id"], riunione["id"], riunione["data"], riunione["data"], riunione["ora_inizio"]),
    ).fetchone()


def precedente_conclusa(db, riunione):
    """L'ultima riunione CONCLUSA dello stesso tipo prima di questa (per i suoi compiti)."""
    return db.execute(
        """SELECT * FROM riunioni WHERE tipo_id=? AND id<>? AND stato='conclusa'
             AND (data<? OR (data=? AND ora_inizio<?))
           ORDER BY data DESC, ora_inizio DESC LIMIT 1""",
        (riunione["tipo_id"], riunione["id"], riunione["data"], riunione["data"], riunione["ora_inizio"]),
    ).fetchone()


def si_puo_iniziare(riunione, tipo):
    """Il pulsante "Inizia" compare da 3 ore prima dell'orario fissato in poi."""
    if riunione["stato"] != "in_programma":
        return False
    inizio, _ = inizio_fine(riunione, tipo["durata_abituale"])
    return datetime.now(ROMA) >= inizio - timedelta(hours=ORE_PRIMA_DI_INIZIARE)


def si_puo_proporre(riunione):
    """Proposte e Varie restano aperte fino alla conclusione. Una riunione
    passata e mai iniziata non accetta più proposte."""
    if riunione["stato"] == "conclusa":
        return False
    return riunione["stato"] == "in_corso" or riunione["data"] >= oggi()


# ---------------------------------------------------------------- stato completo

def compiti_di(db, condizione, parametri):
    righe = db.execute(
        f"""SELECT c.*, pa.nome AS persona_nome, pa.colore AS persona_colore,
                   pu.titolo AS punto_titolo
            FROM compiti c LEFT JOIN persone pa ON pa.id = c.persona_id
            LEFT JOIN punti pu ON pu.id = c.punto_id
            WHERE {condizione} ORDER BY c.creato_il, c.id""",
        parametri,
    ).fetchall()
    return [dict(r) for r in righe]


def stato(db, riunione_id):
    """Tutto quello che serve alla pagina della riunione per disegnarsi."""
    riunione = db.execute("SELECT * FROM riunioni WHERE id=?", (riunione_id,)).fetchone()
    tipo = db.execute("SELECT * FROM tipi_riunione WHERE id=?", (riunione["tipo_id"],)).fetchone()
    adesso = adesso_utc()

    punti = []
    for p in db.execute(
        """SELECT pu.*, pp.nome AS proposto_da_nome, pp.colore AS proposto_da_colore,
                  ps.nome AS spuntato_da_nome, ps.colore AS spuntato_da_colore,
                  ro.data AS riportato_dal
           FROM punti pu
           LEFT JOIN persone pp ON pp.id = pu.proposto_da
           LEFT JOIN persone ps ON ps.id = pu.spuntato_da
           LEFT JOIN punti orig ON orig.id = pu.spostato_da
           LEFT JOIN riunioni ro ON ro.id = orig.riunione_id
           WHERE pu.riunione_id=? ORDER BY pu.ordine""",
        (riunione_id,),
    ):
        d = dict(p)
        # Tempo trascorso fino a "adesso": quello accumulato + quello del timer acceso
        d["trascorsi"] = d["secondi"] + (
            max(int((adesso - da_testo_utc(d["timer_dal"])).total_seconds()), 0) if d["timer_dal"] else 0)
        d["timer_acceso"] = bool(d["timer_dal"])
        if riunione["stato"] == "conclusa" and not d["spuntato_da"] and not d["fisso"]:
            d["destino"] = destino_punto(db, d["id"])
        punti.append(d)

    proposte = db.execute(
        """SELECT pr.id, pr.tipo, pr.punto_id, pr.titolo, pr.minuti, pr.persona_id,
                  pe.nome AS persona_nome, pe.colore AS persona_colore,
                  pu.titolo AS punto_titolo, pu.minuti AS punto_minuti
           FROM proposte pr JOIN persone pe ON pe.id = pr.persona_id
           LEFT JOIN punti pu ON pu.id = pr.punto_id
           WHERE pr.riunione_id=? AND pr.stato='in_attesa' ORDER BY pr.creata_il, pr.id""",
        (riunione_id,),
    ).fetchall()
    varie = db.execute(
        """SELECT v.id, v.testo, v.persona_id, pe.nome AS persona_nome, pe.colore AS persona_colore
           FROM voci_varie v LEFT JOIN persone pe ON pe.id = v.persona_id
           WHERE v.riunione_id=? ORDER BY v.creata_il, v.id""",
        (riunione_id,),
    ).fetchall()
    prec = precedente_conclusa(db, riunione)
    succ = successiva(db, riunione)
    presenti = db.execute(
        """SELECT pe.id, pe.nome, pe.colore FROM presenze pr JOIN persone pe ON pe.id = pr.persona_id
           WHERE pr.riunione_id=? ORDER BY pe.nome COLLATE NOCASE""",
        (riunione_id,),
    ).fetchall()
    return {
        "riunione": dict(riunione),
        "presenti": [dict(p) for p in presenti],
        "punti": punti,
        "proposte": [dict(p) for p in proposte],
        "varie": [dict(v) for v in varie],
        "compiti": compiti_di(db, "c.riunione_id=?", (riunione_id,)),
        "compiti_precedenti": compiti_di(db, "c.riunione_id=?", (prec["id"],)) if prec else [],
        "precedente": {"codice": prec["codice"], "data": prec["data"]} if prec else None,
        "successiva": {"codice": succ["codice"], "data": succ["data"], "ora_inizio": succ["ora_inizio"]} if succ else None,
        "in_attesa_per_il_tipo": db.execute("SELECT COUNT(*) FROM da_riportare WHERE tipo_id=?",
                                            (tipo["id"],)).fetchone()[0],
        "puo": {
            "iniziare": puo("conclude") and si_puo_iniziare(riunione, tipo),
            "concludere": puo("conclude") and riunione["stato"] == "in_corso",
            "odg": puo("odg") and riunione["stato"] != "conclusa",
            "verbale": puo("verbale"),
            "proporre": si_puo_proporre(riunione),
        },
        "io_id": g.io["id"] if g.get("io") else None,
        # Ora del server in millisecondi: il telefono la usa per allineare i timer
        # anche se il suo orologio è un po' avanti o indietro
        "adesso_ms": int(adesso.timestamp() * 1000),
    }


def destino_punto(db, punto_id):
    """Dove è finito un punto non trattato: in una riunione successiva, o in attesa."""
    riga = db.execute(
        "SELECT r.codice, r.data FROM punti p JOIN riunioni r ON r.id=p.riunione_id WHERE p.spostato_da=? LIMIT 1",
        (punto_id,),
    ).fetchone()
    if riga:
        return {"codice": riga["codice"], "data": riga["data"]}
    if db.execute("SELECT 1 FROM da_riportare WHERE punto_id=?", (punto_id,)).fetchone():
        return {"in_attesa": True}
    return None
