# Sotto il cofano

*Come ragiona SchieraXI, passo per passo, e quanto ci si può fidare*

Versione leggibile dei testi di `fanta/contenuti/sotto-il-cofano.json`, che è la fonte unica: web, iOS e Android mostrano lo stesso testo (vedi `docs/API-SOTTO-IL-COFANO.md`). Questo file è generato dal JSON: non modificarlo a mano, cambia il JSON e rigeneralo. Aggiornato al 2026-10-30.

Nell'app si trova in Impostazioni > Informazioni > «Sotto il cofano». Le sezioni **[base]** sono per tutti, le **[nerd]** hanno formule e parametri. Le righe «Codice» (file:funzione) non si vedono nell'app.

SchieraXI non indovina il futuro: stima, per ogni giocatore e per ogni giornata, quanti punti fantacalcio porterà in media, e poi sceglie la formazione che in media ne porta di più. Qui sotto trovi come fa, da dove prende i dati e, soprattutto, dove sbaglia.

Le sezioni «base» si leggono in un minuto ciascuna. Quelle «nerd» hanno formule, parametri e piccoli esempi con numeri veri, calcolati con il modello e con le regole della lega usata per le prove (bonus gol 3, assist 1, ammonizione -0,5, modificatore difesa a soglie).

I numeri di affidabilità sono misure vere fatte il 30/10/2026 sulle giornate già giocate (2025-26 dalla giornata 5 e 2026-27 fino alla giornata 8) con le rose della lega di prova. Nell'app si aggiornano da soli nella schermata Stato dei dati.

## Indice

1. [base] Il quadro generale
2. [base] Come nasce il fantavoto atteso
3. [nerd] Il voto in pagella atteso
4. [nerd] Il peso del tempo: forma recente e stagioni passate
5. [nerd] Il restringimento verso la media (shrinkage)
6. [nerd] Gol e assist: da xG e xA alle probabilità
7. [nerd] Gol attesi della partita: forza delle squadre
8. [nerd] Portieri: gol subiti e porta inviolata
9. [nerd] Cartellini, autogol e migliore in campo
10. [base] La probabilità di giocare e le probabili formazioni
11. [nerd] Senza probabili: presenze recenti, coppe e calibrazione
12. [base] Come si sceglie la formazione
13. [nerd] La simulazione delle sostituzioni
14. [nerd] La panchina: per ruolo o libera
15. [base] Gli stili: preset di rischio e di modulo
16. [nerd] Gli stili alla prova
17. [base] Come si valuta uno scambio
18. [nerd] Scambi: il conto, la stima veloce e le proposte
19. [nerd] Scambi N contro M (da 1 a 4 giocatori per lato)
20. [nerd] Conguagli in crediti
21. [base] Svincoli e rimborso
22. [nerd] Asta e riparazione
23. [base] Quanto è affidabile? La prova sul passato
24. [nerd] Le misure: errore, Brier e punti
25. [nerd] L'esperimento «oracolo»: quanto vale sapere in anticipo
26. [base] Il diario: la tua scelta contro la consigliata
27. [base] Da dove arrivano i dati e ogni quanto
28. [nerd] Dati puliti: nomi, controlli e rischi delle fonti
29. [nerd] Fonti in modalità ombra e come si promuovono
30. [nerd] Gli avatar: volti inventati dal codice
31. [base] La tecnologia in breve
32. [nerd] Backup e sicurezza in breve
33. [base] I limiti onesti: cosa il modello non sa fare
34. [nerd] Limiti tecnici e rischi di sovradattamento

## Le misure di riferimento

Data: 2026-10-30. python -m fanta verifica e python -m fanta oracolo, regole e rose della lega del repository, 300 simulazioni per formazione, archivio con le stagioni 2025-26 (38 giornate) e 2026-27 (8 giornate giocate).

Misura di una data precisa su un campione piccolo: serve per capire l'ordine di grandezza, non per promettere punti. I valori marcati «app» sono la prova automatica che l'app rifà da sola dopo ogni giornata finita (ultime 8 giornate, file affidabilità del 28/10/2026).

| Misura | Valore | Unità |
|---|---|---|
| Giornate provate (`backtest.giornate`) | 41 | giornate |
| Casi squadra-giornata con rosa sufficiente (almeno 20 giocatori presenti) (`backtest.casi_rosa`) | 93 | casi |
| Errore del modello sul fantavoto di chi ha giocato (radice dell'errore quadratico medio) (`backtest.errore_modello`) | 1,46 | punti |
| Errore del modello, stagione 2025-26 (34 giornate) (`backtest.errore_modello_2025_26`) | 1,43 | punti |
| Errore di una stima «da fantamedia», stagione 2025-26 (`backtest.errore_fantamedia_2025_26`) | 1,5 | punti |
| Errore del modello, stagione 2026-27 (7 giornate) (`backtest.errore_modello_2026_27`) | 1,61 | punti |
| Errore di una stima «da fantamedia», stagione 2026-27 (`backtest.errore_fantamedia_2026_27`) | 1,84 | punti |
| Punteggio di Brier delle probabilità di giocare (0 = perfetto, 0,25 = dire sempre 50%) (`backtest.brier`) | 0,157 |  |
| Punti veri a giornata con la formazione consigliata (`backtest.punti_modello`) | 68,6 | punti |
| Massimo possibile col senno di poi (stessa rosa, stessi giorni) (`backtest.punti_perfetta`) | 71,8 | punti |
| Punti con la consigliata, 2025-26 (`backtest.punti_modello_2025_26`) | 67,1 | punti |
| Punti scegliendo da fantamedia, 2025-26 (`backtest.punti_fantamedia_2025_26`) | 66,5 | punti |
| Massimo possibile, 2025-26 (`backtest.punti_perfetta_2025_26`) | 69,0 | punti |
| Punti con la consigliata, 2026-27 (`backtest.punti_modello_2026_27`) | 71,9 | punti |
| Punti scegliendo da fantamedia, 2026-27 (`backtest.punti_fantamedia_2026_27`) | 71,3 | punti |
| Massimo possibile, 2026-27 (`backtest.punti_perfetta_2026_27`) | 77,9 | punti |
| Guadagno se si sapesse in anticipo chi prende voto (`oracolo.presenze`) | 0,68 | punti a giornata |
| Guadagno se si sapessero i gol veri della squadra (`oracolo.gol_squadra`) | 1,35 | punti a giornata |
| Guadagno se si sapesse il rigorista vero (`oracolo.rigorista`) | 0,02 | punti a giornata |
| Guadagno sapendo tutte e tre le cose insieme (`oracolo.tutti`) | 2,5 | punti a giornata |
| Soglia sotto la quale una lacuna non vale una fonte nuova (`oracolo.soglia`) | 0,3 | punti a giornata |
| Errore sul fantavoto sapendo i gol veri della squadra (invece di 1,46) (`oracolo.errore_gol_squadra`) | 1,3 | punti |
| Scarto tipico tra punti fatti e attesi della consigliata (8 giornate del 2026-27) (`diario.scarto_tipico`) | 5,9 | punti |
| Deviazione della sola simulazione (dev_simulata) sulle formazioni delle prime 4 rose di prova: non è più quella mostrata (`formazione.oscillazione_mostrata`) | da 0,7 a 2,6 | punti |
| Deviazione dello scarto tra punti fatti e attesi (913 casi, 41 giornate) (`incertezza.scarto_vero`) | 6,7 | punti |
| Larghezza della fascia «8 volte su 10» con una dev_simulata di 2 (da −8,0 a +8,5) (`incertezza.fascia_larghezza`) | 16,5 | punti |
| Quota dei punti veri dentro la fascia, obiettivo 80% (`incertezza.copertura`) | 80% (76% sulle rose della lega) |  |
| App: errore del modello nelle ultime 8 giornate (`app.errore_modello`) | 1,6 | punti |
| App: errore da fantamedia nelle ultime 8 giornate (`app.errore_fantamedia`) | 1,82 | punti |
| App: punti con la consigliata nelle ultime 8 giornate (`app.punti_modello`) | 71,7 | punti |
| App: punti da fantamedia nelle ultime 8 giornate (`app.punti_fantamedia`) | 70,6 | punti |
| App: massimo possibile nelle ultime 8 giornate (`app.punti_perfetta`) | 77,8 | punti |

## 1. Il quadro generale  [base]

Il lavoro si fa in quattro tempi. 1) Raccoglie i dati: calendario, voti, probabili formazioni, statistiche avanzate (gli xG). 2) Per ogni giocatore calcola due numeri: la probabilità che prenda voto e il fantavoto che farebbe se gioca. 3) Con quei numeri sceglie la formazione, valuta gli scambi, propone gli svincoli. 4) Si controlla da solo: rifà i conti sulle giornate passate, usando solo ciò che si sapeva allora, e confronta con quello che è successo davvero.

Tutte le regole della tua lega (bonus, malus, moduli, panchina, modificatore difesa) vengono dalla configurazione della lega e non sono scritte nel codice: cambiando le regole cambiano i conti.

Formula:

```
dati -> forza delle squadre e dei giocatori -> (probabilità di giocare, fantavoto se gioca) -> formazione / scambi / svincoli -> verifica sul passato
```

Nell'app: Oggi; Stato dei dati.

Codice: `fanta/modello.py:previsioni`, `fanta/formazione.py:migliore`, `fanta/verifica.py:verifica`, `fanta/regole.py:Regole`

## 2. Come nasce il fantavoto atteso  [base]

Per ogni giocatore il modello tiene separate due domande. La prima: giocherà? (la probabilità di prendere voto, chiamata p). La seconda: se gioca, quanto fa? (il fantavoto atteso, chiamato mu). I punti attesi sono semplicemente p per mu.

Il mu si costruisce come il fantavoto vero: parte dal voto in pagella che ci si aspetta e aggiunge i bonus e i malus della tua lega, ognuno moltiplicato per quanto è probabile che accada (gol attesi, assist attesi, probabilità di ammonizione e così via). I rigori hanno una quota a parte. Per i portieri si aggiungono i gol subiti e la porta inviolata.

Formula:

```
punti attesi = P(prende voto) × mu
mu = voto in pagella atteso
   + bonus_gol(ruolo) × gol attesi + bonus_assist × assist attesi
   + rigori attesi × (0,78 × bonus_rigore_segnato + 0,22 × malus_rigore_sbagliato)
   + malus_ammonizione × P(ammonizione) + malus_espulsione × P(espulsione) + malus_autogol × P(autogol) + bonus_mvp × P(migliore in campo)
   + (solo portieri) malus_gol_subito × gol subiti attesi + bonus_imbattuto × P(porta inviolata) + rigori parati attesi × bonus
```

> **Un caso vero: Thuram, giornata 8 del 2026-27 (Inter-Fiorentina)** (numeri veri del modello). Calcolo rifatto il 30/10/2026 con i soli dati precedenti alla giornata 8 (senza probabili, quindi p viene dalle presenze, vedi la sezione 11: ha preso voto in tutte le ultime 6 partite, ma p = 0,86, ricalcolata il 2/11/2026). La partita vale 2,46 gol attesi per l'Inter contro 0,99 della Fiorentina. Voto in pagella atteso 6,46; gol attesi 0,505 e a 3 punti l'uno fanno +1,52; assist attesi 0,144 fanno +0,14; cartellini e altro circa -0,06. Totale mu = 8,06. La probabilità di segnare almeno un gol è 1 - e^(-0,505) = 39,7%.

Nell'app: Formazione (tocca un giocatore per vedere i pezzi); Lega > Regole.

Codice: `fanta/modello.py:previsioni`, `fanta/punteggio.py:fantavoto`, `fanta/consigli.py:_componenti`

## 3. Il voto in pagella atteso  [nerd]

Il voto in pagella atteso è una media dei voti passati del giocatore (la fonte voto è un'impostazione della lega: redazione, statistico o Italia), con due correzioni. Primo: i voti vecchi pesano meno (vedi «Il peso del tempo»). Secondo: la media viene tirata verso quella tipica del ruolo quando i dati sono pochi (vedi «Il restringimento verso la media»).

Poi si aggiusta per la partita: per ogni gol di vantaggio atteso della squadra sull'avversaria si aggiungono 0,1 punti di voto (beta_voto = 0,1). Chi gioca una partita facile prende voti un po' più alti, chi gioca una partita difficile un po' più bassi. Con 2,46 gol attesi contro 0,99 sono +0,15 di voto.

Formula:

```
voto in pagella atteso = (Σ peso × voto + 20 × voto_di_partenza) / (Σ peso + 20) + 0,1 × (gol attesi squadra - gol attesi avversario)
```

> **Un esempio di calcolo (numeri scelti per far vedere la formula)** (esempio di calcolo). Un centrocampista con 5 presenze pesate e voto medio pesato 7,0, in un ruolo la cui partenza è 6,0: (5 × 7,0 + 20 × 6,0) / (5 + 20) = 6,2. Con poche partite la media alta viene presa solo in parte.

Codice: `fanta/modello.py:previsioni`, `fanta/modello.py:Parametri`, `fanta/punteggio.py:COLONNA_VOTO`

## 4. Il peso del tempo: forma recente e stagioni passate  [nerd]

Ogni partita passata entra nei conti con un peso che scende col tempo: una giornata prima vale 0,92 volte quella dopo, due giornate prima 0,92 al quadrato, e così via. Dopo circa 8 giornate il peso si dimezza. Questo è l'unico modo in cui il modello tiene conto della «forma recente»: non esiste un bonus separato per chi è in serie positiva.

Le partite della stagione scorsa valgono in più la metà (peso_stagione_prec = 0,5). Tra due stagioni il conto della distanza lascia 50 «giornate» (38 più la pausa estiva), quindi alla giornata 1 una partita dell'ultima giornata della scorsa stagione pesa 0,92^13 × 0,5, cioè circa 0,17 rispetto a una partita appena giocata.

Gli stessi pesi servono per voti, gol, assist, minuti e per la forza delle squadre. Il modello usa soltanto partite giocate prima della data d'inizio della giornata che sta prevedendo: così lo stesso codice si può provare sul passato senza «barare».

Formula:

```
peso della partita = 0,92 ^ (giornate di distanza) × (1 se stessa stagione, 0,5 se scorsa)
```

> **Mezza vita** (esempio di calcolo). 0,92^8 = 0,51: una partita di 8 giornate fa conta la metà dell'ultima. Una di 16 giornate fa conta un quarto.

Codice: `fanta/modello.py:_pesi`, `fanta/modello.py:Parametri`, `fanta/modello.py:PASSO_STAGIONE`, `fanta/modello.py:Dati.inizio`, `fanta/modello.py:prima_di`

## 5. Il restringimento verso la media (shrinkage)  [nerd]

Con poche partite una media è inaffidabile: un attaccante con un gol in una presenza non ha «un gol a partita». Per questo ogni stima è mescolata con una stima di partenza come se il giocatore avesse già giocato un certo numero di partite fittizie: 20 presenze per il voto (k_voto), 16 partite intere da 90 minuti per gol e assist (k_90), 10 per i cartellini, 20 per gli autogol, 6 partite per la forza delle squadre. Più il giocatore ha giocato, meno conta la stima di partenza.

La stima di partenza non è per forza la media del ruolo. Per i giocatori con poche partite il modello usa la quotazione iniziale di inizio stagione, fissata prima del campionato e quindi senza informazioni dal futuro. Per ogni ruolo calcola, sui dati già giocati, la retta che lega quotazione a voto, gol e assist ogni 90 minuti (servono almeno 15 giocatori con dati sufficienti) e vi fa partire i nuovi: un bomber appena arrivato parte da una stima da bomber, non da attaccante medio. Per gol e assist la stima è comunque tenuta tra un quarto e quattro volte la media del ruolo. Per il voto si usa solo metà della retta (a metà strada tra la media del ruolo e la retta): con la retta intera il voto dei giocatori più cari veniva sopravvalutato di circa un decimo, in tutte e due le stagioni provate (misura del 2/11/2026).

I valori dei parametri sono stati tarati il 26/10/2026 sulla stagione 2025-26 (giornate 5-38) minimizzando l'errore quadratico, e poi controllati sul 2026-27.

Formula:

```
stima = (Σ peso × osservazioni + k × valore di partenza) / (Σ peso + k)
```

> **Esempio di calcolo per i gol** (esempio di calcolo). Un attaccante con 3,0 gol attesi (senza rigori) in 5 partite complete e un tasso di partenza di 0,25 gol ogni 90 minuti: (3,0 + 16 × 0,25) / (5 + 16) = 0,33 gol ogni 90 minuti. Senza il restringimento sarebbe 0,60.

Codice: `fanta/modello.py:Parametri`, `fanta/modello.py:previsioni`, `fanta/modello.py:forza_squadre`, `fanta/modello.py:PESO_QUOTAZIONE_VOTO`

## 6. Gol e assist: da xG e xA alle probabilità  [nerd]

L'xG (gol attesi) è la probabilità che un tiro diventi gol, stimata da dove e come è partito; l'xA fa lo stesso per l'ultimo passaggio. Sono più stabili dei gol veri, che sono rari e dipendono molto dalla fortuna. Il modello usa solo l'xG per i gol (peso_xg = 1,0, senza i rigori: un rigore vale 0,76 xG e viene tolto) e per gli assist mescola il 30% di xA e il 70% di assist veri (peso_xa = 0,3).

Il tasso del giocatore (gol e assist ogni 90 minuti, con pesi nel tempo e restringimento) viene moltiplicato per la quota di partita che giocherà (minuti attesi diviso 90, al massimo 1) e per il «fattore partita»: i gol attesi della squadra in questa partita diviso i suoi gol attesi normali, tenuto tra 0,5 e 2.

Per i rigori conta la quota di rigori della squadra che il giocatore ha calciato (rigori suoi / rigori della squadra + 0,5) per i rigori attesi per partita (media del campionato, 0,13 nella prova fatta il 30/10/2026). Ogni rigore è segnato con probabilità 0,78 (conversione_rigori) e sbagliato con 0,22.

La probabilità di «almeno un gol» si ottiene da una distribuzione di Poisson (quella degli eventi rari e indipendenti): 1 meno e alla meno il numero di gol attesi, rigori compresi. La stessa cosa per gli assist.

Formula:

```
gol attesi = tasso gol/90' × min(minuti,90)/90 × fattore partita
P(almeno un gol) = 1 - e^-(gol attesi + 0,78 × rigori attesi)
rigori attesi = quota rigorista × rigori squadra a partita × fattore partita × min(1, minuti/75)
```

> **Un caso vero: Ramos G. (Milan-Udinese, giornata 8 del 2026-27)** (numeri veri del modello). Gol attesi 0,498 e rigori attesi 0,100. La probabilità di segnare è 1 - e^-(0,498 + 0,78 × 0,100) = 43,8%, come mostra l'app. In punti: 0,498 × 3 + 0,100 × (0,78 × 3 - 0,22 × 3) = 1,49 + 0,17.

Nell'app: Scheda del giocatore.

Codice: `fanta/modello.py:previsioni`, `fanta/modello.py:XG_RIGORE`, `fanta/modello.py:Parametri`, `fanta/fonti/understat.py:leggi_lega`

## 7. Gol attesi della partita: forza delle squadre  [nerd]

Ogni squadra ha un indice d'attacco e uno di difesa (1 = nella media, sopra 1 l'attacco segna di più o la difesa subisce di più), calcolati dagli xG fatti e subiti nelle partite passate con gli stessi pesi nel tempo e il restringimento verso 1. Le neopromosse partono un po' sotto (attacco 0,85, difesa 1,15). C'è anche un fattore campo: calcolato sui dati, nella prova del 30/10/2026 la squadra di casa segna il 4,7% in più (la media del campionato era 1,67 gol per squadra a partita).

I gol attesi si ottengono moltiplicando: base del campionato × attacco di una squadra × difesa dell'altra × fattore campo (diviso, per chi gioca fuori).

Formula:

```
gol casa = base × attacco(casa) × difesa(trasferta) × fattore campo
```

Codice: `fanta/modello.py:forza_squadre`, `fanta/modello.py:Forza.gol_attesi`, `fanta/modello.py:Parametri`

## 8. Portieri: gol subiti e porta inviolata  [nerd]

Per un portiere i gol subiti attesi sono i gol attesi dell'avversario in quella partita (vedi sopra). La probabilità di porta inviolata (clean sheet) è la probabilità che una Poisson con quel valore dia zero: e elevato a meno i gol subiti attesi. Il bonus di porta inviolata e il malus per ogni gol subito vengono dalle regole della lega.

Si aggiunge una piccola quota per i rigori parati: i rigori attesi per squadra a partita × 0,2 × il bonus del rigore parato (il 20% è una stima fissa del modello, non misurata sul singolo portiere).

Il modificatore difesa non fa parte del mu del singolo portiere: è un bonus di squadra che dipende da portiere e difensori insieme, e viene calcolato nella simulazione della formazione (vedi «Come si sceglie la formazione»).

Formula:

```
P(porta inviolata) = e^-(gol subiti attesi)
mu portiere = voto in pagella atteso + malus_gol_subito × gol subiti attesi + bonus_imbattuto × P(porta inviolata) + 0,2 × rigori a partita × bonus_rigore_parato
```

> **Un caso vero: Mandas (Lazio-Parma, giornata 8 del 2026-27)** (numeri veri del modello). Gol subiti attesi 0,74: porta inviolata e^-0,74 = 48%. mu = 6,33 (voto in pagella atteso) - 0,74 + 0,48 + 0,08 (rigori parati) = circa 6,13.

Codice: `fanta/modello.py:previsioni`, `fanta/consigli.py:_componenti`

## 9. Cartellini, autogol e migliore in campo  [nerd]

Ammonizioni, espulsioni, autogol e premio di migliore in campo sono eventi rari e per presenza: si stimano con le frequenze pesate del giocatore, tirate verso quelle del ruolo (10 presenze fittizie per ammonizioni, espulsioni nel mu e migliore in campo; 20 per gli autogol).

Per mostrare la probabilità di rosso nell'app serve più prudenza (60 presenze fittizie invece di 10): un solo rosso non rende un giocatore «un rosso facile». Il valore nel mu e quello mostrato non coincidono per questo motivo.

Formula:

```
P(evento) = (Σ peso × eventi + k × frequenza del ruolo) / (Σ peso + k)
```

Codice: `fanta/modello.py:previsioni`

## 10. La probabilità di giocare e le probabili formazioni  [base]

È la parte più delicata, perché un campione che resta in panchina porta zero punti. Quando ci sono le probabili formazioni di Fantacalcio.it (si aggiornano più volte al giorno) il modello le legge: titolare con una percentuale, panchina con una percentuale, infortunato, squalificato, in dubbio, diffidato.

Un titolare al 90% non gioca con probabilità 0,90: se non parte spesso entra comunque dalla panchina, e il voto manca solo se entra per pochi minuti. Un infortunato o squalificato vale 0. Chi è in dubbio vale un quarto in meno. Un giocatore non citato vale 2%.

Questi numeri di partenza sono scelti a mano. Da 4 giornate giocate con le probabili salvate poco prima della prima partita il server li ritara da solo su metà delle giornate e li prova sull'altra metà; li usa solo da 8 giornate e se sbagliano meno; se poi peggiorano torna ai numeri di partenza.

Formula:

```
titolare con percentuale q: p = (q + (1 - q) × 0,6) × 0,96
panchina con percentuale q: p = q
in dubbio: p × 0,75 · infortunato o squalificato: 0 · non citato: 0,02
```

> **Esempi di calcolo** (esempio di calcolo). Titolare al 90%: (0,90 + 0,10 × 0,6) × 0,96 = 92%. Titolare al 70%: (0,70 + 0,30 × 0,6) × 0,96 = 84%. Panchina al 30% in dubbio: 0,30 × 0,75 = 22,5%.

Nell'app: Formazione (stato e percentuale accanto a ogni giocatore).

Codice: `fanta/modello.py:_p_da_probabili`, `fanta/modello.py:P_SUBENTRO_TITOLARE`, `fanta/modello.py:P_SENZA_VOTO`, `fanta/fonti/fantacalcio.py:leggi_probabili`, `fanta/taratura_probabili.py:esegui`

## 11. Senza probabili: presenze recenti, coppe e calibrazione  [nerd]

Per le giornate lontane, o quando una squadra non è coperta dalle probabili, p viene dalle presenze. Si calcolano quattro quote sulle partite della SUA squadra: presenze recenti (le ultime 6 in cui ha preso voto, con peso 0,75 elevato alla distanza: la più recente pesa 1), presenze lunghe (20 partite, decadimento 0,93), partite iniziate da titolare (ultime 6, stessi pesi) e l'ultima partita da sola. Le partite prima del suo arrivo in quella squadra e quelle rinviate non contano come assenze. Con meno di 3 partite utili ogni quota è tirata verso 0,5 (per l'ultima partita da sola: 0,75 se ha preso voto, 0,25 se no); senza nessuna è 0,3.

Le quattro quote entrano in una regressione logistica (con un termine in più per i portieri, perché il titolare gioca quasi sempre e la riserva quasi mai). Prima, p era la sola quota delle presenze recenti: chi aveva giocato le ultime 6 partite riceveva «98%» e poi prendeva voto 86 volte su 100. I pesi sono stimati SOLO sul 2025-26 (giornate 5-38) e provati sul 2026-27 (giornate 2-8), senza guardare il futuro: nella fascia «90-100%» si passa da 98,9% detto e 86,6% giocato a 90,8% detto e 91,1% giocato; l'errore medio di calibrazione passa da 6,7 a 4,1 punti percentuali (da 8,4 a 2,6 tra i giocatori ancora nella squadra). p va da circa 6% a circa 93%.

Se la squadra gioca in coppa europea entro 3 giorni, la probabilità si moltiplica per 0,93 (turnover). Le date delle coppe sono scritte a mano nel codice (6 squadre, fino al 28/01/2027) e vanno aggiornate: dopo quella data il turnover non si calcola più. Quando ci sono le probabili, il turnover lo dicono già loro.

Una volta giocate le giornate, l'app confronta le percentuali delle probabili con chi ha davvero preso voto, per gruppi (titolare 90-100%, titolare 70-89%, panchina 20-49% e così via). Se almeno 3 giornate e almeno 30 giocatori per gruppo mostrano uno scarto, corregge le percentuali di quel gruppo, ma di poco: il fattore è osservati/previsti, pesato n / (n + 60) e mai oltre il 15% in più o in meno.

Formula:

```
presenze = Σ (0,75^distanza × [ha preso voto]) / Σ 0,75^distanza, sulle ultime 6 partite
z = -2,681 + 1,058 × presenze + 1,5 × presenze_lunghe + 0,772 × da_titolare + 2,122 × ultima
    (portieri: + (-0,909 + 1,221 × presenze))
p = 1 / (1 + e^(-z))
correzione di un gruppo = 1 + (osservati/previsti - 1) × n/(n + 60), tra 0,85 e 1,15
```

> **Esempio di calcolo** (esempio di calcolo). Tre partite: ha preso voto nelle due più recenti ma non nella più vecchia. Pesi 0,5625 (più vecchia), 0,75, 1,0: presenze = (0,75 + 1,0) / 2,3125 = 76%. Thuram alla giornata 8 del 2026-27: presenze 1,0, presenze lunghe 0,81, da titolare 0,83, ultima 0,75: z = -2,681 + 1,058 + 1,212 + 0,642 + 1,592 = 1,82 e p = 86%. Con n = 30 giocatori in un gruppo e osservati/previsti = 1,20 la correzione è 1 + 0,20 × 30/90 = 1,07.

Nell'app: Stato dei dati > Calibrazione delle probabili.

Codice: `fanta/modello.py:_presenze_recenti_varie`, `fanta/modello.py:p_senza_probabili`, `prove/calibra_p_voto.py`, `fanta/coppe.py:fattore_turnover`, `fanta/coppe.py:COPPE`, `fanta/stato_dati.py:calibrazione`, `fanta/stato_dati.py:fattori_da`

## 12. Come si sceglie la formazione  [base]

Per ogni modulo ammesso dalla tua lega il sistema compone i migliori undici e poi prova a migliorarli scambiando un titolare con i migliori esclusi dello stesso ruolo, finché non trova più vantaggi. Alla fine sceglie il modulo con il punteggio migliore.

«Migliore» non vuol dire solo punti attesi più alti: a parità (entro 0,2-0,3 punti) vince la formazione con i titolari più sicuri, cioè con meno rischio di una brutta giornata. Tutte le formazioni sono confrontate sulle stesse simulazioni, per un confronto leale.

Ogni modulo ha la sua formazione migliore, e puoi vederli tutti nell'app con i punti attesi.

Nell'app: Formazione; Oggi.

Codice: `fanta/formazione.py:migliore`, `fanta/consigli.py:_calcola_formazione`

## 13. La simulazione delle sostituzioni  [nerd]

I punti attesi di una formazione non sono la somma dei punti attesi degli undici, perché un titolare senza voto viene sostituito dalla panchina e conta come la lega decide. Per tenerne conto si fanno 600 giornate simulate (300 nelle verifiche sul passato, 200 nel controllo automatico dell'app). In ogni simulazione ogni giocatore prende voto con la sua probabilità p, in modo indipendente dagli altri, con un seme fisso (7) così il risultato è ripetibile.

In ogni simulazione si applicano le regole della lega: chi manca viene sostituito dal primo della panchina, nell'ordine, che ha preso voto e dello stesso ruolo. Se la lega ammette il cambio modulo, può entrare anche uno di un altro ruolo, ma solo se il modulo risultante è ammesso (la scelta è tra chi è disponibile, e con la panchina «per ruolo» prima si prova lo stesso ruolo). I cambi sono al massimo quelli consentiti dalla lega; i portieri si cambiano solo con portieri; un titolare senza sostituto vale zero, o il voto d'ufficio se la lega lo prevede.

Il modificatore difesa si calcola in ogni simulazione: se in campo ci sono portiere e almeno 4 difensori con voto, si fa la media del voto del portiere e dei 3 migliori difensori e si dà il bonus della soglia più alta raggiunta. Servono voti e non solo medie, perché il bonus va a scalini: a ogni voto in pagella atteso si somma un rumore casuale con deviazione 0,6.

Si prende la media sulle simulazioni (punti attesi), la deviazione standard e il 10° e il 90° percentile (brutta giornata e giornata eccezionale).

Formula:

```
punteggio simulato = Σ fantavoto di chi va a punteggio (titolari con voto + riserve entrate) + (scoperti × voto d'ufficio) + modificatore difesa
punti attesi = media dei punteggi simulati
```

> **Modificatore difesa con le soglie della lega di prova** (numeri veri del modello). Portiere 6,5 e difensori 6,5, 6,5, 6,0 e 6,0: media di portiere e 3 migliori = (6,5 + 6,5 + 6,5 + 6,0) / 4 = 6,375, che supera la soglia 6,25 ma non 6,5: bonus +1,5. Le soglie della lega sono 6 = +1, 6,25 = +1,5, 6,5 = +2, 6,75 = +2,5, 7 = +3, 7,25 = +3,5.

Codice: `fanta/formazione.py:Valutatore`, `fanta/formazione.py:chi_va_a_punteggio`, `fanta/formazione.py:Valutatore._sostituzioni`, `fanta/formazione.py:Valutatore._difesa`, `fanta/formazione.py:SCARTO_VOTO`, `fanta/punteggio.py:modificatore_difesa`, `fanta/affidabilita.py:calcola`

## 14. La panchina: per ruolo o libera  [nerd]

Se la lega fissa i posti di panchina per ruolo (per esempio 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti), il sistema porta in panchina i migliori di ogni ruolo per punti attesi, tanti quanti sono i posti. Altrimenti prende i migliori non titolari, con almeno un portiere se c'è.

L'ordine conta perché il primo disponibile entra per primo: con la panchina «per ruolo» le riserve sono ordinate per ruolo e poi per valore, con la «libera» per valore. Provare criteri diversi per scegliere la panchina non ha dato motivi per cambiare quello attuale.

Codice: `fanta/formazione.py:_panchina`, `fanta/regole.py:Panchina`, `docs/STILI.md`

## 15. Gli stili: preset di rischio e di modulo  [base]

Uno stile è un modo di scegliere: dal «Molto sicura» al «Molto rischiosa», passando per «Equilibrata», che è la consigliata. Cambia due cose insieme. Il profilo dei giocatori: quanto pesa evitare la brutta giornata o inseguire la giornata eccezionale. E la preferenza di modulo: gli stili sicuri premiano le difese più folte, quelli rischiosi un attaccante in più.

Gli stili cambiano il carattere della scelta, non fanno magicamente guadagnare punti: nella misura del 30/10/2026 sulle rose della lega, nessuno stile (tranne il «Molto sicura», che costa circa un punto a giornata) si distingue dall'«Equilibrata» oltre il rumore di misura.

Formula:

```
punteggio di scelta = punti attesi - peso_giù × (punti attesi - brutta giornata) + peso_su × (giornata eccezionale - punti attesi)
+ inclinazione modulo: punti per ogni difensore e per ogni attaccante oltre il 4-x-3
```

> **Equilibrata con numeri di esempio** (esempio di calcolo). Peso 0,15: una formazione con 70 punti attesi e brutta giornata a 64 (10° percentile) vale 70 - 0,15 × 6 = 69,1 per la scelta. Una da 69,7 con brutta giornata a 67 vale 69,7 - 0,15 × 2,7 = 69,3 e passa avanti.

Nell'app: Formazione > Stile.

Codice: `fanta/formazione.py:LIVELLI_RISCHIO`, `fanta/formazione.py:Valutatore.scelta`, `fanta/formazione.py:migliore`, `docs/STILI.md`

## 16. Gli stili alla prova  [nerd]

Pesi usati: Molto sicura (1,5 giù / 0 su, inclinazione 0,5 punti per difensore), Sicura (0,6 / 0, 0,5), Equilibrata (0,15 / 0, 0), Rischiosa (0 / 0,25, 0,5 per attaccante), Molto rischiosa (0 / 0,5, 0,5).

Misura del 30/10/2026 (76 casi squadra-giornata, 100 simulazioni): Equilibrata 69,29 punti a giornata. Sicura +0,09 (errore standard 0,09), Sicura con inclinazione sui difensori +0,18, Molto sicura -0,96 (0,44), Rischiosa +0,32 (0,31), Molto rischiosa +0,26 (0,32). Sotto circa ±0,3 con questo campione è rumore.

Letture oneste: spostare il modulo non costa punti oltre il rumore; il vantaggio dei preset è nel profilo, non nei punti medi; con la qualità attuale dei dati il 4-3-3 resta il modulo più scelto da tutti gli stili. Da rimisurare quando l'archivio avrà più giornate.

Codice: `fanta/formazione.py:LIVELLI_RISCHIO`, `docs/STILI.md`

## 17. Come si valuta uno scambio  [base]

Uno scambio conviene a una squadra se fa crescere il valore della sua rosa. Il valore di una rosa è la somma dei punti attesi della sua formazione migliore nelle prossime 5 giornate (una per una, con calendario e probabili) più il resto della stagione, che conta la metà perché le rose e le gerarchie cambiano.

L'app calcola lo scambio per te e per l'altra squadra: una proposta è «buona» solo se guadagnano tutte e due almeno mezzo punto in stagione. Il verdetto dice a parole se conviene a te, a lui, a entrambi o a nessuno, e se le rose restano valide (massimo per ruolo e abbastanza giocatori per schierare un modulo).

Nell'app: Scambi.

Codice: `fanta/scambi.py:analizza`, `fanta/scambi.py:totale`, `fanta/scambi_multi.py:_verdetto`, `fanta/scambi_multi.py:problemi_rosa`

## 18. Scambi: il conto, la stima veloce e le proposte  [nerd]

Per cercare tra migliaia di scambi non si può simulare ogni volta, quindi il valore di una giornata usa una stima veloce: per ogni modulo ammesso si prendono i migliori per p × mu di ogni ruolo; le riserve dello stesso ruolo entrano in ordine, e la j-esima riserva vale solo se mancano almeno j titolari di quel ruolo (calcolato con le probabilità di assenza, tutte indipendenti), fino al numero di posti di panchina di quel ruolo. Niente limite di cambi e niente modificatore difesa: è un'approssimazione.

Per le giornate dopo la prima la probabilità è metà presenze recenti e metà presenze su 20 partite. Chi è infortunato oggi manca anche la giornata dopo; poi rientra con una stima basata su quante volte parte titolare. Chi è squalificato manca solo la giornata in corso.

Il guadagno di una squadra è la differenza tra il valore con e senza lo scambio. Le proposte 1 contro 1 sono tutte le coppie dello stesso ruolo (o di ruoli diversi se le rose hanno posto) in cui entrambe guadagnano almeno 0,5 punti; si ordinano per il guadagno mio più metà del più piccolo dei due guadagni, e ogni giocatore compare al massimo due volte.

Formula:

```
valore rosa = Σ(5 giornate) punti attesi + 0,5 × giornate rimanenti × media dei punti attesi delle giornate lontane
guadagno = valore con lo scambio - valore senza
proposta buona se guadagno_mio ≥ 0,5 e guadagno_loro ≥ 0,5
```

> **Esempio di calcolo** (esempio di calcolo). Se lo scambio vale in tutto +2,0 punti nelle prime 5 giornate e +0,6 punti a giornata in quelle lontane, e restano 25 giornate da giocare, il guadagno è 2,0 + 0,5 × 25 × 0,6 = 9,5 punti in stagione.

Codice: `fanta/scambi.py:valore_giornata`, `fanta/scambi.py:_almeno`, `fanta/scambi.py:valori`, `fanta/scambi.py:totale`, `fanta/scambi.py:proponi`, `fanta/scambi.py:ORIZZONTE`, `fanta/scambi.py:SOGLIA`, `fanta/scambi.py:PESO_RESTO`

## 19. Scambi N contro M (da 1 a 4 giocatori per lato)  [nerd]

L'analisi di uno scambio qualunque (fino a 4 giocatori per parte, anche 3 contro 2) usa gli stessi conti, ma controlla che le rose dopo lo scambio restino valide: non oltre il massimo di ogni ruolo e con abbastanza giocatori per un modulo. Se non lo sono, lo scambio si analizza lo stesso e ti dice il motivo; se un ruolo supera il massimo, chi ha troppi giocatori libera i meno forti prima di valutare.

Cercare in automatico tutti i 2 contro 2, 3 contro 2 e simili è enorme, quindi c'è un budget di calcolo: si stima l'effetto di ogni giocatore da solo, per lato si tengono i più promettenti (7-9 giocatori in tutto, al massimo 4 per ruolo), le combinazioni si provano dalla più promettente e ci si ferma dopo 1500 calcoli completi per squadra avversaria. Il tempo è solo una rete di sicurezza, così il risultato non cambia da una volta all'altra. Le proposte che sono un 1 contro 1 con dei «riempitivi» in più si scartano, perché la versione semplice è già nell'elenco.

Limite da sapere: nelle ricerche grandi si guardano solo i candidati migliori, quindi uno scambio buono ma con giocatori poco promettenti da soli può sfuggire.

Codice: `fanta/scambi_multi.py:analizza_completo`, `fanta/scambi_multi.py:cerca_grandi`, `fanta/scambi_multi.py:_riempitivo`, `fanta/scambi_multi.py:problemi_rosa`, `fanta/scambi_multi.py:POOL_PER_LATO`, `fanta/scambi_multi.py:MAX_VALUTAZIONI`

## 20. Conguagli in crediti  [nerd]

Uno scambio può includere crediti (positivi se li ricevi, negativi se li paghi). L'app controlla che chi paga li abbia, secondo i crediti residui salvati in Lega, e che nessuno superi il limite di 100.000.

Per dare un valore in punti ai crediti, usa il mercato degli svincolati della squadra: somma i guadagni in punti delle sue migliori mosse e li divide per quanto costano (quotazione di chi entra meno il rimborso di chi esce). Il risultato è un tasso: punti attesi in stagione per ogni credito. Il valore dei crediti scambiati è conguaglio × tasso, e il giudizio finale usa il guadagno netto. Senza tasso (nessuna mossa utile) i crediti si mostrano ma non entrano nel giudizio.

È una stima grossolana: dipende da quali svincolati ci sono oggi.

Formula:

```
tasso = Σ guadagno delle mosse utili / Σ (quotazione di chi entra - rimborso)
netto = guadagno in punti + conguaglio × tasso
```

Nell'app: Scambi > Conguaglio; Lega > Crediti.

Codice: `fanta/scambi_multi.py:tasso_da_mercato`, `fanta/scambi_multi.py:controlla_conguaglio`, `fanta/scambi_multi.py:analizza_completo`

## 21. Svincoli e rimborso  [base]

Il mercato propone di svincolare un tuo giocatore per prenderne uno libero dello stesso ruolo, se la tua rosa ne guadagna almeno mezzo punto in stagione. Se hai inserito i crediti, vengono considerati solo gli svincolati che puoi permetterti: i tuoi crediti più il rimborso di chi esce, che per ipotesi è la metà del prezzo pagato (regola della lega, modificabile).

Quanto resta nei crediti dopo il cambio si calcola così: crediti + rimborso - quotazione di chi entra.

Formula:

```
rimborso = prezzo pagato × 0,5 (parametro della lega)
crediti dopo = crediti + rimborso - quotazione di chi entra
```

Nell'app: Mercato.

Codice: `fanta/gestione.py:mercato`, `fanta/regole.py:Regole.rimborso_svincolo`

## 22. Asta e riparazione  [nerd]

L'asta è una versione di base, per orientarsi e non per garantire prezzi. Il metodo è il classico «valore sopra il sostituto»: si stimano i punti di stagione di ogni giocatore (giornate × media di p × mu), si toglie il livello del primo giocatore che non farebbe il titolare in nessuna squadra (10 portieri, 40 difensori, 40 centrocampisti e 30 attaccanti per una lega da 10 squadre) e si divide il budget della lega in proporzione a quello che resta. Il 12% del budget è lasciato alla panchina.

La riparazione (di febbraio) è la stessa idea ma solo tra gli svincolati: il prezzo di ognuno è la sua parte dei crediti che restano alla lega, in proporzione a quanto vale sopra l'ultimo svincolato che troverebbe posto. I posti da riempire sono quelli che mancano nelle rose; se sono piene si ipotizza che ogni squadra cambi 3 giocatori. Senza i crediti inseriti, come prezzo di riferimento si usa la quotazione.

In asta contano anche la fretta e le mosse degli avversari: questi prezzi non lo sanno.

Formula:

```
valore sopra il sostituto = max(0, punti di stagione - punti del sostituto del ruolo)
prezzo = budget spendibile × valore sopra il sostituto / somma dei valori
```

Nell'app: Mercato.

Codice: `fanta/asta.py:piano`, `fanta/asta.py:piano_riparazione`, `fanta/asta.py:POSTI_CHE_CONTANO`, `fanta/asta.py:QUOTA_PANCHINA`

## 23. Quanto è affidabile? La prova sul passato  [base]

Per sapere se il modello vale qualcosa lo si rifà girare sulle giornate già giocate, giornata per giornata, dandogli soltanto ciò che si sapeva prima di ognuna. Poi si confronta con quello che è successo e con una scelta semplice «da fantamedia» (chi ha la media più alta).

Il 30/10/2026, su 41 giornate e 10 rose: il modello sbaglia il fantavoto di chi gioca di circa 1,46 punti (errore tipico). Una stima «da fantamedia» sbaglia di più: 1,50 contro 1,43 del modello nel 2025-26 e 1,84 contro 1,61 nel 2026-27. La formazione consigliata ha fatto 68,6 punti a giornata contro un massimo possibile col senno di poi di 71,8.

Si legge così: il modello batte la scelta semplice, ma di poco sui punti della formazione (qualche decimo, che con un campione piccolo non si distingue dal caso) e con più margine sull'errore del fantavoto. Il margine con il massimo possibile esiste anche perché nessuno conosce in anticipo chi segna.

Numeri misurati (2026-10-30): Giornate provate: **41** giornate; Casi squadra-giornata con rosa sufficiente (almeno 20 giocatori presenti): **93** casi; Errore del modello sul fantavoto di chi ha giocato (radice dell'errore quadratico medio): **1,46** punti; Errore del modello, stagione 2025-26 (34 giornate): **1,43** punti; Errore di una stima «da fantamedia», stagione 2025-26: **1,5** punti; Errore del modello, stagione 2026-27 (7 giornate): **1,61** punti; Errore di una stima «da fantamedia», stagione 2026-27: **1,84** punti; Punteggio di Brier delle probabilità di giocare (0 = perfetto, 0,25 = dire sempre 50%): **0,157**; Punti veri a giornata con la formazione consigliata: **68,6** punti; Massimo possibile col senno di poi (stessa rosa, stessi giorni): **71,8** punti; Punti con la consigliata, 2025-26: **67,1** punti; Punti scegliendo da fantamedia, 2025-26: **66,5** punti; Massimo possibile, 2025-26: **69,0** punti; Punti con la consigliata, 2026-27: **71,9** punti; Punti scegliendo da fantamedia, 2026-27: **71,3** punti; Massimo possibile, 2026-27: **77,9** punti; App: errore del modello nelle ultime 8 giornate: **1,6** punti; App: errore da fantamedia nelle ultime 8 giornate: **1,82** punti; App: punti con la consigliata nelle ultime 8 giornate: **71,7** punti; App: punti da fantamedia nelle ultime 8 giornate: **70,6** punti; App: massimo possibile nelle ultime 8 giornate: **77,8** punti

Nell'app: Stato dei dati (numeri aggiornati dell'app); Diario.

Codice: `fanta/verifica.py:verifica`, `fanta/verifica.py:verifica_giornata`, `fanta/affidabilita.py:calcola`, `fanta/affidabilita.py:sintesi`

## 24. Le misure: errore, Brier e punti  [nerd]

Errore sul fantavoto: per chi ha davvero preso voto si confronta il mu previsto con il fantavoto vero calcolato con le regole della lega. La misura principale è la radice della media dei quadrati degli errori (RMSE), perché il mu è un valore medio e gli errori grandi pesano di più; si riporta anche l'errore assoluto medio (0,93 nel 2025-26, 1,03 nel 2026-27). Il confronto è con un'ipotetica scelta «da fantamedia»: la media dei fantavoti della stagione, 6 se non ha voti.

Brier delle presenze: media dei quadrati della differenza tra la probabilità di giocare prevista (0-1) e quello che è successo (1 ha preso voto, 0 no). 0 è perfetto; dire sempre 50% darebbe 0,25. Nella prova passata vale 0,157 (0,161 nel 2025-26, 0,140 nel 2026-27).

Punti delle formazioni: per ogni rosa della lega e ogni giornata si scelgono due formazioni, la consigliata e quella «da fantamedia» (stesse probabilità di giocare, mu sostituito dalla fantamedia: il confronto misura quindi la qualità del mu, non della p). Si calcolano i punti veri con le sostituzioni reali. La «perfetta» è il massimo col senno di poi: i migliori fantavoti veri nel modulo migliore, senza modificatore difesa. È un tetto teorico che nessuno può toccare.

Attenzione a due cose. Nelle giornate passate non abbiamo le probabili formazioni, quindi la p è ricavata dalle presenze recenti: nella prova il modello è più debole che dal vivo. E le rose sono quelle di oggi applicate al passato: contano solo le rose che in quella giornata hanno almeno 20 giocatori presenti (93 casi su 410 possibili, quindi molti meno di quanti sembrerebbero).

Formula:

```
RMSE = radice( media( (mu previsto - fantavoto vero)^2 ) )
Brier = media( (p prevista - preso voto)^2 )
```

Numeri misurati (2026-10-30): Errore del modello sul fantavoto di chi ha giocato (radice dell'errore quadratico medio): **1,46** punti; Punteggio di Brier delle probabilità di giocare (0 = perfetto, 0,25 = dire sempre 50%): **0,157**

Codice: `fanta/verifica.py:verifica_giornata`, `fanta/verifica.py:_fantamedia`, `fanta/verifica.py:_perfetta`, `fanta/verifica.py:MIN_GIOCATORI_ROSA`, `fanta/affidabilita.py:sintesi`

## 25. L'esperimento «oracolo»: quanto vale sapere in anticipo  [nerd]

L'oracolo è una misura, non una funzione dell'app: si dà al modello, una cosa alla volta, la conoscenza perfetta di quello che nella realtà non si sa prima della partita, e si vede di quanto salgono i punti. Serve a decidere se vale la pena cercare una fonte nuova: se il guadagno massimo è sotto 0,3 punti a giornata, la lacuna non lo merita.

Misura del 30/10/2026 (41 giornate, 10 rose, punti a giornata per rosa rispetto a 68,56 della base): sapere chi prende voto vale +0,68; sapere i gol veri della squadra vale +1,35 (e l'errore sul fantavoto scende da 1,46 a 1,30); sapere il rigorista vero vale +0,02, cioè niente; tutte e tre insieme +2,50 (71,06 contro un massimo di 71,76).

Lettura onesta: sono tetti, non promesse. Le formazioni ufficiali escono circa un'ora prima della partita, dopo il termine per schierare, quindi il guadagno ottenibile sulle presenze è solo quanto si riesce a prevederle meglio (più redazioni, notizie su infortuni e squalifiche, storico). Per i gol della squadra, invece, il guadagno può venire da una seconda misura di forza. I rigoristi non meritano una fonte dedicata.

Numeri misurati (2026-10-30): Guadagno se si sapesse in anticipo chi prende voto: **0,68** punti a giornata; Guadagno se si sapessero i gol veri della squadra: **1,35** punti a giornata; Guadagno se si sapesse il rigorista vero: **0,02** punti a giornata; Guadagno sapendo tutte e tre le cose insieme: **2,5** punti a giornata; Soglia sotto la quale una lacuna non vale una fonte nuova: **0,3** punti a giornata; Errore sul fantavoto sapendo i gol veri della squadra (invece di 1,46): **1,3** punti

Codice: `fanta/verifica.py:guadagno_oracoli`, `fanta/verifica.py:dati_oracolo`, `fanta/verifica.py:ORACOLI`, `fanta/modello.py:previsioni`, `docs/archivio/PIANO-DATI.md`, `docs/archivio/PIANO-FONTI.md`

## 26. Il diario: la tua scelta contro la consigliata  [base]

Per ogni giornata finita il diario mette a confronto la formazione che hai schierato e quella che il sistema avrebbe consigliato, con i punti attesi e quelli fatti. Il sistema rifà la scelta con i soli dati che c'erano prima della giornata, ma con la rosa di oggi (le rose passate non si conservano), e la panchina è quella scelta dal sistema anche per la tua.

Con poche giornate è solo un racconto: l'oscillazione dei punti è molto più grande della differenza tra le due scelte.

Nell'app: Diario.

Codice: `fanta/diario.py:calcola_giornata`, `fanta/diario.py:sintesi`

## 27. Da dove arrivano i dati e ogni quanto  [base]

Fantacalcio.it: listone dei calciatori (una volta al giorno), calendario, voti delle giornate (quelle giocate che mancano più quelle finite da meno di 4 giorni, perché le correzioni arrivano dopo) e probabili formazioni (a ogni aggiornamento).

Understat: xG, xA, tiri, minuti e rigori calciati, partita per partita (totali a ogni aggiornamento, dettaglio delle partite giocate che mancano). È l'unica fonte di queste statistiche: se sparisse, ci sarebbe un piano B a pagamento ancora da decidere.

football-data.co.uk: solo le statistiche di squadra (xG, tiri, angoli, cartellini) per le partite giocate e per le prossime (al massimo ogni 6 ore), conservate in ombra.

Sul server l'aggiornamento è programmato alle 8, 13, 17 e 21 di ogni giorno. Le richieste sono educate: una alla volta, almeno un secondo di pausa, fino a 3 tentativi, e non si riscarica quello che c'è già. I dati si possono sempre ricostruire da capo.

Le coppe europee (per il turnover) sono date inserite a mano e vanno aggiornate.

Nell'app: Stato dei dati.

Codice: `fanta/aggiorna.py:Aggiornamento`, `fanta/rete.py:scarica`, `fanta/fonti/fantacalcio.py`, `fanta/fonti/understat.py`, `fanta/fonti/footballdata.py`, `script/server/aggiorna.sh`, `fanta/coppe.py:COPPE`

## 28. Dati puliti: nomi, controlli e rischi delle fonti  [nerd]

Il codice calciatore di Fantacalcio.it è la chiave di tutto. Le altre fonti scrivono i nomi in modo diverso («Laurientè», «Lauriente», «Esposito Se.», «N'Dicka»): un modulo di riconoscimento toglie accenti, punti e apostrofi e abbina per squadra e somiglianza. Gli abbinamenti sicuri (stessa squadra) restano, quelli per somiglianza si rifanno ogni volta: sono i punti dove un errore si nasconde meglio.

Dopo ogni aggiornamento girano controlli di coerenza: 10 partite per giornata, almeno 180 voti per giornata finita, somma degli xG dei giocatori vicina a quella della partita (scarto massimo 1), 11 titolari per squadra. Fino al 2% di righe fuori misura è rumore delle fonti, oltre è un avviso, e tutto si vede in Stato dei dati.

Rischio onesto: Understat è l'unica fonte di xG, xA e rigori e Fantacalcio.it quella di voti e probabili. I loro termini non sono pensati per un uso da programma: per uso personale il rischio è basso, ma va ripensato prima di aprire l'app a molte persone (permessi, fonti alternative).

Nell'app: Stato dei dati > Controlli.

Codice: `fanta/nomi.py:normalizza`, `fanta/fonti/understat.py`, `fanta/controlli.py:esegui`, `docs/archivio/PIANO-DATI.md`

## 29. Fonti in modalità ombra e come si promuovono  [nerd]

«In ombra» vuol dire: il dato viene raccolto e conservato, ma il modello non lo legge. Serve a capire, con una misura, se varrebbe qualcosa prima di fidarsene. Oggi le fonti in ombra sono due: le colonne in più di football-data.co.uk (xG di squadra, tiri, tiri in porta) e una seconda fonte di probabili formazioni.

Le prove si lanciano con verifica --fonti (una variante: xG di squadra di football-data al posto di quello di Understat; più la seconda fonte di probabili).

Regola di promozione: una fonte entra nel modello solo se l'errore sui voti scende almeno dello 0,5% e il miglioramento c'è in almeno 2 delle ultime 3 stagioni misurate. Per il piano dati servono anche un miglioramento del Brier delle presenze dell'1% e, sui punti delle formazioni, +0,3 a giornata su almeno 100 giornate. Con una sola stagione di dati il risultato è «solo indicativo», non si promuove. La decisione la prende una persona guardando i numeri: il modello non cambia da solo.

Stato al 30/10/2026: nessuna fonte è stata promossa. Sul computer di sviluppo la tabella delle colonne extra è vuota (0 partite con il dato nuovo), quindi la prova dice «niente da misurare»; i conteggi veri della raccolta stanno sul server e si leggono in Stato dei dati.

Nell'app: Stato dei dati > Fonti in ombra.

Codice: `fanta/verifica_fonti.py:giudizio`, `fanta/verifica_fonti.py:SOGLIA_ERRORE`, `fanta/verifica_fonti.py:dati_con_variante`, `fanta/stato_dati.py:ombra`, `docs/archivio/PIANO-DATI.md`, `docs/archivio/PIANO-FONTI.md`

## 30. Gli avatar: volti inventati dal codice  [nerd]

I volti illustrati non sono foto e non somigliano a nessuno di preciso: sono generati dal codice calciatore. Lo stesso codice dà sempre lo stesso volto, su web, iPhone e Android, perché ogni piattaforma usa lo stesso generatore di numeri pseudo-casuali (mulberry32, a 32 bit) con lo stesso seme: codice calciatore × 0x9E3779B1, in XOR con 0xA5C1D1CE.

Con quel seme si fanno dieci estrazioni sempre nello stesso ordine (pelle, forma del viso, acconciatura, colore dei capelli, barba, sopracciglia, occhi, bocca, accessorio, orecchie), ognuna con pesi che rendono le combinazioni comuni più frequenti. Le combinazioni possibili sono 2.903.040. Qualche regola evita abbinamenti strani (per esempio niente orecchino con capelli lunghi, afro od ondulati). Colori della maglia e dello sfondo vengono dai colori della squadra; i portieri hanno maglia grigia e guanti.

Per dare un po' di aria al giocatore vero, per chi ha un ritaglio già scaricato (circa 260 su 600 no) si usano tre tratti grossolani calcolati una volta sola e salvati in un file: colore dei capelli, famiglia di acconciatura (rasata, corta, lunga, riccia) e barba sì/no. Nessuna foto resta nell'app né nel repository.

La specifica completa, con vettori di prova uguali per tutte le piattaforme, è in docs/AVATAR.md: un test controlla che il generatore dia sempre gli stessi indici.

Formula:

```
seme = (codice × 0x9E3779B1) XOR 0xA5C1D1CE (32 bit)
scelta con pesi: n = floor(estrazione × somma dei pesi), si scorrono le parti sommando i pesi
```

Codice: `docs/AVATAR.md`, `fanta/avatar.py:di`, `fanta/web/avatar.js`

## 31. La tecnologia in breve  [base]

Il cervello è in Python (pandas e numpy per i conti). Il server è FastAPI; l'archivio dei dati scaricati è un database SQLite in un file solo, che si può ricostruire da capo, mentre le tue cose (regole, rose, scelte, osservati, impostazioni) sono file JSON piccoli scritti in modo sicuro (prima su un file temporaneo, poi rinominato, così un guasto a metà non rovina quello vecchio).

L'app web è una PWA (si installa sul telefono) fatta con HTML, CSS e JavaScript senza librerie né compilazione. L'app per iPhone è nativa, in SwiftUI; quella per Android è in Jetpack Compose con Material 3 (a uno stadio iniziale). Tutte parlano con lo stesso server: i testi e i numeri di questa pagina sono uguali ovunque.

Il server può girare su un computer piccolo e economico. L'app si aggiorna da sola: ogni 10 minuti il server controlla GitHub, installa la versione nuova, riavvia il servizio, verifica che risponda e, se no, torna alla versione di prima. I test sono automatici (pytest, su GitHub a ogni modifica).

Gli avvisi sul telefono (formazione pronta, cambi nelle probabili, riepilogo di giornata) rispettano le «ore tranquille» che imposti.

Nell'app: Novità.

Codice: `requirements.txt`, `fanta/server.py`, `fanta/percorsi.py:scrivi_sicuro`, `script/server/aggiorna-app.sh`, `script/server/fantacalcio.service`, `fanta/notifiche.py`, `android/README.md`

## 32. Backup e sicurezza in breve  [nerd]

Il backup è un file solo con regole, rose, movimenti, scelte, osservati e impostazioni degli avvisi. Non contiene chiavi né iscrizioni alle notifiche. Ripristinando, tutto viene controllato prima e lo stato di prima viene salvato in un file di sicurezza. Sul server c'è anche una copia notturna (le ultime 7).

Ogni richiesta che modifica qualcosa deve avere un'intestazione speciale dell'app, altrimenti è rifiutata: protegge dai siti che provano a far scrivere al tuo browser. Le risorse personali usano un controllo di versione (ETag e If-Match): se due dispositivi modificano la stessa cosa insieme, il secondo viene avvisato invece di sovrascrivere.

Con più utenti attivi: password salvate con scrypt (parametri costosi, circa mezzo secondo e 64 MB per controllo), sessioni, limiti di tentativi e di uso per utente e per indirizzo, file Excel letti in un processo separato. Ogni utente ha la sua cartella e non può vedere quella degli altri. Questa modalità è spenta di default.

Chiavi e segreti restano nelle cartelle del server e mai in git, nei registri o nelle richieste.

Codice: `fanta/backup.py`, `fanta/server.py`, `fanta/versioni.py`, `fanta/account.py:COSTO`, `fanta/importa_sicuro.py`, `script/server/backup-serale.sh`

## 33. I limiti onesti: cosa il modello non sa fare  [base]

Non sa chi gioca davvero: le formazioni ufficiali escono troppo tardi, e finché non ci sono si affida alle probabili formazioni di una sola fonte. Un'assenza all'ultimo minuto fa sbagliare la scelta, e la panchina serve proprio a questo.

Non conosce il singolo duello (quel difensore contro quell'attaccante), il meteo, l'arbitro, le motivazioni, chi tira i calci piazzati (a parte i rigori), la posizione reale in campo, la durata esatta degli infortuni (conta solo l'infortunio di oggi e la giornata dopo), né quanto un'assenza di un compagno apra spazi. I trasferimenti in corsa entrano solo con le poche partite già giocate e con la quotazione.

Il fantacalcio è dominato dal caso: un gol vale 3 punti e capita raramente. Anche un ottimo modello sbaglia di circa 1,5 punti su un singolo giocatore. Nel 2026-27, per la consigliata, la differenza tra punti fatti e attesi ha oscillato in media di circa 6 punti da una giornata all'altra: per questo accanto ai punti attesi l'app non scrive un «± piccolo» ma una fascia «tra X e Y, 8 volte su 10», larga circa 16 punti (da −8 a +8,5 attorno ai punti attesi), calibrata proprio su questi scarti.

Scegliere bene aumenta la probabilità di fare punti, non la garantisce: contro le giornate storte non c'è formazione che regga.

Numeri misurati (2026-10-30): Scarto tipico tra punti fatti e attesi della consigliata (8 giornate del 2026-27): **5,9** punti; Deviazione dello scarto tra punti fatti e attesi (913 casi, 41 giornate): **6,7** punti; Larghezza della fascia «8 volte su 10» con una dev_simulata di 2 (da −8,0 a +8,5): **16,5** punti; Quota dei punti veri dentro la fascia, obiettivo 80%: **80% (76% sulle rose della lega)**

Codice: `fanta/formazione.py:Valutatore`, `fanta/scambi.py:GIORNATE_INFORTUNIO`, `fanta/diario.py:elenco`

## 34. Limiti tecnici e rischi di sovradattamento  [nerd]

La simulazione da sola è troppo ottimista: rende casuali solo chi prende voto e il rumore del voto per il modificatore difesa, mentre gol, assist e voti di chi gioca restano al loro valore atteso. La sua deviazione (dev_simulata, in media 1,6 punti sui 913 casi provati) serve a confrontare due formazioni ma non a stimare il rischio: lo scarto vero tra punti fatti e attesi ha una deviazione di 6,7 punti, con il 10° e il 90° percentile a −7,9 e +8,3. Per questo la fascia «tra X e Y» che vedi è calibrata sul backtest: scarto tipico = radice(6,47² + dev_simulata²); basso = atteso − 1,18 × scarto tipico; alto = atteso + 1,25 × scarto tipico. Con una dev_simulata di 2 va da −8,0 a +8,5 punti attorno all'atteso, larga circa 16,5, con confidenza dichiarata 0,8 (8 volte su 10). Copertura misurata: 80% sui 913 casi (93 rose della lega e 820 rose estratte a sorte, 41 giornate), 76% sulle sole rose della lega, 74% se la fascia è tarata sulle rose a sorte e provata su quelle della lega, 78% e 80% se è tarata su una stagione e provata sull'altra (rispetto al 24% della vecchia fascia ±1,28 × dev_simulata). Sulle rose della lega lo scarto è un po' più grande (circa 8 contro 6,5): finché i loro casi sono meno di 200 la fascia è segnata «indicativa». La fascia è quasi uguale per ogni formazione: oggi il modello non sa dire quale sia più «sicura» (una parte che cresce con i bonus attesi è stata provata e tolta, correlazione con lo scarto circa 0). Per scegliere tra due formazioni va bene lo stesso, perché il confronto è identico per entrambe.

Le simulazioni trattano le presenze come indipendenti tra i giocatori: ma quando una squadra fa turnover, o c'è un'influenza nello spogliatoio, escono insieme. Il modello dei gol è una Poisson per squadra, indipendente tra le due squadre; il tasso della singola partita viene dalla forza delle squadre e non ha una variabilità propria.

I campioni sono piccoli: 41 giornate in tutto e solo 8 della stagione in corso; i casi con le rose sufficienti sono 93. Differenze di 0,3 punti a giornata sono rumore. La stima del guadagno degli stili e degli oracoli ha un errore standard che in alcuni casi supera il guadagno.

Il rischio più grave nel migliorare un modello è il sovradattamento (overfitting): ritoccare parametri finché i numeri sul passato migliorano, adattandosi al caso e non a un fenomeno vero. I parametri attuali sono tarati su una stagione (2025-26, giornate 5-38) e controllati su un'altra (2026-27). Per questo ogni modifica si prova con verifica prima e dopo; una fonte nuova entra solo se vince in almeno due stagioni e oltre una soglia; e nessun numero qui sopra va letto come una promessa.

Alcune costanti sono scelte a mano e non misurate: la conversione dei rigori (78%), il 20% di rigori parati, i minuti tipici di titolare (78) e di chi entra (22), la probabilità che un titolare mancante entri comunque (0,6), il 4% di voto mancante, il fattore turnover (0,93). Sono ragionevoli ma andrebbero riconfermate con più dati.

Numeri misurati (2026-10-30): Scarto tipico tra punti fatti e attesi della consigliata (8 giornate del 2026-27): **5,9** punti; Deviazione dello scarto tra punti fatti e attesi (913 casi, 41 giornate): **6,7** punti; Larghezza della fascia «8 volte su 10» con una dev_simulata di 2 (da −8,0 a +8,5): **16,5** punti; Quota dei punti veri dentro la fascia, obiettivo 80%: **80% (76% sulle rose della lega)**

Codice: `fanta/formazione.py:Valutatore`, `fanta/formazione.py:SCARTO_VOTO`, `fanta/modello.py:Parametri`, `fanta/modello.py:MINUTI_TITOLARE`, `fanta/modello.py:P_SUBENTRO_TITOLARE`, `fanta/modello.py:P_SENZA_VOTO`, `fanta/coppe.py:FATTORE_TURNOVER`, `fanta/diario.py:calcola_giornata`

## Glossario

- **Fantavoto**: Il punteggio di un giocatore in una giornata: voto in pagella più bonus e malus (gol, assist, cartellini, porta inviolata...) con le regole della tua lega.
- **Fantavoto atteso**: Il fantavoto che SchieraXI si aspetta da un giocatore in una partita, SE gioca, con le regole della tua lega: avversario, casa o trasferta, rendimento, rigori, bonus e malus. Sta sempre accanto a «gioca N%». Per la formazione intera si parla di punti attesi.
- **mu**: Il fantavoto atteso, in formula: il fantavoto che il modello si aspetta SE il giocatore prende voto.
- **p (probabilità di prendere voto)**: Quanto è probabile che il giocatore entri in campo abbastanza da avere un voto. I punti attesi sono p × mu.
- **xG (gol attesi)**: Per ogni tiro, la probabilità che sia gol in base a posizione e tipo di tiro; sommata dà i «gol che la squadra o il giocatore avrebbe dovuto fare». xA fa lo stesso per l'ultimo passaggio.
- **Poisson**: Distribuzione degli eventi rari e indipendenti (come i gol): da un numero medio di eventi dà la probabilità di 0, 1, 2... eventi. Con media m, P(zero) = e^-m.
- **Porta inviolata (clean sheet)**: Partita senza gol subiti. Dà un bonus al portiere nella tua lega.
- **Decadimento**: Peso che scende per le partite più vecchie (0,92 per ogni giornata): rende la stima sensibile alla forma recente.
- **Restringimento (shrinkage)**: Mescolare una stima con una stima di partenza (la media del ruolo o quella legata alla quotazione): evita che pochi dati diano valori esagerati.
- **Quotazione iniziale**: Prezzo del giocatore a inizio stagione, fissato prima del campionato: riassume le attese degli esperti e serve da punto di partenza per i giocatori con poche partite.
- **Voto in pagella atteso**: La parte del fantavoto atteso che viene dal voto, senza bonus e malus.
- **Fantamedia**: Media dei fantavoti di un giocatore. È la scelta semplice con cui si confronta il modello.
- **Simulazione (Monte Carlo)**: Ripetere centinaia di volte una giornata finta, estraendo a sorte chi gioca, per vedere la media e la variabilità dei punti.
- **Percentile**: Il 10° percentile è il valore sotto cui cade il 10% delle giornate simulate (brutta giornata); il 90° è quello sopra cui sta il 10% (giornata eccezionale).
- **Modificatore difesa**: Bonus di squadra che dipende dalla media del voto del portiere e dei tre migliori difensori, a scalini decisi dalla lega.
- **Panchina libera / per ruolo**: Libera: il primo della panchina che può entrare. Per ruolo: prima chi è dello stesso ruolo del titolare mancante.
- **Voto d'ufficio**: Voto dato dalla lega a un titolare senza voto e senza sostituto, se previsto.
- **Stile**: Preset di scelta della formazione: da Molto sicura a Molto rischiosa.
- **Conguaglio**: Crediti pagati o ricevuti in uno scambio per compensare la differenza di valore.
- **Rimborso allo svincolo**: Quota del prezzo pagato che si riavrebbe svincolando un giocatore (metà, per ipotesi della lega).
- **Valore sopra il sostituto**: Punti di un giocatore meno quelli di un sostituto di livello basso del suo ruolo: misura quanto vale davvero in asta.
- **Backtest**: Rifare i conti su giornate passate usando solo ciò che si sapeva prima di ognuna, per misurare quanto avrebbe funzionato.
- **RMSE**: Radice dell'errore quadratico medio: l'errore tipico di una stima, con più peso agli errori grandi.
- **Brier**: Errore delle probabilità: media dei quadrati tra probabilità prevista e risultato (0 o 1). Più basso è meglio.
- **Calibrazione**: Se tra i giocatori a cui si dà il 70% di giocare, davvero circa il 70% gioca.
- **Oracolo**: Esperimento: dare al modello una verità del futuro per misurare quanto varrebbe saperla in anticipo.
- **Fonte in ombra**: Dato raccolto ma non ancora usato dal modello, finché una misura non dimostra che serve.
- **Promozione**: Il passaggio di una fonte dall'ombra al modello: serve un miglioramento dell'errore di almeno lo 0,5% in almeno 2 stagioni su 3.
- **Sovradattamento (overfitting)**: Un modello troppo ritoccato sul passato che va bene su quei dati e peggio sul futuro.
- **Turnover**: Far riposare i titolari, tipico a ridosso delle coppe.
- **mulberry32**: Un piccolo generatore di numeri pseudo-casuali: dallo stesso seme dà sempre la stessa sequenza. Serve per gli avatar.
- **PWA**: Applicazione web che si installa sul telefono come un'app, senza passare dallo store.
- **ETag / If-Match**: Un'etichetta di versione di una risorsa: permette al server di accorgersi che due dispositivi stanno modificando la stessa cosa.
