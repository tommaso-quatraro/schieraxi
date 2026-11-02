"""Corpus di prova per il riconoscimento dei nomi (`fanta/nomi.py`).

Da un listone genera i modi in cui la gente scrive davvero i nomi dei calciatori (maiuscole, senza accenti, «L. Martinez»,
squadra e crediti attaccati, emoji, spazi strani, un errore di battitura...) e misura cosa risponde `Indice.cerca`.
Il listone di prova è INVENTATO (nomi di fantasia, sigle delle squadre di Serie A); `prove/misura_nomi.py` usa lo stesso
corpus anche sul listone vero salvato in locale, senza scrivere nomi da nessuna parte.

Regola d'oro: zero abbinamenti sbagliati dati per sicuri. «Sicuro» = metodo `esatto` senza avvisi (come l'anteprima delle rose).
"""
from __future__ import annotations

import random
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from fanta.listone import Calciatore
from fanta.nomi import Indice, normalizza

SQUADRE = {"ATA": "atalanta", "BOL": "bologna", "CAG": "cagliari", "COM": "como", "CRE": "cremonese", "FIO": "fiorentina",
           "GEN": "genoa", "INT": "inter", "JUV": "juventus", "LAZ": "lazio", "LEC": "lecce", "MIL": "milan",
           "NAP": "napoli", "PAR": "parma", "PIS": "pisa", "ROM": "roma", "SAS": "sassuolo", "TOR": "torino",
           "UDI": "udinese", "VER": "verona"}

# nomi di fantasia scelti per mettere in difficoltà il riconoscimento (stessi schemi del listone vero)
_DIFFICILI = [
    # omonimi nella stessa squadra, distinti dall'iniziale
    ("Ferrandi L.", "A", "INT"), ("Ferrandi Jo.", "P", "INT"),
    ("Calvisi Se.", "A", "INT"), ("Calvisi F.P.", "A", "INT"),
    # omonimi in squadre diverse
    ("Mbenda P.", "D", "FIO"), ("Mbenda N.", "C", "TOR"),
    ("Mbaye T.", "D", "LEC"), ("Mbaye I.", "C", "CAG"),
    ("Pellandini Lu.", "D", "LAZ"), ("Pellandini Lo.", "C", "ROM"),
    ("Okafor S.", "A", "MIL"), ("Okafor B.", "D", "PIS"),
    ("Rodrigo Ja.", "C", "COM"), ("Rodrigo Ju.", "D", "COM"),
    # stesso nome identico, ruoli e squadre diversi
    ("Rosati", "D", "GEN"), ("Rosati", "A", "LEC"),
    # il nome nudo è di un giocatore, con l'iniziale di un altro
    ("Bortolan", "A", "INT"), ("Bortolan K.", "C", "JUV"),
    # apostrofi
    ("D'Ambrogi", "D", "NAP"), ("Dell'Orsetto", "P", "SAS"), ("N'Gassa", "D", "ROM"), ("N'Diaro", "A", "PAR"),
    ("Dall'Oglio", "C", "UDI"),
    # prefissi
    ("De Pascalis", "C", "ATA"), ("Di Lorenzetti", "D", "NAP"), ("Van Der Bolt", "D", "BOL"), ("Van Hoeck", "C", "GEN"),
    ("El Fassi", "A", "MIL"), ("El Mourad A.", "C", "CRE"), ("Da Silvano", "C", "COM"), ("De Gaetano", "P", "MIL"),
    ("Di Gaetano", "D", "VER"), ("Lo Faso", "C", "LEC"), ("La Mantia R.", "A", "PIS"),
    # cognomi doppi
    ("Kolo Mbeki", "A", "JUV"), ("Zambo Ateba", "C", "NAP"), ("Floris Mancuso", "D", "LAZ"),
    ("Milinovic-Savac V.", "P", "TOR"), ("Norton-Brady", "D", "CRE"), ("Loftus-Kemp", "C", "MIL"),
    ("Bella-Tchako", "D", "GEN"),
    # nomi brasiliani o portoghesi (nome + nome)
    ("Carlos Amaro", "D", "INT"), ("Diego Torvald", "D", "ROM"), ("Juan Julio", "D", "NAP"), ("Tiago Bento", "D", "ATA"),
    ("Luis Henry", "C", "INT"), ("Kevin Carlos", "A", "SAS"),
    # accenti e lettere speciali
    ("Lorentè", "C", "SAS"), ("Peñalta", "A", "BOL"), ("Ødegren", "C", "FIO"), ("Çelikay", "D", "JUV"),
    ("Koné M.", "C", "ROM"), ("Koné I.", "C", "SAS"), ("Zé Pinho", "D", "PAR"), ("Touré E.", "A", "PIS"),
    ("Cissé A.", "D", "VER"), ("Gonçalo P.", "C", "UDI"), ("Müllerson", "D", "GEN"), ("Šimić L.", "D", "MIL"),
    ("Edinho D.S.", "C", "ATA"),
    # nomi corti
    ("Kuel", "A", "FIO"), ("Bah", "D", "LEC"), ("Ola", "C", "CAG"), ("Pau", "P", "VER"),
    # cognomi vicini tra loro (una lettera di differenza)
    ("Mancini", "D", "ROM"), ("Mancinu", "C", "CAG"), ("Bianchetti", "D", "CRE"), ("Bianchelli", "C", "BOL"),
    ("Rossetti", "A", "JUV"), ("Rossetto", "C", "TOR"),
    # come li scrive l'app di Leghe nella scheda di una squadra (tutti inventati): cognome nudo e con l'iniziale in squadre diverse,
    # iniziali doppie o di due lettere, accento in fondo, nomi composti
    ("Brahmeri", "D", "NAP"), ("Brahmeri Al.", "A", "PIS"), ("Adamis C.", "D", "TOR"), ("Adamis A.", "C", "CRE"),
    ("Spadafino Se.", "A", "SAS"), ("Spadafino F.P.", "A", "INT"), ("Turano", "A", "INT"), ("Turano K.", "C", "JUV"),
    ("Sandoval Ro.", "C", "BOL"), ("Sandoval Ra.", "D", "GEN"), ("Lucumè", "D", "BOL"), ("Bernabò", "C", "PAR"),
    ("Soulè", "C", "ROM"), ("Nicolosi Cavaglia", "C", "GEN"), ("Kolo Muandi", "A", "JUV"), ("N'Dorka", "D", "ROM"),
    ("Ederinho D.S.", "C", "ATA"), ("Milanovic-Sabic V.", "P", "NAP"), ("Milanovic-Sabic S.", "C", "LAZ"),
]

_SILLABE = ["ba", "be", "bo", "ca", "ce", "ci", "da", "di", "do", "fa", "fe", "ga", "gi", "go", "la", "le", "li", "lo",
            "ma", "me", "mi", "na", "ne", "no", "pa", "pe", "pi", "ra", "re", "ri", "ro", "sa", "se", "si", "ta", "te",
            "ti", "to", "va", "ve", "vi", "za", "zo", "ko", "ki", "ny", "an", "el", "or", "us"]
_FINALI = ["", "ni", "tti", "lli", "s", "ez", "ic", "ov", "son", "er", "an", "o", "i"]


def _ruolo(rnd: random.Random) -> str:
    return rnd.choices("PDCA", weights=[1, 3, 3, 2])[0]


def listone_inventato(quanti: int = 300, seme: int = 11) -> list[Calciatore]:
    """Un listone di fantasia: i casi difficili più cognomi inventati con le sillabe (alcuni con l'iniziale)."""
    rnd = random.Random(seme)
    voci = list(_DIFFICILI)
    visti = {normalizza(n) for n, _, _ in voci}
    sigle = list(SQUADRE)
    while len(voci) < quanti:
        cognome = "".join(rnd.choice(_SILLABE) for _ in range(rnd.randint(2, 3))) + rnd.choice(_FINALI)
        cognome = cognome.capitalize()
        if len(cognome) < 4:
            continue
        nome = cognome + (f" {rnd.choice('ABCDEFGLMNPRST')}." if rnd.random() < 0.15 else "")
        if normalizza(nome) in visti or normalizza(cognome) in visti:
            continue
        visti.add(normalizza(nome))
        voci.append((nome, _ruolo(rnd), rnd.choice(sigle)))
    return [Calciatore(1000 + i, nome, ruolo, "", sq, SQUADRE[sq], 10, 10, 100) for i, (nome, ruolo, sq) in enumerate(voci)]


# nomi che NON sono calciatori del listone: fantasquadre, persone qualsiasi, righe di contorno
NEGATIVI = [
    "Pinco Pallino", "Real Mattone", "Atletico Ma Non Troppo", "FC Bomber", "Dinamo Divano", "Sporting Spritz",
    "Mario Rossini", "Inter Nos", "Rimpianto FC", "Panchina d'Oro", "Lokomotiv Pigiama", "Borussia Sbronza",
    "Crediti residui 12", "Totale 500", "Allenatore", "Gianni Pittore", "Squadra 3", "Gli Invincibili", "Zio Peppe",
    "Ultimo Posto", "Bayern Monaco", "Paris FC", "Real Sociedad", "Ajax", "Benfica", "⚽⚽⚽", "---", "N/D", "???",
]


@dataclass
class Prova:
    testo: str
    squadra: str | None
    ruolo: str | None
    atteso: int | None        # codice del calciatore giusto, None = non è nel listone
    tipo: str
    vietato_sicuro: bool = False    # ruolo o squadra indicati diversi dal listone: mai «sicuro» su chi non li ha


def _senza_accenti(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


def _parti(nome: str) -> tuple[str, str]:
    """('Martinez', 'L.') da 'Martinez L.'; ('Kolo Mbeki', '') da 'Kolo Mbeki'."""
    m = re.fullmatch(r"(.+?)\s+((?:[A-Za-zÀ-ž]{1,2}\.)+)", nome)
    return (m.group(1), m.group(2)) if m else (nome, "")


def _refuso(parola: str, rnd: random.Random) -> str | None:
    """Un errore di battitura in una parola lunga almeno 5 lettere: lettera cambiata, tolta, raddoppiata o due scambiate."""
    if len(parola) < 5:
        return None
    i = rnd.randrange(1, len(parola) - 1)
    tipo = rnd.choice(["cambia", "togli", "raddoppia", "scambia"])
    if tipo == "cambia":
        nuova = rnd.choice([x for x in "aeiourstnlm" if x != parola[i].lower()])
        return parola[:i] + nuova + parola[i + 1:]
    if tipo == "togli":
        return parola[:i] + parola[i + 1:]
    if tipo == "raddoppia":
        return parola[:i] + parola[i] + parola[i:]
    if parola[i] == parola[i + 1]:
        return None
    return parola[:i] + parola[i + 1] + parola[i] + parola[i + 2:]


def _varianti(c: Calciatore, rnd: random.Random, nomi_esatti: set[str]) -> list[tuple[str, str]]:
    nome = c.nome
    cognome, iniziali = _parti(nome)
    sigla, squadra = c.squadra, c.squadra_slug.capitalize()
    v = [
        ("esatto", nome),
        ("maiuscole", nome.upper()),
        ("minuscole", nome.lower()),
        ("senza accenti", _senza_accenti(nome)),
        ("spazi strani", " " + nome.replace(" ", " ") + " \t"),
        ("squadra tra parentesi", f"{nome} ({sigla})"),
        ("squadra col trattino", f"{nome} - {squadra}"),
        ("ruolo davanti", f"{c.ruolo} {nome}"),
        ("ruolo col trattino", f"{c.ruolo} - {nome}"),
        ("crediti", f"{nome} {rnd.randint(1, 300)}"),
        ("crediti con cr", f"{nome} {rnd.randint(1, 300)} cr"),
        ("numero di maglia", f"#{rnd.randint(1, 99)} {nome}"),
        ("emoji", rnd.choice([f"{nome} ⭐", f"⚽ {nome}", f"{nome} 🔥"])),
        ("tutto insieme", f"{c.ruolo} {nome} ({sigla}) {rnd.randint(1, 300)}"),
        ("riga incollata", f"{c.ruolo} {nome} – {squadra} – {rnd.randint(1, 300)}"),
    ]
    if "'" in nome or "-" in nome:
        v.append(("senza apostrofi", nome.replace("'", "").replace("-", " ")))
        v.append(("apostrofo tipografico", nome.replace("'", "’")))
    if iniziali:
        v += [
            ("iniziale davanti", f"{iniziali} {cognome}"),
            ("iniziale senza punto", f"{cognome} {iniziali.replace('.', '')}"),
            ("iniziale con la virgola", f"{cognome}, {iniziali}"),
        ]
        if normalizza(cognome) not in nomi_esatti:     # «Thuram» è il nome di un altro: non si può pretendere l'altro
            v.append(("solo cognome", cognome))
        propri = " ".join(i.capitalize() + "ando" for i in normalizza(iniziali).split())   # «L.» -> «Lando»
        v += [("nome per esteso", f"{propri} {cognome}"), ("cognome e nome", f"{cognome} {propri}")]
    elif len(normalizza(nome)) >= 4:                    # «Pulisic C.» quando il listone scrive solo «Pulisic»
        libere = [x for x in "zyxwvqhg" if not any(k.startswith(normalizza(f"{nome} {x}")) for k in nomi_esatti)]
        if libere:
            v.append(("iniziale in più", f"{nome} {libere[0].upper()}."))
    parole = cognome.split()
    if len(parole) == 2 and not iniziali:
        v.append(("ordine invertito", f"{parole[1]} {parole[0]}"))
    lunga = max(parole, key=len)
    refuso = _refuso(lunga, rnd)
    if refuso:
        v.append(("refuso", nome.replace(lunga, refuso, 1)))
    return v


def genera(calciatori: list[Calciatore], seme: int = 7) -> list[Prova]:
    """Tutte le varianti di ogni calciatore; a caso una su tre con la squadra o il ruolo passati a parte."""
    rnd = random.Random(seme)
    nomi_esatti = {normalizza(c.nome) for c in calciatori}
    prove = []
    for c in calciatori:
        for tipo, testo in _varianti(c, rnd, nomi_esatti):
            if tipo == "refuso" and normalizza(testo) in nomi_esatti:
                continue                                  # l'errore ha dato il nome di un altro: non è un errore
            aiuto = rnd.random()
            prove.append(Prova(testo, c.squadra if aiuto < 0.15 else None, c.ruolo if 0.15 <= aiuto < 0.3 else None,
                               c.id, tipo))
    for testo in NEGATIVI:
        prove.append(Prova(testo, None, None, None, "non è nel listone"))
    iniziali_usate: dict[str, set[str]] = {}
    for c in calciatori:
        cognome, iniziali = _parti(c.nome)
        if iniziali:
            iniziali_usate.setdefault(normalizza(cognome), set()).add(normalizza(iniziali)[:1])
    for cognome, usate in iniziali_usate.items():      # stesso cognome, iniziale che nessuno ha: un'altra persona
        if cognome in nomi_esatti:                     # c'è anche il cognome nudo, di cui non si sa l'iniziale
            continue
        libera = next(x for x in "zyxwvqhg" if x not in usate)
        prove.append(Prova(f"{libera.upper()}. {cognome.title()}", None, None, None, "iniziale di un altro"))
    for c in rnd.sample(calciatori, min(60, len(calciatori))):      # cognomi con due lettere sbagliate: un altro giocatore
        parola = max(_parti(c.nome)[0].split(), key=len)
        if len(parola) >= 6:
            altro = parola[0] + "x" + parola[2:-2] + "k" + parola[-1]
            if sum(a != b for a, b in zip(altro, parola)) == 2 and normalizza(altro) not in nomi_esatti:
                prove.append(Prova(altro, None, None, None, "non è nel listone"))
    return prove + genera_ocr(calciatori)


_ACCENTI_OCR = str.maketrans("èéàáìíòóùú", "éèáàíìóòúù")


def _ocr(c: Calciatore, rnd: random.Random) -> list[tuple[str, str]]:
    """Come l'OCR del telefono legge il nome scritto da Leghe: punti persi, spazi doppi, apostrofi e trattini persi,
    «0» per «O», «1» per «l», accento cambiato o perso, l'iniziale persa o accorciata."""
    nome = c.nome
    cognome, iniziali = _parti(nome)
    v = [("ocr com'è", nome), ("ocr spazi doppi", nome.replace(" ", "  "))]
    if "." in nome:
        v.append(("ocr senza punti", nome.replace(".", "")))
    if "'" in nome or "-" in nome:
        v.append(("ocr senza apostrofo", nome.replace("'", "").replace("-", rnd.choice(["", " "]))))
    if "o" in cognome.lower():
        i = cognome.lower().index("o")
        v.append(("ocr 0 per O", cognome[:i] + "0" + cognome[i + 1:] + nome[len(cognome):]))
    if "l" in cognome[1:]:
        v.append(("ocr 1 per l", cognome[0] + cognome[1:].replace("l", "1", 1) + nome[len(cognome):]))
    if _senza_accenti(nome) != nome:
        v += [("ocr accento cambiato", nome.translate(_ACCENTI_OCR)), ("ocr accento perso", _senza_accenti(nome))]
    if iniziali:
        v.append(("ocr senza iniziale", cognome))
        corta = iniziali[0] + "."
        if corta != iniziali:
            v.append(("ocr iniziale corta", f"{cognome} {corta}"))
    return v


def genera_ocr(calciatori: list[Calciatore], seme: int = 5) -> list[Prova]:
    """Le righe del testo letto dalle schermate di Leghe: nome come lo legge l'OCR, con ruolo E squadra di Serie A (in sigla
    o per esteso). Più le stesse righe con il ruolo o la squadra sbagliati: lì non deve mai essere «sicuro»."""
    rnd = random.Random(seme)
    nomi_esatti = {normalizza(c.nome) for c in calciatori}
    stessi: dict[str, set[tuple[str, str]]] = {}         # cognome -> (ruolo, squadra) già usati da chi lo porta
    for c in calciatori:
        stessi.setdefault(normalizza(_parti(c.nome)[0]), set()).add((c.ruolo, c.squadra))
    prove = []
    for c in calciatori:
        club = rnd.choice([c.squadra, c.squadra_slug.capitalize(), c.squadra_slug.upper()])
        for tipo, testo in _ocr(c, rnd):
            prove.append(Prova(testo, club, c.ruolo, c.id, tipo))
        usati = stessi[normalizza(_parti(c.nome)[0])]
        ruolo = rnd.choice([r for r in "PDCA" if (r, c.squadra) not in usati])
        altra = rnd.choice([sq for sq in SQUADRE if (c.ruolo, sq) not in usati])
        cognome = _parti(c.nome)[0]
        # il cognome nudo solo se non è il nome esatto di un altro («Turano» A dell'Inter e «Turano K.» C della Juventus)
        for testo in dict.fromkeys([c.nome] + ([cognome] if normalizza(cognome) not in nomi_esatti else [])):
            prove.append(Prova(testo, club, ruolo, c.id, "ocr ruolo diverso", vietato_sicuro=True))
            prove.append(Prova(testo, rnd.choice([altra, SQUADRE[altra].capitalize()]), c.ruolo, c.id,
                               "ocr squadra diversa", vietato_sicuro=True))
    return prove


def esito_di(indice: Indice, p: Prova) -> str:
    e = indice.cerca(p.testo, p.squadra, p.ruolo)
    if e.calciatore is not None:
        sicuro = e.metodo == "esatto" and not e.avviso
        if sicuro and p.vietato_sicuro and (e.calciatore.ruolo != p.ruolo or not Indice.squadra_corrisponde(p.squadra, e.calciatore)):
            return "sicuro SBAGLIATO"
        giusto = e.calciatore.id == p.atteso
        return ("sicuro " if sicuro else "proposto ") + ("giusto" if giusto else "SBAGLIATO")
    if e.metodo == "ambiguo":
        return "dubbio con il giusto" if any(a.id == p.atteso for a in e.alternative) else "dubbio senza il giusto"
    return "non trovato"


def misura(indice: Indice, prove: list[Prova]) -> tuple[Counter, Counter, dict[str, Counter]]:
    """(esiti dei calciatori veri, esiti dei nomi che non sono nel listone, esiti per tipo di variante)."""
    veri, finti, per_tipo = Counter(), Counter(), {}
    for p in prove:
        e = esito_di(indice, p)
        (veri if p.atteso is not None else finti)[e] += 1
        per_tipo.setdefault(p.tipo, Counter())[e] += 1
    return veri, finti, per_tipo


def tabella(veri: Counter, finti: Counter) -> str:
    n, m = sum(veri.values()), sum(finti.values())
    pc = lambda k: f"{100 * veri[k] / n:5.1f}%"       # noqa: E731
    righe = [
        f"calciatori veri: {n} prove",
        f"  sicuri giusti          {pc('sicuro giusto')}",
        f"  sicuri SBAGLIATI       {pc('sicuro SBAGLIATO')}  ({veri['sicuro SBAGLIATO']})",
        f"  proposti giusti        {pc('proposto giusto')}   (da controllare)",
        f"  proposti sbagliati     {pc('proposto SBAGLIATO')}  ({veri['proposto SBAGLIATO']})",
        f"  dubbi con il giusto    {pc('dubbio con il giusto')}",
        f"  dubbi senza il giusto  {pc('dubbio senza il giusto')}",
        f"  non trovati            {pc('non trovato')}",
        f"nomi che non sono nel listone: {m} prove",
        f"  sicuri SBAGLIATI {finti['sicuro SBAGLIATO']}, proposti {finti['proposto SBAGLIATO']}, "
        f"dubbi {finti['dubbio senza il giusto']}, non trovati {finti['non trovato']}",
    ]
    return "\n".join(righe)
