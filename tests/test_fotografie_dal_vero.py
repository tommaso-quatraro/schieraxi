"""Le parti pure di prove/fotografie_dal_vero.py: nomi inventati coerenti, nessun nome vero che resta, orologio fermo."""
import importlib.util
from datetime import date, datetime
from pathlib import Path

_FILE = Path(__file__).resolve().parent.parent / "prove" / "fotografie_dal_vero.py"
_spec = importlib.util.spec_from_file_location("fotografie_dal_vero", _FILE)
fv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fv)

VERI = {"Rossetti", "Bianconeri", "Lautarini", "Esposti", "Martinelli"}      # nomi d'esempio, inventati


def test_lo_stesso_pezzo_diventa_sempre_lo_stesso_nome_finto():
    finti = fv.NomiFinti(VERI)
    a = finti.nome("Rossetti M.")
    b = finti.nome("Mario ROSSETTI")
    assert a.endswith(" M.") and a.split()[0].upper() == b.split()[1]
    assert finti.nome("Di Martinelli").startswith("Di ")              # le particelle restano
    assert finti.nome("Mario Rossetti").startswith("Mario ")          # un pezzo che non è un nome vero resta com'è


def test_un_nome_finto_non_e_mai_un_nome_vero_ne_lo_contiene():
    finti = fv.NomiFinti(VERI, vietate=["zzz"])
    for vero in VERI:
        f = fv.piega(finti.pezzo(vero))
        assert f not in {fv.piega(v) for v in VERI}
        assert not any(fv.piega(v) in f for v in VERI if len(v) >= 5)
        assert "zzz" not in f and not any(s in f for s in fv.SCONCI)


def test_il_controllo_trova_nomi_veri_email_e_indirizzi_ma_non_le_parole_italiane():
    veri = {fv.piega(v) for v in VERI} | {"massimo"}
    assert fv.controlla('{"testo": "al massimo 3 cambi"}', [], veri, fv.PAROLE_ITALIANE) == []
    assert fv.controlla('{"nome": "Rossetti"}', [], veri, fv.PAROLE_ITALIANE)
    assert fv.controlla('{"nome": "Massimo Verdi"}', [], veri, fv.PAROLE_ITALIANE)       # con la maiuscola è un nome
    assert fv.controlla('{"e": "uno@esempio.it"}', [], set(), set())
    assert fv.controlla('{"e": "https://casa.' + 'ts.net"}', [], set(), set())          # a pezzi: il controllo dei residui
    problemi = fv.controlla('{"x": "Squadra Segreta"}', ["segreta"], set(), set())
    assert problemi == ["parola vietata n. 1 del file privato"]                          # la parola non si stampa


def test_l_orologio_fermo_vale_per_i_moduli_di_fanta(monkeypatch):
    import sys
    import types
    finto = types.ModuleType("fanta.finto_per_test")
    finto.datetime, finto.date = datetime, date
    monkeypatch.setitem(sys.modules, "fanta.finto_per_test", finto)
    momento = datetime(2026, 10, 25, 13, 42)
    monkeypatch.setattr(fv, "_moduli_da_fermare", lambda: [finto])
    fv.ferma_orologio(momento)
    assert finto.datetime.now() == momento
    assert finto.date.today() == momento.date()
    assert isinstance(datetime(2026, 1, 1), finto.datetime)        # le date normali restano «datetime» per i controlli isinstance


def test_la_mappatura_privata_vale_in_ogni_forma_del_nome():
    coppie = sorted(fv.leggi_mappatura("# commento\nMario Rossi => Luca Bianchi\nI Lupi => Squadra Demo\n").items(),
                    key=lambda c: -len(c[0]))
    testo = "Mario Rossi, /api/rosa?squadra=I%20Lupi, mario-rossi, MARIO ROSSI, i_lupi"
    assert fv.applica_mappatura(testo, coppie) == "Luca Bianchi, /api/rosa?squadra=Squadra%20Demo, luca-bianchi, LUCA BIANCHI, squadra_demo"
