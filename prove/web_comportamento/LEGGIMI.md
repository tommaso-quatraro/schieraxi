# Test di comportamento della web nel browser

Provano la web app come la vede chi la usa: cosa compare in una schermata e cosa succede a un tocco. Non cercano testo nel
sorgente, quindi restano validi quando il codice si riordina.

- Chrome già installato sul computer, senza finestra, con un profilo temporaneo (nessun cookie di chi lancia).
- La web è quella di questa cartella di lavoro (`fanta/web/`), servita da un server finto (`ServerFinto` di
  `script/ci/aspetto_web.py`, solo libreria standard) che risponde alle `/api/...` con le risposte registrate di
  `ios/fotografie/vero-*.json`: nomi inventati, tre fasi della giornata (`prima`, `in-corso`, `finita`), orologio fermo sul momento
  della registrazione. Niente rete, niente server vero, niente dati veri.
- Alla fine di ogni test: nessun errore del JavaScript nelle pagine aperte.

## Una volta sola: l'ambiente con Playwright

Playwright non sta nei requisiti del progetto: si mette in un ambiente a parte, fuori dal repository (lo stesso delle foto,
`prove/foto_web/LEGGIMI.md`), con in più pytest:

```
py -3.13 -m venv <cartella-temporanea>\pw-web
<cartella-temporanea>\pw-web\Scripts\python.exe -m pip install playwright==1.64.1 pytest
```

## Il comando

Dalla radice del repository (anche da una worktree):

```
<cartella-temporanea>\pw-web\Scripts\python.exe -m pytest -q prove\web_comportamento
```

Con il Python del progetto (senza Playwright) questi test si saltano da soli: la suite normale non cambia.

Per vedere fallire un test sulla web di prima di una modifica, si indica un'altra cartella della web:
`SCHIERAXI_WEB_DI_PROVA=<cartella con index.html e app.js>`.

## Come si scrive un test

```python
def test_squadra_ha_due_voci(apri):
    s = apri("/?vista=squadra")                       # telefono (390×844), prima della scadenza
    assert [v.strip() for v in s.pagina.locator(".lega-menu .nome").all_inner_texts()] == ["Squadre e rose", "Aggiorna le rose"]
```

`apri(indirizzo, fase="prima", misura=TELEFONO, risposte={...}, memoria={...})` (in `conftest.py`) dà una `Schermata`
(`web_di_prova.py`): `s.pagina` è la pagina di Playwright, `s.vai(indirizzo)`, `s.tocca(selettore)`, `s.titolo()`, `s.testo()`,
`s.chieste("/api/...")` (le rotte chieste dalla pagina).

- `risposte`: una risposta diversa da quella registrata, o una in più (`{"/api/novita": [...]}`); con `...` la rotta non risponde
  (`{"/api/oggi": ...}`), per provare una schermata che non si apre.
- `memoria`: valori messi in `localStorage` prima che la pagina parta (una preferenza salvata da una versione di prima).

Un errore mostrato nell'area principale ha `role="alert"`; avvisi, stati vuoti e promemoria no. Così una schermata che si rompe si
riconosce anche se la web cattura i suoi errori e non scrive in console (`test_tagli.py`, in fondo).

Quando i test del browser entreranno nei controlli delle pull request (`tests/browser/`, #619), questi si spostano lì.
