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
- Il nome è sempre fatto di tracciati già calcolati, mai di testo in un font: si vede uguale ovunque, senza lampi di carattere
  sbagliato. Dal 5/11/2026 (#355) il sito serve anche Archivo semi-stretto per titoli e numeri, dai suoi file (`sito/font/`, licenza
  accanto): quello è il carattere del testo, non il nome.

## Nel sito
Dal 5/11/2026 il sito mostra il nome una volta sola, compatto (`#wm-c`), nella barra in alto: niente nome grande né animazione
d'apertura. Lo sprite con `#wm` e `#wm-c` resta in ogni pagina perché `--sito` lo riscrive; la funzione che riscrive il nome
animato (`eroe`) agisce solo se una pagina ha di nuovo `class="nome-gioco"`.

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

Alla fine stampa i valori da copiare in `sito/stile.css` (la proporzione `aspect-ratio` di `.wm-svg`) se cambiano. Dopo `--sito`
alza `VERSIONE` in `sito/sw.js`.

## Licenza
Il font Archivo resta sotto SIL OFL 1.1 (`OFL.txt`): si può usare, modificare e ridistribuire, anche dentro un logo.
Il disegno del nome (X e I comprese) è un marchio di SchieraXI e non è coperto né dall'AGPL né dalla OFL: vedi `TRADEMARKS.md`.
