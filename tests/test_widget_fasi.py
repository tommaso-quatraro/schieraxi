"""/api/widget porta, facoltativi, `fase`, `in_corso`, `riepilogo` e `prossima` con la stessa forma di /api/oggi (stessa funzione;
`in_corso` senza gli elenchi `giocatori` e `sostituzioni`, che nessun widget mostra)."""
import json
from datetime import datetime

import pytest

from fanta import calcolo, consigli, gestione, widget as w
from test_fasi import REGOLE, ROSA, _giornata_finita, _oggi, ambiente  # noqa: F401  (fixture)
from test_token_widget import OGGI, due_utenti, token_di, widget  # noqa: F401  (fixture)


def _scheda(i, x=None):
    n, r, s, a, st = ROSA[i]
    return {"id": i, "nome": n, "ruolo": r, "squadra": s, "avversario": "XXX", "in_casa": True, "data_partita": None, "stato": st,
            "percentuale": 90.0, "dubbio": False, "diffidato": False, "punti_attesi": a, "p_voto": 0.9, "rigori_attesi": 0.0, "nota": None}


@pytest.fixture
def widget_vero(ambiente, monkeypatch):  # noqa: F811
    """Il widget sull'archivio finto di test_fasi, con il vero gestione.oggi (e quindi il vero fasi.aggiungi) a un'ora fissata."""
    orig = gestione.oggi
    ora = {}
    monkeypatch.setattr(w.gestione, "oggi", lambda *a, **k: orig(*a, **({"adesso": ora["adesso"]} | k)))
    monkeypatch.setattr(consigli, "scheda_previsione", _scheda)
    monkeypatch.setattr(consigli, "proposte_scambi", lambda *a, **k: (_ for _ in ()).throw(calcolo.InCalcolo()))
    monkeypatch.setattr(consigli, "mercato", lambda *a, **k: (_ for _ in ()).throw(calcolo.InCalcolo()))
    monkeypatch.setattr(w.avatar, "tutti", lambda: {})
    ambiente.db.execute("CREATE TABLE IF NOT EXISTS aggiornamenti (quando TEXT, cosa TEXT, dettaglio TEXT)")

    def costruisci(adesso, **k):
        ora["adesso"] = adesso
        return w.costruisci(ambiente.db, REGOLE, ambiente.rose, ambiente.tmp / "diario.json", ambiente.tmp / "osservati.json",
                            file_scelte=ambiente.tmp / "scelte.json", **k)
    return ambiente, costruisci


def test_tre_fasi_come_in_oggi(widget_vero):
    a, costruisci = widget_vero
    # prima della scadenza: solo `fase`, i blocchi null non si mandano
    c = costruisci(datetime(2026, 11, 6, 12, 0))
    assert c["fase"] == "prima" and not {"in_corso", "riepilogo", "prossima"} & set(c)
    # giornata in corso: `in_corso` uguale a quello di /api/oggi (stessa funzione, anche con la diretta), tranne gli elenchi per
    # giocatore che nessun widget mostra (restano in /api/oggi: vedi test_widget_peso)
    adesso, live = datetime(2026, 11, 8, 22, 40), {("roma", "lazio"): {"stato": "finita"}}
    c = costruisci(adesso, live_partite=live)
    o = _oggi(a, adesso, live_partite=live)
    assert o["in_corso"]["giocatori"]
    assert c["fase"] == "in_corso" and c["in_corso"]["punti_fatti"] > 0
    assert c["in_corso"] == {k: v for k, v in o["in_corso"].items() if k not in ("giocatori", "sostituzioni")}
    assert not {"riepilogo", "prossima"} & set(c)
    # giornata finita: `riepilogo` e `prossima` come in /api/oggi
    _giornata_finita(a)
    (a.tmp / "diario.json").write_text(json.dumps({"giornate": {"2026-27/10": {"stagione": "2026-27", "giornata": 10,
        "consigliata": {"reale": 70.5, "atteso": 68.0}}}}), encoding="utf-8")
    adesso = datetime(2026, 11, 10, 10, 0)
    c, o = costruisci(adesso), _oggi(a, adesso)
    assert c["fase"] == "finita" and "in_corso" not in c
    assert c["riepilogo"] == o["riepilogo"] and c["riepilogo"]["punti_fatti"] == 70.5 and c["prossima"] == o["prossima"]


def test_chi_entra_a_giornata_iniziata_nel_widget_prepara_la_prossima(widget_vero):
    """#651: come /api/oggi, chi è entrato dopo la scadenza senza formazione non vede i punti di una formazione che non ha schierato
    (niente `in_corso`) ma `senza_formazione` e la `prossima` giornata da preparare."""
    a, costruisci = widget_vero
    adesso, nato = datetime(2026, 11, 8, 21, 30), datetime(2026, 11, 8, 18, 0)
    c, o = costruisci(adesso, dal=nato), _oggi(a, adesso, dal=nato)
    assert c["fase"] == "in_corso" and "in_corso" not in c and c["senza_formazione"] is True
    assert c["prossima"] == o["prossima"] and c["prossima"]["giornata"] == 11
    c = costruisci(adesso, dal=datetime(2026, 11, 1, 10, 0))          # c'era già prima della scadenza: la giornata in diretta
    assert c["in_corso"]["formazione_di"] == "consigliata" and "senza_formazione" not in c and "prossima" not in c


def test_rosa_che_non_basta_il_widget_risponde_senza_formazione(widget_vero, monkeypatch):
    """#651: l'errore di un calcolo in coda arriva una volta sola; il widget chiedeva la formazione due volte (Oggi e poi lui) e la
    seconda ripartiva in coda: «sto calcolando» a ogni richiesta. Ora la chiede una volta e, come Oggi, risponde senza formazione;
    nemmeno la formazione salvata la richiede."""
    from fanta import scelte
    from test_fasi import PANCHINA, ST, TITOLARI
    a, costruisci = widget_vero
    consegnato = []

    def formazione(*x, **k):
        if consegnato:
            raise calcolo.InCalcolo()                    # chiesta di nuovo: ripartirebbe in coda
        consegnato.append(1)
        raise ValueError("Non si riesce a formare una squadra: in qualche ruolo nessuno gioca questa giornata")
    monkeypatch.setattr(consigli, "formazione", formazione)
    monkeypatch.setattr(consigli, "valuta", lambda *x, **k: (_ for _ in ()).throw(calcolo.InCalcolo()))
    scelte.salva(ST, 10, TITOLARI, "4-4-2", a.tmp / "scelte.json", panchina=PANCHINA)
    c = costruisci(datetime(2026, 11, 6, 12, 0))
    z = c["formazione"]
    assert (z["modulo"], z["punti_attesi"], z["titolari"], z["panchina"]) == ("–", None, [], []) and "tua_scelta" not in z
    assert c["squadra"] == "Mia" and c["rosa"] and not any(m["titolare"] for m in c["rosa"])


def test_senza_fase_i_campi_mancano(due_utenti):
    a, _ = due_utenti
    c, h = widget(token_di(a))
    corpo = c.get("/api/widget", headers=h).json()
    assert not {"fase", "in_corso", "riepilogo", "prossima"} & set(corpo)       # OGGI senza fase: client vecchi e nuovi invariati


def test_token_widget_etag_cambia_con_i_punti(due_utenti, monkeypatch):
    a, _ = due_utenti
    c, h = widget(token_di(a))
    stato = {"punti": 12.0}
    monkeypatch.setattr(w.gestione, "oggi", lambda *x, **k: OGGI | {"iniziata": True, "fase": "in_corso", "riepilogo": None,
                                                                     "prossima": None, "in_corso": {"giornata": 9, "punti_fatti": stato["punti"]}})
    r1 = c.get("/api/widget", headers=h)
    assert r1.status_code == 200 and r1.json()["fase"] == "in_corso" and r1.json()["in_corso"]["punti_fatti"] == 12.0
    assert "riepilogo" not in r1.json() and "prossima" not in r1.json()
    assert c.get("/api/widget", headers=h | {"If-None-Match": r1.headers["etag"]}).status_code == 304
    stato["punti"] = 15.5                                                            # un gol: l'ETag cambia, niente 304
    r2 = c.get("/api/widget", headers=h | {"If-None-Match": r1.headers["etag"]})
    assert r2.status_code == 200 and r2.json()["in_corso"]["punti_fatti"] == 15.5 and r2.headers["etag"] != r1.headers["etag"]
    # il token resta valido solo per le tre letture
    assert c.get("/api/formazione", headers=h).status_code == 403
    assert c.post("/api/widget", headers=h).status_code in (403, 405)
