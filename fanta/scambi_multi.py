"""Scambi N contro M (da 1 a 4 giocatori per lato), con conguaglio di crediti, e la loro ricerca automatica.

- `analizza_completo`: analisi di uno scambio qualsiasi con le regole della lega. Le due rose dopo lo scambio devono restare
  valide (massimo per ruolo dalle regole, abbastanza giocatori per schierare almeno un modulo): se non lo sono lo scambio si
  analizza lo stesso, ma lo si dice con il motivo. Il conguaglio è in crediti, con segno dal punto di vista di chi chiede
  (positivo = io ricevo crediti, negativo = li pago io) e si controlla con i crediti residui salvati in Lega.
- `cerca_grandi`: ricerca automatica dei 2 contro 2, 2 contro 1, 3 contro 2... con un budget di calcolo: pochi giocatori per
  lato (i più promettenti, scelti per ruolo e valore), combinazioni provate dalla più promettente, si smette dopo un numero
  fisso di calcoli (il tempo è solo una rete di sicurezza: così il risultato non cambia da una volta all'altra e si può ricordare).
"""
from __future__ import annotations

import time
from collections import Counter
from itertools import combinations

from . import scambi
from .lega import Rose, Squadra
from .lingua import EN
from .regole import RUOLI, Regole, modulo_in_numeri

MAX_PER_LATO = 4
LIMITE_CREDITI = 100_000          # un conguaglio più grande è sicuramente un errore di battitura
POOL_PER_LATO = {2: 9, 3: 8, 4: 7}   # giocatori per lato nella ricerca automatica, secondo la misura più grande cercata
POOL_PER_RUOLO = 4
MAX_VALUTAZIONI = 1500            # calcoli completi (due rose ciascuno) per squadra avversaria
NOMI_RUOLO = {"P": "portieri", "D": "difensori", "C": "centrocampisti", "A": "attaccanti"}
NOMI_RUOLO_EN = {"P": ("goalkeeper", "goalkeepers"), "D": ("defender", "defenders"), "C": ("midfielder", "midfielders"),
                 "A": ("forward", "forwards")}


def _ruolo_en(r: str, n: int) -> str:
    return NOMI_RUOLO_EN[r][0 if n == 1 else 1]


# ---------------------------------------------------------------- rosa valida?
def problemi_rosa(nome: str, conteggio: dict[str, int], regole: Regole, lingua: str = "it") -> list[dict]:
    """Motivi per cui una rosa con questi giocatori per ruolo non va bene: oltre il massimo di un ruolo, oppure troppo
    pochi giocatori per schierare un modulo ammesso. Vuoto = valida. `lingua` ("it" o "en") è la lingua dei testi."""
    en = lingua == EN
    problemi = []
    for r in RUOLI:
        massimo = regole.rosa.get(r)
        if massimo is not None and conteggio.get(r, 0) > massimo:
            k = conteggio[r] - massimo
            testo = (f"{nome}: {conteggio[r]} {_ruolo_en(r, conteggio[r])} out of a maximum of {massimo}, {k} would have to be released" if en
                     else f"{nome}: {conteggio[r]} {NOMI_RUOLO[r]} su un massimo di {massimo}, "
                          + ("ne andrebbe liberato 1" if k == 1 else f"ne andrebbero liberati {k}"))
            problemi.append({"tipo": "eccesso", "squadra": nome, "ruolo": r, "testo": testo})
    mancano = _mancanti(conteggio, regole)
    if mancano:
        if en:
            pezzi = ", ".join(f"{k} {_ruolo_en(r, k)}" for r, k in mancano.items())
            testo = f"{nome}: no formation could be fielded, {pezzi} missing"
        else:
            pezzi = ", ".join(f"{k} {NOMI_RUOLO[r]}" for r, k in mancano.items())
            testo = f"{nome}: non si potrebbe schierare nessun modulo, mancano {pezzi}"
        problemi.append({"tipo": "mancano", "squadra": nome, "ruolo": next(iter(mancano)), "testo": testo})
    return problemi


def _mancanti(conteggio: dict[str, int], regole: Regole) -> dict[str, int]:
    """Il minimo che manca per schierare il modulo ammesso più facile da riempire ({} = si può schierare)."""
    migliore: dict[str, int] | None = None
    for m in regole.moduli:
        d, c, a = modulo_in_numeri(m)
        servono = {"P": 1, "D": d, "C": c, "A": a}
        manca = {r: servono[r] - conteggio.get(r, 0) for r in RUOLI if conteggio.get(r, 0) < servono[r]}
        if not manca:
            return {}
        if migliore is None or sum(manca.values()) < sum(migliore.values()):
            migliore = manca
    return migliore or {}


def rosa_valida(conteggio: dict[str, int], regole: Regole) -> bool:
    return not problemi_rosa("", conteggio, regole)


def non_peggiora(prima: dict[str, int], dopo: dict[str, int], regole: Regole) -> bool:
    """La rosa dopo lo scambio è valida, oppure (se lo era già male prima, per esempio rose importate incomplete) non è messa peggio."""
    if rosa_valida(dopo, regole):
        return True
    eccesso = lambda c: sum(max(0, c.get(r, 0) - regole.rosa.get(r, 99)) for r in RUOLI)  # noqa: E731
    return (not rosa_valida(prima, regole) and eccesso(dopo) <= eccesso(prima)
            and sum(_mancanti(dopo, regole).values()) <= sum(_mancanti(prima, regole).values()))


def ok_dopo(cont_a: dict, cont_b: dict, ruoli_do, ruoli_ricevo, regole: Regole) -> bool:
    """Se io (conteggio ruoli `cont_a`) do giocatori con questi ruoli e ricevo gli altri, le due rose restano a posto?"""
    nx, ny = Counter(ruoli_do), Counter(ruoli_ricevo)
    return (non_peggiora(cont_a, {r: cont_a[r] - nx[r] + ny[r] for r in RUOLI}, regole)
            and non_peggiora(cont_b, {r: cont_b[r] - ny[r] + nx[r] for r in RUOLI}, regole))


def _conteggio(squadra: Squadra, v: scambi.Valori, via: list[int], dentro: list[int]) -> dict[str, int]:
    """Giocatori per ruolo della rosa dopo lo scambio (contando anche chi non è riconosciuto)."""
    conta = Counter(g.ruolo for g in squadra.giocatori if g.ruolo in RUOLI)
    for i in via:
        conta[v.info.at[i, "ruolo"]] -= 1
    for i in dentro:
        conta[v.info.at[i, "ruolo"]] += 1
    return {r: conta.get(r, 0) for r in RUOLI}


def _forza(v: scambi.Valori, i: int) -> float:
    return sum(t[i][1] * t[i][2] for t in v.per_giornata if i in t)


def _taglia_eccesso(ids: list[int], v: scambi.Valori, regole: Regole) -> list[int]:
    """Se un ruolo supera il massimo, chi ha troppi giocatori libera i meno forti: si valuta la rosa già sistemata."""
    risultato = list(ids)
    for r in RUOLI:
        massimo = regole.rosa.get(r)
        del_ruolo = [i for i in risultato if v.info.at[i, "ruolo"] == r]
        if massimo is not None and len(del_ruolo) > massimo:
            via = sorted(del_ruolo, key=lambda i: _forza(v, i))[:len(del_ruolo) - massimo]
            risultato = [i for i in risultato if i not in via]
    return risultato


# ---------------------------------------------------------------- analisi completa
def _controlla_lista(v: scambi.Valori, rosa_ids: list[int], lista: list[int], chi: str, nome: str) -> None:
    if not lista:
        raise ValueError(f"Scegli almeno un giocatore da {chi}")
    if len(lista) > MAX_PER_LATO:
        raise ValueError(f"Al massimo {MAX_PER_LATO} giocatori per parte")
    if len(set(lista)) != len(lista):
        raise ValueError("Un giocatore è ripetuto: ogni giocatore può comparire una volta sola")
    if any(i not in v.info.index for i in lista):
        raise ValueError("Uno dei giocatori non è nel listone di Serie A: non si può valutare")
    if not set(lista) <= set(rosa_ids):
        raise ValueError(f"Non tutti i giocatori da {chi} sono in {nome}")


def controlla_conguaglio(conguaglio: int, mia: Squadra, loro: Squadra, lingua: str = "it") -> dict:
    """Il conguaglio in crediti (positivo = li ricevo io, negativo = li pago io) e se ci sono i fondi.
    Gli errori di input restano in italiano; `lingua` cambia solo il testo di `problema`."""
    en = lingua == EN
    if isinstance(conguaglio, bool) or not isinstance(conguaglio, int):
        raise ValueError("Il conguaglio deve essere un numero intero di crediti")
    if abs(conguaglio) > LIMITE_CREDITI:
        raise ValueError(f"Il conguaglio non può superare {LIMITE_CREDITI} crediti")
    residui = {"mio": mia.crediti_residui, "loro": loro.crediti_residui}
    dopo = {"mio": None, "loro": None}
    problema = None
    valido = True
    if conguaglio:
        paga, nome_paga, riceve = ("mio", mia.nome, "loro") if conguaglio < 0 else ("loro", loro.nome, "mio")
        x = abs(conguaglio)
        if residui[paga] is None:
            problema = (f"The remaining credits of {nome_paga} are not set in League: I cannot check that they are enough" if en
                        else f"I crediti residui di {nome_paga} non sono indicati in Lega: non posso controllare che bastino")
        elif residui[paga] < x:
            valido = False
            problema = (f"{nome_paga} has {residui[paga]} credits and cannot pay {x}" if en
                        else f"{nome_paga} ha {residui[paga]} crediti e non può pagarne {x}")
        for chi, segno in (("mio", 1 if conguaglio > 0 else -1), ("loro", -1 if conguaglio > 0 else 1)):
            if residui[chi] is not None and valido:            # chi non può pagare non va sotto zero: il «dopo» non esiste
                dopo[chi] = residui[chi] + segno * x
        if valido and residui[riceve] is not None and residui[riceve] + x > LIMITE_CREDITI:
            valido = False
            chi_riceve = mia.nome if riceve == 'mio' else loro.nome
            problema = (f"The credits of {chi_riceve} would exceed the limit of {LIMITE_CREDITI}" if en
                        else f"I crediti di {chi_riceve} supererebbero il limite di {LIMITE_CREDITI}")
    else:
        dopo = dict(residui)
    return {"crediti": conguaglio, "valido": valido, "problema": problema, "residui": residui, "dopo": dopo,
            "chi_paga": "nessuno" if not conguaglio else ("loro" if conguaglio > 0 else "tu")}


def _somme(ids: list[int], v: scambi.Valori, regole: Regole) -> dict:
    """Per le prossime giornate: punti attesi totali, della panchina, e il modulo scelto nella prima giornata."""
    totali, panca, modulo = [], 0.0, None
    for k, t in enumerate(v.per_giornata):
        d: dict = {}
        totali.append(scambi.valore_giornata(ids, t, regole, dettaglio=d))
        panca += d.get("panchina", 0.0)
        if k == 0:
            modulo = d.get("modulo")
    return {"per_giornata": totali, "breve": sum(totali), "panchina": panca, "modulo": modulo}


def _verdetto_en(netto_mio: float, netto_loro: float, valido: bool, soglia: float) -> dict:
    """Lo stesso giudizio di `_verdetto`, in inglese (stessi codici `chi`)."""
    if netto_mio >= soglia and netto_loro >= soglia:
        chi, testo = "entrambi", "Good for both of you: you can propose it with a good chance that they accept."
    elif netto_mio >= soglia:
        if netto_loro > -soglia:
            chi, testo = "te", "Good for you; little changes for them, so they may accept."
        else:
            chi, testo = "te", "Good for you but not for them: unlikely to be accepted."
    elif netto_loro >= soglia:
        if netto_mio > -soglia:
            chi, testo = "lui", "Good for them; little changes for you: your call."
        else:
            chi, testo = "lui", "Good for them and not for you: do not accept it like this."
    elif netto_mio > -soglia and netto_loro > -soglia:
        chi, testo = "poco", "Little changes for either of you: not worth it."
    else:
        chi, testo = "nessuno", "Not worth it: " + ("for neither of you." if netto_mio <= -soglia and netto_loro <= -soglia
                                                    else ("for you." if netto_mio <= -soglia else "for them."))
    if not valido:
        testo = "As it stands the trade cannot be made (the reasons are below). Looking at the points only: " + testo[0].lower() + testo[1:]
    return {"chi": chi, "testo": testo, "soglia": soglia}


def _verdetto(netto_mio: float, netto_loro: float, valido: bool, soglia: float, lingua: str = "it") -> dict:
    """Il giudizio in parole: conviene a te, a lui o a entrambi, con la stessa soglia delle proposte. Se lo scambio non si può
    fare (rose non valide, fondi che non bastano) lo dice, e il giudizio vale per i soli punti; i motivi stanno in `problemi`."""
    if lingua == EN:
        return _verdetto_en(netto_mio, netto_loro, valido, soglia)
    if netto_mio >= soglia and netto_loro >= soglia:
        chi, testo = "entrambi", "Conviene a tutti e due: puoi proporlo con buone probabilità che accetti."
    elif netto_mio >= soglia:
        if netto_loro > -soglia:
            chi, testo = "te", "Conviene a te; a lui cambia poco, quindi può anche accettare."
        else:
            chi, testo = "te", "Conviene a te ma non a lui: difficile che accetti."
    elif netto_loro >= soglia:
        if netto_mio > -soglia:
            chi, testo = "lui", "Conviene a lui; per te cambia poco: decidi tu."
        else:
            chi, testo = "lui", "Conviene a lui e non a te: non accettarlo così."
    elif netto_mio > -soglia and netto_loro > -soglia:
        chi, testo = "poco", "Cambia poco per tutti e due: non vale la pena."
    else:
        chi, testo = "nessuno", "Non conviene: " + ("a nessuno dei due." if netto_mio <= -soglia and netto_loro <= -soglia
                                                    else ("a te." if netto_mio <= -soglia else "a lui."))
    if not valido:
        testo = "Così com'è lo scambio non si può fare (i motivi sono qui sotto). Guardando solo i punti: " + testo[0].lower() + testo[1:]
    return {"chi": chi, "testo": testo, "soglia": soglia}


def analizza_completo(v: scambi.Valori, regole: Regole, rose: Rose, mia: str, altra: str, do: list[int], ricevo: list[int],
                      conguaglio: int = 0, tasso_mio: float | None = None, tasso_loro: float | None = None,
                      soglia: float = scambi.SOGLIA, lingua: str = "it") -> dict:
    """Analisi di uno scambio N contro M (1-4 per lato) con conguaglio opzionale. `tasso_*` = punti attesi in stagione per ogni
    credito, per la squadra (stima dal mercato svincolati); senza tasso i crediti sono mostrati ma non valutati.
    `lingua` ("it" o "en"): lingua di giudizio, spiegazione e motivi per cui lo scambio non si può fare (gli errori restano in italiano)."""
    sq_a, sq_b = rose.squadra(mia), rose.squadra(altra)
    if sq_a is None:
        raise ValueError(f"Squadra non trovata: {mia}")
    if sq_b is None:
        raise ValueError(f"Squadra non trovata: {altra}")
    if sq_a.nome == sq_b.nome:
        raise ValueError("Scegli un'altra squadra: non puoi scambiare con te stesso")
    a, b = scambi._ids(rose, mia), scambi._ids(rose, altra)
    do, ricevo = list(do), list(ricevo)
    _controlla_lista(v, a, do, "dare", sq_a.nome)
    _controlla_lista(v, b, ricevo, "ricevere", sq_b.nome)
    cred = controlla_conguaglio(conguaglio, sq_a, sq_b, lingua)

    a2 = [i for i in a if i not in do] + ricevo
    b2 = [i for i in b if i not in ricevo] + do
    problemi, conteggi = [], {}
    for chi, sq, via, dentro in (("mio", sq_a, do, ricevo), ("loro", sq_b, ricevo, do)):
        conteggi[chi] = _conteggio(sq, v, via, dentro)
        problemi += problemi_rosa(sq.nome, conteggi[chi], regole, lingua)
    a_val, b_val = _taglia_eccesso(a2, v, regole), _taglia_eccesso(b2, v, regole)

    prima_a, dopo_a = _somme(a, v, regole), _somme(a_val, v, regole)
    prima_b, dopo_b = _somme(b, v, regole), _somme(b_val, v, regole)
    pa = [y - x for x, y in zip(prima_a["per_giornata"], dopo_a["per_giornata"])]
    pb = [y - x for x, y in zip(prima_b["per_giornata"], dopo_b["per_giornata"])]
    s = scambi.Scambio(sq_a.nome, sq_b.nome, do, ricevo, scambi.totale(pa, v), scambi.totale(pb, v), pa, pb,
                       scambi._quot(v, do), scambi._quot(v, ricevo))
    reparti = {}
    for chi, prima, dopo in (("mio", a, a_val), ("loro", b, b_val)):
        x, y = scambi.valore_reparti(prima, v, regole), scambi.valore_reparti(dopo, v, regole)
        reparti[chi] = {r: round(100 * (y[r] - x[r]) / x[r], 1) if x[r] >= scambi.MIN_BASE else 0.0 for r in RUOLI}
    s.reparti = reparti
    pct = lambda p, d: round(100 * (d["breve"] - p["breve"]) / p["breve"], 1) if p["breve"] >= scambi.MIN_BASE else 0.0  # noqa: E731
    s.percentuale_mio = pct(prima_a, dopo_a)

    # un conguaglio che non si può fare (fondi che non bastano, crediti oltre il limite) non si valuta: niente punti inventati
    valore_cred_mio = None if tasso_mio is None or not cred["valido"] else round(conguaglio * tasso_mio, 2)
    valore_cred_loro = None if tasso_loro is None or not cred["valido"] else round(-conguaglio * tasso_loro, 2)
    netto_mio = s.guadagno_mio + (valore_cred_mio or 0.0)
    netto_loro = s.guadagno_loro + (valore_cred_loro or 0.0)
    valido = not problemi and cred["valido"]

    d = s.come_dict(v)
    r2 = lambda x: round(x, 2)  # noqa: E731
    d.update({
        "completo": True,
        "valido": valido, "problemi": [p["testo"] for p in problemi] + ([cred["problema"]] if cred["problema"] else []),
        "rose": {"mio": {"squadra": sq_a.nome, "conteggio": conteggi["mio"], "valida": not [p for p in problemi if p["squadra"] == sq_a.nome],
                         "problemi": [p["testo"] for p in problemi if p["squadra"] == sq_a.nome], "modulo": dopo_a["modulo"]},
                 "loro": {"squadra": sq_b.nome, "conteggio": conteggi["loro"], "valida": not [p for p in problemi if p["squadra"] == sq_b.nome],
                          "problemi": [p["testo"] for p in problemi if p["squadra"] == sq_b.nome], "modulo": dopo_b["modulo"]}},
        "valore_rosa": {chi: {"prima": r2(p["breve"]), "dopo": r2(q["breve"]), "variazione": r2(q["breve"] - p["breve"]),
                              "percentuale": pct(p, q)}
                        for chi, p, q in (("mio", prima_a, dopo_a), ("loro", prima_b, dopo_b))},
        "panchina": {chi: {"prima": r2(p["panchina"]), "dopo": r2(q["panchina"]), "variazione": r2(q["panchina"] - p["panchina"])}
                     for chi, p, q in (("mio", prima_a, dopo_a), ("loro", prima_b, dopo_b))},
        "conguaglio": {**cred, "tasso_mio": None if tasso_mio is None else round(tasso_mio, 4),
                       "tasso_loro": None if tasso_loro is None else round(tasso_loro, 4),
                       "valore_mio": valore_cred_mio, "valore_loro": valore_cred_loro},
        "netto_mio": r2(netto_mio), "netto_loro": r2(netto_loro),
    })
    giudizio = _verdetto(netto_mio, netto_loro, valido, soglia, lingua)
    giudizio["spiegazione"] = _spiegazione(d, sq_a.nome, sq_b.nome, conguaglio, valore_cred_mio, valore_cred_loro, tasso_mio, lingua,
                                           cred["valido"])
    d["giudizio"] = giudizio
    return d


def _spiegazione_en(d: dict, altra: str, conguaglio: int, vc_mio: float | None, tasso_mio: float | None,
                    possibile: bool = True) -> list[str]:
    segno = lambda x: f"{x:+.1f}".replace("-", "−")  # noqa: E731
    righe = [f"For you the best line-up goes from {d['valore_rosa']['mio']['prima']:.1f} to {d['valore_rosa']['mio']['dopo']:.1f} expected points "
             f"over the next {len(d['giornate'])} matchdays; with the rest of the season that is {segno(d['guadagno_mio'])} points.",
             f"For {altra}: {segno(d['guadagno_loro'])} points over the season.",
             f"Bench: you {segno(d['panchina']['mio']['variazione'])}, {altra} {segno(d['panchina']['loro']['variazione'])} expected points."]
    if conguaglio:
        verbo = "receiving" if conguaglio > 0 else "paying"
        if not possibile:
            righe.append(f"Balance: {verbo} {abs(conguaglio)} credits is not possible (see above), so it is not counted in the verdict.")
        elif vc_mio is None:
            righe.append(f"Balance: {verbo} {abs(conguaglio)} credits. I cannot estimate what they are worth in points, so they are not counted in the verdict.")
        else:
            righe.append(f"Balance: {verbo} {abs(conguaglio)} credits is worth about {segno(vc_mio)} points for you "
                         f"(estimate: on the free-agent market one credit yields about {tasso_mio:.2f} points).")
    return righe


def _spiegazione(d: dict, mia: str, altra: str, conguaglio: int, vc_mio: float | None, vc_loro: float | None,
                 tasso_mio: float | None, lingua: str = "it", possibile: bool = True) -> list[str]:
    if lingua == EN:
        return _spiegazione_en(d, altra, conguaglio, vc_mio, tasso_mio, possibile)
    segno = lambda x: f"{x:+.1f}".replace("-", "−").replace(".", ",")  # noqa: E731
    uno = lambda x: f"{x:.1f}".replace(".", ",")  # noqa: E731
    righe = [f"Per te la formazione migliore passa da {uno(d['valore_rosa']['mio']['prima'])} a {uno(d['valore_rosa']['mio']['dopo'])} punti attesi "
             f"nelle prossime {len(d['giornate'])} giornate; con il resto della stagione sono {segno(d['guadagno_mio'])} punti.",
             f"Per {altra}: {segno(d['guadagno_loro'])} punti in stagione.",
             f"Panchina: tu {segno(d['panchina']['mio']['variazione'])}, {altra} {segno(d['panchina']['loro']['variazione'])} punti attesi."]
    if conguaglio:
        verbo = "ricevere" if conguaglio > 0 else "pagare"
        if not possibile:
            righe.append(f"Conguaglio: {verbo} {abs(conguaglio)} crediti non si può (vedi sopra), quindi non lo conto nel giudizio.")
        elif vc_mio is None:
            righe.append(f"Conguaglio: {verbo} {abs(conguaglio)} crediti. Non riesco a stimare quanto valgono in punti, quindi non li conto nel giudizio.")
        else:
            righe.append(f"Conguaglio: {verbo} {abs(conguaglio)} crediti vale circa {segno(vc_mio)} punti per te "
                         f"(stima: sul mercato svincolati un credito rende circa {f'{tasso_mio:.2f}'.replace('.', ',')} punti).")
    return righe


# ---------------------------------------------------------------- tasso crediti -> punti
def tasso_da_mercato(mercato: dict) -> float | None:
    """Punti attesi in stagione per ogni credito speso, dalle migliori mosse sul mercato svincolati di una squadra
    (guadagno diviso costo, cioè quotazione di chi entra meno il rimborso di chi esce). None se non ci sono mosse utili."""
    punti = costo = 0.0
    for t in mercato.get("proposte", []):
        spesa = t["entra"]["quotazione"] - (t.get("rimborso") or 0)
        if spesa > 0 and t["guadagno"] > 0:
            punti += t["guadagno"]
            costo += spesa
    return punti / costo if costo > 0 else None


# ---------------------------------------------------------------- ricerca automatica
def formati_da_cercare(anche_due: bool = False, fino_a: int = 0) -> list[tuple[int, int]]:
    """Le misure (do, ricevo) oltre l'1 contro 1: `anche_due` = solo 2 contro 2; `fino_a` k = tutte quelle fino a k per lato."""
    if fino_a and not 2 <= fino_a <= MAX_PER_LATO:
        raise ValueError(f"fino_a deve essere un numero da 2 a {MAX_PER_LATO}")
    if fino_a:
        return [(n, m) for n in range(1, fino_a + 1) for m in range(1, fino_a + 1) if (n, m) != (1, 1)]
    return [(2, 2)] if anche_due else []


def _riempitivo(xs, ys, ga, gb, calcola, ruolo, cont_a, cont_b, regole, soglia) -> bool:
    """True se uno scambio più piccolo, ottenuto togliendo uno o due giocatori, vale quasi quanto questo: i giocatori in più sono
    solo un riempitivo (per esempio "do un attaccante e un difensore, ricevo un centrocampista e un difensore uguale") e la
    proposta più semplice è già nell'elenco."""
    ridotti = []
    if len(xs) > 1:
        ridotti += [(tuple(x for x in xs if x != tolto), ys) for tolto in xs]
    if len(ys) > 1:
        ridotti += [(xs, tuple(y for y in ys if y != tolto)) for tolto in ys]
    if len(xs) > 1 and len(ys) > 1:
        ridotti += [(tuple(x for x in xs if x != tx), tuple(y for y in ys if y != ty)) for tx in xs for ty in ys]
    for x2, y2 in ridotti:
        if not ok_dopo(cont_a, cont_b, map(ruolo, x2), map(ruolo, y2), regole):
            continue
        _, _, g1, g2 = calcola(x2, y2)
        if g1 >= soglia and g2 >= soglia and g1 + g2 >= ga + gb - soglia:
            return True
    return False


def cerca_grandi(v: scambi.Valori, regole: Regole, rose: Rose, mia: str, altra: str, a: list[int], b: list[int],
                 base_a: list[float], base_b: list[float], formati: list[tuple[int, int]],
                 singoli: dict, soglia: float, max_valutazioni: int | None = None, tempo_massimo: float = 20.0) -> list[scambi.Scambio]:
    """Scambi N contro M in cui guadagnano tutte e due le squadre (rose dopo lo scambio valide).

    Per tenere il lavoro limitato: (1) si stima l'effetto di ogni giocatore da solo (cosa perdo se lo do, cosa guadagno se lo ricevo);
    (2) per lato restano i giocatori col saldo migliore, al massimo POOL_PER_RUOLO per ruolo e pochi in tutto (POOL_PER_LATO);
    (3) le combinazioni si ordinano per il peggiore dei due guadagni stimati e si calcolano in quell'ordine fino al budget."""
    budget = MAX_VALUTAZIONI if max_valutazioni is None else max_valutazioni
    inizio = time.monotonic()
    tot = lambda pg: scambi.totale(pg, v)  # noqa: E731
    sq_a, sq_b = rose.squadra(mia), rose.squadra(altra)
    ruolo = v.ruoli.get
    a = [i for i in a if ruolo(i)]
    b = [i for i in b if ruolo(i)]

    def stima(base, mie, i, aggiungi):
        nuova = (mie + [i]) if aggiungi else [x for x in mie if x != i]
        return tot([y - x for x, y in zip(base, scambi.valore_rosa(nuova, v, regole))])

    perdo_a = {x: -stima(base_a, a, x, False) for x in a}      # quanto perde la mia rosa se do x
    prendo_a = {y: stima(base_a, a, y, True) for y in b}        # quanto guadagna se ricevo y
    perdo_b = {y: -stima(base_b, b, y, False) for y in b}
    prendo_b = {x: stima(base_b, b, x, True) for x in a}

    taglia = POOL_PER_LATO[max(2, max(max(f) for f in formati))]

    def pool(ids, saldo):
        per_ruolo: Counter = Counter()
        scelti = []
        # a parità di saldo prima i meno forti: sono i riempitivi che servono a tenere in ordine i ruoli delle rose
        for i in sorted(ids, key=lambda i: (-round(saldo[i], 6), _forza(v, i))):
            if per_ruolo[ruolo(i)] < POOL_PER_RUOLO and len(scelti) < taglia:
                per_ruolo[ruolo(i)] += 1
                scelti.append(i)
        return scelti
    pool_a = pool(a, {x: prendo_b[x] - perdo_a[x] for x in a})
    pool_b = pool(b, {y: prendo_a[y] - perdo_b[y] for y in b})

    cont_a, cont_b = _conteggio(sq_a, v, [], []), _conteggio(sq_b, v, [], [])
    # 1 contro 1 già calcolati con precisione: servono per stimare bene i cambi di pari ruolo (se do un difensore e ne ricevo
    # uno, non perdo "un titolare" e guadagno "un titolare": cambia solo la differenza tra i due)
    sa = {coppia: tot(p1) for coppia, (p1, p2) in singoli.items()}
    sb = {coppia: tot(p2) for coppia, (p1, p2) in singoli.items()}

    def stima(xs, ys):
        ea = sum(prendo_a[y] for y in ys) - sum(perdo_a[x] for x in xs)
        eb = sum(prendo_b[x] for x in xs) - sum(perdo_b[y] for y in ys)
        usati_x, usati_y = set(), set()
        for _, x, y in sorted(((sa[(x, y)] + sb[(x, y)], x, y) for x in xs for y in ys if (x, y) in sa), reverse=True):
            if x in usati_x or y in usati_y:
                continue
            usati_x.add(x)
            usati_y.add(y)
            ea += sa[(x, y)] - (prendo_a[y] - perdo_a[x])
            eb += sb[(x, y)] - (prendo_b[x] - perdo_b[y])
        return ea, eb
    candidati = []
    for n, m in formati:
        for xs in combinations(pool_a, n):
            if time.monotonic() - inizio > tempo_massimo:
                break
            for ys in combinations(pool_b, m):
                if not ok_dopo(cont_a, cont_b, map(ruolo, xs), map(ruolo, ys), regole):
                    continue
                stima_a, stima_b = stima(xs, ys)
                # se dentro c'è un 1 contro 1 già calcolato che vale quanto la stima, lo scambio grande non aggiunge nulla (e
                # sprecherebbe un calcolo del budget); il controllo preciso viene dopo
                contenuti = [sa[(x, y)] + sb[(x, y)] for x in xs for y in ys if (x, y) in sa]
                if contenuti and stima_a + stima_b <= max(contenuti):
                    continue
                candidati.append((min(stima_a, stima_b), stima_a + stima_b, xs, ys))
    candidati.sort(key=lambda c: (-c[0], -c[1]))

    def calcola(xs, ys):
        pa, pb = scambi._coppia(v, regole, a, b, base_a, base_b, xs, ys)
        return pa, pb, tot(pa), tot(pb)

    trovati = []
    for _, _, xs, ys in candidati[:budget]:
        if time.monotonic() - inizio > tempo_massimo:
            break
        pa, pb, ga, gb = calcola(xs, ys)
        if ga < soglia or gb < soglia:
            continue
        if _riempitivo(xs, ys, ga, gb, calcola, ruolo, cont_a, cont_b, regole, soglia):
            continue
        trovati.append(scambi.Scambio(sq_a.nome, sq_b.nome, list(xs), list(ys), ga, gb, pa, pb,
                                      quotazione_do=scambi._quot(v, xs), quotazione_ricevo=scambi._quot(v, ys)))
    return trovati
