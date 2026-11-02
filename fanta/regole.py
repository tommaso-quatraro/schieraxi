"""Regole della lega (classic), tutte parametriche.

I valori predefiniti sono quelli tipici di Leghe Fantacalcio classic: vanno adattati alla propria lega
con il comando `regole --imposta` (o, più avanti, dall'app). Si salvano in lega/regole.json.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, get_type_hints

from .percorsi import scrivi_sicuro

RUOLI = ("P", "D", "C", "A")
FONTI_VOTO = ("redazione", "statistico", "italia")
GIORNATE_SERIE_A = 38
MAX_SCADENZA_MINUTI = 720          # al massimo 12 ore prima
MAX_MODULI = 30                    # tetti contro regole esagerate (rallentano i calcoli o li fanno fallire)
MAX_ROSA_PER_RUOLO = 30
MAX_SOSTITUZIONI = 10


@dataclass
class Bonus:
    gol: dict[str, float] = field(default_factory=lambda: {"P": 3.0, "D": 3.0, "C": 3.0, "A": 3.0})
    rigore_segnato: float = 3.0
    assist: float = 1.0
    rigore_parato: float = 3.0
    rigore_sbagliato: float = -1.0
    autogol: float = -2.0
    gol_subito_portiere: float = -1.0
    portiere_imbattuto: float = 1.0
    ammonizione: float = -0.5
    espulsione: float = -1.0
    mvp: float = 0.0


@dataclass
class Panchina:
    numero: int = 7
    tipo: str = "libera"            # "libera" oppure "per_ruolo"
    max_sostituzioni: int = 3
    cambio_modulo: bool = True      # le sostituzioni possono cambiare modulo (purché ammesso)
    # Posti fissi per ruolo (es. {"P": 2, "D": 3, "C": 3, "A": 3} = 11 in panchina). Con i posti indicati la panchina ha
    # esattamente quei posti per ruolo e "numero" deve essere la loro somma; None = nessun vincolo di ruolo.
    posti: dict[str, int] | None = None


@dataclass
class ModificatoreDifesa:
    attivo: bool = False
    min_difensori: int = 4
    # [media minima, bonus]: si applica il bonus della soglia più alta raggiunta.
    # La media è di portiere + i 3 migliori difensori.
    soglie: list[list[float]] = field(default_factory=lambda: [[6.0, 1.0], [6.5, 3.0], [7.0, 6.0]])


@dataclass
class Regole:
    nome_lega: str = "La mia lega"
    fonte_voto: str = "redazione"
    bonus: Bonus = field(default_factory=Bonus)
    rosa: dict[str, int] = field(default_factory=lambda: {"P": 3, "D": 8, "C": 8, "A": 6})
    crediti_iniziali: int = 500
    rimborso_svincolo: float = 0.5          # quota del prezzo pagato che si riavrebbe svincolando un giocatore (0,5 = metà)
    moduli: list[str] = field(default_factory=lambda: ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"])
    panchina: Panchina = field(default_factory=Panchina)
    modificatore_difesa: ModificatoreDifesa = field(default_factory=ModificatoreDifesa)
    voto_senza_sostituto: float | None = None   # None = conta zero; es. 4 per il "voto d'ufficio"
    # Partite testa a testa (servono per le simulazioni, non per scegliere la formazione)
    fattore_campo: float = 0.0
    soglia_primo_gol: float = 66.0
    ampiezza_fascia_gol: float = 6.0
    # Tempi della lega. `scadenza_minuti`: la formazione si chiude tanti minuti PRIMA della prima partita della giornata (0 = proprio
    # all'inizio). `prima_giornata_lega`: la giornata di Serie A da cui parte la lega (1 = dall'inizio; se la lega è nata dopo, per
    # esempio con un'asta a mercato chiuso, è quella della sua prima giornata). Prima di allora per la lega non esiste nulla.
    scadenza_minuti: int = 0
    prima_giornata_lega: int = 1
    # Aggiornamenti più fitti di probabili e infortuni a 60, 30 e 15 minuti dalla scadenza (pianificatore.py). Interruttore per lega.
    aggiornamenti_vicino_scadenza: bool = True

    # ---- controlli ----
    def problemi(self) -> list[str]:
        p = self._problemi_di_tipo()
        if p:  # con tipi sbagliati gli altri controlli non hanno senso
            return p
        if self.fonte_voto not in FONTI_VOTO:
            p.append(f"fonte_voto deve essere una di {FONTI_VOTO}")
        if set(self.bonus.gol) != set(RUOLI):
            p.append("bonus.gol deve avere un valore per ogni ruolo P, D, C, A")
        if set(self.rosa) != set(RUOLI) or any(v < 1 for v in self.rosa.values()):
            p.append("rosa deve indicare quanti P, D, C, A (almeno 1 ciascuno)")
        if any(v > MAX_ROSA_PER_RUOLO for v in self.rosa.values()):
            p.append(f"rosa: al massimo {MAX_ROSA_PER_RUOLO} giocatori per ruolo")
        if not self.moduli:
            p.append("serve almeno un modulo")
        if len(self.moduli) > MAX_MODULI:
            p.append(f"al massimo {MAX_MODULI} moduli")
        if len(set(self.moduli)) != len(self.moduli):
            p.append("ci sono moduli ripetuti")
        for m in self.moduli:
            try:
                d, c, a = modulo_in_numeri(m)
            except ValueError as e:
                p.append(str(e))
                continue
            if self.rosa and (d > self.rosa.get("D", 0) or c > self.rosa.get("C", 0) or a > self.rosa.get("A", 0)):
                p.append(f"il modulo {m} chiede più giocatori di quanti ce ne sono in rosa")
        if not 0 <= self.rimborso_svincolo <= 1:
            p.append("il rimborso di chi si svincola deve essere tra 0 e 1 (0,5 = metà del prezzo pagato)")
        if not 0 <= self.scadenza_minuti <= MAX_SCADENZA_MINUTI:
            p.append(f"la scadenza della formazione deve essere tra 0 e {MAX_SCADENZA_MINUTI} minuti prima della prima partita")
        if not 1 <= self.prima_giornata_lega <= GIORNATE_SERIE_A:
            p.append(f"la prima giornata della lega deve essere tra 1 e {GIORNATE_SERIE_A}")
        if self.panchina.tipo not in ("libera", "per_ruolo"):
            p.append('panchina.tipo deve essere "libera" o "per_ruolo"')
        if self.panchina.numero < 0 or self.panchina.max_sostituzioni < 0:
            p.append("panchina.numero e panchina.max_sostituzioni non possono essere negativi")
        if self.panchina.max_sostituzioni > MAX_SOSTITUZIONI:
            p.append(f"panchina.max_sostituzioni: al massimo {MAX_SOSTITUZIONI}")
        if self.panchina.numero > 2 * MAX_SOSTITUZIONI + 10:
            p.append("panchina.numero troppo alto")
        posti = self.panchina.posti
        if posti is not None:
            if set(posti) != set(RUOLI) or any(v < 0 for v in posti.values()):
                p.append("panchina.posti deve indicare quanti posti per P, D, C, A (zero o più)")
            elif sum(posti.values()) != self.panchina.numero:
                p.append(f"panchina.numero ({self.panchina.numero}) deve essere la somma dei posti per ruolo ({sum(posti.values())})")
        return p

    def _problemi_di_tipo(self) -> list[str]:
        p = []
        numeri = {f"bonus.{k}": v for k, v in asdict(self.bonus).items() if k != "gol"}
        numeri |= {f"bonus.gol.{k}": v for k, v in self.bonus.gol.items()} if isinstance(self.bonus.gol, dict) else {}
        numeri |= {"fattore_campo": self.fattore_campo, "soglia_primo_gol": self.soglia_primo_gol,
                   "ampiezza_fascia_gol": self.ampiezza_fascia_gol}
        if self.voto_senza_sostituto is not None:
            numeri["voto_senza_sostituto"] = self.voto_senza_sostituto
        p += [f"{k} deve essere un numero" for k, v in numeri.items() if not _numero(v)]
        if not _numero(self.rimborso_svincolo):       # (il Mercato lo moltiplica per il prezzo pagato: un testo lo faceva andare in errore)
            p.append("il rimborso di chi si svincola deve essere un numero tra 0 e 1 (0,5 = metà del prezzo pagato)")
        interi = {"crediti_iniziali": self.crediti_iniziali, "panchina.numero": self.panchina.numero,
                  "panchina.max_sostituzioni": self.panchina.max_sostituzioni,
                  "scadenza_minuti": self.scadenza_minuti, "prima_giornata_lega": self.prima_giornata_lega,
                  "modificatore_difesa.min_difensori": self.modificatore_difesa.min_difensori}
        if self.panchina.posti is not None:
            if isinstance(self.panchina.posti, dict):
                interi |= {f"panchina.posti.{k}": v for k, v in self.panchina.posti.items()}
            else:
                p.append('panchina.posti deve essere del tipo {"P": 2, "D": 3, "C": 3, "A": 3} oppure vuoto')
        if isinstance(self.rosa, dict):
            interi |= {f"rosa.{k}": v for k, v in self.rosa.items()}
        else:
            p.append("rosa deve essere del tipo {\"P\": 3, \"D\": 8, \"C\": 8, \"A\": 6}")
        p += [f"{k} deve essere un numero intero" for k, v in interi.items() if not (_numero(v) and v == int(v))]
        for k, v in {"panchina.cambio_modulo": self.panchina.cambio_modulo,
                     "modificatore_difesa.attivo": self.modificatore_difesa.attivo,
                     "aggiornamenti_vicino_scadenza": self.aggiornamenti_vicino_scadenza}.items():
            if not isinstance(v, bool):
                p.append(f"{k} deve essere true o false")
        for k, v in {"nome_lega": self.nome_lega, "fonte_voto": self.fonte_voto, "panchina.tipo": self.panchina.tipo}.items():
            if not isinstance(v, str):
                p.append(f"{k} deve essere un testo")
        if not isinstance(self.bonus.gol, dict):
            p.append("bonus.gol deve indicare un valore per ruolo")
        if not isinstance(self.moduli, list) or not all(isinstance(m, str) for m in self.moduli):
            p.append('moduli deve essere una lista di testi, es. ["3-4-3", "4-4-2"]')
        s = self.modificatore_difesa.soglie
        if not isinstance(s, list) or not all(isinstance(x, list) and len(x) == 2 and all(map(_numero, x)) for x in s):
            p.append("modificatore_difesa.soglie deve essere una lista di [media, bonus], es. [[6, 1], [6.5, 3]]")
        return p


def lega_a_serie_a(giornata_lega: int, regole: "Regole") -> int | None:
    """La giornata di Serie A di una giornata della lega (con prima_giornata_lega = 4: lega 7 = Serie A 10).
    None se il risultato non è una giornata vera (1-38)."""
    n = giornata_lega + regole.prima_giornata_lega - 1
    return n if giornata_lega >= 1 and 1 <= n <= 38 else None


def serie_a_a_lega(giornata_serie_a: int, regole: "Regole") -> int | None:
    """La giornata della lega di una giornata di Serie A; None se la lega non era ancora partita."""
    n = giornata_serie_a - regole.prima_giornata_lega + 1
    return n if n >= 1 else None


def _e_intero(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)      # niente inf e nan


@lru_cache(maxsize=256)
@lru_cache(maxsize=512)          # chiamata decine di migliaia di volte per ricerca (scambi, formazione): il testo del modulo è sempre lo stesso
def modulo_in_numeri(modulo: str) -> tuple[int, int, int]:
    """'3-4-3' -> (3, 4, 3). Gli 11 sono portiere + 10 di movimento."""
    m = re.fullmatch(r"\s*(\d)\s*-\s*(\d)\s*-\s*(\d)\s*", modulo)
    if not m:
        raise ValueError(f"modulo non valido: {modulo!r} (formato atteso tipo 3-4-3)")
    d, c, a = map(int, m.groups())
    if d + c + a != 10:
        raise ValueError(f"il modulo {modulo} non somma a 10 giocatori di movimento")
    return d, c, a


# ---- lettura e scrittura ----
def _da_dict(classe, dati: dict[str, Any]):
    """Crea la dataclass dai dati JSON, segnalando le chiavi sconosciute (errori di battitura)."""
    if not isinstance(dati, dict):
        raise ValueError(f"{classe.__name__}: atteso un gruppo di valori {{...}}, trovato {dati!r}")
    tipi = get_type_hints(classe)
    validi = {f.name for f in fields(classe)}
    ignote = set(dati) - validi
    if ignote:
        raise ValueError(f"{classe.__name__}: chiavi sconosciute {sorted(ignote)}")
    argomenti = {}
    for nome, valore in dati.items():
        tipo = tipi[nome]
        if is_dataclass(tipo):
            valore = _da_dict(tipo, valore)
        elif _e_intero(valore) and "float" in str(tipo):       # 3 -> 3.0 (l'app manda i numeri senza decimali)
            valore = float(valore)
        elif tipo == dict[str, float] and isinstance(valore, dict):
            valore = {k: float(v) if _e_intero(v) else v for k, v in valore.items()}
        argomenti[nome] = valore
    return classe(**argomenti)


def da_dict(dati: dict[str, Any]) -> Regole:
    regole = _da_dict(Regole, dati)
    problemi = regole.problemi()
    if problemi:
        raise ValueError("Regole non valide:\n- " + "\n- ".join(problemi))
    return regole


def carica(percorso: Path) -> Regole:
    if not percorso.exists():
        return Regole()
    return da_dict(json.loads(percorso.read_text(encoding="utf-8")))


def salva(regole: Regole, percorso: Path) -> None:
    problemi = regole.problemi()
    if problemi:
        raise ValueError("Regole non valide:\n- " + "\n- ".join(problemi))
    scrivi_sicuro(percorso, json.dumps(asdict(regole), ensure_ascii=False, indent=2))


def imposta(regole: Regole, chiave: str, valore_testo: str) -> Regole:
    """Cambia un valore con un percorso puntato, es. 'bonus.assist' = '1.5' o 'bonus.gol.D' = '4.5'.

    Il valore si scrive come in JSON (numeri, true/false, null, liste); il testo semplice va bene così com'è.
    Restituisce nuove regole (controllate); quelle di partenza non cambiano.
    """
    try:
        valore = json.loads(valore_testo)
    except json.JSONDecodeError:
        valore = valore_testo
    dati = asdict(regole)
    nodo = dati
    parti = chiave.split(".")
    for p in parti[:-1]:
        if not isinstance(nodo, dict) or p not in nodo:
            raise ValueError(f"chiave sconosciuta: {chiave}")
        nodo = nodo[p]
    if not isinstance(nodo, dict) or parti[-1] not in nodo:
        raise ValueError(f"chiave sconosciuta: {chiave}")
    vecchio = nodo[parti[-1]]
    if isinstance(vecchio, float) and isinstance(valore, int) and not isinstance(valore, bool):
        valore = float(valore)
    if vecchio is not None and valore is not None and type(vecchio) is not type(valore):
        raise ValueError(f"{chiave}: atteso un valore di tipo {type(vecchio).__name__}, ricevuto {valore!r}")
    nodo[parti[-1]] = valore
    return da_dict(dati)
