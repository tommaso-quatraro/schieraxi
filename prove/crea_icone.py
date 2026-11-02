r"""Crea l'icona di SchieraXI: undici punti in formazione 4-3-3 (con il portiere in basso) e il punto del capitano in evidenza,
su un campo verde profondo con un leggero bagliore. Il logo è la formazione stessa, e nell'app i punti si muovono (caricamenti).

Uso: .venv\Scripts\python.exe prove\crea_icone.py   (serve Pillow: pip install pillow)
Scrive in fanta/web: icona-512.png, icona-192.png, icona-180.png (quadrate, senza angoli: iOS le arrotonda da sola),
icone/<tema>-<lato>.png e icone/<tema>-maskable-<lato>.png (Android) per i temi tra cui scegliere in Lega > Icona, e icona.svg (anche nella scheda del browser).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

WEB = Path(__file__).resolve().parent.parent / "fanta" / "web"
S = 2048                                   # si disegna grande e si rimpicciolisce: bordi lisci

# La formazione, su una griglia 120x120 (come l'SVG): (x, y, raggio). L'ultimo punto, il capitano, è a parte.
PUNTI = [(34, 28), (60, 25), (86, 28), (30, 50), (90, 50), (24, 72), (47, 74), (73, 74), (96, 72), (60, 95)]
CAPITANO = (60, 50)
R_PUNTO, R_CAPITANO = 6.5, 9.0
SCALA_MASKABLE = 0.82                      # il disegno più lontano dal centro resta dentro il cerchio sicuro (40% del lato)

# I colori delle icone tra cui scegliere nell'app (Lega > Icona): sfondo alto/basso, due luci, punti, capitano.
TEMI = {
    "verde":   dict(alto=(18, 92, 66), basso=(6, 40, 30), luce1=(120, 235, 180), luce2=(8, 30, 70), punto=(234, 246, 238), capitano=(212, 243, 74)),
    "blu":     dict(alto=(40, 110, 220), basso=(8, 28, 84), luce1=(170, 210, 255), luce2=(10, 20, 70), punto=(232, 241, 252), capitano=(140, 235, 255)),
    "viola":   dict(alto=(130, 74, 214), basso=(40, 12, 82), luce1=(225, 190, 255), luce2=(15, 20, 70), punto=(244, 236, 252), capitano=(255, 200, 240)),
    "arancio": dict(alto=(240, 140, 40), basso=(110, 40, 8), luce1=(255, 225, 160), luce2=(80, 20, 20), punto=(255, 244, 232), capitano=(255, 246, 140)),
    "rosso":   dict(alto=(214, 56, 66), basso=(80, 10, 22), luce1=(255, 190, 190), luce2=(40, 10, 60), punto=(255, 240, 240), capitano=(255, 226, 150)),
    "grafite": dict(alto=(84, 94, 104), basso=(14, 17, 22), luce1=(200, 215, 230), luce2=(10, 40, 30), punto=(236, 240, 244), capitano=(212, 243, 74)),
}


def sfumatura(alto, basso) -> Image.Image:
    base = Image.linear_gradient("L").resize((S, S))
    return Image.composite(Image.new("RGB", (S, S), basso), Image.new("RGB", (S, S), alto), base)


def luce(centro, raggio, colore, alpha_max) -> Image.Image:
    cx, cy = centro
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse([cx - raggio, cy - raggio, cx + raggio, cy + raggio], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(raggio * 0.45)).point(lambda v: int(v * alpha_max))
    img = Image.new("RGBA", (S, S), colore + (0,))
    img.putalpha(m)
    return img


def punto(img: Image.Image, x: float, y: float, r: float, colore) -> Image.Image:
    """Un punto con un'ombra morbida sotto e un piccolo riflesso in alto a sinistra."""
    k = S / 120
    cx, cy, rr = x * k, y * k, r * k
    ombra = Image.new("L", (S, S), 0)
    ImageDraw.Draw(ombra).ellipse([cx - rr, cy - rr + S * 0.012, cx + rr, cy + rr + S * 0.012], fill=255)
    ombra = ombra.filter(ImageFilter.GaussianBlur(S * 0.012)).point(lambda v: int(v * 0.4))
    o = Image.new("RGBA", (S, S), (0, 12, 6, 0))
    o.putalpha(ombra)
    img = Image.alpha_composite(img, o)
    d = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dd = ImageDraw.Draw(d)
    dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=colore + (255,))
    riflesso = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(riflesso).ellipse([cx - rr * 0.62, cy - rr * 0.78, cx + rr * 0.12, cy - rr * 0.18], fill=(255, 255, 255, 105))
    riflesso = riflesso.filter(ImageFilter.GaussianBlur(S * 0.004))
    return Image.alpha_composite(Image.alpha_composite(img, d), riflesso)


def disegna(tema: str = "verde", scala: float = 1.0) -> Image.Image:
    """scala < 1: variante «maskable» per Android (il sistema ritaglia a cerchio, goccia, ecc.): il disegno occupa meno spazio."""
    p = TEMI[tema]
    img = sfumatura(p["alto"], p["basso"]).convert("RGBA")
    img = Image.alpha_composite(img, luce((int(S * 0.28), int(S * 0.2)), int(S * 0.62), p["luce1"], 0.30))
    img = Image.alpha_composite(img, luce((int(S * 0.85), int(S * 0.95)), int(S * 0.55), p["luce2"], 0.35))
    # il perimetro del campo, appena visibile
    campo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    m = int(S * (0.5 - 0.4 * scala))
    ImageDraw.Draw(campo).rounded_rectangle([m, m, S - m, S - m], radius=int(S * 0.125 * scala), outline=p["punto"] + (46,), width=int(S * 0.0125))
    img = Image.alpha_composite(img, campo)
    t = lambda v: 60 + (v - 60) * scala  # noqa: E731
    for x, y in PUNTI:
        img = punto(img, t(x), t(y), R_PUNTO * scala, p["punto"])
    return punto(img, t(CAPITANO[0]), t(CAPITANO[1]), R_CAPITANO * scala, p["capitano"]).convert("RGB")


def svg() -> str:
    p = TEMI["verde"]
    c = lambda t: "#%02x%02x%02x" % t  # noqa: E731
    cerchi = "".join(f'<circle cx="{x}" cy="{y}" r="{R_PUNTO}"/>' for x, y in PUNTI)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><title>SchieraXI</title>'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c(p["alto"])}"/><stop offset="1" stop-color="{c(p["basso"])}"/></linearGradient></defs>'
            '<rect width="120" height="120" rx="27" fill="url(#g)"/>'
            f'<rect x="12" y="12" width="96" height="96" rx="15" fill="none" stroke="{c(p["punto"])}" stroke-opacity=".18" stroke-width="1.5"/>'
            f'<g fill="{c(p["punto"])}">{cerchi}</g>'
            f'<circle cx="{CAPITANO[0]}" cy="{CAPITANO[1]}" r="{R_CAPITANO}" fill="{c(p["capitano"])}"/></svg>')


def main() -> None:
    (WEB / "icone").mkdir(exist_ok=True)
    for tema in TEMI:
        grande = disegna(tema)
        for lato in (180, 192, 512):
            grande.resize((lato, lato), Image.LANCZOS).save(WEB / "icone" / f"{tema}-{lato}.png", optimize=True)
            if tema == "verde":
                grande.resize((lato, lato), Image.LANCZOS).save(WEB / f"icona-{lato}.png", optimize=True)
        # Android: variante «maskable», a tutto campo e con il disegno dentro la zona sicura (cerchio del 80%)
        mask = disegna(tema, SCALA_MASKABLE)
        for lato in (192, 512):
            mask.resize((lato, lato), Image.LANCZOS).save(WEB / "icone" / f"{tema}-maskable-{lato}.png", optimize=True)
            if tema == "verde":
                mask.resize((lato, lato), Image.LANCZOS).save(WEB / f"icona-maskable-{lato}.png", optimize=True)
    (WEB / "icona.svg").write_text(svg(), encoding="utf-8")
    print("icone scritte in", WEB)


if __name__ == "__main__":
    main()
