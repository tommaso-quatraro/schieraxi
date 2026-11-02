"""Frasi del server con la chiave per tradurle.

Il server scrive in italiano (lo leggono anche l'app per iPhone, i widget e Android, che non traducono). Per le frasi che cambiano
con i dati (Da fare, motivi, «perché», probabili, avvisi delle rose...) accanto al testo manda anche `chiave` e `param`:

    {"testo": "Rossi è infortunato. Meglio Bianchi.", "frase": {"chiave": "dafare.dubbio_infortunato_alt", "param": {"nome": "Rossi", "alt": "Bianchi"}}}

Chi sa tradurre (la web app, `fanta/web/testi.js`, chiave `frase.<chiave>`) usa quella; chi non sa continua a leggere `testo`.
Per un campo di testo `X` l'oggetto sta in `X_frase` (per `testo` si chiama `frase`); per un elenco di testi `X` sta in `X_frasi`, in
parallelo (un oggetto o `null` per ogni voce). I campi vecchi non cambiano mai: i client già installati non si accorgono di niente.

`Frase` è una stringa italiana (`str`) che si porta dietro chiave e parametri: dove una funzione restituiva un testo ne restituisce
una, e tutto il codice che la tratta come testo (confronti, elenchi, `in`) continua a funzionare. Concatenarla con altro testo la
riduce a `str` semplice (la chiave si perde): per le frasi composte si usa un'altra chiave con i pezzi dentro (parametri che sono
a loro volta `Frase`, come in `dafare.svincolato_motivo`).

Parametri: testi (nomi, squadre), interi, numeri decimali (nel JSON sono testo con il punto e UNA cifra, «1.5»; nel testo italiano
la virgola), altre `Frase`. Plurali: le chiavi `x.one` e `x.other` con il parametro `n` (uno solo = `one`).
Il modello italiano di ogni chiave sta in `CATALOGO`; `tests/test_frasi.py` controlla che `fanta/web/testi.js` abbia la stessa
chiave, gli stessi segnaposto e la traduzione inglese.
"""
from __future__ import annotations

import numbers
import re

from .frasi_avvisi import NOTIFICHE

# chiave -> modello italiano con segnaposto {nome}. Le traduzioni stanno in fanta/web/testi.js come «frase.<chiave>».
CATALOGO: dict[str, str] = {
    "tempo.meno_di_un_ora": "meno di un'ora",
    "tempo.ore.one": "{n} ora",
    "tempo.ore.other": "{n} ore",
    "tempo.fa_meno_di_un_minuto": "meno di un minuto fa",
    "tempo.minuti_fa.one": "{n} minuto fa",
    "tempo.minuti_fa.other": "{n} minuti fa",
    "tempo.ore_fa.one": "{n} ora fa",
    "tempo.ore_fa.other": "{n} ore fa",
    "tempo.giorni_fa.one": "{n} giorno fa",
    "tempo.giorni_fa.other": "{n} giorni fa",
    "tempo.giornate.one": "giornata",
    "tempo.giornate.other": "{n} giornate",
    "elenco.e": " e ",
    "dafare.dubbio_squalificato": "{nome} non può giocare.",
    "dafare.dubbio_squalificato_alt": "{nome} non può giocare. Meglio {alt}.",
    "dafare.dubbio_infortunato": "{nome} è infortunato.",
    "dafare.dubbio_infortunato_alt": "{nome} è infortunato. Meglio {alt}.",
    "dafare.dubbio_incerto": "{nome} è in dubbio ({p}% di giocare).",
    "dafare.dubbio_incerto_alt": "{nome} è in dubbio ({p}% di giocare). Meglio {alt}.",
    "dafare.formazione_chiude": "La formazione si chiude tra {tempo} e non l'hai ancora salvata.",
    "dafare.rose_vecchie": "Le rose non sono aggiornate da {giorni} giorni e nel frattempo si è giocata una giornata.",
    "dafare.cert_scaduto": "L'app sul telefono è scaduta: va reinstallata.",
    "dafare.cert_oggi": "L'app sul telefono scade oggi: rinnovala adesso.",
    "dafare.cert.one": "L'app sul telefono scade tra {n} giorno: rinnovala.",
    "dafare.cert.other": "L'app sul telefono scade tra {n} giorni: rinnovala.",
    "dafare.diario": "La giornata {n} è finita: dimmi se hai schierato la consigliata.",
    "dafare.dati_vecchi": "I dati delle partite non si aggiornano da {giorni} giorni.",
    "dafare.primo_avvio.one": "Hai saltato {n} passo della configurazione iniziale.",
    "dafare.primo_avvio.other": "Hai saltato {n} passi della configurazione iniziale.",
    "dafare.benvenuto": "Benvenuto! Per cominciare importa le rose della tua lega.",
    "dafare.ti_guido": "Ti guido io: sono pochi passi, tutti facoltativi.",
    "dafare.svincolato": "{entra} (libero) al posto di {esce}: {guadagno}.",
    "dafare.svincolato_motivo": "{entra} (libero) al posto di {esce}: {motivo}, {guadagno}.",
    "dafare.guadagno_breve.one": "circa {punti} punti in più nella prossima giornata",
    "dafare.guadagno_breve.other": "circa {punti} punti in più nelle prossime {n} giornate",
    "dafare.guadagno_stagione": "circa {punti} punti in più",
    "dafare.scambio": "Con {altra} ti conviene scambiare: dai {do}, ricevi {ricevo}, {guadagno}.",
    "dafare.scambio_motivo": "Con {altra} ti conviene scambiare: dai {do}, ricevi {ricevo} ({motivo}), {guadagno}.",
    "dafare.az_sostituisci": "Sostituisci",
    "dafare.az_rimpiazzo": "Cerca un rimpiazzo",
    "dafare.az_formazione": "Apri la formazione",
    "dafare.az_vedi": "Vedi",
    "dafare.az_scambio": "Vedi lo scambio",
    "dafare.az_aggiorna_rose": "Aggiorna le rose",
    "dafare.az_rinnova": "Rinnova",
    "dafare.az_schierato": "Ho schierato la consigliata",
    "dafare.az_controlla": "Controlla",
    "dafare.az_riprendi": "Riprendi",
    "dafare.az_importa": "Importa le rose",
    "dafare.az_inizia": "Inizia",
    "senso.nessuna_giornata": "Non ci sono giornate su cui misurare il guadagno.",
    "senso.differenza_piccola": "La differenza è piccola ({punti} punti in {giornate}): meno del normale su e giù del fantavoto.",
    "senso.entra_infortunato": "{nome} è infortunato.",
    "senso.entra_squalificato": "{nome} è squalificato.",
    "senso.entra_dubbio": "{nome} è in dubbio per la prossima giornata.",
    "senso.entra_non_sicuro": "{nome} non è sicuro di giocare ({p}% di prendere voto).",
    "senso.entra_non_titolare": "{nome} non è un titolare fisso: parte dall'inizio {p}% delle volte.",
    "senso.entra_non_titolare_sq": "{nome} non è un titolare fisso ({squadra}): parte dall'inizio {p}% delle volte.",
    "senso.entra_discontinuo": "{nome} non gioca con continuità ({p}% di presenze nell'ultimo periodo).",
    "senso.entra_discontinuo_sq": "{nome} non gioca con continuità ({squadra}) ({p}% di presenze nell'ultimo periodo).",
    "senso.esce_fuori_poco": "{nome} è fuori per poco: non si svincola un titolare per un'assenza breve.",
    "senso.esce_titolare": "{nome}, quando c'è, è titolare e vale almeno quanto chi entra: la sua assenza di oggi passa.",
    "senso.esce_pagato": "Hai pagato {nome} {costo} crediti: svincolarlo ne restituisce solo il {p}%.",
    "senso.preso_da_poco": "L'hai preso da poco: dagli il tempo di dimostrare quanto vale.",
    "senso.lasciato_da_poco": "L'hai lasciato libero da poco: riprenderlo adesso sarebbe un ripensamento.",
    "senso.crediti": "Non bastano i crediti.",
    "senso.si_titolare_fisso": "{nome} è titolare fisso",
    "senso.si_titolare_fisso_sq": "{nome} è titolare fisso ({squadra})",
    "senso.si_fuori_a_lungo": "{nome} resta fuori a lungo",
    "senso.si_squalificato": "{nome} è squalificato",
    "senso.si_gioca_poco": "{nome} gioca poco",
    "senso.nessuno_accetta": "Nessuno accetta {nome} ({perche}) in cambio di un titolare.",
    "senso.stato_infortunato": "infortunato",
    "senso.stato_squalificato": "squalificato",
    "senso.gioca_poco_perc": "gioca poco, {p}% di presenze",
    "motivo.titolare": "titolare",
    "motivo.titolare_ballottaggio": "titolare in ballottaggio",
    "motivo.panchina": "parte dalla panchina",
    "motivo.infortunato": "infortunato",
    "motivo.squalificato": "squalificato",
    "motivo.non_convocato": "non tra i convocati previsti",
    "motivo.rigorista": "rigorista",
    "motivo.porta_inviolata": "{p}% di non subire gol",
    "motivo.gol_atteso": "gol atteso {p}%",
    "motivo.favorevole": "partita favorevole",
    "motivo.difficile": "partita difficile",
    "perche.voti_su": "voti sopra la media del ruolo",
    "perche.voti_giu": "voti sotto la media del ruolo",
    "perche.partita_su_casa": "partita favorevole in casa",
    "perche.partita_su_fuori": "partita favorevole in trasferta",
    "perche.partita_giu_casa": "partita difficile in casa",
    "perche.partita_giu_fuori": "partita difficile in trasferta",
    "perche.gol_su": "segna più della media del ruolo ({p}% di segnare)",
    "perche.gol_giu": "segna meno della media del ruolo",
    "perche.assist_su": "fa più assist della media del ruolo",
    "perche.assist_giu": "fa meno assist della media del ruolo",
    "perche.rigori_su": "rigorista",
    "perche.rigori_giu": "tira pochi rigori",
    "perche.porta_su": "buone chance di non subire gol ({p}%)",
    "perche.porta_giu": "poche chance di non subire gol ({p}%)",
    "perche.altro_su": "bonus extra (per esempio migliore in campo)",
    "perche.altro_giu": "cartellini e altri malus",
    "perche.gioca_dubbio": "gioca il {p}%: dubbio",
    "perche.gioca_panchina": "gioca il {p}%: probabile panchina",
    "perche.gioca_improbabile": "gioca solo il {p}%: improbabile",
    "perche.infortunato": "infortunato: non gioca",
    "perche.squalificato": "squalificato: non gioca",
    "perche.non_convocato": "non tra i convocati previsti",
    "probabili.oggi": "Probabili aggiornate alle {ora}",
    "probabili.ieri": "Probabili aggiornate ieri alle {ora}",
    "probabili.data": "Probabili aggiornate il {giorno}/{mese} alle {ora}",
    "probabili.vecchie": "Le ho lette {eta} e la formazione si chiude tra {tempo}: potrebbero essere cambiate, ricontrolla prima.",
    "confronto.pari": "{a} e {b} sono quasi alla pari: la differenza è sotto 0,2 punti attesi.",
    "confronto.avanti_sparsi": "{primo} è avanti di {punti} punti attesi, con piccoli vantaggi sparsi.",
    "confronto.avanti": "{primo} è avanti di {punti} punti attesi su {secondo}: {motivi}.",
    "confronto.gioca_di_piu": "gioca di più ({pa}% contro {pb}%: +{peso})",
    "confronto.alto_voto": "voto in pagella atteso più alto (+{peso})",
    "confronto.alto_gol": "gol attesi più alto (+{peso})",
    "confronto.alto_assist": "assist attesi più alto (+{peso})",
    "confronto.alto_rigori": "rigori più alto (+{peso})",
    "confronto.alto_porta": "porta (gol subiti, imbattibilità) più alto (+{peso})",
    "confronto.alto_altro": "cartellini e altro più alto (+{peso})",
    "confronto.tutti_titolari": "{a} e {b} sono tutti e due titolari nel {modulo}: giocano insieme, non si tolgono il posto.",
    "confronto.non_titolari_ordine": "{a} e {b} non sono titolari nel {modulo} ({pa} e {pb}): entra per primo chi sta più in alto in panchina, se il ruolo serve.",
    "confronto.non_titolari_fuori": "{a} e {b} non sono titolari nel {modulo} ({pa} e {pb}): chi è fuori non entra.",
    "confronto.ruoli_diversi": "{titolare} è titolare, {altro} è {posto}, ma sono di ruoli diversi: non si sostituiscono tra loro (a meno di un cambio di modulo durante le sostituzioni).",
    "confronto.principale": "Il sistema schiera {titolare} come titolare. {entrata} {esito} Conta quanto vale ciascuno quando gioca ({titolare} {mu_t} contro {altro} {mu_a}), non solo se gioca.",
    "confronto.entra_fuori": "{altro} resta fuori: in panchina ci sono giocatori più utili al punteggio.",
    "confronto.senza_sostituzioni": "Nella tua lega non sono ammesse sostituzioni: {altro} ({posto}) non può entrare al posto di {titolare}.",
    "confronto.entra_se": "Se {titolare} non prende voto ({p}% di probabilità), al suo posto può entrare {altro} ({posto}).",
    "confronto.esito_meglio": "Con {titolare} titolare la formazione vale {attuale} punti attesi; con i due invertiti {invertita} ({d}).",
    "confronto.esito_peggio": "Invertendoli la formazione varrebbe {invertita} invece di {attuale} ({d}): con il modulo {modulo} (non il migliore) la scelta non è la più conveniente.",
    "confronto.esito_pari": "Le due soluzioni valgono praticamente lo stesso ({attuale} contro {invertita}).",
    "posto.titolare": "titolare",
    "posto.panchina": "panchina {n}",
    "posto.fuori": "fuori",
    "rose.riga_ignorata": "Riga {riga}: ignorata ({celle}): mi aspettavo «nome squadra, codice calciatore, costo».",
    "rose.codice_sconosciuto": "{squadra}: il codice {codice} non è nel listone, quindi non so chi sia: correggilo a mano.",
    "rose.codice_doppio": "{squadra}: {nome} (codice {codice}) compare due volte, l'ho tenuto una volta sola.",
    "rose.piu_giocatori_riga": "Riga {riga}: più giocatori sulla stessa riga ({nomi}). Se sono squadre affiancate, lascia una colonna vuota tra una squadra e l'altra.",
    "rose.riga_non_chiara": "Riga {riga}: ignorata ({celle}): non è chiaro se sia un'intestazione o il nome di più squadre.",
    "rose.nome_doppio": "{squadra}: {nome} compare due volte, l'ho tenuto una volta sola.",
    "rose.codice_assente": "codice {codice} non presente nel listone",
    "rose.diversa": "{squadra}: rosa diversa dalle regole ({dettaglio})",
    "rose.doppione": "{squadra}: {nome} compare {volte} volte nella rosa: togli le righe in più",
    "rose.non_riconosciuto": "{squadra}: '{nome}' non riconosciuto con certezza ({motivo})",
    "rose.motivo_ceduto": "ceduto o nome diverso?",
    "rose.somiglianza": "{squadra}: '{nome}' riconosciuto per somiglianza ({come}), controlla che sia lui",
    "rose.come_abbreviato": "abbreviato",
    "rose.come_simile": "simile",
    "rose.avviso_giocatore": "{squadra}: {nome}: {avviso}",
    "rose.in_piu_squadre": "{nome} è in più squadre: {squadre}",
    "rose.squadra_avviso": "{squadra}: {avviso}",
    "rose.n_giocatori_su.one": "{n} giocatore su {attesi}",
    "rose.n_giocatori_su.other": "{n} giocatori su {attesi}",
    "rose.mancano": "mancano {elenco}",
    "rose.in_piu": "in più: {elenco}",
    "rose.senza_ruolo.one": "{n} giocatore senza ruolo",
    "rose.senza_ruolo.other": "{n} giocatori senza ruolo",
    "rose.portieri.one": "{n} portiere",
    "rose.portieri.other": "{n} portieri",
    "rose.difensori.one": "{n} difensore",
    "rose.difensori.other": "{n} difensori",
    "rose.centrocampisti.one": "{n} centrocampista",
    "rose.centrocampisti.other": "{n} centrocampisti",
    "rose.attaccanti.one": "{n} attaccante",
    "rose.attaccanti.other": "{n} attaccanti",
    "rose.potrebbe_essere": "potrebbe essere: {elenco}",
    "nomi.ruolo_diverso": "ruolo diverso: indicato {indicato}, nel listone {listone}",
    "nomi.squadra_diversa": "squadra diversa: indicata {indicata}, nel listone {listone}",
}


E_ELENCO = {"it": " e ", "en": " and "}


def _it(valore, lingua: str = "it") -> str:
    """Un parametro nel testo: i decimali con una cifra (la virgola in italiano, il punto in inglese); le frasi nella stessa lingua."""
    if isinstance(valore, Frase):
        return valore.in_lingua(lingua)
    if isinstance(valore, bool) or not isinstance(valore, numbers.Real) or isinstance(valore, numbers.Integral):
        return str(valore)
    testo = f"{float(valore):.1f}"
    return testo.replace(".", ",") if lingua == "it" else testo


def _modello(chiave: str, param: dict, lingua: str) -> str:
    """Il modello di una chiave: `CATALOGO` (solo italiano; l'inglese sta in testi.js) o `NOTIFICHE` (italiano e inglese).
    Una lingua che non c'è si legge in italiano."""
    if chiave in CATALOGO or chiave + ".other" in CATALOGO:
        suffisso = (".one" if param.get("n") == 1 else ".other") if chiave + ".other" in CATALOGO else ""
        return CATALOGO[chiave + suffisso]
    indice = 1 if lingua == "en" else 0
    suffisso = (".one" if param.get("n") == 1 else ".other") if chiave + ".other" in NOTIFICHE else ""
    return NOTIFICHE[chiave + suffisso][indice]


def _componi(chiave: str, param: dict, lingua: str = "it") -> str:
    if chiave in ("elenco", "elenco_e"):
        parti = [_it(p, lingua) for p in param["parti"]]
        sep = str(param.get("sep", ", "))
        if chiave == "elenco_e" and len(parti) > 1:
            return sep.join(parti[:-1]) + E_ELENCO[lingua if lingua in E_ELENCO else "it"] + parti[-1]
        return sep.join(parti)
    testo = _modello(chiave, param, lingua).format(**{k: _it(v, lingua) for k, v in param.items()})
    return re.sub(r"\.\.$", ".", testo)          # «Meglio Adams A.» + «.» = un punto solo


def _json(valore):
    if isinstance(valore, Frase):
        return valore.json()
    if isinstance(valore, (list, tuple)):
        return [_json(v) for v in valore]
    if isinstance(valore, bool) or valore is None or isinstance(valore, str):
        return valore
    if isinstance(valore, numbers.Integral):
        return int(valore)
    if isinstance(valore, numbers.Real):
        return f"{float(valore):.1f}"                # decimali: testo con il punto e una cifra («1.5»), uguale in ogni lingua inglese
    return str(valore)


class Frase(str):
    """Testo italiano + chiave e parametri per tradurlo (vedi la guida del modulo)."""

    chiave: str
    param: dict

    def __new__(cls, chiave: str, param: dict | None = None):
        param = dict(param or {})
        self = super().__new__(cls, _componi(chiave, param))
        self.chiave, self.param = chiave, param
        return self

    def __getnewargs__(self):                    # copy e pickle ricostruiscono la frase dai suoi pezzi
        return (self.chiave, self.param)

    def in_lingua(self, lingua: str) -> str:
        """Il testo nella lingua data (`it` o `en`), come testo semplice. L'inglese c'è solo per gli avvisi sul telefono (`NOTIFICHE`):
        le altre frasi le traduce il web da testi.js, e qui restano in italiano."""
        return _componi(self.chiave, self.param, lingua)

    def json(self) -> dict:
        """L'oggetto che va nelle risposte: `{"chiave": ..., "param": {...}}` (i parametri che sono frasi diventano oggetti)."""
        return {"chiave": self.chiave, "param": {k: _json(v) for k, v in self.param.items()}}


def F(chiave: str, **param) -> Frase:
    """`F("dafare.diario", n=3)`: la frase italiana con la sua chiave."""
    return Frase(chiave, param)


def testo(valore, lingua: str = "it") -> str:
    """Un testo nella lingua data: una `Frase` si riscrive, un testo semplice resta com'è."""
    return valore.in_lingua(lingua) if isinstance(valore, Frase) else valore


def di(valore) -> dict | None:
    """L'oggetto `{chiave, param}` di una frase, oppure None se `valore` è un testo qualunque (nessuna traduzione possibile)."""
    return valore.json() if isinstance(valore, Frase) else None


def lista(valori) -> list[dict | None]:
    """Per un elenco di testi: un oggetto (o None) per ogni voce, nello stesso ordine."""
    return [di(v) for v in valori]


def elenco(parti: list, sep: str = ", ", con_e: bool = False):
    """Più frasi in fila: «a, b e c» (con_e) o «a; b; c» (sep). Una sola parte resta com'è; nessuna parte: testo vuoto."""
    parti = list(parti)
    if not parti:
        return ""
    if len(parti) == 1:
        return parti[0]
    return Frase("elenco_e" if con_e else "elenco", {"parti": parti, "sep": sep})


def da_json(valore) -> Frase | None:
    """L'inverso di `Frase.json()`: serve a chi riceve una frase già salvata o in cache come oggetto. None se non è valida."""
    try:
        if not isinstance(valore, dict) or not isinstance(valore.get("chiave"), str):
            return None
        def pezzo(v):
            if isinstance(v, dict):
                return da_json(v) or v
            if isinstance(v, list):
                return [pezzo(x) for x in v]
            return float(v) if isinstance(v, str) and re.fullmatch(r"-?\d+\.\d", v) else v     # un decimale torna decimale (virgola in italiano)
        param = {k: pezzo(v) for k, v in (valore.get("param") or {}).items()}
        return Frase(valore["chiave"], param)
    except (KeyError, IndexError, ValueError, TypeError):
        return None
