# Test della web nel browser

Qui la web si prova in Chrome vero, senza finestra: pochi test di **comportamento** (cosa succede nella pagina), che
reggono a un rifacimento della grafica. Non cercano stringhe nel codice di `fanta/web/`.

La web si apre su un server finto (`ServerFinto` di `script/ci/aspetto_web.py`, solo libreria standard): serve `fanta/web/`
e risponde alle `/api/...` con le risposte registrate di `ios/fotografie/` (nomi inventati). Niente server vero, niente
rete, nessun segreto. Ogni test che usa la fixture `web` gira **tre volte**, una per fase della giornata:

| fase | scenario | momento |
|---|---|---|
| `prima` | `vero-prima.json` | qualche ora prima della scadenza, con una formazione salvata |
| `in-corso` | `vero-in-corso.json` | giornata a metà, partite in corso |
| `finita` | `vero-finita.json` | giornata finita, voti usciti |

L'orologio della pagina è fermo sul momento dello scenario (`adesso`), in italiano e con l'ora italiana; ogni test parte
da una scheda nuova (nessun dato salvato da un test prima).

## Quando girano
- **Nelle pull request**: job `browser` dei controlli (`.github/workflows/test.yml`), quando la PR tocca `fanta/web/`,
  `fanta/testi/`, `tests/browser/`, `tests/strumenti/axe/`, `ios/fotografie/`, `.github/browser-requisiti.txt` o
  `test.yml`. Per ora è solo un avviso (fuori dai `needs` di `unisci`).
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
- la prima schermata si apre, non è vuota e non scrive errori nella console (né errori del codice);
- nessuna richiesta fallita (risposta 4xx o 5xx, o richiesta che non arriva);
- a 390 px la pagina non è più larga dello schermo (niente scorrimento di lato);
- nessuna violazione grave (`critical` o `serious`) di axe, regole WCAG 2.0, 2.1 e 2.2 livelli A e AA
  (`tests/strumenti/axe/`).

## Aggiungere un test di comportamento (dieci righe)
Un file `tests/browser/test_<cosa>.py`:

```python
import pytest

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("vista", ["formazione", "squadra"])
def test_la_vista_si_apre_pulita(web, vista):
    web.apri(f"/?vista={vista}")                     # larghezza=390, tema="chiaro" di norma
    assert web.testo_visibile(), f"{web.fase}: pagina vuota"
    assert not web.errori_console, web.errori_console
    assert not web.richieste_fallite, web.richieste_fallite
```

Cosa offre la fixture `web`:
- `web.apri(percorso, larghezza=390, tema="chiaro")`: apre un indirizzo e aspetta che la pagina sia ferma (rete ferma,
  poi DOM fermo per 300 ms, animazioni portate alla fine);
- `web.pagina`: la pagina di Playwright, per cliccare e leggere (`web.pagina.get_by_role("button", name="…").click()`);
  dopo un clic, `web.aspetta()`;
- `web.errori_console`, `web.richieste_fallite`: liste che si riempiono da sole;
- `web.testo_visibile()`, `web.scorre_di_lato()`, `web.violazioni_gravi()`;
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
