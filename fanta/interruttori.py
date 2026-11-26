"""Il file delle scelte dell'amministratore per gli interruttori: `dati/funzioni.json` (funzioni.py) e `dati/fonti.json`
(fonti_attive.py). Un oggetto JSON {nome: vero o falso}; valgono anche `1` e `0`, come nelle variabili d'ambiente.

- Il file si rilegge solo se è cambiato (data e dimensione).
- Un file che non si legge (JSON rotto, non un oggetto) vale «nessuna scelta» (decidono ambiente e predefinito), ma lascia una
  riga nel registro con il suo nome; così fanno anche i nomi sconosciuti e i valori diversi da vero e falso, che si ignorano.
  La riga si scrive una volta per ogni versione del file, non a ogni richiesta.
- Cambiare un interruttore dall'app con il file illeggibile viene rifiutato (`FileIlleggibile`, 409 con la frase): riscriverlo
  da capo cancellerebbe tutte le altre scelte scritte a mano.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Container
from pathlib import Path

from .percorsi import scrivi_sicuro

LOG = logging.getLogger(__name__)
MAX_NOMI_NEL_REGISTRO = 10


class FileIlleggibile(ValueError):
    """Il file delle scelte c'è ma non si legge: la frase va a chi ha premuto l'interruttore (409, vedi server._errore_valore)."""
    stato = 409


def vero_falso(valore) -> bool | None:
    """`true`/`false`, oppure `1`/`0`; qualunque altra cosa (anche il testo "1") vale None."""
    if isinstance(valore, bool):
        return valore
    if type(valore) is int and valore in (0, 1):
        return bool(valore)
    return None


class FileScelte:
    """Le scelte di un file, con la cache e il lucchetto per scriverle. `nomi`: i nomi ammessi (le chiavi di FUNZIONI o FONTI)."""

    def __init__(self, nomi: Container[str]):
        self.nomi = nomi
        self._blocco = threading.Lock()
        self._cache: dict[str, tuple[tuple[int, int], dict[str, bool] | None]] = {}   # percorso -> ((data, dimensione), scelte o None)

    def leggi(self, percorso: Path) -> dict[str, bool] | None:
        """Le scelte del file: {} se il file non c'è, None se c'è ma non si legge."""
        try:
            s = percorso.stat()
        except OSError:
            return {}
        impronta = (s.st_mtime_ns, s.st_size)
        c = self._cache.get(str(percorso))
        if c and c[0] == impronta:
            return None if c[1] is None else dict(c[1])
        try:
            d = json.loads(percorso.read_text(encoding="utf-8"))
            motivo = None if isinstance(d, dict) else "non è un oggetto {...}"
        except (OSError, ValueError) as e:
            motivo = type(e).__name__
        if motivo:
            LOG.warning("%s non si legge (%s): le scelte scritte lì non valgono finché non lo correggi, e dall'app non si "
                        "possono cambiare gli interruttori", percorso.name, motivo)
            self._cache[str(percorso)] = (impronta, None)
            return None
        ok = {k: vero_falso(v) for k, v in d.items() if k in self.nomi and vero_falso(v) is not None}
        scartati = ["".join(ch if ch.isprintable() else "?" for ch in str(k)[:40]) for k in d if k not in ok]   # mai a capo nel registro
        if scartati:
            LOG.warning("%s: ignorate le voci %s (nome che non c'è o valore diverso da true e false)", percorso.name,
                        ", ".join(scartati[:MAX_NOMI_NEL_REGISTRO]) + (" e altre" if len(scartati) > MAX_NOMI_NEL_REGISTRO else ""))
        self._cache[str(percorso)] = (impronta, ok)
        return dict(ok)

    def imposta(self, percorso: Path, nome: str, acceso: bool | None) -> None:
        """Scelta dell'amministratore; None la toglie. Leggi-modifica-scrivi sotto il lucchetto: due richieste insieme non si
        perdono a vicenda. Con il file illeggibile alza FileIlleggibile e non lo tocca."""
        with self._blocco:
            scelte = self.leggi(percorso)
            if scelte is None:
                raise FileIlleggibile(f"Non cambio l'interruttore: il file {percorso.name} sul server è scritto male e lo perderei. "
                                      "Correggilo o toglilo, poi riprova.")
            if acceso is None:
                scelte.pop(nome, None)
            else:
                scelte[nome] = bool(acceso)
            scrivi_sicuro(percorso, json.dumps(scelte))
            try:
                os.chmod(percorso, 0o600)                   # solo il proprietario (su Windows non ha effetto)
            except OSError:
                pass
            self._cache.pop(str(percorso), None)
