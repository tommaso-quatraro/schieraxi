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


@pytest.mark.parametrize("sezione, nome, valore", [
    ("Rosa e crediti", "Portieri", "3,5"),
    ("Rosa e crediti", "Crediti iniziali", "500,5"),
    ("Panchina e sostituzioni", "Cambi massimi", "2,5"),
])
def test_un_numero_con_la_virgola_in_un_campo_intero_si_dice_prima_di_salvare(web, sezione, nome, valore):
    """«3,5» portieri passava la pagina e il server rispondeva «rosa.P deve essere un numero intero», con il nome interno."""
    solo_prima(web)
    salvate = scritture(web)
    apri_valori(web, sezione)
    campo(web, nome).fill(valore)
    tocca(web, principale(web).get_by_role("button", name="Salva le regole"))
    assert avviso(web) == f"«{nome}» deve essere un numero intero"
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
