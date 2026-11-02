# Incertezza dei punti attesi: la fascia «tra X e Y»

Misura del 30/10/2026 (`python -m fanta verifica --incertezza`, codice in `fanta/incertezza.py`).

## Il problema
Accanto ai punti attesi l'app scriveva «oscilla di ±N» (N = deviazione della simulazione, di solito 1-5 punti). La simulazione
rende casuali solo chi prende voto e il voto per il modificatore difesa: gol, assist e voti di chi gioca restano fissi al valore
atteso. Per confrontare due formazioni va bene, per dire quanto ci si può fidare no: nel backtest la fascia «atteso ± 1,28 × dev»
conteneva i punti veri solo 24 volte su 100 invece di 80.

## Come si misura
Backtest su 41 giornate (2025-26 dalla 5ª, 2026-27 dalla 2ª), solo con i dati di prima di ogni giornata e senza probabili
formazioni (come in `verifica`): per ogni rosa, la formazione che il modello consiglia, i suoi punti attesi e i punti fatti con le
sostituzioni vere. Casi: 93 sulle rose della lega (quelle di oggi, quindi poche nella stagione scorsa) e 820 su rose estratte a sorte
(20 per giornata, 3 P, 8 D, 8 C, 6 A tra chi ha almeno il 30% di prendere voto, seme fisso): servono a avere abbastanza casi.

Scarto vero (punti fatti − attesi):

| Casi | n | media | deviazione | 10° perc. | 90° perc. | dev simulata media |
|---|---|---|---|---|---|---|
| tutti | 913 | −0,3 | 6,7 | −7,9 | +8,3 | 1,6 |
| rose della lega 2025-26 | 26 | −0,4 | 7,8 | −9,5 | +6,2 | 3,9 |
| rose della lega 2026-27 | 67 | +0,2 | 8,1 | −8,4 | +9,0 | 1,9 |
| sintetiche 2025-26 | 680 | −0,5 | 6,5 | −8,0 | +8,2 | 1,5 |
| sintetiche 2026-27 | 140 | +0,6 | 7,0 | −7,3 | +9,1 | 1,8 |

Il diario (8 giornate della mia squadra) dà uno scarto di 5,9: stesso ordine di grandezza.

## La fascia calibrata
    scarto tipico = radice(6,47² + dev simulata²)
    fascia 80%    = da atteso − 1,18 × scarto tipico  a  atteso + 1,25 × scarto tipico

Con una dev simulata di 2 la fascia va da circa −8 a +8,5 punti attorno all'atteso (larga circa 16,5).
Provata anche una parte che cresce con i bonus attesi dei titolari (varianza di gol, assist, rigori come eventi rari): non dice
quali giornate andranno peggio (correlazione con lo scarto circa 0, e così anche la dev simulata), quindi è stata tolta.
La fascia quindi è quasi la stessa per ogni formazione, modulo e stile: onestamente il modello oggi non sa dire quale formazione
è più «sicura» di un'altra oltre a questo.

## Copertura (quota dei punti veri dentro la fascia 10-90%, obiettivo 80%)

| Casi | prima (± 1,28 × dev) | dopo | larghezza media prima → dopo |
|---|---|---|---|
| tutti (913) | 24% | 80% | 4,1 → 16,3 |
| rose della lega (93) | 33% | 76% | 6,3 → 17,1 |
| fuori campione: tarata sul 2025-26, provata sul 2026-27 (207) | — | 78% | 16,4 |
| fuori campione: tarata sul 2026-27, provata sul 2025-26 (706) | — | 80% | 16,2 |
| fuori campione: tarata sulle sintetiche, provata sulle rose della lega (93) | — | 74% | 17,0 |
| diario della mia squadra (8 giornate) | — | 6 su 8 | — |

Con 93 casi l'errore di misura della copertura è circa ±8 punti percentuali, e le rose della stessa giornata non sono indipendenti:
la fascia è segnata `indicativo: true` finché i casi sulle rose della lega sono meno di 200 (`MIN_CASI_LEGA`). Sulle rose della
lega lo scarto è un po' più grande (circa 8 contro 6,5): se con più giornate resta così, la fascia andrà allargata.

## Contratto per le app (web, iOS, Android)
- `GET /api/formazione`: in cima, in ogni `livelli[]` e in ogni `moduli[]`: `intervallo: {basso, alto, confidenza: 0.8, indicativo}`,
  `dev` (ora coerente con la fascia: (alto − basso) / 2,56) e `dev_simulata` (la deviazione di prima, solo per confronti).
- `POST /api/formazione/valuta`: gli stessi campi; `brutta_giornata` e `giornata_eccezionale` sono ora `intervallo.basso` e `.alto`.
- `GET /api/oggi`: `formazione.intervallo` e `formazione.dev`.
- `GET /api/widget`: `formazione.intervallo` e `diario[].intervallo`.
- `GET /api/diario`: `consigliata`, `schierata`, `automatica` hanno `intervallo` (e `dev_simulata` per le voci nuove; per quelle
  vecchie la fascia si calcola con dev simulata 0).
- Testo da mostrare: «tra X e Y» con «8 volte su 10» (più «indicativo» se `indicativo` è vero). Se `intervallo` manca
  (server vecchio) mostrare «oscilla di ±dev».

Nessuna scelta cambia: `verifica` e le formazioni di tutte le squadre (tutti gli stili e moduli) sono identiche prima e dopo.
Rifare la misura ogni tanto (più giornate = numeri più solidi) e copiare le costanti stampate in `incertezza.CALIBRAZIONE`.
