"""Date in italiano, file .ics e link "aggiungi a Google Calendar".

Tutti gli orari salvati nel database sono "ora di Ravenna". Per i calendari
vanno convertiti in UTC (l'ora universale), altrimenti un telefono impostato
su un altro fuso, o il passaggio all'ora legale, sposterebbero la riunione.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

ROMA = ZoneInfo("Europe/Rome")

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _data(iso):
    return datetime.strptime(iso, "%Y-%m-%d")


def data_estesa(iso, con_anno=False):
    """ "2026-10-08" -> "giovedì 8 ottobre" (o "giovedì 8 ottobre 2026")."""
    d = _data(iso)
    testo = f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]}"
    return f"{testo} {d.year}" if con_anno else testo


def inizio_fine(riunione, durata_abituale):
    """Restituisce (inizio, fine) come datetime con fuso orario di Roma.
    Se la riunione non ha un'ora di fine, si usa la durata abituale del tipo."""
    inizio = datetime.strptime(f"{riunione['data']} {riunione['ora_inizio']}", "%Y-%m-%d %H:%M")
    inizio = inizio.replace(tzinfo=ROMA)
    if riunione["ora_fine"]:
        fine = datetime.strptime(f"{riunione['data']} {riunione['ora_fine']}", "%Y-%m-%d %H:%M")
        fine = fine.replace(tzinfo=ROMA)
        if fine <= inizio:             # es. 21:00 - 00:30: la fine è il giorno dopo
            fine += timedelta(days=1)
    else:
        fine = inizio + timedelta(minutes=durata_abituale)
    return inizio, fine


def _utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _testo_ics(testo):
    """Nei file .ics virgole, punti e virgola e a capo vanno "protetti"."""
    return (str(testo or "").replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n"))


def _piega(riga):
    """Lo standard .ics vuole righe di massimo 75 byte: le più lunghe si
    spezzano e si continuano sulla riga dopo iniziando con uno spazio."""
    byte = riga.encode("utf-8")
    if len(byte) <= 75:
        return riga
    pezzi, attuale = [], ""
    for carattere in riga:
        limite = 75 if not pezzi else 74          # le righe di continuazione hanno lo spazio davanti
        if len((attuale + carattere).encode("utf-8")) > limite:
            pezzi.append(attuale)
            attuale = ""
        attuale += carattere
    pezzi.append(attuale)
    return "\r\n ".join(pezzi)


def descrizione(punti, url):
    """Testo che finisce nella descrizione dell'evento in calendario."""
    righe = []
    if punti:
        righe.append("Ordine del giorno:")
        righe += [f"{i}. {p['titolo']}" for i, p in enumerate(punti, 1)]
        righe.append("")
    righe.append(f"OdG sempre aggiornato: {url}")
    return "\n".join(righe)


# Promemoria che si possono scegliere in "Salva la data": nome -> minuti di anticipo
AVVISI = {"nessuno": [], "ora": [60], "giorno": [1440], "entrambi": [1440, 60]}


def _promemoria(minuti):
    """Un "allarme" dentro l'evento: il calendario del telefono avvisa
    'minuti' prima dell'inizio. (Google Calendar lo ignora e usa i suoi.)"""
    return ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Promemoria riunione",
            f"TRIGGER:-PT{minuti}M", "END:VALARM"]


def file_ics(riunione, tipo, punti, url, avviso="nessuno"):
    """Crea il contenuto di un file .ics con un solo evento (la riunione)."""
    inizio, fine = inizio_fine(riunione, tipo["durata_abituale"])
    luogo = riunione["luogo"] or riunione["link_online"] or ""
    righe = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AC Ravenna-Cervia//OdG//IT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        # UID: identifica l'evento. Se la persona riscarica il file dopo una
        # modifica, il calendario aggiorna l'evento invece di duplicarlo.
        f"UID:riunione-{riunione['codice']}@odg-ac-ravenna-cervia",
        f"DTSTAMP:{_utc(datetime.now(timezone.utc))}",
        f"DTSTART:{_utc(inizio)}",
        f"DTEND:{_utc(fine)}",
        f"SUMMARY:{_testo_ics(tipo['nome'])}",
        f"LOCATION:{_testo_ics(luogo)}",
        f"DESCRIPTION:{_testo_ics(descrizione(punti, url))}",
        f"URL:{url}",
        *[riga for minuti in AVVISI.get(avviso, []) for riga in _promemoria(minuti)],
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_piega(r) for r in righe) + "\r\n"


def link_google(riunione, tipo, punti, url):
    """Link che apre Google Calendar con l'evento già compilato (basta premere Salva)."""
    inizio, fine = inizio_fine(riunione, tipo["durata_abituale"])
    parametri = {
        "action": "TEMPLATE",
        "text": tipo["nome"],
        "dates": f"{_utc(inizio)}/{_utc(fine)}",
        "details": descrizione(punti, url),
        "location": riunione["luogo"] or riunione["link_online"] or "",
        "ctz": "Europe/Rome",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(parametri)
