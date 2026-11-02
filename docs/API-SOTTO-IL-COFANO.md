# Specifica: `GET /api/sotto-il-cofano`

Realizzata nel server (`fanta/sotto_il_cofano.py`, rotta in `server.py`, pagina web in Impostazioni > Informazioni > Sotto il cofano) e proposta per iOS e Android. Differenze dalla bozza: `attuali.ombra.quote_giocatore` ha solo `righe`, `ultima`, `giornate` (niente crediti dell'API); la rotta è personale ma NON vale con il token del widget (403). Serve per mostrare «Sotto il cofano» (Impostazioni > Informazioni) con lo STESSO testo su web, iOS e Android.
I testi stanno in `fanta/contenuti/sotto-il-cofano.json` (fonte unica; la versione leggibile è `docs/SOTTO-IL-COFANO.md`, generata da quel file). Il server li serve con alcuni numeri aggiornati; i client non hanno testi propri, solo il disegno.

## Perché un endpoint e non il testo dentro ogni app
Una correzione di testo o un numero nuovo arriva a tutti con un aggiornamento del server (il server si aggiorna da solo), senza rilasciare tre app. I client mostrano quello che arriva e ricordano l'ultima copia per l'uso senza rete.

## Richiesta
`GET /api/sotto-il-cofano` senza parametri. Come le altre `GET`: niente `X-Fanta`; in modalità multiutente serve la sessione (come ogni `/api/*`). Contiene testi uguali per tutti; solo `attuali.affidabilita` dipende dall'utente (le sue rose), per questo va dietro il contesto della lega (`Depends(lega_corrente)`).
Intestazioni: `ETag` (hash del corpo) e `Cache-Control: no-cache`; con `If-None-Match` uguale risponde `304` (opzionale per i client).

## Risposta `200`
```
{
  "formato": 1,                         // versione della struttura; un client che non la conosce mostra «aggiorna l'app»
  "titolo": "Sotto il cofano", "sottotitolo": "...", "aggiornato": "2026-10-30",
  "livelli": {"base": "...", "nerd": "..."},
  "introduzione": ["paragrafo", ...],   // testo semplice, nessun markdown
  "sezioni": [ {                        // nell'ordine in cui si mostrano
      "id": "fantavoto-atteso", "titolo": "...", "livello": "base" | "nerd",
      "paragrafi": ["...", ...],
      "formula": "testo su più righe (\n) in carattere a spaziatura fissa" | assente,
      "esempio": {"titolo": "...", "testo": "...", "origine": "vero" | "di calcolo"} | assente,
      "numeri": ["backtest.errore_modello", ...] | assente,        // chiavi di `misure.voci`
      "rimandi": [{"schermata": "stato-dati", "etichetta": "Stato dei dati"}] | assente
  } ],
  "glossario": [{"termine": "...", "spiegazione": "..."}],
  "misure": {
    "riferimento": {                    // dal file: misura fatta in una data precisa (backtest, oracolo, stili), non cambia da sola
      "data": "2026-10-30", "come": "...", "nota": "...",
      "voci": {"backtest.errore_modello": {"valore": 1.46, "etichetta": "...", "unita": "punti"}, ...}
    },
    "attuali": {                        // calcolati dal server a ogni richiesta (letture rapide, mai simulazioni)
      "voci": {"app.errore_modello": {"valore": 1.60, "aggiornato": "2026-10-28T00:38:07"}, ...},   // assenti se la prova non è ancora stata fatta
      "affidabilita": {"giornate": 8, "ultima": "2026-27/8", "calcolato": "...", "sintesi": {...}} | null,
      "calibrazione": {"giornate": 3, "gruppi": [...], "fattori": {...}},
      "ombra": {"partite_extra": {...}}
    }
  }
}
```
Il campo `fonte_codice` che c'è nel file NON viene inviato (è per chi controlla i testi).

### Come un client usa i numeri
Per ogni chiave in `sezione.numeri`: se esiste in `misure.attuali.voci` mostra quel valore con «aggiornato il…»; altrimenti mostra `misure.riferimento.voci[chiave]` con «misura del {data}». Chiavi `app.*` = prova automatica dell'app sulle ultime giornate (dal file `dati/affidabilita.json`, `affidabilita.carica` e `affidabilita.sintesi`); chiavi `backtest.*`, `oracolo.*`, `diario.*`, `formazione.*` = solo riferimento. Mai mescolare due finestre di giornate senza dire quale: `app.*` sono le ultime 8 giornate, `backtest.*` sono 41.
In `attuali.ombra` i client mostrano solo i campi che conoscono e ignorano gli altri (anche quelli dei server vecchi, ora non più prodotti): ogni campo è facoltativo.
`attuali.calibrazione` e `attuali.ombra` vengono da `stato_dati.calibrazione`/`fattori_da` e `stato_dati.ombra`: stesse funzioni di `/api/stato-dati`, nessun calcolo nuovo.

### Identificatori di schermata (`rimandi[].schermata`)
`oggi`, `formazione`, `scambi`, `mercato`, `lega`, `regole`, `crediti`, `stato-dati`, `diario`, `giocatore`, `novita`. Ogni client li collega alla sua navigazione; un id sconosciuto va mostrato come testo semplice, senza link (il contenuto può crescere prima delle app).

## Come mostrarlo (indicazioni per i tre client)
- Prima le sezioni `base` aperte; le `nerd` dietro un interruttore «Mostra i dettagli per i più nerd» (ricordato sul dispositivo), oppure una sezione ripiegabile ciascuna. Il glossario in fondo, ordinato per termine, con ricerca se la lista è lunga.
- `formula`: carattere a spaziatura fissa, scorrimento orizzontale, testo selezionabile (non immagine: deve poter essere letto da VoiceOver/TalkBack). `esempio`: carta con etichetta «Numeri veri» o «Esempio di calcolo» secondo `origine`.
- Una riga di data in cima: «Testi aggiornati il {aggiornato}; misure del {riferimento.data}».
- Tutto è testo semplice in italiano; `«»` e `±` sono caratteri normali. Niente HTML e niente markdown da interpretare.

## Errori
- File mancante o non valido: `503` con `{"detail": "I testi di «Sotto il cofano» non sono disponibili in questo momento"}`; il client mostra l'ultima copia salvata.
- Il server legge il file una volta e lo ricarica se cambia (data di modifica), come per `novita.json`; deve controllare all'avvio e in un test che: JSON valido, `id` unici, `livello` solo `base`/`nerd`, ogni chiave di `numeri` esiste in `misure.riferimento.voci`, ogni `schermata` è nell'elenco sopra.

## Passi per realizzarlo (piccoli, ognuno verificabile)
1. Server: lettore con cache e controlli + rotta + test (`tests/test_sotto_il_cofano.py`: struttura, chiavi dei numeri, 304, 503, e che `fonte_codice` non esca). Fatto quando: `GET /api/sotto-il-cofano` risponde 200 con `attuali.voci` riempiti se esiste `affidabilita.json`, e il job `versione` passa con un file in `fanta/novita.d/`.
2. Web: vista in fondo a Lega (poi spostata in Impostazioni > Informazioni). Fatto quando: si legge su telefono, le formule non escono dallo schermo, tema chiaro e scuro, `VERSIONE` di `sw.js` alzata.
3. iOS (SwiftUI) e Android (Compose): stessa struttura. Fatto quando: gli stessi testi, con `Codable`/`kotlinx.serialization` che ignorano i campi sconosciuti.
4. Quando una misura cambia (nuovo backtest, nuova fonte promossa): aggiornare `misure.riferimento` e le frasi che ne parlano nello stesso file, rigenerare `docs/SOTTO-IL-COFANO.md`. Regola: ogni affermazione nel testo deve avere in `fonte_codice` il punto del codice che la rende vera; se il codice cambia, si rilegge la sezione.

## Decisioni per l'utente
- Se la sezione `limiti-tecnici` deve restare nell'app così com'è: dice apertamente che la barra «oscilla di ±N» è più stretta della realtà (da 0,7 a 2,6 contro circa 5,9 punti). È una scoperta utile; se la si ritiene da correggere nel modello, è un lavoro a parte (dare variabilità al fantavoto nella simulazione) e va misurato con `verifica` prima e dopo.
- Se l'avvertimento sulle fonti (Understat e Fantacalcio.it: termini d'uso non pensati per un uso da programma) va mostrato a tutti o solo a chi attiva più utenti.
