"""Genera la coppia di chiavi VAPID, necessaria per inviare notifiche push.

Cos'è VAPID, in breve: è la "firma" con cui questa app si presenta ai servizi
push di Google, Apple e Mozilla (quelli che davvero recapitano la notifica al
telefono). La chiave PRIVATA resta sul server e serve per firmare ogni invio;
quella PUBBLICA la usa il telefono quando si iscrive, per dire "accetto solo
notifiche firmate da questa chiave".

Si lancia UNA VOLTA SOLA per ogni posto in cui gira l'app (sul PC per le prove,
su PythonAnywhere per il sito vero): le chiavi non vanno su GitHub (.gitignore).
    python genera_vapid.py

Rigenerarle invaliderebbe le iscrizioni già fatte (andrebbero rifatte sui
telefoni): per questo il programma si rifiuta se le chiavi esistono già.
"""
import base64
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid

BASE_DIR = Path(__file__).parent
FILE_PRIVATA = BASE_DIR / "vapid_private.pem"
FILE_PUBBLICA = BASE_DIR / "vapid_public.txt"

if __name__ == "__main__":
    if FILE_PRIVATA.exists():
        print(f"{FILE_PRIVATA.name} esiste già: non lo sovrascrivo.")
        raise SystemExit(1)
    v = Vapid()
    v.generate_keys()
    FILE_PRIVATA.write_text(v.private_pem().decode(), encoding="utf-8")
    grezza = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    FILE_PUBBLICA.write_text(base64.urlsafe_b64encode(grezza).decode().rstrip("="), encoding="utf-8")
    print(f"Create {FILE_PRIVATA.name} e {FILE_PUBBLICA.name}.")
