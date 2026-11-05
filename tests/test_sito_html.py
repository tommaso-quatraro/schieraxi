"""Sito di presentazione: HTML ben formato, id unici, esempi con nomi inventati."""
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

SITO = Path(__file__).resolve().parent.parent / "sito"
PAGINE = ["index.html", "en/index.html", "404.html", "offline.html"]
VUOTI = {"meta", "link", "img", "br", "input", "hr", "source", "area", "base", "col", "embed", "wbr", "path", "circle", "rect"}


class Nidificazione(HTMLParser):
    """Controllo semplice: ogni tag aperto si chiude, nell'ordine giusto."""

    def __init__(self):
        super().__init__()
        self.pila, self.errori = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VUOTI:
            self.pila.append(tag)

    def handle_endtag(self, tag):
        if tag in VUOTI:
            return
        if not self.pila or self.pila[-1] != tag:
            self.errori.append(f"</{tag}> inatteso (aperti: {self.pila[-3:]})")
        else:
            self.pila.pop()


@pytest.mark.parametrize("nome", PAGINE)
def test_html_ben_formato(nome):
    testo = (SITO / nome).read_text(encoding="utf-8")
    n = Nidificazione()
    n.feed(testo)
    assert not n.errori, n.errori[:3]
    assert not n.pila, n.pila
    ids = re.findall(r'\sid="([^"]+)"', testo)
    assert len(ids) == len(set(ids)), "id duplicati"


@pytest.mark.parametrize("nome", ["index.html", "en/index.html"])
def test_esempi_con_nomi_inventati(nome):
    testo = (SITO / nome).read_text(encoding="utf-8")
    nomi = re.findall(r'<span class="nm">([^<]+)</span>', testo)
    nomi += re.findall(r'<span class="ord n">\d</span> ([^<]+)</th>', testo)
    nomi += re.findall(r"<caption>[^:<]+: ([^,<]+),", testo)
    assert len(nomi) == 15 and len(set(nomi)) == 14  # 11 titolari, 3 in panchina; l'esempio del calcolo è un titolare
    noti = {"Immobile", "Lukaku", "Vlahovic", "Osimhen", "Lautaro", "Leao", "Barella", "Donnarumma", "Bastoni", "Theo",
            "Thuram", "Kvaratskhelia", "Dybala", "Pulisic", "Retegui", "Calhanoglu", "Dimarco", "Maignan", "Sommer", "Lookman"}
    assert not noti & set(nomi)
