"""Copia della consigliata alla scadenza fatta dal server (fanta/copia_scadenza.py): una volta sola negli ultimi minuti, mai sopra
una scelta vera, anche per chi non ha mai aperto Formazione; a giornata finita Oggi ha il riepilogo. Orari simulati, file in una
cartella temporanea, nessuna rete."""
import threading
from datetime import datetime, timedelta

from fanta import consigli, copia_scadenza, diario, gestione, lega, regole, scelte
from fanta.contesto import FILE_UTENTE, Contesto
from test_fasi import PANCHINA, REGOLE, ST, TITOLARI, _giornata_finita, _oggi, ambiente  # noqa: F401  (ambiente = fixture)

SCADENZA = datetime(2026, 11, 7, 15, 0)          # prima partita della giornata 10 (regola della lega: 0 minuti)


def _ctx(cartella, a, utente_id=None):
    cartella.mkdir(parents=True, exist_ok=True)
    file = {k: cartella / v for k, v in FILE_UTENTE.items()}
    lega.salva(a.rose, file["rose"])
    regole.salva(REGOLE, file["regole"])
    return Contesto(utente_id=utente_id, immagini=cartella / "immagini", **file)


class _NonChiudere:
    """L'archivio finto è uno per test: `giro` chiude la sua connessione, qui la chiusura non fa niente."""
    def __init__(self, db):
        self.db = db

    def __getattr__(self, nome):
        return getattr(self.db, nome)

    def close(self):
        pass


def _db(a):
    return lambda: _NonChiudere(a.db)


def _con_giornata(monkeypatch, conta=None):
    vera = consigli.formazione

    def formazione(*x, **k):
        if conta is not None:
            conta.append(1)
        return vera(*x, **k) | {"giornata": 10}
    monkeypatch.setattr(consigli, "formazione", formazione)


def test_dovuta_solo_negli_ultimi_minuti():
    assert not copia_scadenza.dovuta(SCADENZA - timedelta(minutes=11), SCADENZA)
    assert copia_scadenza.dovuta(SCADENZA - copia_scadenza.ANTICIPO, SCADENZA)
    assert copia_scadenza.dovuta(SCADENZA - timedelta(minutes=1), SCADENZA)
    assert not copia_scadenza.dovuta(SCADENZA, SCADENZA)                  # a scadenza la formazione è chiusa
    assert not copia_scadenza.dovuta(SCADENZA, None)


def test_copia_una_volta_sola_e_riepilogo_a_giornata_finita(ambiente, monkeypatch):
    chiamate = []
    _con_giornata(monkeypatch, chiamate)
    ctx = _ctx(ambiente.tmp / "u1", ambiente, 1)
    fatte: set[str] = set()
    assert copia_scadenza.giro(SCADENZA - timedelta(minutes=30), [ctx], _db(ambiente), fatte) == []      # troppo presto
    assert chiamate == [] and scelte.leggi(ST, 10, ctx.scelte, anche_automatica=True) is None
    assert copia_scadenza.giro(SCADENZA - timedelta(minutes=8), [ctx], _db(ambiente), fatte) == [f"1/{ST}/10"]
    auto = scelte.leggi(ST, 10, ctx.scelte, anche_automatica=True)
    assert auto["tipo"] == scelte.TIPO_AUTOMATICA and auto["titolari"] == TITOLARI
    assert scelte.leggi(ST, 10, ctx.scelte) is None                       # non è una scelta dell'utente
    assert diario.carica(ctx.diario)["istantanee"][f"{ST}/10"]["atteso"] == 70.0
    assert copia_scadenza.giro(SCADENZA - timedelta(minutes=5), [ctx], _db(ambiente), fatte) == []       # una volta sola
    assert copia_scadenza.giro(SCADENZA + timedelta(minutes=1), [ctx], _db(ambiente), fatte) == []
    assert len(chiamate) == 1
    # a giornata finita Oggi ha il riepilogo, anche se l'utente non ha mai aperto Formazione
    _giornata_finita(ambiente)
    o = gestione.oggi(ambiente.db, REGOLE, ambiente.rose, adesso=datetime(2026, 11, 10, 10, 0), file_scelte=ctx.scelte,
                      file_diario=ctx.diario)
    r = o["riepilogo"]
    assert o["fase"] == "finita" and r is not None
    assert r["giornata"] == 10 and r["formazione_di"] == "consigliata" and r["punti_attesi"] == 70.0 and r["punti_fatti"] is not None


def test_senza_copia_il_riepilogo_manca(ambiente):
    """Il caso di prima: nessuno ha aperto Formazione e il server non ha copiato niente."""
    _giornata_finita(ambiente)
    assert _oggi(ambiente, datetime(2026, 11, 10, 10, 0))["riepilogo"] is None


def test_mai_sopra_una_scelta_vera(ambiente, monkeypatch):
    _con_giornata(monkeypatch)
    ctx = _ctx(ambiente.tmp / "u2", ambiente, 2)
    mia = TITOLARI[:10] + [PANCHINA[0]]
    scelte.salva(ST, 10, mia, "4-4-2", ctx.scelte)
    copia_scadenza.giro(SCADENZA - timedelta(minutes=5), [ctx], _db(ambiente), set())
    v = scelte.leggi(ST, 10, ctx.scelte)
    assert v["titolari"] == mia and v["tipo"] == "manuale"
    assert f"{ST}/10" in diario.carica(ctx.diario)["istantanee"]        # la consigliata di allora resta per il confronto del Diario


def test_ogni_utente_con_i_suoi_file_e_chi_non_ha_squadra_si_salta(ambiente, monkeypatch):
    _con_giornata(monkeypatch)
    uno, due = _ctx(ambiente.tmp / "u1", ambiente, 1), _ctx(ambiente.tmp / "u2", ambiente, 2)
    vuoto = Contesto(utente_id=3, immagini=ambiente.tmp / "u3" / "immagini",
                     **{k: ambiente.tmp / "u3" / v for k, v in FILE_UTENTE.items()})          # nessuna rosa
    rotto = _ctx(ambiente.tmp / "u4", ambiente, 4)
    rotto.rose.write_text("{non è json", encoding="utf-8")
    fatte = copia_scadenza.giro(SCADENZA - timedelta(minutes=5), [vuoto, rotto, uno, due], _db(ambiente), set())
    assert fatte == [f"1/{ST}/10", f"2/{ST}/10"]                          # un errore con un utente non ferma gli altri
    for c in (uno, due):
        assert scelte.leggi(ST, 10, c.scelte, anche_automatica=True)["tipo"] == scelte.TIPO_AUTOMATICA
    assert not (ambiente.tmp / "u3" / "scelte.json").exists()


def test_calcolo_non_riuscito_si_riprova(ambiente, monkeypatch):
    ctx = _ctx(ambiente.tmp / "u1", ambiente, 1)
    vera = consigli.formazione
    esiti = iter([RuntimeError("occupato")])

    def formazione(*x, **k):
        e = next(esiti, None)
        if e:
            raise e
        return vera(*x, **k) | {"giornata": 10}
    monkeypatch.setattr(consigli, "formazione", formazione)
    fatte: set[str] = set()
    assert copia_scadenza.giro(SCADENZA - timedelta(minutes=6), [ctx], _db(ambiente), fatte) == []
    assert copia_scadenza.giro(SCADENZA - timedelta(minutes=5), [ctx], _db(ambiente), fatte) == [f"1/{ST}/10"]


def test_sorveglia_rispetta_l_interruttore(ambiente, monkeypatch):
    _con_giornata(monkeypatch)
    ctx = _ctx(ambiente.tmp / "u1", ambiente, 1)
    giri = []
    monkeypatch.setattr(copia_scadenza, "giro", lambda *a: giri.append(1) or [])
    for valore, attesi in (("0", 0), ("1", 1)):
        monkeypatch.setenv("FANTA_COPIA_SCADENZA", valore)
        giri.clear()
        fermo = threading.Event()
        t = threading.Thread(daemon=True, target=copia_scadenza.sorveglia, args=(fermo, lambda: [ctx], _db(ambiente), 0.01,
                                                                    lambda: SCADENZA - timedelta(minutes=5)))
        t.start()
        threading.Event().wait(0.05)
        fermo.set()
        t.join(2)
        assert (len(giri) > 0) == bool(attesi)
