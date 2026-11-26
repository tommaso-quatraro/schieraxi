"""#911: nel widget medio la riga del server su chi aspetta il recupero (`in_corso.situazione`, con i nomi: «Hanno giocato tutti
tranne Glauco Brevisi, Teo Kloosmeijer e Cesare Pulinski, che aspettano il recupero; mancano anche i voti ufficiali.») non entra
senza rimpicciolirsi. /api/widget manda anche `in_corso.situazione_breve` (con `situazione_breve_frase`): la stessa cosa con il
numero al posto dei nomi, solo per le due frasi con i nomi. `situazione` resta com'è: la leggono i widget già installati.
Nomi inventati."""
import re
from pathlib import Path

import pytest

from fanta import fasi, widget as w
from test_token_widget import OGGI, due_utenti, token_di, widget  # noqa: F401  (fixture)

NOMI = ["Glauco Brevisi", "Teo Kloosmeijer", "Cesare Pulinski"]
LEGA_DEMO = Path(__file__).resolve().parent.parent / "ios" / "Sources" / "Support" / "LegaDemo.swift"


def _in_corso_del_widget(due_utenti, monkeypatch, riga) -> dict:  # noqa: F811
    """Il blocco `in_corso` di /api/widget quando Oggi ha questa riga sotto i punti (una `Frase` vera di `fasi.situazione`)."""
    a, _ = due_utenti
    blocco = {"giornata": 9, "giornata_lega": 6, "punti_fatti": 61.5, "punti_previsti": 66.0, "ancora_da_giocare": 0,
              "situazione": riga, "situazione_frase": riga.json()}
    monkeypatch.setattr(w.gestione, "oggi", lambda *x, **k: OGGI | {"iniziata": True, "fase": "in_corso", "riepilogo": None,
                                                                     "prossima": None, "in_corso": blocco})
    c, h = widget(token_di(a))
    r = c.get("/api/widget", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["in_corso"]


@pytest.mark.parametrize("attesa_voti,nomi,breve,chiave", [
    (False, NOMI[:1], "1 giocatore aspetta il recupero.", "in_corso.recupero_breve"),
    (False, NOMI, "3 giocatori aspettano il recupero.", "in_corso.recupero_breve"),
    (True, NOMI[:1], "1 giocatore aspetta il recupero; mancano i voti ufficiali.", "in_corso.voti_e_recupero_breve"),
    (True, NOMI, "3 giocatori aspettano il recupero; mancano i voti ufficiali.", "in_corso.voti_e_recupero_breve"),
])
def test_con_il_recupero_anche_la_frase_breve(due_utenti, monkeypatch, attesa_voti, nomi, breve, chiave):  # noqa: F811
    riga = fasi.situazione(0, attesa_voti, nomi, 11)
    c = _in_corso_del_widget(due_utenti, monkeypatch, riga)
    # la riga di sempre, con i nomi, resta uguale (i widget già installati leggono quella)
    assert c["situazione"] == riga and all(n in c["situazione"] for n in nomi)
    assert c["situazione_frase"] == riga.json()
    # la breve: il numero al posto dei nomi, singolare e plurale, entro i 60 caratteri
    assert c["situazione_breve"] == breve and len(breve) <= 60
    assert c["situazione_breve_frase"] == {"chiave": chiave, "param": {"n": len(nomi)}}


@pytest.mark.parametrize("riga", [
    fasi.situazione(3, False, [], 11),          # «3 giocatori devono ancora giocare»
    fasi.situazione(0, True, [], 11),           # «Hanno giocato tutti: mancano solo i voti ufficiali.»
    fasi.situazione(0, False, [], 11),          # «I voti dei tuoi giocatori sono tutti usciti.»
    fasi.situazione(0, True, NOMI, 3),          # «I tuoi giocatori aspettano tutti il recupero.»
], ids=["da_giocare", "voti", "finiti", "tutti_recupero"])
def test_le_frasi_gia_corte_non_hanno_la_breve(due_utenti, monkeypatch, riga):  # noqa: F811
    c = _in_corso_del_widget(due_utenti, monkeypatch, riga)
    assert c["situazione"] == riga and c["situazione_frase"] == riga.json()
    assert "situazione_breve" not in c and "situazione_breve_frase" not in c


@pytest.mark.parametrize("frase", [None, "testo", {"chiave": "in_corso.recupero"}, {"chiave": "in_corso.recupero", "param": {"n": 0}},
                                   {"chiave": "in_corso.recupero", "param": {"n": True}}, {"chiave": "in_corso.recupero", "param": {"n": "3"}}])
def test_senza_una_frase_valida_niente_breve(frase):
    """Una riga senza chiave (un testo semplice) o senza un numero valido non ha la breve: resta la riga di sempre."""
    assert fasi.situazione_breve(frase) is None


def test_la_galleria_dei_widget_ha_la_frase_breve_del_server():
    """Le foto `*_recupero` dei widget mostrano `LegaDemo.situazioneRecuperoBreve` (ios/Sources/Support/LegaDemo.swift): deve essere
    la frase che il server manda per i giocatori della frase lunga della demo (`situazioneRecupero`, voti e recupero che mancano).
    Se il catalogo cambia, la demo va riscritta con la stessa frase."""
    swift = LEGA_DEMO.read_text(encoding="utf-8")
    ids = re.search(r"static var situazioneRecupero: String \{\s*let nomi = \[([\d,\s]+)\]", swift)
    breve = re.search(r'static let situazioneRecuperoBreve = "([^"\\]*)"', swift)
    assert ids and breve, "in LegaDemo.swift non trovo situazioneRecupero o situazioneRecuperoBreve"
    nomi = [f"Nome{i.strip()}" for i in ids.group(1).split(",")]
    lunga = fasi.situazione(0, True, nomi, 11)
    assert lunga.chiave == "in_corso.voti_e_recupero"
    assert breve.group(1) == fasi.situazione_breve(lunga.json())
