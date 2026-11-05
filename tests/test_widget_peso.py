"""/api/widget e il suo peso: i blocchi tolti perché la risposta è troppo grande finiscono in `mancano` (il widget lo sa),
e `in_corso` porta solo i numeri della giornata (gli elenchi per giocatore, che nessun widget mostra, restano in /api/oggi)."""
import json

from fanta import widget as w
from test_token_widget import OGGI, _scheda, due_utenti, token_di, widget  # noqa: F401  (fixture)

SCAMBIO = {"mia": "Real Esempio", "altra": "Altra Prova", "do": [{"id": 4, "nome": "g4"}], "ricevo": [{"id": 70, "nome": "g70"}],
           "guadagno_mio": 1.5, "guadagno_loro": 0.4, "valido": True}

IN_CORSO = {"giornata": 9, "giornata_lega": 6, "formazione_di": "consigliata", "punti_fatti": 40.5, "punti_attesi_restanti": 30.0,
            "punti_previsti": 70.5, "modificatore": 0.0, "ancora_da_giocare": 4,
            "giocatori": [{"id": i, "nome": f"g{i}", "ruolo": "C", "squadra": "inter", "titolare": True, "a_punteggio": True,
                           "stato": "fatto", "fantavoto": 6.5, "data": "2026-11-01 18:00"} for i in range(1, 12)],
            "sostituzioni": [{"esce": {"id": 2, "nome": "g2"}, "entra": {"id": 12, "nome": "g12"}}],
            "partite": {"in_corso": 1, "finite": 5, "da_giocare": 3, "rinviate": 0}}


def _peso(corpo: dict) -> int:
    """La stessa misura del server (e della sentinella): JSON con gli spazi, senza escape dei caratteri accentati."""
    return len(json.dumps(corpo, ensure_ascii=False))


def test_sopra_il_tetto_i_blocchi_tolti_finiscono_in_mancano(due_utenti, monkeypatch):
    a, _ = due_utenti
    monkeypatch.setattr(w.osservati, "leggi", lambda f: [1, 2])
    monkeypatch.setattr(w.consigli, "proposte_scambi", lambda *x, **k: (None, [SCAMBIO]))
    c, h = widget(token_di(a))
    pieno = c.get("/api/widget", headers=h).json()
    assert pieno["scambio"] == SCAMBIO and len(pieno["osservati"]) == 2 and "mancano" not in pieno

    monkeypatch.setattr(w, "MAX_BYTE", 100)                     # troppo grande: via scambio e poi osservati
    corpo = c.get("/api/widget", headers=h).json()
    assert "scambio" not in corpo and "osservati" not in corpo
    assert corpo["mancano"] == ["scambio", "osservati"]


def test_si_toglie_solo_quanto_basta(due_utenti, monkeypatch):
    a, _ = due_utenti
    monkeypatch.setattr(w.osservati, "leggi", lambda f: [1, 2])
    monkeypatch.setattr(w.consigli, "proposte_scambi", lambda *x, **k: (None, [SCAMBIO]))
    c, h = widget(token_di(a))
    pieno = c.get("/api/widget", headers=h).json()

    monkeypatch.setattr(w, "MAX_BYTE", _peso(pieno) - 1)        # basta togliere lo scambio
    corpo = c.get("/api/widget", headers=h).json()
    assert "scambio" not in corpo and len(corpo["osservati"]) == 2
    assert corpo["mancano"] == ["scambio"]


def test_un_blocco_gia_mancante_non_si_ripete(due_utenti, monkeypatch):
    """Lo scambio non è in cache (già in `mancano`): sopra il tetto si aggiungono solo gli osservati, senza doppioni."""
    a, _ = due_utenti
    monkeypatch.setattr(w.osservati, "leggi", lambda f: [1, 2])
    c, h = widget(token_di(a))
    monkeypatch.setattr(w, "MAX_BYTE", 100)
    corpo = c.get("/api/widget", headers=h).json()
    assert "osservati" not in corpo and corpo["mancano"] == ["scambio", "osservati"]


def test_senza_osservati_non_si_dice_che_mancano(due_utenti, monkeypatch):
    """Nessun giocatore seguito: non c'è niente da togliere, quindi `osservati` non finisce in `mancano`."""
    a, _ = due_utenti
    c, h = widget(token_di(a))
    monkeypatch.setattr(w, "MAX_BYTE", 100)
    corpo = c.get("/api/widget", headers=h).json()
    assert corpo["mancano"] == ["scambio"]


def test_seguiti_al_massimo_con_gioca_percentuale_entro_il_tetto(due_utenti, monkeypatch):
    """Il numero massimo di seguiti, ognuno con «In dubbio · gioca N%» (`dubbio`, `p_voto`): la risposta resta sotto il tetto
    e niente si toglie."""
    a, _ = due_utenti
    monkeypatch.setattr(w.osservati, "leggi", lambda f: list(range(1, 15)))     # più seguiti del massimo: il widget ne manda 8
    c, h = widget(token_di(a))
    corpo = c.get("/api/widget", headers=h).json()
    assert len(corpo["osservati"]) == w.MAX_OSSERVATI
    assert all((g["p_voto"], g["dubbio"]) == (0.9, False) for g in corpo["osservati"])
    assert _peso(corpo) <= w.MAX_BYTE and corpo["mancano"] == ["scambio"]      # lo scambio non è in cache, i seguiti restano
    # quanto pesano i due campi in tutto: pochi caratteri per seguito
    senza = [{k: v for k, v in g.items() if k not in ("p_voto", "dubbio")} for g in corpo["osservati"]]
    assert _peso(corpo) - _peso(corpo | {"osservati": senza}) <= 35 * w.MAX_OSSERVATI


def test_titolari_con_fantavoto_atteso_entro_il_tetto(due_utenti, monkeypatch):
    """Il fantavoto atteso accanto a ogni titolare (`fv_atteso`, #240), anche con i seguiti al massimo: la risposta resta sotto
    il tetto, niente si toglie, e il campo costa pochi caratteri per titolare."""
    a, _ = due_utenti
    monkeypatch.setattr(w.osservati, "leggi", lambda f: list(range(1, 15)))
    monkeypatch.setattr(w.consigli, "formazione", lambda *x, **k: {
        "squadra": "Real Esempio", "modulo": "3-4-3", "punteggio_atteso": 71.5,
        "titolari": [_scheda(i, fv_atteso=7.62) for i in range(1, 12)], "panchina": [_scheda(i) for i in range(12, 15)]})
    c, h = widget(token_di(a))
    corpo = c.get("/api/widget", headers=h).json()
    tit = corpo["formazione"]["titolari"]
    assert [t["fv_atteso"] for t in tit] == [7.62] * 11
    assert _peso(corpo) <= w.MAX_BYTE and corpo["mancano"] == ["scambio"]      # i seguiti restano
    senza = [{k: v for k, v in t.items() if k != "fv_atteso"} for t in tit]
    assert _peso(corpo) - _peso(corpo | {"formazione": corpo["formazione"] | {"titolari": senza}}) <= 20 * len(tit)


def test_in_corso_del_widget_senza_gli_elenchi_per_giocatore(due_utenti, monkeypatch):
    a, _ = due_utenti
    monkeypatch.setattr(w.gestione, "oggi", lambda *x, **k: OGGI | {"iniziata": True, "fase": "in_corso", "riepilogo": None,
                                                                     "prossima": None, "in_corso": IN_CORSO})
    c, h = widget(token_di(a))
    corpo = c.get("/api/widget", headers=h).json()
    # i numeri della giornata (quelli che il widget mostra) restano, uguali a /api/oggi
    assert corpo["in_corso"] == {k: v for k, v in IN_CORSO.items() if k not in ("giocatori", "sostituzioni")}
    # /api/oggi resta intero (stessa funzione: il blocco non si modifica sul posto)
    oggi = c.get("/api/oggi", headers=h).json()
    assert len(oggi["in_corso"]["giocatori"]) == 11 and len(oggi["in_corso"]["sostituzioni"]) == 1
    assert len(IN_CORSO["giocatori"]) == 11
