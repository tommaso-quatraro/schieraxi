"""Linee guida di design della web app (docs/DESIGN.md): controlli statici su stile.css e app.js.
La prova visiva si fa a mano a 390, 768 e 1280 px, tema chiaro e scuro."""
import re

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
IMP_JS = (server.WEB / "impostazioni.js").read_text(encoding="utf-8")


def test_aree_di_tocco_da_44px_anche_in_densita_compatta():
    assert not re.search(r'data-densita="compatta"\] \.chip \{[^}]*min-height: (?:[0-3]\d|4[0-3])px', CSS)
    assert re.search(r"\.proposta-r button\.nome-g \{ padding: 13px 4px; margin: -13px -4px; \}", CSS)
    imp = (server.WEB / "impostazioni.js").read_text(encoding="utf-8")
    assert 'class="voce voce-link"' in imp                                   # privacy, termini e crediti sono voci intere da toccare
    # ✕ dei fogli, ⇄ della formazione e caselle: 44 px veri, senza aree invisibili intorno
    assert re.search(r"\.foglio-chiudi \{[^}]*width: 44px; height: 44px", CSS) and "foglio-chiudi::after" not in CSS
    assert re.search(r"\.confronta-mini \{[^}]*width: 44px; height: 44px", CSS) and "confronta-mini::after" not in CSS
    assert re.search(r'\.interruttore input\[type="checkbox"\], \.scelte input\[type="checkbox"\] \{[^}]*width: 44px; height: 44px; margin: -9px', CSS)

def test_accesso_e_primo_avvio_centrati():
    # il margine di .carta (e quello della densità compatta) spingeva la scheda d'accesso in basso: serve un selettore più forte, con auto su tutti i lati
    assert re.search(r"\.accesso > \.accesso-corpo\.carta \{[^}]*margin: auto;", CSS)
    assert ".onb-griglia" not in CSS and ".onb-blocco" in CSS

def test_schermi_grandi_ingranditi():
    # su PC e ultrawide l'interfaccia si ingrandisce a gradini; l'iPad (fino a 1366 px) non cambia
    for larghezza, z in (("1800", "1.15"), ("2400", "1.3"), ("3000", "1.5")):
        assert f"@media (min-width: {larghezza}px) {{ :root {{ --z: {z}; }}" in CSS
    assert "html { zoom: var(--z); }" in CSS
    # le misure in vh si dividono per l'ingrandimento, altrimenti i fogli e l'indice escono dallo schermo
    assert "calc(90vh / var(--z))" in CSS


def test_composizione_a_colonne_su_schermi_larghi():
    # Oggi e Formazione su 3 colonne da 1400 px, foglio come pannello laterale da 1100 px, gradino di ingrandimento per i 5120 px
    assert re.search(r"@media \(min-width: 1400px\) \{\s*main \.colonne-oggi, main \.colonne-campo \{ grid-template-columns: minmax\(0, 1fr\) minmax\(0, 2fr\)", CSS)
    assert "columns: 2" in CSS and "animation-name: sale-lato" in CSS
    assert "@media (min-width: 4400px) { :root { --z: 1.75; } }" in CSS

def test_scorciatoia_virgola_per_le_impostazioni():
    app = (server.WEB / "app.js").read_text(encoding="utf-8")
    assert 'ev.key === ","' in app and 'vai("impostazioni")' in app

def test_stile_ha_le_parentesi_graffe_in_pari():
    # una } mancante nasconde nel @media tutto quello che viene dopo
    assert CSS.count("{") == CSS.count("}")
    assert re.search(r"\n\}\n/\* ---- Lega: la mia squadra", CSS)


def test_barra_in_basso_con_fondo_quasi_opaco_e_spazio_riservato():
    assert re.search(r"\.schede\.vetro \{[^}]*color-mix\(in srgb, var\(--solido\) 90%", CSS)
    corpo = re.search(r"\nbody \{([^}]*)\}", CSS).group(1)
    assert "padding-bottom: calc(var(--barra) + env(safe-area-inset-bottom)" in corpo


def test_densita_sempre_compatta():
    """Dal 1/11/2026 la densità non si sceglie più (come sull'iPhone): sempre compatta, con le aree di tocco grandi."""
    assert 'pref("densita"' not in APP and 'radice.dataset.densita = "compatta";' in APP
    assert re.search(r'data-densita="compatta"\] \.voce \{[^}]*min-height: 48px', CSS)
    assert re.search(r'data-densita="compatta"\] \.chip \{[^}]*min-height: 44px', CSS)


def test_mercato_ha_quattro_voci_a_tutta_larghezza():
    """Da 6 a 4 schede: un controllo segmentato a tutta larghezza, senza voci tagliate."""
    assert 'class="segmenti" id="mercato-tab"' in APP
    voci = re.search(r"const TAB_MERCATO = (\[.*?\]);", APP).group(1)
    assert voci.count('["') == 4 and "Asta" not in voci
    assert re.search(r"\.segmenti button \{[^}]*flex: 1; min-width: 0; min-height: 44px", CSS)


def test_card_introduttive_compatte_con_spiegazione_chiusa():
    assert "const introCompatta = " in APP
    corpo = APP[APP.index("const introCompatta"):APP.index("async function tabConsigli")]
    assert "<details" in corpo and " open" not in corpo        # la spiegazione lunga è chiusa di default
    consigli = APP[APP.index("async function tabConsigli"):APP.index("async function datiCalendario")]
    assert "introCompatta(" in consigli and "<h2>Svincolati che migliorano" not in consigli


def test_formazione_controlli_compatti_una_riga_e_un_solo_pulsante_primario():
    blocco = APP[APP.index('<div class="etichetta-riga">${t("formazione.modulo")}</div>'):APP.index('<div class="campo">')]          # la legenda del campo viene subito dopo
    assert blocco.count('class="chips scorri" data-striscia') == 2          # moduli e stili: una riga che scorre
    assert 'id="modifica"' in blocco and 'class="bottone" id="modifica"' in blocco
    assert 'class="altre-azioni"' in blocco and 'id="copia"' in blocco and 'id="condividi"' in blocco
    assert re.search(r"\.chips\.scorri \{[^}]*flex-wrap: nowrap", CSS)


def test_la_scelta_attiva_e_lime_con_testo_scuro():
    assert re.search(r"\.chip\.attiva \{[^}]*var\(--capitano\)[^}]*var\(--capitano-testo\)", CSS)
    assert "--capitano-testo: #1a2600" in CSS


def test_proposta_di_mercato_ha_il_guadagno_in_evidenza_e_nomi_protetti():
    consigli = APP[APP.index("async function tabConsigli"):APP.index("async function datiCalendario")]
    assert 'class="pr-num"' in consigli and "esc(p.entra.nome)" in consigli and "esc(p.esce.nome)" in consigli
    assert re.search(r"\.pr-num b \{[^}]*font-size: var\(--t-titolo\)", CSS)
    assert re.search(r"\.proposta-r button\.nome-g \{[^}]*font-size: var\(--t-valore\)", CSS)


def test_scala_tipografica_a_sette_livelli_nessun_testo_sotto_12_px():
    for livello in ("eroe", "titolo", "card", "valore", "corpo", "sec", "eti"):
        assert re.search(rf"--t-{livello}: \d+px", CSS), livello
    assert not re.search(r"font-size:\s*[0-9.]+px", CSS), "font-size solo con le variabili --t-*"
    assert not re.search(r"font-size:\s*[0-9.]+px", APP), "niente font-size in pixel nello stile in linea"
    assert not re.search(r"--t-\w+: (?:[0-9]|1[01])(?:\.\d+)?px", CSS)
    assert "body { font-size: 18px" not in CSS                    # il testo non cresce sugli schermi enormi


def test_bersagli_di_tocco_44_px_e_date_di_stato_dati_come_altrove():
    assert re.search(r"\.stepper button \{ width: 44px", CSS)               # i «−/+» delle regole
    assert re.search(r"\.proposta-r button\.nome-g \{ padding: 13px 4px; margin: -13px -4px", CSS)
    assert 'class="debole piccolo piede-legale"' not in APP and 'voceLegale("privacy"' in IMP_JS   # Privacy e Termini: voci intere in Impostazioni > Informazioni, un posto solo
    assert "esc(quando(a.quando))" in APP and "esc(quando(p.rilevato))" in APP       # «ieri 18:30», non «2026-10-26 23:55»


def test_colori_semantici_come_su_ios():
    scuro, chiaro = CSS.split("@media (prefers-color-scheme: light)")[0], CSS.split(':root[data-tema="chiaro"] {')[1]
    for nome, s, c in (("verde", "#3ddc97", "#0a7d4c"), ("rosso", "#ff6b5e", "#b3261e"), ("arancio", "#ffb04a", "#9c5400"),
                       ("capitano", "#d4f34a", "#86a800"), ("azione", "#3ddc97", "#526600"),("blu", "#62a9ff", "#1a5bb5")):
        assert f"--{nome}: {s}" in scuro and f"--{nome}: {c}" in chiaro, nome
    assert "--testo-2: #b3c6ba" in scuro and "--testo-2: #587064" in chiaro


def test_nomi_piccoli_del_mercato_hanno_area_di_tocco_larga_44px():
    regola = re.search(r"\.proposta-r button\.nome-g\.piccolo \{([^}]*)\}", CSS).group(1)
    assert "min-width: 44px" in regola and "padding: 13px 10px" in regola and "margin: -13px -10px" in regola


def _lum(esa):
    c = [int(esa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrasto(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _misto(sopra, alfa, sotto):
    s, t = (tuple(int(x[i:i + 2], 16) for i in (1, 3, 5)) for x in (sopra, sotto))
    return "#%02x%02x%02x" % tuple(round(a * alfa + b * (1 - alfa)) for a, b in zip(s, t))


def test_tema_chiaro_azioni_in_oliva_con_contrasto_sufficiente_su_ogni_superficie():
    chiaro = CSS.split(':root[data-tema="chiaro"] {')[1].split("}")[0]
    assert "--azione: #526600" in chiaro and "--azione-testo: #ffffff" in chiaro
    sfondo, bianco = "#eaf3ee", "#ffffff"
    superfici = [sfondo, bianco, _misto(bianco, .72, sfondo), _misto(bianco, .55, sfondo)]
    for s in superfici:
        assert _contrasto("#526600", s) >= 4.5, s                       # testo e link di azione
        assert _contrasto("#1f8a4b", s) >= 3, s                         # il verde del campo si distingue dal fondo
    assert _contrasto("#ffffff", "#526600") >= 4.5                      # testo bianco sul pulsante pieno
    assert _contrasto("#ffffff", "#3f4f00") >= 4.5                      # fine sfumatura del pulsante
    assert _contrasto("#1a2600", "#86a800") >= 4.5                      # testo scuro sulla scelta lime
    assert _contrasto("#86a800", bianco) < 4.5                          # per questo il lime non e' mai testo
    assert _contrasto("#ffffff", "#1f8a4b") >= 3                        # nomi e numeri sul campo


def test_pulsanti_link_e_azioni_usano_la_variabile_azione_non_il_lime():
    assert re.search(r"\.bottone \{[^}]*var\(--azione\)[^}]*var\(--azione-2\)[^}]*var\(--azione-testo\)", CSS)
    assert re.search(r"\.bottone\.secondario \{[^}]*color: var\(--azione\)", CSS)
    assert re.search(r"\.schede button\.attiva \{ color: var\(--azione\)", CSS)
    assert re.search(r"\.testo-lungo a[^{]*\{ color: var\(--azione\)", CSS)
    assert '"--azione-testo"' not in APP                                # niente colori a scelta: le azioni hanno sempre i colori del marchio
