"""Le note sugli infortuni che arrivano dalle fonti («risentimento muscolare al polpaccio destro, rientro da metà novembre»).

Le scrive una redazione in italiano, a mano: qui si traducono in inglese con un piccolo vocabolario (cause, parti del corpo, tempi di
rientro, partite). Se anche una sola parola non è nel vocabolario la nota NON si traduce e resta com'è: meglio un testo italiano
corretto di un inglese sbagliato. I nomi delle squadre e delle città (con la maiuscola) passano così come sono.
"""
from __future__ import annotations

import re
from functools import lru_cache

MESI = {"gennaio": "January", "febbraio": "February", "marzo": "March", "aprile": "April", "maggio": "May", "giugno": "June", "luglio": "July",
        "agosto": "August", "settembre": "September", "ottobre": "October", "novembre": "November", "dicembre": "December"}

# Cause: il più lungo vince. «di basso grado» ecc. si tolgono prima e diventano un aggettivo davanti alla causa.
CAUSE = {
    "rottura del legamento crociato anteriore": "torn anterior cruciate ligament", "rottura del legamento crociato": "torn cruciate ligament",
    "rottura del menisco": "torn meniscus", "rottura di tibia e perone": "fractured tibia and fibula", "rottura": "rupture",
    "schiacciamento di un nervo": "pinched nerve", "sindrome retto-adduttoria": "rectus-adductor syndrome",
    "sindrome femoro-rotulea": "patellofemoral syndrome", "sovraccarico muscolare": "muscle overload",
    "sovraccarico funzionale": "functional overload", "sovraccarico": "overload", "risentimento muscolare": "muscle strain",
    "risentimento miofasciale": "myofascial strain", "risentimento": "strain", "problema muscolare": "muscle problem",
    "problema fisico": "physical problem", "problema": "problem", "noie muscolari": "muscle trouble", "noie fisiche": "physical trouble",
    "lesione muscolare": "muscle injury", "lesione tendinea": "tendon injury", "lesione distrattiva": "muscle tear",
    "lesione miotendinea": "myotendinous injury", "lesione": "injury", "distorsione": "sprain", "contusione": "bruise",
    "frattura": "fracture", "affaticamento muscolare": "muscle fatigue", "affaticamento": "fatigue", "infiammazione": "inflammation",
    "lussazione": "dislocation", "lombalgia": "lower back pain", "tracheite": "tracheitis", "influenza": "flu", "stiramento": "muscle strain",
    "pubalgia": "groin pain", "tendinite": "tendinitis", "trauma": "trauma", "ernia": "hernia", "edema": "edema",
    "fastidio muscolare": "muscle discomfort", "fastidio": "discomfort", "appendicite acuta": "acute appendicitis", "appendicite": "appendicitis",
    "distrazione muscolare": "muscle strain", "distrazione": "strain", "fascite plantare": "plantar fasciitis", "infortunio": "injury",
    "frattura composta": "non-displaced fracture", "rottura del menisco esterno": "torn lateral meniscus", "rottura del menisco interno": "torn medial meniscus",
    "lesione al crociato anteriore": "anterior cruciate ligament injury", "lesione crociato anteriore": "anterior cruciate ligament injury",
    "frattura della falange": "phalanx fracture", "lesione al crociato": "cruciate ligament injury", "lesione crociato": "cruciate ligament injury",
}
GRADI_PAROLA = {"moderato": "moderate-grade", "lieve": "mild", "severo": "severe"}
GRADI = {"basso": "low-grade", "medio": "medium-grade", "medio-alto": "medium-to-high-grade", "primo": "first-degree", "alto": "high-grade",
         "secondo": "second-degree", "terzo": "third-degree"}
# Parti del corpo (anche di più parole: l'ordine conta, le più lunghe prima). L'inglese con «_» è una parola sola per le regole sotto.
CORPO = {
    "bicipite femorale": "hamstring", "retto femorale": "rectus_femoris", "adduttore lungo": "long_adductor", "tendine rotuleo": "patellar_tendon",
    "muscolo semitendinoso": "semitendinosus_muscle", "muscoli flessori": "flexor_muscles", "muscoli": "muscles", "muscolo": "muscle",
    "flessori": "flexors", "flessore": "flexor", "adduttori": "adductors", "adduttore": "adductor", "semitendinoso": "semitendinosus",
    "gamba": "leg", "coscia": "thigh", "polpaccio": "calf", "caviglia": "ankle", "ginocchio": "knee", "spalla": "shoulder", "schiena": "back",
    "anca": "hip", "inguine": "groin", "addome": "abdomen", "piede": "foot", "menisco": "meniscus", "rotula": "kneecap",
    "tendine": "tendon", "polso": "wrist", "mano": "hand", "braccio": "arm", "gomito": "elbow", "costole": "ribs", "testa": "head",
    "collo": "neck", "fianco": "flank", "quadricipite": "quadriceps", "tallone": "heel", "alluce": "big_toe", "dito": "toe", "bacino": "pelvis",
    "tibia": "tibia", "perone": "fibula", "femore": "femur", "gluteo": "glute", "glutei": "glutes", "legamento": "ligament",
    "crociato anteriore": "anterior_cruciate_ligament", "crociato": "cruciate_ligament", "collaterale mediale": "medial_collateral_ligament",
    "menisco esterno": "lateral_meniscus", "menisco interno": "medial_meniscus", "malleolo mediale": "medial_malleolus",
    "soleo": "soleus", "semimembranoso": "semimembranosus", "muscolo semimembranoso": "semimembranosus_muscle", "metatarso": "metatarsus",
    "tendine prossimale": "proximal_tendon",
}
LATI = {"destra": "right", "destro": "right", "sinistra": "left", "sinistro": "left"}
ARTICOLI_NOME = r"(?:il |lo |la |l'|i |gli |le |l’)?"
NOME = r"([A-ZÀ-Ý][\wÀ-ÿ'’.\-]*(?: [A-ZÀ-Ý][\wÀ-ÿ'’.\-]*)*)"
CONNETTORI = r"\b(?:al|alla|all'|all’|allo|ai|agli|alle|del|della|dell'|dell’|dello|dei|degli|delle|di|a|ad|un|una)\b ?"
FASE = {"inizio": "early", "fine": "late"}
# Quello che le frasi di glue possono dire (oltre ai vocabolari sopra): serve a riconoscere le parole sconosciute.
_GLUE = ("in the of with and to be assessed for against at from out return possible attempted play call-up doubt early late mid first half second "
         "left right a an by on the match big_toe").split()


def _quando(r: str) -> str | None:
    """«da metà novembre», «dalla fine di ottobre», «dall'inizio di novembre», «febbraio»: il tempo del rientro."""
    r = r.strip()
    if not r:
        return ""
    m = re.fullmatch(r"(da|dal|dalla|dall'|dall’|dalle)?\s*(?:(?:la |l'|l’)?(inizio|fine|metà|prima metà|seconda metà)(?: di| del)?\s+)?(" + "|".join(MESI) + ")", r)
    if not m:
        return None
    da, fase, mese = m.groups()
    nome = MESI[mese]
    if fase in FASE:
        quando = f"{FASE[fase]} {nome}"
    elif fase == "metà":
        quando = f"mid-{nome}"
    elif fase:
        quando = f"the {'first' if fase.startswith('prima') else 'second'} half of {nome}"
    else:
        quando = nome
    return ("from " if da else "") + quando


def _incontro(r: str) -> str | None:
    """«contro il Sassuolo», «a Firenze», «per Parma», «convocazione contro l'Atalanta», «rientro da fine ottobre»."""
    r = r.strip()
    m = re.fullmatch(r"(?:convocazione )?contro " + ARTICOLI_NOME + NOME, r)
    if m:
        return ("call-up " if r.startswith("convocazione") else "") + "against " + m.group(1)
    m = re.fullmatch(r"(convocazione )?(a|per) " + NOME, r)
    if m:
        return ("call-up " if m.group(1) else "") + ("at " if m.group(2) == "a" else "for ") + m.group(3)
    m = re.fullmatch(r"(?:rientro|il rientro)\s*(.*)", r)
    if m:
        q = _quando(m.group(1))
        return None if q is None else ("return " + q).strip()
    return None


def _tempo(p: str) -> str | None:
    """Una parte della nota che parla di tempi e partite («rientro da metà novembre», «out contro il Como», «da valutare»)."""
    m = re.fullmatch(r"(ipotesi rientro|tentativo(?: di)? rientro|rientro in campo|rientro|da valutare rientro)\s*(.*)", p)
    if m:
        testa = {"ipotesi rientro": "possible return", "rientro in campo": "return to play", "rientro": "return",
                 "da valutare rientro": "return to be assessed"}.get(m.group(1), "attempted return")
        q = _quando(m.group(2))
        return None if q is None else (testa + " " + q).strip()
    m = re.fullmatch(r"da valutare(?: (.+))?", p)
    if m:
        if not m.group(1):
            return "to be assessed"
        i = _incontro(m.group(1))
        if i is None:
            return None
        if i.startswith("call-up "):
            return "call-up to be assessed " + i[len("call-up "):]
        return "to be assessed " + i
    if p.startswith("contro "):
        return _incontro(p)
    m = re.fullmatch(r"recuperabile\s*(.*)", p)
    if m:
        q = _quando(m.group(1))
        return None if q is None else ("could return " + q).strip()
    m = re.fullmatch(r"out (.+)", p)
    if m:
        i = _incontro(m.group(1))
        return None if i is None else "out " + i
    m = re.fullmatch(r"in dubbio convocazione (.+)", p)
    if m:
        i = _incontro("convocazione " + m.group(1)) if m.group(1).startswith("contro") else _incontro(m.group(1))
        return None if i is None else "call-up in doubt " + i.replace("call-up ", "", 1)
    if p == "out":
        return "out"
    return None


def _lunghe_prima(d: dict) -> list[str]:
    return sorted(d, key=len, reverse=True)


def _causa(p: str) -> str | None:
    """«risentimento muscolare al polpaccio destro» -> «muscle strain in the right calf»."""
    cause = [c for c in _lunghe_prima(CAUSE) if p.startswith(c)]
    if not cause:
        return None
    c = cause[0]
    resto = p[len(c):].strip()
    parte_con = None
    if re.search(r"\bcon\b", resto):
        resto, _, parte_con = resto.partition(" con ")
    grado = ""
    m = re.search(r"\b(?:di )?(medio-alto|basso|medio|primo|alto|secondo|terzo) grado\b", resto)
    if m:
        grado = GRADI[m.group(1)] + " "
        resto = (resto[:m.start()] + " " + resto[m.end():]).strip()
    m = re.search(r"\b(?:di )?grado (moderato|lieve|severo)\b", resto)
    if m:
        grado = GRADI_PAROLA[m.group(1)] + " "
        resto = (resto[:m.start()] + " " + resto[m.end():]).strip()
    for it in _lunghe_prima(CORPO):
        resto = re.sub(rf"\b{re.escape(it)}\b", CORPO[it], resto)
    resto = re.sub(r"\b([a-z_]+) (destra|destro|sinistra|sinistro)\b", lambda x: f"{LATI[x.group(2)]} {x.group(1)}", resto)
    pezzi = [x.strip() for x in re.split(CONNETTORI, resto) if x.strip()]
    corpo = ""
    for k, x in enumerate(pezzi):
        corpo += (" in the " if k == 0 else " of the ") + x
    testo = grado + CAUSE[c] + corpo
    if parte_con:
        extra = _causa_con(parte_con.strip())
        if extra is None:
            return None
        testo += " with " + extra
    return testo.replace("_", " ")


def _causa_con(p: str) -> str | None:
    """«lesione parziale del tendine» (dopo «con»): la causa con un «parziale» davanti."""
    parziale = False
    if p == "parziale interessamento tendineo":
        return "partial tendon involvement"
    if re.match(r"(lesione|rottura|distorsione|frattura) parziale", p):
        p, parziale = re.sub(r" parziale", "", p, count=1), True
    t = _causa(p)
    return None if t is None else ("partial " if parziale else "") + t


def _conosciute() -> set[str]:
    testi = list(CAUSE.values()) + list(GRADI.values()) + [v.replace("_", " ") for v in CORPO.values()] + list(LATI.values()) + _GLUE
    testi += list(FASE.values()) + list(MESI.values()) + list(GRADI_PAROLA.values()) + ["partial", "tendon involvement", "could"]
    return {w.lower() for t in testi for w in re.findall(r"[A-Za-z]+", t)}


_CONOSCIUTE = _conosciute()


_NOME_EN = re.compile(r"\b(?:against|at|for) [A-ZÀ-Ý][\wÀ-ÿ'’.\-]*(?: [A-ZÀ-Ý][\wÀ-ÿ'’.\-]*)*")


def _tutte_note(t: str) -> bool:
    """Ogni parola dell'inglese deve essere nel vocabolario; le maiuscole passano solo come nome di squadra dopo «against», «at», «for»
    («fracture in the Qualcosa» non è una nota fidata: resta in italiano)."""
    senza_nomi = _NOME_EN.sub(lambda m: m.group(0).split(" ", 1)[0], t)
    return all(w.lower() in _CONOSCIUTE for w in re.findall(r"[^\W\d_]+", senza_nomi))


def traduci_dati(x):
    """Cammina in una risposta JSON già letta e traduce i campi `nota` (e la stessa nota dentro `motivi`). Il resto resta com'è."""
    if isinstance(x, list):
        return [traduci_dati(i) for i in x]
    if not isinstance(x, dict):
        return x
    nota = x.get("nota")
    tradotta = traduci(nota) if isinstance(nota, str) else None
    fuori = {}
    for k, v in x.items():
        if k == "nota" and isinstance(v, str):
            fuori[k] = tradotta
        elif k == "motivi" and isinstance(v, list) and tradotta is not None and tradotta != nota:
            fuori[k] = [tradotta if i == nota else i for i in v]
        else:
            fuori[k] = traduci_dati(v)
    return fuori


@lru_cache(maxsize=2048)
def traduci(nota: str | None) -> str | None:
    """La nota in inglese; se non si riconosce tutta, la nota com'è (italiano)."""
    if not isinstance(nota, str) or not nota.strip() or len(nota) > 300:
        return nota
    parti = [x.strip() for x in nota.strip().split(",")]
    fuori = []
    for x in parti:
        x = x[:1].lower() + x[1:]                      # solo la prima lettera: i nomi delle squadre tengono la maiuscola
        t = _tempo(x) or _causa(x)
        if t is None:
            return nota
        fuori.append(t)
    testo = ", ".join(fuori)
    return testo[0].upper() + testo[1:] if _tutte_note(testo) and testo else nota
