# Il nome disegnato «SchieraXI» (wordmark)

Il nome che compare nel sito e nell'app. Si scrive sempre «SchieraXI»: «Schiera» nel colore del testo, «XI» nel colore d'accento.
L'etichetta per chi usa lettori dello schermo è «Schiera undici» (sul sito «SchieraXI, schiera undici»).

## Com'è fatto
- **«Schiera»**: lettere del font **Archivo** ExtraBold (peso 800) condensato (larghezza 72), con la crenatura del font e la
  spaziatura appena stretta (-0,005 em). Font di Omnibus-Type, licenza SIL Open Font License 1.1 (`OFL.txt`).
- **X**: due barre dritte che si incrociano, alte come le maiuscole, spesse il 90% dell'asta di Archivo, con i tagli orizzontali.
- **I**: un palo con il «punto» in cima, l'idea del giocatore schierato.
  - Versione **grande** (`#wm` nel sito, sopra i ~40 px di altezza): un taglio obliquo sottile (circa 30 gradi) stacca il pezzo in cima.
  - Versione **compatta** (`#wm-c`: barra in alto, piè di pagina, app): la I è piena. Sotto i ~40 px il taglio la farebbe leggere «i».
- Colori dell'accento: `#378000` sul chiaro, `#D4F34A` sullo scuro (variabile `--xi` del sito).
- Sito e app **non caricano nessun font**: usano solo i tracciati già calcolati. Così la Content-Security-Policy del sito resta stretta
  e non ci sono lampi di carattere sbagliato.

## Animazione d'apertura del sito
«Schierali» diventa «SchieraXI»: la l esce ruotando, la i scivola a destra e il suo punto scende sul palo (diventa la cima della I),
poi la X si disegna con due barre che si incrociano. Una volta sola, all'apertura. Con «Riduci movimento» si vede subito il nome finito.
Classi `wm-*` in `sito/stile.css`.

## File
| File | Cosa |
|---|---|
| `genera.py` | ricalcola tutto dal font (vedi sotto) |
| `Archivo-sottoinsieme.ttf` | solo le lettere che servono di Archivo (variabile, assi peso e larghezza) |
| `OFL.txt` | licenza del font |
| `wordmark-chiaro.svg`, `wordmark-scuro.svg` | il nome grande per fondi chiari e scuri (documenti, stampa, social) |

## Rigenerare
In un ambiente Python a parte (non serve all'app):
```
python -m venv .venv-marchio
.venv-marchio\Scripts\python.exe -m pip install fonttools uharfbuzz
.venv-marchio\Scripts\python.exe assets\marchio\wordmark\genera.py --sito --og
```
- senza opzioni rifà solo i due SVG qui;
- `--sito` riscrive il nome in `sito/index.html`, `sito/en/index.html`, `sito/404.html`, `sito/offline.html`;
- `--og` rifà `sito/img/og.png` (serve Chrome o Edge);
- `--swift PERCORSO` scrive la View SwiftUI `WordmarkSchieraXI` (forme disegnate, niente font nell'app).

Alla fine stampa i valori da copiare in `sito/stile.css` (proporzione e partenza dell'animazione) se cambiano. Dopo `--sito`
alza `VERSIONE` in `sito/sw.js`.

## Licenza
Il font Archivo resta sotto SIL OFL 1.1 (`OFL.txt`): si può usare, modificare e ridistribuire, anche dentro un logo.
Il disegno del nome (X e I comprese) è un marchio di SchieraXI e non è coperto né dall'AGPL né dalla OFL: vedi `TRADEMARKS.md`.
