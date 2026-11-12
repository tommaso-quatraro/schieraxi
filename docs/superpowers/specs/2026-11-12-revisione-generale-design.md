# Revisione generale del 12/11/2026: cosa abbiamo trovato e cosa cambia

Il proprietario ha chiesto di rivedere tutto da capo: istruzioni e metodo di lavoro, web, iPhone, logiche, fonti e
precisione dei dati, con carta bianca anche per stravolgere. Sette analisi indipendenti hanno guardato il progetto con i
dati veri della stagione (archivio del server, registri, foto di tutte le schermate). Qui c'è la sintesi, le scelte prese e
il piano. I numeri sono aggregati: nessun dato di una lega vera.

## 1. Cosa abbiamo trovato

### Il consiglio
- Il fantavoto atteso non è sbagliato, ma vale poco più di una media: sbaglia circa l'1% in meno di una fantamedia fatta
  bene (non l'11% che l'app si attribuiva confrontandosi con una fantamedia fatta male). In punti di formazione la
  consigliata vale da +0,4 a +0,8 a giornata rispetto a «scelgo per media voto, sapendo chi gioca», e da +1,3 a +2,2
  rispetto a «scelgo per media voto senza sapere chi gioca». **Il valore vero dell'app è sapere chi gioca** e dirlo bene,
  più che il decimale del fantavoto atteso. Il tetto è il caso: il fantavoto di una partita è per il 90% imprevedibile.
- Il livello è basso: gol attesi all'85% dei veri, rigori attesi a un quarto dei veri, centrocampisti sottostimati; i
  punti attesi della formazione sono più bassi del vero di circa 2.
- Difetti di logica verificati: la panchina è ordinata per «probabilità × valore» invece che per valore (entra la riserva
  più sicura invece della più forte); lo stile «Equilibrata» non sceglie il massimo dei punti attesi e i cinque stili non
  hanno effetto misurabile; la correzione di «gioca N%» era imparata da formazioni lette dopo le partite; la frase
  «rigorista» non può mai comparire; il Diario confronta la formazione schierata con una consigliata ricostruita dopo, mai
  mostrata; il «massimo possibile» non è un massimo.
- Le misure in punti su 10 rose vere non distinguono mezzo punto: avvisi e verdetti scattano per caso.
- Misura e sorveglianza sono 3.450 righe di codice contro 1.255 di modello e scelta.

### I dati
- I dati di base (calendario, risultati, voti, listone, nomi) sono puliti: zero buchi e zero incoerenze su 490 partite.
- La fonte dei gol attesi è ferma dal 1° novembre (il sito risponde con una pagina di manutenzione) e nessuno è stato più
  avvisato: l'allarme scatta una volta sola e poi tace, quindi oggi nessun guasto nuovo avviserebbe.
- La mattina dopo una giornata le probabili mostrate come «aggiornate oggi» sono la copia della giornata finita (verificato
  su due passaggi su due); l'app ci calcola formazione, «Da fare» e avvisi di cambi.
- Alla scadenza le probabili azzeccano l'83% dei titolari: è il limite della fonte, leggere più spesso non lo sposta.
- Due fonti «in ombra» dovevano essere tolte e sono ancora accese; restano residui delle quote, contro la decisione 0005.

### Il prodotto
- Circa 40 fra schermate e fogli, 18 voci di secondo livello, 62 impostazioni per un utente normale, 7 moduli × 5 stili in
  cima alla Formazione, 5 numeri per giocatore in una riga e 15 etichette di stato.
- Oggi non dice chi schierare (zero nomi nel primo schermo). Formazione sul telefono è lunga quasi 6 schermi e il campo è
  sotto la piega; gli 11 titolari compaiono tre volte.
- Il numero grande non spiega la scelta (un 7,5 in panchina, un 5,7 titolare) e l'app rimedia con cinque spiegazioni.
- «Titolare» e «panchina» hanno due significati (la mia formazione, la squadra vera). «Salvata» non dice dove: l'app non sa
  se la formazione è stata messa nell'app della lega, l'unica cosa che fa punti.
- «Da fare» elenca informazioni senza azione e le ripete in «Da controllare». Il Diario, che è nel nucleo, è a tre tocchi.
- Due schede su quattro (Squadra, Altro) sono cassetti di funzioni congelate.

### L'iPhone
- 37.000 righe di Swift per fare ciò che la web fa in 8.000. Dal 28/10 è costato un terzo delle pull request e metà delle
  issue (67 solo di «coerenza»); una modifica costa 104 minuti di Mac. Un solo utente la usa. Ha gli stessi difetti di
  prodotto della web. La parte riuscita meglio sono i widget.

### Il server e il codice
- Il server è sano (memoria, disco, copie, certificati). 102 installazioni in 10 giorni, ognuna con un riavvio e un avviso.
- `server.py` importa 61 moduli; il nucleo dipende da funzioni non di nucleo; 102 `except Exception`, 61 senza registro.
- 4.618 test in 145 secondi: il 23% cerca stringhe nel testo dei sorgenti (web, Swift, workflow, documenti) e si rompe a
  ogni riordino; `modello.py` ha 11 test; la web non gira mai in un browser vero nei controlli che bloccano.

### Il metodo
- In 15 giorni 337 pull request: circa il 37% prodotto nuovo, 21% riparazioni, 16% coerenza web-iPhone, 21% processo.
- Le istruzioni erano 2.700 righe su 7 strati, con la stessa regola scritta fino a 13 volte, regole superate e cronaca al
  posto delle regole; un agente leggeva circa 950 righe prima di scrivere codice. Le regole del progetto stavano fuori dal
  repository.

## 2. Le scelte

Prese da chi coordina con la carta bianca del proprietario; quelle che restano a lui sono al §4.

### Prodotto: tre destinazioni
1. **Formazione** (Oggi + Formazione): una riga con giornata e scadenza; al massimo due decisioni vere, ognuna con il suo
   pulsante; il campo con gli 11 nel primo schermo; sotto, la panchina nell'ordine in cui entra e i non schierati. Il
   modulo è un menu. La stessa schermata cambia testa con la fase (prima, in corso, finita).
2. **Giornate** (il Diario, come pagina): per ogni giornata punti fatti e attesi, e al tocco gli 11 con atteso e preso.
   Il confronto si fa con la consigliata mostrata prima della scadenza.
3. **Impostazioni**: avvisi, la mia lega (rose, squadra, regole e scadenza), account, tema, informazioni; per chi gestisce,
   una sezione di gestione.

- Sul giocatore due numeri: fantavoto atteso (se gioca) e «gioca N%», quest'ultimo solo quando è sotto l'80%. Via l'indice
  0-100, le quattro etichette di titolarità (restano «in dubbio», «infortunato», «squalificato»), la legenda.
- La scheda del giocatore assorbe «Perché questo numero», il Confronto e la sostituzione: tre motivi, ultimi voti,
  «Sostituisci» con la differenza in punti per ogni alternativa.
- Salvataggio automatico: valgono due stati, «la consigliata» e «cambiata da te», più «chiusa». «Copia per l'app della
  lega» e la spunta «L'ho messa» dicono all'app cosa è stato schierato davvero.
- Via dalle schermate: stili, scambi, cambi consigliati, calendario, movimenti, crediti, seguiti, elenco dei giocatori (resta
  la ricerca), immagine da condividere, banner delle novità, dimensione del testo, frecce «Aggiorna i dati». Il codice
  resta nella storia di git.

### Modello: correggere, non rifare
Un modello più semplice farebbe lo stesso errore: non si rifà per la precisione. Si correggono, con misura prima e dopo:
panchina in ordine di valore; consigliata = massimo dei punti attesi (un solo stile); correzione di «gioca N%» solo da
letture di prima della partita; ripiego quando mancano le statistiche di una partita (righe ricostruite dai voti) e avviso;
rigori dalla quota di squadra; un solo fattore di livello dei gol, tirato verso 1; Diario sulla consigliata mostrata;
confronti onesti nelle misure (numero fisso per ruolo, fantamedia tirata verso il ruolo) e punti misurati su rose a sorte
con il loro intervallo. Indicatori che non distinguono niente: via.

### Dati
Probabili copiate riconosciute e trattate come «non ancora uscite»; ultimo successo di ogni passo dell'aggiornamento
visibile e allarme per fonte, ripetuto finché dura; controlli sui voti che contano come errori; via la seconda fonte di
probabili e i residui delle quote; archivio dei dati di calcio nella copia notturna; squalificati e diffidati calcolati dai
nostri cartellini. Obiettivo: dipendere da una fonte sola, con ciò che si può calcolato in casa.

### Server
Niente avviso a ogni installazione riuscita; dopo, in ordine: via il codice morto e le funzioni tolte dalle schermate,
`server.py` diviso per area, misura e sorveglianza fuori dal servizio.

### Metodo
Le regole stanno nel repository: `CLAUDE.md` corto, quattro schede per area in `.claude/rules/`, `docs/METODO.md` per chi
coordina, `MAPPA.md` corta con i dettagli in `docs/RIFERIMENTO.md`, quattro agenti generici e quattro skill di progetto.
Ciò che una macchina impone non si ripete a parole. Una revisione indipendente per pull request. Test di comportamento al
posto dei test che cercano stringhe.

## 3. Il piano

Corsie con file diversi, in parallelo; dentro una corsia le pull request vanno in fila.

| Corsia | Pull request, in ordine |
|---|---|
| Metodo | regole nuove nel repository (questa) |
| Server | avvisi e copia notturna (#607) → codice morto → funzioni tolte → `server.py` per area |
| Dati | probabili copiate, guasti visibili, controlli (#608) → via la seconda fonte (#609) → squalificati dai cartellini |
| Modello | panchina, massimo dei punti attesi, un solo stile → ripiego senza statistiche, rigori, livello dei gol → Diario e misure oneste |
| Web | tagli → Formazione unita → Giornate → Impostazioni e navigazione; test di comportamento nel browser al posto dei test sul sorgente |
| iPhone | ferma finché il proprietario non sceglie (§4); intanto nessun lavoro di allineamento |

Ogni pull request: misura o prova prima e dopo, una revisione indipendente, rilascio automatico. Per il modello
`python -m fanta verifica` e le misure su rose a sorte; per la web le schermate guardate a 390 e 1440 px nelle tre fasi.

## 4. Cosa resta al proprietario
1. **iPhone**: tenere l'app nativa completa, oppure passare a un involucro attorno alla web con i widget nativi e i
   promemoria (il Swift scende da 40.000 a circa 5.000 righe e una modifica alla web non tocca più i Mac). L'analisi
   consiglia l'involucro; si perdono aspetto e gesti nativi.
2. **Rilasci**: uno per pull request come oggi, oppure raggruppati (per esempio uno all'ora, subito solo per le urgenze).
3. **Fonte con licenza** prima dell'apertura al pubblico: resta la decisione già nota.
