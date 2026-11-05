"""L'etichetta di stato di un giocatore, pronta dal server: una regola sola per web, iPhone e widget.

Prima la stessa scelta (titolarità prima della scadenza, stato della partita dopo, infortunati e squalificati, dubbio) si rifaceva
in quattro punti dei client, con tre vocabolari diversi (docs/COERENZA-WEB-IPHONE.md, «Etichette pronte dal server?»). Ora ogni
giocatore delle risposte ha il campo facoltativo `etichetta` = {codice, testo, tono}:
- `codice`: stabile, uno di CODICI (i client lo usano solo per decidere, mai per scrivere);
- `testo`: le parole del vocabolario comune, nella lingua della richiesta (`?lingua=en` o `Accept-Language: en`, vedi lingua.py);
- `tono`: neutro, attenzione, negativo o positivo (il colore della pillola).

Il testo si scrive in italiano dove nascono le schede (anche nei calcoli in cache: costa un piccolo dizionario per giocatore);
per una richiesta in inglese lo riscrive `traduci_dati`, nello stesso passaggio che traduce le note degli infortuni (server.py).
"""
from __future__ import annotations

import re

NEUTRO, ATTENZIONE, NEGATIVO, POSITIVO = "neutro", "attenzione", "negativo", "positivo"
TONI = (NEUTRO, ATTENZIONE, NEGATIVO, POSITIVO)

# codice -> (italiano, inglese, tono). Le parole sono quelle di fanta/web/testi.js (tit.*, oggi.*): vocabolario comune.
CODICI: dict[str, tuple[str, str, str]] = {
    # prima della scadenza: dalle probabili e da «gioca N%»
    "titolare": ("Probabile titolare", "Likely starter", POSITIVO),
    "ballottaggio": ("In ballottaggio", "Contested", ATTENZIONE),
    "panchina": ("Probabile panchina", "Likely bench", ATTENZIONE),
    "improbabile": ("Improbabile", "Unlikely", NEGATIVO),
    "in_dubbio": ("In dubbio · gioca {p}%", "Doubtful · plays {p}%", ATTENZIONE),
    "infortunato": ("Infortunato", "Injured", NEGATIVO),
    "squalificato": ("Squalificato", "Suspended", NEGATIVO),
    "fuori": ("Fuori", "Out", NEGATIVO),
    "rinviata": ("Rinviata", "Postponed", ATTENZIONE),
    # dopo la scadenza: com'è la sua partita (fasi.py)
    "da_giocare": ("Da giocare", "Still to play", NEUTRO),
    "in_corso": ("Partita in corso", "Match on", POSITIVO),
    "voto_in_arrivo": ("Voto in arrivo", "Grade coming", NEUTRO),
    "voto": ("Ha giocato", "Played", POSITIVO),
    "senza_voto": ("Senza voto", "No grade", ATTENZIONE),
    # solo negli avvisi di Oggi (non è uno stato: si aggiunge alle altre etichette)
    "diffidato": ("Diffidato", "One yellow from a ban", ATTENZIONE),
}

# stato_partita di fasi.py -> codice
_DA_PARTITA = {"fatto": "voto", "senza_voto": "senza_voto", "attesa_voti": "voto_in_arrivo", "in_corso": "in_corso",
               "da_giocare": "da_giocare", "rinviata": "rinviata"}
_FUORI = ("infortunato", "squalificato")


def _percento(p_voto) -> int:
    """«gioca N%» come lo scrive la web (Math.round): mezzo punto in su, mai l'arrotondamento al pari di Python."""
    try:
        return max(0, min(100, int(float(p_voto) * 100 + 0.5)))
    except (TypeError, ValueError):
        return 0


def crea(codice: str, p_voto=None, lingua: str = "it") -> dict:
    """L'etichetta di un codice: {codice, testo, tono}. `p_voto` serve solo a «In dubbio · gioca N%»."""
    it, en, tono = CODICI[codice]
    testo = (en if lingua == "en" else it).format(p=_percento(p_voto))
    return {"codice": codice, "testo": testo, "tono": tono}


def codice(x: dict) -> str | None:
    """LA regola dello stato di un giocatore (una sola, per tutte le risposte). `x` è una scheda: `titolarita`, `stato` (delle
    probabili), `dubbio`, `rinvio`, `p_voto` e, a giornata iniziata, `stato_partita`. None se non c'è niente da dire.

    Dopo la scadenza conta la partita: voto, senza voto, rinviata; chi è infortunato o squalificato resta tale finché non escono
    i voti (`titolarita` «fuori», come fasi.schede_a_giornata_iniziata); poi voto in arrivo, partita in corso, da giocare.
    Prima della scadenza: partita rinviata, infortunato o squalificato, fuori, in dubbio (lo dicono le probabili), poi la
    titolarità a parole (consigli.titolarita)."""
    stato, partita = x.get("stato"), x.get("stato_partita")
    if partita in _DA_PARTITA:
        c = _DA_PARTITA[partita]
        if c in ("voto", "senza_voto", "rinviata"):
            return c
        if x.get("titolarita") == "fuori":
            return stato if stato in _FUORI else "fuori"
        return c
    if isinstance(x.get("rinvio"), str):
        return "rinviata"
    if stato in _FUORI:
        return stato
    tit = x.get("titolarita")
    if tit == "fuori":
        return "fuori"
    if x.get("dubbio"):
        return "in_dubbio"
    return tit if tit in ("titolare", "ballottaggio", "panchina", "improbabile") else None


def di_giocatore(x: dict, lingua: str = "it") -> dict | None:
    """L'etichetta di una scheda (vedi `codice`), o None."""
    c = codice(x)
    return crea(c, x.get("p_voto"), lingua) if c else None


def di_avviso(tipo: str, p_voto=None, lingua: str = "it") -> dict | None:
    """L'etichetta di un avviso di Oggi per `tipo` (infortunato, squalificato, diffidato). Gli avvisi `dubbio` di Oggi non la usano:
    hanno `di_giocatore` della loro scheda, la stessa della Formazione («Improbabile», «Probabile panchina»...; #282)."""
    c = "in_dubbio" if tipo == "dubbio" else tipo
    return crea(c, p_voto, lingua) if c in CODICI else None


_NUMERO = re.compile(r"(\d+)\s*%")


def in_lingua(et: dict, lingua: str) -> dict:
    """La stessa etichetta con il testo in un'altra lingua (il numero di «gioca N%» si riprende dal testo). Un codice sconosciuto
    resta com'è."""
    c = et.get("codice")
    if c not in CODICI or not isinstance(et.get("testo"), str):
        return et
    m = _NUMERO.search(et["testo"])
    return et | {"testo": crea(c, int(m.group(1)) / 100 if m else None, lingua)["testo"]}


def traduci_dati(x, lingua: str = "en"):
    """Cammina in una risposta JSON già letta e riscrive il testo di ogni `etichetta` nella lingua data. Il resto resta com'è."""
    if isinstance(x, list):
        return [traduci_dati(i, lingua) for i in x]
    if not isinstance(x, dict):
        return x
    return {k: (in_lingua(v, lingua) if k == "etichetta" and isinstance(v, dict) else traduci_dati(v, lingua)) for k, v in x.items()}
