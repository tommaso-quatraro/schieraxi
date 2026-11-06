"""Collaudo finale della grafica B (#354), gruppo «navigazione e focus»: #448 (focus nel foglio che cambia contenuto), #449
(Indietro del browser dentro Squadra, Altro e Impostazioni), #450 (titolo del Confronto sotto la ✕), #458 (sezioni di Squadra
con i nomi e l'ordine del menu). Codice vero di app.js e impostazioni.js con node e una cronologia finta che si comporta come
quella del browser (banco di prova di test_navigazione_web.py e del pannello di test_grafica_b_web.py); le prove nel browser vero
(Chrome senza finestra) sono nella descrizione della pull request."""
import json
import re
import shutil
import subprocess

import pytest
from test_grafica_b_web import AMBIENTE_PANNELLO, _codice_pannello
from test_navigazione_web import AMBIENTE, _da_a, _funzione, _riga

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
IMP = (server.WEB / "impostazioni.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
NODE = shutil.which("node")
serve_node = pytest.mark.skipif(not NODE, reason="serve node")


def _node(codice: str):
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- #449: Indietro dentro Squadra, Altro e Impostazioni

# le voci di Squadra e Altro nel banco di prova: Squadre e rose e Aggiorna le rose stanno in Squadra, il resto in Altro
# e vistaLega, come quella vera, usa (e consuma) la voce e la rosa chieste: il disegno le registra
AMBIENTE_LEGA = AMBIENTE.replace('const ambitoVoce = () => "altro";',
                                 'const ambitoVoce = id => (["squadre", "importa"].includes(id) ? "squadra" : "altro");').replace(
    'const vistaLega = a => chiamate.push(["disegna", a]),',
    'const vistaLega = a => { chiamate.push(["disegna", a, stato.legaTorna ?? null, stato.rosaTorna ?? null]); stato.legaTorna = null; '
    'stato.rosaTorna = null; },')
assert AMBIENTE_LEGA.count("ambitoVoce = id") == 1 and AMBIENTE_LEGA.count("stato.rosaTorna = null; }") == 1


def _cronologia(scena: str):
    codice = "\n".join([
        AMBIENTE_LEGA,
        "const sotto = () => ({ voce: stato.legaTorna ?? null, rosa: stato.rosaTorna ?? null, da: (history.state || {}).da ?? null });",
        APP[APP.index("const VISTE = "):APP.index("const SCHEDA_DI = ")], _riga("const SCHEDA_DI = "),
        _riga("const indirizzoVista = "), _riga("let indirizzoMostrato = "),
        _riga("const modificaNonSalvata = "), _funzione("lasciaFormazione"), _riga("const DISEGNO_VISTE = "), _funzione("vai"),
        _da_a('window.addEventListener("popstate"', "\n});\n"),
        _funzione("scriviIndirizzo"), _funzione("indirizzoLega"), _funzione("tornaIndietro"), _funzione("tornaAllaSezione"),
        _riga("function vaiLega("),
        scena,
    ])
    return _node(codice)


@serve_node
def test_ogni_pagina_di_squadra_e_altro_ha_il_suo_indirizzo():
    """Un ricaricamento riapre la pagina: la voce di Squadra o di Altro (`&voce=`) e la rosa di una squadra (`&rosa=`) stanno
    nell'indirizzo. Un nome di squadra con l'apostrofo o gli spazi si scrive come lo scrive il browser (stesso indirizzo dopo)."""
    corpo = _riga("const indirizzoVista = ")
    r = _node(corpo + """
    console.log(JSON.stringify([indirizzoVista("squadra", null, null, "squadre"), indirizzoVista("altro", null, null, "regole"),
      indirizzoVista("squadra", null, null, "squadre", "Dell'Orto FC"), indirizzoVista("squadra", null, null, null, ""),
      indirizzoVista("oggi", null, null, "squadre"), indirizzoVista("mercato", null, "osservati", "osservati")]));""")
    assert r == ["/?vista=squadra&voce=squadre", "/?vista=altro&voce=regole", "/?vista=squadra&rosa=Dell%27Orto+FC",
                 "/?vista=squadra&rosa=", "/?vista=oggi", "/?vista=mercato&scheda=osservati"]


@serve_node
def test_indietro_dalla_voce_e_dalla_rosa_torna_al_passo_di_prima_sotto_i_1100_px():
    """390 px: Squadra › «Squadre e rose» › rosa di un'altra squadra. Ogni passo è una voce della cronologia: Indietro torna alla
    lista delle squadre, poi al menu di Squadra, poi a Oggi (prima uscivano subito su Oggi). Avanti rifà i passi; la voce che si
    riapre (Squadre e rose, la rosa) arriva a vistaLega da `stato.legaTorna` e `stato.rosaTorna`."""
    e = _cronologia("""
    const esiti = {};
    vai("oggi"); vai("squadra"); chiamate.splice(0);
    indirizzoLega("squadra", null, true, "squadre"); esiti.voce = { ...foto(), ...sotto() };            // clic su «Squadre e rose»
    scriviIndirizzo({ vista: "squadra", voce: "squadre", rosa: "Real Esempio", pagina: true }, true);   // clic su una squadra
    esiti.rosa = { ...foto(), ...sotto() };
    history.back(); esiti.indietro1 = { ...foto(), ...sotto() };
    history.back(); esiti.indietro2 = { ...foto(), ...sotto() };
    history.back(); esiti.indietro3 = { ...foto(), ...sotto() };
    history.forward(); history.forward(); history.forward(); esiti.avanti = { ...foto(), ...sotto() };
    console.log(JSON.stringify(esiti));
    """)
    assert e["voce"]["indirizzo"] == "/?vista=squadra&voce=squadre" and e["voce"]["voci"] == 3
    assert e["voce"]["da"] == "/?vista=squadra"                       # la voce di prima è il menu: «‹ Squadra» lo sa
    assert e["rosa"]["indirizzo"] == "/?vista=squadra&rosa=Real+Esempio" and e["rosa"]["voci"] == 4
    assert e["rosa"]["da"] == "/?vista=squadra&voce=squadre"
    assert e["indietro1"]["indirizzo"] == "/?vista=squadra&voce=squadre"
    assert ["disegna", "squadra", "squadre", None] in e["indietro1"]["chiamate"]
    assert e["indietro2"]["indirizzo"] == "/?vista=squadra"                # il menu, non l'ultima voce vista
    assert ["disegna", "squadra", None, None] in e["indietro2"]["chiamate"]
    assert e["indietro3"]["indirizzo"] == "/?vista=oggi" and e["indietro3"]["pos"] == 0
    assert e["avanti"]["indirizzo"] == "/?vista=squadra&rosa=Real+Esempio"
    assert ["disegna", "squadra", "squadre", "Real Esempio"] in e["avanti"]["chiamate"]
    assert not any(c[0] in ("push", "replace") for k in ("indietro1", "indietro2", "indietro3", "avanti") for c in e[k]["chiamate"])


@serve_node
def test_da_1100_px_regole_e_novita_tornano_alla_voce_di_altro():
    """1440 px: Altro apre accanto al menu il Diario (l'indirizzo si corregge, niente voce in più); Regole è una pagina sua con una
    voce nuova: Indietro torna ad Altro con il Diario, poi a Oggi. La scheda «Altro» con una voce di Altro aperta accanto al menu
    non aggiunge voci (la pagina riaprirebbe la stessa); da Regole sì, perché Regole è un'altra pagina."""
    e = _cronologia("""
    const esiti = {};
    largo = true; vai("oggi"); vai("altro"); indirizzoLega("altro", null, false, "diario"); esiti.altro = foto();
    scriviIndirizzo({ vista: "altro", voce: "regole", pagina: true }, true); esiti.regole = { ...foto(), ...sotto() };
    history.back(); esiti.indietro = { ...foto(), ...sotto() };
    vai("altro"); esiti.scheda_altro = foto();
    history.forward(); chiamate.splice(0); vai("altro"); esiti.scheda_da_regole = foto();
    console.log(JSON.stringify(esiti));
    """)
    assert e["altro"]["indirizzo"] == "/?vista=altro&voce=diario" and e["altro"]["voci"] == 2
    assert e["regole"]["indirizzo"] == "/?vista=altro&voce=regole" and e["regole"]["voci"] == 3
    assert e["regole"]["da"] == "/?vista=altro&voce=diario"
    assert e["indietro"]["indirizzo"] == "/?vista=altro&voce=diario" and ["disegna", "altro", "diario", None] in e["indietro"]["chiamate"]
    assert e["scheda_altro"]["voci"] == 3 and not any(c[0] == "push" for c in e["scheda_altro"]["chiamate"])
    assert ["push", "/?vista=altro"] in e["scheda_da_regole"]["chiamate"]


@serve_node
def test_i_pulsanti_indietro_dell_app_non_lasciano_voci_morte():
    """«‹ Squadra» della rosa e «‹ Altro» di Regole e Novità: aperte con un clic dalla loro sezione sono Indietro del browser (la voce
    di prima è la sezione), così Indietro dopo non riporta alla stessa pagina. Aperte da un indirizzo (nessuna voce di prima nella
    sezione) la sezione prende il posto della pagina: nessuna voce in più."""
    e = _cronologia("""
    const esiti = {};
    vai("oggi"); vai("squadra"); indirizzoLega("squadra", null, true, "squadre");
    scriviIndirizzo({ vista: "squadra", voce: "squadre", rosa: "Real Esempio", pagina: true }, true); chiamate.splice(0);
    tornaAllaSezione("squadre"); esiti.rosa_da_clic = { ...foto(), ...sotto() };
    vai("altro"); scriviIndirizzo({ vista: "altro", voce: "novita", pagina: true }, true); chiamate.splice(0);
    tornaAllaSezione("altro"); esiti.novita_da_clic = { ...foto(), ...sotto() };
    // Regole aperta da un indirizzo (o da «Da fare»): la voce di prima non è Altro
    vai("oggi"); stato.legaTorna = "regole"; vai("altro"); scriviIndirizzo({ vista: "altro", voce: "regole", pagina: true }, false);
    const quante = foto().voci;
    tornaAllaSezione("altro"); esiti.regole_da_indirizzo = { ...foto(), ...sotto(), prima: quante };
    console.log(JSON.stringify(esiti));
    """)
    r = e["rosa_da_clic"]
    assert r["indirizzo"] == "/?vista=squadra&voce=squadre" and r["voci"] == 4 and r["pos"] == 2
    assert not any(c[0] in ("push", "replace") for c in r["chiamate"]) and ["disegna", "squadra", "squadre", None] in r["chiamate"]
    n = e["novita_da_clic"]
    assert n["indirizzo"] == "/?vista=altro" and n["pos"] == n["voci"] - 2
    d = e["regole_da_indirizzo"]
    assert d["indirizzo"] == "/?vista=altro" and d["voci"] == d["prima"] and ["disegna", "altro", None, None] in d["chiamate"]
    assert ["replace", "/?vista=altro"] in d["chiamate"] and not any(c[0] == "push" for c in d["chiamate"])
    assert ["focus-titolo", True] in d["chiamate"]


@serve_node
def test_ricaricando_una_voce_non_si_aggiunge_niente_e_si_ricorda_da_dove_si_veniva():
    """Ricaricando (o aprendo) ?vista=squadra&voce=importa l'app riapre la voce senza aggiungere voci alla cronologia, e la voce
    tiene il segno della sezione da cui era stata aperta (lo stato della cronologia resta dopo un ricaricamento). Un'altra scheda
    pulisce la voce chiesta, così non resta per la prossima volta."""
    e = _cronologia("""
    const esiti = {};
    history.replaceState({ vista: "squadra", voce: "importa", da: "/?vista=squadra" }, "", "/?vista=squadra&voce=importa"); chiamate.splice(0);
    stato.legaTorna = "importa"; vai("squadra"); esiti.ricarica = { ...foto(), ...sotto() };
    stato.legaTorna = "importa"; stato.rosaTorna = "X"; vai("oggi"); esiti.oggi = { ...foto(), ...sotto() };
    console.log(JSON.stringify(esiti));
    """)
    assert ["replace", "/?vista=squadra&voce=importa"] in e["ricarica"]["chiamate"] and e["ricarica"]["voci"] == 1
    assert not any(c[0] == "push" for c in e["ricarica"]["chiamate"])
    assert ["disegna", "squadra", "importa", None] in e["ricarica"]["chiamate"]
    assert e["ricarica"]["da"] == "/?vista=squadra"
    assert e["oggi"]["voce"] is None and e["oggi"]["rosa"] is None


@serve_node
def test_impostazioni_ogni_gruppo_ha_la_sua_voce():
    """390 px: Impostazioni › Notifiche era una pagina senza indirizzo, Indietro usciva su Oggi. Il gruppo aperto con un clic scrive
    ?vista=impostazioni&gruppo=…; aperto da solo (da 768 px il primo, o da un indirizzo) corregge la voce di adesso; «‹ Impostazioni»
    torna alla lista come Indietro."""
    codice = "\n".join([
        AMBIENTE_LEGA,
        APP[APP.index("const VISTE = "):APP.index("const SCHEDA_DI = ")], _riga("const SCHEDA_DI = "),
        _riga("const indirizzoVista = "), _riga("let indirizzoMostrato = "),
        _riga("const modificaNonSalvata = "), _funzione("lasciaFormazione"), _riga("const DISEGNO_VISTE = "), _funzione("vai"),
        _da_a('window.addEventListener("popstate"', "\n});\n"),
        _funzione("scriviIndirizzo"), _funzione("tornaIndietro"),
        IMP[IMP.index("function indirizzoImp("):IMP.index("\n}\n", IMP.index("function indirizzoImp(")) + 3],
        IMP[IMP.index("function listaImp("):IMP.index("\n}\n", IMP.index("function listaImp(")) + 3],
        """
        const esiti = {};
        vai("oggi"); vai("impostazioni"); chiamate.splice(0);
        indirizzoImp("avvisi", true); esiti.gruppo = foto();
        history.back(); esiti.indietro = foto();
        history.forward(); chiamate.splice(0); listaImp(); esiti.lista = foto();
        vai("impostazioni"); chiamate.splice(0); indirizzoImp("aspetto", false); esiti.primo = foto();
        console.log(JSON.stringify(esiti));
        """,
    ])
    e = _node(codice)
    assert e["gruppo"]["indirizzo"] == "/?vista=impostazioni&gruppo=avvisi" and e["gruppo"]["voci"] == 3
    assert e["indietro"]["indirizzo"] == "/?vista=impostazioni" and ["disegna", "impostazioni", None] in e["indietro"]["chiamate"]
    assert e["lista"]["indirizzo"] == "/?vista=impostazioni" and e["lista"]["pos"] == 1
    assert not any(c[0] == "disegna" for c in e["lista"]["chiamate"])          # la lista c'è già: Indietro non ridisegna
    assert e["primo"]["chiamate"] == [["replace", "/?vista=impostazioni&gruppo=aspetto"]]


def test_i_pulsanti_e_le_pagine_usano_la_cronologia():
    """I pezzi che scrivono la cronologia sono quelli provati sopra: la voce aperta accanto al menu, Regole, Novità, la rosa, i
    gruppi delle Impostazioni e i loro pulsanti «‹»."""
    lega = _funzione("vistaLega")
    assert "tornaIndietro(" in lega and 'id="lega-indietro"' in lega
    assert "stato.rosaTorna" in lega
    for nome, segno in (("vistaRegole", 'voce: "regole"'), ("vistaNovita", 'voce: "novita"'), ("vistaRosa", "rosa: ")):
        corpo = _funzione(nome)
        assert "scriviIndirizzo(" in corpo and segno in corpo and "pagina: true" in corpo, nome
    assert 'data-indietro="altro"' in _funzione("vistaRegole") and 'data-indietro="altro"' in _funzione("vistaNovita")
    assert 'data-indietro="squadre"' in _funzione("vistaRosa")
    assert 'closest("[data-indietro]")' in APP
    assert "cfg.indirizzo(" in IMP and "cfg.lista(" in IMP
    avvio = APP[APP.index('let iniziale = "oggi";'):APP.index("controllaAccesso().then(")]
    assert 'get("voce")' in avvio and 'get("rosa")' in avvio


# ---------------------------------------------------------------- #448: focus nel foglio che cambia contenuto

@serve_node
def test_foglio_modale_che_cambia_contenuto_porta_il_focus_sul_titolo():
    """Sotto i 1200 px (e per i fogli sempre modali come il Diario) un foglio già aperto che cambia contenuto (ricerca → scheda,
    «Ho schierato la consigliata», «Correggi a mano») perdeva il focus: restava sull'elemento che non c'è più, cioè sul body. Ora va
    sul titolo del contenuto nuovo, come nel pannello affiancato; durante il caricamento (contenuto senza titolo) sulla ✕. Il primo
    foglio con il contenuto pronto resta come prima (✕), e la ricerca che tiene il cursore nel suo campo non cambia."""
    e = _node("\n".join([AMBIENTE_PANNELLO, _codice_pannello(), r"""
    const f = () => document.activeElement && document.activeElement.nome;
    const esiti = {};
    largo = false;
    const riga1 = el("riga1"), campo = el("campo", { dentro: true });
    riga1.focus(); apriFoglio("<div>carico</div>", { affianco: true }); scorri(); esiti.carico = f();
    apriFoglio("<h2>Rossi</h2>", { affianco: true }); scorri(); esiti.arriva = f();
    document.activeElement = corpoPagina;                    // il pulsante premuto nel foglio se n'è andato con il contenuto
    apriFoglio("<div>carico</div>"); scorri(); esiti.ricarico = f();
    apriFoglio("<h2>Diario delle giornate</h2>"); scorri(); esiti.diario = f();
    document.activeElement = corpoPagina; apriFoglio("<h2>Cosa hai schierato</h2>"); scorri(); esiti.correggi = f();
    campo.focus(); apriFoglio("<h2>Cerca</h2>", { affianco: true, focusResta: true }); scorri(); esiti.ricerca = f();
    chiudiFoglio(); scorri(); esiti.chiuso = f();
    riga1.focus(); apriFoglio("<h2>Bianchi</h2>", { affianco: true }); scorri(); esiti.primo = f();
    console.log(JSON.stringify(esiti));
    """]))
    assert e == {"carico": "chiudi", "arriva": "titolo:Rossi", "ricarico": "chiudi", "diario": "titolo:Diario delle giornate",
                 "correggi": "titolo:Cosa hai schierato", "ricerca": "campo", "chiuso": "riga1", "primo": "chiudi"}


def test_il_diario_riaperto_su_una_giornata_porta_li_il_focus():
    """Dopo «Ho schierato la consigliata» o «Salva» il Diario si riapre scorso sulla giornata appena segnata: il focus va sul suo
    titolo, non su quello in cima (il Tab dopo farebbe saltare la pagina all'inizio)."""
    corpo = _funzione("apriDiario")
    i = corpo.index("const daMostrare")
    pezzo = corpo[i:corpo.index('$("#foglio").querySelectorAll("[data-correggi]")', i)]
    assert "scrollIntoView" in pezzo and ".focus({ preventScroll: true })" in pezzo and 'querySelector("h2")' in pezzo


# ---------------------------------------------------------------- #450: il titolo del foglio non passa sotto la ✕

def test_il_primo_titolo_del_foglio_va_a_capo_prima_della_x():
    """A 390 px il titolo del Confronto («Chi schierare? Giornata 11 · 11ª di Serie A») arrivava a x=373 e la ✕ (44 px, 14 px dal
    bordo) parte da x=331: la «A» finale era coperta. Il primo pezzo del foglio lascia a destra il posto della ✕ (anche con il
    riempimento del foglio più piccolo, 8 px nella pagina strettissima); il pannello affiancato da 1200 px ha già la sua regola
    (la ✕ ferma è un float)."""
    m = re.search(r"\nbody:not\(\.con-pannello\) #foglio-contenuto > :first-child \{ padding-right: (\d+)px; \}", CSS)
    assert m
    x = re.search(r"\n\.foglio-chiudi \{[^}]*top: 14px; right: (\d+)px;[^}]*width: (\d+)px", CSS)
    destra, larga = int(x.group(1)), int(x.group(2))
    assert int(m.group(1)) >= destra + larga - 8 + 4                     # riempimento più piccolo del foglio: 8 px; 4 px di stacco


# ---------------------------------------------------------------- #458: sezioni di Squadra come il menu

def test_le_sezioni_di_squadra_hanno_i_nomi_e_l_ordine_del_menu():
    """Sotto i 1100 px le pagine di Squadra (Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario) hanno in cima la fila delle
    quattro sezioni: diceva «Consigliati · Giocatori · Seguiti · Calendario», con nomi diversi e Seguiti/Giocatori al contrario del
    menu. Stessi nomi (le stesse chiavi di testi.js) e stesso ordine di VOCI_LEGA (docs/COERENZA-WEB-IPHONE.md, «Sezioni e menu»)."""
    menu = re.findall(r'\{ id: "(\w+)", ambito: "squadra",[^\n]*?nome: t\("([\w.]+)"\)[^\n]*vaiMercato\(', APP)
    sezioni = re.findall(r'\["(\w+)", "([\w.]+)"\]', re.search(r"const TAB_MERCATO = (\[[^\n]*\]);", APP).group(1))
    assert len(menu) == 4 and sezioni == menu
