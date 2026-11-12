# Test della web nel browser

Qui la web si prova in Chrome vero, senza finestra: pochi test di **comportamento** (cosa succede nella pagina), che
reggono a un rifacimento della grafica. Non cercano stringhe nel codice di `fanta/web/`.

La web si apre sul server finto di `script/ci/server_finto.py` (solo libreria standard, lo stesso della regressione
visiva): serve `fanta/web/` e risponde alle `/api/...` con le risposte registrate di `ios/fotografie/` (nomi inventati).
Niente server vero, niente rete, nessun segreto. Ogni test che usa la fixture `web` gira **tre volte**, una per fase della
giornata:

| fase | scenario | momento |
|---|---|---|
| `prima` | `vero-prima.json` | qualche ora prima della scadenza, con una formazione salvata |
| `in-corso` | `vero-in-corso.json` | giornata a metà, partite in corso |
| `finita` | `vero-finita.json` | giornata finita, voti usciti |

L'orologio della pagina è fermo sul momento dello scenario (`adesso`), in italiano e con l'ora italiana; ogni test parte
da una scheda nuova (nessun dato salvato da un test prima).

## Tre patti con ogni versione della web
I test non conoscono le schermate: si appoggiano a tre regole che ogni versione della web rispetta.
- **Il contenuto della schermata sta nell'area principale**: `<main>` (o un elemento con `role="main"`). Una schermata
  con l'area principale vuota è rotta, anche se la testata c'è.
- **Mentre una schermata carica, l'area principale (o il suo contenitore del caricamento) ha `aria-busy="true"`**, e lo
  toglie quando ha finito. I test aspettano al massimo 10 secondi che nell'area principale non ci sia più nessun
  `aria-busy="true"`, poi falliscono («ferma sul caricamento»). La web di oggi non ha ancora l'attributo: si riconosce il
  suo caricamento dalle classi `caricamento` e `scheletro` (la rotella e le righe grigie di `caricamento()` in `app.js`).
- **Un errore mostrato all'utente ha `role="alert"`** (lo legge subito anche chi usa un lettore di schermo); un avviso
  normale ha `role="status"`. Un elemento `role="alert"` con del testo, visibile nell'area principale, fa fallire i test
  della prima schermata. La web di oggi scrive gli errori anche con la classe `errore`, che vale lo stesso. Un contenitore
  `role="alert"` vuoto, pronto per un messaggio, va bene.

Cosa nota della web di oggi: la schermata di accesso e il riconoscimento delle rose mettono dentro `role="alert"` anche
avvisi che non sono errori (classe `attenzione`). Il controllo non li conta come errori; nella web rifatta quegli avvisi
passano a `role="status"`.

## Quando girano
- **Nelle pull request**: job `browser` dei controlli (`.github/workflows/test.yml`), quando la PR tocca `fanta/web/`,
  `fanta/testi/`, `tests/browser/`, `tests/strumenti/axe/`, `ios/fotografie/`, `script/ci/server_finto.py`,
  `.github/browser-requisiti.txt` o `test.yml` (anche spostando un file da lì). Per ora è solo un avviso (fuori dai
  `needs` di `unisci`).
- **A mano su un ramo**: `gh workflow run test.yml --ref <ramo>` (girano tutti i controlli, questo compreso).
- **Nella suite normale no**: senza `-m browser` si saltano. Si saltano anche se mancano Playwright o Chrome; nel job dei
  controlli (variabile `BROWSER_OBBLIGATORIO=1`) invece falliscono, perché lì un test saltato sarebbe un verde finto.

## In locale
Playwright e pytest stanno in un ambiente a parte, **mai** nel `.venv` del progetto né nel Python di sistema. Nessun
browser da scaricare: si usa Chrome già installato. Una volta sola (Windows):

```
py -3.13 -m venv <cartella-temporanea>\pw-test
<cartella-temporanea>\pw-test\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r .github\browser-requisiti.txt
```

Poi, dalla radice del repository (anche da una worktree), circa un minuto:

```
<cartella-temporanea>\pw-test\Scripts\python.exe -m pytest -q -m browser --confcutdir tests/browser tests/browser
```

`--confcutdir tests/browser` serve: senza, pytest carica anche `tests/conftest.py`, che vuole le librerie dell'app
(errore `No module named 'requests'`). Su macOS e Linux il Python è `<cartella>/pw-test/bin/python`.

## Cosa controllano oggi
`test_prima_schermata.py`, in ognuna delle tre fasi, a 390 e 1440 px, tema chiaro e scuro:
- la prima schermata ha del testo nell'area principale, non è ferma sul caricamento (`aria-busy`), non mostra errori
  (`role="alert"`) e non scrive errori nella console (né errori del codice);
- nessuna richiesta fallita (risposta 4xx o 5xx, o richiesta che non arriva; una richiesta annullata non conta);
- a 390 px la pagina non è più larga dello schermo (niente scorrimento di lato);
- nessuna violazione grave (`critical` o `serious`) di axe, regole WCAG 2.0, 2.1 e 2.2 livelli A e AA
  (`tests/strumenti/axe/`).

## Aggiungere un test di comportamento (dieci righe)
Un file `tests/browser/test_<cosa>.py`. Il segno `browser` lo mette da solo `conftest.py` a ogni test di questa cartella:
non serve scriverlo.

```python
import pytest


@pytest.mark.parametrize("vista", ["formazione", "squadra"])
def test_la_vista_si_apre_pulita(web, vista):
    web.apri(f"/?vista={vista}")                     # larghezza=390, tema="chiaro" di norma
    assert web.testo_principale(), f"{web.fase}: area principale vuota"
    assert not web.errori_mostrati(), web.errori_mostrati()
    assert not web.errori_console, web.errori_console
    assert not web.richieste_fallite, web.richieste_fallite
```

Cosa offre la fixture `web`:
- `web.apri(percorso, larghezza=390, tema="chiaro")`: apre un indirizzo e aspetta che la pagina sia pronta (area
  principale con del testo e senza caricamento, al massimo 10 s; poi rete ferma, al massimo 2 s; poi DOM fermo per
  300 ms, al massimo 3 s; animazioni portate alla fine). Un'attesa scaduta non ferma il test: lo dicono i controlli dopo;
- `web.pagina`: la pagina di Playwright, per cliccare e leggere (`web.pagina.get_by_role("button", name="…").click()`);
  dopo un clic, `web.aspetta()`;
- `web.errori_console`, `web.richieste_fallite`: liste che si riempiono da sole;
- `web.testo_principale()`, `web.in_caricamento()`, `web.errori_mostrati()`, `web.scorre_di_lato()`,
  `web.violazioni_gravi()`;
- `web.fase`: `prima`, `in-corso` o `finita` (per un test che vale per una fase sola:
  `if web.fase != "prima": pytest.skip("solo prima della scadenza")`).

Regole:
- si prova un comportamento che l'utente vede, non il testo di `app.js`; gli elementi si cercano per ruolo ed etichetta
  (`get_by_role`, `get_by_label`), che sono anche ciò che legge chi usa un lettore di schermo;
- il server finto non salva niente: ogni metodo (anche un salvataggio) riceve la risposta registrata per quell'indirizzo;
- niente orologio vero e niente attese a tempo fisso: `web.aspetta()`.

## Una rotta che manca nello scenario
Il server finto risponde 404 a una rotta che non ha registrata, e il test delle richieste fallite lo dice
(`GET /api/<rotta>: risposta 404`). Se la web chiama una rotta nuova, gli scenari si registrano di nuovo con
`prove/fotografie_dal_vero.py` (serve l'archivio dei dati: lo fa chi coordina). Se invece la registrazione la toglie
apposta (come `/api/avatar`, che viene dalle foto vere dei calciatori), la sua risposta «senza dati» del server vero va in
`RISPOSTE_IN_PIU` di `conftest.py`.

## Renderli bloccanti
Quando la web nuova è unita, in `test.yml`: `browser` nei `needs` del job `unisci` e `needs.browser.result == 'success'`
nella sua condizione. Nelle PR il job non si salta mai (se la PR non tocca la web salta solo i passi e resta verde), quindi
non serve altro.
