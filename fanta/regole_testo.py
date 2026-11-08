"""Legge il testo del regolamento copiato da Leghe (o da un'altra piattaforma) e propone i valori per le regole dell'app.

Non conosce il formato esatto: cerca le parole chiave di ogni regola ("assist", "ammonizione", "modificatore difesa"...) e il numero
che le segue. Per questo NON applica nulla da solo: restituisce le modifiche proposte, ognuna con la riga da cui viene, e l'app le mostra
per controllarle. Nei casi dubbi (una riga con più numeri e ruoli, intervalli, negazioni) preferisce non riconoscere: le righe con numeri
non riconosciute vengono elencate, così si vede cosa manca.
"""
from __future__ import annotations

import math
import re
import unicodedata

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
MAX_CIFRE = 9                    # un valore di regola con più cifre non è un valore vero: si ignora
RUOLI = {"portier": "P", "difensor": "D", "centrocamp": "C", "attaccant": "A"}
NOMI_PLURALE = {"P": "portieri", "D": "difensori", "C": "centrocampisti", "A": "attaccanti"}
NOMI_SINGOLARE = {"P": "portiere", "D": "difensore", "C": "centrocampista", "A": "attaccante"}

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
    righe = [_normalizza(r) for r in originali]
    modifiche: dict[str, dict] = {}
    usate: set[int] = set()

    def imposta(chiave, etichetta, valore, n):
        modifiche[chiave] = {"chiave": chiave, "etichetta": etichetta, "valore": valore, "riga": originali[n][:120]}
        usate.add(n)

    in_modificatore = False
    soglie: list[list[float]] = []
    riga_soglie = 0
    for n, riga in enumerate(righe):
        # ---- modificatore difesa: titolo, "attivo", difensori minimi, fasce
        if "modificator" in riga and "difes" in riga:
            in_modificatore = True
            imposta("modificatore_difesa.attivo", "Modificatore difesa attivo",
                    not re.search(r"non attiv|disattiv|\bno\b|assent|nessun|non previst", riga), n)
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
                        soglie.append([media, abs(bonus)]); usate.add(n); riga_soglie = n; continue
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
                numero = _primo_numero(riga[riga.find("gol"):])
                if numero is not None:
                    for r in ([r for k, r in RUOLI.items() if k in riga] or ["P", "D", "C", "A"]):
                        imposta(f"bonus.gol.{r}", f"Gol ({NOMI_SINGOLARE[r]})", abs(numero), n)
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
        if re.search(r"modul|formazion", riga) and not re.search(r"non (?:sono )?(?:ammess|consent|valid)|esclus|vietat|tranne|eccetto", riga):
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
            if re.search(r"libera|senza vincol|non vincolat|nessun vincolo|qualsiasi ruolo", riga):
                imposta("panchina.tipo", "Ordine dei cambi", "libera", n)
            elif re.search(rf"per ruolo|fissa|vincolat{SUFFISSO} (?:al|dal) ruolo|ruoli? fiss", riga):
                imposta("panchina.tipo", "Ordine dei cambi", "per_ruolo", n)
        if re.search(r"sostituzion|cambi", riga) \
                and (ns := re.search(rf"(?:massim{SUFFISSO}|max|consentit{SUFFISSO}|fino a|al massimo)\D{{0,15}}(\d+)"
                                     r"|(?<!\d)(\d+)\s*(?:sostituzion|cambi)", riga)) \
                and (numero := _intero(ns.group(1) or ns.group(2))) is not None:
            imposta("panchina.max_sostituzioni", "Sostituzioni massime", numero, n)
        if re.search(r"cambio (?:di )?modulo|cambi di modulo", riga):
            imposta("panchina.cambio_modulo", "Cambio modulo nelle sostituzioni",
                    not re.search(r"non (?:consent|ammess)|\bno\b|disattiv|vietat", riga), n)
        if re.search(r"credit", riga) and re.search(r"inizial|a disposizione|parte con|budget", riga) and not re.search(r"residu|giornata|speso", riga) \
                and (nc := re.search(r"\d+", riga)) and (numero := _intero(nc.group())) is not None:
            imposta("crediti_iniziali", "Crediti iniziali", numero, n)
        if (rr := re.search(RUOLO_ROSA, riga)) and n not in usate \
                and not re.search(r"gol|assist|bonus|malus|voto|modificat|media", riga):
            r = next(v for k, v in RUOLI.items() if k in rr.group(1))
            imposta(f"rosa.{r}", f"Rosa: {NOMI_PLURALE[r]}", int(rr.group(2)), n)
    if soglie:
        modifiche["modificatore_difesa.soglie"] = {"chiave": "modificatore_difesa.soglie", "etichetta": "Fasce del modificatore difesa",
                                                   "valore": sorted(soglie), "riga": originali[riga_soglie][:120]}
        modifiche.setdefault("modificatore_difesa.attivo", {"chiave": "modificatore_difesa.attivo", "etichetta": "Modificatore difesa attivo",
                                                           "valore": True, "riga": originali[riga_soglie][:120]})
    non = [originali[n] for n in range(len(righe)) if n not in usate and re.search(r"\d", righe[n]) and len(righe[n]) < 140]
    return {"modifiche": list(modifiche.values()), "non_riconosciute": non[:30]}
