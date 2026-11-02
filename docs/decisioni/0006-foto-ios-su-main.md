# 0006. Le foto iOS si fanno su `main` dopo l'unione

Data: 2/11/2026. Stato: accettata.

## Contesto e problema
Le foto dell'app iPhone (`screenshot.yml`) occupano un Mac di GitHub per 45-90 minuti e il piano gratuito ne dà pochi insieme.
Fatte su ogni pull request, tenevano le PR in bozza ad aspettare, toglievano i Mac ai test e portavano a unire i rami fra loro
solo per fotografarli.

## Fattori della decisione
- Pochi Mac: i test iOS (`ios / test`) hanno la precedenza.
- `main` si protegge con i test, non con le foto: le foto trovano difetti d'aspetto da correggere dopo.

## Opzioni considerate
- Foto su ogni pull request iOS prima dell'unione.
- Foto su `main` dopo l'unione, a giri.

## Decisione
Scelta: prima dell'unione bastano `ios / test` verde e la revisione. Le foto si fanno su `main` dopo l'unione, una corsa ogni
60-90 minuti con le schermate chieste dalle pull request unite («Foto da fare: …»), lanciata da una sola persona. Ogni difetto
visto diventa un'issue `P1`. Eccezione: una pull request che cambia molto l'aspetto può chiedere una corsa sul suo ramo prima
di uscire dalla bozza, una alla volta in tutto il repository.

## Conseguenze
- Bene: le pull request iOS si uniscono appena i test sono verdi; un solo Mac per le foto.
- Male: un difetto d'aspetto arriva su `main` e si corregge dopo.
- Controlli: `screenshot.yml` non prende un Mac sulle PR senza etichetta né sulle bozze; mai merge dei rami delle PR per le foto.
