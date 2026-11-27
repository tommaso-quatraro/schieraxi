"""Avvisi del server (#906, parte A): niente doppioni per lo stesso fatto, la parte importante all'inizio del testo, testi giusti
per una formazione salvata o schierata, e i testi pronti dei promemoria in GET /api/oggi per l'iPhone (che non compone frasi sue).

Mai l'orologio vero: `adesso` è un argomento. Dati inventati e cartelle temporanee."""
from datetime import datetime

import pytest

from fanta import avvisi, consigli, frasi, notifiche, scelte, server
from fanta.regole import Regole

import test_cambio_pronto as cp
from test_promemoria_messa import QUARTO, ROSA_12, SCHIERATI, ST, UN_ORA, _mondo, _salvata
from test_promemoria_schierato import _db
from test_server import client  # noqa: F401 (fixture: un solo utente, senza account)

GIORNATA = "Giornata 9 · 9ª di Serie A"           # la formazione si chiude il 28/10 alle 18:30


def _alle(ora: str) -> datetime:
    h, m = ora.split(":")
    return datetime(2026, 10, 28, int(h), int(m))


CHIUSURA = _alle("18:30")                          # la scadenza della formazione, quella che mostra Oggi


# ---------------------------------------------------------------- punto 4: un solo avviso per lo stesso fatto
DOMANDA = "Hai messo la formazione nell'app della lega? Se sì, spunta «L'ho messa»."


def _cambio_pronto(tmp_path, monkeypatch, ora="17:27", messa=False):
    """Formazione con Castro salvata dalla web (di base senza la spunta); Castro infortunato: all'`ora` il giro dei cambi manda
    «cambio pronto» (Castro infortunato, meglio Bonny). Restituisce le previsioni, gli avvisi mandati e il giro dei promemoria."""
    prev, mandati, manda = cp._scena(monkeypatch)
    monkeypatch.setattr(consigli, "valuta", lambda *a, **k: {"modulo": "4-4-2", "punteggio_atteso": 70.0})     # «cambia la formazione» tace
    fs = tmp_path / "scelte.json"
    scelte.salva(ST, 9, cp.CON_CASTRO, "4-4-2", fs, da="web", messa=messa)
    db = cp._db()
    notifiche.cambi(db, Regole(), cp.ROSE, _alle(ora), tmp_path / "notifiche.json", manda, file_scelte=fs)
    assert [t for t, _, _ in mandati] == ["SchieraXI · cambio pronto"]

    def promemoria(ora):
        return notifiche.promemoria(db, Regole(), cp.ROSE, _alle(ora), tmp_path / "notifiche-promemoria.json", manda, {}, fs)
    return prev, mandati, promemoria


def test_dopo_il_cambio_pronto_il_promemoria_non_ripete_lo_stesso_titolare(tmp_path, monkeypatch):
    """Il doppione del collaudo: «cambio pronto» alle 17:27 e alle 17:31 «un tuo titolare è a rischio» per lo stesso Castro. Ora
    alle 17:31 parte il richiamo della scadenza senza Castro (con la domanda della spunta, che manca), una volta sola."""
    _, mandati, promemoria = _cambio_pronto(tmp_path, monkeypatch)
    assert len(promemoria("17:31")) == 1
    assert promemoria("17:41") == []                      # un promemoria per finestra
    assert mandati[1] == ("SchieraXI · hai messo la formazione?",
                          f"{DOMANDA} {GIORNATA}: si chiude tra circa un'ora, alle 18:30.", "alarm_clock")


def test_nella_finestra_dopo_il_titolare_ancora_fuori_si_ricorda(tmp_path, monkeypatch):
    """Un quarto d'ora prima della scadenza, quasi un'ora dopo il «cambio pronto», Castro è ancora nella formazione salvata."""
    _, mandati, promemoria = _cambio_pronto(tmp_path, monkeypatch)
    promemoria("17:31")
    assert len(promemoria("18:20")) == 1
    assert mandati[-1][1].startswith("Castro è infortunato")


@pytest.mark.parametrize("messa, atteso", [
    (False, ("SchieraXI · hai messo la formazione?", f"{DOMANDA} {GIORNATA}: si chiude alle 18:30.")),
    (True, ("SchieraXI · ultimi minuti per la formazione", f"{GIORNATA}: la formazione si chiude alle 18:30.")),
])
def test_dopo_il_cambio_pronto_vicino_alla_scadenza_l_ultimo_richiamo_arriva_lo_stesso(tmp_path, monkeypatch, messa, atteso):
    """Revisione della #908: «cambio pronto» alle 17:55, scadenza alle 18:30. Alle 18:11 il filtro toglieva Castro e chiudeva la
    finestra del quarto d'ora senza mandare niente: alle 18:21 non partiva più nulla. Il richiamo della scadenza arriva sempre,
    senza la parte su Castro: con la domanda «L'ho messa?» se la spunta manca, solo la scadenza se c'è."""
    _, mandati, promemoria = _cambio_pronto(tmp_path, monkeypatch, ora="17:55", messa=messa)
    promemoria("18:11")
    promemoria("18:21")
    arrivati = [(t, testo) for t, testo, tag in mandati if tag == "alarm_clock"]
    assert arrivati == [atteso]


def test_il_promemoria_dice_solo_i_titolari_che_il_cambio_pronto_non_ha_detto(tmp_path, monkeypatch):
    prev, mandati, promemoria = _cambio_pronto(tmp_path, monkeypatch)
    prev.loc[12, "stato"] = "non_citato"                   # Tosi esce dai convocati dopo il «cambio pronto»
    assert len(promemoria("17:31")) == 1
    testo = mandati[-1][1]
    assert testo.startswith("Tosi non è tra i convocati: controlla la formazione che hai salvato.") and "Castro" not in testo


# ---------------------------------------------------------------- punti 4 e 7: il titolare a rischio
@pytest.mark.parametrize("messa, parola", [(False, "salvato"), (True, "schierato")])
def test_titolare_a_rischio_dice_cosa_ha_e_se_la_formazione_e_salvata_o_schierata(tmp_path, monkeypatch, messa, parola):
    """Prima diceva «Hai già schierato, ma Castro non è più sicuro come titolare» anche per un infortunio e per una formazione solo
    salvata. Ora il fatto vero in testa, e «salvato» senza la spunta «L'ho messa», «schierato» con la spunta."""
    promemoria, mandati = _mondo(tmp_path, monkeypatch, stato="infortunato")
    _salvata(tmp_path, da="web", messa=messa)
    assert len(promemoria(UN_ORA)) == 1
    assert mandati[0] == ("SchieraXI · un tuo titolare è a rischio",
                          f"Castro è infortunato: controlla la formazione che hai {parola}. {GIORNATA}: si chiude alle 18:30.")


def test_piu_titolari_a_rischio_in_elenco_con_la_e_e_con_gli_altri(tmp_path, monkeypatch):
    """Prima «Castro, Ferri non sono più sicuri come titolare», senza «e» e dal quinto nome spariti senza «e altri»."""
    promemoria, mandati = _mondo(tmp_path, monkeypatch, stato="infortunato")
    prev = consigli.previsioni(None, None, 9)[0]
    prev.loc[2, "stato"] = "squalificato"
    _salvata(tmp_path, da="web", messa=True)
    promemoria(UN_ORA)
    assert mandati[-1][0] == "SchieraXI · alcuni tuoi titolari sono a rischio"
    assert mandati[-1][1].startswith("Castro è infortunato e Ferri è squalificato: controlla")
    prev.loc[[3, 4, 5], "stato"] = ["panchina", "non_citato", "infortunato"]
    promemoria(QUARTO)
    assert mandati[-1][1].startswith("Castro è infortunato, Ferri è squalificato e altri 3: controlla")


# ---------------------------------------------------------------- punto 5: la parte importante all'inizio
def test_formazione_non_valida_lo_dice_all_inizio_e_nel_titolo(tmp_path, monkeypatch):
    promemoria, mandati = _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, [*SCHIERATI[1:], 99], da="web")                  # 99 non è nella rosa: non si può schierare
    promemoria(UN_ORA)
    promemoria(QUARTO)
    assert [t for t, _ in mandati] == ["SchieraXI · formazione non più valida"] * 2
    assert all(testo.startswith("La formazione che hai salvato non è più valida: salvane un'altra.") for _, testo in mandati)
    assert f"{GIORNATA}: si chiude tra circa un'ora, alle 18:30." in mandati[0][1]
    assert mandati[1][1].endswith(f"{GIORNATA}: si chiude alle 18:30.")


def test_spunta_mancante_la_domanda_all_inizio_e_nel_titolo(tmp_path, monkeypatch):
    promemoria, mandati = _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, da="web")
    promemoria(UN_ORA)
    promemoria(QUARTO)
    assert [t for t, _ in mandati] == ["SchieraXI · hai messo la formazione?"] * 2
    domanda = "Hai messo la formazione nell'app della lega? Se sì, spunta «L'ho messa»."
    assert mandati[0][1] == f"{domanda} {GIORNATA}: si chiude tra circa un'ora, alle 18:30."
    assert mandati[1][1] == f"{domanda} {GIORNATA}: si chiude alle 18:30."


def test_i_testi_nuovi_hanno_l_inglese():
    for chiave in ("n.t_titolari_rischio", "n.t_non_valida", "n.t_non_messa"):
        assert frasi.F(chiave).in_lingua("en") != frasi.F(chiave)
    motivi = frasi.F("n.m_infortunato", nome="Castro")
    assert (frasi.F("n.rischio_salvata", motivi=motivi, giornata="Matchday 9", ora="18:30").in_lingua("en")
            == "Castro is injured: check the lineup you saved. Matchday 9: it closes at 18:30.")
    assert frasi.F("n.solo_scadenza", giornata="Matchday 9", ora="18:30").in_lingua("en") == "Matchday 9: the lineup closes at 18:30."


# ---------------------------------------------------------------- punto 7: titolo che non sembra un ordine
def test_titolo_della_consigliata_cambiata_non_e_un_ordine():
    assert frasi.F("n.t_cambia_consigliata") == "SchieraXI · la formazione consigliata è cambiata"
    assert frasi.F("n.t_cambia_consigliata").in_lingua("en") == "SchieraXI · the recommended lineup has changed"


# ---------------------------------------------------------------- punto 3: i testi pronti per l'iPhone
SCENARI = {
    "nessuna scelta": ({}, None),
    "senza spunta": ({}, {"da": "web"}),
    "titolare infortunato": ({"stato": "infortunato"}, {"da": "app", "messa": True}),
    "non valida": ({}, {"da": "web", "titolari": [*SCHIERATI[1:], 99]}),
    "a posto": ({}, {"da": "app", "messa": True}),
}


@pytest.mark.parametrize("nome", SCENARI)
def test_i_testi_dei_promemoria_sono_quelli_che_il_server_manda(tmp_path, monkeypatch, nome):
    """`testi_promemoria`: titolo e testo dei due promemoria come partirebbero, gli stessi del giro del server; nessuno se il
    promemoria non serve (la regola di `serve_promemoria`)."""
    mondo, scelta = SCENARI[nome]
    promemoria, mandati = _mondo(tmp_path, monkeypatch, **mondo)
    if scelta is not None:
        scelta = dict(scelta)
        _salvata(tmp_path, scelta.pop("titolari", SCHIERATI), **scelta)
    testi = notifiche.testi_promemoria(_db(), Regole(), ROSA_12, ST, 9, CHIUSURA, tmp_path / "scelte.json", adesso=UN_ORA)
    promemoria(UN_ORA)
    promemoria(QUARTO)
    assert [(t["titolo"], t["testo"]) for t in testi] == [(str(a), str(b)) for a, b in mandati]
    assert [t["minuti"] for t in testi] == ([60, 15] if mandati else [])
    assert bool(testi) is notifiche.serve_promemoria(_db(), Regole(), ROSA_12, ST, 9, tmp_path / "scelte.json")


def test_i_testi_dei_promemoria_nella_lingua_chiesta(tmp_path, monkeypatch):
    _mondo(tmp_path, monkeypatch)
    testi = notifiche.testi_promemoria(_db(), Regole(), ROSA_12, ST, 9, CHIUSURA, tmp_path / "scelte.json", adesso=UN_ORA, lingua="en")
    assert testi[1] == {"minuti": 15, "titolo": "SchieraXI · last minutes for the lineup",
                        "testo": "Matchday 9 · Serie A 9: the lineup closes at 18:30. Have you entered it on Leghe?"}


def test_senza_la_scadenza_niente_testi(tmp_path, monkeypatch):
    """Giornata ancora senza date (Oggi dice «Data da definire»): non c'è un'ora da scrivere, quindi nessun testo."""
    _mondo(tmp_path, monkeypatch)
    assert notifiche.testi_promemoria(_db(), Regole(), ROSA_12, ST, 9, None, tmp_path / "scelte.json", adesso=UN_ORA) == []


def _oggi_finto(monkeypatch, corpo: dict) -> None:
    monkeypatch.setattr(server, "_rose", lambda ctx: ROSA_12)
    monkeypatch.setattr(server.gestione, "oggi", lambda *a, **k: dict(corpo))
    monkeypatch.setattr(server.da_fare, "costruisci", lambda *a, **k: [])


def test_oggi_ha_i_testi_dei_promemoria_nella_lingua_degli_avvisi(client, tmp_path, monkeypatch):  # noqa: F811
    """L'ora nei testi è la scadenza che Oggi mostra (`scadenza`): il campo non rilegge il calendario."""
    _mondo(tmp_path, monkeypatch)
    _oggi_finto(monkeypatch, {"giornata": 9, "scadenza": "2026-10-28 18:30"})
    corpo = client.get("/api/oggi").json()
    assert corpo["serve_promemoria"] is True
    assert corpo["testi_promemoria"][1] == {"minuti": 15, "titolo": "SchieraXI · ultimi minuti per la formazione",
                                            "testo": f"{GIORNATA}: la formazione si chiude alle 18:30. L'hai inserita su Leghe?"}
    assert corpo["testi_promemoria"][0]["minuti"] == 60
    assert client.put("/api/avvisi", json={"lingua": "en"}).status_code == 200
    assert client.get("/api/oggi").json()["testi_promemoria"][1]["titolo"] == "SchieraXI · last minutes for the lineup"
    scelte.salva(ST, 9, SCHIERATI, "4-4-2", scelte.FILE_SCELTE, da="app", messa=True)
    corpo = client.get("/api/oggi").json()
    assert corpo["serve_promemoria"] is False and corpo["testi_promemoria"] == []


def test_oggi_senza_scadenza_ha_la_lista_vuota_senza_leggere_il_calendario(client, tmp_path, monkeypatch):  # noqa: F811
    """Come nei test del widget, l'archivio può non avere il calendario: il campo non lo legge (prima della correzione: errore 500)."""
    _mondo(tmp_path, monkeypatch)
    _oggi_finto(monkeypatch, {"giornata": 9, "scadenza": None})

    def calendario(*a, **k):
        raise AssertionError("il calendario non si rilegge")
    monkeypatch.setattr(avvisi, "prima_partita", calendario)
    r = client.get("/api/oggi")
    assert r.status_code == 200 and r.json()["testi_promemoria"] == [] and r.json()["serve_promemoria"] is True
