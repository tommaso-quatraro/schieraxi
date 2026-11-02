"""Anteprima delle rose: cosa capirebbe l'importazione, SENZA salvare niente (piano «Ingresso facile», passo S1/S2).

Usa lo stesso lettore dell'importazione (`rose.estrai`) e la stessa costruzione delle rose (`lega.da_import`), così l'anteprima
dice esattamente cosa verrà salvato. Per ogni giocatore uno `stato`:
- `sicuro`: nome trovato uguale nel listone, ruolo e squadra compatibili (o scelto a mano); anche un nome abbreviato se ruolo E
  squadra indicati coincidono col listone (`nomi.Indice.cerca` lo dà già come `esatto`);
- `da_controllare`: trovato solo per somiglianza o abbreviazione, ambiguo tra più giocatori, o con ruolo/squadra diversi;
- `non_trovato`: nessun giocatore del listone (ceduto, nome scritto male, codice sconosciuto); se qualcuno gli somiglia,
  fino a 3 suggerimenti in `alternative` (nessuno scelto in partenza).

Le `correzioni` (scelte dell'utente sui dubbi) valgono sia qui sia nell'importazione: `applica_correzioni`.
Funzioni pure: nessun file scritto, niente log del testo (contiene nomi di persone della lega).
"""
from __future__ import annotations

from collections import Counter

from . import frasi, lega, movimenti
from .frasi import F
from .listone import Calciatore
from .nomi import Esito
from .regole import RUOLI, Regole
from .rose import SquadraLetta

SICURO, DA_CONTROLLARE, NON_TROVATO = "sicuro", "da_controllare", "non_trovato"
MANUALE = "manuale"                     # come in /api/rose/correggi: scelto dall'utente

NOMI_RUOLO = {"P": ("portiere", "portieri"), "D": ("difensore", "difensori"),
              "C": ("centrocampista", "centrocampisti"), "A": ("attaccante", "attaccanti")}

CORREZIONE_NON_TROVATA = ("Alcune scelte non corrispondono più alle rose caricate: rifai il controllo delle rose e scegli di nuovo.")
GIOCATORE_NON_NEL_LISTONE = "Uno dei giocatori scelti non è nel listone: rifai il controllo delle rose e scegli di nuovo."
MIA_NON_TROVATA = "La squadra scelta come tua non è tra le rose: scegline un'altra."


def stato(esito: Esito) -> str:
    if esito.calciatore is None:
        return DA_CONTROLLARE if esito.metodo == "ambiguo" and esito.alternative else NON_TROVATO
    if esito.metodo == MANUALE or (esito.metodo == "esatto" and not esito.avviso):
        return SICURO
    return DA_CONTROLLARE


def _calciatore(c: Calciatore) -> dict:
    return {"id": c.id, "nome": c.nome, "ruolo": c.ruolo, "squadra": c.squadra}


def _alternative(esito: Esito) -> list[dict]:
    """I candidati già trovati dal riconoscimento dei nomi: per un dubbio con una proposta, la proposta per prima."""
    candidati = ([esito.calciatore] if esito.calciatore is not None else []) + list(esito.alternative)
    visti, uniche = set(), []
    for c in candidati:
        if c.id not in visti:
            visti.add(c.id)
            uniche.append(_calciatore(c))
    return uniche


def _quanti(n: int, ruolo: str) -> str:
    uno, tanti = NOMI_RUOLO[ruolo]
    return f"{n} {uno if n == 1 else tanti}"


def _elenco(parti: list[str]) -> str:
    return parti[0] if len(parti) == 1 else ", ".join(parti[:-1]) + " e " + parti[-1]


def _conteggio(squadra: lega.Squadra, regole: Regole) -> dict:
    """Ruoli e completezza di una rosa rispetto alle regole, con gli avvisi in italiano semplice."""
    conta = Counter(g.ruolo for g in squadra.giocatori)
    ruoli = {r: conta.get(r, 0) for r in RUOLI}
    senza_ruolo = sum(n for r, n in conta.items() if r not in RUOLI)
    mancano = {r: regole.rosa[r] - ruoli[r] for r in RUOLI if ruoli[r] < regole.rosa[r]}
    in_piu = {r: ruoli[r] - regole.rosa[r] for r in RUOLI if ruoli[r] > regole.rosa[r]}
    attesi = sum(regole.rosa.values())
    avvisi = []
    if len(squadra.giocatori) != attesi:
        n = len(squadra.giocatori)
        avvisi.append(f"{n} {'giocatore' if n == 1 else 'giocatori'} su {attesi}")
    if mancano:
        avvisi.append("mancano " + _elenco([_quanti(n, r) for r, n in mancano.items()]))
    if in_piu:
        avvisi.append("in più: " + _elenco([_quanti(n, r) for r, n in in_piu.items()]))
    if senza_ruolo:
        avvisi.append(f"{senza_ruolo} {'giocatore' if senza_ruolo == 1 else 'giocatori'} senza ruolo")
    return {"totale": len(squadra.giocatori), "attesi": attesi, "ruoli": ruoli, "mancano": mancano, "in_piu": in_piu,
            "senza_ruolo": senza_ruolo, "completa": not avvisi, "avvisi": avvisi}


def applica_correzioni(lette: list[SquadraLetta], correzioni: list[dict] | None, calciatori: list[Calciatore]) -> None:
    """Le scelte dell'utente sui dubbi, prima di salvare: `{squadra, testo, id}` con `testo` = il nome come scritto nel file
    (campo `testo` dell'anteprima) e `id` = il giocatore giusto del listone, oppure None per togliere quella riga.
    Una scelta che non corrisponde a niente (testo cambiato nel frattempo) o un id fuori listone: ValueError, niente si salva."""
    if not correzioni:
        return
    per_id = {c.id: c for c in calciatori}
    per_squadra = {s.nome: s for s in lette}
    togliere: dict[str, set[str]] = {}
    scelte: dict[tuple[str, str], Calciatore] = {}
    for corr in correzioni:
        s = per_squadra.get(corr["squadra"])
        if s is None or not any(r.testo == corr["testo"] for r in s.righe):
            raise ValueError(CORREZIONE_NON_TROVATA)
        if corr.get("id") is None:
            togliere.setdefault(s.nome, set()).add(corr["testo"])
            continue
        c = per_id.get(corr["id"])
        if c is None:
            raise ValueError(GIOCATORE_NON_NEL_LISTONE)
        scelte[s.nome, corr["testo"]] = c
    for s in lette:
        via = togliere.get(s.nome, set())
        s.righe = [r for r in s.righe if r.testo not in via]
        for r in s.righe:
            c = scelte.get((s.nome, r.testo))
            if c is not None:
                r.esito, r.ruolo, r.squadra = Esito(c, MANUALE), c.ruolo, c.squadra


def scegli_mia(rose: lega.Rose, nome: str | None) -> None:
    """Segna la squadra dell'utente (facoltativo nell'importazione). Nome che non c'è: ValueError."""
    if not nome:
        return
    s = rose.squadra(nome)
    if s is None:
        raise ValueError(MIA_NON_TROVATA)
    rose.mia_squadra = s.nome


def _mia_suggerita(lette: list[SquadraLetta], prima: lega.Rose | None, nuove: lega.Rose | None = None) -> str | None:
    """La squadra dell'utente già nota, se è tra quelle lette o se resta com'era (si aggiungono solo le rose degli altri); se se
    n'è letta una sola (si comincia con la propria rosa), quella."""
    nomi = [s.nome for s in lette]
    if prima and prima.mia_squadra and (prima.mia_squadra in nomi or (nuove and any(s.nome == prima.mia_squadra for s in nuove.squadre))):
        return prima.mia_squadra
    return nomi[0] if len(nomi) == 1 else None


def anteprima(lette: list[SquadraLetta], avvisi_lettura: list[str], regole: Regole, prima: lega.Rose | None,
              nuove: lega.Rose) -> dict:
    """Cosa salverebbe l'importazione, senza salvare. `lette` viene da `rose.estrai` (già con le eventuali correzioni),
    `nuove` = `lega.da_import(lette, prima, sostituisci_tutto)`, cioè le rose come diventerebbero."""
    per_nome = {s.nome: s for s in nuove.squadre}
    nomi_prima = {s.nome for s in prima.squadre} if prima else set()
    squadre = []
    totali = Counter()
    for s in lette:
        salvata = per_nome[s.nome]
        giocatori = []
        for riga, g in zip(s.righe, salvata.giocatori):        # da_import tiene l'ordine delle righe
            st = stato(riga.esito)
            totali[st] += 1
            giocatori.append({
                "testo": riga.testo, "stato": st, "metodo": riga.esito.metodo,
                "id": g.id, "nome": g.nome if g.id is not None else None, "ruolo": g.ruolo, "squadra": g.squadra,
                "costo": g.costo, "avviso": riga.esito.avviso, "avviso_frase": frasi.di(riga.esito.avviso),
                "alternative": _alternative(riga.esito) if st != SICURO else [],
            })
        conteggio = _conteggio(salvata, regole)
        squadre.append({"nome": s.nome, "nuova": s.nome not in nomi_prima, "crediti_residui": salvata.crediti_residui,
                        "sicuri": sum(x["stato"] == SICURO for x in giocatori),
                        "da_controllare": sum(x["stato"] == DA_CONTROLLARE for x in giocatori),
                        "non_trovati": sum(x["stato"] == NON_TROVATO for x in giocatori),
                        **conteggio, "giocatori": giocatori})
    avvisi = list(avvisi_lettura)
    avvisi += [f"{s['nome']}: {a}" for s in squadre for a in s["avvisi"]]
    proprietari: dict[int, list[str]] = {}
    for s in nuove.squadre:
        for g in s.giocatori:
            if g.id is not None and s.nome not in proprietari.setdefault(g.id, []):
                proprietari[g.id].append(s.nome)
    letti = {s.nome for s in lette}
    for gid, dove in proprietari.items():
        if len(dove) > 1 and letti & set(dove):
            nome = next(g.nome for s in nuove.squadre for g in s.giocatori if g.id == gid)
            avvisi.append(F("rose.in_piu_squadre", nome=nome, squadre=", ".join(dove)))
    if len(nuove.squadre) == 1:
        avvisi.append(lega.UNA_SQUADRA)
    diff = movimenti.differenze(prima, nuove)
    return {"squadre": squadre, "avvisi": avvisi, "avvisi_frasi": frasi.lista(avvisi), "mia_squadra": _mia_suggerita(lette, prima, nuove),
            "totale_squadre": len(nuove.squadre), "sicuri": totali[SICURO], "da_controllare": totali[DA_CONTROLLARE],
            "non_trovati": totali[NON_TROVATO], "differenze": diff, "riepilogo": diff["testo"]}
