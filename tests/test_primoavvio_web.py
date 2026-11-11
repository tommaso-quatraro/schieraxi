"""Primo avvio (fanta/web/primoavvio.js): quale passo viene dopo. La funzione `paPassoDopo` si legge dal file e si prova con node."""
import json
import re
import shutil
import subprocess

import pytest
import codice_web

NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node non installato")

PASSI = ["rose", "squadra"]


def _funzione() -> str:
    src = codice_web.leggi("primoavvio.js")
    m = re.search(r"^function paPassoDopo\(.*?^\}\n", src, re.S | re.M)
    assert m, "paPassoDopo non trovata in primoavvio.js"
    return m.group(0)


def passo_dopo(attuale, fatti, saltati, passi=PASSI):
    codice = _funzione() + (
        f"\nconsole.log(JSON.stringify(paPassoDopo({json.dumps(passi)}, {json.dumps(attuale)}, "
        f"{json.dumps(fatti)}, {json.dumps(saltati)})));"
    )
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_dalle_rose_si_va_alla_squadra():
    assert passo_dopo("rose", [], []) == "squadra"


def test_saltate_le_rose_avanti_sulla_squadra_chiude_il_primo_avvio():
    # Il bug: senza rose, «Avanti» sul passo della squadra restava lì. Ora non c'è più nessun passo aperto: null = si chiude.
    assert passo_dopo("squadra", [], ["rose"]) is None


def test_tutto_fatto_chiude():
    assert passo_dopo("squadra", ["rose", "squadra"], []) is None


def test_se_le_rose_sono_saltate_ma_la_squadra_e_aperta_si_va_alla_squadra():
    assert passo_dopo("rose", [], ["rose"]) == "squadra"


def test_non_torna_mai_al_passo_attuale_se_ce_n_e_un_altro_aperto():
    # Dalla squadra, con le rose ancora aperte: si torna alle rose, non si resta sulla squadra.
    assert passo_dopo("squadra", [], []) == "rose"


# Con il passo «tempi» (dal 2/11/2026): scadenza e prima giornata, dopo la squadra.
PASSI_CON_TEMPI = ["rose", "squadra", "tempi"]


def test_l_elenco_dei_passi_ha_i_tempi_della_lega():
    src = codice_web.leggi("primoavvio.js")
    assert 'const PA_PASSI = ["rose", "squadra", "tempi"];' in src
    assert "scadenza_minuti" in src and "prima_giornata_lega" in src


def test_dopo_la_squadra_vengono_i_tempi():
    assert passo_dopo("squadra", ["rose", "squadra"], [], PASSI_CON_TEMPI) == "tempi"
    # la squadra scelta già nell'anteprima delle rose: dalle rose si salta direttamente ai tempi
    assert passo_dopo("rose", ["rose", "squadra"], [], PASSI_CON_TEMPI) == "tempi"


def test_tempi_fatti_o_saltati_chiude():
    assert passo_dopo("tempi", ["rose", "squadra", "tempi"], [], PASSI_CON_TEMPI) is None
    assert passo_dopo("tempi", ["rose", "squadra"], ["tempi"], PASSI_CON_TEMPI) is None


# ---- #456: nel passo «Le rose» il file si sceglie con il pulsante dell'app, come in Squadra › Aggiorna le rose ----
def _rose_html() -> str:
    testi = codice_web.leggi("testi.js")
    codice = "\n".join([testi, "const esc = x => String(x); const stato = { account: true };",
                        codice_web.leggi("primoavvio.js"), "console.log(JSON.stringify(PA_SCHERMATE.rose().html));"])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_il_file_si_sceglie_con_il_pulsante_dell_app():
    html = _rose_html()
    campo = re.search(r"<input id=\"pa-file\"[^>]*>", html).group(0)
    assert 'type="file"' in campo and " hidden" in campo                  # il controllo del browser non si vede più
    assert re.search(r'<button class="bottone secondario" id="pa-scegli-file" type="button">Scegli il file Excel</button>', html)
    assert re.search(r'<p class="debole piccolo" id="pa-file-nome" role="status"[^>]*></p>', html)   # il nome del file scelto
    src = codice_web.leggi("primoavvio.js")
    assert '$("#pa-scegli-file").addEventListener("click", () => $("#pa-file").click())' in src
    assert '$("#pa-file").addEventListener("change"' in src


# ---- #578: dopo «Torna indietro» il file sbagliato non resta scelto e non blocca il testo incollato ----
# Il codice vero del passo «Le rose» gira in node con un DOM finto minimo. Il campo del file si comporta come nel browser:
# `files` si legge soltanto, `value = ""` lo svuota, qualsiasi altro valore è rifiutato. `anteprimaRose` (anteprima.js) è
# finta: ricorda cosa le si manda e restituisce le sue opzioni, da cui il test tocca «Torna indietro» (`opz.annulla`).
DOM_ROSE = r"""
const elementi = {}, mandati = [];
function nuovo(id) {
  const e = { id, value: "", textContent: "", innerHTML: "", hidden: false, disabled: false, ascoltatori: {},
              addEventListener(tipo, fn) { (this.ascoltatori[tipo] ||= []).push(fn); }, focus() {}, click() {} };
  return (elementi[id] = e);
}
const $ = sel => elementi[sel.slice(1)] || null;
const emetti = (e, tipo) => (e.ascoltatori[tipo] || []).forEach(fn => fn({ target: e }));
for (const id of ["pa-ingresso", "pa-testo", "pa-scegli-file", "pa-file-nome", "pa-esempi", "pa-anteprima", "pa-msg",
                  "pa-avanti", "pa-salta"]) nuovo(id);
const campoFile = nuovo("pa-file");
let scelti = [];
Object.defineProperty(campoFile, "files", { get: () => scelti });
Object.defineProperty(campoFile, "value", {
  get: () => (scelti.length ? "C:\\fakepath\\" + scelti[0].name : ""),
  set: v => { if (v !== "") throw new Error("InvalidStateError: solo una stringa vuota"); scelti = []; },
});
const scegliFile = nome => { scelti = [{ name: nome }]; emetti(campoFile, "change"); };
let ultime = null;
function anteprimaRose(dove, sorgente, opz) {
  mandati.push(sorgente.file ? { file: sorgente.file.name } : { testo: sorgente.testo });
  ultime = opz;
}
const api = async () => ({}), avviso = () => {};
"""


def _rose_scenario(passi: str) -> dict:
    """Disegna il passo «Le rose», esegue `passi` (codice async: `scegliFile(nome)`, `ultime.annulla()` = «Torna indietro»,
    `scrivi(testo)`, `await controlla()` = «Controlla le rose») e restituisce cosa è stato mandato e cosa resta sullo schermo."""
    testi = codice_web.leggi("testi.js")
    codice = "\n".join([
        testi, "const esc = x => String(x); const stato = { account: true };", DOM_ROSE, codice_web.leggi("primoavvio.js"),
        "const schermata = PA_SCHERMATE.rose(); schermata.dopo();",
        'const scrivi = testo => { $("#pa-testo").value = testo; emetti($("#pa-testo"), "input"); };',
        "const controlla = () => schermata.esegui();",
        f"(async () => {{ {passi};",
        '  console.log(JSON.stringify({ mandati, file_nel_campo: campoFile.files.length, scritta: $("#pa-file-nome").textContent }));',
        "})().catch(e => { console.error(e.stack || e); process.exit(1); });",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


TESTO_ROSE = "P;Portiere Uno;ABC;1"


def test_dopo_torna_indietro_controlla_le_rose_manda_il_testo_incollato():
    # Il difetto di #578: calendario scelto, «nessuna rosa», «Torna indietro», testo incollato, «Controlla le rose»:
    # tornava al server il calendario (400) e il testo non veniva mai letto.
    esito = _rose_scenario(f"scegliFile('calendario.csv'); ultime.annulla(); scrivi({json.dumps(TESTO_ROSE)}); await controlla()")
    assert esito["mandati"] == [{"file": "calendario.csv"}, {"testo": TESTO_ROSE}]


def test_torna_indietro_dimentica_il_file_scelto():
    esito = _rose_scenario("scegliFile('calendario.csv'); ultime.annulla()")
    assert esito["file_nel_campo"] == 0
    assert esito["scritta"] == ""                     # niente più «File scelto: calendario.csv» sullo schermo


def test_incollare_un_testo_dimentica_il_file_scelto():
    # Anche senza passare da «Torna indietro»: si vede il testo, si manda il testo.
    esito = _rose_scenario(f"scegliFile('calendario.csv'); scrivi({json.dumps(TESTO_ROSE)}); await controlla()")
    assert esito["mandati"][-1] == {"testo": TESTO_ROSE}
    assert esito["file_nel_campo"] == 0 and esito["scritta"] == ""


def test_dopo_torna_indietro_senza_testo_controlla_chiede_cosa_controllare():
    # Il file dimenticato non torna fuori: con il riquadro vuoto «Controlla le rose» non manda niente e chiede il testo o un file.
    esito = _rose_scenario(
        "scegliFile('calendario.csv'); ultime.annulla();"
        " try { await controlla(); } catch (e) { mandati.push({ errore: e.message }); }")
    assert esito["mandati"] == [{"file": "calendario.csv"}, {"errore": "Incolla il testo delle rose o scegli un file"}]


def test_scegliere_un_file_buono_dopo_torna_indietro_lo_controlla():
    esito = _rose_scenario("scegliFile('calendario.csv'); ultime.annulla(); scegliFile('rose.xlsx')")
    assert esito["mandati"] == [{"file": "calendario.csv"}, {"file": "rose.xlsx"}]
    assert esito["scritta"] == "File scelto: rose.xlsx"
