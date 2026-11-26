"""Promemoria anche dalla web app (26/11/2026). Chi ha l'app per iPhone e la web app sulla Home con gli avvisi accesi può
ricevere lo stesso promemoria due volte: quello locale dell'app e quello del server alla web. `GET /api/avvisi` dice da dove
arrivano già i promemoria (`promemoria_da`): `web`, `ntfy` con «Avvisi anche per l'app nativa» e il canale, altrimenti `app`.
Serve solo a informare: l'app per iPhone programma sempre i suoi promemoria (nessuna regola del server sa con certezza cosa
mostra quel telefono) e con `web` la riga sotto «Avvisi su questo dispositivo» dice che il promemoria arriva anche dalla web app.

`web` vale solo per un'iscrizione che sicuramente arriva a un iPhone ed è viva:
- nata su un iPhone (la web lo dice quando la manda, `iphone`); iPad e Mac si presentano come «Macintosh» e non contano, e
  nemmeno le iscrizioni di prima, senza il dato;
- del servizio di notifica di Apple;
- confermata negli ultimi GIORNI_CONFERMA giorni (`confermata`: la scrive il server a ogni iscrizione, e la web rimanda la sua
  una volta al giorno, finché ha il permesso). Una web app tolta dalla Home o con le notifiche spente smette di confermare;
- senza un invio rifiutato dopo la conferma (`fallita`: Apple ha risposto con un codice diverso da 404/410, che invece
  tolgono l'iscrizione)."""
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from fanta import notifiche, push, server

CHIAVI = {"p256dh": "chiave-finta", "auth": "segreto-finto"}
APPLE = "https://web.push.apple.com/QGinventato123"
CHROME = "https://fcm.googleapis.com/fcm/send/inventato456"
FIREFOX = "https://updates.push.services.mozilla.com/wpush/v2/inventato789"
ADESSO = datetime(2026, 11, 26, 9, 30)


def _data(d):
    return d.isoformat(timespec="seconds") if isinstance(d, datetime) else d


def _voce(ep, iphone=None, confermata=None, fallita=None):
    v = {"endpoint": ep, "keys": CHIAVI}
    if iphone is not None:
        v["iphone"] = iphone
    if confermata is not None:
        v["confermata"] = _data(confermata)
    if fallita is not None:
        v["fallita"] = _data(fallita)
    return v


@pytest.fixture
def c(dati_isolati, monkeypatch):
    monkeypatch.setattr(notifiche, "canale", lambda: None)
    return TestClient(server.app, headers={"X-Fanta": "1"})


def _iscritti(dati_isolati, *voci):
    (dati_isolati / "push.json").parent.mkdir(parents=True, exist_ok=True)
    (dati_isolati / "push.json").write_text(json.dumps(list(voci)), encoding="utf-8")


@pytest.mark.parametrize(("voci", "atteso"), [
    ((), "app"),
    ((_voce(CHROME, True, ADESSO),), "app"),                       # notifiche della web solo sul computer
    ((_voce(APPLE, True, ADESSO),), "web"),                        # web app sulla Home di un iPhone, confermata adesso
    ((_voce(CHROME, None, ADESSO), _voce(APPLE, True, ADESSO)), "web"),
    ((_voce(APPLE, False, ADESSO),), "app"),                       # iPad o Mac («Macintosh»): forse non è questo telefono
    ((_voce(APPLE, None, ADESSO),), "app"),                        # iscrizione di prima, senza il dato
    ((_voce(APPLE, "sì", ADESSO),), "app"),                        # dato strano
    ((_voce(APPLE, True),), "app"),                                # mai confermata
    ((_voce(APPLE, True, "ieri"),), "app"),                        # data illeggibile
    ((_voce(APPLE, True, ADESSO - timedelta(days=3)),), "web"),    # al limite della finestra
    ((_voce(APPLE, True, ADESSO - timedelta(days=3, minutes=1)),), "app"),   # scaduta o revocata senza che il server lo sappia
    ((_voce(APPLE, True, ADESSO + timedelta(days=1)),), "app"),    # nel futuro: orologio sbagliato, non si sa
    ((_voce(APPLE, True, ADESSO - timedelta(days=1), ADESSO),), "app"),                       # rifiutata dopo la conferma
    ((_voce(APPLE, True, ADESSO - timedelta(days=1), ADESSO - timedelta(days=1)),), "app"),   # rifiutata nello stesso istante
    ((_voce(APPLE, True, ADESSO, ADESSO - timedelta(days=2)),), "web"),                       # confermata di nuovo dopo il rifiuto
    ((_voce(APPLE, True, ADESSO, "boh"),), "app"),                                            # rifiuto con data illeggibile
])
def test_promemoria_da_conta_solo_iscrizioni_vive_di_un_iphone(voci, atteso):
    assert server._promemoria_da(list(voci), False, ADESSO) == atteso


def test_con_ntfy_per_l_app_nativa_i_promemoria_arrivano_da_ntfy():
    assert server._promemoria_da([], True, ADESSO) == "ntfy"
    assert server._promemoria_da([_voce(CHROME, None, ADESSO)], True, ADESSO) == "ntfy"     # il server manda anche a ntfy
    assert server._promemoria_da([_voce(APPLE, True, ADESSO)], True, ADESSO) == "web"


def test_la_rotta_dice_promemoria_da(c, dati_isolati, monkeypatch):
    adesso = datetime.now()
    assert c.get("/api/avvisi").json()["promemoria_da"] == "app"
    _iscritti(dati_isolati, _voce(APPLE, True, adesso))
    stato = c.get("/api/avvisi").json()
    assert (stato["dispositivi"], stato["promemoria_da"]) == (1, "web")
    _iscritti(dati_isolati, _voce(APPLE, True, adesso - timedelta(days=10)))
    assert c.get("/api/avvisi").json()["promemoria_da"] == "app"
    monkeypatch.setattr(notifiche, "canale", lambda: "canale-finto")
    assert c.put("/api/avvisi", json={"app_nativa": True}).json()["promemoria_da"] == "ntfy"


def test_l_iscrizione_tiene_l_iphone_e_la_data_della_conferma(c, dati_isolati):
    """La web manda `iphone` insieme all'iscrizione; il server lo tiene solo se è vero, e segna quando l'ha ricevuta. Rimandata
    (la conferma di ogni giorno) la data si aggiorna e l'iscrizione resta una."""
    prima = datetime.now().replace(microsecond=0)
    assert c.post("/api/push/iscrivi", json={"endpoint": APPLE, "keys": CHIAVI, "iphone": True}).json() == {"dispositivi": 1}
    [salvata] = push.iscrizioni(dati_isolati / "push.json")
    assert salvata["iphone"] is True
    assert prima <= datetime.fromisoformat(salvata["confermata"]) <= datetime.now()
    assert c.get("/api/avvisi").json()["promemoria_da"] == "web"
    assert c.post("/api/push/iscrivi", json={"endpoint": APPLE, "keys": CHIAVI}).json() == {"dispositivi": 1}
    [rimandata] = push.iscrizioni(dati_isolati / "push.json")
    assert "iphone" not in rimandata                                    # senza il dato (web di prima): non conta più
    assert c.get("/api/avvisi").json()["promemoria_da"] == "app"
    c.post("/api/push/iscrivi", json={"endpoint": CHROME, "keys": CHIAVI, "iphone": "sì"})
    assert all("iphone" not in s for s in push.iscrizioni(dati_isolati / "push.json"))


def test_un_invio_rifiutato_da_apple_resta_segnato_e_l_iscrizione_non_conta_piu(tmp_path, monkeypatch):
    """Apple rifiuta con un codice diverso da 404/410 (per esempio 403 o 400): l'iscrizione resta, come prima, ma con la data del
    rifiuto (`fallita`), e per `promemoria_da` non è più viva finché la web non la conferma di nuovo. Un errore di rete non è un
    rifiuto di Apple e non la segna."""
    import pywebpush

    f = tmp_path / "push.json"
    monkeypatch.setattr(push, "FILE_ISCRIZIONI", f)                     # push.log nella cartella temporanea, non in dati/
    push.iscrivi({"endpoint": APPLE, "keys": CHIAVI, "iphone": True}, f, adesso=datetime.now() - timedelta(hours=1))
    assert server._promemoria_da(push.iscrizioni(f), False, datetime.now()) == "web"

    class Risposta:
        status_code = 503

    def lento(**k):
        raise TimeoutError("rete lenta")
    monkeypatch.setattr("pywebpush.webpush", lento)
    assert push.invia("T", "x", percorso=f, file_chiavi=tmp_path / "v.json") == 0
    assert "fallita" not in push.iscrizioni(f)[0]

    def rifiutata(**k):
        raise pywebpush.WebPushException("rifiutata", response=Risposta())
    monkeypatch.setattr("pywebpush.webpush", rifiutata)
    prima = datetime.now().replace(microsecond=0)
    assert push.invia("T", "x", percorso=f, file_chiavi=tmp_path / "v.json") == 0
    [salvata] = push.iscrizioni(f)
    assert prima <= datetime.fromisoformat(salvata["fallita"]) <= datetime.now()
    assert server._promemoria_da([salvata], False, datetime.now()) == "app"
    push.iscrivi({"endpoint": APPLE, "keys": CHIAVI, "iphone": True}, f)          # la web la conferma di nuovo
    assert server._promemoria_da(push.iscrizioni(f), False, datetime.now() + timedelta(seconds=1)) == "web"


def test_conferma_scritta_con_l_ora_passata(tmp_path):
    lista = push.iscrivi({"endpoint": APPLE, "keys": CHIAVI, "iphone": True}, tmp_path / "push.json", adesso=ADESSO)
    assert lista == [{"endpoint": APPLE, "keys": CHIAVI, "iphone": True, "confermata": "2026-11-26T09:30:00"}]


@pytest.mark.parametrize(("indirizzo", "atteso"), [
    (APPLE, True), ("https://api.push.apple.com/x", True), (CHROME, False), (FIREFOX, False),
    ("https://web.push.apple.com.esempio.org/x", False), ("https://apple.com/x", False), ("non un indirizzo", False), ("", False),
])
def test_riconosce_il_servizio_di_notifica_di_apple(indirizzo, atteso):
    assert push.su_apple(indirizzo) is atteso
