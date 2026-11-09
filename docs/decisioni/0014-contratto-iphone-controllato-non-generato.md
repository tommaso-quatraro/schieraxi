# 0014. Il contratto fra iPhone e server si controlla, non si genera

Data: 9/11/2026. Stato: accettata (scelta della spec dell'ondata 2, §6; messa in opera con le PR #520 e #534, issue #506 e #507).

## Contesto e problema
Se il server toglie o rinomina un campo che l'app per iPhone legge, l'app installata mostra «una risposta che l'app non capisce» e lo
scopre l'utente. L'idea naturale è generare i modelli Swift dall'OpenAPI del server, ma `docs/openapi.json` descrive i corpi delle
richieste e nessuna risposta: le rotte restituiscono dizionari. Spec: `docs/superpowers/specs/2026-11-08-ondata-2-design.md`, §4 e (f).

## Fattori della decisione
- Un errore si deve vedere nella PR, possibilmente in pochi secondi su Linux, senza aspettare un Mac.
- Rischio: i modelli dell'iPhone hanno logica loro; riscriverli senza Mac in locale è pericoloso.
- Nessuna libreria nuova.

## Opzioni considerate
- Descrivere le risposte sul server e generare i modelli Swift dall'OpenAPI.
- Due controlli: i nomi dei campi su Linux in ogni PR, i tipi sul Mac con le risposte vere registrate.
- Nessun controllo: affidarsi alle foto e alla revisione.

## Decisione
Scelta: i due controlli. Su Linux `tests/contratto_ios.py` (con `tests/test_contratto_ios.py`) legge i modelli `Decodable`
dell'iPhone e vuole ogni campo come chiave da qualche parte in `fanta/`; le eccezioni stanno, ognuna con il motivo, in
`tests/dati/contratto_ios_eccezioni.json`. Sul Mac `ios/Tests/SchieraxiTests/ContrattoDalVeroTests.swift` legge le risposte di
`ios/fotografie/vero-*.json` con i tipi e il decodificatore dell'app. Generare oggi vorrebbe dire descrivere tutte le risposte sul
server e riscrivere i modelli: troppo per ora. Senza controlli l'errore lo trova l'utente.

## Conseguenze
- Bene: una chiave sparita da tutto il server si vede in ogni PR in pochi secondi; un tipo sbagliato si vede in `ios / test`.
- Male (il prezzo): il controllo su Linux non vede un campo tolto da una sola rotta se la chiave resta in un altro file (circa 3
  chiavi su 10 lette dall'iPhone stanno in 5 o più file); quello sul Mac vede solo i dati dell'ultima registrazione. Chi rivede una
  PR che toglie o rinomina una chiave guarda lo stesso le rotte lette dall'iPhone (`docs/METODO.md`, «Contratto delle API»).
- I corpi delle richieste generati dall'OpenAPI restano un'idea rimandata (#509).
