"""«Da fare» di Oggi: le cose che l'utente dovrebbe sbrigare adesso, in ordine di importanza (campo `da_fare` di GET /api/oggi).

Tutto si legge da cose già pronte: previsioni e formazione già in cache (le ha appena usate `gestione.oggi`), svincolati e scambi
SOLO se già in cache (mai un calcolo nuovo), e piccoli file dell'utente. Ogni controllo è a sé: se uno fallisce gli altri restano,
e `costruisci` non alza mai errori (Oggi si deve aprire comunque). Contratto per le app in docs/API.md.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from . import affidabilita, buon_senso, consigli, diario, movimenti, scelte, stato_utente, widget
from .lega import Rose
from .regole import Regole

MAX_VOCI = 8
MAX_DUBBI = 3
MAX_DIARIO = 2
MAX_COPERTURA = 2
ORE_FORMAZIONE = 12            # la formazione non salvata si segnala da qui alla scadenza
ORE_URGENTE = 3
SOGLIA_GUADAGNO = 1.5          # punti in più (stagione) sotto cui uno svincolato o uno scambio non si nomina nemmeno; le regole
#                                di buon senso (soglie per ruolo sulle prossime giornate, titolarità, costo...) stanno in buon_senso.py
CONSIGLI = ("dubbio", "copertura", "svincolato", "scambio")      # le voci che sono consigli: al massimo buon_senso.MAX_CONSIGLI
GIORNI_ROSE = 4
GIORNI_DATI = 3
GIORNI_CERTIFICATO = 3
ALTA, MEDIA, BASSA = 1, 2, 3
FUORI = ("infortunato", "squalificato")


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _destinazione(scheda: str, sezione: str | None = None, **extra) -> dict:
    """Dove porta il pulsante. `scheda`: oggi|formazione|mercato|scambi|lega|impostazioni (le stesse del web e dei collegamenti
    schieraxi://). `link` è già pronto per iOS e Android; `sezione` e gli extra (giocatore, giornata) dicono il punto preciso."""
    link = f"schieraxi://{scheda}" + (f"/{sezione}" if sezione else "")
    if "giocatore" in extra:
        link = f"schieraxi://giocatore/{extra['giocatore']}"
    return {"scheda": scheda, "sezione": sezione, "link": link} | extra


def _voce(id: str, tipo: str, testo: str, priorita: int, azione: str, destinazione: dict, **extra) -> dict:
    return {"id": id, "tipo": tipo, "testo": testo, "priorita": priorita, "azione": azione, "destinazione": destinazione} | extra


def _ore_a_parole(ore: float) -> str:
    if ore < 1:
        return "meno di un'ora"
    n = round(ore)
    return "1 ora" if n == 1 else f"{n} ore"


# ---------------------------------------------------------------- i singoli controlli
def _dubbi(db, regole: Regole, rose: Rose, giornata: int, file_scelte: Path | None, consigliati: list[int] | None = None) -> list[dict]:
    """Titolari (quelli che l'utente ha salvato, altrimenti i consigliati) fuori o in dubbio, con il miglior sostituto disponibile.
    `consigliati`: i titolari consigliati già calcolati da chi chiama (evita di ricalcolare la formazione)."""
    s = rose.squadra(rose.mia_squadra or "")
    prev, _, _ = consigli.previsioni(db, regole)
    scelta = scelte.leggi(consigli.stagione_corrente(), giornata, file_scelte)
    if scelta:
        titolari = [int(i) for i in scelta["titolari"]]
    elif consigliati:
        titolari = [int(i) for i in consigliati]
    else:
        titolari = [g["id"] for g in consigli.formazione(db, regole, rose)["titolari"]]
    schede = {g.id: consigli.scheda_previsione(g.id, prev.loc[g.id]) for g in s.giocatori if g.id is not None and g.id in prev.index}
    voci = []
    for i in titolari:
        x = schede.get(i)
        if not x:
            continue
        fuori = x["stato"] in FUORI
        if not (fuori or x["dubbio"] or x["p_voto"] < 0.75):
            continue
        liberi = [y for j, y in schede.items() if j not in titolari and y["ruolo"] == x["ruolo"] and y["stato"] not in FUORI]
        alt = max(liberi, key=lambda y: y["punti_attesi"], default=None)
        if fuori:
            testo = f"{x['nome']} {'non può giocare' if x['stato'] == 'squalificato' else 'è infortunato'}."
        else:
            testo = f"{x['nome']} è in dubbio ({round(x['p_voto'] * 100)}% di giocare)."
        extra = {}
        if alt:
            testo += f" Meglio {alt['nome']}" + ("" if str(alt["nome"]).endswith(".") else ".")      # «Adams A.» finisce già col punto
            extra["alternativa"] = {"id": alt["id"], "nome": alt["nome"], "ruolo": alt["ruolo"], "punti_attesi": alt["punti_attesi"]}
        voci.append(_voce(f"dubbio:{i}", "dubbio", testo, ALTA if fuori else MEDIA, "Sostituisci",
                          _destinazione("formazione", giocatore=i), giocatore={"id": i, "nome": x["nome"]}, **extra))
    voci.sort(key=lambda v: (v["priorita"], v["id"]))
    return voci[:MAX_DUBBI]


def _copertura(db, regole: Regole, rose: Rose, lingua: str = "it") -> list[dict]:
    """Reparti della rosa scoperti (priorità alta) o senza ricambi (media): un conteggio sulle previsioni già in cache."""
    from . import copertura
    prev, _, _ = consigli.previsioni(db, regole)
    r = copertura.analizza(prev, regole, rose, lingua)
    voci = []
    for x in (r or {}).get("reparti", [])[:MAX_COPERTURA]:
        scoperto = x["livello"] == copertura.SCOPERTO
        voci.append(_voce(f"copertura:{x['ruolo'] or 'moduli'}", "copertura", x["testo"], ALTA if scoperto else MEDIA,
                          "Cerca un rimpiazzo" if x["ruolo"] else "Apri la formazione",
                          _destinazione("mercato" if x["ruolo"] else "formazione"), reparto=x["ruolo"], livello=x["livello"],
                          disponibili=x["disponibili"], minimo=x["minimo"]))
    return voci


def _formazione_non_salvata(ore: float | None, giornata: int, file_scelte: Path | None) -> dict | None:
    if ore is None or not 0 < ore <= ORE_FORMAZIONE:
        return None
    if scelte.leggi(consigli.stagione_corrente(), giornata, file_scelte):
        return None
    return _voce(f"formazione:{giornata}", "formazione", f"La formazione si chiude tra {_ore_a_parole(ore)} e non l'hai ancora salvata.",
                 ALTA if ore <= ORE_URGENTE else MEDIA, "Apri la formazione", _destinazione("formazione"))


def _recenti(rose: Rose, file_movimenti: Path | None, adesso: datetime) -> tuple[set[int], set[int]]:
    """(presi da poco, lasciati liberi da poco) dai movimenti registrati: regola (f) di buon_senso.py."""
    if file_movimenti is None:
        return set(), set()
    return buon_senso.movimenti_recenti(movimenti.leggi(file_movimenti), rose.mia_squadra, adesso)


def _frase_guadagno(breve: float | None, guadagno: float, n: int | None) -> str:
    """I punti in più a parole: sulle prossime giornate se si sanno (più concreti), altrimenti il totale di stagione."""
    if breve is not None and n:
        return f"circa {_num(breve)} punti in più nelle prossime {n} giornate"
    return f"circa {_num(guadagno)} punti in più"


def _svincolato(db, regole: Regole, rose: Rose, recenti: tuple[set[int], set[int]]) -> dict | None:
    """Il miglior cambio con uno svincolato già promosso dal buon senso in `gestione.mercato` (solo se in cache). Qui si applica
    in più la regola sui movimenti recenti, che il mercato (in cache per tutti) non conosce."""
    mancano: list[str] = []
    m = widget._opzionale(mancano, "svincolato", lambda: consigli.mercato(db, regole, rose))
    for p in (m or {}).get("proposte") or []:
        if p.get("sensato") is False or p.get("fattibile") is False or p.get("guadagno", 0) < SOGLIA_GUADAGNO:
            continue
        esce, entra = p["esce"], p["entra"]
        if buon_senso.ripensamento(esce["id"], entra["id"], recenti):
            continue
        motivo = p.get("motivo") or ""
        n = len(p.get("giornate") or []) or None
        testo = f"{entra['nome']} (libero) al posto di {esce['nome']}: " + (f"{motivo}, " if motivo else "") \
            + _frase_guadagno(p.get("breve"), p["guadagno"], n) + "."
        return _voce(f"svincolato:{entra['id']}", "svincolato", testo, BASSA, "Vedi",
                     _destinazione("mercato", giocatore=entra["id"]), esce={"id": esce["id"], "nome": esce["nome"]},
                     entra={"id": entra["id"], "nome": entra["nome"]}, guadagno=p["guadagno"], motivo=motivo)
    return None


def _scambio(db, regole: Regole, rose: Rose, recenti: tuple[set[int], set[int]]) -> dict | None:
    """La prima proposta di scambio (in cache) che supera il buon senso (`buon_senso.giudica_scambio`)."""
    mancano: list[str] = []
    r = widget._opzionale(mancano, "scambio", lambda: consigli.proposte_scambi(db, regole, rose)[1])
    if not r:
        return None
    prof = {}
    try:
        prof = buon_senso.profili(consigli.previsioni(db, regole)[0])
    except Exception:                                   # noqa: BLE001  (senza profili si giudica solo il guadagno)
        pass
    for p in r:
        if p.get("guadagno_mio", 0) < SOGLIA_GUADAGNO:
            continue
        ok, motivo = buon_senso.giudica_scambio(p, prof, recenti)
        if not ok:
            continue
        do, ricevo = ", ".join(g["nome"] for g in p["do"]), ", ".join(g["nome"] for g in p["ricevo"])
        n = len(p.get("giornate") or []) or None
        testo = f"Con {p['altra']} ti conviene scambiare: dai {do}, ricevi {ricevo}" + (f" ({motivo})" if motivo else "") \
            + f", {_frase_guadagno(p.get('breve_mio'), p['guadagno_mio'], n)}."
        return _voce(f"scambio:{p['altra']}", "scambio", testo, BASSA, "Vedi lo scambio", _destinazione("scambi"), con=p["altra"],
                     guadagno=p["guadagno_mio"], motivo=motivo)
    return None


def _giocatori_di(v: dict) -> set[int]:
    """Gli id dei giocatori nominati da una voce (per non proporre due consigli sullo stesso giocatore)."""
    ids = set()
    for k in ("giocatore", "alternativa", "esce", "entra"):
        if isinstance(v.get(k), dict) and v[k].get("id") is not None:
            ids.add(int(v[k]["id"]))
    return ids


def _limita_consigli(voci: list[dict]) -> list[dict]:
    """(g) e (f) di buon_senso.py: al massimo MAX_CONSIGLI consigli (dubbi, coperture, svincolati, scambi), in ordine di
    importanza, e mai due consigli di mercato sullo stesso giocatore. Le altre voci (formazione, diario, backup...) restano."""
    out, n, visti = [], 0, set()
    for v in voci:
        if v["tipo"] not in CONSIGLI:
            out.append(v)
            continue
        ids = _giocatori_di(v) if v["tipo"] in ("svincolato", "scambio") else set()
        if n >= buon_senso.MAX_CONSIGLI or (ids & visti):
            continue
        visti |= _giocatori_di(v)
        out.append(v)
        n += 1
    return out


def _rose_vecchie(db, stagione: str, file_rose: Path, adesso: datetime) -> dict | None:
    """Dopo una giornata giocata le rose non sono state aggiornate per qualche giorno."""
    ultima = db.execute("SELECT MAX(data) FROM partite WHERE stagione = ? AND giocata = 1", (stagione,)).fetchone()[0]
    if not ultima:
        return None
    ultima = datetime.fromisoformat(str(ultima)[:16].replace("T", " "))
    aggiornate = datetime.fromtimestamp(file_rose.stat().st_mtime)
    giorni = (adesso - aggiornate).days
    if aggiornate >= ultima or giorni < GIORNI_ROSE:
        return None
    return _voce("rose-vecchie", "rose", f"Le rose non sono aggiornate da {giorni} giorni e nel frattempo si è giocata una giornata.",
                 MEDIA, "Aggiorna le rose", _destinazione("lega", "rose"), giorni=giorni)


def _certificato(giorni: int | None) -> dict | None:
    """Lo calcola il client (il server non sa quando scade il certificato dell'app sull'iPhone) e lo manda in `certificato_giorni`."""
    if giorni is None or giorni > GIORNI_CERTIFICATO:
        return None
    if giorni < 0:
        testo, pr = "L'app sul telefono è scaduta: va reinstallata.", ALTA
    elif giorni == 0:
        testo, pr = "L'app sul telefono scade oggi: rinnovala adesso.", ALTA
    else:
        testo, pr = f"L'app sul telefono scade tra {giorni} {'giorno' if giorni == 1 else 'giorni'}: rinnovala.", ALTA if giorni == 1 else MEDIA
    return _voce("certificato", "certificato", testo, pr, "Rinnova", _destinazione("impostazioni", "installazione"))


def _diario(db, stagione: str, file_scelte: Path | None, file_diario: Path | None, regole: Regole | None = None) -> list[dict]:
    """Giornate finite (le ultime 3) senza una formazione dichiarata: basta un tocco per dire «ho schierato la consigliata»."""
    voci = diario.carica(file_diario).get("giornate", {})
    out = []
    prima = getattr(regole, "prima_giornata_lega", 1)
    for g in reversed([x for x in affidabilita.giornate_concluse(db, stagione) if x >= prima][-3:]):
        if scelte.leggi(stagione, g, file_scelte):
            continue
        if (voci.get(f"{stagione}/{g}") or {}).get("schierata"):
            continue
        out.append(_voce(f"diario:{g}", "diario", f"La giornata {g - prima + 1} è finita: dimmi se hai schierato la consigliata.", BASSA,
                         "Ho schierato la consigliata", _destinazione("lega", "diario", giornata=g), giornata=g))
    return out[:MAX_DIARIO]


def _dati_vecchi(db, adesso: datetime) -> dict | None:
    """Avviso del server, solo per chi lo gestisce: i dati non si aggiornano da giorni."""
    q = db.execute("SELECT MAX(quando) FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()[0]
    if not q:
        return None
    giorni = (adesso - datetime.fromisoformat(str(q)[:19])).days
    if giorni < GIORNI_DATI:
        return None
    return _voce("dati-vecchi", "server", f"I dati delle partite non si aggiornano da {giorni} giorni.", MEDIA, "Controlla",
                 _destinazione("impostazioni", "avanzate"), giorni=giorni)


def _primo_avvio(file_impostazioni: Path | None) -> dict | None:
    s = stato_utente.leggi_primo_avvio(file_impostazioni) if file_impostazioni else None
    if not s or s["chiuso"] or not s["saltati"]:
        return None
    n = len(s["saltati"])
    return _voce("primo-avvio", "primo_avvio", f"Hai saltato {n} {'passo' if n == 1 else 'passi'} della configurazione iniziale.", BASSA,
                 "Riprendi", _destinazione("impostazioni", "informazioni"), saltati=s["saltati"])


# ---------------------------------------------------------------- senza rose
def senza_rose(imp: Path | None) -> list[dict]:
    """Per chi non ha ancora importato le rose: Oggi non è un errore ma un benvenuto. Prima voce `rose` (importa), poi, se la
    configurazione guidata non è mai stata iniziata, `primo_avvio`."""
    destinazione = _destinazione("lega", "rose")
    voci = [_voce("senza-rose", "rose", "Benvenuto! Per cominciare importa le rose della tua lega.", ALTA, "Importa le rose", destinazione)]
    try:
        iniziato = bool(stato_utente.leggi_primo_avvio(imp)) if imp else True
    except Exception:                                       # noqa: BLE001  (Oggi si apre comunque)
        iniziato = True
    if not iniziato:
        voci.append(_voce("primo-avvio", "primo_avvio", "Ti guido io: sono pochi passi, tutti facoltativi.", MEDIA, "Inizia",
                          _destinazione("impostazioni", "informazioni"), saltati=[]))
    return voci


# ---------------------------------------------------------------- insieme
def costruisci(db: sqlite3.Connection, regole: Regole, rose: Rose, oggi: dict, ctx, certificato_giorni: int | None = None,
               amministratore: bool = False, adesso: datetime | None = None, lingua: str = "it") -> list[dict]:
    """La lista ordinata (priorità 1 = alta, poi 2 e 3; a parità, nell'ordine dei controlli), al massimo MAX_VOCI voci e al
    massimo buon_senso.MAX_CONSIGLI consigli. `ctx` è il contesto dell'utente (percorsi dei suoi file). Non alza mai errori:
    un controllo che fallisce viene saltato."""
    adesso = adesso or datetime.now()
    stagione = consigli.stagione_corrente()
    ore, giornata = oggi.get("ore_mancanti"), oggi.get("giornata")
    aperta = not oggi.get("iniziata")
    rose_file = getattr(ctx, "rose", None)
    con_account = getattr(ctx, "utente_id", None) is not None
    imp = getattr(ctx, "impostazioni_avvisi", None)
    # fasi della giornata (fasi.py): «in_corso» = formazione chiusa, nessun consiglio su chi schierare; «finita» = la prossima è
    # ancora lontana: niente dubbi sui titolari (le probabili non ci sono ancora), restano rosa e mercato se superano il buon senso
    finita = oggi.get("fase") == "finita"
    controlli = []
    if aperta and giornata and not finita:
        controlli += [lambda: _dubbi(db, regole, rose, giornata, ctx.scelte)]
    if aperta and giornata:
        controlli += [lambda: _copertura(db, regole, rose, lingua),
                      lambda: _formazione_non_salvata(ore, giornata, ctx.scelte)]
    controlli += [lambda: _certificato(certificato_giorni)]
    if rose_file is not None:
        controlli += [lambda: _rose_vecchie(db, stagione, rose_file, adesso)]
    if aperta:
        recenti = _recenti(rose, getattr(ctx, "movimenti", None), adesso)
        controlli += [lambda: _svincolato(db, regole, rose, recenti), lambda: _scambio(db, regole, rose, recenti)]
    controlli += [lambda: _diario(db, stagione, ctx.scelte, ctx.diario, regole)]
    if amministratore or not con_account:
        controlli += [lambda: _dati_vecchi(db, adesso)]
    controlli += [lambda: _primo_avvio(imp)]

    voci: list[dict] = []
    for c in controlli:
        try:
            r = c()
        except Exception:                                   # noqa: BLE001  (Oggi si apre comunque)
            continue
        voci += r if isinstance(r, list) else [r] if r else []
    voci.sort(key=lambda v: v["priorita"])                   # ordinamento stabile: a parità resta l'ordine dei controlli
    return _limita_consigli(voci)[:MAX_VOCI]
