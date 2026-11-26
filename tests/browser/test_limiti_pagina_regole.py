"""Regole e scadenza, «Modifica i valori»: i numeri delle regole e i loro limiti (#881, parte B, collaudo del 25/11/2026).

4. Un campo svuotato si salvava come 0, con «Regole salvate». Ora un campo vuoto è un errore che dice quale campo, e non si
   manda niente al server.
5. I pulsanti − e + avevano limiti loro, diversi da quelli del server (arrivavano a 14 cambi e a 0 portieri, che il server
   rifiuta) e i numeri scritti a mano non avevano limiti. Ora pulsanti e numeri scritti a mano usano i limiti del server
   (`fanta/web/limiti-regole.json`): un numero fuori dai limiti si dice prima di salvare, con il nome del campo.

Si guarda ciò che vede chi usa la pagina (nomi dei campi, avvisi, richieste che partono), non il sorgente. Non dipendono dalla
fase della giornata: girano solo prima della scadenza.
"""
import re

import pytest


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("vale per la fase: prima")


def principale(web):
    return web.pagina.locator("main")


def tocca(web, bersaglio) -> None:
    bersaglio.click(timeout=10000)
    web.aspetta()


def scritture(web) -> list[str]:
    """Le richieste che scrivono le regole (PUT /api/regole), man mano che partono."""
    viste = []
    web.pagina.on("request", lambda r: r.method == "PUT" and r.url.split("?")[0].endswith("/api/regole") and viste.append(r.url))
    return viste


def apri_valori(web, *sezioni: str, inglese: bool = False) -> None:
    """Regole e scadenza con «Modifica i valori» aperto e le sezioni chieste aperte («Punteggi» è già aperta)."""
    if inglese:
        web.memoria({"lingua": "en"})
    web.apri("/?vista=impostazioni&gruppo=regole")
    tocca(web, principale(web).get_by_text("Edit the values" if inglese else "Modifica i valori", exact=True))
    for s in sezioni:
        tocca(web, principale(web).get_by_text(s, exact=True))


def campo(web, nome: str):
    return principale(web).get_by_role("textbox", name=nome, exact=True)


def avviso(web) -> str:
    stato = web.pagina.get_by_role("status").filter(has_text=re.compile(r"\S"))
    stato.first.wait_for(timeout=5000)
    return stato.first.inner_text().strip()


def test_un_campo_svuotato_non_si_salva_come_zero(web):
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web)
    campo(web, "Assist").fill("")
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert avviso(web) == "«Assist» è vuoto: scrivi un numero"
    assert salvate == [], "con un campo vuoto le regole sono partite verso il server"
    assert campo(web, "Assist").evaluate("e => e === document.activeElement")          # il cursore è nel campo da sistemare


@pytest.mark.parametrize("nome, valore, frase", [
    ("Assist", "99", "«Assist» deve essere tra 0 e 20"),
    ("Autogol", "3", "«Autogol» deve essere tra −20 e 0"),
])
def test_un_numero_scritto_fuori_dai_limiti_si_dice_prima_di_salvare(web, nome, valore, frase):
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web)
    campo(web, nome).fill(valore)
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert avviso(web) == frase
    assert salvate == []


def test_i_pulsanti_non_superano_i_cambi_che_il_server_accetta(web):
    solo_prima(web)
    apri_valori(web, "Panchina e sostituzioni")
    cambi = campo(web, "Cambi massimi")
    cambi.fill("9")
    piu = cambi.locator("xpath=..").get_by_role("button", name="Aumenta")
    tocca(web, piu)
    tocca(web, piu)
    assert cambi.input_value() == "10"


def test_i_pulsanti_non_scendono_a_zero_portieri(web):
    solo_prima(web)
    apri_valori(web, "Rosa e crediti")
    portieri = campo(web, "Portieri")
    portieri.fill("2")
    meno = portieri.locator("xpath=..").get_by_role("button", name="Diminuisci")
    tocca(web, meno)
    tocca(web, meno)
    assert portieri.input_value() == "1"


def test_in_inglese_il_campo_vuoto_si_dice_in_inglese(web):
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web, inglese=True)
    campo(web, "Assist").fill("")
    tocca(web, principale(web).get_by_role("button", name="Save the rules"))
    assert avviso(web) == "“Assist” is empty: enter a number"
    assert salvate == []


def test_valori_validi_si_salvano_come_prima(web):
    """Con i valori dentro i limiti il salvataggio parte, come prima."""
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web)
    campo(web, "Assist").fill("1,5")
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert salvate, "le regole valide non sono partite"
    assert not web.errori_mostrati()


# ---------------------------------------------------------------- revisione di #886
def corpi_scritti(web) -> list[dict]:
    """I corpi delle richieste che scrivono le regole (PUT /api/regole), man mano che partono."""
    import json
    corpi = []
    web.pagina.on("request", lambda r: r.method == "PUT" and r.url.split("?")[0].endswith("/api/regole")
                  and corpi.append(json.loads(r.post_data or "null")))
    return corpi


@pytest.mark.parametrize("sezione, nome, valore, nell_avviso", [
    ("Rosa e crediti", "Portieri", "3,5", "Portieri della rosa"),       # la riga dei posti in panchina si chiama uguale (#889)
    ("Rosa e crediti", "Crediti iniziali", "500,5", "Crediti iniziali"),
    ("Panchina e sostituzioni", "Cambi massimi", "2,5", "Cambi massimi"),
])
def test_un_numero_con_la_virgola_in_un_campo_intero_si_dice_prima_di_salvare(web, sezione, nome, valore, nell_avviso):
    """«3,5» portieri passava la pagina e il server rispondeva «rosa.P deve essere un numero intero», con il nome interno."""
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web, sezione)
    campo(web, nome).fill(valore)
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert avviso(web) == f"«{nell_avviso}» deve essere un numero intero"
    assert salvate == []


# ---------------------------------------------------------------- nomi distinti nell'avviso, come l'iPhone (#889)
def nella_sezione(web, sezione: str, nome: str):
    """Il campo `nome` della sezione di «Modifica i valori» intitolata `sezione` (due sezioni hanno righe con lo stesso titolo)."""
    return principale(web).locator("details.regola-sez").filter(has_text=sezione).get_by_role("textbox", name=nome, exact=True)


@pytest.mark.parametrize("sezione, valore, frase", [
    ("Rosa e crediti", "40", "«Difensori della rosa» deve essere tra 1 e 30"),
    ("Panchina e sostituzioni", "11", "«Posti in panchina per i difensori» deve essere tra 0 e 10"),
])
def test_due_righe_con_lo_stesso_titolo_si_distinguono_nell_avviso(web, sezione, valore, frase):
    """Con i posti fissi in panchina ci sono due righe «Difensori» (rosa e panchina): l'avviso diceva «Difensori» per tutte e
    due. Ora dice il nome del campo, come il server e l'iPhone (`err.p_regola_*`), e la riga resta «Difensori»."""
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web, sezione)
    nella_sezione(web, sezione, "Difensori").fill(valore)
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert avviso(web) == frase
    assert salvate == []


@pytest.mark.parametrize("chiave, frase", [
    ("voto_senza_sostituto", "«Voto d'ufficio di chi resta senza sostituto» deve essere tra 0 e 10"),
    ("voto_ufficio_rinviate", "«Voto d'ufficio delle partite rinviate» deve essere tra 0 e 10"),
])
def test_i_due_voti_d_ufficio_si_distinguono_nell_avviso(web, chiave, frase):
    """Due righe «Voto d'ufficio» (chi resta senza sostituto, partite rinviate): l'avviso dice quale (#889). Il valore fuori dai
    limiti arriva dalle regole salvate; il voto delle partite rinviate si controlla anche nascosto."""
    solo_prima(web)
    web.risposta("/api/regole", web.registrata("/api/regole") | {chiave: 12})
    salvate = scritture(web)
    apri_valori(web)
    campo(web, "Assist").fill("1,5")                                    # una modifica qualsiasi: compare «Salva le regole»
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert avviso(web) == frase
    assert salvate == []


def test_con_il_modificatore_spento_le_fasce_nascoste_non_si_controllano(web):
    """Una fascia svuotata e poi il modificatore spento: le fasce sono nascoste, non si controllano e restano quelle salvate."""
    solo_prima(web)
    corpi = corpi_scritti(web)
    salvate = web.registrata("/api/regole")["modificatore_difesa"]
    apri_valori(web, "Modificatore difesa")
    campo(web, "Fascia 1, media almeno").fill("")
    spento = principale(web).get_by_role("checkbox", name=re.compile(r"^Attivo nella mia lega"))
    spento.set_checked(False)
    web.aspetta()
    assert not spento.is_checked()
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert corpi, "con il modificatore spento le regole non sono partite"
    md = corpi[-1]["modificatore_difesa"]
    assert md["attivo"] is False and md["soglie"] == salvate["soglie"] and md["min_difensori"] == salvate["min_difensori"]
    assert not web.errori_mostrati()


# ---------------------------------------------------------------- il segno meno (collaudo del 26/11/2026)
MENO = "−"          # il meno tipografico «−», quello dell'anteprima del regolamento e degli avvisi


@pytest.mark.parametrize("scritto", [f"{MENO}0,5", "-0,5", f"{MENO}0.5"])
def test_un_negativo_si_legge_con_il_meno_vero_o_con_il_trattino(web, scritto):
    """«−0,5» scritto con il meno vero (U+2212, quello che la pagina stessa scrive nell'anteprima) non si leggeva: «Salva le regole»
    diceva «Ci sono valori non numerici» senza dire quale campo. Ora valgono «−» e «-», la virgola e il punto, e parte −0,5."""
    solo_prima(web)
    corpi = corpi_scritti(web)
    apri_valori(web)
    campo(web, "Ammonizione").fill(scritto)
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert corpi, f"con «{scritto}» le regole non sono partite"
    assert corpi[-1]["bonus"]["ammonizione"] == -0.5, corpi[-1]["bonus"]
    assert not web.errori_mostrati()


def test_nei_campi_i_negativi_hanno_il_meno_vero(web):
    """I campi scrivevano «-0,5» con il trattino, mentre l'anteprima del regolamento e gli avvisi scrivono «−0,5». Ora anche i
    campi, all'apertura e dopo − e +; lo zero resta senza segno."""
    solo_prima(web)
    regole = web.registrata("/api/regole")
    regole["bonus"] |= {"ammonizione": -0.5}
    web.risposta("/api/regole", regole)
    apri_valori(web)
    amm = campo(web, "Ammonizione")
    assert amm.input_value() == f"{MENO}0,5"
    riga = amm.locator("xpath=..")
    tocca(web, riga.get_by_role("button", name="Diminuisci"))
    assert amm.input_value() == f"{MENO}1,0"
    tocca(web, riga.get_by_role("button", name="Aumenta"))
    tocca(web, riga.get_by_role("button", name="Aumenta"))
    assert amm.input_value() == "0,0"


def test_un_valore_che_non_e_un_numero_dice_quale_campo(web):
    """«Ci sono valori non numerici: correggili prima di salvare» non diceva dove: con circa 45 campi, molti chiusi, bisognava
    cercarlo. Ora l'avviso dice il nome del campo, come per un campo vuoto o fuori dai limiti."""
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web)
    campo(web, "Ammonizione").fill("mezzo punto")
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert avviso(web) == "«Ammonizione» non è un numero: correggilo prima di salvare"
    assert salvate == []
    assert campo(web, "Ammonizione").evaluate("e => e === document.activeElement")
