"""Notifiche push: invio di un messaggio ai dispositivi di una persona.

Usato dall'app (notifica di prova quando si attivano) e da invia_promemoria.py
(il promemoria del giorno prima, lanciato una volta al giorno).
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
_file_pubblica = BASE_DIR / "vapid_public.txt"
_file_privata = BASE_DIR / "vapid_private.pem"
CHIAVE_PUBBLICA = _file_pubblica.read_text().strip() if _file_pubblica.exists() else None
# pywebpush vuole il PERCORSO del file della chiave privata, non il suo contenuto
CHIAVE_PRIVATA = str(_file_privata) if _file_privata.exists() else None
# "Chi manda le notifiche": i servizi push vogliono un contatto. Usiamo
# l'indirizzo del sito invece di un'email personale.
CONTATTO = os.environ.get("VAPID_CONTATTO", "https://acravennacervia.pythonanywhere.com")


def attive():
    return bool(CHIAVE_PUBBLICA and CHIAVE_PRIVATA)


def invia(db, iscrizione, titolo, corpo, url="/"):
    """Manda UNA notifica a UN dispositivo. True se il servizio l'ha accettata.
    Se il dispositivo non è più iscritto (risposta 404/410: app disinstallata,
    notifiche tolte dalle impostazioni) l'iscrizione viene cancellata."""
    from pywebpush import WebPushException, webpush
    try:
        webpush(
            subscription_info={"endpoint": iscrizione["endpoint"], "keys": json.loads(iscrizione["chiavi"])},
            data=json.dumps({"titolo": titolo, "corpo": corpo, "url": url}),
            vapid_private_key=CHIAVE_PRIVATA,
            vapid_claims={"sub": CONTATTO},
            timeout=10,
        )
        return True
    except WebPushException as e:
        if e.response is not None and e.response.status_code in (404, 410):
            db.execute("DELETE FROM iscrizioni_push WHERE id=?", (iscrizione["id"],))
            db.commit()
        print(f"Notifica non consegnata a {iscrizione['endpoint'][:40]}...: {e}")
        return False
    except Exception as e:   # es. rete bloccata dal server che ospita il sito
        print(f"Notifica non inviata: {e}")
        return False


def invia_a_persona(db, persona_id, titolo, corpo, url="/"):
    """Manda la notifica a tutti i dispositivi della persona. Restituisce quanti l'hanno ricevuta."""
    iscrizioni = db.execute("SELECT * FROM iscrizioni_push WHERE persona_id=?", (persona_id,)).fetchall()
    return sum(invia(db, i, titolo, corpo, url) for i in iscrizioni)
