"""Scheda del giocatore e Rosa (27/11/2026): la web mostra quello che decide il server, con un ripiego per un server di prima.

- «Gol e assist rispetto alle occasioni»: frase e colore li sceglieva la web con la soglia 0,3 sul numero; ora il server manda
  `rendimento.tendenza` (`cala`, `sblocca`, `in_linea`) e la frase (`testo`, `frase`). Senza i campi (gli scenari registrati non
  li hanno) resta la soglia.
- La tessera «gol (N rig.)»: il numero è `stagione.gol_con_rigori` del server; senza, la somma di gol e rigori segnati.
- «Prossime partite»: dal campo `prossime_partite` del server, anche senza previsione; senza il campo, dal calendario della
  squadra della previsione o, senza previsione, di quella del listone (come l'iPhone). Prima senza previsione non c'erano.
- Rosa: un giocatore senza quotazione è uscito dal listone e non ha una scheda: il tocco lo dice con la frase del catalogo
  (`err.fuori_listone`) e non chiede la scheda al server, che risponderebbe 404 con la stessa frase.
Gli scenari registrati non hanno i campi nuovi: li aggiunge il test alle risposte registrate (`web.risposta`).
"""
import re

from test_formazione_unica import campo, scheda, solo, tocca

CALA = "Sta segnando più di quanto crea: è probabile che cali."
SBLOCCA = "Crea più di quanto segna: è probabile che si sblocchi."
FUORI_LISTONE = "Questo giocatore non è più nel listone di Serie A."


def _cognome(nome: str) -> str:
    return re.sub(r"\s+\S{1,3}\.$", "", nome)


def _titolare(web, cambia) -> tuple[str, dict]:
    """Un titolare della consigliata registrata con il rendimento; la sua scheda risponde come la cambia `cambia(s)`. Torna il
    cognome e la scheda data alla pagina."""
    web.risposta("/api/scelta?giornata=9", None)                      # si parte dalla consigliata
    f = web.registrata("/api/formazione")
    titolari = next(m for m in f["moduli"] if m["modulo"] == f["modulo"])["titolari"]
    for i in titolari:
        s = web.registrata(f"/api/giocatore/{i}")
        if s.get("rendimento") and s.get("previsione"):
            cambia(s)
            web.risposta(f"/api/giocatore/{i}", s)
            return _cognome(f["schede"][str(i)]["nome"]), s
    raise AssertionError("nello scenario registrato nessun titolare ha il rendimento: il test non proverebbe niente")


def _tutti_i_numeri(web, cognome: str):
    """Apre la scheda del titolare e «Tutti i numeri»; torna la parte aperta."""
    web.apri("/")
    tocca(web, campo(web).filter(has_text=cognome).first)
    tocca(web, scheda(web).get_by_text("Tutti i numeri"))
    return scheda(web).locator("details", has=web.pagina.locator("summary", has_text="Tutti i numeri"))


def _rendimento(parte) -> tuple[str, str]:
    """La frase sotto «Gol e assist rispetto alle occasioni» e la classe del numero grande."""
    return parte.evaluate("""p => {
      const titolo = [...p.querySelectorAll('h3')].find(h => h.textContent.includes('Gol e assist rispetto alle occasioni'));
      const numero = titolo.nextElementSibling, riga = numero.nextElementSibling;
      return [riga.innerText.replace(/\\s+/g, ' ').trim(), numero.className];
    }""")


def test_frase_e_colore_del_rendimento_sono_quelli_del_server(web):
    solo(web, "prima")

    def cambia(s):          # un numero sopra la soglia con il codice «sblocca»: vale il codice del server, non la soglia
        s["rendimento"] |= {"sovra_rendimento": 0.5, "tendenza": "sblocca", "testo": SBLOCCA,
                            "frase": {"chiave": "rendimento.sblocca", "param": {}}}
    frase, classe = _rendimento(_tutti_i_numeri(web, _titolare(web, cambia)[0]))
    assert frase.endswith(SBLOCCA) and CALA not in frase, frase
    assert "negativo" in classe.split() and "positivo" not in classe.split(), classe
    assert not web.errori_console, web.errori_console


def test_senza_il_codice_del_server_la_frase_viene_dalla_soglia(web):
    solo(web, "prima")

    def cambia(s):
        s["rendimento"] = {k: v for k, v in s["rendimento"].items() if k not in ("tendenza", "testo", "frase")} | {"sovra_rendimento": 0.5}
    frase, classe = _rendimento(_tutti_i_numeri(web, _titolare(web, cambia)[0]))
    assert frase.endswith(CALA), frase
    assert "positivo" in classe.split(), classe


def _tessera_gol(parte) -> str:
    return parte.evaluate("""p => {
      const t = [...p.querySelectorAll('.statistiche > div')].find(d => /gol \\(/.test(d.querySelector('span').textContent));
      return t.querySelector('b').textContent.trim();
    }""")


def test_i_gol_con_i_rigori_sono_il_numero_del_server(web):
    solo(web, "prima")

    def cambia(s):
        s["stagione"] |= {"gol": 4, "rig_segnati": 1, "gol_con_rigori": 9}      # 9 e non 5: si vede che il numero è quello del server
    assert _tessera_gol(_tutti_i_numeri(web, _titolare(web, cambia)[0])) == "9"


def test_senza_il_campo_i_gol_si_sommano_come_prima(web):
    solo(web, "prima")

    def cambia(s):
        s["stagione"] = {k: v for k, v in s["stagione"].items() if k != "gol_con_rigori"} | {"gol": 4, "rig_segnati": 1}
    assert _tessera_gol(_tutti_i_numeri(web, _titolare(web, cambia)[0])) == "5"


def _prossime(parte) -> list[str]:
    return [" ".join(c.split()) for c in parte.locator(".prossime > .cella").all_inner_texts()]


def test_le_prossime_partite_del_server_anche_senza_previsione(web):
    solo(web, "prima")
    partite = [{"giornata": 10, "avversario": "como", "in_casa": True, "difficolta": 1, "data": None},
               {"giornata": 11, "avversario": "lazio", "in_casa": False, "difficolta": 5, "data": None}]

    def cambia(s):
        s.pop("previsione")
        s["prossime_partite"] = partite
    celle = _prossime(_tutti_i_numeri(web, _titolare(web, cambia)[0]))
    assert celle == ["vs COM in casa contro Como Facile", "@ LAZ in trasferta contro Lazio Molto dura"], celle   # con la frase per i lettori di schermo


def test_senza_il_campo_le_prossime_partite_sono_quelle_della_squadra_del_listone(web):
    solo(web, "prima")
    cognome, s = _titolare(web, lambda s: s.pop("previsione"))
    squadra = s["calciatore"]["squadra_slug"]
    attese = next(x for x in web.registrata("/api/calendario")["squadre"] if x["squadra"] == squadra)["partite"]
    parte = _tutti_i_numeri(web, cognome)
    parte.get_by_role("heading", name="Prossime partite").wait_for(timeout=10000)
    assert len(_prossime(parte)) == len(attese) > 0


def test_chi_e_uscito_dal_listone_lo_decide_il_server(web):
    """`fuori_listone` di /api/rosa (revisione della #985): vale il campo del server, non la quotazione vuota."""
    solo(web, "prima")
    r = web.registrata("/api/rosa")
    for x in r["giocatori"]:
        x["fuori_listone"] = False
    fuori, dentro = r["giocatori"][0], r["giocatori"][1]
    fuori["fuori_listone"] = True                       # ha la quotazione, ma il server dice che è fuori
    dentro["quotazione"] = None                         # nel listone senza quotazione: la scheda si apre
    web.risposta("/api/rosa", r)
    web.apri("/?vista=impostazioni&gruppo=squadra")
    tocca(web, web.pagina.locator("main .riga-gioc button").filter(has_text=fuori["nome"]).first)
    web.pagina.locator("#avviso").filter(has_text=FUORI_LISTONE).wait_for(timeout=5000)
    assert f"/api/giocatore/{fuori['id']}" not in web.richieste
    tocca(web, web.pagina.locator("main .riga-gioc button").filter(has_text=dentro["nome"]).first)
    assert f"/api/giocatore/{dentro['id']}" in web.richieste


def test_un_server_di_prima_senza_il_campo_si_regola_sulla_quotazione(web):
    """Gli scenari registrati non hanno `fuori_listone`: senza il campo vale il ripiego, la quotazione vuota."""
    solo(web, "prima")
    r = web.registrata("/api/rosa")
    fuori = r["giocatori"][0]
    fuori["quotazione"] = None
    fuori.pop("previsione", None)
    web.risposta("/api/rosa", r)
    web.apri("/?vista=impostazioni&gruppo=squadra")
    riga = web.pagina.locator("main .riga-gioc button").filter(has_text=fuori["nome"]).first
    tocca(web, riga)
    web.pagina.locator("#avviso").filter(has_text=FUORI_LISTONE).wait_for(timeout=5000)
    assert f"/api/giocatore/{fuori['id']}" not in web.richieste, "la scheda di chi non è nel listone non si chiede"
    assert not scheda(web).is_visible(), "nessuna scheda vuota o con un errore"
    # gli altri giocatori della rosa aprono la scheda come prima
    altro = r["giocatori"][1]
    tocca(web, web.pagina.locator("main .riga-gioc button").filter(has_text=altro["nome"]).first)
    assert f"/api/giocatore/{altro['id']}" in web.richieste
