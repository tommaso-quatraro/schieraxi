"""La Formazione unica della web (#616), con node: i pezzi che decidono cosa si legge.
- sul campo e nelle righe «gioca N%» solo sotto l'80% (arancio fra 50 e 79, rosso sotto 50), mai le etichette di titolarità;
- lo stato a parole solo per «in dubbio», «infortunato», «squalificato», «fuori», «rinviata»;
- il perché di un titolare regge `altro` e `riserva` che mancano (null);
- la scheda del giocatore prima della partita, a partita in corso e finita, con «Sostituisci» solo per chi si può sostituire;
- la testa della schermata nelle tre fasi della giornata.
Il comportamento intero (tocchi, salvataggio, spunta «L'ho messa») è nei test del browser: tests/browser/test_formazione_unica.py."""
import json
import re
import shutil
import subprocess

import pytest

import codice_web

APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="serve node")

# l'orologio fermo: la scadenza si conta da qui, mai dall'ora vera
OROLOGIO = ("const FERMO = Date.parse('2026-10-26T09:35:00'), DataVera = Date;\n"
            "globalThis.Date = class extends DataVera { constructor(...a) { super(...(a.length ? a : [FERMO])); } static now() { return FERMO; } };")


def _pezzo(inizio: str, fine: str) -> str:
    a = APP.index(inizio)
    return APP[a:APP.index(fine, a)]


def _riga(nome: str) -> str:
    return re.search(rf"^const {nome} = .*$", APP, re.M).group(0)


BASE = "\n".join([_pezzo("function esc(x)", "const sigla ="), _riga("num"), _riga("perc"), _riga("segno"), _riga("ruoloSigla"),
                  _pezzo("const SIGLE =", "const NOMI_DIFF"), _riga("sigla"), _pezzo("function parseData(s)", "// ETag e If-Match")])
STATI = "\n".join([_pezzo("const STATO_PARTITA =", "// Le regole riconosciute"),
                   _pezzo("// Lo stato di un giocatore, dal codice", "// Il nome del club"), _riga("nomeClub"),
                   _pezzo("const SOGLIA_GIOCA", "// Il numero della giornata, uguale")])
RIGHE = _pezzo("const nomeFvAtteso", "// ---------------------------------------------------------------- navigazione")
COGNOME = _riga("cognome")


def _esegui(chiamata: str, *pezzi: str, lingua: str = "it"):
    codice = "\n".join([TESTI, f"LINGUA = {json.dumps(lingua)};", OROLOGIO, BASE, *pezzi, f"console.log(JSON.stringify({chiamata}));"])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _testo(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _visibile(html: str) -> str:
    """Il testo che si vede: senza quello scritto solo per i lettori di schermo."""
    return _testo(re.sub(r'<span class="solo-lettori">.*?</span>', " ", html, flags=re.S))


def _giocatore(**campi) -> dict:
    return {"id": 7, "nome": "Rossi L.", "ruolo": "C", "squadra": "genoa", "avversario": "parma", "in_casa": True,
            "data_partita": "2026-10-31 20:45", "p_voto": 0.92, "fv_atteso": 6.8, "punti_attesi": 6.3, "titolarita": "titolare",
            "etichetta": {"codice": "titolare", "testo": "Probabile titolare", "tono": "positivo"}} | campi


# ---------------------------------------------------------------- la pedina e le righe
def test_sulla_pedina_gioca_solo_sotto_l_80():
    casi = [_giocatore(), _giocatore(p_voto=0.796), _giocatore(p_voto=0.65), _giocatore(p_voto=0.3)]
    sicuro, arrotondato, medio, basso = _esegui(f"{json.dumps(casi)}.map(x => pedina(x))", STATI, COGNOME)
    assert _visibile(sicuro) == "6,8 Rossi"                                # solo il numero e il cognome
    assert "gioca" not in _visibile(arrotondato)                           # 79,6% si legge «80%»: non è sotto l'80%
    assert '<span class="gioca medio" aria-hidden="true">gioca 65%</span>' in medio
    assert '<span class="gioca basso" aria-hidden="true">gioca 30%</span>' in basso
    # i lettori di schermo sentono le stesse cose che si vedono
    assert _testo(sicuro).endswith("Rossi L., fantavoto atteso 6,8") and "gioca al 65 per cento" in _testo(medio)


@pytest.mark.parametrize("codice, testo", [("titolare", "Probabile titolare"), ("ballottaggio", "In ballottaggio"),
                                           ("panchina", "Probabile panchina"), ("improbabile", "Improbabile")])
def test_le_etichette_di_titolarita_non_si_mostrano(codice, testo):
    """«Titolare» e «panchina» vogliono dire la tua formazione: quanto è probabile che giochi lo dice «gioca N%»."""
    x = _giocatore(p_voto=0.45, titolarita=codice, etichetta={"codice": codice, "testo": testo, "tono": "attenzione"})
    pedina, riga, parola = _esegui(f"(x => [pedina(x), etichetteGiocatore(x) + numeriRiga(x), parolaStato(x)])({json.dumps(x)})",
                                   STATI, COGNOME, RIGHE)
    assert parola is None
    assert testo not in pedina and testo not in riga
    assert "gioca 45%" in _visibile(pedina) and '<span class="pv-g basso">gioca 45%</span>' in riga


def test_lo_stato_a_parole_e_niente_gioca_per_chi_non_gioca_di_sicuro():
    dubbio = _giocatore(p_voto=0.55, etichetta={"codice": "in_dubbio", "testo": "In dubbio · gioca 55%", "tono": "attenzione"})
    fermo = _giocatore(p_voto=0.0, stato="infortunato", etichetta={"codice": "infortunato", "testo": "Infortunato", "tono": "negativo"})
    vecchio = {k: v for k, v in fermo.items() if k != "etichetta"} | {"stato": "squalificato"}        # server vecchio: dai campi grezzi
    esiti = _esegui(f"{json.dumps([dubbio, fermo, vecchio])}.map(x => [pedina(x), numeriRiga(x), parolaStato(x)])", STATI, COGNOME, RIGHE)
    (p_dubbio, r_dubbio, s_dubbio), (p_fermo, r_fermo, s_fermo), (p_vecchio, _, s_vecchio) = esiti
    assert s_dubbio == {"codice": "in_dubbio", "classe": "arancio", "testo": "In dubbio"}             # senza « · gioca 55%»: sta accanto
    assert _visibile(p_dubbio) == "6,8 Rossi gioca 55% In dubbio" and '<span class="pv-g medio">gioca 55%</span>' in r_dubbio
    assert s_fermo["classe"] == "rossa" and _visibile(p_fermo) == "6,8 Rossi Infortunato"             # la parola basta: niente «gioca 0%»
    assert '<span class="pv-g"></span>' in r_fermo
    assert s_vecchio["testo"] == "Squalificato" and "gioca" not in _visibile(p_vecchio)


def test_la_nota_delle_probabili_spiega_lo_stato_nelle_righe_e_nella_scheda():
    """«contusione al ginocchio, in forte dubbio»: il motivo di «In dubbio» o di «Infortunato» (campo `nota` della scheda). Si legge
    nella riga, sotto lo stato, e nella scheda del giocatore; non sulla pedina (non c'è spazio) e non per chi non ha uno stato."""
    nota = "contusione al ginocchio, in forte dubbio <dal 1'>"
    dubbio = _giocatore(p_voto=0.19, nota=nota, etichetta={"codice": "in_dubbio", "testo": "In dubbio · gioca 19%", "tono": "attenzione"})
    fermo = _giocatore(p_voto=0.0, nota="lombalgia, out a Roma", stato="infortunato",
                       etichetta={"codice": "infortunato", "testo": "Infortunato", "tono": "negativo"})
    sano = _giocatore(nota="rientra dalla squalifica")                    # nessuno stato da spiegare: la riga resta pulita
    r_dubbio, r_fermo, r_sano, pedina = _esegui(
        f"(g => [...g.map(x => etichetteGiocatore(x)), pedina(g[0])])({json.dumps([dubbio, fermo, sano])})", STATI, COGNOME, RIGHE)
    assert _testo(r_dubbio) == "In dubbio contusione al ginocchio, in forte dubbio &lt;dal 1&#39;&gt;"
    assert '<span class="etichetta neutra nota-stato">' in r_dubbio and "<dal" not in r_dubbio       # testo della fonte: sempre con esc()
    assert _testo(r_fermo) == "Infortunato lombalgia, out a Roma"
    assert r_sano == ""
    assert "contusione" not in pedina
    scheda = _scheda(dubbio)
    assert '<p class="scheda-nota">contusione al ginocchio, in forte dubbio &lt;dal 1&#39;&gt;</p>' in scheda
    assert scheda.index('class="cifre-oggi cifre-scheda"') < scheda.index('class="scheda-nota"') < scheda.index('id="scheda-voti"')
    assert "scheda-nota" not in _scheda(_giocatore())                     # senza nota niente riga vuota
    in_corso = dubbio | {"stato_partita": "in_corso", "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}}
    assert "scheda-nota" not in _scheda(in_corso, sostituibile=False)      # a partita cominciata la nota di prima non serve più


def test_a_partita_cominciata_sulla_pedina_il_voto_preso_o_lo_stato():
    preso = _giocatore(stato_partita="fatto", fv_preso=7.5, etichetta={"codice": "voto", "testo": "Ha giocato", "tono": "positivo"})
    arrivo = _giocatore(stato_partita="attesa_voti", etichetta={"codice": "voto_in_arrivo", "testo": "Voto in arrivo", "tono": "neutro"})
    dopo = _giocatore(p_voto=0.4, stato_partita="da_giocare", etichetta={"codice": "da_giocare", "testo": "Da giocare", "tono": "neutro"})
    a, b, c = _esegui(f"{json.dumps([preso, arrivo, dopo])}.map(x => pedina(x))", STATI, COGNOME)
    assert _visibile(a) == "7,5 Rossi" and 'class="pedina"' in a
    assert _visibile(b) == "6,8 Rossi Voto in arrivo" and 'class="pedina attesa"' in b               # il disco vuoto: l'atteso, non un voto
    assert _visibile(c) == "6,8 Rossi sab 31 20:45" and 'class="pedina attesa"' in c                 # formazione chiusa: quando gioca
    assert _testo(c).endswith("Rossi L., fantavoto atteso 6,8, sab 31 20:45")                        # e i lettori di schermo lo stesso: niente «gioca al 40»


# ---------------------------------------------------------------- il perché di un titolare
PERCHE = _pezzo("function percheTitolare(", "// Anticipi già cominciati")


def test_il_perche_di_un_titolare_regge_altro_e_riserva_che_mancano():
    schede = {"5": {"id": 5, "nome": "Rossi L.", "p_voto": 0.35}, "9": {"id": 9, "nome": "Gallo <b>", "p_voto": 0.95}}
    moduli = [
        {"perche_scelta": [{"titolare": 5, "altro": None, "testo": "Titolare: nessun compagno di ruolo gioca di più."}]},
        {"perche_scelta": [{"titolare": 5, "altro": 9, "testo": "Preferito a Gallo: rigorista."}], "incerti": [{"titolare": 5, "riserva": 9}]},
        {"incerti": [{"titolare": 5, "riserva": None}]},                 # titolare incerto senza una riserva sicura: niente frase a metà
        {"incerti": [{"titolare": 5, "riserva": 9}]},
        {"perche_scelta": None, "incerti": None},
        {},
    ]
    esiti = _esegui(f"(s => {json.dumps(moduli)}.map(m => percheTitolare(m, 5, id => s[String(id)])))({json.dumps(schede)})", PERCHE)
    assert esiti[0] == "Titolare: nessun compagno di ruolo gioca di più."
    assert esiti[1] == "Preferito a Gallo: rigorista."                     # la frase del server viene prima degli incerti
    assert esiti[2] == ""
    assert esiti[3] == ("Titolare anche se incerto (gioca 35%): se non gioca, in panchina c'è Gallo &lt;b&gt; che gioca quasi di sicuro, "
                        "e insieme valgono di più.")
    assert esiti[4] == "" and esiti[5] == ""


# ---------------------------------------------------------------- la scheda del giocatore
SCHEDA = "\n".join(["const volto = () => ''; const NOME_RUOLO_1 = { P: 'Portiere', D: 'Difensore', C: 'Centrocampista', A: 'Attaccante' };",
                    _pezzo("function bloccoPerche(x)", "// Gli ultimi voti e «Tutti i numeri»")])
CALCIATORE = {"id": 7, "nome": "Rossi L.", "ruolo": "C", "squadra": "Genoa", "squadra_slug": "genoa"}


def _scheda(pr, sostituibile=True, perche="", lingua="it", fermo=False, pronta=True) -> str:
    fz = (f"{{ perche: () => {json.dumps(perche)}, sostituibile: () => {json.dumps(sostituibile)}, fermo: () => {json.dumps(fermo)}, "
          f"pronta: () => {json.dumps(pronta)} }}")
    return _esegui(f"htmlScheda({json.dumps(CALCIATORE)}, {json.dumps(pr)}, {fz})", STATI, SCHEDA, lingua=lingua)


def test_la_scheda_prima_della_partita():
    motivi = [{"chiave": "forma", "testo": "È in forma: 3 bonus nelle ultime 5.", "effetto": 0.4}, {"chiave": "gioca", "testo": "Gioca al 65%.", "effetto": None}]
    html = _scheda(_giocatore(p_voto=0.65, in_casa=False, perche_numero=motivi, fv_atteso_medio_ruolo=6.1), perche="Preferito a Gallo: rigorista.")
    testo = _testo(html)
    assert "In trasferta contro parma · sab 31 20:45" in testo
    assert "Fantavoto atteso, se gioca 6,8" in testo                       # il numero grande, con il suo nome
    assert '<div class="grande gioca-medio">65%</div>' in html             # «gioca N%» nel colore che ha sul campo
    assert "Perché è titolare Preferito a Gallo: rigorista." in testo
    assert "È in forma: 3 bonus nelle ultime 5." in testo and "Gioca al 65%." in testo
    assert '<button class="bottone" type="button" data-sostituisci="7">Sostituisci</button>' in html
    assert "Probabile titolare" not in html                                # la titolarità non si scrive nemmeno qui
    # in ordine: numeri, perché è titolare, perché questo numero, ultimi voti, Sostituisci, e in fondo «Tutti i numeri» chiuso
    ordine = [html.index(x) for x in ('class="cifre-oggi cifre-scheda"', 'id="perche-titolare"', 'class="perche"', 'id="scheda-voti"',
                                      "data-sostituisci", '<details class="scheda-numeri"')]
    assert ordine == sorted(ordine)
    assert "<details open" not in html
    sicuro = _scheda(_giocatore())
    assert '<div class="grande">92%</div>' in sicuro                       # sopra l'80% senza colore
    en = _scheda(_giocatore(p_voto=0.3), lingua="en")
    assert "Expected fantasy score, if he plays" in _testo(en) and '<div class="grande gioca-basso">30%</div>' in en and ">Replace<" in en


def test_la_scheda_di_chi_non_si_puo_sostituire_non_ha_il_pulsante():
    """Chi gioca un anticipo già cominciato, chi non è titolare, la formazione chiusa o di un'altra squadra: niente «Sostituisci»."""
    panchina = _scheda(_giocatore(), sostituibile=False)
    assert "data-sostituisci" not in panchina and "non si può più spostare" not in panchina
    # un titolare che gioca un anticipo già cominciato: al posto del pulsante, perché non si sposta (#373)
    # sulla copia tenuta sul telefono (dati nuovi in arrivo) il pulsante c'è ma è spento: resta al suo posto
    assert '<button class="bottone" type="button" data-sostituisci="7" disabled>Sostituisci</button>' in _scheda(_giocatore(), pronta=False)
    fermo = _scheda(_giocatore(), sostituibile=False, fermo=True)
    assert "data-sostituisci" not in fermo
    assert '<p class="debole piccolo" id="scheda-fermo">Chi gioca in una partita già cominciata non si può più spostare.</p>' in fermo
    senza_formazione = _esegui(f"htmlScheda({json.dumps(CALCIATORE)}, {json.dumps(_giocatore())}, null)", STATI, SCHEDA)
    assert "data-sostituisci" not in senza_formazione and 'id="perche-titolare"' not in senza_formazione   # dalla ricerca o dalla rosa
    senza_previsione = _esegui(f"htmlScheda({json.dumps(CALCIATORE)}, null, null)", STATI, SCHEDA)
    assert "Nessuna previsione" in _testo(senza_previsione) and 'id="scheda-voti"' in senza_previsione


def test_la_scheda_a_partita_in_corso_e_finita():
    motivi = [{"chiave": "forma", "testo": "È in forma.", "effetto": 0.4}, {"chiave": "gioca", "testo": "Gioca al 65%.", "effetto": None}]
    base = _giocatore(p_voto=0.65, perche_numero=motivi, fv_atteso_medio_ruolo=6.1)
    corso = _scheda(base | {"stato_partita": "in_corso", "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}}, sostituibile=False)
    assert "Partita in corso" in _testo(corso) and "65%" not in corso and "Gioca al 65%." not in corso   # «gioca N%» non serve più
    assert "Fantavoto atteso, se gioca 6,8" in _testo(corso) and "È in forma." in corso
    finita = _scheda(base | {"stato_partita": "fatto", "fv_preso": 7.5, "etichetta": {"codice": "voto", "testo": "Ha giocato", "tono": "positivo"}}, sostituibile=False)
    assert "fantavoto 7,5" in _testo(finita) and "atteso" not in _testo(finita).split("Ultimi voti")[0]   # resta solo com'è andata
    assert 'class="perche"' not in finita
    senza = _scheda(base | {"stato_partita": "senza_voto", "etichetta": {"codice": "senza_voto", "testo": "Senza voto", "tono": "attenzione"}}, sostituibile=False)
    assert '<div class="grande stato-partita">Senza voto</div>' in senza and "6,8" not in senza


# ---------------------------------------------------------------- la testa nelle tre fasi
TESTA = "\n".join([_pezzo("function nomeGiornata(", "// La partita in una riga"), _pezzo("const MODI_RINVIO", "function collegaRinvio"),
                   _pezzo("const scadenzaDi = ", "// Account nuovo, senza rose"), _pezzo("function testaGiornata(", "// A giornata in corso: i cambi")])
F = {"giornata": 11, "giornata_lega": 8}


def _testa(o, f=F, lingua="it") -> str:
    return _esegui(f"testaGiornata({json.dumps(o)}, {json.dumps(f)})", TESTA, lingua=lingua)


def test_la_testa_prima_della_scadenza():
    html = _testa({"fase": "prima", "giornata": 11, "scadenza": "2026-10-26 14:50"})
    assert _testo(html) == "Giornata 8 · 11ª di Serie A Si chiude oggi 14:50 fra 5 h 15 min"
    assert 'id="conto-chiude"' in html and 'id="conto"' in html            # il conto si aggiorna da solo
    assert _testo(_testa({"fase": "prima", "scadenza": "2026-10-26 14:50"}, lingua="en")).endswith("Closes today 14:50 in 5 h 15 min")
    # la formazione di un'altra squadra: solo la giornata
    assert _testo(_testa(None)) == "Giornata 8 · 11ª di Serie A"


def test_la_testa_a_giornata_in_corso():
    corso = {"punti_fatti": 34.5, "punti_previsti": 71.4, "ancora_da_giocare": 5, "giocatori": []}
    testo = _testo(_testa({"fase": "in_corso", "scadenza": "2026-10-25 14:50", "in_corso": corso}))
    assert testo == "Giornata 8 · 11ª di Serie A · in corso 34,5 punti finora · circa 71 a fine giornata 5 giocatori devono ancora giocare"
    tutti = _testo(_testa({"fase": "in_corso", "in_corso": corso | {"ancora_da_giocare": 0, "punti_previsti": None}}))
    assert "circa" not in tutti and tutti.endswith("Hanno giocato tutti: mancano solo i voti ufficiali.")
    # arrivato a partite cominciate: niente punti, la formazione è già quella della prossima giornata
    saltata = _testa({"fase": "in_corso", "senza_formazione": True, "prossima": {"scadenza": "2026-10-31 14:50"}},
                     F | {"giornata_saltata": 10, "giornata_saltata_lega": 7})
    assert "punti" not in _testo(saltata) and "Si chiude sab 31 14:50" in _testo(saltata) and 'id="formazione-prossima"' in saltata


def test_la_testa_a_giornata_finita():
    r = {"giornata": 10, "giornata_lega": 7, "formazione_di": "tua", "punti_fatti": 68.5, "punti_attesi": 64.2,
         "consigliata": {"punti_fatti": 72.0, "punti_attesi": 66.1}}
    html = _testa({"fase": "finita", "riepilogo": r, "prossima": {"scadenza": "2026-10-31 14:50"}})
    testo = _testo(html)
    assert testo.startswith("Giornata 7 · 10ª di Serie A: finita 68,5 punti (attesi 64,2) Com'è andata")
    assert '<button class="bottone secondario" type="button" data-apri-diario="10">Com\'è andata</button>' in html
    assert "Con la consigliata: 72,0 punti (66,1 attesi)." in testo
    assert testo.endswith("Giornata 8 · 11ª di Serie A Si chiude sab 31 14:50 fra 5 giorni 5 h")   # sotto, la prossima
    # con la consigliata schierata (o gli stessi punti) il confronto non si ripete
    uguale = _testo(_testa({"fase": "finita", "riepilogo": r | {"formazione_di": "consigliata"}}))
    assert "Con la consigliata" not in uguale
    stessi = _testo(_testa({"fase": "finita", "riepilogo": r | {"consigliata": {"punti_fatti": 68.5, "punti_attesi": 64.2}}}))
    assert "Con la consigliata" not in stessi
