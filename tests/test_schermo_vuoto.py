"""Foto dell'app iOS con lo schermo ancora vuoto (`ios/scripts/schermo_vuoto.py`, usato da `ios/scripts/screenshot.sh`, #860).

Una foto poteva uscire con la schermata d'avvio (`iphone_scuro_accesso-recupero.png` della corsa 44837338026), con il solo
marchio del caricamento (`ipad_scuro_verticale_giornate-confronto.png`, corse 44826938210 e 44837724561) o con uno scheletro
troppo chiaro per vedersi (`ipad_chiaro_orizzontale_giocatore-fondo.png`, corsa 44676311120), e la corsa restava verde.
Ora lo script guarda la foto: tolte le barre in alto e in basso, una schermata vera riempie lo schermo; se resta al più un oggetto
piccolo la foto si rifà e, se resta così, la corsa fallisce dicendolo.

Le immagini di `tests/dati/foto/` sono foto della demo (dati inventati) rimpicciolite a 200 punti sul lato lungo, come fa lo
script prima di guardarle: `vuota_*` vanno riconosciute, `piena_*` no. Le altre immagini sono costruite qui.
"""
import importlib.util
import os
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from test_foto_avvisi import BASH, serve_bash

RADICE = Path(__file__).resolve().parent.parent
SCRIPT = RADICE / "ios" / "scripts" / "schermo_vuoto.py"
FOTO = RADICE / "ios" / "scripts" / "screenshot.sh"
DATI = RADICE / "tests" / "dati" / "foto"
FIRMA = b"\x89PNG\r\n\x1a\n"


def _modulo():
    spec = importlib.util.spec_from_file_location("schermo_vuoto", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


sv = _modulo()


# ---------------------------------------------------------------- PNG costruiti qui, con tutti i filtri

def _pezzo(tipo, corpo):
    return struct.pack(">I", len(corpo)) + tipo + corpo + struct.pack(">I", zlib.crc32(tipo + corpo) & 0xFFFFFFFF)


def _filtra(riga, sopra, bpp, tipo):
    uscita = bytearray()
    for i, v in enumerate(riga):
        a = riga[i - bpp] if i >= bpp else 0
        b = sopra[i]
        c = sopra[i - bpp] if i >= bpp else 0
        if tipo == 0:
            p = 0
        elif tipo == 1:
            p = a
        elif tipo == 2:
            p = b
        elif tipo == 3:
            p = (a + b) // 2
        else:
            pp = a + b - c
            pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
            p = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
        uscita.append((v - p) & 255)
    return bytes(uscita)


def _png(pixel, tipo_colore=2, profondita=8, filtri=(0,), interlacciato=0):
    """Un PNG dei `pixel` (righe di tuple RGB) nel tipo di colore chiesto: 0 grigio, 2 RGB, 3 tavolozza, 4 grigio e alfa,
    6 RGBA. Con 16 bit ogni campione vale v*257 (il byte alto è v). Le righe usano a turno i `filtri`."""
    altezza, larghezza = len(pixel), len(pixel[0])
    tavolozza = sorted({p for riga in pixel for p in riga}) if tipo_colore == 3 else []

    def campioni(p):
        return {0: [p[0]], 2: list(p), 3: [tavolozza.index(p) if tavolozza else 0], 4: [p[0], 255], 6: [*p, 255]}[tipo_colore]

    lato = profondita // 8
    bpp = len(campioni(pixel[0][0])) * lato
    grezzi, sopra = b"", bytes(larghezza * bpp)
    for y, riga in enumerate(pixel):
        dati = b"".join(bytes([v] * lato) for p in riga for v in campioni(p))
        tipo = filtri[y % len(filtri)]
        grezzi += bytes([tipo]) + _filtra(dati, sopra, bpp, tipo)
        sopra = dati
    testa = struct.pack(">IIBBBBB", larghezza, altezza, profondita, tipo_colore, 0, 0, interlacciato)
    plte = _pezzo(b"PLTE", b"".join(bytes(c) for c in tavolozza)) if tavolozza else b""
    return FIRMA + _pezzo(b"IHDR", testa) + plte + _pezzo(b"IDAT", zlib.compress(grezzi)) + _pezzo(b"IEND", b"")


def _variopinta(larghezza=7, altezza=5, grigia=False):
    righe = []
    for y in range(altezza):
        riga = []
        for x in range(larghezza):
            r, g, b = (x * 37 + y * 11) % 256, (x * 5 + y * 71 + 128) % 256, (x * y * 13 + 7) % 256
            riga.append((r, r, r) if grigia else (r, g, b))
        righe.append(riga)
    return righe


@pytest.mark.parametrize("filtro", [0, 1, 2, 3, 4])
def test_legge_ogni_filtro_del_png(filtro):
    immagine = _variopinta()
    assert sv.leggi_png(_png(immagine, filtri=(filtro,))) == (7, 5, immagine)


def test_legge_righe_con_filtri_diversi():
    immagine = _variopinta(9, 10)
    assert sv.leggi_png(_png(immagine, filtri=(0, 1, 2, 3, 4))) == (9, 10, immagine)


@pytest.mark.parametrize("tipo_colore,profondita", [(0, 8), (0, 16), (2, 16), (3, 8), (4, 8), (6, 8), (6, 16)])
def test_legge_i_tipi_di_colore(tipo_colore, profondita):
    immagine = _variopinta(grigia=tipo_colore in (0, 4))
    assert sv.leggi_png(_png(immagine, tipo_colore, profondita, filtri=(4, 1, 3))) == (7, 5, immagine)


def test_le_immagini_della_cartella_si_leggono_come_le_legge_pillow():
    pil = pytest.importorskip("PIL.Image")
    for percorso in sorted(DATI.glob("*.png")):
        with pil.open(percorso) as img:
            rgb = img.convert("RGB")
            atteso = [[rgb.getpixel((x, y)) for x in range(rgb.width)] for y in range(rgb.height)]
        assert sv.leggi_png(percorso.read_bytes()) == (rgb.width, rgb.height, atteso), percorso.name


def test_i_png_scritti_da_pillow_in_ogni_modo_si_leggono(tmp_path):
    pil = pytest.importorskip("PIL.Image")
    base = pil.new("RGB", (13, 6))
    base.putdata([p for riga in _variopinta(13, 6) for p in riga])
    for modo in ("RGB", "RGBA", "L", "LA", "P"):
        img = base.convert(modo)
        img.save(tmp_path / f"{modo}.png")
        atteso = img.convert("RGB")
        righe = [[atteso.getpixel((x, y)) for x in range(13)] for y in range(6)]
        assert sv.leggi_png((tmp_path / f"{modo}.png").read_bytes()) == (13, 6, righe), modo


def test_png_che_non_si_sanno_leggere_danno_none():
    buona = _png(_variopinta())
    assert sv.leggi_png(b"non sono un png") is None
    assert sv.leggi_png(buona[:45]) is None                                    # tronco
    assert sv.leggi_png(_png(_variopinta(), interlacciato=1)) is None           # interlacciato: sips non lo scrive
    quattro_bit = FIRMA + _pezzo(b"IHDR", struct.pack(">IIBBBBB", 4, 2, 4, 0, 0, 0, 0)) \
        + _pezzo(b"IDAT", zlib.compress(b"\x00\x00\x00" * 2)) + _pezzo(b"IEND", b"")
    assert sv.leggi_png(quattro_bit) is None                                    # meno di 8 bit: sips non lo scrive
    rotta = bytearray(zlib.decompress(buona[buona.index(b"IDAT") + 4:buona.index(b"IEND") - 8]))
    rotta[0] = 7   # filtro che non esiste
    testa = buona[:buona.index(b"IDAT") - 4]
    assert sv.leggi_png(testa + _pezzo(b"IDAT", zlib.compress(bytes(rotta))) + _pezzo(b"IEND", b"")) is None


# ---------------------------------------------------------------- quando lo schermo è vuoto (immagini costruite)

def _schermo(larghezza, altezza, fondo, *oggetti):
    """Un'immagine finta: `fondo(x, y)` dà il colore del fondo; ogni oggetto è (x0, y0, x1, y1, colore) in frazioni dello schermo."""
    righe = []
    for y in range(altezza):
        riga = []
        for x in range(larghezza):
            colore = fondo(x, y)
            for x0, y0, x1, y1, c in oggetti:
                if x0 * larghezza <= x < x1 * larghezza and y0 * altezza <= y < y1 * altezza:
                    colore = c
            riga.append(colore)
        righe.append(riga)
    return larghezza, altezza, righe


BIANCO = (235, 245, 238)
LIME = (200, 240, 20)
NERO = (10, 10, 10)
VERDE_SCURO = (0, 64, 47)


def _pieno(_x, _y):
    return VERDE_SCURO


def _sfumato(x, y):
    """Il fondo dell'iPad: cambia piano piano (pochi livelli da un punto al vicino), non è un bordo."""
    return (20 + y * 30 // 200, 40 + x * 20 // 138, 35)


BARRA_DI_STATO = [(0.10, 0.02, 0.22, 0.04, BIANCO), (0.72, 0.02, 0.90, 0.04, BIANCO)]
MARCHIO = [(0.42, 0.45, 0.46, 0.47, BIANCO), (0.48, 0.45, 0.52, 0.47, BIANCO), (0.54, 0.45, 0.58, 0.47, BIANCO),
           (0.47, 0.49, 0.53, 0.51, LIME), (0.40, 0.53, 0.44, 0.55, BIANCO), (0.56, 0.53, 0.60, 0.55, BIANCO)]


def test_la_schermata_d_avvio_e_vuota():
    assert sv.vuoto(*_schermo(92, 200, _pieno, *BARRA_DI_STATO, *MARCHIO))


def test_il_marchio_del_caricamento_con_la_barra_in_alto_e_l_angolo_in_basso_e_vuoto():
    barra = [(0.22, 0.03, 0.78, 0.06, (60, 80, 70)), (0.30, 0.04, 0.45, 0.05, BIANCO), (0.55, 0.04, 0.70, 0.05, BIANCO)]
    angolo = [(0.95, 0.96, 0.99, 0.99, (150, 150, 150))]
    assert sv.vuoto(*_schermo(138, 200, _sfumato, *barra, *MARCHIO, *angolo))


def test_uno_schermo_senza_niente_e_vuoto():
    assert sv.vuoto(*_schermo(92, 200, _pieno, *BARRA_DI_STATO))


def test_uno_scheletro_troppo_chiaro_con_la_sola_barra_laterale_e_vuoto():
    fondo = (242, 242, 247)
    scheletro = [(0.27, 0.10 + i * 0.12, 0.92, 0.12 + i * 0.12, (229, 229, 234)) for i in range(7)]
    laterale = [(0.04, 0.16 + i * 0.05, 0.22, 0.18 + i * 0.05, NERO) for i in range(4)]
    assert sv.vuoto(*_schermo(200, 138, lambda _x, _y: fondo, *scheletro, *laterale))


def test_l_accesso_con_il_marchio_in_alto_e_il_modulo_non_e_vuoto():
    modulo = [(0.05, 0.36, 0.48, 0.40, LIME), (0.52, 0.36, 0.95, 0.40, (40, 40, 40)),
              (0.08, 0.45, 0.30, 0.47, BIANCO), (0.08, 0.55, 0.30, 0.57, BIANCO), (0.05, 0.62, 0.95, 0.66, (60, 60, 60))]
    marchio_in_alto = [(0.42, 0.12, 0.58, 0.20, BIANCO), (0.33, 0.23, 0.67, 0.26, BIANCO)]
    assert not sv.vuoto(*_schermo(92, 200, lambda _x, _y: NERO, *BARRA_DI_STATO, *marchio_in_alto, *modulo))


def test_una_lista_a_tutta_larghezza_non_e_vuota():
    righe = [(0.05, 0.20 + i * 0.06, 0.60 if i % 2 else 0.85, 0.22 + i * 0.06, BIANCO) for i in range(10)]
    assert not sv.vuoto(*_schermo(92, 200, lambda _x, _y: NERO, *BARRA_DI_STATO, *righe))


def test_una_colonna_stretta_ma_alta_non_e_vuota():
    """L'accesso sull'iPad in orizzontale: il modulo è una colonna al centro (36% dello schermo) che scende per metà schermo."""
    colonna = [(0.28 + (i % 3) * 0.04, 0.17 + i * 0.06, 0.64, 0.19 + i * 0.06, BIANCO) for i in range(9)]
    assert not sv.vuoto(*_schermo(200, 138, lambda _x, _y: NERO, *colonna))


def test_uno_stato_vuoto_con_il_marchio_e_un_titolo_largo_non_e_vuoto():
    titolo = [(0.20, 0.58, 0.80, 0.61, BIANCO), (0.28, 0.63, 0.72, 0.65, (150, 150, 150))]
    assert not sv.vuoto(*_schermo(92, 200, _pieno, *BARRA_DI_STATO, *MARCHIO, *titolo))


def test_le_barre_in_alto_e_in_basso_non_contano():
    """Barra di stato, barre delle schede e titolo in alto, barra delle schede in basso: senza niente in mezzo è vuoto."""
    alto = [(0.05, 0.08, 0.60, 0.14, BIANCO)]
    basso = [(0.10, 0.90, 0.90, 0.96, (90, 90, 90)), (0.15, 0.92, 0.85, 0.94, BIANCO)]
    assert sv.vuoto(*_schermo(92, 200, _pieno, *BARRA_DI_STATO, *alto, *basso))


# ---------------------------------------------------------------- le foto vere (rimpicciolite)

def _foto_della_cartella():
    return sorted(DATI.glob("*.png"))


def test_la_cartella_ha_foto_vuote_e_piene():
    nomi = [p.name for p in _foto_della_cartella()]
    assert any(n.startswith("vuota_") for n in nomi) and any(n.startswith("piena_") for n in nomi), nomi
    assert all(n.startswith(("vuota_", "piena_")) for n in nomi), nomi


@pytest.mark.parametrize("percorso", _foto_della_cartella(), ids=lambda p: p.name)
def test_le_foto_vere_si_riconoscono(percorso):
    larghezza, altezza, righe = sv.leggi_png(percorso.read_bytes())
    assert max(larghezza, altezza) == sv.LATO
    assert sv.vuoto(larghezza, altezza, righe) == percorso.name.startswith("vuota_")


# ---------------------------------------------------------------- uso da riga di comando

def test_uso_sbagliato_esce_con_2():
    assert sv.main(["schermo_vuoto.py"]) == sv.USO
    assert sv.main(["schermo_vuoto.py", "a.png", "b.png"]) == sv.USO


def test_un_file_che_non_e_un_png_non_si_puo_dire(tmp_path, capsys):
    rotto = tmp_path / "rotto.png"
    rotto.write_bytes(b"niente")
    assert sv.main(["schermo_vuoto.py", str(rotto)]) == sv.ERRORE
    assert sv.main(["schermo_vuoto.py", str(tmp_path / "manca.png")]) == sv.ERRORE
    assert "non" in capsys.readouterr().out


def test_dalla_riga_di_comando_una_foto_vuota_esce_con_3_e_dice_perche(capsys):
    assert sv.main(["schermo_vuoto.py", str(DATI / "vuota_avvio_iphone.png")]) == sv.VUOTO
    assert "schermo vuoto" in capsys.readouterr().out


def test_dalla_riga_di_comando_una_foto_piena_esce_con_0(capsys):
    assert sv.main(["schermo_vuoto.py", str(DATI / "piena_accesso_iphone.png")]) == sv.PIENO
    assert "schermata" in capsys.readouterr().out


def test_una_foto_grande_si_rimpicciolisce_prima_di_guardarla(tmp_path):
    grande = tmp_path / "grande.png"
    grande.write_bytes(_png([[(0, 0, 0)] * 500] * 2))
    chiamate = []

    def rimpicciolisci(origine, destinazione, lato):
        chiamate.append((Path(origine), lato))
        Path(destinazione).write_bytes((DATI / "vuota_caricamento_ipad.png").read_bytes())
        return True

    esito, _ = sv.esamina(grande, rimpicciolisci=rimpicciolisci)
    assert esito == sv.VUOTO
    assert chiamate == [(grande, sv.LATO)]
    assert [p.name for p in tmp_path.iterdir()] == ["grande.png"], "nessun file di prova resta accanto alle foto"


def test_una_foto_piccola_si_guarda_com_e_e_se_il_rimpicciolimento_non_riesce_non_si_puo_dire(tmp_path):
    def mai(*_):
        raise AssertionError("una foto già piccola non si rimpicciolisce")

    assert sv.esamina(DATI / "piena_accesso_iphone.png", rimpicciolisci=mai)[0] == sv.PIENO
    grande = tmp_path / "grande.png"
    grande.write_bytes(_png([[(0, 0, 0)] * 500] * 2))
    assert sv.esamina(grande, rimpicciolisci=lambda *_: False)[0] == sv.ERRORE


# ---------------------------------------------------------------- come screenshot.sh rifà le foto vuote (bash vero, comandi finti)

def _funzione(testo, nome):
    import re
    trovata = re.search(rf"^{nome}\(\) \{{\n.*?^\}}\n", testo, re.S | re.M)
    assert trovata, f"screenshot.sh non ha la funzione {nome}"
    return trovata.group(0)


def _scatta(tmp_path, fermo, vuoto, comandi="scatta UDID iphone_scuro accesso-recupero", raddrizza=0):
    """Lancia `comandi` con le funzioni di screenshot.sh. Simulatore, attese e sips sono finti; schermo_fermo.py e
    schermo_vuoto.py finti escono a turno con i codici di `fermo` e `vuoto` (poi 0). Torna (processo, chiamate in ordine)."""
    testo = FOTO.read_text(encoding="utf-8")
    uscita = tmp_path / "foto"
    uscita.mkdir(parents=True)
    code = tmp_path / "code"
    code.mkdir()
    (code / "fermo.txt").write_text("".join(f"{e}\n" for e in fermo), encoding="utf-8", newline="\n")
    (code / "vuoto.txt").write_text("".join(f"{e}\n" for e in vuoto), encoding="utf-8", newline="\n")
    righe = [
        "ID_APP=it.schieraxi.app", f'USCITA="{uscita.as_posix()}"', f'CODE="{code.as_posix()}"', "ERRORI=0", "IN_MOVIMENTO=0",
        "NON_RIUSCITI=()", "FOTO_VUOTE=()", "FOTO_RIFATTE=0", f"RADDRIZZA={raddrizza}",
        'xcrun() { [ "$2" = spawn ] && echo "UIKitApplication:$ID_APP"; return 0; }',
        'sleep() { echo "sleep $*" >> "$CODE/chiamate.txt"; }',
        "stat() { echo 999999; }",
        'sips() { echo "sips $*" >> "$CODE/chiamate.txt"; }',
        "avvisi_rifai() { return 0; }",
        "avvisi_riepilogo() { :; }",
        # il primo codice della fila e via dalla fila: head e tail, uguali con i comandi del Mac e con quelli di Linux (sed -i no)
        'prossimo() { local f="$CODE/$1.txt" n; n=$(head -n 1 "$f"); tail -n +2 "$f" > "$f.resto"; mv "$f.resto" "$f"; echo "${n:-0}"; }',
        "python3() {",
        '  local e',
        '  case "$2" in',
        '    *schermo_fermo.py) e=$(prossimo fermo); echo "fermo" >> "$CODE/chiamate.txt"; [ "$e" != 1 ] && : > "$4"; return "$e" ;;',
        '    *schermo_vuoto.py) e=$(prossimo vuoto); echo "vuoto $3" >> "$CODE/chiamate.txt"; '
        '[ "$e" = 3 ] && echo "schermo vuoto: solo un oggetto piccolo"; [ "$e" = 1 ] && echo "foto non leggibile"; return "$e" ;;',
        "  esac",
        "}",
        _funzione(testo, "scatta"),
        _funzione(testo, "riepilogo"),
        _funzione(testo, "fine"),
        comandi,
        'echo "ERRORI=$ERRORI IN_MOVIMENTO=$IN_MOVIMENTO"',
    ]
    prova = tmp_path / "prova.sh"
    prova.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", "")}
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=60, env=ambiente,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    chiamate = (code / "chiamate.txt").read_text(encoding="utf-8").splitlines() if (code / "chiamate.txt").exists() else []
    return r, chiamate


@serve_bash
def test_una_foto_vuota_si_rifa_e_se_poi_e_buona_non_e_un_problema(tmp_path):
    r, chiamate = _scatta(tmp_path, fermo=[0, 0], vuoto=[3, 0])
    assert r.returncode == 0, r.stderr
    assert chiamate.count("fermo") == 2, chiamate
    assert "ERRORI=0 IN_MOVIMENTO=0" in r.stdout
    assert "iphone_scuro / accesso-recupero: schermo vuoto: solo un oggetto piccolo; aspetto e rifaccio la foto" in r.stdout
    # tra le due foto si aspetta un po' (l'app sta ancora partendo o caricando)
    i = chiamate.index("vuoto " + (tmp_path / "foto" / "iphone_scuro_accesso-recupero.png").as_posix())
    assert "sleep 5" in chiamate[i:chiamate.index("fermo", i)]


@serve_bash
def test_una_foto_sempre_vuota_dopo_due_nuove_prove_e_un_errore_che_fa_fallire_la_corsa(tmp_path):
    r, chiamate = _scatta(tmp_path, fermo=[0, 0, 0, 0], vuoto=[3, 3, 3, 0],
                          comandi="scatta UDID iphone_scuro accesso-recupero; scatta UDID ipad lega; fine")
    assert chiamate.count("fermo") == 4, "tre foto per la prima schermata (una e due nuove prove), una per la seconda"
    assert r.returncode == 1, r.stdout + r.stderr
    assert "::error title=Foto::" in r.stdout
    errore = next(riga for riga in r.stdout.splitlines() if riga.startswith("::error"))
    assert "iphone_scuro / accesso-recupero" in errore and "ipad / lega" not in errore
    assert "Foto rifatte perché lo schermo era ancora vuoto (avvio o caricamento): 2" in r.stdout


@serve_bash
def test_senza_foto_vuote_la_fine_e_quella_di_prima(tmp_path):
    r, _ = _scatta(tmp_path / "una", fermo=[0], vuoto=[0], comandi="scatta UDID iphone_scuro formazione; fine")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "::error" not in r.stdout and "::warning" not in r.stdout
    r, _ = _scatta(tmp_path / "nessuna", fermo=[1], vuoto=[], comandi="scatta UDID iphone_scuro formazione; fine")
    assert r.returncode == 1, "nessuna foto: la corsa fallisce come prima"


@serve_bash
def test_le_foto_non_controllate_danno_un_avviso_visibile_su_github(tmp_path):
    """Il controllo stesso non riesce (manca sips, file illeggibile): non basta l'ATTENZIONE nel registro."""
    r, _ = _scatta(tmp_path, fermo=[0, 0], vuoto=[1, 0],
                   comandi="scatta UDID iphone_scuro accesso-recupero; scatta UDID iphone_scuro formazione; fine")
    assert r.returncode == 0, r.stdout + r.stderr
    avviso = next((riga for riga in r.stdout.splitlines() if riga.startswith("::warning")), "")
    assert avviso.startswith("::warning title=Foto::1 foto non controllate"), r.stdout
    assert "iphone_scuro / accesso-recupero" in avviso and "formazione" not in avviso
    assert "::error" not in r.stdout
    assert "Foto non controllate (il controllo dello schermo vuoto non è riuscito): 1" in r.stdout


@serve_bash
def test_se_nessuna_foto_si_puo_controllare_la_corsa_fallisce(tmp_path):
    """Se il controllo non va mai (sips che manca, Python rotto) le foto vuote passerebbero tutte: la corsa fallisce."""
    r, _ = _scatta(tmp_path, fermo=[0, 0], vuoto=[1, 1],
                   comandi="scatta UDID iphone_scuro accesso-recupero; scatta UDID iphone_scuro formazione; fine")
    assert r.returncode == 1, r.stdout + r.stderr
    assert any(riga.startswith("::warning title=Foto::2 foto non controllate") for riga in r.stdout.splitlines()), r.stdout
    errore = next((riga for riga in r.stdout.splitlines() if riga.startswith("::error")), "")
    assert errore.startswith("::error title=Foto::Nessuna foto controllata"), r.stdout


@serve_bash
def test_lo_schermo_in_movimento_si_conta_solo_per_la_foto_tenuta(tmp_path):
    r, _ = _scatta(tmp_path, fermo=[3, 0], vuoto=[3, 0])
    assert "ERRORI=0 IN_MOVIMENTO=0" in r.stdout, "la foto rifatta era ferma"
    assert "si muoveva ancora" not in r.stdout


@serve_bash
def test_una_foto_che_non_si_puo_controllare_e_un_problema_ma_non_si_rifa(tmp_path):
    r, chiamate = _scatta(tmp_path, fermo=[0], vuoto=[1])
    assert chiamate.count("fermo") == 1
    assert "ERRORI=1 IN_MOVIMENTO=0" in r.stdout
    assert "ATTENZIONE: foto non controllata (iphone_scuro / accesso-recupero): foto non leggibile" in r.stdout


@serve_bash
def test_la_foto_si_controlla_dopo_averla_raddrizzata(tmp_path):
    r, chiamate = _scatta(tmp_path, fermo=[0, 0], vuoto=[3, 0], raddrizza=1)
    file = (tmp_path / "foto" / "iphone_scuro_accesso-recupero.png").as_posix()
    girate = [i for i, c in enumerate(chiamate) if c.startswith("sips -r 270")]
    controlli = [i for i, c in enumerate(chiamate) if c == f"vuoto {file}"]
    assert len(girate) == 2 and len(controlli) == 2, chiamate
    assert girate[0] < controlli[0] < girate[1] < controlli[1], "ogni foto nuova si raddrizza e poi si controlla"


def test_la_foto_dell_avvio_prova_il_controllo_sul_mac():
    """`avvio_iphone.png` di solito mostra la schermata d'avvio: il registro dice cosa ne pensa il controllo (prova sul Mac vero,
    dove le foto si rimpiccioliscono con sips), senza fermare niente."""
    testo = FOTO.read_text(encoding="utf-8")
    avvio = testo.index('avvisi_foto "$UDID_IPHONE" "$USCITA/avvio_iphone.png"')
    assert 'schermo_vuoto.py" "$USCITA/avvio_iphone.png"' in testo[avvio:avvio + 600]


def test_lo_script_finisce_sempre_con_fine():
    testo = FOTO.read_text(encoding="utf-8")
    assert testo.count("\n  fine\n") + testo.count("\nfine\n") == 3, "foto dal vero, solo iPhone, iPhone e iPad"
    assert "riepilogo\n  [ \"$(ls" not in testo and "riepilogo\n[ \"$(ls" not in testo
