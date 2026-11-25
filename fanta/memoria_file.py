"""File JSON piccoli letti a ogni richiesta (`rose.json`, `regole.json`) tenuti in memoria già trasformati, finché il loro contenuto
non cambia (#907).

Il file si legge sempre (pochi centesimi di millisecondo): la memoria vale solo per un contenuto identico byte per byte, quindi un
file cambiato si vede alla lettura dopo, anche se l'ha cambiato un altro processo con la stessa ora di modifica e la stessa
dimensione. La chiave è il percorso: ogni account ha i suoi file e quindi le sue voci, e il risultato dipende solo dal contenuto.
Chi legge riceve sempre un oggetto nuovo, ricostruito da una copia `pickle` fatta qui in memoria (mai letta da disco né arrivata
da fuori): può modificarlo senza toccare quello delle altre richieste. Tetto: MAX_VOCI, escono prima le meno usate."""
from __future__ import annotations

import pickle
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")
MAX_VOCI = 256                  # due file per account; una voce con le rose di una lega di 10 squadre pesa meno di 100 kB
_voci: OrderedDict[tuple[str, str], tuple[bytes, bytes]] = OrderedDict()     # (tipo, percorso) -> (contenuto, copia pickle)
_blocco = threading.Lock()


def leggi(percorso: Path, tipo: str, trasforma: Callable[[bytes], T]) -> T:
    """`trasforma(contenuto del file)`, rifatto solo se il contenuto è cambiato dall'ultima lettura di questo percorso. `tipo` separa
    chi legge lo stesso file in modi diversi. Gli errori (file che manca, `trasforma` che non accetta il contenuto) passano a chi
    chiama e non si ricordano: alla lettura dopo si riprova."""
    contenuto = percorso.read_bytes()
    chiave = (tipo, str(percorso))
    with _blocco:
        voce = _voci.get(chiave)
        copia = voce[1] if voce is not None and voce[0] == contenuto else None
        if copia is not None:
            _voci.move_to_end(chiave)
    if copia is not None:
        return pickle.loads(copia)       # noqa: S301 - la copia l'ha fatta pickle.dumps qui sotto, da un nostro oggetto
    oggetto = trasforma(contenuto)
    copia = pickle.dumps(oggetto, protocol=pickle.HIGHEST_PROTOCOL)       # prima di darlo a chi chiama, che può modificarlo
    with _blocco:
        _voci[chiave] = (contenuto, copia)
        _voci.move_to_end(chiave)
        while len(_voci) > MAX_VOCI:
            _voci.popitem(last=False)
    return oggetto
