"""Contrasto del grigio secondario (--testo-2) sui fondi principali della web app: calcolo dai valori del CSS.
Uso: python fondi.py   (i due punti del fondo sfumato vengono da sfondo.mjs; vedi docs/DESIGN.md, «Grigio secondario»)"""
def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def L(rgb): return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])
def hx(s): s = s.lstrip("#"); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
def sopra(fg, a, bg): return tuple(a * f + (1 - a) * b for f, b in zip(fg, bg))
def cr(a, b):
    la, lb = sorted([L(a), L(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)

# --- chiaro (stile.css, tema chiaro)
sf = hx("#eaf3ee"); bianco = (255, 255, 255)
carta_ch = lambda fondo: sopra(bianco, .72, fondo)  # --vetro-carta
# i punti piu carichi del fondo sfumato sono stati misurati sul fondo vero di Chrome (sfondo.mjs: 20 immagini, 2 larghezze, 5 momenti)
SFUM_CH = (163, 199, 201)   # punto piu scuro del fondo in chiaro (macchie verde e blu sovrapposte)
SFUM_SC = (39, 97, 96)      # punto piu chiaro del fondo in scuro
fondi_chiaro = {
    "bianco": bianco,
    "fondo piatto (#eaf3ee)": sf,
    "carta su fondo piatto": carta_ch(sf),
    "fondo sfumato, punto piu carico": SFUM_CH,
    "carta su fondo sfumato piu carico": carta_ch(SFUM_CH),
}
sf_d = hx("#07100b"); carta_rgb = (26, 42, 33)
carta_sc = lambda fondo: sopra(carta_rgb, .62, fondo)
chiara_luce = lambda fondo: sopra(bianco, .06, fondo)   # velo di luce della carta (luce-2)
fondi_scuro = {
    "fondo piatto (#07100b)": sf_d,
    "carta su fondo piatto": chiara_luce(carta_sc(sf_d)),
    "fondo sfumato, punto piu carico": SFUM_SC,
    "carta su fondo sfumato piu carico": chiara_luce(carta_sc(SFUM_SC)),
    "carta con riflesso del dito (+22% bianco)": sopra(bianco, .22, chiara_luce(carta_sc(SFUM_SC))),
}

def tabella(titolo, fondi, colori):
    print(f"\n{titolo}")
    print("| fondo | " + " | ".join(colori) + " |")
    print("|---|" + "---|" * len(colori))
    for nome, f in fondi.items():
        print(f"| {nome} | " + " | ".join(f"{cr(hx(c), f):.2f}" for c in colori) + " |")

tabella("CHIARO (vecchio #587064, nuovo #46564D)", fondi_chiaro, ["#587064", "#46564D"])
tabella("SCURO (vecchio #B3C6BA, iOS #BCCDC2)", fondi_scuro, ["#B3C6BA", "#BCCDC2"])
