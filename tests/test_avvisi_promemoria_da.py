"""Un solo promemoria per telefono (26/11/2026). Chi ha l'app per iPhone e la web app sulla Home con gli avvisi accesi riceveva
lo stesso promemoria due volte: quello locale dell'app e quello del server alla web. `GET /api/avvisi` dice ora da dove arrivano
già i promemoria (`promemoria_da`): `web` se le notifiche della web sono accese su un dispositivo Apple (il servizio di notifica è
quello di Apple: web app sulla Home di iPhone e iPad, Safari sul Mac), `ntfy` con «Avvisi anche per l'app nativa» e il canale,
altrimenti `app`. Con `web` o `ntfy` l'app per iPhone non programma i suoi promemoria. Le notifiche della web su un computer con
Chrome, Firefox o Edge non contano: lì il telefono resterebbe senza promemoria."""
import json

import pytest
from fastapi.testclient import TestClient

from fanta import notifiche, push, server

CHIAVI = {"p256dh": "chiave-finta", "auth": "segreto-finto"}
APPLE = "https://web.push.apple.com/QGinventato123"
CHROME = "https://fcm.googleapis.com/fcm/send/inventato456"
FIREFOX = "https://updates.push.services.mozilla.com/wpush/v2/inventato789"


@pytest.fixture
def c(dati_isolati, monkeypatch):
    monkeypatch.setattr(notifiche, "canale", lambda: None)
    return TestClient(server.app, headers={"X-Fanta": "1"})


def _iscritti(dati_isolati, *indirizzi):
    (dati_isolati / "push.json").parent.mkdir(parents=True, exist_ok=True)
    (dati_isolati / "push.json").write_text(json.dumps([{"endpoint": e, "keys": CHIAVI} for e in indirizzi]), encoding="utf-8")


@pytest.mark.parametrize(("indirizzi", "atteso"), [
    ((), "app"),
    ((CHROME,), "app"),                    # notifiche della web solo sul computer: il telefono ha bisogno dei suoi promemoria
    ((CHROME, FIREFOX), "app"),
    ((APPLE,), "web"),                     # web app sulla Home di un iPhone o di un iPad (o Safari sul Mac)
    ((CHROME, APPLE), "web"),
])
def test_promemoria_da_segue_le_notifiche_della_web(c, dati_isolati, indirizzi, atteso):
    _iscritti(dati_isolati, *indirizzi)
    stato = c.get("/api/avvisi").json()
    assert stato["dispositivi"] == len(indirizzi)
    assert stato["promemoria_da"] == atteso


def test_con_ntfy_per_l_app_nativa_i_promemoria_arrivano_da_ntfy(c, dati_isolati, monkeypatch):
    monkeypatch.setattr(notifiche, "canale", lambda: "canale-finto")
    assert c.get("/api/avvisi").json()["promemoria_da"] == "app"          # ntfy senza l'opzione dell'app nativa: non apre l'app
    assert c.put("/api/avvisi", json={"app_nativa": True}).json()["promemoria_da"] == "ntfy"
    _iscritti(dati_isolati, CHROME)
    assert c.get("/api/avvisi").json()["promemoria_da"] == "ntfy"         # il server manda anche a ntfy, non solo alla web
    _iscritti(dati_isolati, APPLE)
    assert c.get("/api/avvisi").json()["promemoria_da"] == "web"
    monkeypatch.setattr(notifiche, "canale", lambda: None)
    _iscritti(dati_isolati)
    assert c.get("/api/avvisi").json()["promemoria_da"] == "app"          # senza canale ntfy non parte niente


@pytest.mark.parametrize(("indirizzo", "atteso"), [
    (APPLE, True), ("https://api.push.apple.com/x", True), (CHROME, False), (FIREFOX, False),
    ("https://web.push.apple.com.esempio.org/x", False), ("https://apple.com/x", False), ("non un indirizzo", False), ("", False),
])
def test_riconosce_il_servizio_di_notifica_di_apple(indirizzo, atteso):
    assert push.su_apple(indirizzo) is atteso
