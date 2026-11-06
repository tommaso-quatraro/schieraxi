"""Formazione e «Da fare» (collaudo del 2/11/2026): «Modifica a mano» lasciata senza cambi, ★ non sul numero più alto,
etichette a capo a 768 px, «Controlla» dei dati vecchi che apre Stato dei dati."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
DAFARE = (WEB / "dafare.js").read_text(encoding="utf-8")
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def test_modifica_a_mano_senza_cambi_non_resta_la_tua_scelta():
    assert "if (sc.manuale && sc.manuale.uguale && !comeSalvata(sc.manuale.titolari)) sc.manuale = null;" in APP
    assert "uguale: stessiIds(ids, moduloAuto().titolari)" in APP
    assert "salvata: salva ||" not in APP                                # «salvata» non è più un segno che resta acceso dopo una sostituzione


def _node(codice: str):
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_stato_della_scelta_dal_confronto_con_il_server():
    """Progetto comune con l'app iPhone: A consigliata, B salvata, C modifiche non salvate, D modifica a mano non salvata;
    l'ordine non conta; senza lettura del server nessuna riga; la scelta non più valida lo dice."""
    funz = APP[APP.index("const stessiIds"):APP.index("// «oggi alle 21:40»")]
    undici = list(range(1, 12))
    casi = [
        (undici, None, False, False), (undici, None, True, False),
        (undici, {"titolari": list(reversed(undici))}, True, False), (undici, {"titolari": undici[:10] + [99]}, False, False),
        (undici, {"titolari": undici[:10] + [99]}, True, False), (undici, "NON_LETTA", False, False),
        (undici, {"titolari": undici}, False, True),
        (undici, {"titolari": undici[:10] + [99]}, True, True),          # scelta non valida + «Modifica a mano»: si può salvare la nuova
    ]
    righe = ",".join(f"statoScelta({json.dumps(m)}, {'undefined' if s == 'NON_LETTA' else json.dumps(s)}, {str(man).lower()}, {str(nv).lower()})"
                     for m, s, man, nv in casi)
    assert _node(funz + f"console.log(JSON.stringify([{righe}]))") == ["consigliata", "mano", "salvata", "modificata", "modificata", None, "non_valida", "modificata"]
    for chiave in ("stato_consigliata", "stato_salvata", "stato_salvata_quando", "stato_modificata_quando", "stato_mano", "stato_non_valida",
                   "salva_questa", "salva_modifiche", "annulla_modifiche"):
        assert TESTI.count(f'"formazione.{chiave}"') == 2, chiave
    assert "squadra ? null : statoScelta(" in APP                        # mai per le squadre altrui


def test_rilettura_fallita_e_cambio_giornata_non_falsano_lo_stato():
    """Revisione della PR: rete assente nella rilettura = stato ignoto (nessuna riga, si riprova); la scelta riletta dopo «Salva»
    non finisce su un'altra giornata; la legenda viene prima delle pedine nel DOM (lettori di schermo) e sta in alto con `order`."""
    corpo = APP[APP.index("const valutaManuale"):APP.index("const annullaRichieste")]
    assert "else if (silenzioso) { if (sc.chiave === chiaveSc) { sc.salvata = undefined; sc.letta = false; }" in corpo
    assert "const ancoraQui = () => n === sc.richiesta && sc.chiave === chiaveSc" in corpo
    assert corpo.index("if (!ancoraQui()) return false;                     // nel frattempo") < corpo.index("sc.salvata = riletta;")
    assert '<div class="campo">${legendaCampo()}<i class="area-alta">' in APP
    assert re.search(r"^\.legenda-campo \{ order: 1;", CSS, re.M)


def test_scelta_non_valida_non_si_cancella_da_sola():
    assert 'e.codice === "formazione_non_valida"' in APP and "sc.nonValida = true" in APP
    corpo = APP[APP.index("const valutaManuale"):APP.index("const annullaRichieste")]
    assert 'method: "DELETE"' not in corpo                                # prima la scelta si cancellava dopo un 400
    assert "La formazione salvata non è più valida: rifalla o torna alla consigliata." in TESTI


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_pedina_per_i_lettori_di_schermo():
    funz = APP[APP.index("const nomeClub"):APP.index("const SOGLIA_GIOCA")]
    base = ("const LINGUA='it'; const COLORI_SQUADRA={napoli:['#3d8fd1','#f3f4f6']}; const SIGLE={napoli:'NAP'};"
            "const esc=x=>String(x); const sigla=s=>SIGLE[s]||s; const num=x=>String(x).replace('.',',');"
            "const T={'formazione.voce_fv':'fantavoto atteso {fv}','formazione.voce_gioca':'gioca al {p} per cento','formazione.voce_gioca_v':\"gioca all'{p} per cento\","
            "'formazione.voce_casa':'in casa contro {avv}','formazione.voce_fuori':'in trasferta contro {avv}'};"
            r"const t=(k,v)=>T[k].replace(/\{(\w+)\}/g,(m,x)=>v[x]);")
    prova = ("console.log(JSON.stringify([vocePedina({nome:'Rossi',fv_atteso:6.8,p_voto:.85,avversario:'napoli',in_casa:true}),"
             "vocePedina({nome:'Bianchi',fv_atteso:6,p_voto:.45,avversario:'juventus',in_casa:false}), distintivo('napoli')]))")
    casa, fuori, dist = _node(base + funz + prova)
    assert casa == "Rossi, fantavoto atteso 6,8, gioca all'85 per cento, in casa contro il Napoli"
    assert fuori == "Bianchi, fantavoto atteso 6, gioca al 45 per cento, in trasferta contro la Juventus"
    assert 'class="dist"' in dist and "--c1:#3d8fd1" in dist and ">NAP<" in dist          # sigla nei colori sociali, niente stemmi
    pedina = APP[APP.index("function pedina("):APP.index("// Legenda del campo")]
    assert '${x.in_casa ? "vs" : "@"}' in pedina and "⚠ " in pedina and "dubbio" not in pedina      # niente pulsazione né anello del ruolo
    assert ".avatar-pedina.P" not in CSS and ".avatar-pedina.dubbio" not in CSS
    assert 'memScrivi("legenda-campo", "1")' in APP and TESTI.count('"formazione.legenda_ok"') == 2


def test_partite_del_turno_in_una_griglia_sola():
    """Le righe con i tuoi titolari non si spostano: stesso rientro per tutte, punteggio nella sua colonna a destra."""
    assert '<span class="pt">${esc(ptUff || "")}</span>' in APP and 'el.querySelector(".pt")' in APP     # vuota o col risultato ufficiale
    regola_mia = re.search(r"^\.partita\.mia \{([^}]*)\}", CSS, re.M).group(1)
    assert "padding" not in regola_mia and "box-shadow" not in regola_mia
    # la colonna di «vs» è larga quanto la parola, uguale in ogni riga (issue #265: a 320 px la sigla «MON» perdeva 2 px)
    assert "grid-template-columns: var(--col-ora) minmax(0, 1fr) auto minmax(0, 1fr) var(--col-pt)" in CSS
    assert re.search(r"^\.partita \.pt \{[^}]*text-align: right", CSS, re.M)


def test_il_nome_sta_nella_testata_non_dentro_oggi():
    """Grafica B (spec §9 e §11): Oggi parte dal suo titolo, come ogni schermata; il nome SchieraXI è quello disegnato della testata
    (letto «SchieraXI» dai lettori di schermo, come il nome della finestra). Il nome con lo slogan dentro Oggi, il suo carattere e i
    suoi testi non ci sono più."""
    assert "marchioOggi" not in APP and "--font-marchio" not in CSS and ".wordmark" not in CSS
    assert '"marchio.slogan"' not in TESTI and '"marchio.nome_voce"' not in TESTI and '"marchio.slogan_voce"' not in TESTI
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<use href="#wm-c"/>' in html[html.index("<header"):html.index("</header>")]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_stella_spiegata_solo_se_un_altro_modulo_ha_di_piu_con_stile_prudente():
    funz = APP[APP.index("function stellaNonMassimo(l)"):APP.index("const stessiIds")]
    codice = ("const esc=x=>String(x); const nomeStile=l=>l.nome; const t=(k,v)=>k+':'+JSON.stringify(v);" + funz
              + "const m=(a,b)=>[{modulo:'3-4-3',punteggio_atteso:a},{modulo:'3-5-2',punteggio_atteso:b}];"
              + "console.log(JSON.stringify([stellaNonMassimo({rischio:0,modulo:'3-4-3',nome:'Equilibrata',moduli:m(72.3,72.4)}),"
              + "stellaNonMassimo({rischio:0,modulo:'3-4-3',nome:'Equilibrata',moduli:m(72.4,72.38)}),"
              + "stellaNonMassimo({rischio:1,modulo:'3-4-3',nome:'Rischiosa',moduli:m(72.3,72.4)})]))")
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    spiegata, pari, rischiosa = json.loads(r.stdout)
    assert "formazione.stella_non_massimo" in spiegata and '"modulo":"3-5-2"' in spiegata and '"consigliato":"3-4-3"' in spiegata
    assert pari == "" and rischiosa == ""                                 # a schermo uguali, o stile rischioso: niente frase
    assert TESTI.count('"formazione.stella_non_massimo"') == 2


def test_etichette_mai_piu_larghe_della_riga_e_colonne_pari_su_ipad_verticale():
    regola = re.search(r"^\.etichetta \{([^}]*)\}", CSS, re.M).group(1)
    # dal 3/11 (issue #230) l'etichetta che non ci sta va a capo dentro la sua pillola invece di finire con i puntini
    assert "max-width: 100%" in regola and "nowrap" not in regola and "ellipsis" not in regola
    assert "@media (max-width: 1023px) { .colonne-campo { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }" in CSS


def test_controlla_dei_dati_vecchi_apre_stato_dei_dati():
    assert 'if (v.id === "dati-vecchi" && typeof apriStatoDati === "function") { vai("impostazioni", "avanzate"); apriStatoDati(); return; }' in DAFARE


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_altro_modulo_o_stile_non_e_la_consigliata():
    """Collaudo del 2/11: con il 3-4-3 o lo stile «Rischiosa» la riga diceva «Stai vedendo la consigliata»."""
    funz = APP[APP.index("const stessiIds"):APP.index("// «oggi alle 21:40»")]
    undici = list(range(1, 12))
    r = _node(funz + f"console.log(JSON.stringify([statoScelta({undici}, null, false, false, true), statoScelta({undici}, null, true, false, true),"
              f"statoScelta({undici}, {{titolari: {undici}}}, false, false, true), statoScelta({undici}, null, false)]))")
    assert r == ["altra", "mano", "salvata", "consigliata"]
    assert "const altra = !manuale && (l.rischio !== 0 || m.modulo !== l.modulo);" in APP
    assert TESTI.count('"formazione.stato_altra"') == 2 and 'altra: b("salva-questa"' in APP


def test_torna_alla_consigliata_rimette_stile_e_modulo():
    corpo = APP[APP.index('bottone("#torna-consigliata"'):APP.index('bottone("#copia"')]
    assert "sc.manuale = null; sc.livello = 0; sc.modulo = null;" in corpo


def test_le_risposte_ridisegnano_la_vista_piu_recente():
    """Copia locale e poi dati nuovi = due viste: la risposta di valuta disegnava la vecchia sopra la nuova (e con la rosa cambiata
    la pagina si fermava con un errore)."""
    corpo = APP[APP.index("const valutaManuale"):APP.index("const annullaRichieste")]
    assert "const disegna = sc.disegna, moduloAuto = sc.moduloAuto;" in corpo
    assert "if (qui) disegna(true)" not in corpo
    assert "Object.assign(sc, { disegna, moduloAuto, valuta: valutaManuale });" in APP
    assert "sc.valuta(sc.salvata.titolari, false, true)" in APP
    assert "...(sc.manuale.panchina || [])].every(id => f.schede[String(id)])" in APP


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_avviso_gioca_sul_numero_che_si_legge_e_data_lontana_col_mese():
    pedina = APP[APP.index("function pedina("):APP.index("// Legenda del campo")]
    assert "const p = Math.round((x.p_voto ?? 0) * 100) / 100;" in pedina
    assert _node("const p = Math.round(0.697 * 100) / 100; console.log(JSON.stringify(p < 0.7))") is False
    funz = APP[APP.index("function quando(s)"):APP.index("// ETag e If-Match")]
    codice = ("const parseData=s=>new Date(s.replace(' ','T')); const fOra=d=>'20:45'; const fData=d=>d.getDate()+' dic';"
              "const t=k=>({'tempo.giorno_4':'gio','tempo.oggi':'oggi','tempo.domani':'domani','tempo.ieri':'ieri'})[k]||k;" + funz
              + "const fra=g=>{const d=new Date(); d.setDate(d.getDate()+g); return d.toISOString().slice(0,10)+' 20:45'};"
              + "console.log(JSON.stringify([quando(fra(30)).split(' ').length, quando(fra(3)).split(' ').length]))")
    assert _node(codice) == [4, 3]                                          # «gio 10 dic 20:45» e «sab 7 20:45»
