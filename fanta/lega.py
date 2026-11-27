"""Le rose della lega salvate su disco (lega/rose.json) e i controlli sulla loro correttezza."""
from __future__ import annotations

import json
import math
import re
import shutil
from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from . import memoria_file
from .frasi import F, elenco, nome_club, nome_ruolo
from .percorsi import scrivi_sicuro, utente_della_cartella
from .regole import RUOLI, Regole
from .rose import SquadraLetta

# Si può cominciare con la sola propria rosa (2/11/2026): lo dicono l'anteprima delle rose e i controlli del primo avvio. Gli scambi
# non ci sono più (#615): le rose degli altri servono a guardare le altre squadre (#873, come docs/GUIDA-UTENTE.md).
UNA_SQUADRA = ("Con una sola squadra funzionano formazione e consigli; le rose degli altri servono a guardare le altre squadre: "
               "puoi aggiungerle quando vuoi.")
# Anteprima e importazione con il file delle rose che non si legge più: si riparte dalle squadre del file (server._rose_di_prima).
ROSE_ROVINATE = "Le rose salvate finora non si leggono più: l'importazione tiene solo le squadre di questo file."


@dataclass
class GiocatoreRosa:
    id: int | None          # codice Fantacalcio.it (None = non riconosciuto)
    nome: str
    ruolo: str | None
    squadra: str | None     # squadra di Serie A (sigla)
    costo: int | None = None
    riconosciuto: str = "esatto"   # come è stato abbinato al listone: esatto, abbreviato, simile, ambiguo, non trovato, manuale
    avviso: str = ""
    # il nome com'era scritto nel file, se diverso da `nome` («Pellegrini» per «Pellegrini Lu.»): alla prossima importazione
    # dello stesso file la scelta fatta su quel nome torna già risolta (anteprima_rose.riusa_scelte)
    testo: str | None = None


@dataclass
class Squadra:
    nome: str
    giocatori: list[GiocatoreRosa] = field(default_factory=list)
    crediti_residui: int | None = None
    nome_importato: str | None = None   # il nome scritto nel file di Leghe, se l'utente l'ha cambiato nell'app (rinomina)


@dataclass
class Rose:
    squadre: list[Squadra] = field(default_factory=list)
    mia_squadra: str | None = None
    aggiornato: str = ""
    stagione: str = ""        # la stagione a cui appartengono le rose ("2026-27"), segnata all'importazione
    # Di quale account è la lega: il suo numero interno, letto dalla cartella del file (`carica`, `percorsi.utente_della_cartella`);
    # None senza account. Non cambia mai (il nome sì) e non si salva: tiene separate le consigliate ricordate di due account (#780).
    di_utente: int | None = field(default=None, compare=False)

    def squadra(self, nome: str) -> Squadra | None:
        """Cerca una squadra per nome, senza badare a maiuscole e spazi; accetta anche l'inizio del nome."""
        n = nome.strip().lower()
        esatte = [s for s in self.squadre if s.nome.lower() == n]
        if esatte:
            return esatte[0]
        parziali = [s for s in self.squadre if s.nome.lower().startswith(n)]
        return parziali[0] if len(parziali) == 1 else None


def nomi_rinominati(lette: list[SquadraLetta], precedenti: Rose | None) -> None:
    """Le squadre lette che l'utente ha rinominato nell'app prendono il nome dell'app: su Leghe resta il nome vecchio, e alla
    reimportazione deve aggiornarsi la stessa squadra (con «la tua squadra»), non nascerne una nuova. Da chiamare subito dopo la
    lettura, prima delle scelte dell'utente sui dubbi (l'anteprima mostra già il nome dell'app)."""
    if not precedenti:
        return
    nomi = {s.nome for s in precedenti.squadre}
    rinominate = {s.nome_importato: s.nome for s in precedenti.squadre if s.nome_importato}
    for s in lette:
        if s.nome not in nomi and s.nome in rinominate:
            s.nome = rinominate[s.nome]


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
                avviso = potrebbe_essere(r.esito.alternative)
            nome = c.nome if c else r.testo
            giocatori.append(GiocatoreRosa(
                id=c.id if c else None,
                nome=nome,
                ruolo=r.ruolo or (c.ruolo if c else None),
                squadra=c.squadra if c else r.squadra,
                costo=r.costo,
                riconosciuto=r.esito.metodo,
                avviso=avviso,
                testo=r.testo if r.testo != nome else None,
            ))
        # se il file non ha i crediti, restano quelli già inseriti a mano
        vecchia = next((x for x in precedenti.squadre if x.nome == s.nome), None) if precedenti else None
        prima = vecchia.crediti_residui if vecchia else None
        nuove.append(Squadra(s.nome, giocatori, s.crediti_residui if s.crediti_residui is not None else prima,
                             vecchia.nome_importato if vecchia else None))
    squadre = nuove
    if precedenti and not sostituisci_tutto:
        per_nome = {s.nome: s for s in nuove}
        squadre = [per_nome.pop(s.nome, s) for s in precedenti.squadre] + list(per_nome.values())
    mia = precedenti.mia_squadra if precedenti else None
    if mia and not any(s.nome == mia for s in squadre):
        mia = None
    return Rose(squadre, mia, datetime.now().isoformat(timespec="seconds"))


def potrebbe_essere(alternative) -> str:
    """«potrebbe essere uno fra Rossi (difensore, Genoa) e Rossi (attaccante, Lecce)»: i candidati di un dubbio, con ruolo e
    squadra per esteso (niente sigle, collaudo del 26/11)."""
    candidati = [F("rose.candidato", nome=a.nome, ruolo=nome_ruolo(a.ruolo), squadra=nome_club(a.squadra, a.squadra_slug))
                 for a in alternative]
    return F("rose.potrebbe_essere_uno_fra" if len(candidati) > 1 else "rose.potrebbe_essere", elenco=elenco(candidati, con_e=True))


POSTI_DEL_RUOLO = {"P": "rose.portieri", "D": "rose.difensori", "C": "rose.centrocampisti", "A": "rose.attaccanti"}   # «2 portieri»


def problemi_rosa(s: Squadra, regole: Regole) -> list[str]:
    """Cosa non torna nella rosa con le regole, in parole come l'anteprima: «Mia: mancano 1 portiere e 4 difensori.»,
    «Mia: 1 attaccante in più.», «Mia: 2 giocatori senza ruolo.». Vuoto se la rosa è giusta. Fra i giocatori senza ruolo non
    si contano quelli non riconosciuti: hanno già la loro frase (`rose.non_riconosciuto`), un fatto si dice una volta."""
    conta = Counter(g.ruolo for g in s.giocatori)
    mancano = [(r, regole.rosa[r] - conta.get(r, 0)) for r in RUOLI if conta.get(r, 0) < regole.rosa[r]]
    in_piu = [(r, conta.get(r, 0) - regole.rosa[r]) for r in RUOLI if conta.get(r, 0) > regole.rosa[r]]
    senza_ruolo = sum(1 for g in s.giocatori if g.ruolo not in RUOLI and g.id is not None)
    avvisi = []
    if mancano:
        avvisi.append(F("rose.mancano_in_squadra", squadra=s.nome, n=sum(n for _, n in mancano),
                        elenco=elenco([F(POSTI_DEL_RUOLO[r], n=n) for r, n in mancano], con_e=True)))
    if in_piu:
        avvisi.append(F("rose.in_piu_in_squadra", squadra=s.nome, elenco=elenco([F(POSTI_DEL_RUOLO[r], n=n) for r, n in in_piu], con_e=True)))
    if senza_ruolo:
        avvisi.append(F("rose.senza_ruolo_in_squadra", squadra=s.nome, n=senza_ruolo))
    return avvisi


# le chiavi degli avvisi di `problemi_rosa`: chi deve sapere se una rosa non torna con le regole (onboarding.controlli)
CHIAVI_ROSA_DIVERSA = ("rose.mancano_in_squadra", "rose.in_piu_in_squadra", "rose.senza_ruolo_in_squadra")


def controlla(rose: Rose, regole: Regole, squadre: set[str] | None = None) -> list[str]:
    """Avvisi: rose incomplete, giocatori non riconosciuti o riconosciuti solo per somiglianza, doppioni. `squadre`: solo
    quelle (per l'esito di un'importazione, le squadre del file: collaudo del 26/11); un giocatore in più squadre si dice se
    una di loro è fra queste."""
    avvisi = []
    proprietari: dict[int, list[str]] = {}
    for s in rose.squadre:
        for g in s.giocatori:
            if g.id is not None and s.nome not in proprietari.setdefault(g.id, []):
                proprietari[g.id].append(s.nome)
        if squadre is not None and s.nome not in squadre:
            continue
        avvisi += problemi_rosa(s, regole)
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
            if g.riconosciuto in ("abbreviato", "simile"):
                avvisi.append(F("rose.somiglianza", squadra=s.nome, nome=g.nome, come=F("rose.come_" + g.riconosciuto)))
            if g.avviso:
                avvisi.append(F("rose.avviso_giocatore", squadra=s.nome, nome=g.nome, avviso=g.avviso))
    for gid, dove in proprietari.items():
        if len(dove) > 1 and (squadre is None or set(dove) & squadre):
            nome = next(g.nome for s in rose.squadre for g in s.giocatori if g.id == gid)
            avvisi.append(F("rose.in_piu_squadre", nome=nome, squadre=", ".join(dove)))
    return avvisi


def carica(percorso: Path) -> Rose | None:
    """Le rose del file (None se non c'è), trasformate una volta finché il contenuto non cambia (`memoria_file`, #907): ogni
    chiamata riceve un oggetto suo, da modificare liberamente."""
    if not percorso.exists():
        return None
    rose = memoria_file.leggi(percorso, "rose", lambda contenuto: _da_contenuto(contenuto, percorso.name))
    rose.di_utente = utente_della_cartella(percorso)
    return rose


def _da_contenuto(contenuto: bytes, nome: str) -> Rose:
    try:
        dati = json.loads(contenuto.decode("utf-8"))
    except ValueError:
        raise ValueError(f"Il file {nome} è rovinato: ripristina la copia {nome}.bak o importa di nuovo le rose.") from None
    return da_dict(dati)


_CAMPI_GIOCATORE = {f.name for f in fields(GiocatoreRosa)}
FORMA_SBAGLIATA = ("Il file rose.json non ha la forma giusta: ripristina la copia rose.json.bak o un backup, "
                   "oppure importa di nuovo le rose.")
_STAGIONE = re.compile(r"[0-9]{4}-[0-9]{2}")       # «2026-27», come aggiorna.Stagione.codice


def stagione_valida(testo: object) -> bool:
    """Vero solo per un nome di stagione come «2026-27». Serve anche come nome della cartella dell'archivio (stagione.py)."""
    return isinstance(testo, str) and _STAGIONE.fullmatch(testo) is not None


def _testo_o_niente(v: object) -> bool:
    return v is None or isinstance(v, str)


def _numero_o_niente(v: object) -> bool:
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))


def _codice(v: object) -> bool:
    return v is None or (isinstance(v, int) and not isinstance(v, bool))


# il tipo di ogni campo di un giocatore, come lo scrive l'app (i campi che mancano prendono il valore di base)
_TIPI_GIOCATORE = {"id": _codice, "nome": lambda v: isinstance(v, str), "ruolo": _testo_o_niente, "squadra": _testo_o_niente,
                   "costo": _numero_o_niente, "riconosciuto": lambda v: isinstance(v, str), "avviso": lambda v: isinstance(v, str),
                   "testo": _testo_o_niente}


def _giocatore(g: dict) -> GiocatoreRosa:
    campi = {k: v for k, v in g.items() if k in _CAMPI_GIOCATORE}
    if not all(_TIPI_GIOCATORE[k](v) for k, v in campi.items()):
        raise TypeError("tipo sbagliato")
    return GiocatoreRosa(**campi)


def _squadra(s: dict) -> Squadra:
    nome, giocatori, crediti, importato = s["nome"], s["giocatori"], s.get("crediti_residui"), s.get("nome_importato") or None
    if not isinstance(nome, str) or not isinstance(giocatori, list) or not _numero_o_niente(crediti) or not _testo_o_niente(importato):
        raise TypeError("tipo sbagliato")
    return Squadra(nome, [_giocatore(g) for g in giocatori], crediti, importato)


def da_dict(dati: dict) -> Rose:
    """Le rose dal loro formato su file (usato anche per controllare un backup prima di ripristinarlo).
    I campi in più (scritti da una versione più nuova dell'app) si ignorano; una forma sbagliata (anche un campo del tipo
    sbagliato, per esempio un nome che non è un testo) dà un messaggio chiaro.
    `stagione` può mancare (rose di prima) ma, se c'è, è un nome di stagione come «2026-27»."""
    stagione = dati.get("stagione") if isinstance(dati, dict) else None
    if stagione not in (None, "") and not stagione_valida(stagione):
        raise ValueError(FORMA_SBAGLIATA)
    try:
        squadre, mia, aggiornato = dati["squadre"], dati.get("mia_squadra"), dati.get("aggiornato")
        aggiornato = "" if aggiornato is None else aggiornato
        if not isinstance(squadre, list) or not _testo_o_niente(mia) or not isinstance(aggiornato, str):
            raise TypeError("tipo sbagliato")
        return Rose(squadre=[_squadra(s) for s in squadre], mia_squadra=mia, aggiornato=aggiornato, stagione=stagione or "")
    except (KeyError, TypeError, AttributeError):
        raise ValueError(FORMA_SBAGLIATA) from None


def salva(rose: Rose, percorso: Path, copia_di_riserva: bool = False) -> None:
    """Salva le rose. Con copia_di_riserva la versione precedente resta in rose.json.bak."""
    if copia_di_riserva and percorso.exists():
        shutil.copy2(percorso, percorso.with_name(percorso.name + ".bak"))
    dati = asdict(rose)
    dati.pop("di_utente")                          # viene dalla cartella, non dal file
    scrivi_sicuro(percorso, json.dumps(dati, ensure_ascii=False, indent=2))
