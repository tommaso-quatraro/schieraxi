# SchieraXI: spec di prodotto

Data: 8/11/2026. Decisa dal proprietario in un brainstorming con il coordinatore.
È il documento che dice **dove va l'app**: prima di lanciare un lavoro nuovo si controlla che stia dentro questa spec.
Non sostituisce le proposte per obiettivo (`2026-11-05-statistiche-affidabili-proposta.md`,
`2026-11-05-consiglio-giusto-proposta.md`) né la spec dell'ondata 2 (`2026-11-08-ondata-2-design.md`): le mette in ordine.
Le scelte del coordinatore, che il proprietario può cambiare, sono segnate con *[scelta del coordinatore]*.

## 1. Cosa è SchieraXI
Un'app che aiuta a schierare la formazione migliore in una lega classic di Serie A, partendo da una statistica nostra:
il **fantavoto atteso**, cioè il fantavoto che ci si aspetta da un giocatore in quella partita, con le regole della lega.
Non è un'app di fantacalcio completa: poche funzioni, tutte al servizio della formazione.

Perché questa spec ora: tra il 28/10 e l'8/11 sono nati quattro obiettivi, due ondate di lavori e un centinaio di issue,
senza un documento unico che dicesse cosa conta. Il proprietario ha fermato i lanci nuovi finché non c'è.

## 2. Per chi (stagione 2026-27)
- **Il proprietario e pochi amici, su invito**, per tutta la stagione. Restano le regole già in vigore per gli account:
  inviti a tempo e un numero massimo di utenti.
- **Gli amici usano la web installata** sulla schermata Home (iPhone e Android). L'app iPhone nativa resta per il proprietario
  finché non c'è l'App Store, e resta uguale alla web (`docs/COERENZA-WEB-IPHONE.md`). Android = la web installata.
- **Il pubblico arriva dalla stagione 2027-28**, non prima: servono fonte dati con licenza, store, privacy e supporto, e le
  spese restano ferme finché non è chiuso l'obiettivo #168 (decisione del 6/11).

## 3. Il nucleo: le funzioni che contano
| Funzione | A cosa serve |
|---|---|
| **Oggi** | cosa fare prima della scadenza, com'è andata durante e dopo la giornata |
| **Formazione** | gli 11 titolari, il modulo e la panchina consigliati, con il perché in una riga; modifica a mano e salvataggio |
| **Scheda del giocatore** | fantavoto atteso, «gioca N%», fascia di incertezza, «Perché questo numero» |
| **Diario** | a giornata finita: consigliata contro schierata, quanto ci abbiamo preso |
| **Widget iPhone e avvisi** | la formazione e i cambi importanti senza aprire l'app |

Servono al nucleo e restano curati: ingresso (account, inviti, caricare le rose, regole e tempi della lega), Impostazioni,
Stato dei dati, Novità.

## 4. Funzioni congelate
**Scambi** (Trova per me, Costruisci, Valuta un'offerta), **Cambi consigliati** con gli svincolati, **risultati in diretta**,
**Calendario**. *[scelta del coordinatore]* Per la stessa regola anche Seguiti, Elenco dei giocatori, confronto tra due
giocatori, Movimenti e storico, Crediti delle squadre, Nuova stagione, la lingua inglese della web.

«Congelata» vuol dire: resta com'è, si correggono i difetti e resta uguale su web e iPhone, ma niente funzioni, rifiniture o
schermate nuove. Si può proporre di nasconderla o toglierla; non di allargarla. I lavori che cambiano tutta l'app senza
cambiare quello che si vede (per esempio i testi nel catalogo unico, #493-#497) comprendono anche le funzioni congelate,
così la fonte dei testi resta una sola *[scelta del coordinatore]*.

## 5. Cosa SchieraXI non fa
- Niente asta né riparazione, niente quote o scommesse, niente classifica o calendario della lega, niente amministrazione
  della lega («ognuno si gestisce se stesso»).
- Non schiera la squadra al posto dell'utente sul sito della lega.
- Solo lega classic di Serie A: niente Mantra, draft o altri campionati.
- Nessuna funzione nuova che non serva a schierare la formazione o a rendere più preciso il fantavoto atteso.

Fallimenti anche se «funziona»:
- un consiglio che cambia per differenze minime, o una scelta salvata dall'utente che cambia da sola (#335);
- numeri o testi diversi tra web e iPhone;
- un amico che ha bisogno del proprietario per entrare o per caricare la sua lega;
- la produzione toccata da una prova; dati veri o personali nel repository pubblico.

## 6. Come si misura che funziona
**Numero principale: la precisione del fantavoto atteso.** È l'indicatore I1 del registro delle giornate
(`fanta/registro_giornate.py`, mostrato in Stato dei dati): errore del fantavoto atteso mostrato prima della scadenza, contro
quello della fantamedia, su tutta la Serie A, in media sulle ultime 8 giornate registrate. Regge se è **almeno il 3% sotto**.
Accanto, con le soglie già decise il 5/11: I2 (calibrazione di «gioca N%») e I3 (fascia «8 volte su 10»).

Numeri secondari:
- **Consiglio** (#166): nel Diario la consigliata fa almeno i punti della schierata, in media sulle ultime 8 giornate (C1),
  e nessun titolare improbabile con un compagno di ruolo che gioca (C3).
- **App** (#167): una giornata intera senza errori e senza differenze tra web e iPhone.
- **Amici** (#168): un amico entra da solo dalla web e carica la sua lega in meno di 10 minuti *[scelta del coordinatore:
  «pochi minuti» diventa 10]*.

## 7. Ordine degli obiettivi
I `P1` (rotto o sicurezza, per esempio #481) passano sempre davanti.

1. **#167 ridotto**: solo ciò che serve a una giornata senza errori e alla prova prima degli amici.
   - testi da una fonte sola per web e iPhone: #493, #494, #495, #496, #497;
   - ambiente di prova e collaudo automatico dopo il rilascio: #510, #511, #512. La prova è già accesa sul server con l'ok
     del proprietario dell'8/11; restano l'account di collaudo e i segreti su GitHub, che crea il proprietario;
   - limiti per utente e cancellazione dell'account: #483, #514, #515, #516;
   - l'iPhone legge le risposte vere del server con i suoi modelli: #507.
2. **#168 con gli amici**: ingresso da solo dalla web installata, poi un amico vero che prova. Il primo lavoro è un collaudo
   da «amico nuovo» sull'ambiente di prova (invito, installazione sulla Home, rose, regole e tempi della lega), che elenca cosa
   manca: le sotto-issue nascono da lì. Prima di aprire: audit di sicurezza completo con la skill `security-audit`, sulla
   parte che vedono gli amici (account, inviti, importazione, avvisi, widget, token); il rapporto resta privato e i problemi
   gravi o critici bloccano l'apertura *[scelta del coordinatore]*. Nessuna data fissa: #168 parte appena il #167 ridotto è
   chiuso *[scelta del coordinatore]*.
3. **#165 e #166 vanno avanti a ogni giornata, in parallelo**, con le misure del registro e del Diario (prima misura di «gioca
   N%» con le probabili verso il 9/12, #379). Un lavoro sul modello o sul consiglio parte solo se una misura lo chiede: «misura,
   poi accendi». «Lo chiede» vuol dire: un indicatore fuori soglia sulla finestra di 8 giornate. Il registro manda già un
   avviso al proprietario quando I1, I2 o I3 escono dalla soglia; il coordinatore ne fa un'issue sotto #165 o #166.

**Rimandati a dopo #168** (restano issue `P3`): web divisa in moduli (#500, #501, #502), regressione visiva bloccante (#504),
foto iOS mirate (#505), corpi delle richieste iPhone dall'OpenAPI (#509), avviso sulle fotografie vecchie (#508)
*[scelta del coordinatore per #508: fa parte dello stesso lavoro di #509]*.

## 8. Come si decide su una richiesta nuova
1. Serve a schierare la formazione o a rendere più preciso il fantavoto atteso? Se no: non si fa, o issue `P3` con
   l'etichetta `fuori-piano`.
2. Tocca una funzione congelata? Solo se è un difetto.
3. Sta nell'obiettivo in corso (§7)? Se no, aspetta il suo turno.

## 9. Vincoli
- Repository pubblico, AGPL-3.0: niente dati veri, chiavi, indirizzi; il nucleo resta gratuito per sempre.
- Fonti di oggi (Fantacalcio.it per uso personale e pochi amici, Understat come metro, ESPN per la diretta) fino al pubblico.
- La web è il riferimento; l'iPhone si compila e si prova solo sui Mac di GitHub (5 job in tutto).
- Nessuna spesa (fonte con licenza, account Apple) prima della chiusura di #168.

## 10. Cosa resta a chi pianifica
- Il piano rivisto: riallineare `docs/superpowers/plans/2026-11-08-ondata-2.md` a §7 (escono B1-B6, D2, E1, F3) e
  ordinare i lavori del #167 ridotto per area di file, nei tetti di PR.
- La pulizia dell'arretrato: chiudere o portare a `P3` le issue che non stanno in §7, aggiornare il testo dei quattro obiettivi
  (#165-#168) con l'ordine e le misure di questa spec.
- Le misure di §6 esistono già nel registro e nel Diario; manca solo il controllo di «10 minuti» per #168, da scrivere quando
  si arriva lì.
