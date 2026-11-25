"""#832: con gli account la prova del modello («Quanto è affidabile il modello», Stato dei dati e «Sotto il cofano») si rifà per
ogni utente, nella sua cartella, con le sue regole e le sue rose. Prima il comando scriveva solo il file comune: il primo account
vedeva i numeri del giorno del passaggio agli account, gli altri «La prova si fa da sola…» per sempre. Dati inventati."""
import contextlib
import json
import time

import pandas as pd
import pytest

from fanta import account, affidabilita, archivio, consigli, diario, lega, regole, verifica
from fanta.contesto import Contesto
from fanta.regole import Regole, imposta

ST = "2026-27"


@pytest.fixture
def mondo(multiutente, tmp_path, monkeypatch):
    """Quattro giornate finite (una partita a-b con i voti), due utenti con rose e regole diverse; la prova vera è sostituita da
    una che ricorda con quali regole e rose è stata chiamata."""
    db = archivio.apri(tmp_path / "t.sqlite")
    for g in range(1, 5):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, 'a', 'b', 1)",
                   (g, ST, g, f"2026-09-{g:02d} 15:00"))
        archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": g, "calciatore_id": i, "squadra": s, "voto_red": 6.0}
                                        for i, s in ((1, "a"), (2, "b"))])
    db.commit()
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "dati", lambda db: None)
    chiamate = []

    def finta(d, regole_, par, giornate, rose=None, **k):
        chiamate.append((regole_.bonus.gol["A"], rose))
        return pd.DataFrame([{"stagione": s, "giornata": g, "quadratico_modello": 2.0, "quadratico_fantamedia": 2.1}
                             for s, g in giornate])
    monkeypatch.setattr(verifica, "verifica", finta)
    utenti = []
    for k, nome in enumerate(("primo", "secondo")):
        with contextlib.closing(account.apri()) as adb:
            utente, _, _ = account.registra(adb, nome, "una-password-lunga-9", account.crea_invito(adb, nome))
        ctx = Contesto.per_utente(utente.id)
        ctx.cartella.mkdir(parents=True, exist_ok=True)
        lega.salva(lega.Rose([lega.Squadra(f"Squadra {nome}", [lega.GiocatoreRosa(10 * (k + 1) + i, f"G{i}", "C", "INT")
                                                                for i in range(3)])]), ctx.rose)
        regole.salva(imposta(Regole(), "bonus.gol.A", str(3.0 + k)), ctx.regole)
        utenti.append(ctx)
    # il primo ha la copia fatta al passaggio agli account, ferma a una giornata vecchia e senza impronta
    utenti[0].affidabilita.write_text(json.dumps({"ultima": f"{ST}/2", "righe": [{"giornata": 2}]}), encoding="utf-8")
    yield db, utenti, chiamate
    db.close()


def test_la_prova_si_rifa_per_ogni_utente_con_le_sue_regole_e_rose(mondo):
    from fanta import __main__ as comandi
    db, (primo, secondo), chiamate = mondo
    assert comandi._prova_per_utente(db, scadenza=time.monotonic() + 60) == (2, 0, [])
    assert sorted(chiamate) == [(3.0, [[10, 11, 12]]), (4.0, [[20, 21, 22]])]
    for ctx in (primo, secondo):
        f = affidabilita.carica(ctx.affidabilita)
        assert f["ultima"] == f"{ST}/4" and f["impronta"] and f["sintesi"]["giornate"] == 4
    # al giro dopo non è cambiato niente: nessuna prova rifatta
    assert comandi._prova_per_utente(db, scadenza=time.monotonic() + 60) == (0, 0, []) and len(chiamate) == 2


def test_la_prova_si_rifa_quando_l_utente_cambia_le_sue_regole_o_le_sue_rose(mondo):
    """#840: la prova di un utente si rifaceva solo quando cambiavano le giornate o i loro voti; con regole o rose nuove la carta
    restava con i numeri di prima fino alla giornata dopo. Ora regole e rose sono nell'impronta: si rifà quella di chi le ha
    cambiate, una volta. Il nome di una squadra non conta."""
    from fanta import __main__ as comandi
    db, (primo, secondo), chiamate = mondo
    giro = lambda: comandi._prova_per_utente(db, scadenza=time.monotonic() + 60)     # noqa: E731
    assert giro() == (2, 0, []) and giro() == (0, 0, [])
    regole.salva(imposta(Regole(), "bonus.gol.A", "5.0"), secondo.regole)             # il secondo cambia un bonus
    assert giro() == (1, 0, []) and chiamate[-1] == (5.0, [[20, 21, 22]])
    assert giro() == (0, 0, [])
    rose = lega.carica(primo.rose)                                                    # il primo prende un giocatore
    rose.squadre[0].giocatori.append(lega.GiocatoreRosa(19, "G9", "A", "INT"))
    lega.salva(rose, primo.rose)
    assert giro() == (1, 0, []) and chiamate[-1] == (3.0, [[10, 11, 12, 19]])
    assert giro() == (0, 0, [])
    rose.squadre[0].nome = "Un altro nome"                                            # rinominare la squadra non la rifà
    lega.salva(rose, primo.rose)
    assert giro() == (0, 0, []) and len(chiamate) == 4


def test_un_utente_rotto_non_ferma_gli_altri_e_il_tempo_finito_rimanda(mondo, monkeypatch):
    from fanta import __main__ as comandi
    db, (primo, secondo), chiamate = mondo
    vera = comandi.regole.carica

    def carica(p):
        if p == secondo.regole:
            raise ValueError("regole rovinate")
        return vera(p)
    monkeypatch.setattr(comandi.regole, "carica", carica)
    assert comandi._prova_per_utente(db, scadenza=time.monotonic() + 60) == (1, 0, [(secondo.utente_id, "ValueError")])
    assert affidabilita.carica(primo.affidabilita)["ultima"] == f"{ST}/4" and not secondo.affidabilita.exists()
    assert comandi._prova_per_utente(db, scadenza=time.monotonic() - 1) == (0, 2, []) and len(chiamate) == 1


def test_il_comando_del_cron_fa_la_prova_di_ogni_utente(mondo, monkeypatch, capsys, tmp_path):
    """`python -m fanta affidabilita` (cron): la prova comune (modalità senza account), i diari e la prova di ogni utente."""
    from fanta.__main__ import main
    _, (primo, secondo), chiamate = mondo
    vera = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: vera(tmp_path / "t.sqlite"))
    monkeypatch.setattr(diario, "aggiorna", lambda *a, **k: 0)
    main(["affidabilita"])
    out = capsys.readouterr().out
    assert "prova del modello degli utenti: rifatta per 2 utenti" in out
    assert affidabilita.carica(primo.affidabilita)["ultima"] == f"{ST}/4" and affidabilita.carica(secondo.affidabilita)["impronta"]
    assert affidabilita.carica()["ultima"] == f"{ST}/4"                       # il file comune resta, per la modalità senza account
    assert len(chiamate) == 3
