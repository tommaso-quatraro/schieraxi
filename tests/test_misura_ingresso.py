"""Minuti di ingresso degli amici (#574, compito A4 del piano 2026-11-11-aperta-agli-amici): `python -m fanta ingresso` dice,
in sola lettura, quanto ci ha messo ogni account nuovo a caricare la sua lega (rose vere e tempi della lega fatti).

Orologio mai vero: tutte le ore stanno nei dati. Account veri (`account.registra`) in una cartella temporanea, rose inventate
(`lega/esempio/`), fuso del server fissato a Europa/Roma (sul PC e in CI il fuso del sistema è diverso)."""
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fanta import account, lega, misura_ingresso, onboarding, percorsi, regole
from fanta.__main__ import main
from fanta.misura_ingresso import minuti_di_ingresso, misura

ROMA = ZoneInfo("Europe/Rome")
ESEMPIO = Path(__file__).resolve().parent.parent / "lega" / "esempio"
PASSWORD = "tre parole a caso 42"
DAL, AL = "2026-12-10T00:00:00+01:00", "2026-12-10T23:59:59+01:00"


def _rose_vere(aggiornato: str) -> lega.Rose:
    """Rose importate: la lega inventata del repository (dieci squadre, non quelle d'esempio del primo avvio)."""
    rose = lega.carica(ESEMPIO / "rose.json")
    rose.aggiornato = aggiornato
    return rose


def _rose_demo(calciatori, aggiornato: str) -> lega.Rose:
    """Le squadre d'esempio del primo avvio («Usa le squadre di esempio»), fatte come le fa il server."""
    rose = onboarding.crea_demo(calciatori, regole.carica(ESEMPIO / "regole.json"))
    rose.aggiornato = aggiornato
    return rose


def _primo(fatti, saltati=(), aggiornato="2026-12-10T10:08:00") -> dict:
    """Il primo avvio come lo legge `stato_utente.leggi_primo_avvio` (ora senza fuso, quella del server)."""
    return {"fatti": list(fatti), "saltati": list(saltati), "chiuso": False, "aggiornato": aggiornato}


TUTTO = ("server", "accesso", "rose", "squadra", "tempi")


# ---------------------------------------------------------------- minuti_di_ingresso
@pytest.mark.parametrize("creato, rose_alle, primo_alle, fuso, minuti", [
    # 09:00 UTC = 10:00 a Roma in inverno: rose alle 10:06 e tempi alle 10:08, ora del server -> 8 minuti
    ("2026-12-10T09:00:00+00:00", "2026-12-10T10:06:00", "2026-12-10T10:08:00", ROMA, 8.0),
    # conta la più tarda fra le due ore: rose reimportate dopo i tempi
    ("2026-12-10T09:00:00+00:00", "2026-12-10T10:20:00", "2026-12-10T10:08:00", ROMA, 20.0),
    # d'estate Roma è avanti di due ore
    ("2026-07-10T09:00:00+00:00", "2026-07-10T11:03:00", "2026-07-10T11:05:00", ROMA, 5.0),
    # le stesse ore lette su un server in UTC: il fuso del server conta davvero
    ("2026-12-10T09:00:00+00:00", "2026-12-10T10:06:00", "2026-12-10T10:08:00", timezone.utc, 68.0),
])
def test_dentro_quando_rose_e_tempi_fatti(creato, rose_alle, primo_alle, fuso, minuti):
    assert minuti_di_ingresso(creato, _rose_vere(rose_alle), _primo(TUTTO, aggiornato=primo_alle), fuso) == ("dentro", minuti)


@pytest.mark.parametrize("rinominate", [{}, {"Atletico Prova": "I Leoni di Quartiere"},
                                         {nome: f"Squadra {i}" for i, nome in enumerate(onboarding.SQUADRE_DEMO)}])
def test_squadre_di_esempio_non_contano(calciatori, rinominate):
    """Il primo avvio segna `rose` fatto anche con «Usa le squadre di esempio»: la lega non è caricata. Nemmeno se l'amico
    rinomina le squadre d'esempio (la rinomina lascia il nome di prima in `nome_importato`, come fa il server)."""
    rose = _rose_demo(calciatori, "2026-12-10T10:02:00")
    assert {s.nome for s in rose.squadre} == set(onboarding.SQUADRE_DEMO)
    for s in rose.squadre:
        if s.nome in rinominate:
            s.nome_importato, s.nome = s.nome, rinominate[s.nome]
    assert minuti_di_ingresso("2026-12-10T09:00:00+00:00", rose, _primo(TUTTO), ROMA) == ("solo_esempio", None)


@pytest.mark.parametrize("rose, primo", [
    (_rose_vere("2026-12-10T10:06:00"), _primo(("server", "accesso", "rose", "squadra"), saltati=("tempi",))),
    (None, _primo(("server", "accesso", "squadra", "tempi"), saltati=("rose",))),
])
def test_saltato_non_conta_come_dentro(rose, primo):
    assert minuti_di_ingresso("2026-12-10T09:00:00+00:00", rose, primo, ROMA) == ("non_finito", None)


@pytest.mark.parametrize("rose, primo", [
    (None, _primo(("server", "accesso"))),                       # ha aperto il primo avvio e basta
    (_rose_vere("2026-12-10T10:06:00"), None),                   # rose senza i tempi della lega
    (lega.Rose(), _primo(TUTTO)),                                # rose senza squadre
])
def test_non_finito(rose, primo):
    assert minuti_di_ingresso("2026-12-10T09:00:00+00:00", rose, primo, ROMA) == ("non_finito", None)


def test_non_iniziato():
    assert minuti_di_ingresso("2026-12-10T09:00:00+00:00", None, None, ROMA) == ("non_iniziato", None)


@pytest.mark.parametrize("rose_alle, primo_alle", [
    ("", None),                                                  # nessuna ora salvata
    ("2026-12-10T09:30:00", "2026-12-10T09:40:00"),              # ore prima della creazione (10:00 a Roma): orologio sbagliato
])
def test_dentro_senza_ore_utili_non_ha_minuti(rose_alle, primo_alle):
    """Mai «entro 10 minuti» per omissione: senza un'ora buona i minuti restano non misurabili."""
    esito = minuti_di_ingresso("2026-12-10T09:00:00+00:00", _rose_vere(rose_alle), _primo(TUTTO, aggiornato=primo_alle), ROMA)
    assert esito == ("dentro", None)


@pytest.fixture
def sistema_a_roma():
    """Il fuso del sistema messo a Europa/Roma per il solo test (variabile TZ e time.tzset), poi rimesso com'era."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TZ", "Europe/Rome")
        time.tzset()
        yield
    time.tzset()


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset c'è solo su Linux e macOS (in CI gira)")
def test_fuso_del_server_segue_l_ora_legale(sistema_a_roma):
    """Il fuso del server vale per la data dell'ora letta, non solo per adesso: a Roma +1 ora a gennaio e +2 a luglio
    (uno scarto fisso, come quello di `datetime.now().astimezone()`, sbaglierebbe una delle due stagioni)."""
    fuso = misura_ingresso.fuso_del_server()
    assert datetime(2026, 1, 15, 12).replace(tzinfo=fuso).utcoffset() == timedelta(hours=1)
    assert datetime(2026, 7, 15, 12).replace(tzinfo=fuso).utcoffset() == timedelta(hours=2)


# ---------------------------------------------------------------- riassunto (righe e codice di uscita)
@pytest.mark.parametrize("righe, testo, codice", [
    ([{"utente": 1, "esito": "dentro", "minuti": 8.0}, {"utente": 2, "esito": "dentro", "minuti": 9.5}],
     ["utente 1: dentro in 8 minuti", "utente 2: dentro in 9,5 minuti", "dentro in meno di 10 minuti: 2 su 2"], 0),
    ([{"utente": 3, "esito": "dentro", "minuti": 1.0}, {"utente": 4, "esito": "dentro", "minuti": 10.0}],
     ["utente 3: dentro in 1 minuto", "utente 4: dentro in 10 minuti", "dentro in meno di 10 minuti: 1 su 2"], 1),
    # 9 minuti e 58 secondi: in tempo, quindi mai scritto «10 minuti» (si tronca, non si arrotonda)
    ([{"utente": 9, "esito": "dentro", "minuti": 598 / 60}, {"utente": 10, "esito": "dentro", "minuti": 7 + 59 / 60}],
     ["utente 9: dentro in 9,9 minuti", "utente 10: dentro in 7,9 minuti", "dentro in meno di 10 minuti: 2 su 2"], 0),
    ([{"utente": 5, "esito": "dentro", "minuti": None}],
     ["utente 5: dentro, minuti non misurabili", "dentro in meno di 10 minuti: 0 su 1"], 1),
    ([{"utente": 6, "esito": "solo_esempio", "minuti": None}, {"utente": 7, "esito": "non_finito", "minuti": None},
      {"utente": 8, "esito": "non_iniziato", "minuti": None}],
     ["utente 6: solo squadre di esempio", "utente 7: non finito", "utente 8: non iniziato",
      "dentro in meno di 10 minuti: 0 su 3"], 1),
    ([], ["dentro in meno di 10 minuti: 0 su 0"], 2),
])
def test_riassunto(righe, testo, codice):
    assert misura_ingresso.riassunto(righe) == (testo, codice)


# ---------------------------------------------------------------- archivio degli account e comando
@pytest.fixture
def archivio(multiutente, monkeypatch):
    """Il database degli account con la sua struttura vera, nella cartella temporanea della fixture `multiutente`."""
    monkeypatch.setattr(misura_ingresso, "fuso_del_server", lambda: ROMA)
    percorso = percorsi.cartella_account() / "account.sqlite"
    db = account.apri(percorso)
    yield db
    db.close()


def _iscrivi(db, nome: str, creato: str) -> int:
    quando = datetime.fromisoformat(creato)
    invito = account.crea_invito(db, "prova", adesso=quando)
    return account.registra(db, nome, PASSWORD, invito, adesso=quando, accetto_termini=True)[0].id


def _lega_di(utente: int, rose: lega.Rose | None = None, primo: dict | None = None) -> None:
    """I file che il server scrive nella cartella dell'utente: rose.json e avvisi-impostazioni.json (con `primo_avvio`)."""
    cartella = percorsi.cartella_utenti() / str(utente)
    cartella.mkdir(parents=True, exist_ok=True)
    if rose is not None:
        lega.salva(rose, cartella / "rose.json")
    if primo is not None:
        (cartella / "avvisi-impostazioni.json").write_text(json.dumps({"cambi": True, "primo_avvio": primo}), encoding="utf-8")


def _lancia(capsys, *argomenti) -> tuple:
    with pytest.raises(SystemExit) as uscita:
        main(["ingresso", *argomenti])
    return uscita.value.code, capsys.readouterr().out.splitlines()


def _errore(capsys, *argomenti) -> str:
    """Un errore del comando: codice 3 (né «non tutti in tempo», 1, né «nessun account», 2), niente righe di misura, il motivo."""
    with pytest.raises(SystemExit) as uscita:
        main(["ingresso", *argomenti])
    uscite = capsys.readouterr()
    assert (uscita.value.code, uscite.out) == (3, "")
    return uscite.err


def test_solo_account_del_periodo(archivio):
    prima = _iscrivi(archivio, "prima", "2026-12-09T22:59:59+00:00")
    inizio = _iscrivi(archivio, "inizio", "2026-12-09T23:00:00+00:00")       # mezzanotte a Roma: dentro il periodo
    meta = _iscrivi(archivio, "meta", "2026-12-10T12:00:00+00:00")
    dopo = _iscrivi(archivio, "dopo", "2026-12-11T09:00:00+00:00")
    _lega_di(meta, _rose_vere("2026-12-10T13:04:00"), _primo(TUTTO, aggiornato="2026-12-10T13:07:00"))
    _lega_di(dopo, _rose_vere("2026-12-11T10:04:00"), _primo(TUTTO, aggiornato="2026-12-11T10:05:00"))
    assert (prima, inizio, meta, dopo) == (1, 2, 3, 4)
    righe = misura(archivio, percorsi.cartella_utenti(), datetime.fromisoformat(DAL), datetime.fromisoformat(AL), ROMA)
    assert righe == [{"utente": 2, "esito": "non_iniziato", "minuti": None}, {"utente": 3, "esito": "dentro", "minuti": 7.0}]


def test_prima_gli_esempi_poi_le_rose_vere(archivio, calciatori):
    """Squadre di esempio e tempi fatti alle 10:05, rose vere importate alle 10:09 (account delle 10:00 a Roma): conta l'ora
    delle rose vere, anche se le squadre d'esempio restano accanto a quelle importate."""
    utente = _iscrivi(archivio, "luca", "2026-12-10T09:00:00+00:00")
    esempi = _rose_demo(calciatori, "2026-12-10T10:02:00")
    _lega_di(utente, esempi, _primo(TUTTO, aggiornato="2026-12-10T10:05:00"))
    periodo = (percorsi.cartella_utenti(), datetime.fromisoformat(DAL), datetime.fromisoformat(AL), ROMA)
    assert misura(archivio, *periodo) == [{"utente": utente, "esito": "solo_esempio", "minuti": None}]
    vere = _rose_vere("2026-12-10T10:09:00")
    vere.squadre = esempi.squadre + vere.squadre
    _lega_di(utente, vere)
    assert misura(archivio, *periodo) == [{"utente": utente, "esito": "dentro", "minuti": 9.0}]


def test_archivio_in_sola_lettura(archivio):
    utente = _iscrivi(archivio, "luca", "2026-12-10T09:00:00+00:00")
    _lega_di(utente, _rose_vere("2026-12-10T10:06:00"), _primo(TUTTO))
    archivio.close()
    percorso = percorsi.cartella_account() / "account.sqlite"
    prima = percorso.read_bytes()
    db = misura_ingresso.apri_in_sola_lettura(percorso)
    try:
        assert misura(db, percorsi.cartella_utenti(), datetime.fromisoformat(DAL), datetime.fromisoformat(AL), ROMA) == [
            {"utente": utente, "esito": "dentro", "minuti": 8.0}]
        with pytest.raises(sqlite3.OperationalError):
            db.execute("UPDATE utenti SET ruolo = 'amministratore'")
    finally:
        db.close()
    assert percorso.read_bytes() == prima


def test_archivio_che_manca_non_si_crea(multiutente, capsys):
    """Un errore (non «nessun account», che è il codice 2): sul server sbagliato la misura non deve sembrare vuota."""
    assert "database degli account" in _errore(capsys, "--dal", DAL, "--al", AL)
    assert not (percorsi.cartella_account() / "account.sqlite").exists()


def test_file_che_non_si_leggono_danno_un_errore_chiaro(archivio, capsys):
    """Database rovinato o file di un utente che non si apre (permessi): errore con il motivo, mai una misura a metà."""
    utente = _iscrivi(archivio, "luca", "2026-12-10T09:00:00+00:00")
    rose = percorsi.cartella_utenti() / str(utente) / "rose.json"
    rose.parent.mkdir(parents=True)
    rose.write_text('{"squadre": [', encoding="utf-8")                              # rose rovinate: si dice di chi
    assert f"utente {utente}:" in _errore(capsys, "--dal", DAL, "--al", AL)
    rose.unlink()
    rose.mkdir()                                                                   # c'è, ma non si legge come file
    _errore(capsys, "--dal", DAL, "--al", AL)
    archivio.close()
    (percorsi.cartella_account() / "account.sqlite").write_bytes(b"non sono un database" * 100)
    _errore(capsys, "--dal", DAL, "--al", AL)


def test_niente_nomi_utente_nell_uscita(archivio, capsys, calciatori):
    mario = _iscrivi(archivio, "mario.rossi", "2026-12-10T09:00:00+00:00")
    lucia = _iscrivi(archivio, "lucia.bianchi", "2026-12-10T09:10:00+00:00")
    anna = _iscrivi(archivio, "anna.verdi", "2026-12-10T09:20:00+00:00")
    _iscrivi(archivio, "paolo.neri", "2026-12-10T09:30:00+00:00")
    _lega_di(mario, _rose_vere("2026-12-10T10:06:00"), _primo(TUTTO))
    _lega_di(lucia, _rose_demo(calciatori, "2026-12-10T10:12:00"), _primo(TUTTO, aggiornato="2026-12-10T10:15:00"))
    _lega_di(anna, primo=_primo(("server", "accesso")))
    codice, righe = _lancia(capsys, "--dal", DAL, "--al", AL)
    assert righe == ["utente 1: dentro in 8 minuti", "utente 2: solo squadre di esempio", "utente 3: non finito",
                     "utente 4: non iniziato", "dentro in meno di 10 minuti: 1 su 4"]
    assert codice == 1
    testo = "\n".join(righe).lower()
    assert not any(n in testo for n in ("mario", "rossi", "lucia", "bianchi", "anna", "verdi", "paolo", "neri"))


def test_codici_di_uscita(archivio, capsys):
    uno = _iscrivi(archivio, "primo", "2026-12-10T09:00:00+00:00")
    due = _iscrivi(archivio, "secondo", "2026-12-10T09:30:00+00:00")
    _lega_di(uno, _rose_vere("2026-12-10T10:06:00"), _primo(TUTTO))
    _lega_di(due, _rose_vere("2026-12-10T10:35:00"), _primo(TUTTO, aggiornato="2026-12-10T10:39:30"))
    assert _lancia(capsys, "--dal", DAL, "--al", AL) == (0, ["utente 1: dentro in 8 minuti", "utente 2: dentro in 9,5 minuti",
                                                              "dentro in meno di 10 minuti: 2 su 2"])
    tre = _iscrivi(archivio, "terzo", "2026-12-10T10:00:00+00:00")
    _lega_di(tre, _rose_vere("2026-12-10T11:03:00"), _primo(TUTTO, aggiornato="2026-12-10T11:12:00"))
    codice, righe = _lancia(capsys, "--dal", DAL, "--al", AL)
    assert (codice, righe[-2:]) == (1, ["utente 3: dentro in 12 minuti", "dentro in meno di 10 minuti: 2 su 3"])
    assert _lancia(capsys, "--dal", "2026-12-11T00:00:00+01:00", "--al", "2026-12-11T23:59:59+01:00") == (
        2, ["dentro in meno di 10 minuti: 0 su 0"])


def test_date_senza_fuso_rifiutate(archivio, capsys):
    con_fuso, senza = datetime.fromisoformat(DAL), datetime(2026, 12, 10)
    for dal, al in ((senza, con_fuso), (con_fuso, senza)):
        with pytest.raises(ValueError, match="fuso"):
            misura(archivio, percorsi.cartella_utenti(), dal, al, ROMA)
    for argomenti in (("--dal", "2026-12-10T00:00:00", "--al", AL), ("--dal", DAL, "--al", "2026-12-10T23:00:00")):
        assert "fuso" in _errore(capsys, *argomenti)
    _errore(capsys, "--dal", AL, "--al", DAL)                              # al prima di dal: errore, non «nessun account»
    _errore(capsys, "--dal", "domani", "--al", AL)                         # data che non si legge
    assert "--dal" in _errore(capsys, "--al", AL)                          # --dal manca: 3, non il 2 di argparse
