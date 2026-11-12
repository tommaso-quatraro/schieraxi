"""La web aperta in un browser senza finestra su un server finto: i pezzi comuni ai test di comportamento (vedi LEGGIMI.md).

Il server finto è `ServerFinto` di script/ci/aspetto_web.py (solo libreria standard): serve `fanta/web/` di questa cartella di
lavoro e risponde alle `/api/...` con le risposte registrate di `ios/fotografie/vero-*.json` (nomi inventati), nelle tre fasi
della giornata. Niente rete, niente server vero, niente dati veri.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
# La cartella della web da provare: di norma quella di questa cartella di lavoro. SCHIERAXI_WEB_DI_PROVA ne indica un'altra (per
# vedere fallire un test sulla web di prima di una modifica).
WEB = Path(os.environ.get("SCHIERAXI_WEB_DI_PROVA") or RADICE / "fanta" / "web")
FASI = {"prima": "vero-prima.json", "in-corso": "vero-in-corso.json", "finita": "vero-finita.json"}
TELEFONO, PC = (390, 844), (1440, 900)


def aspetto_web():
    """Lo script della regressione visiva, caricato come modulo: ne servono il server finto e le attese della pagina."""
    nome = "aspetto_web_dei_test"
    if nome not in sys.modules:
        spec = importlib.util.spec_from_file_location(nome, RADICE / "script" / "ci" / "aspetto_web.py")
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nome] = modulo                      # le dataclass cercano il loro modulo qui
        spec.loader.exec_module(modulo)
    return sys.modules[nome]


def risposta_registrata(rotta: str, fase: str = "prima"):
    """La risposta registrata di una rotta, come oggetto: per i test che ne cambiano un pezzo."""
    dati = json.loads((RADICE / "ios" / "fotografie" / FASI[fase]).read_text(encoding="utf-8"))
    testo = dati["risposte"][rotta]
    return json.loads(testo) if isinstance(testo, str) else testo


@dataclass
class Schermata:
    """La pagina aperta e ciò che è successo intorno: le rotte `/api/` chieste e gli errori del JavaScript."""
    pagina: object
    base: str
    richieste: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)

    def aspetta(self) -> None:
        aspetto_web()._aspetta(self.pagina)

    def vai(self, indirizzo: str) -> None:
        self.pagina.goto(self.base + indirizzo, wait_until="load")
        self.aspetta()

    def tocca(self, bersaglio) -> None:
        """Un tocco su un elemento (selettore CSS o locator di Playwright), poi si aspetta che la pagina sia ferma."""
        (self.pagina.locator(bersaglio).first if isinstance(bersaglio, str) else bersaglio).click(timeout=10000)
        self.aspetta()

    def titolo(self) -> str:
        return self.pagina.locator("#titolo-pagina").inner_text().strip()

    def testo(self, selettore: str = "#contenuto") -> str:
        return self.pagina.locator(selettore).inner_text()

    def chieste(self, *prefissi: str) -> list[str]:
        return [r for r in self.richieste if r.startswith(prefissi)]
