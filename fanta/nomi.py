"""Riconoscimento dei giocatori quando le fonti scrivono i nomi in modo diverso.

Esempi: "Laurientè" / "Laurienté" / "Lauriente", "Esposito Se." / "Esposito S", "N'Dicka" / "Ndicka".
Anche celle copiate e incollate: "A Martinez L. (INT) 45", "L. Martinez", "#10 Martinez L. ⭐".
E nomi scritti per esteso: "Lautaro Martinez" / "Martinez Lautaro" (il nome proprio comincia con l'iniziale del listone),
"Pulisic C." quando il listone scrive solo "Pulisic", "Christian Pulisic" se si conosce il nome per esteso (`completi`).

Regola d'oro: zero abbinamenti sbagliati dati per sicuri. `esatto` (senza avviso) vuol dire che il nome, tolti ruolo,
squadra, crediti e simboli, è quello del listone; tutto il resto (abbreviato, simile, ambiguo) va controllato.
Due eccezioni, pensate per il testo letto con l'OCR dalle schermate di Leghe:
- errori da lettura automatica che non cambiano il nome (spazi persi o in più, «0» al posto di «O», «1» al posto di «l»/«I»,
  «F P» per «F.P.»): è ancora `esatto`, ma solo se nel listone c'è un solo nome che si scrive così;
- un nome abbreviato («Martinez», «Martinez L», «Esposito F.») con ruolo E squadra indicati che coincidono col listone, e un solo
  giocatore che va bene: diventa `esatto`. Se ruolo o squadra NON coincidono non è mai `esatto` senza avviso.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from .frasi import F, elenco
from .listone import Calciatore


# lettere che la scomposizione Unicode non semplifica da sola
_LETTERE_SPECIALI = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "ß": "ss", "ł": "l", "Ł": "L",
                                   "đ": "d", "Đ": "D", "ð": "d", "þ": "th", "ı": "i", "œ": "oe"})


def normalizza(testo: str) -> str:
    """Minuscolo, senza accenti, punti, apostrofi e trattini: 'N'Dicka' -> 'ndicka', 'Esposito Se.' -> 'esposito se'."""
    t = str(testo).translate(_LETTERE_SPECIALI)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"['’`]", "", t)          # N'Dicka -> ndicka
    t = re.sub(r"[^a-z0-9]+", " ", t)    # punti, trattini, ecc. -> spazio
    return " ".join(t.split())


def _abbreviazione_compatibile(a: str, b: str) -> bool:
    """'esposito s' e 'esposito se': stesso cognome, iniziali compatibili (una è l'inizio dell'altra).
    Anche con meno iniziali: 'esposito f' e 'esposito f p' (l'OCR o chi scrive ne ha persa una)."""
    ta, tb = a.split(), b.split()
    if len(ta) < 2 or len(tb) < 2 or ta == tb:
        return False
    if len(ta) == len(tb) and ta[0] == tb[0]:
        return all(x.startswith(y) or y.startswith(x) for x, y in zip(ta[1:], tb[1:]))
    ca, ia = _cognome_e_iniziali(a)
    cb, ib = _cognome_e_iniziali(b)
    if ca != cb or not ia or not ib:
        return False
    return all(x.startswith(y) or y.startswith(x) for x, y in zip(ia, ib))


def compatta(n: str) -> list[str]:
    """Le chiavi di un nome già normalizzato senza gli errori tipici dell'OCR: niente spazi ('n dicka' = 'ndicka',
    'esposito f p' = 'esposito fp'), «0» letto al posto di «o», «1» al posto di «l» o «i». Più chiavi se l'«1» è incerto."""
    t = "".join(n.split()).replace("0", "o")
    return list(dict.fromkeys([t.replace("1", "l"), t.replace("1", "i")]))


def _lettere_scambiate(a: str, b: str) -> bool:
    """'barlela' e 'barella': uguali tranne due lettere vicine scambiate."""
    if len(a) != len(b) or a == b:
        return False
    diverse = [i for i in range(len(a)) if a[i] != b[i]]
    return (len(diverse) == 2 and diverse[1] == diverse[0] + 1
            and a[diverse[0]] == b[diverse[1]] and a[diverse[1]] == b[diverse[0]])


def _cognome_e_iniziali(n: str) -> tuple[list[str], list[str]]:
    """'martinez l' -> (['martinez'], ['l']): in fondo, le parole di una o due lettere sono iniziali."""
    parole = n.split()
    i = len(parole)
    while i > 1 and len(parole[i - 1]) <= 2:
        i -= 1
    return parole[:i], parole[i:]


def _iniziali_diverse(a: str, b: str) -> bool:
    """'martinez a' e 'martinez l': stesso cognome ma iniziali che non c'entrano tra loro, quindi due persone diverse."""
    ca, ia = _cognome_e_iniziali(a)
    cb, ib = _cognome_e_iniziali(b)
    if ca != cb or not ia or not ib:
        return False
    return not all(x.startswith(y) or y.startswith(x) for x, y in zip(ia, ib))


def _propri_compatibili(iniziali: list[str], propri: list[str]) -> bool:
    """Le iniziali del listone (['l'], ['jo'], ['f', 'p']) sono l'inizio dei nomi propri scritti per esteso, in ordine."""
    return 0 < len(iniziali) <= len(propri) and all(p.startswith(i) for i, p in zip(iniziali, propri))


# pulizia delle celle copiate e incollate
_RUOLI = {"p": "P", "por": "P", "portiere": "P", "d": "D", "dif": "D", "difensore": "D",
          "c": "C", "cen": "C", "centrocampista": "C", "a": "A", "att": "A", "attaccante": "A"}
_PAROLE_CREDITI = {"cr", "crediti", "cred", "fm", "mln", "milioni"}
_PREFISSI_SQUADRA = {"hellas", "ac", "as", "fc", "ss", "ssc", "us", "acf", "afc"}
_SOLO_NUMERO = re.compile(r"(n )?\d+( (cr|crediti|cred|fm|mln|milioni))?")
_PARENTESI = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")
_SEPARATORI = re.compile(r"\s+[-–—|/]\s+|\s*[|\t]\s*|\s+[–—]|[–—]\s+")
_INIZIALI_DAVANTI = re.compile(r"((?:[^\W\d_]{1,2}\.\s*)+)\S")
_CON_INIZIALI = re.compile(r"(.+?)\s+((?:[^\W\d_]{1,2}\.)+)")
MAX_TESTO = 200                  # come MAX_TESTO_CELLA delle rose: una cella con un nome vero è molto più corta


@dataclass
class Esito:
    calciatore: Calciatore | None
    metodo: str                    # esatto, abbreviato, simile, ambiguo, non trovato
    alternative: list[Calciatore] = field(default_factory=list)
    avviso: str = ""               # es. "ruolo diverso: nel file C, nel listone A"

    @property
    def trovato(self) -> bool:
        return self.calciatore is not None


def _senza_doppi(calciatori: list[Calciatore]) -> list[Calciatore]:
    return list({id(c): c for c in calciatori}.values())


class TempoScaduto(Exception):
    """Il riconoscimento ha superato il suo tempo massimo (vedi `Indice(scaduto=...)`): si ferma al nome che stava cercando."""


class Indice:
    """Cerca i giocatori del listone per nome, aiutandosi con squadra e ruolo quando servono."""

    def __init__(self, calciatori: list[Calciatore], completi: dict[int, str] | None = None, *,
                 scaduto: Callable[[], bool] | None = None):
        """`completi` (facoltativo): nome e cognome per esteso di alcuni giocatori, {codice: "Lautaro Martínez"},
        da un'altra fonte già abbinata al listone (`listone.nomi_completi`). Servono solo a proporre, mai a dare per sicuro.
        `scaduto` (facoltativo): guardato prima di ogni nome cercato; se è vero `cerca` alza TempoScaduto (vedi
        `limiti.tempo_riconoscimento`: un'importazione di rose non riconosce giocatori all'infinito)."""
        self.scaduto = scaduto
        self.calciatori = calciatori
        self._per_nome: dict[str, list[Calciatore]] = defaultdict(list)
        for c in calciatori:
            self._per_nome[normalizza(c.nome)].append(c)
        self._nomi = list(self._per_nome)
        self._squadre = set()
        for c in calciatori:
            self._squadre |= {normalizza(c.squadra), normalizza(c.squadra_slug)}
        self._squadre.discard("")
        # «martinez» -> chi nel listone è «Martinez L.», «Martinez Jo.»; parole in ordine -> nomi (per gli ordini invertiti)
        self._cognomi: dict[str, list[Calciatore]] = defaultdict(list)
        for c in calciatori:
            m = _CON_INIZIALI.fullmatch(str(c.nome).strip())
            if m:
                self._cognomi[normalizza(m.group(1))].append(c)
        # chiave senza spazi né errori da OCR -> nomi del listone (vale solo se è di un nome solo)
        self._compatti: dict[str, set[str]] = defaultdict(set)
        for k in self._nomi:
            for chiave in compatta(k):
                self._compatti[chiave].add(k)
        self._per_parole: dict[tuple, list[str]] = defaultdict(list)
        for k in self._nomi:
            self._per_parole[tuple(sorted(k.split()))].append(k)
        # nome e cognome per esteso, in qualunque ordine: («lautaro», «martinez») -> Martinez L.
        self._completi: dict[tuple, list[Calciatore]] = defaultdict(list)
        per_codice = {c.id: c for c in calciatori}
        for codice, testo in (completi or {}).items():
            c, parole = per_codice.get(codice), normalizza(testo).split()
            if c is not None and len(parole) >= 2:
                self._completi[tuple(sorted(parole))].append(c)

    def e_squadra_serie_a(self, testo: str) -> bool:
        """«INT», «Inter», ma anche «Hellas Verona», «AC Milan»."""
        return self._e_squadra_norm(normalizza(testo))

    @staticmethod
    def squadra_corrisponde(testo: str, c: Calciatore) -> bool:
        n = normalizza(testo)
        if not n:
            return True
        slug = normalizza(c.squadra_slug)
        sigla = normalizza(c.squadra)
        return n in (sigla, slug) or n.startswith(sigla) or (len(n) >= 3 and slug.startswith(n)) or slug in n

    def _scegli(self, candidati: list[Calciatore], squadra: str | None,
                ruolo: str | None) -> tuple[list[Calciatore], list[str]]:
        """Restringe i candidati con squadra e ruolo. Un filtro che non lascia nessuno viene ignorato,
        ma lo si segnala (es. giocatore trasferito o ruolo cambiato)."""
        discordanze = []
        for nome_filtro, valore, filtro in (
            ("squadra", squadra, (lambda c: self.squadra_corrisponde(squadra, c))),
            ("ruolo", ruolo, (lambda c: c.ruolo == ruolo)),
        ):
            if not valore:
                continue
            ristretti = [c for c in candidati if filtro(c)]
            if ristretti:
                candidati = ristretti
            else:
                discordanze.append(nome_filtro)
        return candidati, discordanze

    # ---------- pulizia della cella: ruolo, squadra, crediti, numeri e iniziali davanti ----------
    def _e_squadra_norm(self, n: str) -> bool:
        parole = n.split()
        return bool(n) and (n in self._squadre or (len(parole) == 2 and parole[0] in _PREFISSI_SQUADRA
                                                  and parole[1] in self._squadre))

    def _campo(self, testo: str, pezzi: dict) -> str:
        """Un pezzo della cella: se è una squadra, un ruolo o un numero finisce tra gli indizi, altrimenti resta nel nome."""
        n = normalizza(testo)
        if not n or _SOLO_NUMERO.fullmatch(n):
            return ""
        if n in _RUOLI:
            pezzi.setdefault("ruolo", _RUOLI[n])
            return ""
        if self._e_squadra_norm(n):
            pezzi.setdefault("squadra", n)
            return ""
        return testo

    def _interpretazioni(self, testo: str) -> list[tuple[str, str | None, str | None]]:
        """I modi di leggere una cella sporca: [(nome normalizzato, squadra trovata, ruolo trovato)].

        «A Martinez L. (INT) 45» -> ("martinez l", "int", "A"); «L. Martinez» -> ("martinez l", None, None).
        Una lettera sola davanti senza punto («C Rossi») può essere il ruolo o l'iniziale: si tengono le due letture."""
        pezzi: dict = {}
        t = _PARENTESI.sub(lambda m: " " + self._campo(m.group(1) or m.group(2) or "", pezzi) + " ", str(testo)[:MAX_TESTO])
        t = " ".join(self._campo(c, pezzi) for c in _SEPARATORI.split(t))
        m = _INIZIALI_DAVANTI.match(t.strip())            # iniziali puntate davanti: «F.P. Esposito», «Jo. Martinez»
        puntate = normalizza(m.group(1)).split() if m else []
        parole = [p for p in normalizza(t).split() if not p.isdigit()]       # crediti e numeri di maglia
        if len(parole) > 1 and parole[-1] in _PAROLE_CREDITI:
            parole = parole[:-1]
        for in_fondo in (True, False):                    # squadra attaccata alla fine o all'inizio
            for k in (2, 1):
                pezzo = parole[-k:] if in_fondo else parole[:k]
                if len(parole) > k and self._e_squadra_norm(" ".join(pezzo)):
                    pezzi.setdefault("squadra", " ".join(pezzo))
                    parole = parole[:-k] if in_fondo else parole[k:]
                    break
        letture: list[tuple[list[str], str | None]] = []
        if len(parole) > 1 and parole[0] in _RUOLI and not (puntate and puntate[0] == parole[0]):
            letture.append((parole[1:], _RUOLI[parole[0]]))
            if len(parole[0]) == 1:                        # «C Rossi»: C può essere anche l'iniziale
                letture.append((parole, None))
        else:
            letture.append((parole, None))
        risultato = []
        for p, ruolo in letture:
            i = 0                                          # iniziali davanti spostate in fondo, come nel listone
            while i < len(p) - 1 and (len(p[i]) == 1 or (p[i] in puntate and len(p[i]) <= 2)):
                i += 1
            if 0 < i < len(p) and len(p[i]) >= 3:
                p = p[i:] + p[:i]
            if p:
                risultato.append((" ".join(p), pezzi.get("squadra"), ruolo or pezzi.get("ruolo")))
        return list(dict.fromkeys(risultato))

    # ---------- i modi di trovare i candidati, dal più sicuro al meno sicuro ----------
    def _compatto(self, n: str) -> list[Calciatore]:
        """«NDicka» o «N Dicka» per «N'Dicka», «K0ne M» per «Koné M.», «Esposito FP» per «Esposito F.P.»: stesse lettere,
        cambia solo come le ha lette l'OCR. Solo se la chiave porta a un nome solo del listone."""
        nomi = {k for chiave in compatta(n) for k in self._compatti.get(chiave, ())}
        return list(self._per_nome[next(iter(nomi))]) if len(nomi) == 1 else []

    def _abbreviati(self, n: str) -> list[Calciatore]:
        return [c for k in self._nomi if _abbreviazione_compatibile(n, k) for c in self._per_nome[k]]

    def _solo_cognome(self, n: str) -> list[Calciatore]:
        """«Pellegrini» quando il listone scrive «Pellegrini Lu.» (con più omonimi tornano tutti: sarà un dubbio)."""
        return list(self._cognomi.get(n, [])) if len(n) >= 4 else []

    def _cognome_nudo(self, n: str) -> list[Calciatore]:
        """«Pulisic C.» quando il listone scrive solo «Pulisic» (il cognome è di uno solo, l'iniziale non si sa)."""
        cognome, iniziali = _cognome_e_iniziali(n)
        return list(self._per_nome.get(" ".join(cognome), [])) if iniziali and len(" ".join(cognome)) >= 4 else []

    def _per_esteso(self, n: str) -> list[Calciatore]:
        """«Christian Pulisic», «Martinez Lautaro»: il nome per esteso conosciuto da un'altra fonte, in qualunque ordine."""
        return list(self._completi.get(tuple(sorted(n.split())), []))

    def _nome_e_cognome(self, n: str) -> list[Calciatore]:
        """«Lautaro Martinez» o «Martinez Lautaro» per «Martinez L.»: i nomi propri cominciano con le iniziali del listone.
        Il cognome nudo non basta («Real Barella» non è Barella): serve l'iniziale che corrisponde. Se però c'è anche chi ha
        quel cognome senza iniziale («Colombo» e «Colombo L.»), il nome proprio può essere suo: allora è un dubbio tra i due."""
        parole = n.split()
        trovati = []
        for k in range(1, len(parole)):
            for cognome, propri in ((parole[k:], parole[:k]), (parole[:k], parole[k:])):
                if any(len(p) < 3 for p in propri):
                    continue                               # una o due lettere sono iniziali: ci pensano gli altri modi
                compatibili = []
                for c in self._cognomi.get(" ".join(cognome), []):
                    m = _CON_INIZIALI.fullmatch(str(c.nome).strip())
                    if m and _propri_compatibili(normalizza(m.group(2)).split(), propri):
                        compatibili.append(c)
                if compatibili:
                    trovati += compatibili + self._per_nome.get(" ".join(cognome), [])
        return _senza_doppi(trovati)

    def _proposte(self, letture: list[str]) -> list[Calciatore]:
        """Per chi non è stato trovato, fino a 3 nomi che gli somigliano (solo suggerimenti da scegliere a mano):
        il nome intero, poi ogni parola lunga come possibile cognome («Dimarko Federico» -> Dimarco)."""
        trovati: list[Calciatore] = []
        for n in letture:
            for k in difflib.get_close_matches(n, self._nomi, n=3, cutoff=0.75):
                trovati += self._per_nome[k]
            for parola in (p for p in n.split() if len(p) >= 4):
                for k in difflib.get_close_matches(parola, self._nomi, n=2, cutoff=0.8):
                    trovati += self._per_nome[k]
                for k in difflib.get_close_matches(parola, list(self._cognomi), n=2, cutoff=0.8):
                    trovati += self._cognomi[k]
        return _senza_doppi(trovati)[:3]

    def _invertito(self, n: str) -> list[Calciatore]:
        """«Mbeki Kolo» per «Kolo Mbeki»: stesse parole in un altro ordine."""
        parole = n.split()
        if len(parole) < 2:
            return []
        return [c for k in self._per_parole.get(tuple(sorted(parole)), []) if k != n for c in self._per_nome[k]]

    def _simili(self, n: str) -> list[Calciatore]:
        """Un errore di battitura: nome molto somigliante, o due lettere vicine scambiate («Barlela»)."""
        chiavi = difflib.get_close_matches(n, self._nomi, n=3, cutoff=0.88)
        if len(n) >= 5:
            chiavi += [k for k in self._nomi if _lettere_scambiate(n, k)]
        return [c for k in dict.fromkeys(chiavi) if not _iniziali_diverse(n, k) for c in self._per_nome[k]]

    def cerca(self, nome: str, squadra: str | None = None, ruolo: str | None = None) -> Esito:
        if self.scaduto is not None and self.scaduto():
            raise TempoScaduto
        nome = str(nome)[:MAX_TESTO]                       # si legge solo l'inizio di una cella lunghissima
        n = normalizza(nome)
        if not n:
            return Esito(None, "non trovato")
        # squadra e ruolo passati da chi chiama valgono più di quelli trovati dentro la cella
        letture = [(k, squadra or sq, ruolo or ru) for k, sq, ru in self._interpretazioni(nome)]
        for trova in (lambda k: self._per_nome.get(k, []), self._compatto):    # il nome scritto pari pari: come sempre
            if trovati := trova(n):
                return self._con_altri(self._decidi("esatto", [(trovati, squadra, ruolo)]), letture)
        for metodo, trova in (
            ("esatto", lambda k: self._per_nome.get(k, [])),
            ("esatto", self._compatto),
            ("abbreviato", self._abbreviati),
            ("abbreviato", self._solo_cognome),
            ("abbreviato", self._cognome_nudo),
            ("simile", self._invertito),
            ("abbreviato", self._per_esteso),
            ("abbreviato", self._nome_e_cognome),
            ("simile", self._simili),
        ):
            gruppi = [(trovati, sq, ru) for k, sq, ru in letture if (trovati := trova(k))]
            if gruppi:
                esito = self._decidi(metodo, gruppi)
                return self._con_altri(esito, letture) if metodo == "esatto" else esito
        return Esito(None, "non trovato", self._proposte([k for k, _, _ in letture]))

    def _con_altri(self, esito: Esito, letture: list[tuple[str, str | None, str | None]]) -> Esito:
        """Nome uguale nel listone ma con ruolo o squadra diversi: se un altro giocatore dallo stesso cognome ha proprio quel
        ruolo e quella squadra («Thuram» C Juventus quando «Thuram» è A dell'Inter e «Thuram K.» C della Juventus: l'OCR ha
        perso l'iniziale), è un dubbio tra i due, con lui per primo. Mai un abbinamento sicuro."""
        if esito.calciatore is None or not esito.avviso:
            return esito
        altri = []
        for k, sq, ru in letture:
            if not (sq and ru):
                continue
            for trova in (self._abbreviati, self._solo_cognome, self._cognome_nudo):
                altri += [c for c in trova(k)
                          if c is not esito.calciatore and c.ruolo == ru and self.squadra_corrisponde(sq, c)]
        altri = _senza_doppi(altri)
        return Esito(None, "ambiguo", altri + [esito.calciatore]) if altri else esito

    def _decidi(self, metodo: str, gruppi: list[tuple[list[Calciatore], str | None, str | None]]) -> Esito:
        """Dai candidati di ogni lettura della cella a un esito. Letture che portano a giocatori diversi: dubbio."""
        scelte = [(*self._scegli(_senza_doppi(candidati), squadra, ruolo), squadra, ruolo)
                  for candidati, squadra, ruolo in gruppi]
        tutti = _senza_doppi([c for scelti, *_ in scelte for c in scelti])
        if len(tutti) > 1:
            return Esito(None, "ambiguo", tutti)
        c = tutti[0]
        _, discordanze, squadra, ruolo = min(scelte, key=lambda s: len(s[1]))
        if discordanze and metodo != "esatto":
            # nome solo somigliante E ruolo/squadra diversi: troppo rischioso, meglio chiedere
            return Esito(None, "ambiguo", [c])
        if metodo == "abbreviato" and squadra and ruolo and not discordanze:
            # nome abbreviato, ma ruolo E squadra indicati sono i suoi e nessun altro va bene: è lui
            metodo = "esatto"
        avviso = elenco([
            F("nomi.ruolo_diverso", indicato=ruolo, listone=c.ruolo) if d == "ruolo"
            else F("nomi.squadra_diversa", indicata=squadra, listone=c.squadra) for d in discordanze], sep="; ")
        return Esito(c, metodo, avviso=avviso)
