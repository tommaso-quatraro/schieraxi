"""Attesa dello schermo fermo per le foto dell'app iOS (`ios/scripts/schermo_fermo.py`, usato da `ios/scripts/screenshot.sh`).

Le foto uscivano mentre la schermata caricava (scheletro «Scelgo gli undici…») o mentre i numeri salivano («0,0 Fantavoto
atteso»): ora lo script fotografa quando due foto di fila hanno gli stessi pixel. Immagini inventate, costruite qui.
"""
import importlib.util
import struct
import zlib
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
SCRIPT = RADICE / "ios" / "scripts" / "schermo_fermo.py"
FIRMA = b"\x89PNG\r\n\x1a\n"


def _modulo():
    spec = importlib.util.spec_from_file_location("schermo_fermo", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


sf = _modulo()


def _pezzo(tipo, corpo):
    return struct.pack(">I", len(corpo)) + tipo + corpo + struct.pack(">I", zlib.crc32(tipo + corpo) & 0xFFFFFFFF)


def _png(righe, larghezza=2, livello=6, extra=b"", pezzi_idat=1):
    """Un PNG RGB a 8 bit: `righe` sono i byte dei pixel di ogni riga (3 per pixel), senza filtro."""
    testa = struct.pack(">IIBBBBB", larghezza, len(righe), 8, 2, 0, 0, 0)
    compressi = zlib.compress(b"".join(b"\x00" + r for r in righe), livello)
    passo = max(1, len(compressi) // pezzi_idat + 1)
    idat = b"".join(_pezzo(b"IDAT", compressi[i:i + passo]) for i in range(0, len(compressi), passo))
    return FIRMA + _pezzo(b"IHDR", testa) + extra + idat + _pezzo(b"IEND", b"")


ROSSO = [b"\xff\x00\x00" * 2, b"\xff\x00\x00" * 2]
VERDE = [b"\x00\xff\x00" * 2, b"\x00\xff\x00" * 2]


def test_stessi_pixel_sono_uguali_anche_con_metadati_e_compressione_diversi(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(_png(ROSSO, livello=1, extra=_pezzo(b"tEXt", b"Creation Time\x0009:41:00")))
    b.write_bytes(_png(ROSSO, livello=9, extra=_pezzo(b"tEXt", b"Creation Time\x0009:41:01"), pezzi_idat=3))
    assert a.read_bytes() != b.read_bytes()
    assert sf.uguali(a, b)


def test_pixel_diversi_non_sono_uguali(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(_png(ROSSO))
    b.write_bytes(_png(VERDE))
    assert not sf.uguali(a, b)


def test_stessi_byte_con_misure_diverse_non_sono_uguali(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(_png([b"\x01" * 6, b"\x01" * 6], larghezza=2))
    b.write_bytes(_png([b"\x01" * 6, b"\x01" * 6], larghezza=1))   # stessi dati, intestazione diversa
    assert not sf.uguali(a, b)


def test_file_mancanti_o_rotti_non_sono_mai_uguali(tmp_path):
    rotto = tmp_path / "rotto.png"
    rotto.write_bytes(b"non sono un png")
    tronco = tmp_path / "tronco.png"
    tronco.write_bytes(_png(ROSSO)[:40])
    assert not sf.uguali(tmp_path / "manca.png", tmp_path / "manca.png")
    assert not sf.uguali(rotto, rotto)
    assert not sf.uguali(tronco, tronco)


class Fotocamera:
    """Finto simulatore: ogni scatto scrive il fotogramma successivo; l'orologio va avanti solo con `dormi`."""

    def __init__(self, fotogrammi, fallisce_dal=None):
        self.fotogrammi = list(fotogrammi)
        self.scatti = 0
        self.adesso = 0.0
        self.fallisce_dal = fallisce_dal

    def scatta(self, percorso):
        self.scatti += 1
        if self.fallisce_dal is not None and self.scatti >= self.fallisce_dal:
            return False
        indice = min(self.scatti - 1, len(self.fotogrammi) - 1)
        Path(percorso).write_bytes(self.fotogrammi[indice])
        return True

    def orologio(self):
        return self.adesso

    def dormi(self, secondi):
        self.adesso += secondi


def _aspetta(camera, file, massimo=8.0):
    return sf.aspetta_fermo(camera.scatta, file, massimo=massimo, intervallo=1.0,
                            orologio=camera.orologio, dormi=camera.dormi)


def test_fotografa_quando_due_foto_di_fila_sono_uguali(tmp_path):
    caricamento1 = _png([b"\x10" * 6, b"\x20" * 6])
    caricamento2 = _png([b"\x20" * 6, b"\x10" * 6])
    pronta = _png(VERDE)
    camera = Fotocamera([caricamento1, caricamento2, pronta, pronta, _png(ROSSO)])
    file = tmp_path / "foto.png"
    assert _aspetta(camera, file) == sf.FERMO
    assert camera.scatti == 4
    assert sf.uguali(file, _scrivi(tmp_path / "attesa.png", pronta))


def test_schermo_sempre_in_movimento_si_fotografa_allo_scadere_con_l_ultima_foto(tmp_path):
    fotogrammi = [_png([bytes([i]) * 6, b"\x00" * 6]) for i in range(30)]
    camera = Fotocamera(fotogrammi)
    file = tmp_path / "foto.png"
    assert _aspetta(camera, file, massimo=5.0) == sf.SI_MUOVE
    assert camera.adesso == 5.0
    assert camera.scatti == 6   # la prima e una al secondo per 5 secondi
    assert sf.uguali(file, _scrivi(tmp_path / "attesa.png", fotogrammi[5]))


def test_primo_scatto_non_riuscito_e_un_errore_e_non_lascia_file(tmp_path):
    camera = Fotocamera([_png(ROSSO)], fallisce_dal=1)
    file = tmp_path / "foto.png"
    assert _aspetta(camera, file) == sf.ERRORE
    assert not file.exists()


def test_se_un_secondo_scatto_non_riesce_resta_la_foto_buona(tmp_path):
    camera = Fotocamera([_png(ROSSO), _png(VERDE)], fallisce_dal=2)
    file = tmp_path / "foto.png"
    assert _aspetta(camera, file) == sf.SI_MUOVE
    assert sf.uguali(file, _scrivi(tmp_path / "attesa.png", _png(ROSSO)))


def test_nessun_file_di_prova_resta_accanto_alle_foto(tmp_path):
    pronta = _png(VERDE)
    camera = Fotocamera([_png(ROSSO), pronta, pronta])
    file = tmp_path / "foto.png"
    _aspetta(camera, file)
    assert [p.name for p in tmp_path.iterdir()] == ["foto.png"]


def test_uso_sbagliato_esce_con_2():
    assert sf.main(["schermo_fermo.py"]) == 2
    assert sf.main(["schermo_fermo.py", "udid", "foto.png", "tanti"]) == 2


def test_lo_script_delle_foto_aspetta_lo_schermo_fermo_e_conosce_il_fondo_dell_account():
    testo = (RADICE / "ios" / "scripts" / "screenshot.sh").read_text(encoding="utf-8")
    assert "schermo_fermo.py" in testo
    assert "accesso-account-fondo" in testo
    # «accesso-account-fondo» = scenario «account» con -DEMO_FONDO, non uno scenario «account-fondo» che l'app non conosce
    assert '-DEMO_ACCESSO "${schermata#accesso-}"' in testo


def _scrivi(percorso, dati):
    percorso.write_bytes(dati)
    return percorso
