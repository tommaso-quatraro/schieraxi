"""Legge il testo del regolamento copiato da Leghe (o da un'altra piattaforma) e propone i valori per le regole dell'app.

Non conosce il formato esatto: cerca le parole chiave di ogni regola ("assist", "ammonizione", "modificatore difesa"...) e il numero
che le segue. Per questo NON applica nulla da solo: restituisce le modifiche proposte, ognuna con la riga da cui viene, e l'app le mostra
per controllarle. Nei casi dubbi (una riga con più numeri e ruoli, intervalli, negazioni) preferisce non riconoscere: le righe con numeri
non riconosciute vengono elencate, così si vede cosa manca. `da_controllare` le mette insieme alle righe dubbie, anche senza numeri
(nominano il cambio modulo, il modificatore della difesa o il tipo di panchina senza dirne il valore con sicurezza), nell'ordine del
testo e con le regole da impostare a mano.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable

# Tetti del testo incollato: un regolamento vero ha poche migliaia di caratteri e righe corte (una regola per riga).
MAX_TESTO = 30_000
MAX_RIGA = 2_000
# Le espressioni restano in tempo lineare con qualsiasi testo: nessuna parte facoltativa che può cominciare in molti punti di
# una stessa fila di spazi o di cifre, e le parole dopo una radice («portier…», «rigor…») hanno una lunghezza massima.
# Un numero, con il segno se c'è (anche staccato da spazi): gli spazi davanti al numero non fanno parte del numero.
NUM = r"(?:[+\-−–]\s*)?\d+(?:[.,]\d+)?"
SUFFISSO = r"\w{0,20}"           # il resto di una parola dopo la radice: «portier» + «i»
RUOLO_ROSA = (rf"(portier{SUFFISSO}|difensor{SUFFISSO}|centrocamp{SUFFISSO}|attaccant{SUFFISSO})"
              r"\s*(?:[:=]\s*)?(\d{1,2})\b")
# La rosa scritta al contrario, il numero prima del ruolo («composta da 3 portieri, 8 difensori…»): si legge solo in una riga che
# parla della rosa (ROSA_FRASE), perché altrove «4 difensori» è altro (il modificatore, la panchina, un modulo).
NUMERO_RUOLO_ROSA = rf"\b(\d{{1,2}})\s(portier{SUFFISSO}|difensor{SUFFISSO}|centrocamp{SUFFISSO}|attaccant{SUFFISSO})"
ROSA_FRASE = r"\brosa\b|compost"
# I numeri di un titolo non sono valori di regola: l'articolo o il capitolo («ART. 2 - PUNTEGGI», «Capitolo 1»), il numero
# dell'elenco in testa alla riga («2) Rosa», «3. Panchina») e la stagione («2026/27», «2026-2027»). Si tolgono prima di leggere:
# un titolo resta senza numeri e non va fra le righe da controllare.
NUMERO_TITOLO = (r"\b(?:art|articolo|capitolo|cap|sezione|sez|paragrafo)\b\.?\s{0,3}\d{1,3}(?:\.\d{1,3}){0,3}\b"
                 r"|^\W{0,5}\d{1,2}(?:\.\d{1,2}){0,3}[.)](?=\s)"
                 r"|\b(?:(?:stagione|campionato)\s)?(?:19|20)\d\d\s{0,3}[/-]\s{0,3}(?:(?:19|20)\d\d|\d\d)\b"
                 r"|\b(?:stagione|campionato)\s(?:19|20)\d\d\b")
# I moduli («3-4-3», «343» in una riga di moduli) non sono numeri da leggere uno per uno (righe lette in parte, _numeri_da_leggere)
MODULO = r"\b[2-5]\s*-\s*[1-6]\s*-\s*[0-6]\b"
MODULO_UNITO = r"\b[2-5][1-6][0-6]\b"
MAX_CIFRE = 9                    # un valore di regola con più cifre non è un valore vero: si ignora
RUOLI = {"portier": "P", "difensor": "D", "centrocamp": "C", "attaccant": "A"}
NOMI_PLURALE = {"P": "portieri", "D": "difensori", "C": "centrocampisti", "A": "attaccanti"}
NOMI_SINGOLARE = {"P": "portiere", "D": "difensore", "C": "centrocampista", "A": "attaccante"}

# Negazioni. Un «non» nega le parole che lo seguono quando in mezzo ci sono solo parole di passaggio: «non è consentito»,
# «non sono mai stati previsti», «non si può», «non è, in nessun caso, ammesso». Tutto in tempo lineare: tratti brevi e limitati.
PASSAGGIO = (r"e|sono|viene|vengono|verra|verranno|sara|saranno|risulta|risultano|essere|stato|stata|stati|state|mai|piu"
             r"|ancora|affatto|assolutamente|in|alcun|alcuna|nessun|modo|caso|si|ci|lo|la|li|le|il|i|gli|un|una|ne"
             r"|puo|possono|potra")
SEP = r"[\s',]{1,4}"
# Le parole che dicono se una regola sì/no c'è: il loro «non» la spegne.
STATO_CAMBIO_MODULO = (r"consent|ammess|ammett|permess|permett|possibil|previst|utilizz|abilitat|attiv|applic|concess|valid"
                       r"|puo|us(?:a|o|at)")
STATO_MODIFICATORE = (r"attiv|previst|utilizz|applic|abilitat|consent|ammess|valid|vigore|present|esist|c'e"
                      r"|us(?:a|o|at)")
# Le parole che dicono «no» da sole. «Non è vietato» (un no negato) è dubbio: si lascia da controllare.
# «Nessun» dice no solo subito prima del nome della regola («Nessun cambio modulo», «nessun modificatore»), in «in nessun caso»
# e da solo alla fine («Cambio modulo: nessuno»). Dentro una condizione vale come un «non» (_senza_condizione); altrove non si
# sa a cosa risponda («nessun divieto», «nessun limite» vogliono dire sì): la lettura è dubbia (_detto).
NESSUN = r"\bnessun[oa]?\b"
NESSUN_NO = r"\bin\s+nessun\s+caso\b|\bnessun[oa]\W*$"
NESSUN_DICE_NO = rf"\bnessun[oa]?\s+(?:cambi|modificator)|{NESSUN_NO}"     # i «nessun» che dicono no; un altro rende dubbio
NO_CAMBIO_MODULO = rf"\bno\b|\boff\b|disattiv|disabilit|vietat|\bnessun[oa]?\s+cambi|{NESSUN_NO}"
NO_MODIFICATORE = rf"\bno\b|\boff\b|disattiv|disabilit|vietat|assent|\bnessun[oa]?\s+modificator|{NESSUN_NO}"
NO_NEGATO = r"vietat|disattiv|disabilit"
# Da «se», «quando»... alla fine del pezzo c'è una condizione: un suo «non» («cambio modulo quando non è possibile sostituire
# nel ruolo») dice quando scatta la regola, non la spegne (regole_testo._senza_condizione).
CONDIZIONE = r"\b(?:se|quando|qualora|purche|in caso|nel caso|a meno che|salvo che|ogni volta che)\b"
# «se non» come «tranne» («non è consentito se non quando manca un sostituto»): la regola vale solo in parte, non si propone
SE_NON_TRANNE = rf"\bse{SEP}non{SEP}(?:quando|qualora|in|nel|nei|per|dopo|con)\b"
CAMBIO_MODULO = r"cambio (?:di )?modulo|cambi di modulo"
# Anche al plurale («Riserve libere», «riserve fisse»); «liberamente» non è «libera»
PANCHINA_LIBERA = r"\bliber[ae]\b|senza vincol|nessun vincolo|qualsiasi ruolo"
PANCHINA_PER_RUOLO = rf"per ruolo|fiss[ae]|vincolat{SUFFISSO} (?:al|dal) ruolo|ruoli? fiss"
NIENTE = "niente"                        # un pezzo di riga che nomina una regola sì/no senza dire se c'è
MAX_DUBBIE = 30                          # righe dubbie in «da_controllare» oltre a quelle con numeri non lette (anche loro 30)

# (chiave, etichetta, schemi, segno) in ordine: le regole più specifiche prima. segno: +1 bonus, -1 malus.
BONUS = [
    ("bonus.rigore_parato", "Rigore parato", [rf"rigor{SUFFISSO} parat"], 1),
    ("bonus.rigore_sbagliato", "Rigore sbagliato", [rf"rigor{SUFFISSO} (?:sbagliat|fallit|non realizzat|non segnat)", r"errore dal dischetto"], -1),
    ("bonus.rigore_segnato", "Rigore segnato", [rf"rigor{SUFFISSO} (?:segnat|realizzat|trasformat)", r"gol (?:su|da) rigore"], 1),
    ("bonus.autogol", "Autogol", [r"autogol", r"autorete"], -1),
    ("bonus.portiere_imbattuto", "Portiere imbattuto", [r"imbattut", r"porta inviolata", r"clean sheet", r"nessun gol subit", r"senza subire"], 1),
    ("bonus.gol_subito_portiere", "Gol subito (portiere)", [r"gol subit", r"reti subit"], -1),
    ("bonus.assist", "Assist", [r"\bassist(?!enza)"], 1),
    ("bonus.ammonizione", "Ammonizione", [r"ammonizion", r"cartellino giallo", r"\bgiallo\b"], -1),
    ("bonus.espulsione", "Espulsione", [r"espulsion", r"cartellino rosso", r"\brosso\b"], -1),
    ("bonus.mvp", "Migliore in campo", [r"migliore in campo", r"\bmvp\b", r"man of the match"], 1),
]


def _normalizza(testo: str) -> str:
    t = unicodedata.normalize("NFKD", testo.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.replace("’", "'").replace("−", "-").replace("–", "-")


def _numero(s: str) -> float:
    return float(re.sub(r"\s", "", s).replace(",", "."))


def _valore(s: str) -> float | None:
    """Il numero trovato, se è un valore possibile per una regola (non infinito, non lungo come un numero di telefono)."""
    if len(re.sub(r"\D", "", s)) > MAX_CIFRE:
        return None
    v = _numero(s)
    return v if math.isfinite(v) else None


def _intero(s: str | None) -> int | None:
    return int(s) if s is not None and len(s) <= MAX_CIFRE else None


def _primo_numero(testo: str) -> float | None:
    m = re.search(NUM, testo)
    return _valore(m.group()) if m else None


def _numeri(testo: str, da: int = 0) -> list[tuple[int, float]]:
    """I numeri che possono essere valori di regola, con la loro posizione nel testo (da `da` in poi)."""
    return [(m.start(), v) for m in re.compile(NUM).finditer(testo, da) if (v := _valore(m.group())) is not None]


def _arrotonda(v: float) -> float:
    return round(abs(v), 3)


def _numeri_da_leggere(riga: str) -> set[float]:
    """I numeri della riga (già senza i numeri del titolo) che una regola dovrebbe aver letto: senza i moduli e senza segno."""
    testo = re.sub(MODULO, " ", riga)
    if re.search(r"modul|formazion", testo):
        testo = re.sub(MODULO_UNITO, " ", testo)
    return {_arrotonda(v) for _, v in _numeri(testo)}


def _letti(valore) -> set[float]:
    """I numeri del testo che un valore proposto ha letto (un sì/no e i moduli nessuno; i posti per ruolo uno per ruolo)."""
    if isinstance(valore, bool) or isinstance(valore, str):
        return set()
    if isinstance(valore, (int, float)):
        return {_arrotonda(valore)}
    if isinstance(valore, dict):
        return {_arrotonda(v) for v in valore.values()}
    return set()


def _negate(testo: str, parole: str) -> tuple[int, int]:
    """Quante volte le parole compaiono nel testo e quante di queste sono negate da un «non» (vedi PASSAGGIO)."""
    parola = re.compile(rf"\b(?:{parole})")
    tutte = {m.start() for m in parola.finditer(testo)}
    negate: set[int] = set()
    for m in re.finditer(rf"\bnon(?:{SEP}(?:(?:{PASSAGGIO})\b|(?:{parole})\w{{0,20}})){{0,5}}", testo):
        negate |= {p.start() for p in parola.finditer(testo, m.start(), m.end())}
    return len(tutte), len(negate & tutte)


def _si_no(riga: str, soggetto: Callable[[str], bool], stato: str, no: str) -> bool | None:
    """Valore di una regola sì/no (cambio modulo, modificatore difesa), None se la riga è dubbia e quindi non si riconosce.

    Conta il pezzo della riga (fra virgole, punti, punti e virgola, parentesi) che nomina la regola, così un «non» detto di
    altro («non sono consentite più di 3 sostituzioni, cambio modulo consentito») non la spegne; e del pezzo non conta la
    condizione con un «non» (`_senza_condizione`). Se quel pezzo dice solo il nome, decidono i pezzi fatti solo di un sì o di
    un no («Modificatore difesa, non attivo»); se non ce ne sono, il nome da solo vale sì, come un titolo («Modificatore
    difesa»). Dubbi: un «sì» e un «non» per la stessa regola, o un «non» senza la parola che nega.
    """
    if re.search(SE_NON_TRANNE, riga):
        return None
    pezzi = re.split(r"[,;.()]", riga)
    valori = {_detto(_senza_condizione(p, soggetto, no), stato, no) for p in ([p for p in pezzi if soggetto(p)] or [riga])}
    valori.discard(NIENTE)
    if not valori:
        predicato = rf"\W*(?:non(?:{SEP}(?:{PASSAGGIO})\b){{0,5}}{SEP})?(?:{stato}|{no})\w{{0,20}}\W*"
        valori = {_detto(p, stato, no) for p in pezzi if re.fullmatch(predicato, p)} or {True}
    return valori.pop() if len(valori) == 1 else None


def _senza_condizione(pezzo: str, soggetto: Callable[[str], bool], no: str) -> str | None:
    """Il pezzo senza la condizione, da «se», «quando»... alla fine, quando c'entra un «non». Un «non» nella condizione, a
    qualsiasi distanza, dice quando scatta la regola («il cambio modulo avviene quando il titolare non può essere sostituito»:
    conta «il cambio modulo avviene»). None, dubbio: un «non» prima della condizione (un no che vale solo in quel caso: «non
    si applica se il portiere non gioca»), la regola dentro la condizione («in caso di cambio modulo non sono consentite più di
    3 sostituzioni») o un «no» nella condizione («si applica se...? No»). Senza «non» il pezzo si legge tutto, come sempre.
    «Nessun» vale come «non»: prima della condizione è un no che vale solo in quel caso, dentro dice quando scatta la regola
    («il cambio modulo avviene quando nessun giocatore della panchina può sostituire il titolare»)."""
    m = re.search(CONDIZIONE, pezzo)
    if not m:
        return pezzo
    prima, condizione = pezzo[:m.start()], pezzo[m.start():]
    if re.search(rf"\bnon\b|{NESSUN}", prima):
        return None
    if not re.search(rf"\bnon\b|{NESSUN}", condizione):
        return pezzo
    return prima if soggetto(prima) and not re.search(no, re.sub(NESSUN, " ", condizione)) else None


def _detto(testo: str | None, stato: str, no: str) -> bool | None | str:
    """Cosa dice il testo della regola: True, False, None se è dubbio, NIENTE se non dice niente."""
    if testo is None or _negate(testo, NO_NEGATO)[1]:               # «non è vietato»: un no negato
        return None
    tutte, negate = _negate(testo, stato)
    if negate:
        return False if negate == tutte else None
    if re.search(no, re.sub(NESSUN, " ", testo)):
        return False                        # un no detto senza «nessun»: «vietato», «assente», «no» (anche «…, nessuna eccezione»)
    if re.search(NESSUN, re.sub(NESSUN_DICE_NO, " ", testo)):
        return None                         # un «nessun» che non dice no («nessun divieto», «con nessun difensore»): dubbio
    if re.search(no, testo):
        return False
    if tutte:
        return True
    return None if re.search(r"\bnon\b", testo) else NIENTE


def _tipo_panchina(riga: str) -> str | None:
    """«libera», «per_ruolo», None se la riga è dubbia, NIENTE se non dice il tipo. «non (è) vincolata» vuol dire libera; un
    tipo negato («non libera», «non è fissa») vale solo se la riga dice l'altro («riserve non libere: entrano per ruolo»),
    altrimenti è dubbia. Dubbia anche una riga che dice tutti e due i tipi o che ha un «no» («Panchina libera: no»)."""
    testo = re.sub(rf"\bnon(?:{SEP}(?:{PASSAGGIO})\b){{0,4}}{SEP}vincolat{SUFFISSO}", "libera", riga)
    libera, per_ruolo = re.search(PANCHINA_LIBERA, testo), re.search(PANCHINA_PER_RUOLO, testo)
    libera_negata = _negate(testo, r"liber|qualsiasi ruolo")[1]
    ruolo_negato = _negate(testo, r"per ruolo|fiss|vincolat")[1]
    if not (libera or per_ruolo or libera_negata or ruolo_negato):
        return NIENTE
    if re.search(r"\bno\b|\boff\b", riga):
        return None
    if libera_negata or ruolo_negato:
        if libera_negata and not ruolo_negato and per_ruolo:
            return "per_ruolo"
        if ruolo_negato and not libera_negata and libera:
            return "libera"
        return None
    if libera and per_ruolo:
        return None
    return "libera" if libera else "per_ruolo" if per_ruolo else None


class TestoTroppoLungo(ValueError):
    """Il regolamento incollato supera i tetti: il messaggio è una frase per chi usa l'app (il server risponde 422)."""
    stato = 422


def controlla_lunghezza(testo: str) -> None:
    """Errore chiaro se il testo o una sua riga superano i tetti (MAX_TESTO, MAX_RIGA)."""
    if len(testo) > MAX_TESTO:
        raise TestoTroppoLungo(f"Il regolamento è troppo lungo (al massimo {MAX_TESTO // 1000} mila caratteri): "
                               "incolla solo la parte con bonus, malus, moduli e panchina.")
    if any(len(r.strip()) > MAX_RIGA for r in re.split(r"[\r\n]+", testo)):
        raise TestoTroppoLungo(f"Una riga del regolamento è troppo lunga (al massimo {MAX_RIGA} caratteri): "
                               "vai a capo tra una regola e l'altra.")


def interpreta(testo: str) -> dict:
    controlla_lunghezza(testo)
    originali = [r.strip() for r in re.split(r"[\r\n]+", testo) if r.strip()]
    righe = [re.sub(NUMERO_TITOLO, " ", _normalizza(r)) for r in originali]      # senza il numero dell'articolo e la stagione
    modifiche: dict[str, dict] = {}
    usate: set[int] = set()
    letti: dict[int, set[float]] = {}    # riga -> i numeri letti dalle regole (gli altri la lasciano da controllare)
    dubbie: dict[int, list[dict]] = {}   # riga -> regole che nomina senza dirne il valore con sicurezza

    def imposta(chiave, etichetta, valore, n):
        modifiche[chiave] = {"chiave": chiave, "etichetta": etichetta, "valore": valore, "riga": originali[n][:120]}
        usate.add(n)
        letti.setdefault(n, set()).update(_letti(valore))

    def dubbia(chiave, etichetta, n):           # chiave ed etichetta come in imposta (tests/test_frasi.py le legge da qui)
        dubbie.setdefault(n, []).append({"chiave": chiave, "etichetta": etichetta})

    in_modificatore = False
    soglie: list[list[float]] = []
    riga_soglie = 0
    for n, riga in enumerate(righe):
        # ---- modificatore difesa: titolo, "attivo", difensori minimi, fasce
        if "modificator" in riga and "difes" in riga:
            in_modificatore = True
            attivo = _si_no(riga, lambda p: "modificator" in p and "difes" in p, STATO_MODIFICATORE, NO_MODIFICATORE)
            if attivo is None:
                dubbia("modificatore_difesa.attivo", "Modificatore difesa attivo", n)
            else:
                imposta("modificatore_difesa.attivo", "Modificatore difesa attivo", attivo, n)
            continue
        if in_modificatore:
            m = re.search(rf"difensor{SUFFISSO}\s*(?:minim{SUFFISSO}|almeno)\D{{0,6}}\b([3-6])\b(?![.,]\d)"
                          rf"|(?:almeno|minim{SUFFISSO})\s*\b([3-6])\b(?![.,]\d)\s*difensor", riga)
            if m:
                imposta("modificatore_difesa.min_difensori", "Difensori minimi", int(m.group(1) or m.group(2)), n)
                continue
            # una fascia è "media <numero> : bonus <numero>"; gli intervalli ("6-6,5", "da 6 a 6,49") non sono letti per non sbagliare
            if not re.search(r"\d\s*[-a]\s*\d|\bda\b[^\n]{0,40}\ba\b", riga):
                numeri = re.findall(NUM, riga)
                if len(numeri) == 2 and re.search(r"[:=→>+]|bonus|punt", riga):
                    media, bonus = _valore(numeri[0]), _valore(numeri[1])
                    if media is not None and bonus is not None and 3.5 <= media <= 9 and 0 <= abs(bonus) <= 10 and "difensor" not in riga:
                        soglie.append([media, abs(bonus)]); usate.add(n); riga_soglie = n
                        letti.setdefault(n, set()).update({_arrotonda(media), _arrotonda(bonus)})
                        continue
            if re.search(r"(?:pareggi|moduli|panchina|bonus e malus|punteggi|capitano)", riga):
                in_modificatore = False
        # ---- gol: un numero per ruolo se la riga elenca più ruoli, altrimenti uguale per tutti
        trovato = False
        if re.search(r"\bgol\b", riga) and not re.search(r"gol subit|reti subit|gol (?:su|da) rigore|nessun gol|assist|rigor", riga):
            ruoli_riga = [(r, riga.find(k)) for k, r in RUOLI.items() if k in riga]
            if len(ruoli_riga) >= 2:
                for r, pos in sorted(ruoli_riga, key=lambda x: x[1]):
                    numero = _primo_numero(riga[pos:])
                    if numero is not None:
                        imposta(f"bonus.gol.{r}", f"Gol ({NOMI_SINGOLARE[r]})", abs(numero), n); trovato = True
            elif re.search(rf"\bgol\b.{{0,40}}(?:segnat|realizzat|fatt)|\bgol\b\s*(?:[:=]|$|\d|[+-])|(?:segnat|realizzat){SUFFISSO} gol"
                           r"|\bgol\b\W+(?:\w+\W+){0,2}(?:portier|difensor|centrocamp|attaccant)", riga):
                numeri = _numeri(riga, riga.find("gol"))
                if numeri and ruoli_riga:
                    r, pos = ruoli_riga[0]
                    prima, dopo = [v for p, v in numeri if p < pos], [v for p, v in numeri if p > pos]
                    if prima and dopo:
                        # «Gol: +3 (il gol del portiere vale +5)»: il primo numero vale per tutti i ruoli, quello dopo il ruolo
                        # citato solo per lui (#881)
                        for x in RUOLI.values():
                            imposta(f"bonus.gol.{x}", f"Gol ({NOMI_SINGOLARE[x]})", abs(dopo[0] if x == r else prima[0]), n)
                    elif len(prima) < 2:
                        imposta(f"bonus.gol.{r}", f"Gol ({NOMI_SINGOLARE[r]})", abs(numeri[0][1]), n)
                    # due numeri prima del ruolo («3 punti, 5 per il portiere»): non si sa quale sia il suo, la riga resta da controllare
                    trovato = True
                elif numeri:
                    for r in RUOLI.values():
                        imposta(f"bonus.gol.{r}", f"Gol ({NOMI_SINGOLARE[r]})", abs(numeri[0][1]), n)
                    trovato = True
        if not trovato:
            for chiave, etichetta, schemi, segno in BONUS:
                posizioni = [m.start() for s in schemi if (m := re.search(s, riga))]
                if posizioni:
                    numero = _primo_numero(riga[min(posizioni):])
                    if numero is not None:
                        imposta(chiave, etichetta, segno * abs(numero), n); trovato = True
                    break
        if trovato:
            continue
        # ---- moduli, panchina, rosa, crediti
        # un «non», un «no» o un «salvo» in una riga di moduli può togliere un modulo dall'elenco («il 5-4-1 non è ammesso»,
        # «no 5-4-1»): la riga resta da controllare
        if re.search(r"modul|formazion", riga) \
                and not re.search(r"\bnon?\b|esclus|vietat|tranne|eccetto|\bsalvo\b|eccezion|\bmeno\b|\bsenza\b", riga):
            trovati = {f"{a}-{b}-{c}" for a, b, c in re.findall(r"\b([2-5])\s*-\s*([1-6])\s*-\s*([0-6])\b", riga)}
            trovati |= {f"{t[0]}-{t[1]}-{t[2]}" for t in re.findall(r"\b([2-5][1-6][0-6])\b", riga)}
            trovati = {m for m in trovati if sum(map(int, m.split("-"))) == 10}
            if trovati:
                precedenti = modifiche.get("moduli", {"valore": []})["valore"]
                imposta("moduli", "Moduli ammessi", sorted(set(precedenti) | trovati), n)
        if re.search(r"panchin|riserv", riga):
            # posti per ruolo: "2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti"
            posti = {}
            for k, r in RUOLI.items():
                if (mp := re.search(r"\b(\d{1,2})\s*" + k, riga)):
                    posti[r] = int(mp.group(1))
            if len(posti) == 4:
                imposta("panchina.posti", "Posti in panchina per ruolo", posti, n)
                imposta("panchina.numero", "Giocatori in panchina", sum(posti.values()), n)
                continue
            if (nm := re.search(rf"(?:panchin{SUFFISSO}|riserv{SUFFISSO})\D{{0,25}}(\d+)|(?<!\d)(\d+)\s*(?:panchin|riserv)", riga)) \
                    and (numero := _intero(nm.group(1) or nm.group(2))) is not None:
                imposta("panchina.numero", "Giocatori in panchina", numero, n)
            tipo = _tipo_panchina(riga)
            if tipo is None:
                dubbia("panchina.tipo", "Ordine dei cambi", n)
            elif tipo != NIENTE:
                imposta("panchina.tipo", "Ordine dei cambi", tipo, n)
        if re.search(r"sostituzion|cambi", riga) \
                and (ns := re.search(rf"(?:massim{SUFFISSO}|max|consentit{SUFFISSO}|fino a|al massimo)\D{{0,15}}(\d+)"
                                     r"|(?<!\d)(\d+)\s*(?:sostituzion|cambi)", riga)) \
                and (numero := _intero(ns.group(1) or ns.group(2))) is not None:
            imposta("panchina.max_sostituzioni", "Sostituzioni massime", numero, n)
        if re.search(CAMBIO_MODULO, riga):
            cambio = _si_no(riga, lambda p: re.search(CAMBIO_MODULO, p) is not None, STATO_CAMBIO_MODULO, NO_CAMBIO_MODULO)
            if cambio is None:
                dubbia("panchina.cambio_modulo", "Cambio modulo nelle sostituzioni", n)
            else:
                imposta("panchina.cambio_modulo", "Cambio modulo nelle sostituzioni", cambio, n)
        if re.search(r"credit", riga) and re.search(r"inizial|a disposizione|parte con|budget", riga) and not re.search(r"residu|giornata|speso", riga) \
                and (nc := re.search(r"\d+", riga)) and (numero := _intero(nc.group())) is not None:
            imposta("crediti_iniziali", "Crediti iniziali", numero, n)
        if n not in usate and not re.search(r"gol|assist|bonus|malus|voto|modificat|media", riga):
            # tutti i ruoli della riga («Rosa: portieri 3, difensori 9, …», #881); lo stesso ruolo con due numeri resta da controllare
            coppie = [(m.group(1), m.group(2)) for m in re.finditer(RUOLO_ROSA, riga)]
            if not coppie and re.search(ROSA_FRASE, riga):
                coppie = [(m.group(2), m.group(1)) for m in re.finditer(NUMERO_RUOLO_ROSA, riga)]
            rosa: dict[str, set[int]] = {}
            for parola, numero in coppie:
                rosa.setdefault(next(v for k, v in RUOLI.items() if k in parola), set()).add(int(numero))
            if all(len(numeri_ruolo) == 1 for numeri_ruolo in rosa.values()):
                for r in RUOLI.values():
                    if r in rosa:
                        imposta(f"rosa.{r}", f"Rosa: {NOMI_PLURALE[r]}", rosa[r].pop(), n)
    if soglie:
        modifiche["modificatore_difesa.soglie"] = {"chiave": "modificatore_difesa.soglie", "etichetta": "Fasce del modificatore difesa",
                                                   "valore": sorted(soglie), "riga": originali[riga_soglie][:120]}
        modifiche.setdefault("modificatore_difesa.attivo", {"chiave": "modificatore_difesa.attivo", "etichetta": "Modificatore difesa attivo",
                                                           "valore": True, "riga": originali[riga_soglie][:120]})
    def con_numeri_non_letti(n: int) -> bool:
        """La riga ha numeri che nessuna regola ha letto: tutti (riga non usata) o solo una parte (#881: «Assist: +1 (assist da
        fermo +0,5)» propone l'assist, ma lo 0,5 va guardato a mano)."""
        if n not in usate:
            return re.search(r"\d", righe[n]) is not None
        return not _numeri_da_leggere(righe[n]) <= letti.get(n, set())

    non = [n for n in range(len(righe)) if len(righe[n]) < 140 and con_numeri_non_letti(n)][:30]
    # da controllare a mano (#684): le righe con numeri non lette e quelle dubbie, anche senza numeri, nell'ordine del testo;
    # ognuna con le regole che lascia da impostare (vuoto per una riga con numeri che non nomina regole dubbie)
    altre = [n for n in sorted(dubbie) if n not in non][:MAX_DUBBIE]
    return {"modifiche": list(modifiche.values()), "non_riconosciute": [originali[n] for n in non],
            "da_controllare": [{"riga": originali[n], "regole": dubbie.get(n, [])} for n in sorted({*non, *altre})]}
