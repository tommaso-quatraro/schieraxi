"""Gli avvisi sul telefono nella lingua scelta dall'utente (impostazione `lingua` degli avvisi, predefinito italiano)."""
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from fanta import avvisi, frasi, notifiche, push, server
from fanta.regole import Regole

from test_notifiche import ROSE, _db, _finto, _stato
import codice_web


@pytest.fixture
def telefono(monkeypatch, tmp_path):
    """Un telefono finto: raccoglie titolo e testo che arriverebbero davvero, con le impostazioni di un file temporaneo."""
    arrivati = []
    monkeypatch.setattr(push, "iscrizioni", lambda file=None: [{"finto": True}])
    monkeypatch.setattr(push, "invia", lambda titolo, testo, priorita, tag, file=None: arrivati.append((titolo, testo)) or 1)
    impostazioni = tmp_path / "avvisi.json"

    def manda(titolo, testo, priorita=3, tag="x", **k):
        return notifiche.invia(titolo, testo, priorita, tag, file_impostazioni=impostazioni, file_iscrizioni=tmp_path / "i.json", ntfy=False, **k)
    return type("Telefono", (), {"arrivati": arrivati, "manda": staticmethod(manda), "impostazioni": impostazioni})


def test_la_lingua_si_salva_e_il_predefinito_e_l_italiano(tmp_path):
    f = tmp_path / "i.json"
    assert notifiche.impostazioni(f)["lingua"] == "it"
    assert notifiche.salva_impostazioni({"lingua": "en"}, f)["lingua"] == "en"
    assert notifiche.salva_impostazioni({"cambi": False}, f)["lingua"] == "en"             # salvare altro non la cambia
    assert notifiche.salva_impostazioni({"lingua": "fr"}, f)["lingua"] == "en"             # una lingua che non c'è: resta quella di prima
    assert notifiche.salva_impostazioni({"lingua": "it"}, f)["lingua"] == "it"
    f.write_text(json.dumps({"lingua": 7}), encoding="utf-8")
    assert notifiche.impostazioni(f)["lingua"] == "it"


def test_rotta_avvisi_lingua(dati_isolati):
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.get("/api/avvisi").json()["impostazioni"]["lingua"] == "it"
    assert c.put("/api/avvisi", json={"lingua": "en"}).json()["impostazioni"]["lingua"] == "en"
    assert c.put("/api/avvisi", json={"riepilogo": False}).json()["impostazioni"]["lingua"] == "en"      # un client che non la conosce non la azzera
    assert c.get("/api/avvisi").json()["impostazioni"]["lingua"] == "en"
    r = c.put("/api/avvisi", json={"lingua": "fr"})
    assert r.status_code == 422 and "lingua" in json.dumps(r.json().get("campi"))
    assert c.put("/api/avvisi", json={"lingua": "it", "avviso_prima": 30}).json()["impostazioni"]["lingua"] == "it"


def test_invia_scrive_nella_lingua_scelta(telefono):
    titolo, testo = frasi.F("n.t_cambia"), frasi.F("n.ora_dubbio", nome="Rossi")
    assert telefono.manda(titolo, testo)
    telefono.impostazioni.write_text(json.dumps({"lingua": "en"}), encoding="utf-8")
    assert telefono.manda(titolo, testo)
    assert telefono.arrivati == [("SchieraXI · cambia la formazione", "Rossi: ora in dubbio"), ("SchieraXI · change your lineup", "Rossi: now in doubt")]
    assert telefono.manda("Titolo semplice", "Testo semplice") and telefono.arrivati[-1] == ("Titolo semplice", "Testo semplice")      # i testi senza chiave non cambiano


def test_promemoria_e_cambi_in_inglese(telefono, tmp_path, monkeypatch):
    _finto(monkeypatch, titolari=("Castro", "Bonny"), dubbi=("Castro",))
    telefono.impostazioni.write_text(json.dumps({"lingua": "en"}), encoding="utf-8")
    opz = notifiche.impostazioni(telefono.impostazioni)
    notifiche.promemoria(_db("2026-10-28 18:30"), Regole(), ROSE, datetime(2026, 10, 28, 17, 35), tmp_path / "n.json", telefono.manda, opz)
    notifiche.promemoria(_db("2026-10-28 18:30"), Regole(), ROSE, datetime(2026, 10, 28, 18, 20), tmp_path / "n.json", telefono.manda, opz)
    (t1, c1), (t2, c2) = telefono.arrivati
    assert t1 == "SchieraXI · lineup in one hour" and c1.startswith("Matchday 9 · Serie A matchday 9: the lineup closes in about an hour (deadline at 18:30). Recommended: 4-3-3, 71.2 expected points.")
    assert "To check: Castro." in c1
    assert t2 == "SchieraXI · last minutes for the lineup" and c2 == "Matchday 9 · Serie A matchday 9: the lineup closes at 18:30. Have you entered it on Leghe?"
    righe = notifiche.confronta({"1": _stato("Castro", "titolare", 80), "2": _stato("Vicario", "titolare", 90)},
                                {"1": _stato("Castro", "panchina", 40), "2": _stato("Vicario", "infortunato")})
    giornata = frasi.nome_giornata(9, 6, avviso=True)
    assert telefono.manda(frasi.F("n.t_cambi"), frasi.elenco([giornata] + righe, sep="\n"), 4, "rotating_light")
    assert telefono.arrivati[-1] == ("SchieraXI · changes in the probable lineups",
                                     "Matchday 6 · Serie A matchday 9\nCastro: from the starting lineup to the bench\nVicario: now injured")


def test_formazione_pronta_e_avviso_di_prova_in_inglese(telefono):
    telefono.impostazioni.write_text(json.dumps({"lingua": "en"}), encoding="utf-8")
    pronta = {"titolo": "SchieraXI", "testo": frasi.F("n.pronta", giornata=frasi.nome_giornata(12, 9, avviso=True))}
    assert telefono.manda(pronta["titolo"], pronta["testo"]) and "Matchday 9 · Serie A matchday 12: the lineup is ready." in telefono.arrivati[-1][1]
    assert telefono.manda(frasi.F("n.t_prova"), frasi.F("n.prova"), ignora_silenzio=True)
    assert telefono.arrivati[-1] == ("SchieraXI · test", "If you can read this, the alerts work.")
    assert avvisi.F is frasi.F                                                   # il testo di avvisi.py è una frase con chiave


def test_il_web_manda_la_lingua_agli_avvisi_quando_cambia():
    testi = codice_web.leggi("testi.js")
    app = codice_web.app()
    cambia = testi[testi.index("function scegliLingua"):testi.index("// Link alle pagine Privacy")]
    assert cambia.count("linguaAgliAvvisi(") >= 2 and cambia.index("linguaAgliAvvisi(lingua);") < cambia.index("location.reload()")
    assert "keepalive: true" in app and '"/api/avvisi"' in app and "JSON.stringify({ lingua })" in app


def test_cambi_di_titolarita_a_parole_anche_in_inglese():
    """All'utente una sola percentuale, «gioca N%»: i cambi nelle probabili non citano quella della fonte, in nessuna lingua."""
    giu = notifiche.confronta({"1": _stato("Rowe", "titolare", 85)}, {"1": _stato("Rowe", "titolare", 50)})
    su = notifiche.confronta({"1": _stato("Rowe", "titolare", 50)}, {"1": _stato("Rowe", "titolare", 85)})
    assert [x.in_lingua("en") for x in giu + su] == ["Rowe: now contested for a starting spot", "Rowe: now a likely starter"]
