"""La pagina «Giornate», che ha preso il posto del Diario (#617): una pagina della barra, una riga sulla precisione con i dettagli
a richiesta, una riga per giornata dalla più recente e, al tocco, gli 11 con il fantavoto atteso e quello preso.

Il confronto «tu contro la consigliata» si vede solo dove la consigliata è quella mostrata prima della scadenza
(`consigliata.origine == "mostrata"`, #614). Il server di oggi non manda `origine`: lì il confronto non si mostra. Le due forme
della risposta si provano con risposte finte (`web.risposta`), costruite su quella registrata.

Si guarda ciò che vede chi usa l'app (ruoli, etichette, testi), non il sorgente.
"""
import copy
import json
import re

import pytest

GIORNATE = "/?vista=giornate"
PC = 1440


def solo(web, *fasi):
    if web.fase not in fasi:
        pytest.skip(f"vale per la fase: {', '.join(fasi)}")


def principale(web):
    return web.pagina.locator("main")


def titolo(web) -> str:
    return principale(web).get_by_role("heading", level=1).inner_text().strip()


def tocca(web, bersaglio) -> None:
    (web.pagina.locator(bersaglio).first if isinstance(bersaglio, str) else bersaglio).click(timeout=10000)
    web.aspetta()


def righe(web):
    """Le righe delle giornate: nell'elenco «Giornate finite», ognuna è un pulsante che apre e chiude i suoi 11 (aria-expanded).
    Il nome comincia con quello della giornata: «Giornata 5» nella stagione in corso, «30ª giornata di Serie A» in una passata."""
    return principale(web).get_by_role("list", name="Giornate finite").locator("button[aria-expanded]")


def nomi_righe(web) -> list[str]:
    return [re.match(r"Giornata \d+", " ".join(x.split())).group(0) for x in righe(web).all_inner_texts()]


def riga(web, nome: str):
    return principale(web).get_by_role("button", name=re.compile(rf"^{nome}\b"))


def dettaglio(web, nome: str):
    return principale(web).get_by_role("region", name=re.compile(rf"^{nome}\b"))


def nome_di(g: dict) -> str:
    return f"Giornata {g['giornata_lega'] if g.get('giornata_lega') is not None else g['giornata']}"


def undici(g: dict) -> dict:
    """La formazione che conta per la giornata: la tua, la copia fatta alla scadenza, o la consigliata (come nel riepilogo
    della Formazione a giornata finita)."""
    return g.get("schierata") or g.get("automatica") or g["consigliata"]


def virgola(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def con_voti(g: dict, voti: dict[int, tuple[float, float | None]]) -> None:
    """Mette nella voce numeri scelti dal test per alcuni giocatori: {id: (fantavoto atteso, fantavoto preso o None)}."""
    for x in g["giocatori"]:
        if x["id"] in voti:
            x["fv_atteso"], x["fv"] = voti[x["id"]]


def con_una_tua_diversa(d: dict, i: int, da: int, punti: float = 80.0) -> list[str]:
    """Nella giornata `i` mette come formazione schierata gli 11 consigliati della giornata `da` (altri 11 della stessa rosa).
    Torna i nomi di chi c'è nella tua e non nella consigliata."""
    g, altra = d["giornate"][i], d["giornate"][da]["consigliata"]
    g["schierata"] = {**copy.deepcopy(altra), "reale": punti, "atteso": 70.0, "tipo": "manuale"}
    loro = {x["id"] for x in g["consigliata"]["titolari"]}
    return [x["nome"] for x in g["schierata"]["titolari"] if x["id"] not in loro]


def scelta_diversa(g: dict, differenza: float) -> dict:
    """La voce di `scelte_tue.per_giornata` che il server calcola per una giornata con 11 diversi dai consigliati."""
    tue, loro = {x["id"] for x in g["schierata"]["titolari"]}, {x["id"] for x in g["consigliata"]["titolari"]}
    return {"stagione": g["stagione"], "giornata": g["giornata"], "giornata_lega": g.get("giornata_lega"),
            "hai_scelto": [x["nome"] for x in g["schierata"]["titolari"] if x["id"] not in loro],
            "consigliava": [x["nome"] for x in g["consigliata"]["titolari"] if x["id"] not in tue],
            "punti_tua": g["schierata"]["reale"], "punti_consigliata": round(g["schierata"]["reale"] - differenza, 1),
            "differenza": differenza, "esito": "tua" if differenza > 0 else "consigliata" if differenza < 0 else "pari"}


def forma_di_oggi(web) -> tuple[dict, list[str]]:
    """La risposta come la dà il server di oggi: niente `origine`. Nella prima giornata 11 diversi da quelli consigliati, e
    `scelte_tue` li confronta con la consigliata rifatta a giornata finita."""
    d = web.registrata("/api/diario")
    dentro = con_una_tua_diversa(d, 0, 1)
    d["scelte_tue"] = {"giornate": 1, "meglio_tua": 0, "meglio_consigliata": 1, "pari": 0, "punti_differenza": -3.0, "percentuale_tua": 0,
                       "pochi_dati": True, "per_giornata": [scelta_diversa(d["giornate"][0], -3.0)]}
    return d, dentro


def forma_di_domani(web) -> tuple[dict, list[str]]:
    """La risposta come la darà il server con #614: nella prima giornata la consigliata è quella mostrata prima della scadenza e
    gli 11 schierati sono diversi; nella seconda è mostrata e gli 11 sono gli stessi; nella terza la mostrata non c'è (`origine`
    «ricostruita») e gli 11 sono diversi: lì niente confronto."""
    d = web.registrata("/api/diario")
    g0, g1, g2 = d["giornate"][:3]
    for g in d["giornate"]:
        g["consigliata"]["origine"] = "ricostruita"
        g["ricostruita"] = copy.deepcopy(g["consigliata"])
        g["modificabile"] = True
    dentro = con_una_tua_diversa(d, 0, 1)
    con_una_tua_diversa(d, 2, 1)
    g0["consigliata"]["origine"] = g1["consigliata"]["origine"] = "mostrata"
    g1["schierata"] = {**copy.deepcopy(g1["consigliata"]), "tipo": "consigliata", "confermata": True}
    g1["schierata"].pop("origine")
    d["scelte_tue"] = {"giornate": 1, "meglio_tua": 0, "meglio_consigliata": 1, "pari": 0, "punti_differenza": -1.5, "percentuale_tua": 0,
                       "pochi_dati": True, "per_giornata": [scelta_diversa(g0, -1.5)], "senza_istantanea": 1}
    d["sintesi"] = {**d["sintesi"], "senza_consigliata_mostrata": 1}
    return d, dentro


# ---------------------------------------------------------------- una pagina, a un tocco
def test_giornate_si_apre_con_un_tocco_dalla_barra(web):
    web.apri("/?vista=formazione")
    voce = web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link", name="Giornate")
    tocca(web, voce)
    assert titolo(web) == "Giornate"
    assert web.pagina.url.endswith(GIORNATE)
    assert voce.get_attribute("aria-current") == "page"
    assert righe(web).count() >= 1, web.testo_principale()
    assert web.pagina.get_by_role("dialog").count() == 0 or not web.pagina.get_by_role("dialog").is_visible()      # una pagina, non un foglio
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


@pytest.mark.parametrize("vecchio", ["/?vista=altro&voce=diario", "/?vista=lega&voce=diario"])
def test_l_indirizzo_vecchio_del_diario_apre_giornate(web, vecchio):
    solo(web, "prima")
    web.apri(vecchio)
    assert titolo(web) == "Giornate"
    assert web.pagina.url.endswith(GIORNATE)                             # l'indirizzo non resta quello vecchio
    assert righe(web).count() >= 1 and not web.errori_mostrati()


def test_com_e_andata_apre_la_giornata_appena_finita(web):
    solo(web, "finita")
    web.apri("/?vista=formazione")
    tocca(web, principale(web).get_by_role("button", name="Com'è andata"))
    assert titolo(web) == "Giornate"
    prima = web.registrata("/api/diario")["giornate"][0]
    assert riga(web, nome_di(prima)).get_attribute("aria-expanded") == "true"
    assert dettaglio(web, nome_di(prima)).get_by_role("row").count() == 12        # l'intestazione e gli 11


# ---------------------------------------------------------------- in cima: una riga sulla precisione
def test_in_cima_una_riga_sulla_precisione_con_i_dettagli_a_richiesta(web):
    solo(web, "prima")
    d = web.registrata("/api/diario")
    web.apri(GIORNATE)
    errore = virgola(d["precisione"]["fantavoto"]["errore_medio"])
    testo = web.testo_principale()
    assert f"Finora il fantavoto atteso sbaglia in media di {errore} punti a giocatore." in " ".join(testo.split())
    nascosto = principale(web).get_by_text("voti su 10 sono entro un punto")
    assert not nascosto.is_visible()                                     # le quattro statistiche non aprono più la pagina
    tocca(web, principale(web).get_by_text("Dettagli", exact=True))
    assert nascosto.is_visible()


def test_senza_voti_non_c_e_la_riga_sulla_precisione(web):
    solo(web, "prima")
    d = web.registrata("/api/diario")
    d["precisione"]["fantavoto"] = None
    web.risposta("/api/diario", d)
    web.apri(GIORNATE)
    assert "sbaglia in media" not in web.testo_principale()
    assert righe(web).count() == len(d["giornate"])


# ---------------------------------------------------------------- una riga per giornata
def test_una_riga_per_giornata_dalla_piu_recente_con_punti_fatti_e_attesi(web):
    d = web.registrata("/api/diario")
    web.apri(GIORNATE)
    assert nomi_righe(web) == [nome_di(g) for g in d["giornate"]]                # il server le dà dalla più recente
    for g in d["giornate"][:2]:
        testo = " ".join(riga(web, nome_di(g)).inner_text().split())
        assert f"{virgola(undici(g)['reale'])} punti" in testo and f"attesi {virgola(undici(g)['atteso'])}" in testo, testo
    assert righe(web).first.get_attribute("aria-expanded") == "false"           # al telefono si aprono al tocco


def test_al_tocco_gli_11_con_il_fantavoto_atteso_e_quello_preso(web):
    """«A giornata finita si vedono i voti presi dai singoli giocatori»: i numeri sono quelli del server (`giocatori`)."""
    d = web.registrata("/api/diario")
    g = d["giornate"][0]
    primo, secondo, terzo = undici(g)["titolari"][:3]
    con_voti(g, {primo["id"]: (6.1, 10.0), secondo["id"]: (5.6, 4.5), terzo["id"]: (6.3, None)})
    web.risposta("/api/diario", d)
    web.apri(GIORNATE)
    tocca(web, riga(web, nome_di(g)))
    assert riga(web, nome_di(g)).get_attribute("aria-expanded") == "true"
    zona = dettaglio(web, nome_di(g))
    assert zona.get_by_role("row").count() == 12                                # l'intestazione e gli 11
    intestazioni = [x.strip() for x in zona.get_by_role("columnheader").all_inner_texts()]
    assert intestazioni == ["Giocatore", "Atteso", "Preso"], intestazioni
    for giocatore, atteso, preso in ((primo, "6,1", "10,0"), (secondo, "5,6", "4,5"), (terzo, "6,3", "senza voto")):
        celle = [c.strip() for c in zona.get_by_role("row", name=re.compile(re.escape(giocatore["nome"]))).get_by_role("cell").all_inner_texts()]
        assert celle == [atteso, preso], (giocatore["nome"], celle)
    tocca(web, riga(web, nome_di(g)))                                           # un altro tocco la richiude
    assert riga(web, nome_di(g)).get_attribute("aria-expanded") == "false" and not zona.is_visible()
    assert not web.errori_console and not web.richieste_fallite


def test_il_fantavoto_atteso_e_quello_mostrato_prima_della_scadenza_se_c_e(web):
    """Con la consigliata di allora salvata con i suoi numeri (`istantanea`), l'atteso è quello che l'app mostrava."""
    solo(web, "prima")
    d = web.registrata("/api/diario")
    g = d["giornate"][0]
    primo = undici(g)["titolari"][0]
    con_voti(g, {primo["id"]: (6.1, 7.0)})
    g["istantanea"] = {"modulo": g["consigliata"]["modulo"], "calcolata": "2026-10-24T10:00:00", "atteso": g["consigliata"]["atteso"],
                       "titolari": [{**x, "p_voto": 0.9, "fv_atteso": 6.8 if x["id"] == primo["id"] else 6.0} for x in g["consigliata"]["titolari"]],
                       "panchina": []}
    web.risposta("/api/diario", d)
    web.apri(GIORNATE)
    tocca(web, riga(web, nome_di(g)))
    celle = dettaglio(web, nome_di(g)).get_by_role("row", name=re.compile(re.escape(primo["nome"]))).get_by_role("cell").all_inner_texts()
    assert [c.strip() for c in celle] == ["6,8", "7,0"], celle


# ---------------------------------------------------------------- tu contro la consigliata: solo con quella mostrata
PAROLE_DEL_CONFRONTO = ("rispetto alla consigliata", "cambi tuoi", "cambio tuo", "Hai schierato la consigliata", "hai messo",
                        "ha fatto meglio della tua")


def test_con_il_server_di_oggi_il_confronto_con_la_consigliata_non_si_mostra(web):
    solo(web, "prima")
    d, _ = forma_di_oggi(web)
    web.risposta("/api/diario", d)
    web.apri(GIORNATE)
    g = d["giornate"][0]
    testo = " ".join(riga(web, nome_di(g)).inner_text().split())
    assert f"{virgola(g['schierata']['reale'])} punti" in testo and "La tua formazione" in testo, testo      # i punti sono i tuoi
    tocca(web, riga(web, nome_di(g)))
    tocca(web, principale(web).get_by_text("Dettagli", exact=True))
    tutto = web.testo_principale()
    for parola in PAROLE_DEL_CONFRONTO:
        assert parola not in tutto, parola
    assert not web.errori_mostrati() and not web.errori_console


def test_con_la_consigliata_mostrata_la_riga_dice_i_cambi_e_quanto_sono_valsi(web):
    solo(web, "prima")
    d, dentro = forma_di_domani(web)
    web.risposta("/api/diario", d)
    web.apri(GIORNATE)
    g0, g1, g2 = d["giornate"][:3]
    n = len(dentro)
    cambi = "1 cambio tuo" if n == 1 else f"{n} cambi tuoi"
    assert f"{cambi}: −1,5 punti rispetto alla consigliata." in " ".join(riga(web, nome_di(g0)).inner_text().split())
    assert "Hai schierato la consigliata." in riga(web, nome_di(g1)).inner_text()
    senza = " ".join(riga(web, nome_di(g2)).inner_text().split())               # la mostrata non c'è: niente confronto
    assert not any(p in senza for p in PAROLE_DEL_CONFRONTO) and "La tua formazione" in senza, senza
    tocca(web, riga(web, nome_di(g0)))
    cosa = " ".join(dettaglio(web, nome_di(g0)).inner_text().split())
    assert "Al posto di" in cosa and "hai messo" in cosa and all(nome in cosa for nome in dentro), cosa
    tocca(web, riga(web, nome_di(g2)))
    senza = dettaglio(web, nome_di(g2)).inner_text()
    assert "hai messo" not in senza and "Qui il confronto con la consigliata non c'è" in senza, senza
    assert not web.errori_mostrati() and not web.errori_console


# ---------------------------------------------------------------- un solo pulsante di correzione
CORREGGI = "Non è quello che ho schierato"


def test_un_solo_pulsante_di_correzione_per_giornata(web):
    d = web.registrata("/api/diario")
    web.apri(GIORNATE)
    g = d["giornate"][0]
    tocca(web, riga(web, nome_di(g)))
    bottoni = [b.strip() for b in dettaglio(web, nome_di(g)).get_by_role("button").all_inner_texts()]
    assert bottoni == [CORREGGI], bottoni
    tutto = web.testo_principale()
    for vecchio in ("Ho schierato la consigliata", "Ho schierato un'altra formazione", "Correggi a mano"):
        assert vecchio not in tutto, vecchio


def test_la_correzione_fa_scegliere_gli_11_e_li_manda_con_la_stagione(web):
    solo(web, "prima")
    d = web.registrata("/api/diario")
    g = d["giornate"][0]
    mandate = []
    web.pagina.on("request", lambda r: r.method == "POST" and r.url.split("?")[0].endswith("/api/diario/schierata") and mandate.append(r.post_data))
    web.risposta("/api/diario/schierata", g)
    web.apri(GIORNATE)
    tocca(web, riga(web, nome_di(g)))
    tocca(web, dettaglio(web, nome_di(g)).get_by_role("button", name=CORREGGI))
    foglio = web.pagina.get_by_role("dialog")
    assert foglio.get_by_role("heading", name="Cosa hai schierato").is_visible()
    assert foglio.get_by_role("checkbox", checked=True).count() == 11           # si parte dagli 11 della riga
    tocca(web, foglio.get_by_role("button", name="Salva"))
    assert len(mandate) == 1, mandate
    corpo = json.loads(mandate[0])
    assert corpo["giornata"] == g["giornata"] and corpo["stagione"] == g["stagione"] and corpo["tipo"] == "manuale"
    assert sorted(corpo["titolari"]) == sorted(x["id"] for x in undici(g)["titolari"])
    assert not foglio.is_visible() and titolo(web) == "Giornate"                # torna alla pagina, con la giornata aperta
    assert riga(web, nome_di(g)).get_attribute("aria-expanded") == "true"
    assert web.richieste.count("/api/diario") >= 2                              # la pagina rilegge le giornate
    fuoco = web.pagina.evaluate("document.activeElement && (document.activeElement.innerText || '')")
    assert fuoco.startswith(nome_di(g)), fuoco                                  # chiuso il foglio, il fuoco è sulla sua riga
    assert not web.errori_mostrati()


def test_annullare_la_correzione_riporta_al_suo_pulsante(web):
    solo(web, "prima")
    d = web.registrata("/api/diario")
    web.apri(GIORNATE)
    g = d["giornate"][0]
    tocca(web, riga(web, nome_di(g)))
    tocca(web, dettaglio(web, nome_di(g)).get_by_role("button", name=CORREGGI))
    tocca(web, web.pagina.get_by_role("dialog").get_by_role("button", name="Annulla"))
    assert not web.pagina.get_by_role("dialog").is_visible()
    assert web.pagina.evaluate("document.activeElement && document.activeElement.textContent.trim()") == CORREGGI


def test_una_giornata_di_una_stagione_passata_non_si_corregge(web):
    solo(web, "prima")
    d = web.registrata("/api/diario")
    vecchia = copy.deepcopy(d["giornate"][-1])
    vecchia.update(stagione="2025-26", giornata=30, giornata_lega=None, modificabile=False)
    for g in d["giornate"]:
        g["modificabile"] = True
    d["giornate"].append(vecchia)
    web.risposta("/api/diario", d)
    web.apri(GIORNATE)
    ultima = righe(web).last
    assert "2025-26" in ultima.inner_text()                                     # con due stagioni la riga dice di quale è
    tocca(web, ultima)
    assert principale(web).get_by_role("button", name=CORREGGI).count() == 0
    tocca(web, righe(web).first)
    assert principale(web).get_by_role("button", name=CORREGGI).count() == 1


# ---------------------------------------------------------------- i patti e l'aspetto
def test_se_le_giornate_non_si_leggono_c_e_un_errore_con_riprova(web):
    solo(web, "prima")
    web.risposta("/api/diario", {"detail": "archivio occupato"}, stato=500)
    web.apri(GIORNATE)
    assert principale(web).locator('[role="alert"]').count() == 1 and web.errori_mostrati() and not web.in_caricamento()
    assert principale(web).get_by_role("button", name="Riprova").is_visible()


def test_senza_giornate_finite_la_pagina_lo_dice_senza_errori(web):
    solo(web, "prima")
    vuoto = {"giornate": [], "sintesi": {"giornate": 0}, "scelte_tue": {"giornate": 0, "pochi_dati": True, "per_giornata": []},
             "affidabilita": {"giornate": 0, "giudizio": "pochi_dati", "pochi_dati": True, "giornate_minime": 8},
             "precisione": {"giornate": 0, "pochi_dati": True, "giornate_minime": 8, "fonti": {"mostrati": 0, "ricostruiti": 0}, "fantavoto": None,
                            "gioca": None, "confronto": {"giornate": 0}, "squadra": None, "per_giornata": [], "serie_a": None},
             "motivo_vuoto": "giornate"}
    web.risposta("/api/diario", vuoto)
    web.apri(GIORNATE)
    assert titolo(web) == "Giornate"
    assert "nella tua lega non è ancora finita nessuna giornata" in web.testo_principale()
    assert not web.errori_mostrati() and not web.in_caricamento() and righe(web).count() == 0


@pytest.mark.parametrize("larghezza", [390, PC])
@pytest.mark.parametrize("tema", ["chiaro", "scuro"])
def test_giornate_senza_violazioni_gravi_e_senza_scorrere_di_lato(web, larghezza, tema):
    d, _ = forma_di_domani(web)
    web.risposta("/api/diario", d)
    web.apri(GIORNATE, larghezza=larghezza, tema=tema)
    if righe(web).first.get_attribute("aria-expanded") != "true":
        tocca(web, righe(web).first)
    tocca(web, principale(web).get_by_text("Dettagli", exact=True))
    assert not web.scorre_di_lato()
    gravi = web.violazioni_gravi()
    assert not gravi, [(v["id"], v["nodi"][:2]) for v in gravi]
    assert not web.errori_console


@pytest.mark.parametrize("larghezza", [768, PC])
def test_su_tablet_e_pc_l_elenco_sta_a_sinistra_e_gli_11_a_destra(web, larghezza):
    solo(web, "finita")
    d = web.registrata("/api/diario")
    web.apri(GIORNATE, larghezza=larghezza)
    prima, seconda = d["giornate"][:2]
    assert riga(web, nome_di(prima)).get_attribute("aria-expanded") == "true"   # con lo spazio, la più recente è già aperta
    r, z = riga(web, nome_di(prima)).bounding_box(), dettaglio(web, nome_di(prima)).bounding_box()
    assert z["x"] >= r["x"] + r["width"], (r, z)                                 # dettaglio a destra dell'elenco
    assert z["y"] < r["y"] + r["height"], (r, z)                                 # e in alto, non sotto l'elenco
    tocca(web, riga(web, nome_di(seconda)))
    assert riga(web, nome_di(prima)).get_attribute("aria-expanded") == "false"  # una alla volta
    z2 = dettaglio(web, nome_di(seconda)).bounding_box()
    assert z2["x"] == z["x"] and abs(z2["y"] - z["y"]) < 2, (z, z2)             # il dettaglio resta al suo posto


def test_al_telefono_gli_11_si_aprono_sotto_la_riga(web):
    solo(web, "finita")
    d = web.registrata("/api/diario")
    web.apri(GIORNATE)
    prima = d["giornate"][0]
    tocca(web, riga(web, nome_di(prima)))
    r, z = riga(web, nome_di(prima)).bounding_box(), dettaglio(web, nome_di(prima)).bounding_box()
    assert z["y"] >= r["y"] + r["height"] - 1 and z["x"] < r["x"] + r["width"], (r, z)
