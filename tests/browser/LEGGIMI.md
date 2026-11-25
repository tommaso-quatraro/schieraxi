# Test della web nel browser

Qui la web si prova in Chrome vero, senza finestra: pochi test di **comportamento** (cosa succede nella pagina), che
reggono a un rifacimento della grafica. Non cercano stringhe nel codice di `fanta/web/`.

La web si apre sul server finto di `script/ci/server_finto.py` (solo libreria standard, lo stesso della regressione
visiva): serve `fanta/web/` e risponde alle `/api/...` con le risposte registrate di `ios/fotografie/` (nomi inventati).
Niente server vero, niente rete, nessun segreto. Ogni test che usa la fixture `web` gira **tre volte**, una per fase della
giornata:

| fase | scenario | momento |
|---|---|---|
| `prima` | `vero-prima.json` | qualche ora prima della scadenza, con una formazione salvata |
| `in-corso` | `vero-in-corso.json` | giornata a metà, partite in corso |
| `finita` | `vero-finita.json` | giornata finita, voti usciti |

L'orologio della pagina è fermo sul momento dello scenario (`adesso`), in italiano e con l'ora italiana; ogni test parte
da una scheda nuova (nessun dato salvato da un test prima).

## Tre patti con ogni versione della web
I test non conoscono le schermate: si appoggiano a tre regole che ogni versione della web rispetta.
- **Il contenuto della schermata sta nell'area principale**: `<main>` (o un elemento con `role="main"`). Una schermata
  con l'area principale vuota è rotta, anche se la testata c'è.
- **Mentre una schermata carica, l'area principale (o il suo contenitore del caricamento) ha `aria-busy="true"`**, e lo
  toglie quando ha finito. I test aspettano al massimo 10 secondi che nell'area principale non ci sia più nessun
  `aria-busy="true"`, poi falliscono («ferma sul caricamento»). La web lo mette dal 12/11/2026 (#615): sull'area principale
  con `caricamento()` di `app.js` (lo toglie la `pagina()` che arriva dopo, anche quella di un errore) e sui riquadri che si
  riempiono dopo. Il controllo guarda ancora anche le classi `caricamento` e `scheletro` (la rotella e le righe grigie).
- **Un errore mostrato all'utente ha `role="alert"`** (lo legge subito anche chi usa un lettore di schermo); un avviso
  normale ha `role="status"`. Un elemento `role="alert"` con del testo, visibile nell'area principale, fa fallire i test
  della prima schermata. La web di oggi scrive gli errori anche con la classe `errore`, che vale lo stesso. Un contenitore
  `role="alert"` vuoto, pronto per un messaggio, va bene.

Gli avvisi stanno in una regione `role="status"` che resta in pagina, e ci vengono scritti dopo (un lettore di schermo non
legge una regione che nasce già con il suo testo): così il riconoscimento delle rose (#615) e, dal 12/11/2026 (#618), la
schermata di accesso, dove prima anche gli avvisi (classe `attenzione`) stavano in un `role="alert"`; gli errori dell'accesso
hanno il loro `role="alert"`. Il controllo non conta ancora come errori gli elementi con la classe `attenzione`.

## Quando girano
- **Nelle pull request**: job `browser` dei controlli (`.github/workflows/test.yml`), quando la PR tocca `fanta/web/`,
  `fanta/testi/`, `tests/browser/`, `tests/strumenti/axe/`, `ios/fotografie/`, `script/ci/server_finto.py`,
  `.github/browser-requisiti.txt` o `test.yml` (anche spostando un file da lì). Blocca l'unione: `unisci` lo aspetta e
  lo vuole riuscito (se la PR non tocca la web il job salta i passi e resta verde). Il job ha un tetto di 10 minuti: i test
  girano in 4 processi (`pytest-xdist`, `-n 4 --dist worksteal`, #680), ognuno con il suo Chrome e i suoi server finti, e
  il registro del job elenca i dieci test più lenti (`--durations=10`).
- **A mano su un ramo**: `gh workflow run test.yml --ref <ramo>` (girano tutti i controlli, questo compreso).
- **Su `main` dopo un'unione** (#630): nella corsa lanciata da `prova-main`, se dall'ultima corsa verde su `main` sono
  cambiati gli stessi file (lo decide il job `cambi`; se non si sa, girano). Se falliscono, `main-rosso` apre o commenta
  l'issue P1 «CI: main rosso».
- **Nella suite normale no**: senza `-m browser` si saltano. Si saltano anche se mancano Playwright o Chrome; nel job dei
  controlli (variabile `BROWSER_OBBLIGATORIO=1`) invece falliscono, perché lì un test saltato sarebbe un verde finto.

## In locale
Playwright e pytest stanno in un ambiente a parte, **mai** nel `.venv` del progetto né nel Python di sistema. Nessun
browser da scaricare: si usa Chrome già installato. Una volta sola (Windows):

```
py -3.13 -m venv <cartella-temporanea>\pw-test
<cartella-temporanea>\pw-test\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r .github\browser-requisiti.txt
```

Poi, dalla radice del repository (anche da una worktree), circa un minuto:

```
<cartella-temporanea>\pw-test\Scripts\python.exe -m pytest -q -m browser --confcutdir tests/browser tests/browser
```

`--confcutdir tests/browser` serve: senza, pytest carica anche `tests/conftest.py`, che vuole le librerie dell'app
(errore `No module named 'requests'`). Su macOS e Linux il Python è `<cartella>/pw-test/bin/python`.

## Cosa controllano oggi
`test_prima_schermata.py`, in ognuna delle tre fasi, a 390 e 1440 px, tema chiaro e scuro:
- la prima schermata ha del testo nell'area principale, non è ferma sul caricamento (`aria-busy`), non mostra errori
  (`role="alert"`) e non scrive errori nella console (né errori del codice);
- nessuna richiesta fallita (risposta 4xx o 5xx, o richiesta che non arriva; una richiesta annullata non conta);
- a 390 px la pagina non è più larga dello schermo (niente scorrimento di lato);
- nessuna violazione grave (`critical` o `serious`) di axe, regole WCAG 2.0, 2.1 e 2.2 livelli A e AA
  (`tests/strumenti/axe/`).

`test_tagli.py`, la web senza le funzioni tolte il 12/11/2026 (#615). I test che non dipendono dalla fase girano solo
prima della scadenza:
- Impostazioni ha solo le voci che restano (dal #618 Squadra e Altro sono Impostazioni); gli indirizzi delle pagine tolte
  aprono Impostazioni; le novità stanno in Impostazioni > Informazioni (le ultime dieci, le altre a richiesta); «Nuova
  stagione» è un avviso che compare quando serve; la dimensione del testo salvata da una versione di prima non vale più;
- Formazione senza stili, legenda, confronto e indice sui volti, e senza partite del turno e banner, nelle tre fasi;
  girando per l'app non si chiedono le rotte delle funzioni tolte;
- le decisioni in cima alla Formazione: via i consigli di mercato e di scambio; la riga del reparto scoperto resta e
  porta alla rosa;
- i patti: una schermata che non si apre mostra un errore `role="alert"` e non resta in caricamento; le schermate sane
  non ne hanno; mentre una schermata carica `<main>` ha `aria-busy="true"`; nel riconoscimento delle rose gli avvisi
  arrivano in una regione `role="status"` già in pagina e un salvataggio fallito è un errore.

`test_formazione_unica.py`, la schermata «Formazione» che ha preso il posto di Oggi e Formazione (#616):
- nelle tre fasi, a 390×844 px, i nomi degli 11 stanno nel primo schermo; il vecchio indirizzo di Oggi apre la Formazione;
- «gioca N%» si vede solo sotto l'80% e non ci sono etichette di titolarità; un tocco su un titolare apre la scheda con
  «Sostituisci»; fra i sostituti chi gioca meno dell'80% lo dice; la nota che spiega «In dubbio» si legge nella riga e
  nella scheda; un account senza rose vede il benvenuto senza richieste fallite;
- salvataggio automatico: dopo una sostituzione o un altro modulo lo stato dice «L'hai cambiata tu» e la scelta è
  salvata; «Torna alla consigliata» la toglie; la spunta «L'ho messa» resta dopo una ricarica;
- ciò che si salva è ciò che si vede: la copia mostrata subito all'apertura è di sola lettura finché non arrivano i dati
  nuovi; se non arrivano (rete caduta) la nota dice perché non si può cambiare e ha «Riprova», e quando il browser segnala
  che la rete è tornata la pagina riprova da sola, una volta; un salvataggio che torna a schermata già ridisegnata fa rileggere,
  e finché è in volo la pagina riletta ha i comandi spenti (un cambio fatto lì gli scriveva sopra); se quel salvataggio non
  riesce un avviso lo dice e i comandi si riaccendono; un salvataggio (o «Torna alla consigliata») che non riesce quando si è
  già passati a un'altra schermata lo dice lo stesso con un avviso che nomina la formazione (la rete solo se è lei il motivo,
  #667); togliere la spunta non cancella una scelta
  salvata altrove; se la scelta non si legge c'è un errore con «Riprova» e niente si può cambiare; rete caduta, rifiuto
  del server e scelta cambiata su un altro dispositivo lasciano in pagina ciò che è salvato e lo dicono; dopo un 412 i
  comandi restano spenti finché la pagina non ha riletto dal server (l'avviso dice prima «Sto ricaricando…», poi di rifare
  la modifica), e una scrittura sulla scelta porta sempre If-Match, anche dopo un 412 su altri dati;
- tastiera: dopo il menu del modulo, la spunta, «Sostituisci» e «Torna alla consigliata» il fuoco resta su un comando;
- al massimo due decisioni, solo quelle con un'azione: prima le urgenti (fra loro prima quelle con un'azione vera), poi
  le altre; il reparto scoperto non ne prende più di una; «Usa la consigliata» prende quella nuova;
- quando il cambio non si può fare: chi gioca una partita già cominciata non ha «Sostituisci» e la scheda dice perché;
  un ritorno alla consigliata rifiutato lascia la formazione com'è e lo dice un avviso (`role="status"`); se la scadenza
  passa con la pagina aperta la schermata si rilegge;
- a giornata in corso i punti finora e niente da cambiare; a giornata finita «Com'è andata», i recuperi che mancano e la
  scelta sul rinvio, con sotto la formazione della prossima;
- tablet e PC: campo a sinistra e panchina a destra a 768, 1024 e 1440 px; sul PC la scheda nel pannello a fianco, che
  si chiude se cambia il modulo; scheda ed elenco dei sostituti senza violazioni gravi di axe, chiaro e scuro; i pulsanti
  spenti sulla copia («Sostituisci», «Torna alla consigliata») si accendono già pieni quando arrivano i dati nuovi, mai mezzi
  trasparenti (#697: axe lanciato in quell'istante trovava un contrasto troppo basso).

`test_metti_in_campo_scheda.py`, «Metti in campo» dalla scheda di un giocatore che non è fra gli 11 (#643). Gli scenari registrati non
hanno ancora la rotta `POST /api/formazione/metti-in-campo`: la risposta la dà il test con `web.risposta`, costruita sulla
formazione registrata (finché non li si registra di nuovo, la web la chiama solo al tocco sul pulsante):
- dalla scheda di un panchinaro «Metti in campo» chiede al server chi può uscire (con gli 11 in pagina), l'elenco ha la
  differenza dei punti attesi della formazione, «gioca N%» per chi gioca meno dell'80% e, se il modulo cambia, il modulo nuovo
  («Si passa al 5-3-2»); un tocco cambia il campo, lo stato dice «L'hai cambiata tu», la scelta è salvata e il fuoco va su chi è
  entrato; con un cambio di modulo il campo e il menu del modulo passano a quello nuovo;
- se la rotta non risponde la scheda ha un errore `role="alert"` e niente cambia; se il server dice che la sua partita è già
  cominciata (`giocatore_bloccato`) la scheda dice la sua frase come informazione (`role="status"`); se la scheda si chiude prima della risposta,
  resta chiusa; se il salvataggio trova la scelta cambiata da un altro dispositivo (412, con If-Match) la pagina rilegge, mostra
  ciò che è salvato e l'avviso lo dice; scheda ed elenco senza violazioni gravi di axe, chiaro e scuro;
- il pulsante c'è dove c'è «Sostituisci» per la stessa formazione: anche a giornata finita (per la prossima) e per chi entra a
  giornata iniziata; anche per infortunati e squalificati, con il loro stato in cima all'elenco. Non c'è per i titolari (che
  hanno «Sostituisci»), per chi gioca un anticipo già cominciato (la scheda dice perché), né a giornata in corso.

`test_fasi_giornata.py`, la giornata in corso e quella finita ai bordi (#895), con la risposta registrata di /api/oggi (o di
/api/giocatore) cambiata solo nel pezzo che serve:
- in corso: il voto d'ufficio di una partita rinviata sta nel disco con «Voto d'ufficio» (anche per il lettore di schermo);
  sotto i punti la frase del server (`in_corso.situazione`); chi è rimasto senza voto ed è già sostituito ha la lineetta e non
  il suo atteso; in panchina la colonna si chiama «Fantavoto» e chi deve ancora giocare dice «atteso» (prima della scadenza
  resta «Fantavoto atteso»);
- finita: la scelta sul rinvio sta in testa, sopra il campo e la panchina della giornata dopo, con il titolo «Giornata N · Nª di
  Serie A: partita rinviata», la partita e i miei giocatori, e un menu solo; senza voti la testa dice che la giornata è finita
  e la frase del server (`voti_in_arrivo`);
- prima: nella scheda l'andamento è quello del server (`andamento`), anche se i voti direbbero altro.

`test_giornate.py`, la pagina «Giornate» che ha preso il posto del Diario (#617):
- si apre con un tocco dalla barra; gli indirizzi vecchi del Diario la aprono; «Com'è andata» della Formazione la apre
  sulla giornata appena finita;
- in cima la riga sulla precisione, con i numeri di prima dietro «Dettagli»; una riga per giornata dalla più recente con
  punti fatti e attesi; al tocco gli 11 con fantavoto atteso (quello mostrato prima della scadenza, se c'è) e preso;
- il confronto «tu contro la consigliata» solo dove `consigliata.origine` è `"mostrata"`: con la risposta del server di
  oggi (campo assente) non c'è, con quella del server con #614 c'è solo nelle giornate giuste (risposte finte costruite
  su quella registrata);
- la frase sulla consigliata di allora che non entra nel confronto è quella del server (`nota_consigliata`, #674: anche
  «c'è chi non è più nella tua rosa»), sotto la tua formazione o sopra la consigliata rifatta; senza la frase, nessuna nota;
- la riga dice di quanto i punti sono sopra o sotto gli attesi con il numero del server (`fatti_e_attesi.differenza`, #672:
  «+9,2 sul previsto», «come previsto» a zero, niente senza il campo); nel dettaglio, a 390 e 1440 px, la frase del server su
  chi ha fatto meglio o peggio del previsto, e nessuna frase se sono tutti come previsto;
- un solo pulsante di correzione, che fa scegliere gli 11 e li manda con la stagione; non c'è per una stagione passata;
- errore con «Riprova», pagina vuota che dice perché; chiaro e scuro a 390 e 1440 px senza violazioni gravi; elenco a
  sinistra e giornata a destra a 768 e 1440 px, gli 11 sotto la riga al telefono.

`test_impostazioni.py`, la barra a tre voci e le Impostazioni uniche (#618). Girano solo prima della scadenza:
- la barra ha Formazione, Giornate e Impostazioni più la ricerca, a 390 e 1440 px, e niente ingranaggio; Impostazioni si apre
  con un tocco e ha le sezioni Avvisi, La mia lega, Aspetto;
- un utente normale (account non amministratore) vede al massimo dieci controlli (i pulsanti di un gruppo, come il tema,
  contano una volta) e non vede Gestione, neanche con il suo indirizzo; chi gestisce il server la apre, con «Aggiorna i dati»;
- Gestione con un aggiornamento in corso (`aggiornamento_in_corso` di `/api/stato`, #763): «Aggiorna i dati» è spento con la frase
  che dice perché; con l'orologio della pagina portato avanti (`clock.fast_forward`) lo stato si rilegge ogni 15-20 secondi, una
  lettura alla volta (una lettura ferma non ne fa partire altre), e a campo falso il pulsante si riaccende e la frase sparisce;
  entrando in Gestione con il campo già vero (letto all'avvio) lo stato si rilegge subito; fuori da Gestione niente letture;
  «già in corso» dopo il tocco resta un avviso;
- ogni indirizzo di prima apre la voce giusta e l'indirizzo diventa quello nuovo: Squadra, Altro, Lega, Mercato, Scambi,
  i gruppi delle Impostazioni (Avvisi, Aspetto, Avanzate, Informazioni, Account), le voci (Aggiorna le rose, Squadre e
  rose, Regole, Novità), la rosa mia e di un'altra squadra; una scheda salvata da una versione di prima (Squadra, Altro,
  Oggi...) apre la Formazione; Indietro e «‹ Impostazioni» tornano dove si era;
- La mia lega porta alla mia squadra (con «Stemma e maglia» e «Non è la tua squadra?») e alle altre; senza le rose degli altri
  «Le altre squadre» non c'è; il numero della riga «Le altre squadre» e il suo elenco non contano la mia (finché non è scelta,
  tutte; con la sola mia squadra, aperta dal suo indirizzo, dice che c'è solo la mia); senza costo d'acquisto la riga di un giocatore non scrive «costo –» (un costo 0 sì) e senza immagini non restano le
  parole «Stemma» e «Maglia» (#779); «Nuova stagione» compare lì quando serve; «Stemma e maglia» della rosa apre il foglio sulla
  squadra della pagina, con «Rimuovi» (che cancella l'immagine giusta) e «Da indirizzo web»;
- Regole e scadenza: il regolamento incollato si salva con «Salva queste regole»; i singoli valori stanno dietro «Modifica i
  valori»; la scadenza si salva appena cambia; la frase sulla prima giornata parla di Giornate, non del Diario, e scelta la 6ª
  non cita un'altra giornata (#779);
- conflitto (412) su Regole (la scadenza) e rose (i crediti della mia squadra), con un server finto che dà l'ETag: l'avviso lo
  dice e la pagina si ricarica; la modifica rifatta prima della ricarica porta l'If-Match vecchio ed è rifiutata ancora, mai
  senza If-Match; rifatta dopo porta l'ETag riletto e passa (#667);
- Avvisi: niente interruttori di prima, le ore tranquille con la loro fascia, e un cambio manda solo `silenzio`. Senza un
  service worker registrato (il browser di prova) la frase che lo dice arriva subito, senza i 4 secondi di attesa; con una
  registrazione finta in attivazione il riquadro dice «Controllo gli avvisi…» con `aria-busy` e la riga sotto non si sposta
  quando arriva la frase. Con le notifiche finte (service worker e permesso simulati nella pagina, rotte `/api/push/...` e
  `/api/avvisi/prova` con risposte finte): la frase dell'interruttore dice che arrivano anche gli altri avvisi; accenderlo
  manda un avviso di prova e lo dice; se la prova non parte (429 o `inviato: false`) lo dice un avviso `role="status"` e
  l'interruttore resta acceso; con il permesso negato niente prova;
- Il tuo account: «Esci da tutti i dispositivi» chiede conferma con una frase che dice che si esce ovunque, anche da qui, e che si
  dovrà rientrare (e, solo a chi ha Google collegato e una password, che il collegamento con Google si toglie); confermato
  manda la richiesta e torna alla pagina d'accesso senza copie dei dati né account nel browser, con un avviso (`role="status"`)
  che dice che si è fuori da tutti i dispositivi, una volta sola e non dopo un «Esci» normale (#779);
  annullato non manda niente; se la richiesta non riesce (errore del server o rete giù) lo dice un avviso, si resta nella pagina
  e le copie restano (#765);
- Il tuo account, «Esci» (#800): se la richiesta non riesce (500, 502 o rete giù) lo dice un avviso (`role="status"`), la pagina
  non si ricarica, le copie restano e l'iscrizione agli avvisi del browser resta, e torna al server (che l'aveva già tolta);
  riuscito, l'iscrizione si toglie dal server e dal browser e si torna all'accesso senza copie. Con un'iscrizione già nel browser
  (finta, in `localStorage`, che regge alla ricarica: `ISCRIZIONE_GIA_QUI`): dopo un nuovo accesso con la password l'iscrizione
  torna al server una volta, senza chiedere il permesso; riaprendo l'app già dentro non si rimanda; se il server non la prende
  (429) si riprova all'apertura dopo, e poi basta;
- di chi è l'iscrizione (#804): accesa da un account, dopo il suo nuovo accesso torna al server; fatta da un altro account
  non si rimanda e «Avvisi su questo dispositivo» è spento finché il nuovo utente non lo accende (allora è sua);
  un'iscrizione senza numero (versione di prima) dopo un accesso nuovo resta spenta anche alle aperture dopo e non si rimanda;
  con la sessione già aperta prima diventa di chi è dentro e si rimanda una volta; «Esci» con 401 esce senza l'avviso «non riesco»;
- lo stato d'avvio (#801): aperta senza rete, Impostazioni ritrova «La mia squadra» e «Le altre squadre» quando il browser dice
  che la rete è tornata (evento `online`); aperta con il server che riparte (502), la riga di stato di Giornate torna quella di
  sempre alla prima risposta buona («Riprova»);
- «Elimina l'account» (#801): con la password sbagliata (403) gli avvisi del dispositivo restano, nel browser e sul server;
  riuscita, il browser toglie la sua iscrizione;
- i pulsanti dei file (#801): «Scegli il file» di Aggiorna le rose e i due «Da file o foto» di stemma e maglia si raggiungono
  con Tab e con Invio aprono il selettore; il file scelto va al controllo delle rose o si carica come maglia;
- salvataggi lenti (#801): le Regole salvate quando si è già nella Formazione non si ridisegnano sopra di lei (risposta trattenuta
  dal test), l'avviso c'è lo stesso; la scelta sul rinvio (in `test_formazione_unica.py`) lo stesso con Giornate;
- l'immagine condivisa che il server non prende (`?condivisa=no`, #801): l'avviso è quello del catalogo, in italiano e in inglese;
- Stato dei dati scrive le etichette del server (`etichetta`); nella schermata di accesso un avviso non è un errore;
- Gestione, «Errori recenti» (amministratore e registro finti): plurali giusti, tempi con la virgola, ora italiana senza «UTC»,
  eventi con il nome del catalogo (anche un tipo scritto con il trattino, `fonte-cambiata`) e, per un tipo sconosciuto, senza
  trattini bassi (#779).

`test_primo_avvio.py`, il passo «I tempi della lega» del primo avvio (#801). Gira solo prima della scadenza:
- se la lettura delle regole non arriva, «Salva» non scrive i valori di partenza dei menu sopra quelli veri: lo dice
  (`role="alert"`), rilegge, i menu passano ai valori salvati e il tocco dopo li scrive;
- «Salva» toccato con la lettura ancora in volo la aspetta e scrive i valori veri;
- una scelta fatta prima che la lettura torni resta: si salva la scadenza scelta e la prima giornata letta.

`test_accesso_all_avvio.py`, l'avvio con gli account quando la sessione non vale più (401 da «chi sono»). Gira solo prima della
scadenza:
- le copie di un account rimaste nel browser (`localStorage` dei dati e dell'account, copie del service worker) si tolgono
  prima della schermata di accesso, come all'uscita; riaperta senza rete, la Formazione salvata non compare;
- il codice di un link d'invito resta e compare nel modulo di registrazione.

`test_ora_italiana.py`, date e conto alla rovescia nell'ora italiana con il browser su un altro fuso (#776):
- in ogni fase la Formazione con il browser a New York e a Tokyo dice le stesse cose (tutto il testo della pagina) che con il
  browser in Italia; lo stesso la pagina Giornate, che ha la riga di stato con la data dei dati;
- prima della scadenza, a Roma, New York e Tokyo: «Si chiude oggi 18:20» e «fra 3 h 10 min» (a Tokyo le 18:20 italiane sono
  il giorno dopo: resta «oggi»);
- a cavallo del cambio dell'ora (sabato sera prima dell'ultima domenica di ottobre e di marzo, scadenza la domenica): il conto
  alla rovescia conta l'ora in più o in meno;
- una partita con solo il giorno (`data_partita` «2026-11-01», ora non ancora fissata) si scrive «dom 1», mai con un'ora finta
  come «00:00».

`test_web_installata.py`, la web come app installata, con il service worker acceso (#654). Gira una volta sola, senza fasi:
- dopo un rilascio finto (ogni file della scocca dice la sua versione, `VERSIONE` di `sw.js` alzata) con `app.js` e `testi.js`
  lenti oltre i 2,5 secondi, la pagina riaperta è tutta di una versione e un testo nuovo non compare come chiave; la versione
  nuova arriva intera con «Ricarica»;
- con il proxy che risponde 502 (il servizio dietro riparte) si apre l'app salvata, non la pagina d'errore del proxy; con gli
  account (come in produzione) anche «chi sono» riceve 502: la Formazione mostra la copia salvata dell'account e, tornato il
  server, Impostazioni ha «Il tuo account» e non «Gestione»;
- senza rete Privacy, mai aperta prima, dice «Nessuna connessione» e non apre un'altra copia dell'app; l'app si apre dalla copia.

La fixture `installata` (al posto di `web`) apre un contesto di Chrome con il service worker permesso, davanti al server finto
mette `Proxy` (fa la parte di nginx, su 127.0.0.1: senza https la web registra il service worker solo lì e su localhost) e
serve una copia di `fanta/web/` (`installata.web`) da cambiare per un rilascio finto. `installata.installa()` è la prima
apertura con la rete buona, `installata.scheda(percorso)` riapre l'app in una scheda nuova; `installata.proxy.modo` vale `"ok"`,
`"502"` o `"spento"` (niente rete), `installata.proxy.lenti` ritarda i percorsi scelti e `installata.proxy.risposte` dà un
JSON fisso per un percorso (per esempio `/api/account/me` con un account) finché il modo è `"ok"`. `installata.aspetta(pagina)`
aspetta l'area principale pronta, come `web.aspetta()`.

## Aggiungere un test di comportamento (dieci righe)
Un file `tests/browser/test_<cosa>.py`. Il segno `browser` lo mette da solo `conftest.py` a ogni test di questa cartella:
non serve scriverlo.

```python
import pytest


@pytest.mark.parametrize("vista", ["formazione", "squadra"])
def test_la_vista_si_apre_pulita(web, vista):
    web.apri(f"/?vista={vista}")                     # larghezza=390, tema="chiaro" di norma
    assert web.testo_principale(), f"{web.fase}: area principale vuota"
    assert not web.errori_mostrati(), web.errori_mostrati()
    assert not web.errori_console, web.errori_console
    assert not web.richieste_fallite, web.richieste_fallite
```

Cosa offre la fixture `web`:
- `web.apri(percorso, larghezza=390, tema="chiaro")`: apre un indirizzo e aspetta che la pagina sia pronta (area
  principale con del testo e senza caricamento, al massimo 10 s; poi rete ferma, al massimo 2 s; poi DOM fermo per
  300 ms, al massimo 3 s; animazioni portate alla fine). Un'attesa scaduta non ferma il test: lo dicono i controlli dopo;
- `web.pagina`: la pagina di Playwright, per cliccare e leggere (`web.pagina.get_by_role("button", name="…").click()`);
  dopo un clic, `web.aspetta()`;
- `web.errori_console`, `web.richieste_fallite`, `web.richieste` (le `/api/...` chieste, percorso e query): liste che si
  riempiono da sole;
- `web.risposta(rotta, corpo, stato=200)`, prima di `apri` o di un clic: quella rotta risponde con `corpo` (JSON) e
  `stato` al posto della risposta registrata, per un dato che lo scenario non ha o per una rotta che fallisce.
  `web.registrata(rotta)` dà la risposta registrata come oggetto, per cambiarne un pezzo;
- `web.memoria({"chiave": "valore"})`, prima di `apri`: valori già salvati nel browser da una versione di prima;
- `web.con_fuso("America/New_York")`: un'altra scheda sulla stessa fase con il browser su quel fuso (stesso momento dello
  scenario); `web.orologio("2026-10-24T20:00:00")`, prima di `apri`: l'orologio fermo su un altro momento, in ora italiana.
  Il momento dello scenario è ora italiana e si calcola senza il fuso del browser (`istante_italiano` di `conftest.py`);
- `web.testo_principale()`, `web.in_caricamento()`, `web.errori_mostrati()`, `web.scorre_di_lato()`,
  `web.violazioni_gravi()`;
- `web.fase`: `prima`, `in-corso` o `finita` (per un test che vale per una fase sola:
  `if web.fase != "prima": pytest.skip("solo prima della scadenza")`). La scheda di Chrome si apre al primo uso di
  `web.pagina` (o di `apri`, `risposta`, `memoria`): il salto va scritto prima, così un test saltato non la apre (#680).

Regole:
- si prova un comportamento che l'utente vede, non il testo di `app.js`; gli elementi si cercano per ruolo ed etichetta
  (`get_by_role`, `get_by_label`), che sono anche ciò che legge chi usa un lettore di schermo;
- il server finto non salva niente: ogni metodo (anche un salvataggio) riceve la risposta registrata per quell'indirizzo;
- niente orologio vero e niente attese a tempo fisso: `web.aspetta()`;
- ogni test regge da solo: con `-n` i test girano in processi diversi e in un ordine qualsiasi, quindi niente dati lasciati
  da un test per quello dopo, niente file scritti fuori da `tmp_path` e niente porte fisse.

## Una rotta che manca nello scenario
Il server finto risponde 404 a una rotta che non ha registrata, e il test delle richieste fallite lo dice
(`GET /api/<rotta>: risposta 404`). Se la web chiama una rotta nuova, gli scenari si registrano di nuovo con
`prove/fotografie_dal_vero.py` (serve l'archivio dei dati: lo fa chi coordina). Se invece la registrazione la toglie
apposta (come `/api/avatar`, che viene dalle foto vere dei calciatori), la sua risposta «senza dati» del server vero va in
`RISPOSTE_IN_PIU` di `conftest.py`.

## Sono bloccanti
In `test.yml` `browser` sta nei `needs` del job `unisci`, con `needs.browser.result == 'success'` nella sua condizione.
Nelle PR il job non si salta mai (se la PR non tocca la web salta solo i passi e resta verde). Su `main` gira dopo
un'unione che tocca la web: se due pull request verdi da sole rompono insieme una schermata, `main-rosso` apre l'issue P1.
