"""Le novità in inglese con le parole dell'app e le virgolette inglesi (collaudo della web in inglese del 27/11/2026, versione 1.599).

«» sono le virgolette italiane: in inglese si scrive “ ”. La giornata è «matchday», mai «round»; la formazione è «lineup», mai
«line-up». Il controllo vale per le voci in attesa di rilascio (`fanta/novita.d/`, lette tutte senza nome) e per quello che legge
chi usa l'app in inglese oggi: `fanta/novita.json` con le correzioni di `fanta/contenuti/novita.en.json`."""
import json
import re
from pathlib import Path

from fanta import server

RADICE = Path(__file__).resolve().parent.parent
VIETATE = re.compile(r"[«»]|\brounds?\b|\bline-ups?\b", re.I)


def _vietate(testi) -> list[str]:
    return [t for t in testi if isinstance(t, str) and VIETATE.search(t)]


def test_voci_in_attesa_in_inglese_senza_virgolette_italiane_ne_parole_sbagliate():
    trovate = []
    for p in sorted((RADICE / "fanta" / "novita.d").glob("*.json")):
        dati = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(dati, dict):
            trovate += [f"{p.name}: {t}" for t in _vietate([dati.get("titolo_en"), *(dati.get("voci_en") or [])])]
    assert not trovate, "nelle voci in inglese usa “ ”, «matchday» e «lineup»: " + "; ".join(trovate)


def test_novita_uscite_in_inglese_senza_virgolette_italiane_ne_parole_sbagliate():
    trovate = [f"{v['versione']}: {t}" for v in server.novita_in_lingua("en") for t in _vietate([v["titolo"], *v["voci"]])]
    assert not trovate, "correggile in fanta/contenuti/novita.en.json: " + "; ".join(trovate)


def test_la_correzione_di_novita_en_vale_piu_della_traduzione_uscita(monkeypatch):
    """`fanta/novita.json` non si tocca a mano (lo scrive il rilascio): una traduzione uscita sbagliata si corregge in
    `fanta/contenuti/novita.en.json`, che per quella versione vale più di `titolo_en`/`voci_en`."""
    monkeypatch.setattr(server, "_novita", lambda: [
        {"versione": "9.2", "titolo": "Corretta", "voci": ["a"], "titolo_en": "When a round is over", "voci_en": ["«x»"]},
        {"versione": "9.1", "titolo": "Uscita", "voci": ["a"], "titolo_en": "Released", "voci_en": ["y"]}])
    monkeypatch.setattr(server, "_novita_en", lambda: {"9.2": {"titolo": "When a matchday is over", "voci": ["“x”"]}})
    en = server.novita_in_lingua("en")
    assert [(v["titolo"], v["voci"]) for v in en] == [("When a matchday is over", ["“x”"]), ("Released", ["y"])]
