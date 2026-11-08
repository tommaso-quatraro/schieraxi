"""La sentinella ricorda ogni giro (H1, #532): una voce {quando, rotte, inviato} per ogni giro del server nel file di stato,
letta da `giri_sentinella`, dal comando `sentinella --giri` e dal campo `sentinella_giri` di «Stato dei dati».

Serve alla «giornata senza errori» (spec di prodotto, §6): il comando `giornata` del coordinatore (H2) legge questi giri.
Orologio sempre passato come `adesso`, canale finto, archivio e file di stato in cartelle temporanee."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from fanta import archivio, sentinella, stato_dati
from fanta.__main__ import main
from fanta.sentinella import Rottura

ST = "2026-27"
ADESSO = datetime(2026, 11, 15, 20, 0)               # senza fuso, come lo passa il cron
UN = Rottura("punti_diversi", "utente 3", 11, "widget 70.0 contro oggi 72.4")
DUE = Rottura("risposta_in_errore", "utente 4", 11, "widget: KeyError")


def _esito(*rotture, controllati=("utente 3", "utente 4")):
    return {"rotture": list(rotture), "controllati": list(controllati), "rimandati": 0, "secondi": 1.0, "stagione": ST}


def _ora(dopo: timedelta = timedelta()) -> str:
    """Come la sentinella scrive `quando`: l'ora del giro con il fuso del server e i secondi."""
    return (ADESSO + dopo).astimezone().isoformat(timespec="seconds")


class Server:
    """Giri del cron in fila: `esegui` finto (trova le rotture date) e canale finto (riesce o no)."""

    def __init__(self, tmp_path, monkeypatch):
        self.file = tmp_path / "sentinella.json"
        self.db = tmp_path / "fanta.sqlite"
        self.riesce = True
        self.mandati: list[str] = []
        self.trovate: list[Rottura] = []
        monkeypatch.setattr(sentinella, "esegui", lambda db, adesso, minuti, stato: _esito(*self.trovate))

    def manda(self, titolo, testo):
        self.mandati.append(testo)
        return self.riesce

    def giro(self, ore, *rotture, senza_invio=False, manda=None):
        self.trovate = list(rotture)
        sentinella.giro(manda=None if senza_invio else (manda or self.manda), file_stato=self.file,
                        adesso=ADESSO + timedelta(hours=ore), scrivi=lambda s: None, db_percorso=self.db)

    def giri(self) -> list[dict]:
        return json.loads(self.file.read_text(encoding="utf-8"))["giri"]


@pytest.fixture
def server(tmp_path, monkeypatch):
    return Server(tmp_path, monkeypatch)


def _scrivi_stato(file, **campi):
    file.write_text(json.dumps(campi), encoding="utf-8")


# ---------------------------------------------------------------- ogni giro del server entra nella storia
def test_ogni_giro_entra_anche_senza_rotture(server):
    for h in range(3):
        server.giro(h)
    giri = server.giri()
    assert giri == [{"quando": _ora(timedelta(hours=h)), "rotte": [], "inviato": False} for h in range(3)]
    for h, g in enumerate(giri):
        quando = datetime.fromisoformat(g["quando"])
        assert quando.utcoffset() is not None                       # con il fuso, anche se `adesso` non lo ha
        assert quando == (ADESSO + timedelta(hours=h)).astimezone()


def test_rottura_gia_avvisata_entra_con_inviato_falso(server):
    server.giro(0, UN)                  # vista una volta sola: non è ancora un allarme
    server.giro(1, UN)                  # confermata: l'avviso parte
    server.giro(2, UN)                  # ancora rotta, già avvisata: nessun avviso nuovo
    assert len(server.mandati) == 1
    assert [(g["rotte"], g["inviato"]) for g in server.giri()] == [
        ([], False), (["punti_diversi"], True), (["punti_diversi"], False)]


def test_invio_fallito_entra_con_inviato_falso(server, tmp_path, monkeypatch):
    server.riesce = False
    server.giro(0, UN)
    server.giro(1, UN)                  # confermata, ma la rete non c'era
    assert len(server.mandati) == 1
    assert server.giri()[-1] == {"quando": _ora(timedelta(hours=1)), "rotte": ["punti_diversi"], "inviato": False}
    # canale mancante: lo stesso, il giro entra con inviato falso (e non parte niente verso la rete)
    monkeypatch.setenv("SCHIERAXI_CANALE", str(tmp_path / "manca"))
    server.giro(2, UN, manda=sentinella.manda_ntfy)
    assert server.giri()[-1] == {"quando": _ora(timedelta(hours=2)), "rotte": ["punti_diversi"], "inviato": False}


def test_senza_invio_non_registra_il_giro(server):
    server.giro(0, UN, senza_invio=True)
    assert not server.file.exists()                                 # una prova a mano non scrive niente
    server.giro(1)
    prima = server.file.read_text(encoding="utf-8")
    server.giro(2, UN, senza_invio=True)
    server.giro(3, UN, senza_invio=True)
    assert server.file.read_text(encoding="utf-8") == prima         # non copre il buco di un cron fermo
    assert [g["quando"] for g in server.giri()] == [_ora(timedelta(hours=1))]


# ---------------------------------------------------------------- `rotte`: le rotture confermate, anche già avvisate
def test_rotte_comprende_le_rotture_confermate_anche_gia_avvisate(server):
    altro = Rottura("punti_diversi", "utente 4", 11, "formazione 71.0 contro oggi 72.4")   # stessa invariante, altro utente
    server.giro(0, UN)
    server.giro(1, UN)                  # UN confermata e avvisata
    server.giro(2, UN, DUE, altro)      # DUE e altro viste una volta sola
    server.giro(3, UN, DUE, altro)      # confermate tutte: UN già avvisata, DUE nuova
    giri = server.giri()
    assert giri[2]["rotte"] == ["punti_diversi"] and giri[2]["inviato"] is False
    assert giri[3]["rotte"] == ["punti_diversi", "risposta_in_errore"]     # una volta per invariante, in ordine
    assert giri[3]["inviato"] is True


def test_rottura_vista_in_un_giro_solo_non_entra_in_rotte(server):
    server.giro(0, UN)
    server.giro(1)                      # tornata a posto
    server.giro(2, UN)                  # di nuovo una volta sola
    server.giro(3)
    assert [g["rotte"] for g in server.giri()] == [[], [], [], []]
    assert server.mandati == []


# ---------------------------------------------------------------- storia: 60 giorni, letta fra due date con il fuso
def test_giri_oltre_60_giorni_si_tolgono(server):
    assert sentinella.TIENI_GIRI == timedelta(days=60)
    voce = lambda giorni: {"quando": _ora(-timedelta(days=giorni)), "rotte": [], "inviato": False}
    _scrivi_stato(server.file, aperte={}, utenti={}, giri=[voce(61), voce(59), voce(1)])
    server.giro(0)
    assert server.giri() == [voce(59), voce(1), {"quando": _ora(), "rotte": [], "inviato": False}]


def test_giri_fra_due_date_con_fusi_diversi(tmp_path):
    f = tmp_path / "sentinella.json"
    voce = lambda quando, *rotte: {"quando": quando, "rotte": list(rotte), "inviato": False}
    dentro = [voce("2026-11-15T19:00:00+01:00"),                  # = 18:00Z, estremo `dal` compreso
              voce("2026-11-15T20:30:00+01:00", "punti_diversi"),  # = 19:30Z, prima della fine alle 19:45Z
              voce("2026-11-15T19:45:00+00:00")]                  # estremo `al` compreso
    fuori = [voce("2026-11-15T18:59:59+01:00"), voce("2026-11-15T20:45:01+01:00")]
    _scrivi_stato(f, giri=[dentro[2], fuori[1], dentro[0], fuori[0], dentro[1]])      # anche fuori ordine
    dal = datetime.fromisoformat("2026-11-15T20:00:00+02:00")      # = 18:00Z
    al = datetime.fromisoformat("2026-11-15T19:45:00Z")
    assert sentinella.giri_sentinella(dal, al, f) == dentro       # dal più vecchio
    assert sentinella.giri_sentinella(dal, al, tmp_path / "manca.json") == []


def test_date_senza_fuso_rifiutate(tmp_path, monkeypatch):
    con_fuso = datetime(2026, 11, 15, 20, tzinfo=timezone.utc)
    for dal, al in ((ADESSO, con_fuso), (con_fuso, ADESSO)):
        with pytest.raises(ValueError, match="fuso"):
            sentinella.giri_sentinella(dal, al, tmp_path / "sentinella.json")
    monkeypatch.setattr(sentinella, "FILE_STATO", tmp_path / "sentinella.json")
    monkeypatch.setattr(sentinella, "giro", lambda *a, **k: pytest.fail("con --giri il giro non parte"))
    for dal, al in (("2026-11-15T18:00:00", "2026-11-15T19:45:00Z"), ("2026-11-15T18:00:00Z", "2026-11-15T19:45:00")):
        with pytest.raises(SystemExit) as uscita:
            main(["sentinella", "--giri", "--dal", dal, "--al", al])
        assert "fuso" in str(uscita.value.code)


def test_comando_giri_stampa_json_senza_giro(tmp_path, monkeypatch, capsys):
    f = tmp_path / "sentinella.json"
    voci = [{"quando": "2026-11-15T19:00:00+01:00", "rotte": [], "inviato": False},
            {"quando": "2026-11-15T20:30:00+01:00", "rotte": ["punti_diversi"], "inviato": True},
            {"quando": "2026-11-16T09:00:00+01:00", "rotte": [], "inviato": False}]
    _scrivi_stato(f, aperte={}, utenti={}, giri=voci)
    monkeypatch.setattr(sentinella, "FILE_STATO", f)
    monkeypatch.setattr(sentinella, "giro", lambda *a, **k: pytest.fail("con --giri il giro non parte"))
    main(["sentinella", "--giri", "--dal", "2026-11-15T18:00:00Z", "--al", "2026-11-15T21:00:00+01:00"])
    assert json.loads(capsys.readouterr().out) == voci[:2]
    with pytest.raises(SystemExit) as uscita:                      # --giri senza le date: errore, non il giro
        main(["sentinella", "--giri"])
    assert uscita.value.code not in (0, None)


# ---------------------------------------------------------------- «Stato dei dati» e file di oggi
def test_stato_dati_ha_sentinella_giri(tmp_path, monkeypatch):
    f = tmp_path / "sentinella.json"
    voce = lambda ore, *rotte: {"quando": _ora(-timedelta(hours=ore)), "rotte": list(rotte), "inviato": False}
    _scrivi_stato(f, aperte={UN.chiave: {"volte": 2, "avvisata": True, "ultima": "2026-11-15T19:00:00"}},
                  giri=[voce(8 * 24), voce(6 * 24, "punti_diversi"), voce(1) | {"utente": "utente 3"}])
    monkeypatch.setattr(sentinella, "FILE_STATO", f)
    db = archivio.apri(tmp_path / "t.sqlite")
    try:
        r = stato_dati.riepilogo(db, ST, adesso=ADESSO)
    finally:
        db.close()
    assert r["sentinella_giri"] == [voce(6 * 24, "punti_diversi"), voce(1)]   # ultimi 7 giorni: solo ore e invarianti


def test_file_rovinato_non_vale_nessun_giro(tmp_path, monkeypatch, capsys):
    """Un file che non si legge non è «nessun giro» (sarebbe verde per omissione): errore per il comando, null in Stato dei dati.
    Solo il file che manca vale lista vuota."""
    f = tmp_path / "sentinella.json"
    monkeypatch.setattr(sentinella, "FILE_STATO", f)
    monkeypatch.setattr(sentinella, "giro", lambda *a, **k: pytest.fail("con --giri il giro non parte"))
    dal, al = datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 12, 1, tzinfo=timezone.utc)
    cartella = tmp_path / "cartella.json"
    cartella.mkdir()
    with pytest.raises(ValueError):                                 # c'è ma non si legge
        sentinella.giri_sentinella(dal, al, cartella)
    db = archivio.apri(tmp_path / "t.sqlite")
    try:
        for rovinato in ('{"aperte": {}, "giri": [', "[1, 2]", '{"giri": "tanti"}'):
            f.write_text(rovinato, encoding="utf-8")
            with pytest.raises(ValueError):
                sentinella.giri_sentinella(dal, al, f)
            with pytest.raises(SystemExit) as uscita:
                main(["sentinella", "--giri", "--dal", "2026-11-01T00:00:00Z", "--al", "2026-12-01T00:00:00Z"])
            assert uscita.value.code not in (0, None)
            assert stato_dati.riepilogo(db, ST, adesso=ADESSO)["sentinella_giri"] is None
    finally:
        db.close()
    assert capsys.readouterr().out == ""                            # nessuna lista vuota stampata
    f.unlink()
    assert sentinella.giri_sentinella(dal, al, f) == []             # file che manca: ancora nessun giro


def test_file_di_stato_vecchio_senza_giri_si_legge(server):
    prima = "2026-11-15T19:00:00"
    _scrivi_stato(server.file, aperte={UN.chiave: {"volte": 1, "avvisata": False, "ultima": prima}},
                  utenti={"utente 3": prima}, ultimo_giro=prima)
    dal, al = datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert sentinella.giri_sentinella(dal, al, server.file) == []
    server.giro(0, UN)                  # il primo giro dopo l'aggiornamento conferma la rottura vista prima
    assert server.giri() == [{"quando": _ora(), "rotte": ["punti_diversi"], "inviato": True}]
    assert sentinella.giri_sentinella(dal, al, server.file) == server.giri()
