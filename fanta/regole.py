"""Regole della lega (classic), tutte parametriche.

I valori predefiniti sono quelli tipici di Leghe Fantacalcio classic: vanno adattati alla propria lega
con il comando `regole --imposta` (o, più avanti, dall'app). Si salvano in lega/regole.json.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import date
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
# Partite rinviate (anche a settimane dopo). `aspetta`: la lega aspetta il recupero e conta il voto preso lì (come «Attendi il
# recupero» di Leghe Fantacalcio); `senza_voto`: i giocatori restano senza voto ed entra la riserva; `voto_ufficio`: tutti prendono
# il voto fisso `voto_ufficio_rinviate`. Le eccezioni decise volta per volta stanno in `rinvii_giornate` (vedi rinvii.py).
MODI_RINVIO = ("aspetta", "senza_voto", "voto_ufficio")
MAX_ECCEZIONI_RINVII = 2 * GIORNATE_SERIE_A
_CHIAVE_RINVIO = re.compile(r"\d{4}-\d{2}/([1-9]|[12]\d|3[0-8])")
# Momenti di mercato della lega (aste, finestre di scambio): periodi {"dal": "AAAA-MM-GG", "al": "AAAA-MM-GG"}, `al` facoltativo
# (un giorno solo). Dopo questi momenti Da fare ricorda di aggiornare le rose (da_fare._momenti_mercato).
# Aste quando la lega non dice le date: (mese, giorno) di inizio e di fine, 2-3 settimane dopo la chiusura del mercato della Serie A
# (estivo a fine agosto, invernale a fine gennaio). L'asta estiva è nell'anno d'inizio della stagione, l'invernale in quello dopo.
ASTA_ESTIVA_PREDEFINITA = ((9, 1), (9, 21))
ASTA_INVERNALE_PREDEFINITA = ((2, 1), (2, 21))
MAX_FINESTRE_SCAMBIO = 20
MAX_GIORNI_PERIODO = 60
_GIORNO = re.compile(r"\d{4}-\d{2}-\d{2}")
# Tetti di misura (liste e testi): larghi rispetto alle leghe vere, servono solo contro regole enormi che rallenterebbero i calcoli
# di tutti. Oltre i tetti l'errore è RegoleTroppoGrandi (il server risponde 422). Le regole salvate prima dei tetti si leggono
# ancora (carica); per salvarle di nuovo vanno riportate dentro i tetti.
MAX_NOME_LEGA = 100                # caratteri del nome della lega
MAX_TESTO_MODULO = 20              # caratteri di un modulo («3-4-3», anche con qualche spazio)
MAX_SOGLIE = 20                    # fasce del modificatore difesa
MAX_CHIAVE_RINVIO = 20             # caratteri di una giornata delle eccezioni («2026-27/12»)
# Intervalli dei numeri (#663): larghi rispetto ai regolamenti veri (la web e l'iPhone lasciano scegliere bonus da 0 a 20, malus da
# -20 a 0, crediti fino a 5.000, da 3 a 6 difensori, medie delle fasce da 4 a 9), servono solo contro numeri enormi che nei conti
# diventano infiniti e rompono tutte le schermate. Si controllano al salvataggio, come i tetti di misura: le regole salvate prima
# si leggono ancora (la schermata Regole le mostra e le si corregge), ma per salvarle di nuovo vanno riportate negli intervalli.
MAX_BONUS = 100                    # bonus e malus (anche le fasce del modificatore e il fattore campo), da -100 a 100
MAX_VOTO = 10                      # voto di chi resta senza sostituto e media delle fasce del modificatore difesa, da 0 a 10
MAX_CREDITI = 100_000              # crediti iniziali, come il tetto dei crediti delle squadre
MAX_DIFENSORI = 10                 # difensori minimi del modificatore difesa (i giocatori di movimento sono 10)
MAX_SOGLIA_PRIMO_GOL = 200         # partite testa a testa: punti del primo gol (di solito 66)
MAX_FASCIA_GOL = 100               # partite testa a testa: ampiezza delle fasce dei gol (di solito 6)
_RUOLO_DEL_GOL = {"P": "del portiere", "D": "del difensore", "C": "del centrocampista", "A": "dell'attaccante"}
_INTERVALLI_BONUS = {              # campo di `Bonus` -> inizio della frase dell'errore (vedi Regole.problemi_di_intervallo)
    "rigore_segnato": "il bonus per il rigore segnato deve", "assist": "il bonus per l'assist deve",
    "rigore_parato": "il bonus per il rigore parato deve", "rigore_sbagliato": "il malus per il rigore sbagliato deve",
    "autogol": "il malus per l'autogol deve", "gol_subito_portiere": "il malus per ogni gol subito dal portiere deve",
    "portiere_imbattuto": "il bonus per il portiere imbattuto deve", "ammonizione": "il malus per l'ammonizione deve",
    "espulsione": "il malus per l'espulsione deve", "mvp": "il bonus per il migliore in campo deve",
}


class RegoleTroppoGrandi(ValueError):
    """Regole oltre i tetti di misura: il messaggio è per chi usa l'app e non ripete i valori ricevuti (il server risponde 422)."""
    stato = 422


class RegoleFuoriIntervallo(ValueError):
    """Numeri fuori dagli intervalli (MAX_BONUS e gli altri): il messaggio dice il campo e l'intervallo, non il valore ricevuto
    (il server risponde 400; il ripristino di un backup lo riporta invece di dare la colpa al file)."""
    stato = 400


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
    # Partite rinviate: regola generale, voto d'ufficio e eccezioni per una giornata ({"2026-27/12": "voto_ufficio"}: stagione e
    # giornata di Serie A). L'eccezione vince sulla regola generale. Vedi MODI_RINVIO e rinvii.py.
    partite_rinviate: str = "aspetta"
    voto_ufficio_rinviate: float = 6.0
    rinvii_giornate: dict[str, str] = field(default_factory=dict)
    # Quando cambiano le rose della lega, per il promemoria «aggiorna le rose» di Da fare. `asta_estiva`, `asta_invernale`: un
    # periodo; None = ASTA_ESTIVA_PREDEFINITA e ASTA_INVERNALE_PREDEFINITA. `finestre_scambio`: elenco di periodi; None = le soste
    # del campionato dal calendario della Serie A; [] = nessuna finestra. Contano solo le date della stagione in corso (date di
    # un'altra stagione rimaste nel file: valgono le aste di partenza e le soste).
    asta_estiva: dict[str, str | None] | None = None
    asta_invernale: dict[str, str | None] | None = None
    finestre_scambio: list[dict[str, str | None]] | None = None

    # ---- controlli ----
    def problemi_di_misura(self) -> list[str]:
        """Liste e testi oltre i tetti (MAX_*). Controlla solo le misure, con qualunque tipo: si fa prima di tutto il resto,
        così gli altri controlli lavorano su poche voci corte. I messaggi non ripetono i valori ricevuti."""
        p = []
        if isinstance(self.nome_lega, str) and len(self.nome_lega) > MAX_NOME_LEGA:
            p.append(f"il nome della lega può avere al massimo {MAX_NOME_LEGA} caratteri")
        if isinstance(self.moduli, list):
            if len(self.moduli) > MAX_MODULI:
                p.append(f"al massimo {MAX_MODULI} moduli")
            elif any(isinstance(m, str) and len(m) > MAX_TESTO_MODULO for m in self.moduli):
                p.append(f"ogni modulo si scrive come 3-4-3 (al massimo {MAX_TESTO_MODULO} caratteri)")
        soglie = self.modificatore_difesa.soglie if isinstance(self.modificatore_difesa, ModificatoreDifesa) else None
        if isinstance(soglie, list) and len(soglie) > MAX_SOGLIE:
            p.append(f"il modificatore difesa può avere al massimo {MAX_SOGLIE} fasce")
        if isinstance(self.rinvii_giornate, dict):
            if len(self.rinvii_giornate) > MAX_ECCEZIONI_RINVII:
                p.append(f"rinvii_giornate: al massimo {MAX_ECCEZIONI_RINVII} eccezioni")
            elif any(not isinstance(k, str) or len(k) > MAX_CHIAVE_RINVIO for k in self.rinvii_giornate):
                p.append('rinvii_giornate: le giornate si scrivono come "2026-27/12" (stagione/giornata di Serie A)')
        if isinstance(self.finestre_scambio, list) and len(self.finestre_scambio) > MAX_FINESTRE_SCAMBIO:
            p.append(f"finestre_scambio: al massimo {MAX_FINESTRE_SCAMBIO} finestre")
        gol = self.bonus.gol if isinstance(self.bonus, Bonus) else None
        posti = self.panchina.posti if isinstance(self.panchina, Panchina) else None
        for nome, per_ruolo in (("bonus.gol", gol), ("rosa", self.rosa), ("panchina.posti", posti)):
            if isinstance(per_ruolo, dict) and len(per_ruolo) > len(RUOLI):
                p.append(f"{nome}: un valore per ogni ruolo P, D, C, A, non di più")
        return p

    def problemi(self, misure: bool = True) -> list[str]:
        """Tutto ciò che non va. `misure=False` salta i tetti di misura e gli intervalli dei numeri (per leggere le regole salvate
        prima dei tetti e degli intervalli)."""
        p = self.problemi_di_misura() if misure else []
        if p:
            return p
        return self._problemi_di_valore(intervalli=misure)

    def problemi_di_intervallo(self) -> list[str]:
        """Numeri fuori dagli intervalli (MAX_BONUS e gli altri sopra). Da chiamare con i tipi già controllati."""
        md = self.modificatore_difesa
        # (inizio della frase, valori, minimo, massimo): la frase continua con «essere tra minimo e massimo»
        controlli = [(f"il bonus per il gol {_RUOLO_DEL_GOL.get(ruolo, ruolo)} deve", [v], -MAX_BONUS, MAX_BONUS)
                     for ruolo, v in self.bonus.gol.items()]
        controlli += [(frase, [getattr(self.bonus, nome)], -MAX_BONUS, MAX_BONUS) for nome, frase in _INTERVALLI_BONUS.items()]
        controlli += [
            ("il voto di chi resta senza sostituto deve", [v for v in [self.voto_senza_sostituto] if v is not None], 0, MAX_VOTO),
            ("i crediti iniziali devono", [self.crediti_iniziali], 0, MAX_CREDITI),
            ("i difensori minimi del modificatore difesa devono", [md.min_difensori], 0, MAX_DIFENSORI),
            ("la media di ogni fascia del modificatore difesa deve", [media for media, _ in md.soglie], 0, MAX_VOTO),
            ("il bonus di ogni fascia del modificatore difesa deve", [bonus for _, bonus in md.soglie], -MAX_BONUS, MAX_BONUS),
            ("il fattore campo deve", [self.fattore_campo], -MAX_BONUS, MAX_BONUS),
            ("i punti del primo gol (partite testa a testa) devono", [self.soglia_primo_gol], 0, MAX_SOGLIA_PRIMO_GOL),
            ("l'ampiezza delle fasce dei gol (partite testa a testa) deve", [self.ampiezza_fascia_gol], 0, MAX_FASCIA_GOL),
        ]
        return [f"{frase} essere tra {_cifra(minimo)} e {_cifra(massimo)}" for frase, valori, minimo, massimo in controlli
                if any(not minimo <= v <= massimo for v in valori)]

    def _problemi_di_valore(self, intervalli: bool) -> list[str]:
        """Tipi e valori (senza i tetti di misura); `intervalli` aggiunge gli intervalli dei numeri."""
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
        if self.partite_rinviate not in MODI_RINVIO:
            p.append(f"partite_rinviate deve essere una di {MODI_RINVIO}")
        if not 0 <= self.voto_ufficio_rinviate <= 10:
            p.append("il voto d'ufficio delle partite rinviate deve essere tra 0 e 10")
        if len(self.rinvii_giornate) > MAX_ECCEZIONI_RINVII:
            p.append(f"rinvii_giornate: al massimo {MAX_ECCEZIONI_RINVII} eccezioni")
        for k, v in self.rinvii_giornate.items():
            if not _CHIAVE_RINVIO.fullmatch(k):
                p.append(f"rinvii_giornate: {k!r} non è del tipo \"2026-27/12\" (stagione/giornata di Serie A)")
            if v not in MODI_RINVIO:
                p.append(f"rinvii_giornate[{k!r}] deve essere una di {MODI_RINVIO}")
        for nome, asta in (("asta_estiva", self.asta_estiva), ("asta_invernale", self.asta_invernale)):
            if asta is not None:
                p += _problemi_periodo(nome, asta)
        f = self.finestre_scambio
        if f is not None and not isinstance(f, list):
            p.append('finestre_scambio deve essere un elenco di periodi, es. [{"dal": "2026-11-14", "al": "2026-11-16"}], oppure vuoto')
        elif f is not None and len(f) > MAX_FINESTRE_SCAMBIO:
            p.append(f"finestre_scambio: al massimo {MAX_FINESTRE_SCAMBIO} finestre")
        elif f is not None:
            for i, x in enumerate(f):
                p += _problemi_periodo(f"finestre_scambio[{i}]", x)
        if intervalli:
            p += self.problemi_di_intervallo()
        return p

    def _problemi_di_tipo(self) -> list[str]:
        p = []
        numeri = {f"bonus.{k}": v for k, v in asdict(self.bonus).items() if k != "gol"}
        numeri |= {f"bonus.gol.{k}": v for k, v in self.bonus.gol.items()} if isinstance(self.bonus.gol, dict) else {}
        numeri |= {"fattore_campo": self.fattore_campo, "soglia_primo_gol": self.soglia_primo_gol,
                   "ampiezza_fascia_gol": self.ampiezza_fascia_gol, "voto_ufficio_rinviate": self.voto_ufficio_rinviate}
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
        for k, v in {"nome_lega": self.nome_lega, "fonte_voto": self.fonte_voto, "panchina.tipo": self.panchina.tipo,
                     "partite_rinviate": self.partite_rinviate}.items():
            if not isinstance(v, str):
                p.append(f"{k} deve essere un testo")
        if not isinstance(self.rinvii_giornate, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                                 for k, v in self.rinvii_giornate.items()):
            p.append('rinvii_giornate deve essere del tipo {"2026-27/12": "voto_ufficio"} oppure vuoto')
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


def giorno(testo) -> date:
    """«2027-01-20» -> la data. ValueError se non è una data vera scritta così."""
    if not isinstance(testo, str) or not _GIORNO.fullmatch(testo):
        raise ValueError(testo)
    return date.fromisoformat(testo)


def periodo(p: dict) -> tuple[date, date]:
    """Un periodo della lega già controllato ({"dal", "al"}, `al` facoltativo): primo e ultimo giorno."""
    return giorno(p["dal"]), giorno(p.get("al") or p["dal"])


def _problemi_periodo(nome: str, p) -> list[str]:
    if not isinstance(p, dict) or "dal" not in p or set(p) - {"dal", "al"}:
        return [f'{nome} deve essere del tipo {{"dal": "2027-01-20", "al": "2027-01-22"}} ("al" si può omettere per un giorno solo)']
    try:
        dal, al = periodo(p)
    except ValueError:
        return [f"{nome}: le date vanno scritte come 2027-01-20 (anno, mese, giorno)"]
    if al < dal:
        return [f"{nome}: il giorno di fine viene prima di quello d'inizio"]
    if (al - dal).days >= MAX_GIORNI_PERIODO:
        return [f"{nome}: al massimo {MAX_GIORNI_PERIODO} giorni"]
    return []


def _e_intero(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)      # niente inf e nan


def _cifra(n: int) -> str:
    """Un numero intero scritto all'italiana: 100000 -> «100.000»."""
    return f"{n:,}".replace(",", ".")


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


def _controlla(regole: Regole, misure: bool = True) -> Regole:
    """Errore se le regole non vanno: RegoleTroppoGrandi oltre i tetti di misura e RegoleFuoriIntervallo per i numeri fuori dagli
    intervalli (tutti e due solo se `misure`), ValueError per il resto."""
    troppo = regole.problemi_di_misura() if misure else []
    if troppo:
        raise RegoleTroppoGrandi("Regole non valide:\n- " + "\n- ".join(troppo))
    problemi = regole._problemi_di_valore(intervalli=False)
    if problemi:
        raise ValueError("Regole non valide:\n- " + "\n- ".join(problemi))
    fuori = regole.problemi_di_intervallo() if misure else []      # solo con i tipi e gli altri valori a posto
    if fuori:
        raise RegoleFuoriIntervallo("Regole non valide:\n- " + "\n- ".join(fuori))
    return regole


def da_dict(dati: dict[str, Any], misure: bool = True) -> Regole:
    return _controlla(_da_dict(Regole, dati), misure)


def carica(percorso: Path) -> Regole:
    """Le regole salvate (o quelle di partenza se il file non c'è). Senza i tetti di misura e gli intervalli dei numeri: un file
    salvato prima si legge ancora."""
    if not percorso.exists():
        return Regole()
    return da_dict(json.loads(percorso.read_text(encoding="utf-8")), misure=False)


def salva(regole: Regole, percorso: Path) -> None:
    _controlla(regole)
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
