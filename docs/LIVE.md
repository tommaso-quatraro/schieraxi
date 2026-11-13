# Risultati in diretta (Oggi > Partite del turno)

Provato il 30/10/2026 con poche richieste dirette (pausa >= 1 s, User-Agent onesto `schieraxi-personale/1.0`). **[verificato]** = visto con una richiesta; **[non verificato]** = non provabile oggi (nessuna partita in corso al momento delle prove) o di seconda mano.

## Fonti provate

| Fonte | Esito | Pro | Contro |
|---|---|---|---|
| **ESPN** `site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard?dates=AAAAMMGG` (JSON pubblico non ufficiale, senza chiave) | 200, 5-40 kB, 0,2 s [verificato] | punteggio, stato (`STATUS_SCHEDULED`, `FIRST_HALF`, `HALFTIME`, `SECOND_HALF`, `FULL_TIME`, `POSTPONED`, ...), minuto (`displayClock`, es. `90'+3'`), **marcatori con minuto**, rigori, autogol, **gialli e rossi con giocatore**, tutto nella stessa chiamata (`details`) [verificato su partite finite del 24-25/10]. Una chiamata copre un giorno intero di partite. Niente account | Non ufficiale: può cambiare forma o chiudere senza avviso. `dates=A-B` (intervallo) dà 400: si chiede un giorno alla volta. Senza `dates` mostra solo il prossimo giorno di gioco. I nomi dei minuti/stati *durante* la partita non si sono potuti vedere dal vivo [non verificato] (i valori sono quelli noti della stessa API per altri campionati). Non si sa a quale squadra assegni un autogol: il codice sceglie il lato per cui i conti tornano con il punteggio. Il `robots.txt` del dominio API non si può leggere (403); quello di `www.espn.com` elenca bot di addestramento AI, non il nostro uso [letto solo l'inizio]. Condizioni d'uso non lette [da verificare]: per questo uso personale e poche richieste |
| **football-data.org v4** `/competitions/SA/matches?status=LIVE` | 403 «restricted» senza chiave [verificato]; serve registrarsi | API ufficiale, documentata, stabile | Serve un account (NON creato); il piano gratuito dà risultati ma con ritardo e senza marcatori dettagliati nel piano base [da verificare]; 10 richieste/minuto |
| **Fantacalcio.it** `/serie-a/calendario/<giornata>` (già usata dal progetto) | 200, 260 kB di HTML [verificato] | nessuna fonte in più, abbinamento squadre già pronto (slug), `data-match-status` = 0 (da giocare) o 4 (finita) [verificato] | HTML da leggere (fragile); **nessun minuto né marcatori**; gli stati «in corso» e la freschezza del punteggio durante la partita non si sono potuti vedere [non verificato]; pagina grossa. `robots.txt` non vieta il calendario |
| openfootball / Wikipedia | scartate | | non sono in diretta |

## Scelta

- **Principale: ESPN.** Unica fonte gratuita senza account con minuto, marcatori e cartellini.
- **Ripiego: calendario di Fantacalcio.it**, solo punteggio e stato. Entra dopo 3 errori di fila della principale e dura 10 minuti, poi si riprova ESPN. Il campo `fonte` della risposta dice quale dei due ha riempito la cache.
- Se ESPN sparisse del tutto, la funzione degrada a «punteggio senza minuto» (ripiego) e, senza nemmeno quello, a calendario e risultati finali dal database come prima.

## Latenza e frequenza

- ESPN aggiorna il punteggio in genere entro pochi secondi o un minuto da quanto accade [non misurato]. Con 1 richiesta al minuto il ritardo massimo nostro è ~1 minuto, più la cache del telefono (20 s).
- Un solo raccoglitore nel servizio (thread `live`), cache in memoria condivisa: 1 utente o 100 utenti = le stesse richieste. Le schede aperte leggono solo `GET /api/live` (mai richieste esterne).
- Si lavora solo nelle finestre di gioco (da 10 minuti prima del calcio d'inizio a 20 minuti dopo la fine stimata, 110 minuti dall'inizio); le partite segnate «finita» o «rinviata» non si interrogano più (eccezione: una «rinviata» che il calendario rimette a una data la cui finestra si apre dopo l'ultima lettura si segue di nuovo, e se la data è cambiata la voce vecchia esce dalla cache, #661). Un sabato con 4 partite ravvicinate = circa 4-6 ore di finestra = al massimo 1 richiesta al minuto = 240-360 richieste. Fuori finestra: zero.
- Partita che a fine finestra la fonte non dà ancora per finita (inizio in ritardo, recuperi lunghi): si continua a seguirla, una richiesta ogni 5 minuti, finché la fonte dice «finita» o il calendario la dà per giocata, al massimo fino a 4 ore dal calcio d'inizio.
- Dopo le partite il servizio rilegge risultati e voti della giornata (due pagine di Fantacalcio.it) 2 ore e 30 dopo ogni orario di calcio d'inizio, e una seconda volta 4 ore dopo solo se manca ancora qualcosa (`pianificatore.giro_risultati`). Così la partita «finita» e i punti fatti arrivano la sera stessa. L'esito del giro sta nella riga `risultati-rapido` di `aggiornamenti`, come un passo seguito: un giro fallito si vede in Stato dei dati («Risultati la sera stessa») e nella salute, con una riga nel registro.
- Errori: pausa che raddoppia (1, 2, 4, ... fino a 10 minuti); mai due richieste a meno di un minuto l'una dall'altra, qualunque fonte.

## Rischi

- Blocco o cambio di forma di ESPN: il lettore salta le partite che non capisce e la cache resta quella di prima; una risposta senza nessuna delle partite seguite (forma cambiata o elenco vuoto) conta come errore, non aggiorna l'ora né la fonte, e dopo 3 errori il ripiego prende il posto. Ogni lettura non riuscita lascia una riga nel registro del servizio con il nome della fonte. Nessun errore arriva all'utente.
- Termini d'uso: uso personale, frequenza bassa, nessuna ridistribuzione dei dati oltre agli utenti dell'app. Se l'app diventasse pubblica/commerciale, la fonte va rivista (football-data.org o un provider con licenza).
- Nomi squadra non riconosciuti: la partita non compare dal vivo e resta quella del database.
- Memoria: la cache è un dizionario di al massimo qualche decina di partite (2 giorni).
- Riavvii: la cache si salva anche in `dati/live.json` (dopo ogni lettura riuscita, al massimo una volta al minuto, scrittura atomica) e si rilegge all'avvio. Prima (1/11/2026) un riavvio dopo la fine della partita faceva sparire il risultato fino al giro di aggiornamento del mattino. Il file si rigenera da solo: non va nel backup. Formato (lo leggono anche i controlli sui dati):

```
{"versione": 1, "aggiornato": "2026-11-01T22:50:07", "fonte": "espn" | "fantacalcio" | null,
 "partite": {"juventus|napoli": {casa, trasferta, data, stato, minuto, gol_casa, gol_trasferta, eventi,   // come in /api/live
                                 "visto": "2026-11-01T22:50:07"}}}   // quando la fonte ha dato questa partita l'ultima volta
```
Le ore sono italiane, senza fuso. Chi legge ignora i campi che non conosce; file mancante o rotto = cache vuota.

## Contratto di `GET /api/live` (per web, iOS, Android)

Risposta comune a tutti gli utenti (sola lettura), < 8 kB, `ETag` (con `If-None-Match` risponde 304) e `Cache-Control: private, max-age=20`. Si può chiamare anche con il token del widget (`Authorization: Bearer fw_...`).

```
{"aggiornato_il": "2026-10-31 15:20:04" | null,   // ora italiana dell'ultima raccolta riuscita
 "fonte": "espn" | "fantacalcio" | null,
 "in_corso": 2,                                     // quante partite sono in gioco ora
 "partite": [{"casa": "inter", "trasferta": "fiorentina",   // slug di Fantacalcio.it, come in /api/oggi
              "data": "2026-10-31 15:00",
              "stato": "da_giocare|primo_tempo|intervallo|secondo_tempo|in_corso|finita|rinviata|sospesa",
              "minuto": "34'" | "90'+3'" | null,    // solo primo/secondo tempo e in_corso
              "gol_casa": 1, "gol_trasferta": 0,    // null se da giocare e senza dati
              "eventi": [{"tipo": "gol|rigore|autogol|rigore_sbagliato|rosso", "minuto": "10'", "squadra": "casa|trasferta", "chi": "M. Thuram",
                          "assist": "Dimarco"}]}]}   // assist: facoltativo, solo su gol e rigore, solo se la fonte lo dà
```

- Dal 31/10/2026 i cartellini gialli NON sono più nella risposta (`giallo` non esiste più) e non c'è nessun troncamento «altri N» sul server: arrivano tutti gli eventi (tetto 20 per partita). I client vecchi che si aspettano `giallo` semplicemente non ne ricevono. `rosso` vale anche per la doppia ammonizione. `rigore_sbagliato` (parato o fuori) è nuovo: i client che non lo conoscono lo ignorano. Il tetto della risposta è 8 kB (in casi estremi si tolgono prima gli `assist`).
- Client: una riga per evento, due colonne (casa a sinistra, trasferta a destra): `6' Varela (rig.)`, `33' Pobega (ass. Ferguson)`, `58' Lucchesi` con il simbolo del rosso; autogol `70' Rui (autogol)`; mai «e altri N».
- [non verificato] ESPN, nei dati provati, dà un solo nome per evento: l'`assist` compare solo se la fonte aggiunge un secondo nome; il `rigore_sbagliato` si riconosce da `penaltyKick` senza `scoringPlay`.

- `partite` = le partite della giornata mostrata in Oggi (stato dal database se la fonte live non le ha ancora viste: se il calendario non la segna ancora giocata, lo stato viene dall'orario come in Oggi, cioè `da_giocare` prima del calcio d'inizio, `in_corso` per 110 minuti, poi `finita` con `gol_casa`/`gol_trasferta` null finché il calendario non scrive il risultato) più eventuali partite in corso fuori turno (recuperi). Un client sconosciuto deve ignorare stati e tipi nuovi (trattare «stato sconosciuto» come `in_corso` se ha un punteggio).
- Le partite si abbinano per `casa` + `trasferta`.
- Quando il calendario dà una partita per giocata, vincono il suo stato («finita») e il suo punteggio; i marcatori visti in diretta restano solo se il punteggio è lo stesso.
- `GET /api/oggi` ha il campo nuovo `miei_titolari`: `{"inter": [{"id": 123, "nome": "Sommer", "ruolo": "P"}], ...}` = i miei titolari consigliati per squadra (per evidenziare le partite). `GET /api/widget` ha il campo `live` (stessa forma, senza gialli e al più 8 eventi per partita).
- Frequenza consigliata ai client: ogni 30-60 s solo con la schermata visibile e `in_corso > 0`; altrimenti una lettura all'apertura. Se `in_corso == 0` e nessuna partita sta per iniziare, non serve richiedere di nuovo.
- Variabile del servizio `FANTA_LIVE=0` spegne il raccoglitore (la rotta risponde comunque, dal database).
