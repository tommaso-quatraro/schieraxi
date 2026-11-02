"""Testi dell'interfaccia (fanta/web/testi.js): ogni chiave usata nel codice esiste, ogni chiave italiana ha la sua inglese,
i segnaposto tornano, i messaggi del server si riconoscono, l'età minima è quella delle pagine legali."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server, testi_legali

TESTI_JS = (server.WEB / "testi.js").read_text(encoding="utf-8")
FILE_WEB = [server.WEB / n for n in ("app.js", "impostazioni.js", "primoavvio.js", "anteprima.js", "dafare.js", "live.js", "avatar.js")]
CODICE_JS = "\n".join(f.read_text(encoding="utf-8") for f in FILE_WEB) + TESTI_JS[TESTI_JS.index("const LINGUE"):]
# Chiavi scelte al volo (t("prefisso." + qualcosa)): il prefisso basta a tenerle vive.
PREFISSI_DINAMICI = ("err.", "srv.", "formazione.stile_", "tempo.giorno_", "lingua.", "asp.col_", "asp.testo_", "asp.tema_", "nav.")


def _dizionario(lingua: str = "it") -> dict:
    inizio = TESTI_JS.index(f"  {lingua}: {{")
    fine = TESTI_JS.index("\n  },", inizio)
    blocco = TESTI_JS[inizio + len(f"  {lingua}: {{"):fine]
    voci = re.findall(r'^\s*"([\w.]+)":\s*("(?:[^"\\]|\\.)*"),?\s*$', blocco, flags=re.M)
    return {k: json.loads(v) for k, v in voci}


def _usate() -> set:
    """Le chiavi che il codice chiede: t("chiave"), tp("chiave", ...) (chiave.one/other), linkLegale, o data-t nell'HTML."""
    semplici = set(re.findall(r'(?<![\w.])t\("([\w.]+)"', CODICE_JS)) | set(re.findall(r'linkLegale\("\w+", "([\w.]+)"', CODICE_JS))
    plurali = {f"{k}.{c}" for k in re.findall(r'(?<![\w.])tp\("([\w.]+)"', CODICE_JS) for c in ("one", "other")}
    html = (server.WEB / "index.html").read_text(encoding="utf-8")
    return semplici | plurali | set(re.findall(r'data-t(?:-aria|-title)?="([\w.]+)"', html))


def test_chiavi_usate_nel_codice_esistono():
    d = _dizionario()
    assert len(d) > 300
    usate = _usate()
    assert usate, "nessun t(...) nel codice"
    mancanti = sorted(k for k in usate if not (any(x.startswith(k) for x in d) if k.endswith(("_", ".")) else k in d))
    assert not mancanti, mancanti
    for prefisso in ("accesso.scheda_", "accesso.invio_"):               # chiavi costruite al volo: ci sono per ogni scheda
        assert all(f"{prefisso}{s}" in d for s in ("accedi", "registra", "recupero"))


def test_nessuna_chiave_dimenticata():
    """Una chiave nel dizionario che nessuno usa è un testo morto da togliere."""
    d = _dizionario()
    usate = _usate()
    prefissi = tuple(k for k in usate if k.endswith("_")) + PREFISSI_DINAMICI
    morte = sorted(k for k in d if k not in usate and not k.startswith(prefissi) and f'"{k}"' not in CODICE_JS)
    assert not morte, morte


def test_ogni_chiave_italiana_ha_la_sua_inglese():
    it, en = _dizionario("it"), _dizionario("en")
    assert sorted(set(it) - set(en)) == [], "manca in inglese"
    assert sorted(set(en) - set(it)) == [], "c'è in inglese ma non in italiano"
    segnaposto = lambda s: sorted(re.findall(r"\{(\w+)\}", s))
    diverse = sorted(k for k in it if segnaposto(it[k]) != segnaposto(en[k]))
    assert not diverse, f"segnaposto diversi tra le lingue: {diverse}"
    vuote = sorted(k for k, v in en.items() if not v.strip())
    assert not vuote, vuote
    tag = lambda s: sorted(re.findall(r"</?\w+", s))                      # una traduzione non deve rompere l'HTML dentro i testi
    storte = sorted(k for k in it if tag(it[k]) != tag(en[k]))
    assert not storte, storte


def test_l_inglese_non_e_italiano_copiato():
    """Le frasi lunghe inglesi differiscono dalle italiane (le uguali sarebbero testi dimenticati in italiano)."""
    it, en = _dizionario("it"), _dizionario("en")
    uguali = sorted(k for k in it if it[k] == en[k] and len(it[k]) > 12 and re.search(r"[a-zA-Z]{3}", re.sub(r"\{\w+\}", "", it[k])))
    assert not uguali, uguali


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
def test_i_messaggi_del_server_si_riconoscono():
    """Ogni chiave err.* (il cui testo italiano è il messaggio del server) viene riconosciuta e tradotta, parti variabili comprese."""
    it, en = _dizionario("it"), _dizionario("en")
    campioni = [[k, re.sub(r"\{\w+\}", "7", v)] for k, v in it.items() if k.startswith(("err.", "srv."))]
    assert len(campioni) > 20
    prova = TESTI_JS + """
    LINGUA = "en";
    const campioni = JSON.parse(String.raw`CAMPIONI`);
    console.log(JSON.stringify(campioni.map(([k, v]) => [k, traduciErrore(v)])));
    """
    r = subprocess.run(["node", "-"], input=prova.replace("CAMPIONI", json.dumps(campioni)), capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    for (k, v), (k2, esito) in zip(campioni, json.loads(r.stdout)):
        assert esito == re.sub(r"\{\w+\}", "7", en[k]), (k, esito)
    r = subprocess.run(["node", "-"], input=TESTI_JS + 'LINGUA = "en"; console.log(traduciErrore("Frase mai vista"))', capture_output=True, encoding="utf-8", timeout=30)
    assert r.stdout.strip() == "Frase mai vista"                          # un messaggio sconosciuto resta com'è


def test_i_messaggi_tradotti_esistono_nel_server():
    """Le frasi dei messaggi che l'app traduce esistono davvero nel codice del server: se qualcuno le cambia, la traduzione si perde."""
    sorgente = "\n".join(p.read_text(encoding="utf-8") for p in server.WEB.parent.glob("*.py"))
    for k, v in _dizionario("it").items():
        if k.startswith(("err.", "srv.")):
            pezzo = re.split(r"\{\w+\}", v)[0].strip()
            assert pezzo[:(40 if k.startswith("err.") else 12)] in sorgente, (k, pezzo)


def test_eta_minima_uguale_alle_pagine_legali():
    assert f"const ETA_MINIMA = {testi_legali.ETA_MINIMA};" in TESTI_JS


def test_script_caricati_prima_dell_app_e_pubblici():
    html = (server.WEB / "index.html").read_text(encoding="utf-8")
    assert html.index("testi.js") < html.index("primoavvio.js") < html.index("app.js")
    from fanta import rotte_account
    assert "/testi.js" in rotte_account.STATICI          # la pagina di accesso la carica prima di entrare
    assert '"/testi.js"' in (server.WEB / "sw.js").read_text(encoding="utf-8")


def test_index_ha_le_parti_fisse_traducibili():
    html = (server.WEB / "index.html").read_text(encoding="utf-8")
    for chiave in ("nav.oggi", "nav.formazione", "nav.squadra", "nav.altro", "nav.sezioni", "shell.salta", "shell.cerca",
                   "shell.impostazioni", "shell.aggiorna", "shell.dettagli", "shell.chiudi"):
        assert f'"{chiave}"' in html, chiave


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
def test_funzione_t_in_node():
    prova = TESTI_JS + """
    const esito = [t("account.dal", { ruolo: "Utente", data: "1 gennaio" }), t("non.esiste"), t("accesso.riprova_secondi", { n: 5 })];
    LINGUA = "fr";                       // lingua senza traduzioni: si torna all'italiano
    esito.push(t("account.esci"));
    LINGUA = "en";
    esito.push(t("account.esci"), t("account.dal", { ruolo: "User", data: "1 Jan" }), tp("account.esci", 1), fNum(1234.5, { maximumFractionDigits: 1 }));
    console.log(JSON.stringify(esito));
    """
    r = subprocess.run(["node", "-"], input=prova, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["Utente · dal 1 gennaio", "non.esiste", " (riprova tra 5 secondi)", "Esci",
                                    "Sign out", "User · since 1 Jan", "account.esci.other", "1,234.5"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
def test_lingua_scelta_e_rilevata_dal_browser():
    """Senza scelta salvata: inglese se il browser è inglese, altrimenti italiano. La scelta salvata vince; ogni utente ha la sua."""
    prova = """
    const memoria = {};
    globalThis.localStorage = { getItem: k => (k in memoria ? memoria[k] : null), setItem: (k, v) => { memoria[k] = String(v); } };
    globalThis.location = { reload: () => { memoria.__ricarica = "1"; } };
    const sorgente = require("fs").readFileSync(0, "utf8");
    const carica = lingua => { Object.defineProperty(globalThis, "navigator", { value: { language: lingua, languages: [lingua] }, configurable: true });
      return new Function(sorgente + "; return { LINGUA, usaLinguaDi, scegliLingua };")(); };
    const esito = [carica("en-US").LINGUA, carica("it-IT").LINGUA, carica("de-DE").LINGUA];
    memoria.lingua = "it"; esito.push(carica("en-GB").LINGUA);                       // la scelta salvata vince
    delete memoria.lingua;
    let m = carica("en-GB");                                                          // primo accesso di un utente: ricorda quella corrente
    esito.push(m.usaLinguaDi("anna"), memoria["lingua:anna"]);
    memoria["lingua:bruno"] = "it"; m = carica("en-GB");                              // un altro utente aveva scelto l'italiano
    esito.push(m.usaLinguaDi("bruno"), memoria.lingua, memoria.__ricarica);
    console.log(JSON.stringify(esito));
    """
    r = subprocess.run(["node", "-e", prova], input=TESTI_JS, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["en", "it", "it", "it", False, "en", True, "it", "1"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
def test_testi_del_server_con_nomi_e_tempi():
    """Frasi vere del server (Da fare, motivi, probabili) con nomi e durate dentro: si traducono tenendo i dati."""
    prova = TESTI_JS + """
    LINGUA = "en";
    console.log(JSON.stringify([
      traduciErrore("Rossi non può giocare. Meglio Adams A."), traduciErrore("De Bruyne è in dubbio (62% di giocare). Meglio Rossi."),
      traduciErrore("La formazione si chiude tra 3 ore e non l'hai ancora salvata."), traduciErrore("La formazione si chiude tra meno di un'ora e non l'hai ancora salvata."),
      traduciErrore("Le ho lette 7 ore fa e la formazione si chiude tra 2 ore: potrebbero essere cambiate, ricontrolla prima."),
      traduciErrore("titolare al 85%"), traduciErrore("Ho schierato la consigliata"), traduciDurata("1 minuto fa"), traduciDurata("2 giorni fa"), traduciErrore("Frase mai vista")]));
    """
    r = subprocess.run(["node", "-"], input=prova, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        "Rossi cannot play. Better Adams A.", "De Bruyne is in doubt (62% chance of playing). Better Rossi.",
        "The lineup closes in 3 hours and you have not saved it yet.", "The lineup closes in less than an hour and you have not saved it yet.",
        "I read them 7 hours ago and the lineup closes in 2 hours: they may have changed, check again first.",
        "starter at 85%", "I fielded the recommended lineup", "1 minute ago", "2 days ago", "Frase mai vista"]
