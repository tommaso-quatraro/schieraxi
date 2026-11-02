"""Contrasto reale del testo: legge la cartella prodotta da scatta.mjs e scrive riassunto.json.
Uso: python analizza.py <cartella>   (per ogni testo: colore vero con opacita, contro il fondo vero sotto le sue lettere, al 10% peggiore (gli angoli delle pillole non contano))"""
import json, re, sys
from pathlib import Path
import numpy as np
from PIL import Image

def lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def lum(rgb):  # rgb: (...,3) in 0..255
    l = lin(np.asarray(rgb, float))
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]

def rapporto(l1, l2):
    a, b = np.maximum(l1, l2), np.minimum(l1, l2)
    return (a + 0.05) / (b + 0.05)

def colore(s):
    m = re.findall(r"[\d.]+", s)
    v = [float(x) for x in m]
    return np.array(v[:3]), (v[3] if len(v) > 3 else 1.0)

cartella = Path(sys.argv[1])
righe = []
for f in sorted(cartella.glob("*.json")):
    if f.name in ("indice.json", "riassunto.json"):
        continue
    d = json.loads(f.read_text(encoding="utf-8"))
    img = np.asarray(Image.open(f.with_suffix(".png")).convert("RGB"), float)
    sec_rgb, _ = colore(d["testo2"]) if d["testo2"].startswith("rgb") else (np.array([int(d["testo2"][i:i + 2], 16) for i in (1, 3, 5)], float), 1)
    for t in d["testi"]:
        x0, y0 = int(max(0, t["x"])), int(max(0, t["y"]))
        x1, y1 = int(min(img.shape[1], t["x"] + t["w"] + 1)), int(min(img.shape[0], t["y"] + t["h"] + 1))
        reg = img[y0:y1, x0:x1].reshape(-1, 3)
        if len(reg) == 0:
            continue
        fg, a = colore(t["c"])
        a *= t["op"]
        eff = a * fg + (1 - a) * reg
        r = rapporto(lum(eff), lum(reg))
        peggiore = float(np.percentile(r, 10))
        grande = t["fs"] >= 24 or (t["fs"] >= 18.66 and t["fw"] >= 700)
        soglia = 3.0 if grande else 4.5
        e_sec = bool(np.allclose(fg, sec_rgb, atol=1)) and a >= 0.99
        sbiadito = t["op"] < 0.97
        righe.append(dict(ay=round(t.get('ay', t['y'])), ax=round(t['x']), file=f.stem, scena=d["scena"], tema=d["tema"], larg=d["larghezza"], t=t["t"], cls=t["cls"], tag=t["tag"], fs=t["fs"],
                          op=round(t["op"], 2), r=round(peggiore, 2), soglia=soglia, sec=e_sec, sbiadito=sbiadito))
vis = {}
for x in righe:
    k = (x["scena"], x["tema"], x["larg"], x["t"], x["cls"], x["ay"], x["ax"])
    if k not in vis or x["r"] < vis[k]["r"]:
        vis[k] = x
righe = list(vis.values())
(cartella / "riassunto.json").write_text(json.dumps(righe, ensure_ascii=False), encoding="utf-8")

def stampa(titolo, sel):
    print(f"\n== {titolo} ==")
    gruppi = {}
    for r in righe:
        if sel(r):
            gruppi.setdefault((r["tema"], r["larg"]), []).append(r)
    for k in sorted(gruppi):
        v = gruppi[k]
        rs = np.array([x["r"] for x in v])
        sotto = sum(1 for x in v if x["r"] < x["soglia"])
        print(f"{k[0]:5s} {k[1]:5d}px  testi {len(v):4d}  minimo {rs.min():5.2f}  10% peggiori <= {np.percentile(rs, 10):5.2f}  mediana {np.median(rs):5.2f}  sotto soglia {sotto}")
stampa("testo secondario (--testo-2 pieno)", lambda r: r["sec"])
stampa("testo sbiadito da opacita", lambda r: r["sbiadito"])
stampa("tutti i testi", lambda r: True)
print("\n== i 12 peggiori in assoluto (sotto soglia) ==")
for x in sorted([x for x in righe if x["r"] < x["soglia"]], key=lambda x: x["r"] - x["soglia"])[:12]:
    print(f'{x["r"]:5.2f}/{x["soglia"]}  {x["scena"]:12s} {x["tema"]:5s} {x["larg"]:5d}  {x["tag"]}.{x["cls"]:16s} sec={x["sec"]} op={x["op"]}  "{x["t"]}"')
