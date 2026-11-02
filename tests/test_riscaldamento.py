"""Riscaldamento della cache nel servizio: chi si scalda, quando, e che un errore non fermi il controllo."""
import contextlib
import threading
import time
from datetime import datetime, timedelta, timezone

from fanta import account, calcolo, riscaldamento
from fanta.contesto import Contesto

PASSWORD = "una-password-lunga-9"


def _utente(nome: str, adesso: datetime | None = None) -> int:
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, nome)
        utente, _, _ = account.registra(db, nome, PASSWORD, inv, adesso=adesso)
    return utente.id


def test_senza_account_si_scalda_l_utente_unico():
    locale = object()
    assert riscaldamento.contesti_da_scaldare(lambda: locale) == [locale]


def test_con_gli_account_solo_chi_ha_usato_l_app_da_poco(multiutente):
    adesso = datetime.now(timezone.utc)
    vecchio = _utente("vecchio", adesso - timedelta(days=20))
    recente = _utente("recente", adesso - timedelta(days=1))
    contesti = riscaldamento.contesti_da_scaldare(lambda: None, adesso)
    assert [c.utente_id for c in contesti] == [recente]
    assert vecchio not in [c.utente_id for c in contesti]


def test_non_piu_di_max_utenti(multiutente, monkeypatch):
    monkeypatch.setattr(riscaldamento, "MAX_UTENTI", 4)       # il tetto vero è più alto: qui basta vedere che si rispetta
    adesso = datetime.now(timezone.utc)
    for i in range(riscaldamento.MAX_UTENTI + 3):
        _utente(f"utente{i}", adesso - timedelta(minutes=i))
    assert len(riscaldamento.contesti_da_scaldare(lambda: None, adesso)) == riscaldamento.MAX_UTENTI


def test_scalda_tutti_continua_dopo_un_errore(monkeypatch):
    visti = []
    ctx = [Contesto.per_utente(1), Contesto.per_utente(2), Contesto.per_utente(3)]
    monkeypatch.setattr(riscaldamento, "contesti_da_scaldare", lambda locale: ctx)
    monkeypatch.setattr(riscaldamento, "PAUSA", 0)

    class Db:
        def close(self):
            pass

    def scalda(c, db):
        visti.append(c.utente_id)
        if c.utente_id == 1:
            raise ValueError("nessun calendario")
        return True

    monkeypatch.setattr(riscaldamento, "scalda_contesto", scalda)
    assert riscaldamento.scalda_tutti(lambda: None, Db) == 2
    assert visti == [1, 2, 3]


def test_scalda_contesto_senza_rose_non_fa_niente(tmp_path, monkeypatch):
    ctx = Contesto.per_utente(5)       # cartella che non esiste: nessuna rosa
    chiamate = []
    monkeypatch.setattr(riscaldamento.consigli, "formazione", lambda *a, **k: chiamate.append("f"))
    assert riscaldamento.scalda_contesto(ctx, None) is False
    assert chiamate == []


def test_sorveglia_scalda_all_avvio_e_quando_cambia_la_versione():
    versione = ["v1"]
    scaldati = []
    fermo = threading.Event()
    t = threading.Thread(target=riscaldamento.sorveglia, args=(lambda: versione[0], lambda: scaldati.append(versione[0]), fermo, 0.02))
    t.start()
    try:
        _aspetta(lambda: scaldati == ["v1"])
        time.sleep(0.15)
        assert scaldati == ["v1"]            # stessa versione: niente di nuovo
        versione[0] = "v2"
        _aspetta(lambda: scaldati == ["v1", "v2"])
    finally:
        fermo.set()
        t.join(2)
    assert not t.is_alive()


def test_interruttore_e_ritardo_dall_ambiente(monkeypatch):
    monkeypatch.delenv("FANTA_RISCALDA", raising=False)
    assert riscaldamento.attivo()
    monkeypatch.setenv("FANTA_RISCALDA", "0")
    assert not riscaldamento.attivo()
    monkeypatch.setenv("FANTA_RISCALDA_RITARDO", "abc")
    assert riscaldamento.ritardo_avvio() == riscaldamento.RITARDO_AVVIO
    monkeypatch.setenv("FANTA_RISCALDA_RITARDO", "1000")
    assert riscaldamento.ritardo_avvio() == 300


def test_sorveglia_aspetta_il_ritardo_prima_di_scaldare_e_si_ferma_senza_calcolare():
    scaldati = []
    fermo = threading.Event()
    t = threading.Thread(target=riscaldamento.sorveglia, args=(lambda: "v", lambda: scaldati.append(1), fermo, 0.02, 0.3))
    t.start()
    time.sleep(0.1)
    assert scaldati == []                    # ancora in attesa: le richieste dell'avvio passano per prime
    _aspetta(lambda: scaldati == [1])
    fermo.set()
    t.join(2)
    scaldati.clear()
    fermo2 = threading.Event()
    t2 = threading.Thread(target=riscaldamento.sorveglia, args=(lambda: "v", lambda: scaldati.append(1), fermo2, 0.02, 5))
    t2.start()
    fermo2.set()
    t2.join(2)
    assert scaldati == [] and not t2.is_alive()


def test_sorveglia_resiste_agli_errori():
    chiamate = []

    def versione():
        chiamate.append(1)
        if len(chiamate) == 1:
            raise RuntimeError("archivio occupato")
        return "v1"

    scaldati = []
    fermo = threading.Event()
    t = threading.Thread(target=riscaldamento.sorveglia, args=(versione, lambda: scaldati.append(1), fermo, 0.02))
    t.start()
    try:
        _aspetta(lambda: scaldati == [1])
    finally:
        fermo.set()
        t.join(2)


def test_il_riscaldamento_passa_dalla_coda_dei_calcoli():
    """Usa gli stessi permessi dei calcoli delle richieste (al massimo due insieme)."""
    assert calcolo.MAX_CONTEMPORANEI == 2


def _aspetta(condizione, secondi: float = 5) -> None:
    fine = time.monotonic() + secondi
    while not condizione() and time.monotonic() < fine:
        time.sleep(0.01)
    assert condizione()


def test_scalda_contesto_prepara_anche_scambi_svincolati_e_widget(monkeypatch):
    """Dopo un aggiornamento dei dati si preparano formazione, scambi proposti, svincolati e riassunto del widget."""
    from fanta import lega
    chiamate = []
    monkeypatch.setattr(riscaldamento.regole, "carica", lambda p: "regole")
    monkeypatch.setattr(riscaldamento.lega, "carica", lambda p: lega.Rose(squadre=[], mia_squadra="A"))
    for nome in ("formazione", "valori_scambi", "proposte_scambi", "mercato"):
        monkeypatch.setattr(riscaldamento.consigli, nome, lambda *a, _n=nome, **k: chiamate.append(_n))
    monkeypatch.setattr(riscaldamento.widget, "costruisci", lambda *a, **k: chiamate.append("widget"))
    assert riscaldamento.scalda_contesto(Contesto.per_utente(7), None) is True
    assert chiamate == ["formazione", "valori_scambi", "proposte_scambi", "mercato", "widget"]
