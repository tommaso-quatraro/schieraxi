---
name: ui-schieraxi
description: Come devono essere schermate e testi di SchieraXI (web e iPhone) - cosa mostra una schermata, numeri del giocatore, parole, densità, aspetto. Usala prima di disegnare, cambiare o rivedere un'interfaccia o un testo che l'utente vede.
---
# Schermate e testi di SchieraXI

Documenti da consultare per i dettagli (solo le parti che servono): `docs/DESIGN.md` (scala, colori, componenti),
`docs/STILE-SENZA-AI.md` (cosa evitare), `docs/COERENZA-WEB-IPHONE.md` (parole e forme comuni a web e iPhone),
`ios/docs/LINEE-GUIDA-INTERFACCIA.md`.

## Cosa mostra una schermata
- Ogni schermata risponde a una domanda sola e la risposta sta nel primo schermo del telefono. Se per arrivarci bisogna
  scorrere, la schermata è sbagliata.
- Un fatto si dice una volta. Niente elenchi che ripetono ciò che è già sul campo, niente frase che spiega un'altra frase.
- Una cosa che non porta a un'azione non è un «da fare»: è un'informazione, e va dove l'utente la cerca.
- Una spiegazione lunga è il segno di un numero mostrato male: prima si cambia il numero, poi si toglie la spiegazione.
- Le impostazioni sono un costo: una scelta che il server può fare bene da solo non si chiede all'utente.

## Il giocatore
- Un solo fantavoto atteso per giocatore, lo stesso ovunque, calcolato dal server.
- Accanto al numero al massimo un'altra informazione (quanto è probabile che giochi), e solo quando conta.
- «Titolare» e «panchina» vogliono dire la formazione dell'utente. Lo stato del giocatore nella sua squadra si dice con
  altre parole («in dubbio», «infortunato», «squalificato»).

## Parole
- Italiano semplice, frasi brevi, verbi d'azione sui pulsanti. Niente sigle tecniche.
- Plurali giusti («1 credito», «2 crediti»). Numeri con la virgola italiana, cifre allineate.
- Errori: cosa è successo e cosa fare, in una frase.
- «SchieraXI» si scrive sempre così. Niente frasi a effetto.

## Aspetto
- Un dato principale per riga, grande; il resto piccolo. Il colore solo se vuol dire qualcosa, mai come unico segnale.
- Bersagli di tocco di almeno 44 px. Chiaro e scuro, testo grande, movimento ridotto.
- Tablet e PC usano lo spazio (colonne, elenco e dettaglio), non il telefono allargato.
- Vietati: sfondi a macchie sfumate, ombre e vetro su ogni carta, etichette MAIUSCOLE spaziate, emoji come icone, frecce
  nel testo dei pulsanti, parole del titolo colorate, entrate a cascata di ogni blocco.

## Prima di chiudere
Guarda la schermata vera a 390 px e a 1440 px (skill `collaudo`) e confrontala con una schermata che c'è già: deve
sembrare la stessa app.
