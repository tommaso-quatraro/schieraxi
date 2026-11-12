"""Blocco su file, valido tra processi diversi (il servizio e un comando lanciato a mano non scrivono insieme sulle stesse rose).

`threading.Lock` ferma solo i thread dello stesso processo. Qui un file di appoggio viene bloccato dal sistema operativo
(`fcntl` su Linux, `msvcrt` su Windows): se il processo muore, il blocco cade da solo. Dopo `ATTESA` secondi senza riuscire si
lascia perdere con un errore chiaro (meglio che aspettare per sempre). Con `crea_cartella=False` la cartella del file non si
crea: se manca, FileNotFoundError (chi lo usa sa che senza cartella non c'è niente da proteggere, e non la fa rinascere).
"""
from __future__ import annotations

import time
from pathlib import Path

ATTESA = 60.0


class BloccoFile:
    def __init__(self, percorso: Path, attesa: float = ATTESA, crea_cartella: bool = True):
        self.percorso, self.attesa, self.crea_cartella, self._file = Path(percorso), attesa, crea_cartella, None

    def _prova(self) -> bool:
        try:
            import fcntl
        except ImportError:
            import msvcrt
            try:
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False
        try:
            fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def __enter__(self) -> "BloccoFile":
        if self.crea_cartella:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.percorso, "a+b")
        fine = time.monotonic() + self.attesa
        while not self._prova():
            if time.monotonic() > fine:
                self._file.close()
                raise TimeoutError("Un'altra operazione sulle rose è ancora in corso: riprova fra qualche secondo")
            time.sleep(0.05)
        return self

    def __exit__(self, *_):
        try:
            try:
                import fcntl
                fcntl.flock(self._file, fcntl.LOCK_UN)
            except ImportError:
                import msvcrt
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._file.close()
