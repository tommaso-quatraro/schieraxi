"""Genera il nome disegnato «SchieraXI» (wordmark) dal font Archivo (licenza SIL OFL 1.1, file OFL.txt qui accanto).

«Schiera» sono le lettere di Archivo ExtraBold condensato (larghezza 72) trasformate in tracciati SVG, con la crenatura
del font. «XI» è disegnato su misura con lo spessore delle aste di Archivo:
  - X: due barre dritte che si incrociano, tagli orizzontali;
  - I: piena nella versione compatta; nella versione grande ha un taglio obliquo sottile vicino alla cima
    (il «punto» del palo). Sotto i ~40 px di altezza il taglio la farebbe leggere «i»: lì si usa la compatta.
Il sito e l'app non caricano nessun font: usano solo i tracciati.

Strumento per chi ridisegna il marchio, non serve per far girare l'app. In un ambiente a parte:
    python -m venv .venv-marchio
    .venv-marchio\\Scripts\\python.exe -m pip install fonttools uharfbuzz
    .venv-marchio\\Scripts\\python.exe assets\\marchio\\wordmark\\genera.py            (solo i file SVG qui)
    ... genera.py --sito             (riscrive anche il nome nelle pagine di sito/; poi alza VERSIONE in sito/sw.js)
    ... genera.py --og               (rifà sito/img/og.png con Chrome o Edge senza finestra)
    ... genera.py --swift PERCORSO   (scrive la View SwiftUI WordmarkSchieraXI)
Alla fine stampa i valori da copiare nella sezione «wordmark» di sito/stile.css se cambiano le proporzioni.
"""
from __future__ import annotations

import argparse
import base64
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

QUI = Path(__file__).resolve().parent
RADICE = QUI.parents[2]
FONT = QUI / "Archivo-sottoinsieme.ttf"
LUOGO = {"wght": 800, "wdth": 72}  # ExtraBold, condensato
TRACCIA = -0.005  # spaziatura fra le lettere (in em)
SPAZIO_XI = 0.012  # aria in più fra «a» e «X» (in em)
DIAGONALE = 0.9  # spessore delle barre della X rispetto all'asta
TESTA = 1.0  # altezza del pezzo in cima alla I (in aste)
TAGLIO = 0.1  # larghezza del taglio della I grande (in aste)
PENDENZA = 0.58  # inclinazione del taglio (0,58 = circa 30 gradi)
CHIARO = {"testo": "#10201a", "xi": "#378000"}
SCURO = {"testo": "#eef6f0", "xi": "#d4f34a"}


def f(v: float) -> str:
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _barra(sx: float, dx: float, alto: float, basso: float, t: float, verso: int) -> str:
    """Barra diagonale di spessore t (perpendicolare), tagli orizzontali, dentro il riquadro dato."""
    larg, h = dx - sx, basso - alto
    hw = t
    for _ in range(20):
        hw = t / (h / math.hypot(larg - hw, h))
    if verso > 0:
        pts = [(sx, alto), (sx + hw, alto), (dx, basso), (dx - hw, basso)]
    else:
        pts = [(dx - hw, alto), (dx, alto), (sx + hw, basso), (sx, basso)]
    return "M" + "L".join(f"{f(x)} {f(y)}" for x, y in pts) + "Z"


def disegna() -> dict:
    tt = TTFont(FONT)
    upm = tt["head"].unitsPerEm
    gs = tt.getGlyphSet(location=LUOGO)
    cmap = tt.getBestCmap()

    def limiti(nome):
        bp = BoundsPen(gs)
        gs[nome].draw(bp)
        return bp.bounds

    def tracciato(nome, dx):
        sp = SVGPathPen(gs, ntos=f)
        gs[nome].draw(TransformPen(sp, (1, 0, 0, -1, dx, cap)))
        return sp.getCommands()

    cap = limiti(cmap[ord("H")])[3]
    bI = limiti(cmap[ord("I")])
    asta = bI[2] - bI[0]

    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(FONT))))
    font.set_variations(LUOGO)

    def componi(testo):
        buf = hb.Buffer()
        buf.add_str(testo)
        buf.guess_segment_properties()
        hb.shape(font, buf, {"kern": True, "liga": False})
        x, out = 0.0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((tt.getGlyphName(info.codepoint), x + pos.x_offset))
            x += pos.x_advance + TRACCIA * upm
        return out

    pezzi = componi("SchieraXI")
    schierali = componi("Schierali")

    lettere = [tracciato(n, gx) for n, gx in pezzi[:7]]

    nX, xX = pezzi[7]
    bX = limiti(nX)
    sx, dx = xX + bX[0] + SPAZIO_XI * upm, xX + bX[2] + SPAZIO_XI * upm
    x1 = _barra(sx, dx, 0, cap, asta * DIAGONALE, +1)
    x2 = _barra(sx, dx, 0, cap, asta * DIAGONALE, -1)

    nI, xI = pezzi[8]
    cx = xI + (bI[0] + bI[2]) / 2 + SPAZIO_XI * upm
    s, d = cx - asta / 2, cx + asta / 2
    i_piena = f"M{f(s)} 0H{f(d)}V{f(cap)}H{f(s)}Z"
    a, g, k = asta * TESTA, asta * TAGLIO, PENDENZA * asta / 2
    i_testa = f"M{f(s)} 0H{f(d)}V{f(a - k)}L{f(s)} {f(a + k)}Z"
    i_palo = f"M{f(d)} {f(a - k + g)}V{f(cap)}H{f(s)}V{f(a + k + g)}Z"

    # partenza dell'animazione: «Schierali» (la l al posto della X, la i minuscola di Archivo al posto della I)
    nl, xl = schierali[7]
    elle = tracciato(nl, xl)
    ni, xi = schierali[8]
    rp = RecordingPen()
    gs[ni].draw(rp)
    bi = limiti(ni)
    sposta_i = xi + (bi[0] + bi[2]) / 2 - cx  # la i di «Schierali» sta più a sinistra della I finale
    alto_x = limiti(cmap[ord("x")])[3]  # altezza della x di questa istanza
    # il punto della i è il contorno più in alto: ne prendo il fondo
    ys = [pt[1] for op, pts in rp.value for pt in pts]
    fondo_punto = min(y for y in ys if y > alto_x + 5)
    scende_testa = (cap - fondo_punto) - a  # spostamento verticale del pezzo in cima all'inizio
    stringe = (bi[2] - bi[0]) / asta

    margine = upm * 0.02
    x0 = pezzi[0][1] + limiti(pezzi[0][0])[0] - margine
    y0 = min(cap - limiti(n)[3] for n, _ in pezzi[:7]) - margine
    x_fine = d + margine
    y_fine = cap + margine
    vb = (x0, y0, x_fine - x0, y_fine - y0)
    return {
        "viewBox": " ".join(f(v) for v in vb),
        "rapporto": vb[2] / vb[3],
        "lettere": lettere,
        "x1": x1, "x2": x2,
        "i_piena": i_piena, "i_testa": i_testa, "i_palo": i_palo,
        "elle": elle,
        "testa_da": scende_testa, "testa_stringe": stringe, "i_da": sposta_i,
    }


def svg_file(w: dict, colori: dict, grande: bool = True) -> str:
    xi = w["x1"] + w["x2"] + (w["i_testa"] + w["i_palo"] if grande else w["i_piena"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{w["viewBox"]}" role="img" aria-label="SchieraXI">'
            f'<path fill="{colori["testo"]}" d="{"".join(w["lettere"])}"/><path fill="{colori["xi"]}" d="{xi}"/></svg>\n')


def sprite(w: dict) -> str:
    nome = "".join(w["lettere"])
    grande = w["x1"] + w["x2"] + w["i_testa"] + w["i_palo"]
    compatto = w["x1"] + w["x2"] + w["i_piena"]
    return (f'<svg class="sprite" aria-hidden="true" focusable="false">'
            f'<symbol id="wm" viewBox="{w["viewBox"]}"><path fill="currentColor" d="{nome}"/><path class="xi-f" d="{grande}"/></symbol>'
            f'<symbol id="wm-c" viewBox="{w["viewBox"]}"><path fill="currentColor" d="{nome}"/><path class="xi-f" d="{compatto}"/></symbol></svg>')


def eroe(w: dict) -> str:
    """Nome grande animato della prima schermata: «Schierali» diventa «SchieraXI» (classi wm-* in sito/stile.css)."""
    lettere = "".join(f'<path class="wm-a" d="{d}"/>' for d in w["lettere"])
    return (f'<svg class="wm-svg wm-hero" viewBox="{w["viewBox"]}" aria-hidden="true" focusable="false">'
            f'<g class="wm-s" fill="currentColor">{lettere}</g>'
            f'<g class="wm-a wm-a8" fill="currentColor"><path class="wm-L" d="{w["elle"]}"/></g>'
            f'<path class="xi-f wm-X wm-X1" d="{w["x1"]}"/><path class="xi-f wm-X wm-X2" d="{w["x2"]}"/>'
            f'<g class="wm-a wm-a9"><path class="xi-f wm-I" d="{w["i_palo"]}"/><path class="xi-f wm-Id" d="{w["i_testa"]}"/></g></svg>')


PAGINE = ("index.html", "en/index.html", "404.html", "offline.html")


def aggiorna_sito(w: dict) -> None:
    for nome in PAGINE:
        p = RADICE / "sito" / nome
        t = p.read_text(encoding="utf-8")
        t, n = re.subn(r'<svg class="sprite".*?</symbol></svg>', lambda m: sprite(w), t, count=1, flags=re.S)
        assert n == 1, f"sprite non trovato in {nome}"
        if 'class="nome-gioco"' in t:
            t, n = re.subn(r'(<p class="nome-gioco"[^>]*>)<svg class="wm-svg wm-hero".*?</svg>(</p>)',
                           lambda m: m.group(1) + eroe(w) + m.group(2), t, count=1, flags=re.S)
            assert n == 1, f"nome grande non trovato in {nome}"
        p.write_text(t, encoding="utf-8", newline="\n")
        print("aggiornato sito/" + nome)


def _browser() -> str | None:
    for c in ("chrome", "google-chrome", "chromium", "msedge",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        trovato = shutil.which(c) or (c if Path(c).is_file() else None)
        if trovato:
            return trovato
    return None


def crea_og(w: dict) -> None:
    """Anteprima dei link 1200x630: simbolo a sinistra (social-og-1200x630.png) e nome a destra, colori del tema scuro."""
    b = _browser()
    if not b:
        raise SystemExit("Serve Chrome o Edge per creare og.png.")
    fondo = base64.b64encode((QUI.parent / "social-og-1200x630.png").read_bytes()).decode()
    alto = 124
    pagina = (f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;width:1200px;height:630px;overflow:hidden}}'
              f'body{{background:url(data:image/png;base64,{fondo})}}svg{{position:absolute;left:560px;top:{315 - alto // 2}px;'
              f'height:{alto}px;width:{alto * w["rapporto"]:.0f}px}}</style>{svg_file(w, SCURO)}')
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "og.html"
        html.write_text(pagina, encoding="utf-8")
        uscita = RADICE / "sito" / "img" / "og.png"
        subprocess.run([b, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--user-data-dir={Path(tmp) / 'profilo'}", "--window-size=1200,630",
                        f"--screenshot={uscita}", html.as_uri()], check=True, capture_output=True, timeout=120)
    print("creato sito/img/og.png")


def swift(w: dict, percorso: Path) -> None:
    vx, vy, vw, vh = map(float, w["viewBox"].split())

    def codice(d: str) -> str:
        righe, cur, inizio = [], (0.0, 0.0), (0.0, 0.0)

        def p(x, y):
            return f"p({x - vx:.1f}, {y - vy:.1f})"
        for cmd, arg in re.findall(r"([MLHVQCZ])([^MLHVQCZ]*)", d):
            n = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", arg)]
            if cmd == "M":
                cur = inizio = (n[0], n[1])
                righe.append(f"q.move(to: {p(*cur)})")
            elif cmd == "L":
                for i in range(0, len(n), 2):
                    cur = (n[i], n[i + 1])
                    righe.append(f"q.addLine(to: {p(*cur)})")
            elif cmd in "HV":
                cur = (n[0], cur[1]) if cmd == "H" else (cur[0], n[0])
                righe.append(f"q.addLine(to: {p(*cur)})")
            elif cmd == "Q":
                for i in range(0, len(n), 4):
                    righe.append(f"q.addQuadCurve(to: {p(n[i + 2], n[i + 3])}, control: {p(n[i], n[i + 1])})")
                    cur = (n[i + 2], n[i + 3])
            elif cmd == "C":
                for i in range(0, len(n), 6):
                    righe.append(f"q.addCurve(to: {p(n[i + 4], n[i + 5])}, control1: {p(n[i], n[i + 1])}, "
                                 f"control2: {p(n[i + 2], n[i + 3])})")
                    cur = (n[i + 4], n[i + 5])
            elif cmd == "Z":
                righe.append("q.closeSubpath()")
                cur = inizio
        return "\n        ".join(righe)

    testo = f'''import SwiftUI

/// Nome disegnato «SchieraXI» (versione compatta, I piena): «Schiera» nel colore del testo, «XI» nel colore d'accento.
/// Generato da assets/marchio/wordmark/genera.py: non modificare a mano.
struct WordmarkSchieraXI: View {{
    static let rapporto: CGFloat = {vw / vh:.4f}
    var accento: Color = Color("AccentoXI")
    var body: some View {{
        ZStack {{
            NomeForma().fill(.primary)
            XIForma().fill(accento)
        }}
        .aspectRatio(Self.rapporto, contentMode: .fit)
        .accessibilityElement()
        .accessibilityLabel("Schiera undici")
        .accessibilityAddTraits(.isHeader)
    }}
}}

private func scala(_ r: CGRect) -> (CGFloat, CGFloat) -> CGPoint {{
    let s = min(r.width / {vw:.1f}, r.height / {vh:.1f})
    return {{ x, y in CGPoint(x: r.minX + x * s, y: r.minY + y * s) }}
}}

private struct NomeForma: Shape {{
    func path(in r: CGRect) -> Path {{
        let p = scala(r); var q = Path()
        {codice("".join(w["lettere"]))}
        return q
    }}
}}

private struct XIForma: Shape {{
    func path(in r: CGRect) -> Path {{
        let p = scala(r); var q = Path()
        {codice(w["x1"] + w["x2"] + w["i_piena"])}
        return q
    }}
}}
'''
    percorso.write_text(testo, encoding="utf-8", newline="\n")
    print("scritto", percorso)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sito", action="store_true", help="riscrive il nome nelle pagine di sito/")
    ap.add_argument("--og", action="store_true", help="rifà sito/img/og.png")
    ap.add_argument("--swift", type=Path, help="scrive la View SwiftUI in questo file")
    arg = ap.parse_args()
    w = disegna()
    (QUI / "wordmark-chiaro.svg").write_text(svg_file(w, CHIARO), encoding="utf-8", newline="\n")
    (QUI / "wordmark-scuro.svg").write_text(svg_file(w, SCURO), encoding="utf-8", newline="\n")
    if arg.sito:
        aggiorna_sito(w)
    if arg.og:
        crea_og(w)
    if arg.swift:
        swift(w, arg.swift)
    print(f"stile.css: aspect-ratio {w['rapporto']:.4f}; palo translateX({w['i_da']:.0f}px); "
          f"testa translate({w['i_da']:.0f}px, {w['testa_da']:.0f}px) scale({w['testa_stringe']:.2f})")


if __name__ == "__main__":
    main()
