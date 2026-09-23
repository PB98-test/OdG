"""Genera le icone dell'app a partire dal logo AC nel cerchio bianco.

Non fa parte dell'app: si lancia a mano solo quando cambia il logo.
    venv\\Scripts\\python genera_icone.py

- icon-192 / icon-512: il logo nel cerchio, angoli trasparenti (browser, Android).
- icon-maskable-512: per Android, che ritaglia le icone con forme sue (cerchio,
  goccia, quadrato arrotondato): il logo è rimpicciolito all'80% su fondo bianco,
  così qualunque ritaglio non lo taglia.
- apple-touch-icon: per iPhone, che non accetta trasparenze (le riempirebbe di
  nero): logo su fondo bianco pieno, gli angoli li arrotonda iOS.
- favicon-32 e icon.ico: la linguetta del browser e il collegamento sul Desktop.
"""
from pathlib import Path

from PIL import Image

BASE = Path(__file__).parent
LOGO = BASE / "risorse" / "logo-ac-cerchio.webp"
DEST = BASE / "static" / "icons"


def su_bianco(logo, lato, scala=1.0):
    """Logo centrato su un quadrato bianco pieno, rimpicciolito di 'scala'."""
    fondo = Image.new("RGBA", (lato, lato), (255, 255, 255, 255))
    interno = round(lato * scala)
    pezzo = logo.resize((interno, interno), Image.LANCZOS)
    fondo.paste(pezzo, ((lato - interno) // 2, (lato - interno) // 2), pezzo)
    return fondo.convert("RGB")


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    logo = Image.open(LOGO).convert("RGBA")
    for nome, lato in [("icon-512.png", 512), ("icon-192.png", 192), ("favicon-32.png", 32)]:
        logo.resize((lato, lato), Image.LANCZOS).save(DEST / nome, optimize=True)
        print("creato", nome)
    su_bianco(logo, 512, 0.8).save(DEST / "icon-maskable-512.png", optimize=True)
    print("creato icon-maskable-512.png")
    su_bianco(logo, 180, 0.9).save(DEST / "apple-touch-icon.png", optimize=True)
    print("creato apple-touch-icon.png")
    logo.resize((256, 256), Image.LANCZOS).save(
        DEST / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("creato icon.ico")
