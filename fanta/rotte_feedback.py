"""Le rotte di «Scrivici» (la logica sta in `feedback.py`). Solo con gli account accesi; senza, rispondono 404 come gli account.

- `POST /api/feedback`: chi ha l'account manda un commento. Il numero dell'utente viene dalla sessione, la piattaforma dalle
  intestazioni (mai dal corpo); il corpo ha un tetto suo (server.LIMITE_FEEDBACK), il testo MAX_CARATTERI e gli invii il tetto al
  giorno di `limiti.py`. L'avviso al titolare parte dopo la risposta.
- `GET /api/admin/feedback` e `POST /api/admin/feedback/{commento_id}/letto`: solo chi gestisce il server (sotto `/api/admin/`
  li ferma già il controllo d'accesso; la dipendenza lo ripete).
"""
from __future__ import annotations

from contextlib import closing

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi import Path as FPath
from pydantic import BaseModel, Field

from . import account, feedback, limiti, rotte_account
from .account import Utente
from .contesto import Contesto

router = APIRouter()
INTESTAZIONE_APP = "x-schieraxi-client"          # come server.INTESTAZIONE_APP: le app la mandano sempre («ios»)


class Commento(BaseModel):
    testo: str = Field(max_length=feedback.MAX_CARATTERI * 2)       # il controllo vero, con il messaggio, è feedback.pulisci
    versione: str | None = Field(default=None, max_length=100)      # facoltativa: quella dell'app che scrive
    schermata: str | None = Field(default=None, max_length=100)     # facoltativa: da dove arriva


def _con_account() -> None:
    if not account.multiutente():
        raise HTTPException(404, "Gli account non sono attivi")


@router.post("/api/feedback", dependencies=[Depends(_con_account)])
def manda_commento(dati: Commento, request: Request, dopo: BackgroundTasks, utente: Utente = Depends(rotte_account.utente_corrente)):
    """Salva il commento (prima si controlla il testo: uno vuoto o troppo lungo non consuma il tetto del giorno) e, dopo la
    risposta, avvisa il titolare. `{ok, id}`."""
    testo = feedback.pulisci(dati.testo)
    posto = limiti.prenota(Contesto.per_utente(utente.id), "commenti")
    da_browser = bool(request.cookies.get(rotte_account.COOKIE) or request.headers.get("sec-fetch-mode"))
    try:
        with closing(account.apri()) as db:
            numero = feedback.salva(db, utente.id, testo, feedback.piattaforma(request.headers.get(INTESTAZIONE_APP), da_browser),
                                    feedback.versione_valida(dati.versione), feedback.schermata_valida(dati.schermata))
            da_leggere = feedback.da_leggere(db)
    except BaseException:
        if posto is not None:
            posto.annulla()                              # non salvato: il commento non conta nel tetto
        raise
    dopo.add_task(feedback.avvisa_titolare, da_leggere)
    return {"ok": True, "id": numero}


@router.get("/api/admin/feedback", dependencies=[Depends(_con_account), Depends(rotte_account.solo_amministratore)])
def commenti_degli_utenti():
    """Gli ultimi commenti, il più recente in alto, e quanti sono ancora da leggere."""
    with closing(account.apri()) as db:
        return {"commenti": feedback.elenco(db), "da_leggere": feedback.da_leggere(db)}


@router.post("/api/admin/feedback/{commento_id}/letto", dependencies=[Depends(_con_account), Depends(rotte_account.solo_amministratore)])
def segna_letto(commento_id: int = FPath(ge=1, le=rotte_account.MAX_ID)):
    with closing(account.apri()) as db:
        if not feedback.segna_letto(db, commento_id):
            raise HTTPException(404, "Commento non trovato")
    return {"ok": True}
