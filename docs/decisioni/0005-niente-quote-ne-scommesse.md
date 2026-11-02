# 0005. Niente quote né scommesse nel modello

Data: 31/10/2026. Stato: accettata.

## Contesto e problema
Il modello usava anche le quote dei bookmaker. Un'app di consigli per il fantacalcio non deve legarsi al gioco d'azzardo,
né dipendere da fonti di scommesse e dalle loro condizioni d'uso.

## Fattori della decisione
- Nessun legame con l'azzardo, nemmeno indiretto.
- Fonti di dati con condizioni d'uso chiare.
- La qualità dei consigli, misurata con `python -m fanta verifica`.

## Opzioni considerate
- Tenere le quote.
- Toglierle e stimare tutto dai dati delle partite precedenti.

## Decisione
Scelta: il modello non usa quote dei bookmaker né scommesse (tolte il 31/10/2026). Il fantavoto atteso e la probabilità di
giocare vengono solo da dati precedenti alla partita.

## Conseguenze
- Bene: nessun legame con l'azzardo; meno fonti da tenere vive.
- Male: un segnale in meno per il modello.
- Controlli: non si reintroducono; ogni cambio del modello si misura con `python -m fanta verifica` prima e dopo.
