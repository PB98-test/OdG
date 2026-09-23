"""Immagine di anteprima (1200x630) che WhatsApp mostra quando si incolla il link.

Viene disegnata al volo con Pillow per ogni riunione: logo a sinistra, a destra
nome della riunione, data e luogo. 1200x630 è il formato standard delle anteprime
(lo usano WhatsApp, Telegram, Facebook...): con queste misure WhatsApp mostra
l'immagine grande sopra il messaggio, invece di una miniatura.
"""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from calendario import data_estesa

RISORSE = Path(__file__).parent / "risorse"
BLU, GIALLO = (17, 77, 138), (249, 185, 34)
BIANCO, AZZURRO = (255, 255, 255), (220, 230, 242)
L, H = 1200, 630
STRISCIA = 18                     # striscia gialla in fondo
LOGO, X_LOGO = 150, 80            # lato del logo e distanza dal bordo sinistro
X_TESTO, X_MAX = X_LOGO + LOGO + 50, 1150   # colonna del testo, a destra del logo


def _font(nome, dimensione, peso):
    """Antonio e Jost sono font "variabili": un solo file contiene tutti gli
    spessori, e si sceglie quello voluto indicando il peso (400, 500, 700...)."""
    f = ImageFont.truetype(str(RISORSE / "font" / f"{nome}.ttf"), dimensione)
    f.set_variation_by_axes([peso])
    return f


def _adatta(d, testo, nome, dimensione, peso, minimo):
    """Rimpicciolisce il testo finché non entra nella colonna."""
    while dimensione > minimo:
        f = _font(nome, dimensione, peso)
        if d.textlength(testo, font=f) <= X_MAX - X_TESTO:
            return f
        dimensione -= 4
    return _font(nome, minimo, peso)


def _taglia(d, testo, font):
    """Se il testo è ancora troppo lungo, lo accorcia con "…"."""
    if d.textlength(testo, font=font) <= X_MAX - X_TESTO:
        return testo
    while testo and d.textlength(testo + "…", font=font) > X_MAX - X_TESTO:
        testo = testo[:-1]
    return testo.rstrip() + "…"


def disegna(riunione, tipo):
    img = Image.new("RGB", (L, H), BLU)
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - STRISCIA, L, H], fill=GIALLO)

    # Logo nel cerchio bianco, centrato verticalmente sopra la striscia
    logo = Image.open(RISORSE / "logo-ac-cerchio.webp").convert("RGBA").resize((LOGO, LOGO), Image.LANCZOS)
    img.paste(logo, (X_LOGO, (H - STRISCIA - LOGO) // 2), logo)

    # Le quattro righe di testo: (testo, font, colore, spazio sotto)
    riga_luogo = f"ore {riunione['ora_inizio']}"
    if riunione["luogo"]:
        riga_luogo += f" · {riunione['luogo']}"
    elif riunione["link_online"]:
        riga_luogo += " · online"
    f_sopra = _font("Jost", 44, 600)
    f_nome = _adatta(d, tipo["nome"], "Antonio", 104, 700, 60)
    data = data_estesa(riunione["data"])
    data = data[0].upper() + data[1:]
    f_data = _adatta(d, data, "Antonio", 124, 700, 72)
    f_luogo = _font("Jost", 44, 500)
    righe = [
        (_taglia(d, tipo["sottotitolo"] or "AC Ravenna-Cervia", f_sopra), f_sopra, GIALLO, 16),
        (_taglia(d, tipo["nome"], f_nome), f_nome, BIANCO, 12),
        (data, f_data, GIALLO, 22),
        (_taglia(d, riga_luogo, f_luogo), f_luogo, AZZURRO, 0),
    ]

    # Altezza totale del blocco, per centrarlo in verticale
    altezze = [f.getbbox("ÉgAj")[3] for _, f, _, _ in righe]
    totale = sum(altezze) + sum(spazio for *_, spazio in righe)
    y = (H - STRISCIA - totale) // 2
    for (testo, f, colore, spazio), h in zip(righe, altezze):
        d.text((X_TESTO, y), testo, font=f, fill=colore)
        y += h + spazio

    buffer = BytesIO()
    img.save(buffer, "PNG", optimize=True)
    buffer.seek(0)
    return buffer
