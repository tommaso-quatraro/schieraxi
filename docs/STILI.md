# Stili della formazione (preset)

Uno stile è un preset completo: sceglie insieme (a) il profilo di rischio dei giocatori (`peso`: quanto contano la brutta giornata e la giornata eccezionale rispetto ai punti attesi), (b) la preferenza di MODULO (`inclinazione` = punti in più per ogni difensore / ogni attaccante oltre il 4-x-3; sposta solo la scelta del modulo, non quella dei giocatori), (c) un testo di una riga. La panchina resta quella di sempre (ordine per valore o per ruolo secondo le regole della lega): misurare un criterio diverso non ha dato motivi per cambiarla.

Definizione: `LIVELLI_RISCHIO` in `fanta/formazione.py` (`id, nome, peso, inclinazione, descrizione`).

| id | Stile | peso (giù, su) | inclinazione (D, A) |
|---|---|---|---|
| -2 | Molto sicura | 1,5 / 0 | 0,5 / 0 |
| -1 | Sicura | 0,6 / 0 | 0,5 / 0 |
| 0 | Equilibrata | 0,15 / 0 | 0 / 0 (identica a prima: stessi numeri, 4-4-2 71,2 sulla rosa di prova) |
| 1 | Rischiosa | 0 / 0,25 | 0 / 0,5 |
| 2 | Molto rischiosa | 0 / 0,5 | 0 / 0,5 |

**Nota (31/10/2026).** «Equilibrata» NON è lo stile che massimizza i punti attesi: ogni stile sceglie con il proprio punteggio (punti attesi meno una penale per la brutta giornata, o più un premio per quella eccezionale) e con la propria inclinazione del modulo. Per questo «Rischiosa» può mostrare qualche decimo di punto atteso in più (nel backtest 69,61 contro 69,29, dentro il rumore di misura). È voluto, non un difetto: il numero mostrato è sempre la media della formazione scelta da quello stile.

## Misura (backtest, 30/10/2026)
Rose della lega (10 squadre) sulle giornate già giocate dall'archivio (76 casi squadra-giornata con rosa sufficiente), 100 simulazioni, punti veri a giornata con le regole della lega. Differenza dalla Equilibrata (69,29 punti), errore standard in parentesi; con un campione così piccolo sotto circa ±0,3 è rumore.

| Prova | punti | differenza |
|---|---|---|
| Equilibrata | 69,29 | 0 |
| Sicura (solo peso) | 69,38 | +0,09 (0,09) |
| Sicura + D 0,5 | 69,47 | +0,18 (0,16) |
| Sicura + D 1,0 | 69,53 | +0,24 (0,22) |
| Molto sicura (solo peso) | 68,33 | -0,96 (0,44) |
| Molto sicura + D 0,5 | 68,25 | -1,04 (0,46) |
| Rischiosa (solo peso) | 69,61 | +0,32 (0,31) |
| Rischiosa + A 0,5 | 69,38 | +0,09 (0,33) |
| Molto rischiosa (solo peso) | 69,55 | +0,26 (0,32) |
| Molto rischiosa + A 0,5 | 69,24 | -0,05 (0,36) |

Letture oneste: (1) spostare il modulo non costa punti oltre il rumore; (2) il vantaggio dei preset è nel profilo, non nei punti medi: i punti non salgono in modo dimostrabile, cambia solo il carattere della scelta; (3) «Molto sicura» costa circa 1 punto a giornata (già così prima, il modulo non cambia il conto); (4) con la qualità attuale dei dati il 4-3-3 resta il modulo più scelto da tutti gli stili, perché l'inclinazione verso gli attaccanti agisce poco: l'effetto visibile è soprattutto nelle difese folte (5-3-2 in 16 casi su 76 per Sicura). Da rimisurare quando ci saranno più giornate nell'archivio. Script di prova: stesso schema di `verifica` (nessun file del progetto toccato).

## API
`GET /api/formazione` (e per squadra): ogni voce di `livelli` ora ha `stile` (uguale a `rischio`, id numerico -2..2), `nome`, `descrizione` (una riga in italiano), `modulo` (consigliato dallo stile), `punteggio_atteso`, `dev`, `dev_simulata`, `intervallo`, `moduli[]` (per modulo: `modulo, punteggio_atteso, dev, dev_simulata, intervallo, titolari[], panchina[]`). `intervallo` = `{basso, alto, confidenza: 0.8, indicativo}` e `dev` sono calibrati sui punti veri (vedi `docs/INCERTEZZA.md`); `dev_simulata` è la vecchia deviazione della simulazione, utile solo per confrontare due formazioni. `stile_consigliato` = 0. Campi vecchi invariati (compatibile con i client esistenti). Il modulo scelto a mano resta fisso lato client finché si tocca uno stile; `GET /api/confronto?livello=<id>&modulo=<m>` invariato.
