# 0013. #167 si chiude con una «giornata senza errori» misurata da un comando, mai verde per omissione

Data: 9/11/2026. Stato: accettata (misura della spec di prodotto, §6; messa in opera con le PR #544 e #546, issue #532 e #533).

## Contesto e problema
La spec di prodotto (`docs/superpowers/specs/2026-11-08-prodotto-design.md`, §6) dice che l'obiettivo #167 è raggiunto con una
giornata intera senza errori. Detto a parole, ognuno lo può leggere a modo suo, e un pezzo che manca (la sentinella ferma, nessun
collaudo) sembrerebbe «nessun errore». Serve una misura ripetibile. Piano: `docs/superpowers/plans/2026-11-08-ondata-2.md`, (h).

## Fattori della decisione
- Stessa risposta per chiunque la lanci, con le stesse date.
- Conta lo stato per tutta la finestra: un guasto nato prima e ancora aperto non si dimentica.
- Una parte senza dati è un motivo di rosso, non un silenzio.
- Sola lettura: la misura non cambia niente su GitHub né sul server.

## Opzioni considerate
- Giudizio a occhio del coordinatore a fine giornata.
- Contare solo gli errori nuovi della finestra.
- Un comando che mette insieme sentinella, issue, controlli su `main` e collaudo della prova, e dice «ok» solo se tutto c'è ed è verde.

## Decisione
Scelta: il comando `python script/squadra/squadra.py giornata --dal … --al … --sentinella <file>` (`script/squadra/giornata.py`).
La finestra va dalla scadenza della lega a due giorni dopo l'inizio dell'ultima partita. Rosso se: la sentinella ha un allarme o
resta più di 2 ore senza girare; nasce un'issue `P1` o `dall-utente`; un'issue «CI: main rosso», «Collaudo della prova: v<N> non passa» o «La prova
non si aggiorna» è aperta in qualche momento della finestra; una corsa dei controlli su `main` o del collaudo è rossa; la prova non è
stata collaudata davvero; manca il file della sentinella. Per questo la sentinella ricorda ogni giro (`giri` in
`dati/sentinella.json`, 60 giorni). Il giudizio a occhio non è ripetibile; contare solo gli errori nuovi lascerebbe verde una
giornata con `main` rosso da prima.

## Conseguenze
- Bene: «#167 è chiuso» diventa un fatto controllabile; lo stesso comando servirà per ogni giornata dopo.
- Male (il prezzo): il file dei giri si porta a mano dal server (sola lettura) a finestra finita; una giornata senza versioni nuove
  ha bisogno di un collaudo (quello delle 5:17 UTC o uno lanciato a mano).
- Controlli: `tests/test_squadra_giornata.py`, `tests/test_sentinella_giri.py`. Uso e codici di uscita in `script/squadra/LEGGIMI.md`.
