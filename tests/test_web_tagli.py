"""Web senza le funzioni tolte il 12/11/2026 (#615): cosa succede a ciò che puntava a una schermata che non c'è più.

Si esegue il codice vero della web con Node (niente ricerca di testo nel sorgente): quali righe di «Da fare» del server sono
decisioni da mostrare in cima alla Formazione (#616: al massimo due, solo con un'azione vera), e un indirizzo vecchio apre la
schermata più vicina che resta. Le schermate si provano nel browser: tests/browser/.
"""
import json
import re
import shutil
import subprocess

import pytest

import codice_web

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node non installato")


def _node(codice: str):
    out = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _con_dafare(voci: list[dict], espressione: str):
    """Il valore di un'espressione JavaScript su `voci`, con `dafare.js` caricato per intero. I testi sono le loro chiavi
    (`t` finta): il pulsante di una riga si riconosce dalla chiave del suo testo."""
    sorgente = codice_web.leggi("dafare.js")
    codice = f"""
      const vm = require("vm");
      const ctx = {{ t: k => k, tp: (k, n) => k + ":" + n, esc: x => String(x), testoDi: (v, c) => (c ? v[c] : v.testo) }};
      vm.createContext(ctx);
      vm.runInContext({json.dumps(sorgente)} + "\\n;globalThis.voci = " + {json.dumps(json.dumps(voci))} + ";globalThis.fuori = "
                      + {json.dumps(espressione)} + ";", ctx);
      console.log(JSON.stringify(ctx.fuori));
    """
    return _node(codice)


def _decisioni(voci: list[dict]) -> list[str]:
    """Gli id delle decisioni che la Formazione mostra in cima (al massimo due)."""
    return _con_dafare(voci, "dfDecisioni(voci).map(v => v.id)")


def _voce(id: str, tipo: str, scheda: str, sezione: str | None = None, **extra) -> dict:
    return {"id": id, "tipo": tipo, "testo": f"testo di {id}", "priorita": 2, "azione": "Apri",
            "destinazione": {"scheda": scheda, "sezione": sezione, **extra}}


def test_le_decisioni_sono_solo_le_righe_con_un_azione_vera():
    """Via i due consigli delle funzioni tolte (svincolato, scambio; #615) e ciò che non chiede niente (#616): il titolare incerto
    senza un cambio da fare, «non l'hai ancora salvata» (il salvataggio è automatico), «dimmi se hai schierato la consigliata».
    Restano il cambio di un titolare, la consigliata cambiata, le rose da aggiornare, il reparto scoperto (porta anche lui a
    «mercato», ma è un avviso da non perdere) e gli avvisi di chi gestisce."""
    una = lambda v: _decisioni([v])
    assert una({**_voce("dubbio:1", "dubbio", "formazione", giocatore=1), "alternativa": {"id": 2, "nome": "Prova"}}) == ["dubbio:1"]
    assert una(_voce("dubbio:1", "dubbio", "formazione")) == []
    assert una(_voce("consigliata:9", "formazione", "formazione")) == ["consigliata:9"]
    assert una(_voce("formazione:9", "formazione", "formazione")) == []
    assert una(_voce("svincolato:7", "svincolato", "mercato", giocatore=7)) == []
    assert una(_voce("scambio:Atletico Prova", "scambio", "scambi")) == []
    assert una(_voce("diario:5", "diario", "lega", "diario", giornata=5)) == []
    for resta in (_voce("copertura:P", "copertura", "mercato"), _voce("copertura:moduli", "copertura", "formazione"),
                  _voce("rose-vecchie", "rose", "lega", "rose"), _voce("dati-vecchi", "server", "impostazioni", "avanzate"),
                  _voce("primo-avvio", "primo_avvio", "impostazioni", "informazioni")):
        assert una(resta) == [resta["id"]]


def test_le_decisioni_sono_al_massimo_due_e_il_reparto_scoperto_non_nasconde_le_altre():
    """Senza righe urgenti: prima quelle con un'azione vera, nell'ordine del server; il reparto senza ricambi («Vedi la rosa»)
    prende al massimo un posto, e solo se ne resta uno: due righe di copertura nascondevano «rose da aggiornare» o un cambio."""
    copertura_p, copertura_d = _voce("copertura:P", "copertura", "mercato"), _voce("copertura:D", "copertura", "mercato")
    rose, dati = _voce("rose-vecchie", "rose", "lega", "rose"), _voce("dati-vecchi", "server", "impostazioni", "avanzate")
    incerto = _voce("dubbio:1", "dubbio", "formazione")                                       # non chiede niente: non conta
    assert _decisioni([incerto, copertura_p, copertura_d, rose]) == ["rose-vecchie", "copertura:P"]
    assert _decisioni([copertura_p, copertura_d]) == ["copertura:P"]
    assert _decisioni([copertura_p, rose, dati]) == ["rose-vecchie", "dati-vecchi"]
    assert _decisioni([copertura_p, rose]) == ["rose-vecchie", "copertura:P"]
    # `vale`: la Formazione toglie quelle che con la formazione in pagina non hanno più senso, e allora sale la successiva
    voci = [incerto, copertura_p, rose, dati]
    assert _con_dafare(voci, "dfDecisioni(voci, v => v.id !== 'rose-vecchie').map(v => v.id)") == ["dati-vecchi", "copertura:P"]


def test_le_decisioni_urgenti_stanno_in_cima():
    """Prima le righe urgenti (priorità 1), e fra loro prima quelle con un'azione vera; poi le non urgenti con un'azione; poi il
    resto. Dentro ogni gruppo resta l'ordine del server. Un «nessun portiere» urgente restava nascosto da due righe meno importanti."""
    urgente = lambda v: {**v, "priorita": 1}                                                  # noqa: E731
    scoperto_p, scoperto_d = urgente(_voce("copertura:P", "copertura", "mercato")), urgente(_voce("copertura:D", "copertura", "mercato"))
    rischio = _voce("copertura:C", "copertura", "mercato")                                    # reparto senza ricambi: non urgente
    cambio = {**_voce("dubbio:1", "dubbio", "formazione", giocatore=1), "alternativa": {"id": 2, "nome": "Prova"}}
    rose, dati = _voce("rose-vecchie", "rose", "lega", "rose"), _voce("dati-vecchi", "server", "impostazioni", "avanzate")
    primo_avvio = {**_voce("primo-avvio", "primo_avvio", "impostazioni", "informazioni"), "priorita": 3}
    assert _decisioni([scoperto_p, cambio, rose]) == ["copertura:P", "dubbio:1"]
    assert _decisioni([scoperto_p, rose]) == ["copertura:P", "rose-vecchie"]
    assert _decisioni([scoperto_p, dati, primo_avvio]) == ["copertura:P", "dati-vecchi"]
    assert _decisioni([rose, dati, scoperto_p]) == ["copertura:P", "rose-vecchie"]            # conta l'urgenza, non il posto nella lista
    assert _decisioni([scoperto_p, urgente(cambio), rose]) == ["dubbio:1", "copertura:P"]     # fra le urgenti prima quella con un'azione
    assert _decisioni([scoperto_p, urgente(cambio), urgente(rose)]) == ["dubbio:1", "rose-vecchie"]
    assert _decisioni([scoperto_p, scoperto_d]) == ["copertura:P"]                            # al massimo una riga sul reparto scoperto
    assert _decisioni([scoperto_p, scoperto_d, rose]) == ["copertura:P", "rose-vecchie"]
    assert _decisioni([rischio, scoperto_d, rose]) == ["copertura:D", "rose-vecchie"]         # delle due sul reparto resta quella urgente
    assert _decisioni([cambio, rischio, rose]) == ["dubbio:1", "rose-vecchie"]


def test_il_pulsante_di_una_decisione_dice_dove_porta():
    """«Cerca un rimpiazzo» apriva Cambi consigliati, che sulla web non c'è più: il pulsante dice «Vedi la rosa». «La consigliata è
    cambiata» prende la consigliata. Le altre righe tengono il testo del server; i punti in più del cambio stanno accanto al testo."""
    voci = [{**_voce("copertura:P", "copertura", "mercato"), "azione": "Cerca un rimpiazzo"}, _voce("consigliata:9", "formazione", "formazione"),
            {**_voce("dubbio:1", "dubbio", "formazione"), "azione": "Sostituisci"}]
    righe = _con_dafare(voci, "voci.map((v, i) => dfRiga(v, i, i === 2 ? '+0,9 punti.' : ''))")
    pulsanti = [re.search(r'data-df="(\d+)"[^>]*>([^<]*)<', r).groups() for r in righe]
    assert pulsanti == [("0", "lega.vedi_rosa"), ("1", "formazione.usa_consigliata"), ("2", "Sostituisci")]
    assert "+0,9 punti." in righe[2] and "punti" not in righe[0]
    # sulla copia tenuta sul telefono i pulsanti che scrivono sul server sono spenti (restano al loro posto); gli altri no
    cambio = {**_voce("dubbio:2", "dubbio", "formazione", giocatore=1), "alternativa": {"id": 2, "nome": "Prova"}}
    spente = _con_dafare([voci[0], voci[1], cambio], "voci.map((v, i) => dfRiga(v, i, '', true))")
    assert ["disabled" in r for r in spente] == [False, True, True]
    assert all("disabled" not in r for r in righe) and ["data-scrive" in r for r in righe] == [False, True, False]


def test_le_decisioni_tengono_una_riga_senza_destinazione_e_scartano_quelle_senza_testo():
    voci = [{"id": "senza-destinazione", "tipo": "certificato", "testo": "Rinnova"}, {"id": "rotta", "tipo": "rose"}, None]
    assert _decisioni(voci) == ["senza-destinazione"]


def _dove(q: dict, account=None, altrui=True):
    """`dove` di app.js (#618): la schermata di un indirizzo, anche di una versione di prima. `account`: None (server senza account),
    "utente" o "amministratore"; `altrui`: le rose degli altri si vedono. La mia squadra è «Mia Esempio»."""
    js = codice_web.app()
    pezzo = js[js.index("const PAGINE_IMP = "):js.index("// opz.daCronologia")]
    codice = "\n".join([
        f"const stato = {{ account: {json.dumps({'ruolo': account} if account else None)}, squadre: [{{ nome: 'Mia Esempio', mia: true }}, {{ nome: 'Altra Prova' }}] }};",
        "const miaSquadra = () => stato.squadre.find(s => s.mia);",
        f"const funz = id => id !== 'squadre_altrui' || {json.dumps(altrui)};",
        "const soloAmministratore = () => !stato.account || stato.account.ruolo === 'amministratore';",
        pezzo,
        f"const r = dove({json.dumps(q)});",
        "console.log(JSON.stringify({ vista: r.vista, gruppo: r.gruppo ?? null, rosa: r.rosa ?? null, sezione: r.sezione ?? null }));",
    ])
    return _node(codice)


def _imp(gruppo=None, rosa=None, sezione=None):
    return {"vista": "impostazioni", "gruppo": gruppo, "rosa": rosa, "sezione": sezione}


FORMAZIONE = {"vista": "formazione", "gruppo": None, "rosa": None, "sezione": None}
GIORNATE = {"vista": "giornate", "gruppo": None, "rosa": None, "sezione": None}


@pytest.mark.parametrize("q, attesa", [
    # le pagine tolte il 12/11/2026 (#615) stavano in Squadra e in Altro, che dal #618 sono Impostazioni
    ({"vista": "mercato"}, _imp(sezione="lega")),                                   # Cambi consigliati, Seguiti, Elenco, Calendario
    ({"vista": "mercato", "voce": "calendario"}, _imp(sezione="lega")),
    ({"vista": "squadra", "voce": "osservati"}, _imp(sezione="lega")),
    ({"vista": "scambi"}, _imp()),
    ({"vista": "altro", "voce": "movimenti"}, _imp()),
    ({"vista": "altro", "voce": "crediti"}, _imp()),
    ({"vista": "altro", "voce": "stagione"}, _imp()),
    ({"vista": "lega", "voce": "crediti"}, _imp()),
    # le novità si leggono in Impostazioni > Informazioni
    ({"vista": "altro", "voce": "novita"}, _imp("informazioni")),
    ({"vista": "lega", "voce": "novita"}, _imp("informazioni")),
])
def test_un_indirizzo_di_una_pagina_tolta_apre_impostazioni(q, attesa):
    assert _dove(q) == attesa


@pytest.mark.parametrize("q, attesa", [
    ({"vista": "oggi"}, FORMAZIONE),                                               # Oggi è diventata la Formazione (#616)
    ({"vista": "formazione"}, FORMAZIONE),
    ({"vista": "giornate"}, GIORNATE),                                             # il Diario come pagina (#617)
    ({"vista": "diario"}, GIORNATE),
    ({"vista": "altro", "voce": "diario"}, GIORNATE),
    ({"vista": "lega", "voce": "diario"}, GIORNATE),
    # Squadra e Altro (#618): i menu sono Impostazioni, le voci le sue pagine
    ({"vista": "squadra"}, _imp(sezione="lega")),
    ({"vista": "altro"}, _imp()),
    ({"vista": "lega"}, _imp()),
    ({"vista": "squadra", "voce": "importa"}, _imp("rose")),
    ({"vista": "lega", "voce": "importa"}, _imp("rose")),
    ({"vista": "altro", "voce": "importa"}, _imp("rose")),
    ({"vista": "squadra", "voce": "squadre"}, _imp("squadre")),
    ({"vista": "altro", "voce": "regole"}, _imp("regole")),
    ({"vista": "lega", "voce": "regole"}, _imp("regole")),
    ({"vista": "regole"}, _imp("regole")),
    ({"vista": "rosa"}, _imp("squadra")),
    ({"vista": "squadra", "rosa": ""}, _imp("squadra")),                           # la rosa senza nome è la mia
    ({"vista": "squadra", "rosa": "Mia Esempio"}, _imp("squadra")),
    ({"vista": "squadra", "rosa": "Altra Prova"}, _imp("squadre", rosa="Altra Prova")),
    # i gruppi delle Impostazioni di prima (#449)
    ({"vista": "impostazioni"}, _imp()),
    ({"vista": "impostazioni", "gruppo": "avvisi"}, _imp(sezione="avvisi")),
    ({"vista": "impostazioni", "gruppo": "aspetto"}, _imp(sezione="aspetto")),
    ({"vista": "impostazioni", "gruppo": "informazioni"}, _imp("informazioni")),
    ({"vista": "impostazioni", "gruppo": "avanzate"}, _imp("gestione")),           # server senza account: si gestisce
    ({"vista": "impostazioni", "gruppo": "account"}, _imp()),                      # senza account la pagina non c'è
    ({"vista": "impostazioni", "gruppo": "squadre", "rosa": "Altra Prova"}, _imp("squadre", rosa="Altra Prova")),
    ({"vista": "impostazioni", "gruppo": "__proto__"}, _imp()),
    # un nome che non c'è porta alla Formazione
    ({"vista": "__proto__"}, FORMAZIONE),
    ({"vista": "constructor", "voce": "importa"}, FORMAZIONE),
    ({}, FORMAZIONE),
])
def test_ogni_indirizzo_porta_alla_schermata_giusta(q, attesa):
    assert _dove(q) == attesa


def test_le_pagine_che_chi_usa_l_app_non_ha_portano_a_impostazioni():
    assert _dove({"vista": "impostazioni", "gruppo": "account"}, account="utente") == _imp("account")
    assert _dove({"vista": "impostazioni", "gruppo": "gestione"}, account="utente") == _imp()
    assert _dove({"vista": "impostazioni", "gruppo": "avanzate"}, account="utente") == _imp()
    assert _dove({"vista": "impostazioni", "gruppo": "gestione"}, account="amministratore") == _imp("gestione")
    # senza le rose degli altri: niente «Le altre squadre», la rosa di un'altra squadra porta alla mia
    assert _dove({"vista": "squadra", "voce": "squadre"}, altrui=False) == _imp("squadra")
    assert _dove({"vista": "squadra", "rosa": "Altra Prova"}, altrui=False) == _imp("squadra")
