"""Chi sta usando l'app: persone riconosciute dal dispositivo, senza password.

Come funziona:
- quando una persona si presenta ("Come ti chiami?") o apre un link di
  attivazione, il suo browser riceve un "gettone" casuale in un cookie;
- nel database si salva solo l'impronta del gettone (hash SHA-256): è come
  conservare l'impronta di una chiave invece della chiave stessa;
- a ogni visita il cookie viene letto e l'impronta confrontata: se corrisponde,
  sappiamo chi è la persona e quali permessi ha il suo ruolo.
I permessi sono legati al dispositivo, non al nome: chi scrive "Pietro B." su
un altro telefono non ottiene i permessi di Pietro.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import g, jsonify, request

from database import get_db

COOKIE = "odg_dispositivo"
# 400 giorni è il massimo che Chrome accetta per un cookie. Il cookie viene
# rinnovato a ogni uso (al massimo una volta al giorno), quindi di fatto non
# scade per chi usa l'app almeno una volta l'anno.
DURATA_COOKIE = timedelta(days=400)

# I permessi, con la descrizione mostrata nella gestione dei ruoli
PERMESSI = {
    "riunioni": "Crea e modifica riunioni",
    "odg": "Modifica l'OdG e approva le proposte",
    "conclude": "Conclude la riunione",
    "verbale": "Scrive il verbale",
    "persone": "Gestisce persone e ruoli",
}

# Colori delle persone: ben distinguibili tra loro e diversi dal blu e dal
# giallo del marchio, leggibili come testo su fondo bianco.
COLORI = ["#1D7A55", "#C2410C", "#7C3AED", "#BE185D", "#0E7490", "#8B5A2B",
          "#4338CA", "#B42318", "#5B7A1F", "#A21CAF", "#475569", "#0F766E"]


def impronta(gettone):
    return hashlib.sha256(gettone.encode()).hexdigest()


def _adesso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- a ogni richiesta

def riconosci():
    """Legge il cookie e mette in g.io la persona (o None). Chiamata da app.py
    prima di ogni richiesta."""
    g.io = None
    gettone = request.cookies.get(COOKIE)
    if not gettone:
        return
    db = get_db()
    riga = db.execute(
        """SELECT p.*, d.id AS dispositivo_id, r.nome AS ruolo_nome,
                  r.perm_riunioni, r.perm_odg, r.perm_conclude, r.perm_verbale, r.perm_persone
           FROM dispositivi d JOIN persone p ON p.id = d.persona_id JOIN ruoli r ON r.id = p.ruolo_id
           WHERE d.impronta = ?""",
        (impronta(gettone),),
    ).fetchone()
    if not riga:
        g.togli_cookie = True        # gettone sconosciuto (es. dispositivo scollegato)
        return
    g.io = {
        "id": riga["id"], "nome": riga["nome"], "colore": riga["colore"],
        "ruolo_id": riga["ruolo_id"], "ruolo_nome": riga["ruolo_nome"],
        "dispositivo_id": riga["dispositivo_id"],
        "permessi": {p: bool(riga[f"perm_{p}"]) for p in PERMESSI},
    }
    # Segno l'uso e rinnovo il cookie, ma al massimo una volta al giorno
    aggiornato = db.execute(
        "UPDATE dispositivi SET ultimo_uso=datetime('now') WHERE id=? AND ultimo_uso < datetime('now', '-1 day')",
        (riga["dispositivo_id"],),
    ).rowcount
    if aggiornato:
        db.commit()
        g.nuovo_gettone = gettone


def scrivi_cookie(risposta):
    """Chiamata da app.py dopo ogni richiesta: consegna o toglie il cookie."""
    if g.get("nuovo_gettone"):
        risposta.set_cookie(COOKIE, g.nuovo_gettone, max_age=int(DURATA_COOKIE.total_seconds()),
                            httponly=True,             # il JavaScript della pagina non può leggerlo
                            secure=request.is_secure,  # solo in HTTPS (online)
                            samesite="Lax")            # non viene inviato da altri siti
    elif g.get("togli_cookie"):
        risposta.delete_cookie(COOKIE)
    return risposta


def puo(permesso):
    return bool(g.get("io")) and g.io["permessi"][permesso]


def richiede(permesso=None):
    """Decoratore per le API: serve una persona riconosciuta e, se indicato,
    un permesso del suo ruolo."""
    def decoratore(funzione):
        @wraps(funzione)
        def controllata(*args, **kwargs):
            if not g.get("io"):
                return jsonify(errore="Prima dicci come ti chiami", chi_sei=True), 401
            if permesso and not puo(permesso):
                return jsonify(errore="Il tuo ruolo non permette questa azione"), 403
            return funzione(*args, **kwargs)
        return controllata
    return decoratore


# ---------------------------------------------------------------- dispositivi e inviti

def lega_dispositivo(db, persona_id):
    """Collega il dispositivo attuale a una persona e prepara il cookie.
    Se il dispositivo era collegato a qualcun altro, quel legame si scioglie."""
    if g.get("io"):
        db.execute("DELETE FROM dispositivi WHERE id=?", (g.io["dispositivo_id"],))
    gettone = secrets.token_urlsafe(32)
    db.execute("INSERT INTO dispositivi (persona_id, impronta) VALUES (?,?)",
               (persona_id, impronta(gettone)))
    g.nuovo_gettone = gettone
    g.togli_cookie = False


def crea_invito(db, persona_id, durata):
    """Crea un link monouso per la persona. Gli eventuali inviti precedenti non
    ancora usati vengono annullati: vale sempre solo l'ultimo."""
    db.execute("DELETE FROM inviti WHERE persona_id=? AND usato_il IS NULL", (persona_id,))
    gettone = secrets.token_urlsafe(24)
    scadenza = (datetime.now(timezone.utc) + durata).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("INSERT INTO inviti (persona_id, impronta, scade_il) VALUES (?,?,?)",
               (persona_id, impronta(gettone), scadenza))
    return gettone


def invito_valido(db, gettone):
    """La persona a cui porta il link, se è ancora valido (senza consumarlo); altrimenti None."""
    invito = db.execute(
        "SELECT persona_id FROM inviti WHERE impronta=? AND usato_il IS NULL AND scade_il > ?",
        (impronta(gettone), _adesso()),
    ).fetchone()
    return invito["persona_id"] if invito else None


def usa_invito(db, gettone):
    """Se il link è valido lo segna come usato e restituisce la persona, altrimenti None."""
    persona_id = invito_valido(db, gettone)
    if persona_id:
        db.execute("UPDATE inviti SET usato_il=? WHERE impronta=?", (_adesso(), impronta(gettone)))
    return persona_id


def colore_libero(db):
    """Il colore usato da meno persone (a parità, il primo della lista)."""
    usi = {c: 0 for c in COLORI}
    for r in db.execute("SELECT colore, COUNT(*) AS n FROM persone GROUP BY colore"):
        if r["colore"] in usi:
            usi[r["colore"]] = r["n"]
    return min(COLORI, key=lambda c: (usi[c], COLORI.index(c)))


def ha_permessi(riga_ruolo):
    return any(riga_ruolo[f"perm_{p}"] for p in PERMESSI)
