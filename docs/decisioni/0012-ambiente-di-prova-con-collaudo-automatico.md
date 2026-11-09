# 0012. Ogni versione passa prima da un ambiente di prova sullo stesso server, collaudato in automatico

Data: 9/11/2026. Stato: accettata (proposta della spec dell'ondata 2, accesa sul server con l'ok del proprietario l'8/11; PR #523,
#526, #539, #553; issue #510, #511, #512, #549).

## Contesto e problema
Una versione nuova arrivava subito in produzione: un errore lo vedeva per primo chi usa l'app. Prima di aprire l'app agli amici
(#168) serve un posto dove ogni versione gira davvero, con un collaudo che non dipende da qualcuno che si ricorda di farlo. Spec:
`docs/superpowers/specs/2026-11-08-ondata-2-design.md`, (c); piano `docs/superpowers/plans/2026-11-08-ondata-2.md`, C1-C3 e §4.

## Fattori della decisione
- Costo: nessun server in più da pagare e da curare.
- Sicurezza: la prova fa girare codice che in produzione non c'è ancora, quindi non deve vedere i dati della produzione né avere
  meno protezioni.
- Niente avvisi, posta o fonti dalla prova: non deve parlare con gli utenti né con l'esterno.
- Un collaudo rosso si deve vedere subito, nello stesso posto degli altri guasti.

## Opzioni considerate
- Un secondo server per la prova.
- Una seconda copia dell'app sullo stesso server, con un utente e un servizio suoi.
- Nessuna prova: solo i controlli delle PR e la sentinella in produzione.

## Decisione
Scelta: la seconda copia sullo stesso server (`script/server/prova/`): utente di sistema `schieraxi-prova`, servizio su
`127.0.0.1:8001`, `https://prova.<dominio>` non indicizzato, almeno le stesse protezioni systemd della produzione, registrazione solo
con invito, archivio dei dati di calcio copiato ogni notte dalla produzione, pianificatore, registro delle giornate, copia alla
scadenza, posta e fonti spenti. La spec proponeva lo stesso utente della produzione; sul server si è scelto un utente suo, senza
nessun permesso sui file della produzione. `aggiorna-app.sh` con
`SCHIERAXI_ISTANZA=prova` la aggiorna prima della produzione, senza aspettare le partite. Un workflow di GitHub
(`collaudo-prova.yml`) la collauda ogni 20 minuti dopo un rilascio e ogni giorno alle 5:17 UTC; se non passa apre un'issue `P1` e
la corsa è rossa. Il secondo server è scartato per il costo; «nessuna prova» lascerebbe l'utente a fare da collaudatore.

## Conseguenze
- Bene: ogni versione è provata con un account di collaudo prima che la usi qualcuno; il collaudo rosso entra nella misura della
  «giornata senza errori» (decisione 0013).
- Male (il prezzo): la prova usa memoria e processore dello stesso server (`MemoryMax`, `CPUWeight`, `Nice=19`); i segreti
  `PROVA_URL`, `PROVA_UTENTE`, `PROVA_PASSWORD` stanno su GitHub; il collaudo non fa foto (i calciatori sono veri), solo misure.
- La produzione installa anche le versioni non ancora collaudate: il «cancello» (la produzione prende solo le versioni collaudate)
  è una scelta del proprietario, dopo.
- Controlli: `tests/test_prova_server.py`, `tests/test_collaudo_prova.py`; comandi e ritorno indietro in `script/server/prova/LEGGIMI.md`.
