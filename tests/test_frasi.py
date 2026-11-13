"""Frasi del server con chiave e parametri (fanta/frasi.py) e la loro traduzione nella web app (fanta/web/testi.js)."""
import ast
import copy
import json
import pickle
import re
import shutil
import subprocess

import pytest

from fanta import frasi, server
from fanta.frasi import CATALOGO, F
from fanta.frasi_avvisi import NOTIFICHE
import codice_web

PACCHETTO = server.WEB.parent
TESTI_JS = codice_web.leggi("testi.js")
CON_NODE = pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")


def _dizionario(lingua: str) -> dict:
    inizio = TESTI_JS.index(f"  {lingua}: {{")
    blocco = TESTI_JS[inizio:TESTI_JS.index("\n  },", inizio)]
    return {k: json.loads(v) for k, v in re.findall(r'^\s*"([\w.]+)":\s*("(?:[^"\\]|\\.)*"),?\s*$', blocco, flags=re.M)}


def _chiavi_base() -> list[str]:
    return sorted({re.sub(r"\.(one|other)$", "", k) for k in CATALOGO if k != "elenco.e"})


def _param(chiave: str) -> dict:
    """Parametri finti per tutti i segnaposto di una chiave (e dei suoi plurali)."""
    nomi = set()
    for k in (chiave, chiave + ".one", chiave + ".other"):
        nomi |= set(re.findall(r"\{(\w+)\}", CATALOGO.get(k, "")))
    return {n: 2 if n == "n" else "X" for n in nomi}


# ---------------------------------------------------------------- il catalogo e il file dei testi dicono la stessa cosa
def test_catalogo_e_testi_js_hanno_le_stesse_chiavi_e_lo_stesso_italiano():
    it, en = _dizionario("it"), _dizionario("en")
    in_js = {k[len("frase."):] for k in it if k.startswith("frase.")}
    assert in_js == set(CATALOGO), sorted(in_js ^ set(CATALOGO))
    for k, modello in CATALOGO.items():
        assert it["frase." + k] == modello, k               # l'italiano del web e quello del server sono lo stesso testo
        assert en["frase." + k].strip(), k


def test_ogni_chiave_si_costruisce_e_si_ricostruisce_dal_json():
    for chiave in _chiavi_base():
        for n in ((1, 2) if chiave + ".other" in CATALOGO else (None,)):
            param = _param(chiave) | ({"n": n} if n else {})
            f = F(chiave, **param)
            assert f and "{" not in f, chiave
            assert frasi.da_json(json.loads(json.dumps(f.json()))) == f, chiave        # passa dal JSON e torna uguale


def test_le_chiavi_scritte_nel_codice_esistono():
    """Ogni F("chiave") con la chiave scritta per intero nel codice punta a una voce del catalogo (quelle costruite al volo le prova il test sopra)."""
    mancanti = []
    for percorso in sorted(PACCHETTO.glob("*.py")):
        for nodo in ast.walk(ast.parse(percorso.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in ("F", "Frase") and nodo.args:
                a = nodo.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value not in CATALOGO and a.value + ".other" not in CATALOGO \
                        and a.value not in NOTIFICHE and a.value + ".other" not in NOTIFICHE and a.value not in ("elenco", "elenco_e"):
                    mancanti.append(f"{percorso.name}:{nodo.lineno} {a.value}")
    assert not mancanti, mancanti


# ---------------------------------------------------------------- la classe
def test_una_frase_e_un_testo_italiano_con_chiave_e_parametri():
    f = F("dafare.dubbio_infortunato_alt", nome="Rossi", alt="Adams A.")
    assert isinstance(f, str) and f == "Rossi è infortunato. Meglio Adams A."          # un punto solo anche se il nome finisce col punto
    assert f.json() == {"chiave": "dafare.dubbio_infortunato_alt", "param": {"nome": "Rossi", "alt": "Adams A."}}
    assert f.upper() == "ROSSI È INFORTUNATO. MEGLIO ADAMS A." and "infortunato" in f            # per il resto è una stringa


def test_plurali_decimali_e_frasi_dentro_le_frasi():
    assert F("tempo.ore", n=1) == "1 ora" and F("tempo.ore", n=3) == "3 ore"
    assert F("tempo.giornate", n=1) == "giornata" and F("tempo.giornate", n=4) == "4 giornate"
    g = F("dafare.guadagno_breve", punti=1.26, n=3)
    assert g == "circa 1,3 punti in più nelle prossime 3 giornate"                       # in italiano la virgola
    assert g.json()["param"] == {"punti": "1.3", "n": 3}                                 # nel JSON il punto, una cifra, come testo
    assert F("dafare.guadagno_breve", punti=2, n=1) == "circa 2 punti in più nella prossima giornata"
    t = F("dafare.formazione_chiude", tempo=F("tempo.meno_di_un_ora"))
    assert t == "La formazione si chiude tra meno di un'ora e non l'hai ancora salvata."
    assert t.json()["param"]["tempo"] == {"chiave": "tempo.meno_di_un_ora", "param": {}}
    e = frasi.elenco([F("rose.portieri", n=2), F("rose.difensori", n=1), F("rose.attaccanti", n=3)], con_e=True)
    assert e == "2 portieri, 1 difensore e 3 attaccanti"
    assert frasi.elenco([]) == "" and frasi.elenco(["solo"]) == "solo" and frasi.elenco(["a", "b"], sep="; ") == "a; b"


def test_copie_e_ricostruzione_tengono_la_chiave():
    f = F("dafare.svincolato_motivo", entra="A", esce="B", motivo=F("senso.crediti"), guadagno=F("dafare.guadagno_stagione", punti=1.5))
    for copia in (copy.deepcopy(f), pickle.loads(pickle.dumps(f)), frasi.da_json(f.json())):
        assert copia == f and copia.json() == f.json()
    assert frasi.da_json({"chiave": "non.esiste"}) is None and frasi.da_json("testo") is None and frasi.da_json(None) is None
    assert frasi.di("testo qualunque") is None and frasi.di(f) == f.json() and frasi.lista(["x", F("senso.crediti")])[0] is None


# ---------------------------------------------------------------- numeri con il segno (#392)
def test_un_numero_negativo_ha_il_meno_tipografico():
    """«−0,4», mai «-0,4» (come `segno` e `numMeno` della web); se arrotondato vale zero, «0,0» senza segno. Nel JSON resta il
    numero con il trattino, che si legge con qualunque linguaggio."""
    f = F("senso.differenza_piccola", punti=-0.43, giornate="3 giornate")
    assert f.startswith("La differenza è piccola (−0,4 punti in 3 giornate)") and "-" not in f
    assert f.json()["param"]["punti"] == "-0.4"
    assert F("senso.differenza_piccola", punti=-0.04, giornate="3 giornate").startswith("La differenza è piccola (0,0 punti")
    assert F("posto.panchina", n=-3) == "panchina −3"                         # un intero negativo, anche lui con il meno tipografico


@pytest.mark.parametrize("a, b, testo, nel_json", [
    (72.14, 72.74, "−0,6", "-0.6"),          # la foto della issue: 72,7 e 72,1 → la differenza è 0,6
    (72.14, 72.66, "−0,6", "-0.6"),          # quella vera (0,52) arrotondata da sola darebbe 0,5: non torna con 72,7 e 72,1
    (60.56, 60.04, "+0,6", "+0.6"),          # positiva: con il «+»
    (72.10, 72.14, "0,0", "0.0"),            # stessi numeri a schermo: zero, senza segno
])
def test_la_differenza_e_quella_dei_due_numeri_mostrati(a, b, testo, nel_json):
    d = frasi.differenza(a, b)
    f = F("confronto.esito_peggio", invertita=a, attuale=b, d=d, modulo="3-4-3")
    assert f.startswith(f"Invertendoli la formazione varrebbe {frasi._it(a)} invece di {frasi._it(b)} ({testo}):")
    assert f.json()["param"]["d"] == nel_json
    copia = frasi.da_json(json.loads(json.dumps(f.json())))             # passa dal JSON (cache) e torna uguale
    assert copia == f and copia.json() == f.json()


# ---------------------------------------------------------------- la traduzione nel web (node)
def _in_node(lingua: str, casi: list) -> list:
    """Per ogni caso [frase, testo italiano] il risultato di `traduciFrase` con la lingua data."""
    prova = TESTI_JS + f"""
    LINGUA = {json.dumps(lingua)};
    const casi = JSON.parse(String.raw`{json.dumps(casi, ensure_ascii=False)}`);
    console.log(JSON.stringify(casi.map(([f, it]) => traduciFrase(f, it))));
    """
    r = subprocess.run(["node", "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@CON_NODE
def test_ogni_frase_si_traduce_in_inglese_senza_segnaposto_rimasti():
    casi, chiavi = [], []
    for chiave in _chiavi_base():
        for n in ((1, 2) if chiave + ".other" in CATALOGO else (None,)):
            f = F(chiave, **(_param(chiave) | ({"n": n} if n else {})))
            casi.append([f.json(), str(f)])
            chiavi.append(chiave)
    for chiave, esito, caso in zip(chiavi, _in_node("en", casi), casi):
        assert esito and "{" not in esito and "}" not in esito and not esito.startswith("frase."), (chiave, esito)
        if len(caso[1]) > 25:
            assert esito != caso[1], chiave                  # non è rimasto l'italiano


@CON_NODE
def test_frasi_vere_in_inglese_con_nomi_numeri_e_frasi_dentro():
    motivo = F("senso.si_titolare_fisso_sq", nome="Verdi", squadra="Milan")
    casi = [
        F("dafare.dubbio_squalificato_alt", nome="Rossi", alt="Adams A."),
        F("dafare.dubbio_incerto", nome="De Bruyne", p=62),
        F("dafare.formazione_chiude", tempo=F("tempo.meno_di_un_ora")),
        F("dafare.formazione_chiude", tempo=F("tempo.ore", n=3)),
        F("dafare.svincolato_motivo", entra="Bianchi", esce="Rossi", motivo=motivo, guadagno=F("dafare.guadagno_breve", punti=1.234, n=3)),
        F("dafare.svincolato", entra="Bianchi", esce="Rossi", guadagno=F("dafare.guadagno_stagione", punti=4)),
        F("dafare.cert", n=1), F("dafare.cert", n=2),
        F("probabili.vecchie", eta=F("tempo.ore_fa", n=7), tempo=F("tempo.ore", n=2)),
        F("probabili.data", giorno=3, mese=11, ora="14:05"),
        F("confronto.avanti", primo="Rossi", secondo="Bianchi", punti=0.7,
          motivi=frasi.elenco([F("confronto.gioca_di_piu", pa=85, pb=60, peso=0.4), F("confronto.alto_voto", peso=0.3)], sep="; ")),
        F("confronto.principale", titolare="Rossi", altro="Bianchi", mu_t=7.2, mu_a=6.9,
          entrata=F("confronto.entra_se", titolare="Rossi", p=15, altro="Bianchi", posto=F("posto.panchina", n=1)),
          esito=F("confronto.esito_pari", attuale=60.1, invertita=60.0)),
        F("rose.mancano", elenco=frasi.elenco([F("rose.portieri", n=2), F("rose.attaccanti", n=1)], con_e=True)),
        F("motivo.titolare_ballottaggio"), F("perche.partita_giu_fuori"),
    ]
    attesi = [
        "Rossi cannot play. Better Adams A.",
        "De Bruyne is in doubt (62% chance of playing).",
        "The lineup closes in less than an hour and you have not saved it yet.",
        "The lineup closes in 3 hours and you have not saved it yet.",
        "Bianchi (free agent) instead of Rossi: Verdi is a regular starter (Milan), about 1.2 more points over the next 3 matchdays.",
        "Bianchi (free agent) instead of Rossi: about 4 more points.",
        "The app on your phone expires in 1 day: renew it.", "The app on your phone expires in 2 days: renew it.",
        "I read them 7 hours ago and the lineup closes in 2 hours: they may have changed, check again first.",
        "Probable lineups updated on 3/11 at 14:05",
        "Rossi is ahead of Bianchi by 0.7 expected points: plays more often (85% vs 60%: +0.4); higher expected match rating (+0.3).",
        "The system fields Rossi as a starter. If Rossi gets no rating (15% chance), Bianchi (bench 1) can come on in their place. "
        "The two options are worth practically the same (60.1 vs 60.0). What counts is how much each is worth when playing (Rossi 7.2 vs Bianchi 6.9), not only whether they play.",
        "missing 2 goalkeepers and 1 forward",
        "contested starter", "difficult away match",
    ]
    risultato = _in_node("en", [[f.json(), str(f)] for f in casi])
    assert risultato == attesi


@CON_NODE
def test_in_inglese_i_numeri_con_il_segno_hanno_il_meno_tipografico():
    """#392: la frase del Confronto in inglese con la differenza dei due numeri mostrati, «−0.6» e «+0.6»; un decimale negativo
    qualunque ha il meno tipografico anche qui."""
    casi = [F("confronto.esito_meglio", titolare="Rossi", attuale=72.66, invertita=72.14, d=frasi.differenza(72.14, 72.66)),
            F("confronto.esito_peggio", invertita=60.56, attuale=60.04, d=frasi.differenza(60.56, 60.04), modulo="3-4-3"),
            F("senso.differenza_piccola", punti=-0.43, giornate=F("tempo.giornate", n=3)),
            F("posto.panchina", n=-3)]
    assert casi[0] == "Con Rossi titolare la formazione vale 72,7 punti attesi; con i due invertiti 72,1 (−0,6)."
    inglese = _in_node("en", [[f.json(), str(f)] for f in casi])
    assert inglese[0] == "With Rossi as a starter the lineup is worth 72.7 expected points; with the two swapped 72.1 (−0.6)."
    assert inglese[1].startswith("Swapping them the lineup would be worth 60.6 instead of 60.0 (+0.6):")
    assert "(−0.4 " in inglese[2] and "-" not in inglese[2]
    assert "−3" in inglese[3] and "-3" not in inglese[3]


@CON_NODE
def test_in_italiano_si_mostra_il_testo_del_server_e_senza_chiave_si_ripiega():
    f = F("dafare.diario", giornata=frasi.nome_giornata(10, 3))
    assert _in_node("it", [[f.json(), str(f)], [None, "testo del server"]]) == [str(f), "testo del server"]
    # inglese ma senza frase, o con una chiave che questa versione non conosce: si prova a riconoscere il testo; se non si riconosce resta com'è
    esito = _in_node("en", [[None, "Frase mai vista"], [{"chiave": "non.esiste", "param": {}}, "Altra frase mai vista"], [None, None]])
    assert esito == ["Frase mai vista", "Altra frase mai vista", None]


# ---------------------------------------------------------------- le rose: avvisi e anteprima con le loro frasi
@CON_NODE
def test_avvisi_delle_rose_e_dell_anteprima_hanno_la_frase(calciatori):
    from test_anteprima_rose import TESTO, leggi, per_testo
    from fanta import lega, nomi, rose
    from fanta.regole import Regole
    r, lette_avvisi = Regole(), []
    lette = rose.estrai([("testo", rose.griglia_da_testo(TESTO))], nomi.Indice(calciatori), r.rosa, lette_avvisi)
    avvisi = lega.controlla(lega.da_import(lette, None), r)
    assert avvisi and all(frasi.di(a) for a in avvisi)                       # ogni avviso dei controlli è una frase con la sua chiave
    inglese = _in_node("en", [[frasi.di(a), str(a)] for a in avvisi])
    assert "Mia: 'Pinco Pallino' not recognised with certainty (transferred or different name?)" in inglese
    assert any(e.startswith("Mia: roster differs from the rules (P 1/3") for e in inglese), inglese
    assert not [e for e in inglese if "non " in e or " di " in e], inglese       # niente italiano rimasto
    a = leggi(TESTO, calciatori)
    kean = per_testo(a)["Kean"]                                               # squadra diversa da quella del listone
    assert kean["avviso"] == "squadra diversa: indicata JUV, nel listone FIO"
    assert kean["avviso_frase"] == {"chiave": "nomi.squadra_diversa", "param": {"indicata": "JUV", "listone": "FIO"}}
    assert len(a["avvisi_frasi"]) == len(a["avvisi"])                         # in parallelo; i riepiloghi per squadra sono testo semplice (l'app li legge dai numeri)
    assert _in_node("en", [[kean["avviso_frase"], kean["avviso"]]]) == ["different team: given JUV, in the player list FIO"]


# ---------------------------------------------------------------- il codice del web che mostra le frasi (node)
@CON_NODE
def test_le_decisioni_in_inglese_e_in_italiano():
    """Le decisioni in cima alla Formazione (`dfDecisioni` e `dfRiga`, dafare.js) con voci vere del server: in inglese testo e
    pulsante tradotti dalla chiave, in italiano il testo del server. La riga «non l'hai ancora salvata» sulla web non è una
    decisione (il salvataggio è automatico): resta fuori."""
    voci = [
        {"id": "dubbio:5", "tipo": "dubbio", "priorita": 2, "testo": str(F("dafare.dubbio_incerto_alt", nome="Rossi", p=55, alt="Adams A.")),
         "frase": F("dafare.dubbio_incerto_alt", nome="Rossi", p=55, alt="Adams A.").json(),
         "azione": "Sostituisci", "azione_frase": F("dafare.az_sostituisci").json(), "destinazione": {"scheda": "formazione"},
         "giocatore": {"id": 5, "nome": "Rossi"}, "alternativa": {"id": 9, "nome": "Adams A.", "ruolo": "C", "punti_attesi": 5.1}},
        {"id": "formazione:9", "tipo": "formazione", "priorita": 1, "testo": str(F("dafare.formazione_chiude", tempo=F("tempo.ore", n=2))),
         "frase": F("dafare.formazione_chiude", tempo=F("tempo.ore", n=2)).json(),
         "azione": "Apri la formazione", "azione_frase": F("dafare.az_formazione").json(), "destinazione": {"scheda": "formazione"}},
        {"id": "rose-vecchie", "tipo": "rose", "priorita": 2, "testo": "Testo già nella lingua della richiesta", "azione": "Aggiorna le rose",
         "destinazione": {"scheda": "lega", "sezione": "rose"}},                                                                                    # voce senza frase (server vecchio)
    ]
    codice = codice_web.leggi("dafare.js")
    prova = TESTI_JS + 'const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");\n' + codice + f"""
    const voci = JSON.parse(String.raw`{json.dumps(voci, ensure_ascii=False)}`);
    const esito = {{}};
    for (const lingua of ["en", "it"]) {{ LINGUA = lingua; esito[lingua] = dfDecisioni(voci).map((v, i) => dfRiga(v, i)).join(""); }}
    console.log(JSON.stringify(esito));
    """
    r = subprocess.run(["node", "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    html = json.loads(r.stdout)
    assert "Rossi is in doubt (55% chance of playing). Better Adams A." in html["en"] and ">Replace<" in html["en"]
    assert "The lineup closes" not in html["en"] and "La formazione si chiude" not in html["it"]
    assert "Testo già nella lingua della richiesta" in html["en"]                    # senza frase resta com'è
    assert "Rossi è in dubbio (55% di giocare). Meglio Adams A." in html["it"] and ">Sostituisci<" in html["it"]


def test_il_web_mostra_le_frasi_tradotte_nei_punti_giusti():
    """I testi del server che cambiano con i dati passano da `traduciFrase`/`testoDi`/`testiDi` (sempre dentro esc()), non da `traduciErrore`."""
    app = codice_web.app()
    anteprima = codice_web.leggi("anteprima.js")
    dafare = codice_web.leggi("dafare.js")
    for pezzo in ('testoEtichetta(traduciFrase(m.frase, m.testo))',                  # motivi sotto il nome (etichette e scheda): esc dentro testoEtichetta
                  'esc(testoDi(o.probabili))', 'esc(testoDi(o.probabili, "avviso"))',     # probabili di Oggi
                  'esc(testoDi(m))',                                                     # «Perché questo numero»
                  'testiDi(r, "avvisi").map(esc)'):                                     # avvisi della rosa
        assert pezzo in app, pezzo
    assert 'esc(testoDi(g, "avviso"))' in anteprima and "traduciFrase(a.frase, a.testo)" in anteprima
    assert 'esc(testoDi(v))' in dafare and 'esc(v.azione ? testoDi(v, "azione")' in dafare
    for sorgente in (app, anteprima, dafare):
        assert "traduciErrore(o.probabili" not in sorgente and "traduciErrore(m.testo" not in sorgente


def test_le_etichette_delle_regole_riconosciute_hanno_la_traduzione():
    """Il testo del regolamento incollato torna con un'etichetta italiana per ogni regola (regole_testo.py): il web la sceglie dalla chiave."""
    from fanta import regole_testo
    it, en = _dizionario("it"), _dizionario("en")
    etichette = {}
    for nodo in ast.walk(ast.parse((PACCHETTO / "regole_testo.py").read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "imposta" and len(nodo.args) >= 2 \
                and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[1], ast.Constant):
            etichette[nodo.args[0].value] = nodo.args[1].value
        if isinstance(nodo, ast.Dict):
            d = {k.value: v.value for k, v in zip(nodo.keys, nodo.values) if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
            if "chiave" in d and "etichetta" in d:
                etichette[d["chiave"]] = d["etichetta"]
    for chiave, etichetta, *_ in regole_testo.BONUS:
        etichette[chiave] = etichetta
    for r, singolare in regole_testo.NOMI_SINGOLARE.items():
        etichette[f"bonus.gol.{r}"] = f"Gol ({singolare})"
        etichette[f"rosa.{r}"] = f"Rosa: {regole_testo.NOMI_PLURALE[r]}"
    assert len(etichette) >= 27
    for chiave, etichetta in etichette.items():
        assert it.get("regola.et." + chiave) == etichetta, chiave
        assert en["regola.et." + chiave]
    assert {k for k in it if k.startswith("regola.et.")} == {"regola.et." + c for c in etichette}


# ---------------------------------------------------------------- gli avvisi sul telefono: italiano e inglese scritti dal server
def test_ogni_avviso_sul_telefono_ha_italiano_e_inglese_con_gli_stessi_segnaposto():
    segnaposto = lambda s: sorted(re.findall(r"\{(\w+)\}", s))      # noqa: E731
    for chiave, (it, en) in NOTIFICHE.items():
        assert segnaposto(it) == segnaposto(en), chiave
        assert en.strip() and chiave.startswith("n."), chiave
        assert chiave not in CATALOGO                              # un nome solo per volta: le chiavi di testi.js non si confondono con queste
    base = sorted({re.sub(r"\.(one|other)$", "", k) for k in NOTIFICHE})
    for chiave in base:
        for n in ((1, 2) if chiave + ".other" in NOTIFICHE else (None,)):
            nomi = set(re.findall(r"\{(\w+)\}", NOTIFICHE.get(chiave, NOTIFICHE.get(chiave + ".other"))[0]))
            f = F(chiave, **({k: ("x" if k != "n" else 2) for k in nomi} | ({"n": n} if n else {})))
            assert "{" not in f and "{" not in f.in_lingua("en"), chiave
            if len(f) > 30:
                assert f.in_lingua("en") != str(f), chiave           # l'inglese c'è davvero


def test_una_frase_nella_lingua_dell_utente():
    f = frasi.elenco([F("n.tra_un_ora", giornata=frasi.nome_giornata(9, 6, avviso=True), ora="18:30"),
                      F("n.consigliato", modulo="3-4-3", punti=71.34)], sep=" ")
    assert f.in_lingua("it") == str(f) == ("Giornata 6 · 9ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 18:30). "
                                          "Consigliato: 3-4-3, 71,3 punti attesi.")
    assert f.in_lingua("en") == ("Matchday 6 · Serie A matchday 9: the lineup closes in about an hour (deadline at 18:30). "
                                 "Recommended: 3-4-3, 71.3 expected points.")
    righe = frasi.elenco([F("n.ora_dubbio", nome="Rossi"), F("n.ora_infortunato", nome="Bianchi")], sep="\n")
    assert righe.in_lingua("en") == "Rossi: now in doubt\nBianchi: now injured" and str(righe) == "Rossi: ora in dubbio\nBianchi: ora infortunato"
    e = frasi.elenco([F("n.m_infortunato", nome="A"), F("n.m_dubbio", nome="B")], con_e=True)
    assert e.in_lingua("en") == "A is injured and B is in doubt" and str(e) == "A è infortunato e B è in dubbio"
    assert frasi.testo("già testo", "en") == "già testo" and frasi.testo(f, "en") == f.in_lingua("en")
