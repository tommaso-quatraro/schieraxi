"""Lettore del feed RSS di Sosfanta (https://www.sosfanta.com/feed) per la seconda fonte di probabili, in MODALITÀ OMBRA.

Funzioni pure (niente rete, niente database). Si legge solo ciò che serve a un segnale prudente: per ogni giocatore citato in
grassetto, la frase in cui compare dice che è fuori, che è titolare o che è in dubbio? Dei testi non si conserva niente:
restano il nome abbinato, il tipo di segnale, il link e l'ora di pubblicazione (uso personale, nessuna ripubblicazione).
Frasi ambigue o che parlano di recuperi ("ritrova", "torna in gruppo") non danno nessun segnale.
"""
from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape

URL_FEED = "https://www.sosfanta.com/feed"
FONTE = "sosfanta"
# User-Agent onesto: dice chi siamo e che è uso privato (il robots.txt del sito vieta solo /api e /modal)
USER_AGENT = "SchieraXI-fantacalcio/1.0 (uso personale, una richiesta ogni 30 minuti)"
CATEGORIE_UTILI = {"probabili formazioni", "infortunati", "squalificati", "ultime dai campi", "portieri"}

_NS = {"c": "http://purl.org/rss/1.0/modules/content/"}
_FUORI = re.compile(r"\b(indisponibil\w*|out|k\.?o\.?|salta|saltera|salteranno|assente|assenti|squalificat\w*|infortunat\w*|"
                    r"lesion\w*|forfait|non convocat\w*|non ci sara|non sara a disposizione|fermo|ai box|stop)\b")
_RECUPERO = re.compile(r"\b(recuper\w*|rientr\w*|ritrov\w*|torna\w*|in gruppo|a disposizione|tornato|guarit\w*)\b")
_DUBBIO = re.compile(r"\b(ballottagg\w*|dubb\w*|difficile|rischia|chance|uno tra|uno fra|alternativa|se la gioca|"
                     r"verso la panchina|panchina)\b")
_TITOLARE = re.compile(r"(\btitolar\w*|dal 1'|dal primo minuto|dall'inizio|giochera|partira|scendera in campo|confermat\w*|"
                       r"\bsara in campo)")
_PERCENTUALE = re.compile(r"(\d{1,3})\s?%")


def _senza_accenti(t: str) -> str:
    t = t.lower().replace("’", "'")
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _testo_semplice(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _nome_plausibile(g: str) -> str | None:
    """Il grassetto può essere un titoletto («OSMAJIC CON LA JUVE», «GLI ALTRI INFORTUNATI») o un periodo: si tengono solo
    sequenze brevi che sembrano un nome (1-3 parole, niente cifre, e se è tutto maiuscolo una parola sola)."""
    g = g.strip(" ,.;:-–—«»\"'")
    parole = g.split()
    if not 1 <= len(parole) <= 3 or len(g) < 2 or len(g) > 30 or any(c.isdigit() or c in ",;:!?()" for c in g):
        return None
    if g.isupper() and len(parole) > 1:
        return None
    return g


def leggi_feed(contenuto: bytes | str) -> list[dict]:
    """Le voci del feed: titolo, link, pubblicato (ISO, ora del feed senza fuso), categorie, grassetti (nomi),
    testo (testo semplice, serve solo a classificare le frasi). Voci senza data o senza link https sono saltate."""
    radice = ET.fromstring(contenuto)
    voci = []
    for it in radice.iter("item"):
        link = (it.findtext("link") or "").strip()
        try:
            quando = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if not link.startswith("https://"):
            continue
        html = it.findtext("c:encoded", default="", namespaces=_NS) or it.findtext("description") or ""
        grassetti = [_testo_semplice(m) for m in re.findall(r"<strong>(.*?)</strong>", html, flags=re.S)]
        voci.append({"titolo": (it.findtext("title") or "").strip(), "link": link,
                     "pubblicato": quando.replace(tzinfo=None).isoformat(timespec="seconds"),
                     "categorie": [(c.text or "").strip() for c in it.findall("category")],
                     "grassetti": [g for g in map(_nome_plausibile, grassetti) if g],
                     "testo": _testo_semplice(html)})
    return voci


def e_utile(voce: dict) -> bool:
    return any(c.lower() in CATEGORIE_UTILI for c in voce["categorie"])


def classifica_frase(frase: str) -> str | None:
    """'fuori', 'dubbio', 'titolare' oppure None se non è chiaro. Prudente: nel dubbio nessun segnale."""
    f = _senza_accenti(frase)
    if _RECUPERO.search(f):
        return None
    if _FUORI.search(f):
        return "fuori"
    if _DUBBIO.search(f):
        return "dubbio"
    if _TITOLARE.search(f):
        return "titolare"
    return None


def segnali(voce: dict) -> list[dict]:
    """[{nome, segnale, percentuale}] per i nomi in grassetto: la frase che contiene il nome decide. Se lo stesso nome dà
    segnali diversi in frasi diverse, non si tiene (incerto)."""
    frasi = re.split(r"(?<=[.!?])\s+", voce["testo"])
    trovati: dict[str, set] = {}
    perc: dict[str, float | None] = {}
    for nome in dict.fromkeys(voce["grassetti"]):
        for frase in frasi:
            if nome not in frase:
                continue
            s = classifica_frase(frase)
            if s:
                trovati.setdefault(nome, set()).add(s)
                m = _PERCENTUALE.search(frase)
                if m and 0 <= int(m.group(1)) <= 100:
                    perc[nome] = float(m.group(1))
    return [{"nome": n, "segnale": next(iter(s)), "percentuale": perc.get(n)} for n, s in trovati.items() if len(s) == 1]
