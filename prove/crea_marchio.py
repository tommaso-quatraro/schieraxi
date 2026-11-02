r"""Crea le versioni del marchio INDIPENDENTI DAL NOME (nessuna scritta) in assets/marchio/.
Stesse coordinate di crea_icone.py; nessuna immagine di terzi.

Uso: .venv\Scripts\python.exe prove\crea_marchio.py   (serve Pillow)
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crea_icone as ci  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "marchio"
P = ci.TEMI["verde"]
S = ci.S
SCURO = "#0b3d2e"      # punti del simbolo su fondo chiaro
CAPITANO_SCURO = "#5f8f00"


def svg_simbolo(punti: str, capitano: str, titolo: str = "Simbolo") -> str:
    cerchi = "".join(f'<circle cx="{x}" cy="{y}" r="{ci.R_PUNTO}"/>' for x, y in ci.PUNTI)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><title>{titolo}</title>'
            f'<g fill="{punti}">{cerchi}</g>'
            f'<circle cx="{ci.CAPITANO[0]}" cy="{ci.CAPITANO[1]}" r="{ci.R_CAPITANO}" fill="{capitano}"/></svg>\n')


def simbolo_png(colore_punti, colore_cap) -> Image.Image:
    """Il simbolo (con ombra e riflesso, come l'icona) su trasparente, S x S."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for x, y in ci.PUNTI:
        img = ci.punto(img, x, y, ci.R_PUNTO, colore_punti)
    return ci.punto(img, *ci.CAPITANO, ci.R_CAPITANO, colore_cap)


def fondo(w: int, h: int) -> Image.Image:
    return ci.sfumatura(P["alto"], P["basso"]).resize((w, h), Image.LANCZOS).convert("RGBA")


def con_simbolo(w: int, h: int, lato: int, centro_x: float) -> Image.Image:
    img = fondo(w, h)
    sim = simbolo_png(P["punto"], P["capitano"]).resize((lato, lato), Image.LANCZOS)
    img.alpha_composite(sim, (int(centro_x - lato / 2), int((h - lato) / 2)))
    return img.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Vettoriali: solo simbolo senza sfondo, nero, bianco
    (OUT / "simbolo.svg").write_text(svg_simbolo(SCURO, CAPITANO_SCURO), encoding="utf-8")
    (OUT / "simbolo-nero.svg").write_text(svg_simbolo("#000000", "#000000"), encoding="utf-8")
    (OUT / "simbolo-bianco.svg").write_text(svg_simbolo("#ffffff", "#ffffff"), encoding="utf-8")
    # App Store: quadrata, opaca (RGB), senza angoli (li arrotonda iOS)
    grande = ci.disegna("verde")
    grande.resize((1024, 1024), Image.LANCZOS).save(OUT / "app-store-1024.png", optimize=True)
    grande.resize((512, 512), Image.LANCZOS).save(OUT / "google-play-icona-512.png", optimize=True)
    # Google Play: grafica in primo piano 1024x500, solo simbolo su sfondo di marca
    con_simbolo(1024, 500, 400, 512).save(OUT / "google-play-primo-piano-1024x500.png", optimize=True)
    # Open Graph 1200x630: simbolo a sinistra, spazio vuoto per il nome a destra
    con_simbolo(1200, 630, 420, 330).save(OUT / "social-og-1200x630.png", optimize=True)
    # Avatar quadrato: con margine di sicurezza (i social ritagliano a cerchio)
    ci.disegna("verde", ci.SCALA_MASKABLE).resize((800, 800), Image.LANCZOS).save(OUT / "avatar-800.png", optimize=True)
    print("marchio scritto in", OUT)


if __name__ == "__main__":
    main()
