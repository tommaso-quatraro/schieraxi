"""Avvisi per utente (cambi, promemoria, riepilogo, «formazione pronta») e backup per utente, con gli account accesi.
Tutto su cartelle temporanee: le notifiche vere (web push, ntfy) sono sostituite da registri, e l'archivio è in memoria."""
import contextlib
import json
import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from fanta import __main__ as cli
from fanta import account, avvisi, avvisi_utenti, backup, consigli, lega, notifiche, percorsi, push
from fanta.contesto import Contesto
from fanta.regole import Regole

from test_notifiche import ST, _db

PASSWORD = "una-password-lunga-9"
ADESSO = datetime(2026, 10, 27, 9, 0)          # il giorno prima della giornata 9 (prima partita il 28 alle 18:30)
PRONTA = datetime(2026, 10, 28, 8, 0)            # meno di 30 ore alla prima partita (28 alle 18:30): è il momento di «formazione pronta»
SUB = {"keys": {"p256dh": "P" * 40, "auth": "A" * 20}}


class Registro:
    """Cosa è partito, per chi: web push (con il file delle iscrizioni, che dice di quale utente) e ntfy."""
    def __init__(self):
        self.web, self.ntfy = [], []


@pytest.fixture
def registro(monkeypatch):
    r = Registro()
    monkeypatch.setattr(push, "invia", lambda titolo, testo, priorita, tag, percorso=None, **k: r.web.append((percorso.parent.name, titolo, testo)) or 1)
    monkeypatch.setattr(notifiche, "_invia_ntfy", lambda titolo, testo, *a, **k: r.ntfy.append((titolo, testo)) or True)
    monkeypatch.setattr(notifiche, "canale", lambda: "canale-del-proprietario")
    return r


def nuovo(nome: str, giocatore: tuple[int, str], amministratore=False, iscritto=True, squadra=True) -> Contesto:
    """Un utente registrato con una rosa di un giocatore e (se iscritto) un dispositivo per le notifiche."""
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, nome, amministratore)
        utente, _, _ = account.registra(db, nome, PASSWORD, inv)
    ctx = Contesto.per_utente(utente.id)
    i, cognome = giocatore
    lega.salva(lega.Rose([lega.Squadra(f"Squadra di {nome}", [lega.GiocatoreRosa(i, cognome, "A", "ROM", 10)])],
                         f"Squadra di {nome}" if squadra else None), ctx.rose)
    if iscritto:
        push.iscrivi({"endpoint": f"https://web.push.example/{nome}"} | SUB, ctx.iscrizioni_push)
    return ctx


@pytest.fixture
def mondo(multiutente, dati_isolati, monkeypatch):
    """Due giocatori nelle probabili (1 = Castro di A, 2 = Bonny di B) e il conteggio dei calcoli di formazione."""
    prev = pd.DataFrame([{"nome": "Castro", "stato": "titolare", "percentuale": 80.0, "dubbio": False},
                         {"nome": "Bonny", "stato": "titolare", "percentuale": 80.0, "dubbio": False}], index=[1, 2])
    calcoli = []
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st: 9)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    monkeypatch.setattr(consigli, "formazione", lambda db, regole, rose, *a, **k: calcoli.append(rose.mia_squadra) or {
        "modulo": "4-3-3", "punteggio_atteso": 70.0, "titolari": [{"id": g.id, "nome": g.nome, "titolarita": "titolare", "dubbio": False}
                                                                  for g in rose.squadra(rose.mia_squadra).giocatori]})
    return type("M", (), {"prev": prev, "calcoli": calcoli, "db": _db("2026-10-28 18:30")})


# ---------------------------------------------------------------- chi è attivo
def test_sono_attivi_solo_gli_utenti_con_squadra_e_dispositivo(mondo, registro):
    nuovo("amico1", (1, "Castro"))
    nuovo("senzasq", (2, "Bonny"), squadra=False)
    nuovo("senzadisp", (2, "Bonny"), iscritto=False)
    assert [a.utente.nome_utente for a in avvisi_utenti.utenti_attivi()] == ["amico1"]


def test_un_amministratore_con_ntfy_e_senza_dispositivi_e_attivo(mondo, registro):
    ctx = nuovo("capo", (1, "Castro"), amministratore=True, iscritto=False)
    assert avvisi_utenti.utenti_attivi() == []
    notifiche.salva_impostazioni({"app_nativa": True}, ctx.impostazioni_avvisi)
    assert [a.utente.nome_utente for a in avvisi_utenti.utenti_attivi()] == ["capo"]
    nuovo("amico", (2, "Bonny"), iscritto=False)                       # un utente comune non conta mai sul canale del proprietario
    notifiche.salva_impostazioni({"app_nativa": True}, Contesto.per_utente(2).impostazioni_avvisi)
    assert [a.utente.nome_utente for a in avvisi_utenti.utenti_attivi()] == ["capo"]


# ---------------------------------------------------------------- cambi
def test_i_cambi_arrivano_a_ciascuno_con_il_suo_stato(mondo, registro):
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)                    # primo controllo: solo memorizza
    assert registro.web == []
    mondo.prev.loc[1, ["stato", "percentuale"]] = ["panchina", 30.0]  # cambia solo Castro, che è di amico1
    esiti, errori = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert errori == {} and len(esiti["amico1"]) >= 1 and esiti["amico2"] == []
    assert [(chi, testo) for chi, _, testo in registro.web] == [(a.cartella.name, "Castro: dalla formazione titolare alla panchina")]
    assert registro.ntfy == []
    assert json.loads(a.stato_cambi.read_text())["cambi"] and json.loads(b.stato_cambi.read_text())["cambi"]    # ognuno ha il suo stato
    assert a.stato_cambi.parent != b.stato_cambi.parent
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)                    # già comunicato
    assert len(registro.web) == 1


def test_gli_utenti_comuni_non_passano_mai_da_ntfy(mondo, registro, monkeypatch):
    nuovo("amico1", (1, "Castro"))
    monkeypatch.setattr(push, "invia", lambda *a, **k: 0)             # il dispositivo non risponde: per un utente comune non c'è il ripiego su ntfy
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    mondo.prev.loc[1, "stato"] = "infortunato"
    esiti, _ = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert esiti["amico1"] and registro.ntfy == []


def test_l_amministratore_usa_ntfy_solo_con_l_opzione(mondo, registro, monkeypatch):
    capo = nuovo("capo", (1, "Castro"), amministratore=True)
    amico = nuovo("amico", (2, "Bonny"))
    for ctx in (capo, amico):
        notifiche.salva_impostazioni({"app_nativa": True}, ctx.impostazioni_avvisi)      # lo vogliono entrambi: solo il capo può
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    mondo.prev.loc[[1, 2], "stato"] = "infortunato"
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert len(registro.ntfy) == 1 and "Castro" in registro.ntfy[0][1]
    # senza l'opzione, anche l'amministratore resta fuori da ntfy
    notifiche.salva_impostazioni({"app_nativa": False}, capo.impostazioni_avvisi)
    registro.ntfy.clear()
    mondo.prev.loc[[1, 2], "stato"] = "titolare"
    monkeypatch.setattr(push, "invia", lambda *a, **k: 0)
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert registro.ntfy == [] or all("Bonny" not in t for _, t in registro.ntfy)


def test_prima_si_confrontano_gli_stati_la_formazione_solo_se_cambia_qualcosa(mondo, registro):
    nuovo("amico1", (1, "Castro"))
    nuovo("amico2", (2, "Bonny"))
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert len(mondo.calcoli) == 2                                     # il primo giro: una formazione a testa
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert len(mondo.calcoli) == 2                                     # niente di nuovo: nessun ricalcolo
    mondo.prev.loc[1, "stato"] = "infortunato"
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert len(mondo.calcoli) == 3                                     # è cambiato Castro: solo la formazione di chi lo ha
    assert mondo.calcoli[-1] == "Squadra di amico1"


def test_come_prima_senza_risparmio(mondo, registro, tmp_path):
    """Chiamata diretta (l'app di sempre): la formazione si ricalcola a ogni controllo, come prima."""
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10)])], "Mia")
    manda = lambda *a, **k: True  # noqa: E731
    stato = tmp_path / "stato.json"
    for _ in range(3):
        notifiche.cambi(mondo.db, Regole(), rose, ADESSO, stato, manda, {"cambi": True})
    assert len(mondo.calcoli) == 3


def test_con_le_rose_cambiate_la_formazione_si_ricalcola(mondo, registro):
    ctx = nuovo("amico1", (1, "Castro"))
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    lega.salva(lega.Rose([lega.Squadra("Squadra di amico1", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10),
                                                              lega.GiocatoreRosa(2, "Bonny", "A", "ROM", 10)])], "Squadra di amico1"), ctx.rose)
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert len(mondo.calcoli) == 2


def test_se_l_opzione_e_spenta_non_si_fa_nemmeno_il_confronto(mondo, registro):
    ctx = nuovo("amico1", (1, "Castro"))
    notifiche.salva_impostazioni({"cambi": False}, ctx.impostazioni_avvisi)
    esiti, _ = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert esiti == {"amico1": []} and mondo.calcoli == [] and not ctx.stato_cambi.exists()


def test_un_utente_con_dati_rovinati_non_ferma_gli_altri(mondo, registro):
    a, _ = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    a.regole.write_text("{non json", encoding="utf-8")
    esiti, errori = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert set(errori) == {"amico1"} and "amico2" in esiti
    assert "Castro" not in json.dumps(errori) and "Squadra" not in json.dumps(errori)       # del problema si dice solo il tipo


# ---------------------------------------------------------------- promemoria, riepilogo, formazione pronta
def test_promemoria_per_utente_con_le_sue_impostazioni(mondo, registro):
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    notifiche.salva_impostazioni({"promemoria_60": False, "promemoria_15": False}, b.impostazioni_avvisi)
    alle = datetime(2026, 10, 28, 17, 35)                              # 55 minuti prima della prima partita
    esiti, errori = avvisi_utenti.esegui("promemoria", mondo.db, alle)
    assert errori == {} and len(esiti["amico1"]) == 1 and esiti["amico2"] == []
    assert [chi for chi, _, _ in registro.web] == [a.cartella.name]
    # B ha i promemoria spenti: nessuno segnato come mandato (nel file può esserci solo il riferimento dell'avviso «cambia la formazione»)
    assert a.stato_promemoria.exists() and not notifiche._json(b.stato_promemoria).get("promemoria")
    avvisi_utenti.esegui("promemoria", mondo.db, alle)
    assert len(registro.web) == 1                                      # una volta sola


def test_formazione_pronta_una_volta_per_giornata_e_per_utente(mondo, registro):
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    esiti, _ = avvisi_utenti.esegui("pronta", mondo.db, PRONTA)
    assert [chi for chi, _, _ in registro.web] == [a.cartella.name, b.cartella.name]
    assert all("Giornata 9: la formazione è pronta" in testo for _, _, testo in registro.web)
    assert json.loads(a.stato_avvisi.read_text()) == {"ultimo": f"{ST}/9"}
    avvisi_utenti.esegui("pronta", mondo.db, PRONTA)
    assert len(registro.web) == 2
    assert registro.ntfy == []


def test_formazione_pronta_nelle_ore_tranquille_e_se_l_invio_fallisce_si_riprova(mondo, registro, monkeypatch):
    a = nuovo("amico1", (1, "Castro"))
    notifiche.salva_impostazioni({"silenzio": True, "silenzio_da": 0, "silenzio_a": 23}, a.impostazioni_avvisi)
    avvisi_utenti.esegui("pronta", mondo.db, PRONTA)
    assert registro.web == [] and not a.stato_avvisi.exists()          # non partito e non segnato: riprova dopo le ore tranquille
    notifiche.salva_impostazioni({"silenzio": False}, a.impostazioni_avvisi)
    monkeypatch.setattr(push, "invia", lambda *x, **k: 0)
    avvisi_utenti.esegui("pronta", mondo.db, PRONTA)
    assert not a.stato_avvisi.exists()                                 # l'invio non è andato a buon fine: non si segna
    monkeypatch.setattr(push, "invia", lambda titolo, testo, p, t, percorso=None, **k: registro.web.append(1) or 1)
    avvisi_utenti.esegui("pronta", mondo.db, PRONTA)
    assert registro.web == [1] and a.stato_avvisi.exists()


def test_riepilogo_usa_le_opzioni_di_ciascuno(mondo, registro):
    a = nuovo("amico1", (1, "Castro"))
    notifiche.salva_impostazioni({"riepilogo": False}, a.impostazioni_avvisi)
    assert avvisi_utenti.esegui("riepilogo", mondo.db, ADESSO)[0] == {"amico1": []}


# ---------------------------------------------------------------- comandi
def test_i_comandi_con_gli_account_chiamano_il_giro_sugli_utenti(mondo, registro, monkeypatch, capsys):
    nuovo("amico1", (1, "Castro"))
    monkeypatch.setattr(cli, "_avvisi_per_utente", lambda f: print("chiamato", f))
    cli._avvisi_telefono("cambi")
    assert "chiamato cambi" in capsys.readouterr().out


class Finto(datetime):
    @classmethod
    def now(cls, tz=None):
        return PRONTA


def test_il_giro_stampa_solo_i_numeri(mondo, registro, monkeypatch, capsys):
    from fanta import archivio
    monkeypatch.setattr(avvisi_utenti, "datetime", Finto)
    nuovo("amico1", (1, "Castro"))
    monkeypatch.setattr(archivio, "apri", lambda *a: mondo.db)
    cli._avvisi_per_utente("pronta")
    cattura = capsys.readouterr()
    fuori = cattura.out
    assert fuori == ""                                                  # «pronta» non scrive su stdout: lo script ne farebbe un avviso ntfy
    assert "amico1: 1 avvisi (pronta)" in cattura.err and "Castro" not in cattura.err


def test_il_comando_avviso_con_gli_account_non_stampa_niente(mondo, registro, monkeypatch, capsys):
    """Lo script del server manderebbe quel testo sul canale ntfy del proprietario: con gli account gli avvisi partono da soli, per utente."""
    from fanta import archivio
    monkeypatch.setattr(avvisi_utenti, "datetime", Finto)
    nuovo("amico1", (1, "Castro"))
    monkeypatch.setattr(archivio, "apri", lambda *a: mondo.db)
    cli.cmd_avviso(type("A", (), {"prova": False})())
    assert capsys.readouterr().out.strip() == "" and len(registro.web) == 1


def test_spento_i_comandi_restano_quelli_di_sempre(monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    def non_deve_succedere(*a, **k):
        raise AssertionError("a interruttore spento gli avvisi non passano dagli utenti")
    monkeypatch.setattr(cli, "_avvisi_per_utente", non_deve_succedere)
    monkeypatch.setattr(cli, "_backup_per_utente", non_deve_succedere)
    monkeypatch.setattr(cli.lega, "carica", lambda *a, **k: None)         # il percorso di sempre si ferma subito: non tocca né lega/ né notifiche vere
    with pytest.raises(SystemExit):
        cli._avvisi_telefono("cambi")
    chiamate = []
    monkeypatch.setattr(backup, "salva_copia", lambda **k: chiamate.append(k) or None)
    cli.cmd_backup(type("A", (), {"tieni": 5})())
    assert chiamate == [{"tieni": 5}]


# ---------------------------------------------------------------- backup
def test_backup_per_utente_e_del_database_degli_account(mondo, registro, capsys):
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    cli._backup_per_utente(7)
    copia_a, copia_b = sorted((a.cartella / "backup").glob("schieraxi-backup-*.json")), sorted((b.cartella / "backup").glob("schieraxi-backup-*.json"))
    assert len(copia_a) == len(copia_b) == 1
    assert "Squadra di amico1" in copia_a[0].read_text(encoding="utf-8") and "amico2" not in copia_a[0].read_text(encoding="utf-8")
    assert "Squadra di amico2" in copia_b[0].read_text(encoding="utf-8") and "amico1" not in copia_b[0].read_text(encoding="utf-8")
    sqlite_copie = sorted((percorsi.cartella_account() / "backup").glob("account-*.sqlite"))
    assert len(sqlite_copie) == 1
    with contextlib.closing(sqlite3.connect(sqlite_copie[0])) as db:
        assert [r[0] for r in db.execute("SELECT nome_utente FROM utenti ORDER BY id")] == ["amico1", "amico2"]
    assert "2 utenti su 2" in capsys.readouterr().out


def test_le_copie_vecchie_si_tolgono(mondo, tmp_path):
    cartella = tmp_path / "copie"
    origine = tmp_path / "account.sqlite"
    with contextlib.closing(sqlite3.connect(origine)) as db:
        db.execute("CREATE TABLE x (a)")
    cartella.mkdir()
    for giorno in range(1, 6):
        (cartella / f"account-2026-01-0{giorno}.sqlite").write_bytes(b"vecchia")
    assert backup.copia_account(cartella, origine, tieni=3).exists()
    assert len(list(cartella.glob("account-*.sqlite"))) == 3
    assert backup.copia_account(cartella, tmp_path / "non-esiste.sqlite") is None
