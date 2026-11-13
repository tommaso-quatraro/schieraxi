"""Avvisi per utente (cambi e promemoria: i soli due rimasti, #676) e backup per utente, con gli account accesi.
Tutto su cartelle temporanee: le notifiche vere (web push, ntfy) sono sostituite da registri, e l'archivio è in memoria."""
import contextlib
import json
import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from fanta import __main__ as cli
from fanta import account, avvisi_utenti, backup, consigli, lega, notifiche, percorsi, push
from fanta.contesto import Contesto
from fanta.regole import Regole

from test_notifiche import ST, _db

PASSWORD = "una-password-lunga-9"
ADESSO = datetime(2026, 10, 27, 9, 0)          # il giorno prima della giornata 9 (prima partita il 28 alle 18:30)
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
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    # la consigliata finta: tutta la rosa, tranne chi è fuori nelle probabili (come la consigliata vera, che lo toglie)
    monkeypatch.setattr(consigli, "formazione", lambda db, regole, rose, *a, **k: calcoli.append(rose.mia_squadra) or {
        "modulo": "4-3-3", "punteggio_atteso": 70.0, "titolari": [{"id": g.id, "nome": g.nome, "titolarita": "titolare", "dubbio": False}
                                                                  for g in rose.squadra(rose.mia_squadra).giocatori
                                                                  if prev.at[g.id, "stato"] not in notifiche.MOTIVI_FUORI]})
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
    assert errori == {} and len(esiti["amico1"]) == 1 and esiti["amico2"] == []
    assert [(chi, titolo, testo) for chi, titolo, testo in registro.web] == [
        (a.cartella.name, "SchieraXI · cambia un titolare",
         "Castro parte dalla panchina: con la tua rosa non si forma più una squadra. La formazione si chiude il 28/10 alle 18:30.")]
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
    assert esiti["amico1"] == [] and registro.ntfy == []              # non arrivato a nessuno: si riprova al giro dopo, mai su ntfy


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


def test_la_vecchia_opzione_dei_cambi_spenta_non_li_ferma_piu(mondo, registro):
    """#676: decide l'interruttore unico (un dispositivo iscritto), non la scelta `cambi` di prima."""
    ctx = nuovo("amico1", (1, "Castro"))
    notifiche.salva_impostazioni({"cambi": False}, ctx.impostazioni_avvisi)
    esiti, _ = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert esiti == {"amico1": []} and mondo.calcoli == ["Squadra di amico1"] and ctx.stato_cambi.exists()
    mondo.prev.loc[1, "stato"] = "squalificato"
    esiti, _ = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert len(esiti["amico1"]) == 1 and len(registro.web) == 1


def test_un_utente_con_dati_rovinati_non_ferma_gli_altri(mondo, registro):
    a, _ = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    a.regole.write_text("{non json", encoding="utf-8")
    esiti, errori = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert set(errori) == {"amico1"} and "amico2" in esiti
    assert "Castro" not in json.dumps(errori) and "Squadra" not in json.dumps(errori)       # del problema si dice solo il tipo


def test_avvisi_utenti_attivi_un_utente_con_dati_strani_non_ferma_gli_altri(mondo, registro, monkeypatch):
    """La preparazione di ogni utente (rose, impostazioni, iscrizioni) sta dentro il controllo per utente."""
    a, _ = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    vera = notifiche.impostazioni

    def impostazioni(percorso=None):
        if percorso == a.impostazioni_avvisi:
            raise RuntimeError("dati strani")
        return vera(percorso)
    monkeypatch.setattr(notifiche, "impostazioni", impostazioni)
    assert [x.utente.nome_utente for x in avvisi_utenti.utenti_attivi()] == ["amico2"]


class Lento:
    """Un giro finto in cui ogni utente «costa» `secondi`: segna chi è stato servito, in ordine."""
    def __init__(self, secondi: float):
        self.t, self.secondi, self.serviti = 0.0, secondi, []

    def orologio(self) -> float:
        return self.t

    def lavoro(self, a, db, r, adesso):
        self.serviti.append(a.utente.nome_utente)
        self.t += self.secondi
        return []


def test_avvisi_giro_a_tempo_e_a_rotazione(mondo, registro, monkeypatch):
    """Il giro guarda il tempo fra un utente e l'altro: finito il tempo, chi resta passa per primo al giro dopo, e chi è stato
    servito per ultimo va in fondo."""
    for nome, g in (("amico1", (1, "Castro")), ("amico2", (2, "Bonny")), ("amico3", (1, "Castro"))):
        nuovo(nome, g)
    lento = Lento(100)
    monkeypatch.setitem(avvisi_utenti._LAVORI, "promemoria", lento.lavoro)
    esiti, errori = avvisi_utenti.esegui("promemoria", mondo.db, ADESSO, max_secondi=150, orologio=lento.orologio)
    assert lento.serviti == ["amico1", "amico2"] and set(esiti) == {"amico1", "amico2"} and errori == {}
    lento.serviti.clear()
    avvisi_utenti.esegui("promemoria", mondo.db, ADESSO, max_secondi=150, orologio=lento.orologio)
    assert lento.serviti == ["amico3", "amico1"]
    lento.serviti.clear()
    avvisi_utenti.esegui("promemoria", mondo.db, ADESSO, max_secondi=1000, orologio=lento.orologio)
    assert lento.serviti == ["amico2", "amico3", "amico1"]
    lento.serviti.clear()
    monkeypatch.setitem(avvisi_utenti._LAVORI, "cambi", lento.lavoro)
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO, max_secondi=1000, orologio=lento.orologio)       # ogni giro ha il suo ordine
    assert lento.serviti == ["amico1", "amico2", "amico3"]


class Fermato(BaseException):
    """Come il processo fermato dal tempo massimo dello script del server."""


def test_avvisi_se_il_giro_si_ferma_su_un_utente_lui_passa_in_fondo(mondo, registro, monkeypatch):
    """Un utente si segna come servito prima del suo lavoro: se il giro si ferma mentre lavora per lui, al giro dopo va in fondo
    e non blocca più gli altri. Anche chi va in errore conta come servito."""
    for nome, g in (("amico1", (1, "Castro")), ("amico2", (2, "Bonny")), ("amico3", (1, "Castro"))):
        nuovo(nome, g)
    serviti = []

    def lavoro(a, db, r, adesso):
        serviti.append(a.utente.nome_utente)
        if a.utente.nome_utente == "amico2" and serviti == ["amico1", "amico2"]:
            raise Fermato()
        if a.utente.nome_utente == "amico1":
            raise TimeoutError("lento")
        return []
    monkeypatch.setitem(avvisi_utenti._LAVORI, "cambi", lavoro)
    with pytest.raises(Fermato):
        avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    serviti.clear()
    _, errori = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert serviti == ["amico3", "amico1", "amico2"] and errori == {"amico1": "TimeoutError"}


def test_avvisi_ordine_del_giro_non_salvato_lo_dice_nel_registro_una_volta(mondo, registro, monkeypatch, caplog):
    """Se l'ordine del giro non si riesce a salvare gli avvisi partono lo stesso; nel registro una riga sola, con il solo tipo d'errore."""
    nuovo("amico1", (1, "Castro"))
    nuovo("amico2", (2, "Bonny"))

    def rotto(percorso, testo):
        raise PermissionError("negato: cartella-segreta")
    monkeypatch.setattr(avvisi_utenti, "scrivi_sicuro", rotto)
    with caplog.at_level("WARNING", logger="fanta.avvisi_utenti"):
        esiti, errori = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert set(esiti) == {"amico1", "amico2"} and errori == {}
    righe = [r.getMessage() for r in caplog.records if "ordine" in r.getMessage()]
    assert len(righe) == 1 and "PermissionError" in righe[0] and "segreta" not in caplog.text


def test_avvisi_tempo_del_giro_dalle_variabili_del_server(monkeypatch):
    monkeypatch.delenv("FANTA_MAX_SECONDI_GIRO_PROMEMORIA", raising=False)
    monkeypatch.delenv("FANTA_MAX_SECONDI_GIRO_AVVISI", raising=False)
    assert avvisi_utenti.secondi_del_giro("promemoria") < 480 and avvisi_utenti.secondi_del_giro("cambi") < 600
    assert avvisi_utenti.secondi_del_giro("promemoria") >= 240
    monkeypatch.setenv("FANTA_MAX_SECONDI_GIRO_PROMEMORIA", "300")
    monkeypatch.setenv("FANTA_MAX_SECONDI_GIRO_AVVISI", "10m;x")                         # non valido: vale quello di base
    assert 150 <= avvisi_utenti.secondi_del_giro("promemoria") < 300
    assert avvisi_utenti.secondi_del_giro("riepilogo") == avvisi_utenti.secondi_del_giro("cambi") < 600
    monkeypatch.setenv("FANTA_MAX_SECONDI_GIRO_AVVISI", "60")
    assert 0 < avvisi_utenti.secondi_del_giro("pronta") < 60


def test_avvisi_con_impostazioni_non_finite_di_un_utente_gli_altri_ricevono(mondo, registro):
    a, _ = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    a.impostazioni_avvisi.write_text('{"silenzio_da": 1e999, "avviso_prima": 1e999}', encoding="utf-8")
    esiti, errori = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert errori == {} and set(esiti) == {"amico1", "amico2"}


# ---------------------------------------------------------------- promemoria
UN_ORA_PRIMA = datetime(2026, 10, 28, 17, 35)                    # 55 minuti prima della prima partita


def test_promemoria_per_ogni_utente_anche_con_le_vecchie_scelte_spente(mondo, registro):
    """Le scelte per avviso di prima non contano più (#676): B li aveva spenti e li riceve lo stesso, una volta sola."""
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    notifiche.salva_impostazioni({"promemoria_60": False, "promemoria_15": False}, b.impostazioni_avvisi)
    esiti, errori = avvisi_utenti.esegui("promemoria", mondo.db, UN_ORA_PRIMA)
    assert errori == {} and len(esiti["amico1"]) == 1 and len(esiti["amico2"]) == 1
    assert sorted(chi for chi, _, _ in registro.web) == sorted([a.cartella.name, b.cartella.name])
    avvisi_utenti.esegui("promemoria", mondo.db, UN_ORA_PRIMA)
    assert len(registro.web) == 2                                      # una volta sola


# ---------------------------------------------------------------- comandi
def test_i_comandi_con_gli_account_chiamano_il_giro_sugli_utenti(mondo, registro, monkeypatch, capsys):
    nuovo("amico1", (1, "Castro"))
    monkeypatch.setattr(cli, "_avvisi_per_utente", lambda f: print("chiamato", f))
    cli._avvisi_telefono("cambi")
    assert "chiamato cambi" in capsys.readouterr().out


def test_il_giro_stampa_solo_i_numeri(mondo, registro, monkeypatch, capsys):
    from fanta import archivio

    class UnOraPrima(datetime):
        @classmethod
        def now(cls, tz=None):
            return UN_ORA_PRIMA
    monkeypatch.setattr(avvisi_utenti, "datetime", UnOraPrima)
    nuovo("amico1", (1, "Castro"))
    monkeypatch.setattr(archivio, "apri", lambda *a: mondo.db)
    cli._avvisi_per_utente("promemoria")
    cattura = capsys.readouterr()
    assert "amico1: 1 avvisi (promemoria)" in cattura.out and "Castro" not in cattura.out + cattura.err


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
    assert len(chiamate) == 1 and chiamate[0]["tieni"] == 5 and isinstance(chiamate[0]["adesso"], datetime)


# ---------------------------------------------------------------- backup
def test_backup_per_utente_e_del_database_degli_account(mondo, registro, capsys):
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    cli._backup_per_utente(7, ADESSO)
    copia_a, copia_b = sorted((a.cartella / "backup").glob("schieraxi-backup-*.json")), sorted((b.cartella / "backup").glob("schieraxi-backup-*.json"))
    assert len(copia_a) == len(copia_b) == 1
    assert copia_a[0].name == copia_b[0].name == "schieraxi-backup-2026-10-27.json"      # il giorno di ADESSO, non dell'orologio
    assert "Squadra di amico1" in copia_a[0].read_text(encoding="utf-8") and "amico2" not in copia_a[0].read_text(encoding="utf-8")
    assert "Squadra di amico2" in copia_b[0].read_text(encoding="utf-8") and "amico1" not in copia_b[0].read_text(encoding="utf-8")
    sqlite_copie = sorted((percorsi.cartella_account() / "backup").glob("account-*.sqlite"))
    assert len(sqlite_copie) == 1
    with contextlib.closing(sqlite3.connect(sqlite_copie[0])) as db:
        assert [r[0] for r in db.execute("SELECT nome_utente FROM utenti ORDER BY id")] == ["amico1", "amico2"]
    assert "2 utenti su 2" in capsys.readouterr().out


def test_backup_per_utente_conta_solo_le_copie_che_ci_sono(mondo, registro, monkeypatch, capsys, caplog):
    """#709: una copia che dopo il giro non c'è non si conta fra quelle salvate: il comando esce con errore e il motivo va nel
    registro del servizio. La copia dell'altro utente e quella del database degli account si fanno lo stesso."""
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    vera = backup.salva_copia

    def salva(**k):
        scritta = vera(**k)
        if k["cartella"] == b.cartella / "backup":
            scritta.unlink()                                         # sparita subito dopo averla scritta
        return scritta
    monkeypatch.setattr(backup, "salva_copia", salva)
    with pytest.raises(SystemExit) as uscita:
        cli._backup_per_utente(7, ADESSO)
    assert "copie salvate: 1 utenti su 2; database degli account: copiato" in capsys.readouterr().out
    assert str(uscita.value.code) == ("Errore: copia non salvata per 1 utenti su 2 (il motivo è nel registro del "
                                      "servizio).")
    assert "non trovata dopo averla scritta" in caplog.text
    assert len(list((a.cartella / "backup").glob("schieraxi-backup-*.json"))) == 1


def test_le_copie_vecchie_si_tolgono(mondo, tmp_path):
    cartella = tmp_path / "copie"
    origine = tmp_path / "account.sqlite"
    with contextlib.closing(sqlite3.connect(origine)) as db:
        db.execute("CREATE TABLE x (a)")
    cartella.mkdir()
    for giorno in range(1, 6):
        (cartella / f"account-2026-01-0{giorno}.sqlite").write_bytes(b"vecchia")
    assert backup.copia_account(cartella, origine, tieni=3, adesso=ADESSO).exists()
    assert len(list(cartella.glob("account-*.sqlite"))) == 3
    assert backup.copia_account(cartella, tmp_path / "non-esiste.sqlite", adesso=ADESSO) is None
