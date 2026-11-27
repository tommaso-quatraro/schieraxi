"""Stato dei dati, «Quanto è affidabile il modello» (#982): i punti della formazione del modello sono verdi quando il server dice che
battono quelli da fantamedia (`sintesi.modello_batte_fantamedia`). Prima la web confrontava da sola i due numeri; con un server di
prima, senza il campo, lo fa ancora. Si guarda il colore che vede l'utente, non il sorgente."""
import pytest

# Il colore del numero e quello del verde dell'app, letti dalla pagina (il verde cambia con il tema).
COLORI = """(numero) => {
  const prova = document.createElement('span');
  prova.style.color = 'var(--verde)';
  numero.parentElement.appendChild(prova);
  const verde = getComputedStyle(prova).color;
  prova.remove();
  return {numero: getComputedStyle(numero).color, verde};
}"""


def _numero_dei_punti(web, sintesi: dict | None):
    """Apre Stato dei dati con la prova registrata (con `sintesi` cambiata, se c'è) e dà il numero «punti formazione (modello)»."""
    if web.fase != "prima":
        pytest.skip("non dipende dalla fase della giornata")
    if sintesi is not None:
        a = web.registrata("/api/affidabilita")
        a["sintesi"] = {**a["sintesi"], **sintesi}
        web.risposta("/api/affidabilita", a)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    web.pagina.locator("main").get_by_role("button", name="Apri lo stato dei dati").first.click(timeout=10000)
    web.aspetta()
    carta = web.pagina.get_by_role("dialog").locator("#affidabilita")
    tessera = carta.locator(".stat-fila > div", has_text="punti formazione (modello)")
    tessera.wait_for(timeout=10000)
    return tessera.locator("b").first


def _verde(numero) -> bool:
    c = numero.evaluate(COLORI)
    return c["numero"] == c["verde"]


def test_server_di_prima_senza_il_campo_verde_dal_confronto(web):
    # le risposte registrate sono di un server di prima: 71,7 contro 70,6, senza `modello_batte_fantamedia`
    assert _verde(_numero_dei_punti(web, None))


def test_il_server_dice_di_no_e_il_numero_non_e_verde(web):
    numero = _numero_dei_punti(web, {"punti_modello": 71.7, "punti_fantamedia": 70.6, "modello_batte_fantamedia": False})
    assert numero.inner_text().strip() == "71,7" and not _verde(numero)


def test_il_server_dice_di_si_e_il_numero_e_verde(web):
    numero = _numero_dei_punti(web, {"punti_modello": 69.9, "punti_fantamedia": 70.1, "modello_batte_fantamedia": True})
    assert numero.inner_text().strip() == "69,9" and _verde(numero)
