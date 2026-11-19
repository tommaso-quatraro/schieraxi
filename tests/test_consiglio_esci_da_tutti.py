"""Le email di sicurezza e la Privacy consigliano «Esci da tutti i dispositivi» (#765): il nome fra «» è quello del pulsante
vero di Impostazioni > Il tuo account, la chiave `account.esci_tutti` del catalogo comune che mostrano la web e l'iPhone.
Dal 1/11/2026 al #765 il pulsante non c'era più, e le email consigliavano una cosa che non si poteva fare."""
import inspect
import json
import re
from pathlib import Path

from fanta import posta, testi_legali

CATALOGO = json.loads((Path(__file__).resolve().parents[1] / "fanta" / "testi" / "account.json").read_text(encoding="utf-8"))
NOME_IT = re.compile(r"«(Esci da tutti[^»]*)»")
NOME_EN = re.compile(r"«(Sign out of all[^»]*)»")


def _testi_delle_email() -> list[str]:
    """Il testo di ogni modello di email (`posta.modello_*`), con valori inventati: anche i modelli che verranno."""
    testi = []
    for nome, funzione in inspect.getmembers(posta, inspect.isfunction):
        if not nome.startswith("modello_"):
            continue
        valori = [10 if p.annotation is int else "nome@example.invalid" for p in inspect.signature(funzione).parameters.values()
                  if p.default is inspect.Parameter.empty]
        testi.append(funzione(*valori).testo)
    return testi


def test_le_email_consigliano_il_pulsante_che_c_e():
    nomi = [n for testo in _testi_delle_email() for n in NOME_IT.findall(testo)]
    assert len(nomi) >= 3, nomi                     # accesso nuovo, Google collegato, email cambiata
    assert set(nomi) == {CATALOGO["account.esci_tutti"]["it"]}, nomi


def test_le_email_portano_alla_pagina_del_pulsante():
    """Dove l'email dice il percorso, è quello della pagina che ha il pulsante, sulla web e sull'iPhone: Impostazioni > Il tuo
    account (`imp.account`, la riga di Impostazioni che apre la pagina)."""
    imp = json.loads((Path(__file__).resolve().parents[1] / "fanta" / "testi" / "imp.json").read_text(encoding="utf-8"))
    pagina = f"Impostazioni > {imp['imp.account']['it']}"
    con_pulsante = [testo for testo in _testi_delle_email() if NOME_IT.search(testo)]
    percorsi = [p for testo in con_pulsante for p in re.findall(r"Impostazioni > [^.,;)«\n]+?(?= e |[.,;)«\n]|$)", testo)]
    assert len(percorsi) >= 2, percorsi            # accesso nuovo, email cambiata
    assert set(percorsi) == {pagina}, percorsi


def test_la_privacy_nomina_il_pulsante_che_c_e_in_italiano_e_in_inglese():
    for lingua, cerca in (("it", NOME_IT), ("en", NOME_EN)):
        nomi = cerca.findall(testi_legali.pagina("privacy", lingua))
        assert len(nomi) >= 2, (lingua, nomi)      # token del widget e impronte dei dispositivi
        assert set(nomi) == {CATALOGO["account.esci_tutti"][lingua]}, (lingua, nomi)
