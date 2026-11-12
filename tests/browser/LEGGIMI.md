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
  `aria-busy="true"`, poi falliscono («ferma sul caricamento»). La web lo mette dal 12/11/2026 (#615): sull'area principale
  con `caricamento()` di `app.js` (lo toglie la `pagina()` che arriva dopo, anche quella di un errore) e sui riquadri che si
  riempiono dopo. Il controllo guarda ancora anche le classi `caricamento` e `scheletro` (la rotella e le righe grigie).
- **Un errore mostrato all'utente ha `role="alert"`** (lo legge subito anche chi usa un lettore di schermo); un avviso
  normale ha `role="status"`. Un elemento `role="alert"` con del testo, visibile nell'area principale, fa fallire i test
  della prima schermata. La web di oggi scrive gli errori anche con la classe `errore`, che vale lo stesso. Un contenitore
  `role="alert"` vuoto, pronto per un messaggio, va bene.

Cosa nota della web di oggi: la schermata di accesso mette dentro `role="alert"` anche avvisi che non sono errori (classe
`attenzione`). Il controllo non li conta come errori; nella web rifatta quegli avvisi passano a `role="status"`. Il
riconoscimento delle rose lo fa già (#615): il riquadro dei suoi messaggi è una regione `role="status"` che resta in
pagina, e l'avviso ci viene scritto dopo (un lettore di schermo non legge una regione che nasce già con il suo testo).

## Quando girano
- **Nelle pull request**: job `browser` dei controlli (`.github/workflows/test.yml`), quando la PR tocca `fanta/web/`,
  `fanta/testi/`, `tests/browser/`, `tests/strumenti/axe/`, `ios/fotografie/`, `script/ci/server_finto.py`,
  `.github/browser-requisiti.txt` o `test.yml` (anche spostando un file da lì). Blocca l'unione: `unisci` lo aspetta e
  lo vuole riuscito (se la PR non tocca la web il job salta i passi e resta verde).
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

`test_tagli.py`, la web senza le funzioni tolte il 12/11/2026 (#615). I test che non dipendono dalla fase girano solo
prima della scadenza:
- i menu di Squadra e Altro hanno solo le voci che restano; gli indirizzi delle pagine tolte aprono la schermata più
  vicina; le novità stanno in Impostazioni > Informazioni (le ultime dieci, le altre a richiesta); «Nuova stagione» è un
  avviso che compare quando serve; la dimensione del testo salvata da una versione di prima non vale più;
- Formazione senza stili, legenda, confronto e indice sui volti, e senza partite del turno e banner, nelle tre fasi;
  girando per l'app non si chiedono le rotte delle funzioni tolte;
- le decisioni in cima alla Formazione: via i consigli di mercato e di scambio; la riga del reparto scoperto resta e
  porta alla rosa;
- i patti: una schermata che non si apre mostra un errore `role="alert"` e non resta in caricamento; le schermate sane
  non ne hanno; mentre una schermata carica `<main>` ha `aria-busy="true"`; nel riconoscimento delle rose gli avvisi
  arrivano in una regione `role="status"` già in pagina e un salvataggio fallito è un errore.

`test_formazione_unica.py`, la schermata «Formazione» che ha preso il posto di Oggi e Formazione (#616):
- nelle tre fasi, a 390×844 px, i nomi degli 11 stanno nel primo schermo; il vecchio indirizzo di Oggi apre la Formazione;
- «gioca N%» si vede solo sotto l'80% e non ci sono etichette di titolarità; un tocco su un titolare apre la scheda con
  «Sostituisci»; fra i sostituti chi gioca meno dell'80% lo dice; la nota che spiega «In dubbio» si legge nella riga e
  nella scheda; un account senza rose vede il benvenuto senza richieste fallite;
- salvataggio automatico: dopo una sostituzione o un altro modulo lo stato dice «L'hai cambiata tu» e la scelta è
  salvata; «Torna alla consigliata» la toglie; la spunta «L'ho messa» resta dopo una ricarica;
- ciò che si salva è ciò che si vede: la copia mostrata subito all'apertura è di sola lettura finché non arrivano i dati
  nuovi; un salvataggio che torna a schermata già ridisegnata fa rileggere; togliere la spunta non cancella una scelta
  salvata altrove; se la scelta non si legge c'è un errore con «Riprova» e niente si può cambiare; rete caduta, rifiuto
  del server e scelta cambiata su un altro dispositivo lasciano in pagina ciò che è salvato e lo dicono;
- tastiera: dopo il menu del modulo, la spunta, «Sostituisci» e «Torna alla consigliata» il fuoco resta su un comando;
- al massimo due decisioni, solo quelle con un'azione: prima le urgenti (fra loro prima quelle con un'azione vera), poi
  le altre; il reparto scoperto non ne prende più di una; «Usa la consigliata» prende quella nuova;
- quando il cambio non si può fare: chi gioca una partita già cominciata non ha «Sostituisci» e la scheda dice perché;
  un ritorno alla consigliata rifiutato lascia la formazione com'è e lo dice un avviso (`role="status"`); se la scadenza
  passa con la pagina aperta la schermata si rilegge;
- a giornata in corso i punti finora e niente da cambiare; a giornata finita «Com'è andata», i recuperi che mancano e la
  scelta sul rinvio, con sotto la formazione della prossima;
- tablet e PC: campo a sinistra e panchina a destra a 768, 1024 e 1440 px; sul PC la scheda nel pannello a fianco, che
  si chiude se cambia il modulo; scheda ed elenco dei sostituti senza violazioni gravi di axe, chiaro e scuro.

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
- `web.errori_console`, `web.richieste_fallite`, `web.richieste` (le `/api/...` chieste, percorso e query): liste che si
  riempiono da sole;
- `web.risposta(rotta, corpo, stato=200)`, prima di `apri` o di un clic: quella rotta risponde con `corpo` (JSON) e
  `stato` al posto della risposta registrata, per un dato che lo scenario non ha o per una rotta che fallisce.
  `web.registrata(rotta)` dà la risposta registrata come oggetto, per cambiarne un pezzo;
- `web.memoria({"chiave": "valore"})`, prima di `apri`: valori già salvati nel browser da una versione di prima;
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

## Sono bloccanti
In `test.yml` `browser` sta nei `needs` del job `unisci`, con `needs.browser.result == 'success'` nella sua condizione.
Nelle PR il job non si salta mai (se la PR non tocca la web salta solo i passi e resta verde). Su `main` non gira: se due
pull request verdi da sole rompono insieme una schermata, lo vede la pull request successiva che tocca la web.
