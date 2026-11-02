"""Le rose della lega salvate su disco (lega/rose.json) e i controlli sulla loro correttezza."""
from __future__ import annotations

import json
import shutil
from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from .frasi import F
from .percorsi import scrivi_sicuro
from .regole import RUOLI, Regole
from .rose import SquadraLetta

# Si può cominciare con la sola propria rosa (2/11/2026): lo dicono l'anteprima delle rose e i controlli del primo avvio.
UNA_SQUADRA = ("Con una sola squadra funzionano formazione e consigli; per gli scambi servono le rose degli altri: "
               "potrai aggiungerle quando vuoi.")


@dataclass
class GiocatoreRosa:
    id: int | None          # codice Fantacalcio.it (None = non riconosciuto)
    nome: str
    ruolo: str | None
    squadra: str | None     # squadra di Serie A (sigla)
    costo: int | None = None
    riconosciuto: str = "esatto"   # come è stato abbinato al listone: esatto, abbreviato, simile, ambiguo, non trovato
    avviso: str = ""


@dataclass
class Squadra:
    nome: str
    giocatori: list[GiocatoreRosa] = field(default_factory=list)
    crediti_residui: int | None = None


@dataclass
class Rose:
    squadre: list[Squadra] = field(default_factory=list)
    mia_squadra: str | None = None
    aggiornato: str = ""
    stagione: str = ""        # la stagione a cui appartengono le rose ("2026-27"), segnata all'importazione

    def squadra(self, nome: str) -> Squadra | None:
        """Cerca una squadra per nome, senza badare a maiuscole e spazi; accetta anche l'inizio del nome."""
        n = nome.strip().lower()
        esatte = [s for s in self.squadre if s.nome.lower() == n]
        if esatte:
            return esatte[0]
        parziali = [s for s in self.squadre if s.nome.lower().startswith(n)]
        return parziali[0] if len(parziali) == 1 else None


def da_import(lette: list[SquadraLetta], precedenti: Rose | None = None, sostituisci_tutto: bool = False) -> Rose:
    """Costruisce le rose dall'importazione.

    Di norma sostituisce solo le squadre presenti nel file e lascia com'erano le altre
    (così si può reimportare anche solo la propria rosa). Con sostituisci_tutto le altre spariscono.
    """
    nuove = []
    for s in lette:
        giocatori = []
        for r in s.righe:
            c = r.esito.calciatore
            avviso = r.esito.avviso
            if r.esito.metodo == "ambiguo":
                avviso = F("rose.potrebbe_essere", elenco=", ".join(f"{a.nome} ({a.ruolo}, {a.squadra})" for a in r.esito.alternative))
            giocatori.append(GiocatoreRosa(
                id=c.id if c else None,
                nome=c.nome if c else r.testo,
                ruolo=r.ruolo or (c.ruolo if c else None),
                squadra=c.squadra if c else r.squadra,
                costo=r.costo,
                riconosciuto=r.esito.metodo,
                avviso=avviso,
            ))
        # se il file non ha i crediti, restano quelli già inseriti a mano
        prima = next((x.crediti_residui for x in precedenti.squadre if x.nome == s.nome), None) if precedenti else None
        nuove.append(Squadra(s.nome, giocatori, s.crediti_residui if s.crediti_residui is not None else prima))
    squadre = nuove
    if precedenti and not sostituisci_tutto:
        per_nome = {s.nome: s for s in nuove}
        squadre = [per_nome.pop(s.nome, s) for s in precedenti.squadre] + list(per_nome.values())
    mia = precedenti.mia_squadra if precedenti else None
    if mia and not any(s.nome == mia for s in squadre):
        mia = None
    return Rose(squadre, mia, datetime.now().isoformat(timespec="seconds"))


def controlla(rose: Rose, regole: Regole) -> list[str]:
    """Avvisi: rose incomplete, giocatori non riconosciuti o riconosciuti solo per somiglianza, doppioni."""
    avvisi = []
    proprietari: dict[int, list[str]] = {}
    for s in rose.squadre:
        conta = Counter(g.ruolo for g in s.giocatori)
        diversi = [f"{r} {conta.get(r, 0)}/{regole.rosa[r]}" for r in RUOLI if conta.get(r, 0) != regole.rosa[r]]
        if diversi:
            avvisi.append(F("rose.diversa", squadra=s.nome, dettaglio=", ".join(diversi)))
        ripetuti = Counter(g.id for g in s.giocatori if g.id is not None)
        for gid, volte in ripetuti.items():
            if volte > 1:
                nome = next(g.nome for g in s.giocatori if g.id == gid)
                avvisi.append(F("rose.doppione", squadra=s.nome, nome=nome, volte=volte))
        for g in s.giocatori:
            if g.id is None:
                motivo = g.avviso or F("rose.motivo_ceduto")
                avvisi.append(F("rose.non_riconosciuto", squadra=s.nome, nome=g.nome, motivo=motivo))
                continue
            if s.nome not in proprietari.setdefault(g.id, []):
                proprietari[g.id].append(s.nome)
            if g.riconosciuto in ("abbreviato", "simile"):
                avvisi.append(F("rose.somiglianza", squadra=s.nome, nome=g.nome, come=F("rose.come_" + g.riconosciuto)))
            if g.avviso:
                avvisi.append(F("rose.avviso_giocatore", squadra=s.nome, nome=g.nome, avviso=g.avviso))
    for gid, squadre in proprietari.items():
        if len(squadre) > 1:
            nome = next(g.nome for s in rose.squadre for g in s.giocatori if g.id == gid)
            avvisi.append(F("rose.in_piu_squadre", nome=nome, squadre=", ".join(squadre)))
    return avvisi


def carica(percorso: Path) -> Rose | None:
    if not percorso.exists():
        return None
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except ValueError:
        raise ValueError(f"Il file {percorso.name} è rovinato: ripristina la copia {percorso.name}.bak o importa di nuovo le rose") from None
    return da_dict(dati)


_CAMPI_GIOCATORE = {f.name for f in fields(GiocatoreRosa)}
FORMA_SBAGLIATA = ("Il file rose.json non ha la forma giusta: ripristina la copia rose.json.bak o un backup, "
                   "oppure importa di nuovo le rose")


def da_dict(dati: dict) -> Rose:
    """Le rose dal loro formato su file (usato anche per controllare un backup prima di ripristinarlo).
    I campi in più (scritti da una versione più nuova dell'app) si ignorano; una forma sbagliata dà un messaggio chiaro."""
    try:
        return Rose(
            squadre=[Squadra(s["nome"], [GiocatoreRosa(**{k: v for k, v in g.items() if k in _CAMPI_GIOCATORE})
                                         for g in s["giocatori"]], s.get("crediti_residui"))
                     for s in dati["squadre"]],
            mia_squadra=dati.get("mia_squadra"),
            aggiornato=dati.get("aggiornato", ""),
            stagione=dati.get("stagione", ""),
        )
    except (KeyError, TypeError, AttributeError):
        raise ValueError(FORMA_SBAGLIATA) from None


def salva(rose: Rose, percorso: Path, copia_di_riserva: bool = False) -> None:
    """Salva le rose. Con copia_di_riserva la versione precedente resta in rose.json.bak."""
    if copia_di_riserva and percorso.exists():
        shutil.copy2(percorso, percorso.with_name(percorso.name + ".bak"))
    scrivi_sicuro(percorso, json.dumps(asdict(rose), ensure_ascii=False, indent=2))
