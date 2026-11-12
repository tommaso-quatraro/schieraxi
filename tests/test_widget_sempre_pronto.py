"""#651: il widget (token `fw_`, che legge solo la cache e non fa partire calcoli) non resta per sempre su «sto calcolando», non
mostra i punti di una formazione mai schierata e riceve 304 finché non cambia niente di quello che mostra. Ore fissate, dati inventati."""
import contextlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

from fanta import account, calcolo, riscaldamento, server, widget as w
from test_token_widget import _scheda, due_utenti, token_di, widget  # noqa: F401  (fixture)

ADESSO = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
SQUADRA = NS(nome="Real Esempio", crediti_residui=12, giocatori=[NS(id=i) for i in range(1, 15)])


def _formazione_in_cache(monkeypatch, versione: dict, calcolati: list) -> None:
    """La formazione passa dalla cache dei calcoli con una chiave per utente e per versione dei dati, come quella vera: il token del
    widget la trova solo se qualcuno l'ha già calcolata."""
    monkeypatch.setattr(server, "_rose", lambda ctx: NS(mia_squadra="Real Esempio", squadra=lambda n: SQUADRA, utente=ctx.utente_id))

    def formazione(db, regole, rose, *a, **k):
        def calcola(_):
            calcolati.append(rose.utente)
            return {"squadra": "Real Esempio", "modulo": "3-4-3", "punteggio_atteso": 71.5,
                    "titolari": [_scheda(i) for i in range(1, 12)], "panchina": [_scheda(i) for i in range(12, 15)]}
        return calcolo.ottieni(("formazione-prova", versione["v"], rose.utente), calcola, db)
    monkeypatch.setattr(w.consigli, "formazione", formazione)


def _ultimo_uso(tabella: str, utente_id: int, quando: datetime) -> None:
    with contextlib.closing(account.apri()) as db:
        db.execute(f"UPDATE {tabella} SET ultimo_uso = ? WHERE utente_id = ?", (account._testo(quando), utente_id))
        db.commit()


def _id(nome: str) -> int:
    with contextlib.closing(account.apri()) as db:
        return db.execute("SELECT id FROM utenti WHERE nome_utente = ?", (nome,)).fetchone()[0]


# ---------------------------------------------------------------- nessun calcolo partito: niente «riprova fra 3 secondi»
def test_senza_calcolo_partito_il_widget_riprova_fra_un_minuto(due_utenti, monkeypatch):
    a, _ = due_utenti
    calcolo.cache.clear()
    _formazione_in_cache(monkeypatch, {"v": "dati-1"}, [])
    c, h = widget(token_di(a))
    r = c.get("/api/widget", headers=h)
    assert r.status_code == 202 and r.json()["riprova_tra"] == calcolo.RIPROVA_SENZA_CALCOLO
    assert r.headers["retry-after"] == str(calcolo.RIPROVA_SENZA_CALCOLO) and "calcolando" not in r.json()["detail"]


# ---------------------------------------------------------------- chi guarda solo il widget
def test_chi_guarda_solo_il_widget_lo_trova_pronto_dopo_un_aggiornamento(due_utenti, monkeypatch):
    """Anna non apre l'app da 8 giorni ma il suo widget chiede ogni ora: dopo un aggiornamento dei dati il riscaldamento prepara
    anche lei, e il widget riceve 200 invece di «sto calcolando» senza fine."""
    a, _ = due_utenti
    calcolo.cache.clear()
    versione, calcolati = {"v": "dati-1"}, []
    _formazione_in_cache(monkeypatch, versione, calcolati)
    monkeypatch.setattr(riscaldamento, "PAUSA", 0)
    monkeypatch.setattr(riscaldamento, "scalda_contesto", lambda ctx, db: bool(w.consigli.formazione(db, None, server._rose(ctx))))
    c, h = widget(token_di(a))
    assert c.get("/api/widget", headers=h).status_code == 202          # niente in cache: il token non calcola
    anna, bruno = _id("anna"), _id("bruno")
    _ultimo_uso("sessioni", anna, ADESSO - timedelta(days=8))
    _ultimo_uso("token_widget", anna, ADESSO - timedelta(hours=2))
    _ultimo_uso("sessioni", bruno, ADESSO - timedelta(days=1))
    versione["v"] = "dati-2"                                           # aggiornamento dei dati: le chiavi cambiano
    assert riscaldamento.scalda_tutti(server._contesto_locale, server._db, adesso=ADESSO) == 2
    assert anna in calcolati
    assert c.get("/api/widget", headers=h).status_code == 200
