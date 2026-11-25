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
# Limiti dei numeri della pagina Regole (#881): un posto solo, `fanta/web/limiti-regole.json` ({"bonus.assist": {"min": 0,
# "max": 20}, ...}). Lo legge il server, qui, e la pagina Regole della web per i pulsanti − e + e per i numeri scritti a mano:
# così la pagina non arriva mai a un numero che il server rifiuta. Larghi rispetto ai regolamenti veri; i bonus non sono mai
# negativi e i malus mai positivi. Le chiavi sono i percorsi dei campi; «modificatore_difesa.soglie.media» e
# «modificatore_difesa.soglie.bonus» valgono per ogni fascia. Valgono SOLO per i valori che cambiano quando si salvano le regole
# dalla loro pagina (PUT /api/regole, che passa `salvate`): una lega salvata prima con valori ora fuori da questi limiti continua a
# funzionare (eccezione delle partite rinviate, scadenza, procedura guidata, backup) e la pagina chiede di correggerli solo quando
# si salvano i valori.
FILE_LIMITI = Path(__file__).resolve().parent / "web" / "limiti-regole.json"
LIMITI: dict[str, dict[str, int | float]] = json.loads(FILE_LIMITI.read_text(encoding="utf-8"))
# I limiti di prima (#663 e i controlli della lettura): valgono per i valori che non cambiano e per ogni salvataggio che non passa
# `salvate`. Servono solo contro numeri enormi che nei conti diventano infiniti e rompono tutte le schermate.
_LARGO = {"min": -100, "max": 100}
LIMITI_LARGHI: dict[str, dict[str, int | float]] = {k: _LARGO for k in LIMITI if k.startswith("bonus.")} | {
    **{f"rosa.{r}": {"min": 1, "max": 30} for r in RUOLI}, "crediti_iniziali": {"min": 0, "max": 100_000},
    "panchina.numero": {"min": 0, "max": 30}, "panchina.max_sostituzioni": {"min": 0, "max": 10},
    **{f"panchina.posti.{r}": {"min": 0, "max": 30} for r in RUOLI},
    "voto_senza_sostituto": {"min": 0, "max": 10}, "voto_ufficio_rinviate": {"min": 0, "max": 10},
    "modificatore_difesa.min_difensori": {"min": 0, "max": 10}, "modificatore_difesa.soglie.media": {"min": 0, "max": 10},
    "modificatore_difesa.soglie.bonus": _LARGO, "fattore_campo": _LARGO, "soglia_primo_gol": {"min": 0, "max": 200},
    "ampiezza_fascia_gol": {"min": 0, "max": 100},
}
MAX_ROSA_PER_RUOLO = LIMITI_LARGHI["rosa.P"]["max"]
# Controllate anche quando le regole si leggono, con LIMITI_LARGHI (una rosa enorme, troppi cambi o una panchina negativa
# rallentano i calcoli o li fanno fallire); le altre solo quando si salvano.
_SEMPRE = (*(f"rosa.{r}" for r in RUOLI), "panchina.numero", "panchina.max_sostituzioni", *(f"panchina.posti.{r}" for r in RUOLI),
           "voto_ufficio_rinviate")
# Il nome di ogni campo nei messaggi d'errore (la web lo traduce con la chiave err.p_regola_* che ha lo stesso testo)
NOMI_CAMPI = {
    "bonus.gol.P": "Gol di un portiere", "bonus.gol.D": "Gol di un difensore", "bonus.gol.C": "Gol di un centrocampista",
    "bonus.gol.A": "Gol di un attaccante", "bonus.rigore_segnato": "Rigore segnato", "bonus.assist": "Assist",
    "bonus.rigore_parato": "Rigore parato", "bonus.rigore_sbagliato": "Rigore sbagliato", "bonus.autogol": "Autogol",
    "bonus.gol_subito_portiere": "Gol subito dal portiere", "bonus.portiere_imbattuto": "Portiere imbattuto",
    "bonus.ammonizione": "Ammonizione", "bonus.espulsione": "Espulsione", "bonus.mvp": "Migliore in campo",
    "rosa.P": "Portieri della rosa", "rosa.D": "Difensori della rosa", "rosa.C": "Centrocampisti della rosa",
    "rosa.A": "Attaccanti della rosa", "crediti_iniziali": "Crediti iniziali", "panchina.numero": "Giocatori in panchina",
    "panchina.max_sostituzioni": "Cambi massimi", "panchina.posti.P": "Posti in panchina per i portieri",
    "panchina.posti.D": "Posti in panchina per i difensori", "panchina.posti.C": "Posti in panchina per i centrocampisti",
    "panchina.posti.A": "Posti in panchina per gli attaccanti", "panchina.cambio_modulo": "Cambio modulo nelle sostituzioni",
    "panchina.tipo": "Come entrano le riserve", "voto_senza_sostituto": "Voto d'ufficio di chi resta senza sostituto",
    "voto_ufficio_rinviate": "Voto d'ufficio delle partite rinviate", "partite_rinviate": "Partite rinviate",
    "modificatore_difesa.attivo": "Modificatore difesa attivo",
    "modificatore_difesa.min_difensori": "Difensori minimi del modificatore difesa", "fattore_campo": "Fattore campo",
    "soglia_primo_gol": "Punti del primo gol", "ampiezza_fascia_gol": "Ampiezza delle fasce dei gol",
    "scadenza_minuti": "Scadenza della formazione", "prima_giornata_lega": "Prima giornata della lega",
    "aggiornamenti_vicino_scadenza": "Aggiornamenti vicino alla scadenza", "nome_lega": "Nome della lega",
    "fonte_voto": "Voto di partenza",
}
NON_VALIDE = "Regole non valide:"   # prima riga dell'errore, poi una riga «- …» per problema (la web le traduce una per una)
# La frase di ogni limite, per chi usa l'app; {min} e {max} diventano i numeri di LIMITI. La web la traduce con la chiave err.* del
# catalogo che ha lo stesso testo (fanta/testi/err.json).
FRASI_LIMITI = {
    "bonus.gol.P": "il bonus per il gol del portiere deve essere tra {min} e {max}",
    "bonus.gol.D": "il bonus per il gol del difensore deve essere tra {min} e {max}",
    "bonus.gol.C": "il bonus per il gol del centrocampista deve essere tra {min} e {max}",
    "bonus.gol.A": "il bonus per il gol dell'attaccante deve essere tra {min} e {max}",
    "bonus.rigore_segnato": "il bonus per il rigore segnato deve essere tra {min} e {max}",
    "bonus.assist": "il bonus per l'assist deve essere tra {min} e {max}",
    "bonus.rigore_parato": "il bonus per il rigore parato deve essere tra {min} e {max}",
    "bonus.portiere_imbattuto": "il bonus per il portiere imbattuto deve essere tra {min} e {max}",
    "bonus.mvp": "il bonus per il migliore in campo deve essere tra {min} e {max}",
    "bonus.rigore_sbagliato": "il malus per il rigore sbagliato deve essere tra {min} e {max}",
    "bonus.autogol": "il malus per l'autogol deve essere tra {min} e {max}",
    "bonus.gol_subito_portiere": "il malus per ogni gol subito dal portiere deve essere tra {min} e {max}",
    "bonus.ammonizione": "il malus per l'ammonizione deve essere tra {min} e {max}",
    "bonus.espulsione": "il malus per l'espulsione deve essere tra {min} e {max}",
    "rosa.P": "i portieri della rosa devono essere tra {min} e {max}",
    "rosa.D": "i difensori della rosa devono essere tra {min} e {max}",
    "rosa.C": "i centrocampisti della rosa devono essere tra {min} e {max}",
    "rosa.A": "gli attaccanti della rosa devono essere tra {min} e {max}",
    "crediti_iniziali": "i crediti iniziali devono essere tra {min} e {max}",
    "panchina.numero": "i giocatori in panchina devono essere tra {min} e {max}",
    "panchina.max_sostituzioni": "i cambi massimi devono essere tra {min} e {max}",
    "panchina.posti.P": "i posti in panchina per i portieri devono essere tra {min} e {max}",
    "panchina.posti.D": "i posti in panchina per i difensori devono essere tra {min} e {max}",
    "panchina.posti.C": "i posti in panchina per i centrocampisti devono essere tra {min} e {max}",
    "panchina.posti.A": "i posti in panchina per gli attaccanti devono essere tra {min} e {max}",
    "voto_senza_sostituto": "il voto d'ufficio di chi resta senza sostituto deve essere tra {min} e {max}",
    "voto_ufficio_rinviate": "il voto d'ufficio delle partite rinviate deve essere tra {min} e {max}",
    "modificatore_difesa.min_difensori": "i difensori minimi del modificatore difesa devono essere tra {min} e {max}",
    "modificatore_difesa.soglie.media": "la media di ogni fascia del modificatore difesa deve essere tra {min} e {max}",
    "modificatore_difesa.soglie.bonus": "il bonus di ogni fascia del modificatore difesa deve essere tra {min} e {max}",
    "fattore_campo": "il fattore campo deve essere tra {min} e {max}",
    "soglia_primo_gol": "i punti del primo gol (partite testa a testa) devono essere tra {min} e {max}",
    "ampiezza_fascia_gol": "l'ampiezza delle fasce dei gol (partite testa a testa) deve essere tra {min} e {max}",
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

    def problemi(self, misure: bool = True, salvate: "Regole | None" = None) -> list[str]:
        """Tutto ciò che non va. `misure=False` salta i tetti di misura e gli intervalli dei numeri (per leggere le regole salvate
        prima dei tetti e degli intervalli). `salvate`: le regole che queste sostituiscono dalla pagina Regole (i valori cambiati
        hanno i limiti di LIMITI, vedi problemi_di_intervallo)."""
        p = self.problemi_di_misura() if misure else []
        if p:
            return p
        return self._problemi_di_valore(intervalli=misure, salvate=salvate)

    def _numeri_con_limite(self) -> dict[str, list]:
        """I numeri delle regole per ogni chiave di LIMITI, nell'ordine di LIMITI (una fascia del modificatore = un valore per
        chiave; nessun valore se il campo è vuoto). Da chiamare con i tipi già controllati."""
        md, pan = self.modificatore_difesa, self.panchina
        numeri = {f"bonus.gol.{r}": [v] for r, v in self.bonus.gol.items()}
        numeri |= {f"bonus.{f.name}": [getattr(self.bonus, f.name)] for f in fields(Bonus) if f.name != "gol"}
        numeri |= {f"rosa.{r}": [v] for r, v in self.rosa.items()}
        numeri |= {f"panchina.posti.{r}": [v] for r, v in (pan.posti or {}).items()}
        numeri |= {"crediti_iniziali": [self.crediti_iniziali], "panchina.numero": [pan.numero],
                   "panchina.max_sostituzioni": [pan.max_sostituzioni],
                   "voto_senza_sostituto": [v for v in [self.voto_senza_sostituto] if v is not None],
                   "voto_ufficio_rinviate": [self.voto_ufficio_rinviate], "modificatore_difesa.min_difensori": [md.min_difensori],
                   # le fasce ordinate per media: riordinarle non le cambia (la pagina le manda ordinate)
                   "modificatore_difesa.soglie.media": [media for media, _ in sorted(md.soglie)],
                   "modificatore_difesa.soglie.bonus": [bonus for _, bonus in sorted(md.soglie)],
                   "fattore_campo": [self.fattore_campo], "soglia_primo_gol": [self.soglia_primo_gol],
                   "ampiezza_fascia_gol": [self.ampiezza_fascia_gol]}
        return {k: numeri[k] for k in LIMITI if k in numeri}

    def problemi_di_intervallo(self, salvate: "Regole | None" = None, solo_sempre: bool = False) -> list[str]:
        """Numeri fuori dai limiti. Senza `salvate` (ogni salvataggio che non viene dalla pagina Regole) i limiti di prima,
        LIMITI_LARGHI. Con `salvate` (PUT /api/regole) i valori cambiati rispetto a quelle hanno i limiti della pagina, LIMITI, e
        si guardano anche i valori che non hanno senso, se cambiano: modificatore acceso senza fasce, due fasce con la stessa
        media, difensori minimi che nessun modulo ammesso ha (il modificatore non si applicherebbe mai). `solo_sempre`: solo le
        chiavi di _SEMPRE (la lettura). Da chiamare con i tipi già controllati."""
        prima = salvate._numeri_con_limite() if salvate is not None else None
        p = []
        for k, valori in self._numeri_con_limite().items():
            if solo_sempre and k not in _SEMPRE:
                continue
            tabella = LIMITI if prima is not None and prima.get(k) != valori else LIMITI_LARGHI
            if any(not _dentro(k, v, tabella) for v in valori):
                p.append(_frase_limite(k, tabella))
        if salvate is None or solo_sempre:
            return p
        # «cambiato» non dipende dall'ordine: le fasce si confrontano ordinate per media e i moduli come insieme (la pagina manda le
        # fasce ordinate e i moduli nell'ordine dei suoi pulsanti, che possono essere diversi da quelli del file)
        md, md_prima = self.modificatore_difesa, salvate.modificatore_difesa
        cambiano_fasce = sorted(md.soglie) != sorted(md_prima.soglie)
        cambia_md = cambiano_fasce or (md.attivo, md.min_difensori) != (md_prima.attivo, md_prima.min_difensori)
        if cambia_md and md.attivo and not md.soglie:
            p.append("con il modificatore difesa acceso serve almeno una fascia")
        medie = [media for media, _ in md.soglie]
        if cambiano_fasce and len(set(medie)) != len(medie):
            p.append("due fasce del modificatore difesa hanno la stessa media: togline una")
        difensori = [d for d in map(_difensori_del_modulo, self.moduli) if d is not None]
        if (cambia_md or set(self.moduli) != set(salvate.moduli)) and md.attivo and difensori \
                and _dentro("modificatore_difesa.min_difensori", md.min_difensori) and md.min_difensori > max(difensori):
            p.append(f"nessun modulo ammesso ha almeno {int(md.min_difensori)} difensori: "
                     "il modificatore difesa non si applicherebbe mai")
        return p

    def _problemi_di_valore(self, intervalli: bool, salvate: "Regole | None" = None) -> list[str]:
        """Tipi e valori (senza i tetti di misura); `intervalli` aggiunge i limiti dei numeri che valgono al salvataggio (senza,
        solo quelli di _SEMPRE, che valgono anche quando si legge). `salvate`: vedi problemi_di_intervallo."""
        p = self._problemi_di_tipo()
        if p:  # con tipi sbagliati gli altri controlli non hanno senso
            return p
        if self.fonte_voto not in FONTI_VOTO:
            p.append("il voto di partenza deve essere quello della redazione, quello statistico o quello di Italia")
        if set(self.bonus.gol) != set(RUOLI):
            p.append("il bonus per il gol deve indicare un valore per portieri, difensori, centrocampisti e attaccanti")
        if set(self.rosa) != set(RUOLI):
            p.append("la rosa deve indicare quanti portieri, difensori, centrocampisti e attaccanti")
        p += self.problemi_di_intervallo(salvate, solo_sempre=not intervalli)
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
            p.append("le riserve devono entrare per ruolo o liberamente")
        posti = self.panchina.posti
        if posti is not None:                   # (posti negativi o enormi: li dicono i limiti di _SEMPRE)
            if set(posti) != set(RUOLI):
                p.append("i posti fissi in panchina devono indicare quanti portieri, difensori, centrocampisti e attaccanti")
            elif all(v >= 0 for v in posti.values()) and sum(posti.values()) != self.panchina.numero:
                p.append(f"i giocatori in panchina ({int(self.panchina.numero)}) devono essere la somma dei posti per ruolo "
                         f"({int(sum(posti.values()))})")
        if self.partite_rinviate not in MODI_RINVIO:
            p.append("le partite rinviate devono aspettare il recupero, restare senza voto o avere il voto d'ufficio")
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
        return p

    def _problemi_di_tipo(self) -> list[str]:
        """Tipi sbagliati, con il nome del campo come lo vede chi usa l'app (NOMI_CAMPI), mai quello del file."""
        p = []
        numeri = {f"bonus.{k}": v for k, v in asdict(self.bonus).items() if k != "gol"}
        numeri |= {f"bonus.gol.{k}": v for k, v in self.bonus.gol.items() if k in RUOLI} if isinstance(self.bonus.gol, dict) else {}
        numeri |= {"fattore_campo": self.fattore_campo, "soglia_primo_gol": self.soglia_primo_gol,
                   "ampiezza_fascia_gol": self.ampiezza_fascia_gol, "voto_ufficio_rinviate": self.voto_ufficio_rinviate}
        if self.voto_senza_sostituto is not None:
            numeri["voto_senza_sostituto"] = self.voto_senza_sostituto
        p += [f"«{NOMI_CAMPI[k]}» deve essere un numero" for k, v in numeri.items() if not _numero(v)]
        if not _numero(self.rimborso_svincolo):       # (il Mercato lo moltiplica per il prezzo pagato: un testo lo faceva andare in errore)
            p.append("il rimborso di chi si svincola deve essere un numero tra 0 e 1 (0,5 = metà del prezzo pagato)")
        interi = {"crediti_iniziali": self.crediti_iniziali, "panchina.numero": self.panchina.numero,
                  "panchina.max_sostituzioni": self.panchina.max_sostituzioni,
                  "scadenza_minuti": self.scadenza_minuti, "prima_giornata_lega": self.prima_giornata_lega,
                  "modificatore_difesa.min_difensori": self.modificatore_difesa.min_difensori}
        if self.panchina.posti is not None:
            if isinstance(self.panchina.posti, dict):
                interi |= {f"panchina.posti.{k}": v for k, v in self.panchina.posti.items() if k in RUOLI}
            else:
                p.append("i posti fissi in panchina devono indicare quanti portieri, difensori, centrocampisti e attaccanti")
        if isinstance(self.rosa, dict):
            interi |= {f"rosa.{k}": v for k, v in self.rosa.items() if k in RUOLI}
        else:
            p.append("la rosa deve indicare quanti portieri, difensori, centrocampisti e attaccanti")
        p += [f"«{NOMI_CAMPI[k]}» deve essere un numero intero" for k, v in interi.items() if not (_numero(v) and v == int(v))]
        for k, v in {"panchina.cambio_modulo": self.panchina.cambio_modulo,
                     "modificatore_difesa.attivo": self.modificatore_difesa.attivo,
                     "aggiornamenti_vicino_scadenza": self.aggiornamenti_vicino_scadenza}.items():
            if not isinstance(v, bool):
                p.append(f"«{NOMI_CAMPI[k]}» deve essere sì o no")
        for k, v in {"nome_lega": self.nome_lega, "fonte_voto": self.fonte_voto, "panchina.tipo": self.panchina.tipo,
                     "partite_rinviate": self.partite_rinviate}.items():
            if not isinstance(v, str):
                p.append(f"«{NOMI_CAMPI[k]}» deve essere un testo")
        if not isinstance(self.rinvii_giornate, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                                 for k, v in self.rinvii_giornate.items()):
            p.append("ogni eccezione delle partite rinviate deve dire la giornata e cosa fare")
        if not isinstance(self.bonus.gol, dict):
            p.append("il bonus per il gol deve indicare un valore per portieri, difensori, centrocampisti e attaccanti")
        if not isinstance(self.moduli, list) or not all(isinstance(m, str) for m in self.moduli):
            p.append("i moduli devono essere scritti come 3-4-3")
        s = self.modificatore_difesa.soglie
        if not isinstance(s, list) or not all(isinstance(x, list) and len(x) == 2 and all(map(_numero, x)) for x in s):
            p.append("ogni fascia del modificatore difesa deve avere una media e un bonus")
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


def _cifra(n: int | float) -> str:
    """Un numero scritto all'italiana, con il meno tipografico: 100000 -> «100.000», -20 -> «−20», 0.5 -> «0,5»."""
    a = abs(n)
    testo = f"{int(a):,}".replace(",", ".") if a == int(a) else str(a).replace(".", ",")
    return ("−" if n < 0 else "") + testo


def _dentro(chiave: str, valore, tabella: dict = LIMITI) -> bool:
    return tabella[chiave]["min"] <= valore <= tabella[chiave]["max"]


def _frase_limite(chiave: str, tabella: dict = LIMITI) -> str:
    """«il bonus per l'assist deve essere tra 0 e 20»: la frase del limite di `chiave` in `tabella`, con i suoi numeri."""
    return FRASI_LIMITI[chiave].format(min=_cifra(tabella[chiave]["min"]), max=_cifra(tabella[chiave]["max"]))


def _difensori_del_modulo(modulo: str) -> int | None:
    try:
        return modulo_in_numeri(modulo)[0]
    except ValueError:              # (un modulo scritto male lo dice già il controllo dei moduli)
        return None


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


def _controlla(regole: Regole, misure: bool = True, salvate: Regole | None = None) -> Regole:
    """Errore se le regole non vanno: RegoleTroppoGrandi oltre i tetti di misura e RegoleFuoriIntervallo per i numeri fuori dagli
    intervalli (tutti e due solo se `misure`), ValueError per il resto."""
    troppo = regole.problemi_di_misura() if misure else []
    if troppo:
        raise RegoleTroppoGrandi(NON_VALIDE + "\n- " + "\n- ".join(troppo))
    problemi = regole._problemi_di_valore(intervalli=False, salvate=salvate)
    if problemi:
        raise ValueError(NON_VALIDE + "\n- " + "\n- ".join(problemi))
    fuori = regole.problemi_di_intervallo(salvate) if misure else []      # solo con i tipi e gli altri valori a posto
    if fuori:
        raise RegoleFuoriIntervallo(NON_VALIDE + "\n- " + "\n- ".join(fuori))
    return regole


def da_dict(dati: dict[str, Any], misure: bool = True, salvate: Regole | None = None) -> Regole:
    """Le regole dai dati JSON, controllate. `salvate`: quelle che sostituiscono, dalla pagina Regole (PUT /api/regole): i valori
    cambiati rispetto a quelle hanno i limiti della pagina (LIMITI); senza, i limiti di prima (LIMITI_LARGHI)."""
    return _controlla(_da_dict(Regole, dati), misure, salvate)


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
