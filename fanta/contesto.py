"""Dove stanno i file personali di chi sta chiedendo.

Interruttore spento: sono quelli di sempre (`lega/` e `dati/`), e li compone server.py leggendo i percorsi dei moduli al
momento della richiesta. Interruttore acceso: una cartella per utente, `dati/utenti/<id>/`, con gli stessi file; il numero
viene SOLO dalla sessione (mai da un parametro della richiesta), quindi un utente non può nemmeno nominare i file di un altro.
I dati comuni a tutti (`dati/fanta.sqlite`: calendario, voti, probabili, quotazioni, modello) non passano di qui.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import percorsi

# nome del file nella cartella dell'utente per ogni cosa personale; in `lega/` e `dati/` si chiamano allo stesso modo
FILE_UTENTE = {"regole": "regole.json", "rose": "rose.json", "movimenti": "movimenti.json", "scelte": "scelte.json",
               "osservati": "osservati.json", "impostazioni_avvisi": "avvisi-impostazioni.json", "icona": "icona.json",
               "iscrizioni_push": "push.json", "diario": "diario.json", "affidabilita": "affidabilita.json",
               "stato_cambi": "notifiche.json", "stato_promemoria": "notifiche-promemoria.json",
               "stato_riepilogo": "notifiche-riepilogo.json", "stato_avvisi": "avvisi.json"}
# gli stessi, ma con il nome che hanno nel backup (e quindi dove stanno oggi, con l'interruttore spento)
NOMI_BACKUP = {"regole": "lega/regole.json", "rose": "lega/rose.json", "movimenti": "lega/movimenti.json",
               "scelte": "dati/scelte.json", "osservati": "dati/osservati.json", "impostazioni_avvisi": "dati/avvisi-impostazioni.json"}
# cosa copia la migrazione dai file di oggi alla cartella del primo utente: (dove sta oggi, come si chiama lì)
DA_MIGRARE = [("lega/regole.json", "regole.json"), ("lega/rose.json", "rose.json"), ("lega/movimenti.json", "movimenti.json"),
              ("lega/immagini", "immagini"), ("lega/archivio", "archivio"),
              ("dati/scelte.json", "scelte.json"), ("dati/osservati.json", "osservati.json"),
              ("dati/avvisi-impostazioni.json", "avvisi-impostazioni.json"), ("dati/icona.json", "icona.json"),
              ("dati/push.json", "push.json"), ("dati/diario.json", "diario.json"), ("dati/affidabilita.json", "affidabilita.json"),
              ("dati/notifiche.json", "notifiche.json"), ("dati/notifiche-promemoria.json", "notifiche-promemoria.json"),
              ("dati/notifiche-riepilogo.json", "notifiche-riepilogo.json"), ("dati/avvisi.json", "avvisi.json")]


@dataclass(frozen=True)
class Contesto:
    utente_id: int | None          # None = l'app di sempre, senza account
    regole: Path
    rose: Path
    movimenti: Path
    scelte: Path
    osservati: Path
    impostazioni_avvisi: Path
    icona: Path
    iscrizioni_push: Path
    diario: Path
    affidabilita: Path
    stato_cambi: Path              # cosa è già stato avvisato: cambi delle probabili, promemoria, riepilogo, «formazione pronta»
    stato_promemoria: Path
    stato_riepilogo: Path
    stato_avvisi: Path
    immagini: Path                 # cartella degli stemmi e delle maglie
    ntfy: bool = True              # avvisi anche con ntfy: solo per l'app di sempre (il canale è uno, del proprietario)
    file_backup: dict[str, Path] | None = None       # per il backup: nome nel backup -> file (None = quelli di sempre sotto la radice)
    copia_prima: Path | None = None                  # dove il ripristino lascia lo stato di prima (None = il solito)

    @classmethod
    def per_utente(cls, utente_id: int) -> "Contesto":
        c = cartella_utente(utente_id)
        file = {k: c / v for k, v in FILE_UTENTE.items()}
        return cls(utente_id=int(utente_id), immagini=c / "immagini", ntfy=False, copia_prima=c / "backup-prima-del-ripristino.json",
                   file_backup={nome: file[k] for k, nome in NOMI_BACKUP.items()}, **file)

    @property
    def cartella(self) -> Path:
        return self.rose.parent


def cartella_utente(utente_id: int) -> Path:
    return percorsi.cartella_account() / "utenti" / str(int(utente_id))


def elimina_cartella(utente_id: int) -> None:
    """Cancella tutti i dati dell'utente (account eliminato)."""
    shutil.rmtree(cartella_utente(utente_id), ignore_errors=True)


def migra(utente_id: int, radice: Path = percorsi.RADICE, forza: bool = False) -> list[str]:
    """COPIA (non sposta) i file della lega di oggi nella cartella dell'utente. I file originali restano dove sono.
    Se nella cartella dell'utente c'è già qualcosa si ferma, a meno di `forza` (che sovrascrive)."""
    destinazione = cartella_utente(utente_id)
    da_copiare = [(radice / a, destinazione / b) for a, b in DA_MIGRARE if (radice / a).exists()]
    gia = [d.name for _, d in da_copiare if d.exists()]
    if gia and not forza:
        raise ValueError(f"Nella cartella dell'utente ci sono già dei dati ({', '.join(gia)}): non li sovrascrivo. "
                         "Se vuoi sostituirli, aggiungi --forza.")
    for origine, dest in da_copiare:
        if origine.is_dir():
            shutil.copytree(origine, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origine, dest)
    return [d.name for _, d in da_copiare]
