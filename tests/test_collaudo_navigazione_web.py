"""Collaudo finale della grafica B (#354), gruppo «navigazione e focus»: #448 (focus nel foglio che cambia contenuto), #449
(Indietro del browser dentro Squadra, Altro e Impostazioni), #450 (titolo del foglio sotto la ✕). Codice vero di app.js e impostazioni.js con node e una cronologia finta che si comporta come
quella del browser (banco di prova di test_navigazione_web.py e del pannello di test_grafica_b_web.py); le prove nel browser vero
(Chrome senza finestra) sono nella descrizione della pull request."""
import json
import re
import shutil
import subprocess

import pytest
from test_grafica_b_web import AMBIENTE_PANNELLO, _codice_pannello

from fanta import server

CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
NODE = shutil.which("node")
serve_node = pytest.mark.skipif(not NODE, reason="serve node")


def _node(codice: str):
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- #449: Indietro dentro Impostazioni
# Dal 12/11/2026 (#618) Squadra e Altro non ci sono più e Impostazioni è una pagina con le sue pagine: indirizzi, Indietro e i
# pulsanti «‹ Impostazioni» si provano nel browser vero (tests/browser/test_impostazioni.py).


# ---------------------------------------------------------------- #448: focus nel foglio che cambia contenuto

@serve_node
def test_foglio_modale_che_cambia_contenuto_porta_il_focus_sul_titolo():
    """Sotto i 1200 px (e per i fogli sempre modali come il Diario) un foglio già aperto che cambia contenuto (ricerca → scheda,
    «Ho schierato la consigliata», «Correggi a mano») perdeva il focus: restava sull'elemento che non c'è più, cioè sul body. Ora va
    sul titolo del contenuto nuovo, come nel pannello affiancato; durante il caricamento (contenuto senza titolo) sulla ✕. Il primo
    foglio con il contenuto pronto resta come prima (✕), e la ricerca che tiene il cursore nel suo campo non cambia."""
    e = _node("\n".join([AMBIENTE_PANNELLO, _codice_pannello(), r"""
    const f = () => document.activeElement && document.activeElement.nome;
    const esiti = {};
    largo = false;
    const riga1 = el("riga1"), campo = el("campo", { dentro: true });
    riga1.focus(); apriFoglio("<div>carico</div>", { affianco: true }); scorri(); esiti.carico = f();
    apriFoglio("<h2>Rossi</h2>", { affianco: true }); scorri(); esiti.arriva = f();
    document.activeElement = corpoPagina;                    // il pulsante premuto nel foglio se n'è andato con il contenuto
    apriFoglio("<div>carico</div>"); scorri(); esiti.ricarico = f();
    apriFoglio("<h2>Diario delle giornate</h2>"); scorri(); esiti.diario = f();
    document.activeElement = corpoPagina; apriFoglio("<h2>Cosa hai schierato</h2>"); scorri(); esiti.correggi = f();
    campo.focus(); apriFoglio("<h2>Cerca</h2>", { affianco: true, focusResta: true }); scorri(); esiti.ricerca = f();
    chiudiFoglio(); scorri(); esiti.chiuso = f();
    riga1.focus(); apriFoglio("<h2>Bianchi</h2>", { affianco: true }); scorri(); esiti.primo = f();
    console.log(JSON.stringify(esiti));
    """]))
    assert e == {"carico": "chiudi", "arriva": "titolo:Rossi", "ricarico": "chiudi", "diario": "titolo:Diario delle giornate",
                 "correggi": "titolo:Cosa hai schierato", "ricerca": "campo", "chiuso": "riga1", "primo": "chiudi"}


def test_il_titolo_della_giornata_con_il_focus_non_finisce_sotto_la_maniglia():
    """Revisione della #462: sotto i 1100 px il foglio dal basso ha la maniglia ferma in alto (33 px: 14 + 5 + 14) e il titolo della
    giornata, portato in cima da scrollIntoView, le finiva sotto. Il foglio lascia in alto lo spazio della maniglia più 8 px
    (`scroll-padding-top`); da 1100 px la maniglia non c'è. Il titolo che prende il focus non ha il contorno, come gli altri titoli."""
    stretta = re.search(r"\n@media \(max-width: 1099\.98px\) \{(.*?)\n\}", CSS, re.S).group(1)
    m = re.search(r"\.foglio-corpo \{ scroll-padding-top: (\d+)px; \}", stretta)
    maniglia = re.search(r"\n\.maniglia \{[^}]*padding: (\d+)px 0 (\d+)px", CSS)
    barretta = re.search(r"\n\.maniglia i \{ width: \d+px; height: (\d+)px", CSS)
    assert m and maniglia and barretta
    assert int(m.group(1)) >= int(maniglia.group(1)) + int(maniglia.group(2)) + int(barretta.group(1)) + 8
    assert re.search(r'\n#foglio-contenuto h2\[tabindex="-1"\]:focus \{ outline: none; \}', CSS)


# ---------------------------------------------------------------- #450: il titolo del foglio non passa sotto la ✕

def test_il_primo_titolo_del_foglio_va_a_capo_prima_della_x():
    """A 390 px il titolo del Confronto («Chi schierare? Giornata 11 · 11ª di Serie A») arrivava a x=373 e la ✕ (44 px, 14 px dal
    bordo) parte da x=331: la «A» finale era coperta. Il primo pezzo del foglio lascia a destra il posto della ✕ (anche con il
    riempimento del foglio più piccolo, 8 px nella pagina strettissima); il pannello affiancato da 1200 px ha già la sua regola
    (la ✕ ferma è un float)."""
    m = re.search(r"\nbody:not\(\.con-pannello\) #foglio-contenuto > :first-child \{ padding-right: (\d+)px; \}", CSS)
    assert m
    x = re.search(r"\n\.foglio-chiudi \{[^}]*top: 14px; right: (\d+)px;[^}]*width: (\d+)px", CSS)
    destra, larga = int(x.group(1)), int(x.group(2))
    assert int(m.group(1)) >= destra + larga - 8 + 4                     # riempimento più piccolo del foglio: 8 px; 4 px di stacco
