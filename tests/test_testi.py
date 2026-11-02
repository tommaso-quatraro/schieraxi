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
PREFISSI_DINAMICI = ("err.", "srv.", "frase.", "confronto.fattore_", "regola.et.", "formazione.stile_", "tempo.giorno_", "lingua.", "asp.col_", "asp.testo_", "asp.tema_", "nav.")


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


def _testi_del_server() -> set[str]:
    """Tutti i testi scritti nel codice del server: stringhe e f-string (ogni {…} diventa il carattere nullo, che vale «qualunque cosa»)."""
    import ast
    testi = set()
    for percorso in server.WEB.parent.glob("*.py"):
        for nodo in ast.walk(ast.parse(percorso.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                testi.add(nodo.value)
            elif isinstance(nodo, ast.JoinedStr):
                testi.add("".join(v.value if isinstance(v, ast.Constant) else "\0" for v in nodo.values))
    return testi


def test_i_messaggi_tradotti_esistono_nel_server():
    """Ogni messaggio che l'app traduce (chiavi err.* e srv.*) è scritto per intero, parola per parola, nel codice del server: se qualcuno
    cambia un messaggio e non la chiave, la traduzione si perde in silenzio e l'utente inglese rivede l'italiano."""
    testi = _testi_del_server()
    for k, v in _dizionario("it").items():
        if k.startswith(("err.", "srv.")):
            modello = re.compile("^" + ".+?".join(re.escape(pezzo) for pezzo in re.split(r"\{\w+\}", v)) + "$", re.S)
            assert any(modello.match(t) for t in testi), (k, v)


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


# Moduli senza messaggi per chi usa l'app (comandi da terminale, email, pagine legali, misure, cose per chi gestisce il server): non si controllano
MODULI_SENZA_MESSAGGI = {"__main__.py", "testi_legali.py", "posta.py", "verifica.py", "verifica_pacchetti.py", "verifica_fonti.py",
                         "verifica_probabili_fonte2.py", "aggiorna.py", "contesto.py", "listone.py", "salute.py", "pianificatore.py",
                         "formazioni_lega.py", "foto.py", "rotte_foto.py", "fonti_attive.py"}
# Messaggi che l'utente della web app non dovrebbe mai vedere (errori interni, cose per chi gestisce il server): niente traduzione.
# L'elenco può solo accorciarsi: se un messaggio qui sotto viene tradotto o sparisce, il test chiede di toglierlo.
MESSAGGI_SENZA_TRADUZIONE = {
    "Per iscriverti devi accettare Privacy e Termini d'uso. / To sign up you must accept the Privacy policy and the Terms of use.",    # già nelle due lingue
    "Il database degli account è di una versione più nuova dell'app: aggiorna l'app",           # database degli account: li legge chi gestisce il server
    "Il database degli account (account.sqlite) non si riesce a leggere: forse è rovinato. Non ho cancellato niente. "
    "L'amministratore deve rimetterlo dalla copia di backup (cartella backup accanto al file) e riavviare il servizio.",
    "deve essere una lista", "deve essere un elenco di voci", "formato non riconosciuto",                                        # dentro il controllo del backup
    "{x}: atteso un gruppo di valori {...}, trovato {x}", "{x}: atteso un valore di tipo {x}, ricevuto {x}",                      # regole.json a mano
    "calciatore {x} non nel listone", "token non valido",
    "Questa funzione serve solo con gli account attivi: accendi FANTA_MULTIUTENTE=1 sul server",
}


def _messaggi_di_errore() -> dict[str, str]:
    """I messaggi che il server scrive nelle eccezioni (`raise X("...")`, `HTTPException(codice, "...")`): testo -> «modulo:riga»."""
    import ast
    trovati = {}
    for percorso in sorted(server.WEB.parent.glob("*.py")):
        if percorso.name in MODULI_SENZA_MESSAGGI:
            continue
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        costanti = {}

        def testo(n):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                return n.value
            if isinstance(n, ast.Name):
                return costanti.get(n.id)
            if isinstance(n, ast.JoinedStr):
                return "".join(v.value if isinstance(v, ast.Constant) else "{x}" for v in n.values)
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
                a, b = testo(n.left), testo(n.right)
                return a + b if a is not None and b is not None else None
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format":
                return testo(n.func.value)
            return None

        for n in albero.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and testo(n.value):
                costanti[n.targets[0].id] = testo(n.value)
        for n in ast.walk(albero):
            if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call):
                http = ast.unparse(n.exc.func).endswith("HTTPException")
                candidati = n.exc.args[1:2] + [k.value for k in n.exc.keywords if k.arg == "detail"] if http else n.exc.args[:1]
                for a in candidati:
                    s = testo(a)
                    if s and len(s.split()) >= 2 and re.search(r"[àèéìòù]|\b(il|la|le|di|che|non|per|con|è|hai|una|un|più|riprova|rosa|squadra|dati)\b", s, re.I):
                        trovati.setdefault(s, f"{percorso.name}:{n.lineno}")
    return trovati


def test_ogni_messaggio_d_errore_e_tradotto_o_e_nell_elenco_di_quelli_interni():
    """Un messaggio nuovo scritto nel server senza la sua traduzione (chiave err.* in testi.js) fa fallire il controllo: l'utente inglese lo vedrebbe
    in italiano. Se è un messaggio che nessun utente vede, si aggiunge a MESSAGGI_SENZA_TRADUZIONE scrivendo il perché."""
    modelli = [re.compile("^" + ".+?".join(re.escape(p) for p in re.split(r"\{\w+\}", v)) + "$", re.S)
               for k, v in _dizionario("it").items() if k.startswith(("err.", "srv."))]
    senza = {}
    for messaggio, dove in _messaggi_di_errore().items():
        if not any(m.match(messaggio.replace("{x}", "7")) for m in modelli):
            senza[messaggio] = dove
    nuovi = {m: d for m, d in senza.items() if m not in MESSAGGI_SENZA_TRADUZIONE}
    assert not nuovi, f"messaggi senza traduzione (aggiungi la chiave err.* in testi.js, italiano e inglese): {nuovi}"
    superati = sorted(MESSAGGI_SENZA_TRADUZIONE - set(senza))
    assert not superati, f"ora tradotti o spariti: toglili da MESSAGGI_SENZA_TRADUZIONE: {superati}"
