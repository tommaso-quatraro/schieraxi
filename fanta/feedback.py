"""«Scrivici»: i commenti che gli utenti mandano a chi gestisce il server (decisione del proprietario, 26/11/2026).

- Un commento è un testo (al massimo MAX_CARATTERI, che va a capo come l'ha scritto) con chi lo manda, quando, piattaforma (web,
  iPhone, Android: la decide il server dalle intestazioni), versione dell'app e, se il client la dice, la schermata da cui arriva.
  Sta nel database degli account (tabella `feedback`, una migrazione di `account.MIGRAZIONI`) e se ne va con l'account.
- Al massimo MAX_AL_GIORNO al giorno per utente (contatori di `limiti.py`); un testo vuoto o troppo lungo non si salva e non conta.
- Privato: il testo non va mai nei log né nell'avviso. L'avviso al titolare passa dal suo canale ntfy (lo stesso della sentinella e
  degli script del server, `sentinella.canale`) e dice solo che c'è un commento nuovo e dove leggerlo: ntfy.sh è un servizio pubblico.
  Al massimo MAX_AVVISI_ORA avvisi all'ora per tutto il server; oltre, i commenti si salvano senza avviso.
- Lo legge solo chi gestisce il server: Impostazioni › Gestione › «Commenti degli utenti» (`GET /api/admin/feedback`) oppure, sul
  server, `python -m fanta feedback --ultimi 20`.
Le rotte stanno in `rotte_feedback.py`; qui solo la logica, senza FastAPI.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from . import account, fuso, limiti, sentinella
from .account import ErroreAccount

LOG = logging.getLogger(__name__)
MAX_CARATTERI = 2000
MAX_AL_GIORNO = limiti.MAX_COMMENTI_AL_GIORNO     # per utente (sul server: FANTA_MAX_COMMENTI_AL_GIORNO); chi gestisce non ha tetto
MAX_AVVISI_ORA = 6                    # avvisi al titolare all'ora per tutto il server: oltre, i commenti si salvano senza avviso
MAX_ELENCO = 100                      # commenti mostrati in Gestione (i più recenti); «da leggere» in Gestione conta questi
PIATTAFORME = ("web", "ios", "android")
NOMI_PIATTAFORME = {"web": "web", "ios": "iPhone", "android": "Android"}
VUOTO = "Il commento è vuoto: scrivi qualcosa e riprova."
TROPPO_LUNGO = f"Il commento è troppo lungo: al massimo {MAX_CARATTERI} caratteri."

# caratteri di controllo (tranne a capo e tabulazione) e quelli che girano il verso del testo: nell'elenco di Gestione farebbero
# sembrare il commento un'altra cosa
_INVISIBILI = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u202a-\u202e\u2066-\u2069]")
_VERSIONE = re.compile(r"[0-9A-Za-z.+_() -]{1,40}")
_SCHERMATA = re.compile(r"[a-z0-9_-]{1,40}")


def pulisci(testo: str) -> str:
    """Il testo da salvare: a capo uniformi, senza caratteri invisibili né spazi in testa e in coda. ErroreAccount 400 se resta
    vuoto o supera MAX_CARATTERI (contati come li vede chi legge, non in byte)."""
    t = str(testo or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u2028", "\n").replace("\u2029", "\n")
    t = _INVISIBILI.sub("", t).strip()
    if not t:
        raise ErroreAccount(VUOTO, 400)
    if len(t) > MAX_CARATTERI:
        raise ErroreAccount(TROPPO_LUNGO, 400)
    return t


def versione_valida(v: str | None) -> str | None:
    """La versione dichiarata dal client, se ha la forma di una versione («1.572», «2.1 (45)»); altrimenti niente (il commento si
    salva lo stesso: un client sbagliato non deve perdere il commento)."""
    v = (v or "").strip()
    return v if _VERSIONE.fullmatch(v) else None


def schermata_valida(s: str | None) -> str | None:
    s = (s or "").strip().lower()
    return s if _SCHERMATA.fullmatch(s) else None


def piattaforma(client: str | None, da_browser: bool) -> str | None:
    """Da dove arriva: l'intestazione `X-Schieraxi-Client` che le app mandano sempre («ios», domani «android»), altrimenti «web» se
    la richiesta ha i segni di un browser (cookie della sessione o `Sec-Fetch-Mode`); None se non si sa. Solo un'etichetta."""
    c = (client or "").strip().lower()
    if c in PIATTAFORME:
        return c
    return "web" if da_browser else None


def _ora(adesso: datetime | None) -> str:
    return (adesso or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")


def salva(db: sqlite3.Connection, utente_id: int, testo: str, piattaforma: str | None, versione: str | None,
          schermata: str | None, adesso: datetime | None = None) -> int:
    """Salva un commento già pulito (`pulisci`) e restituisce il suo numero."""
    cur = db.execute("INSERT INTO feedback (utente_id, testo, creato, piattaforma, versione, schermata) VALUES (?, ?, ?, ?, ?, ?)",
                     (utente_id, testo, _ora(adesso), piattaforma, versione, schermata))
    db.commit()
    return cur.lastrowid


def elenco(db: sqlite3.Connection, massimo: int = MAX_ELENCO) -> list[dict]:
    """I commenti, il più recente in alto: {id, testo, quando (UTC con il fuso), utente (il nome che si mostra), piattaforma,
    versione, schermata, letto}."""
    righe = db.execute("SELECT f.*, COALESCE(NULLIF(u.nome_visualizzato, ''), u.nome_utente) AS nome FROM feedback f "
                       "JOIN utenti u ON u.id = f.utente_id ORDER BY f.creato DESC, f.id DESC LIMIT ?", (int(massimo),))
    return [{"id": r["id"], "testo": r["testo"], "quando": r["creato"], "utente": r["nome"], "piattaforma": r["piattaforma"],
             "versione": r["versione"], "schermata": r["schermata"], "letto": r["letto"] is not None} for r in righe]


def da_leggere(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM feedback WHERE letto IS NULL").fetchone()[0]


def segna_letto(db: sqlite3.Connection, numero: int, adesso: datetime | None = None) -> bool:
    """Segna letto il commento `numero` (una seconda volta non cambia niente). False se non esiste."""
    if db.execute("SELECT 1 FROM feedback WHERE id = ?", (numero,)).fetchone() is None:
        return False
    db.execute("UPDATE feedback SET letto = COALESCE(letto, ?) WHERE id = ?", (_ora(adesso), numero))
    db.commit()
    return True


# ---------------------------------------------------------------- avviso al titolare
def _canale() -> str | None:
    return sentinella.canale()


def _manda(titolo: str, testo: str) -> bool:
    return sentinella.manda_ntfy(titolo, testo, priorita=3, tag="speech_balloon")


def testo_avviso(da_leggere: int) -> tuple[str, str]:
    """Titolo e riga dell'avviso: né il testo né il nome di chi scrive (passano da ntfy.sh)."""
    testo = "Leggilo sulla web in Impostazioni › Gestione › Commenti degli utenti."      # sull'iPhone l'elenco non c'è
    return "SchieraXI · un commento nuovo", testo + (f" Da leggere: {da_leggere}." if da_leggere > 1 else "")


def _avviso_concesso() -> bool:
    """Tetto degli avvisi per tutto il server (MAX_AVVISI_ORA all'ora, contati nel database degli account come i tentativi): con la
    registrazione aperta chiunque può scrivere, e il telefono del titolare non deve ricevere una raffica. Controlla e conta in una
    transazione sola."""
    try:
        with closing(account.apri()) as db:
            account.limite.consuma(db, account._chiave("avviso-commenti"), MAX_AVVISI_ORA, account.ORA)
    except ErroreAccount:
        return False
    return True


def avvisa_titolare(da_leggere: int) -> None:
    """Dopo il salvataggio, fuori dalla richiesta. Senza canale (PC, ambiente di prova) non c'è niente da mandare; oltre il tetto
    dell'ora l'avviso si salta (il commento resta salvato e si vede in Gestione); con il canale e l'invio che non riesce, una riga
    nel registro."""
    if not _canale():
        return
    if not _avviso_concesso():
        LOG.info("Commento salvato senza avviso al titolare: già %d avvisi nell'ultima ora", MAX_AVVISI_ORA)
        return
    if not _manda(*testo_avviso(da_leggere)):
        LOG.warning("Commento salvato, ma l'avviso al titolare non è partito: ntfy non ha risposto")


# ---------------------------------------------------------------- comando per il coordinatore
def quando_italiano(quando: str) -> str:
    try:
        return datetime.fromisoformat(quando).astimezone(fuso.FUSO).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(quando)


def righe_comando(commenti: list[dict]) -> list[str]:
    """`python -m fanta feedback`: per ogni commento una riga con numero, ora italiana, chi, da dove e se è da leggere, poi il
    testo intero rientrato (va a capo come l'ha scritto)."""
    righe = []
    for c in commenti:
        dove = " ".join(x for x in (NOMI_PIATTAFORME.get(c["piattaforma"] or "", c["piattaforma"] or ""), c["versione"] or "") if x)
        testa = [f"#{c['id']}", quando_italiano(c["quando"]), c["utente"], dove or "da dove non si sa",
                 *([f"schermata {c['schermata']}"] if c["schermata"] else []), "letto" if c["letto"] else "da leggere"]
        righe.append(" · ".join(testa))
        righe += [f"  {r}" for r in c["testo"].split("\n")]
        righe.append("")
    return righe
