---
name: collaudo
description: Come si prova davvero la web app di SchieraXI - foto e misure senza finestra con lo strumento del repository, percorso di un utente nuovo, cosa guardare nelle schermate. Usala dopo una modifica visibile alla web, prima di togliere la bozza a una pull request che cambia l'aspetto, o per un collaudo a rotazione.
---
# Collaudo della web

Una sola strada: lo strumento del repository, che usa Chrome di sistema senza finestra con un profilo temporaneo. Non si
usa il browser dell'utente e non si aprono finestre.

## Una volta per sessione: Playwright in un ambiente a parte
Fuori dal repository (cartella temporanea della sessione), mai nel Python di sistema né nel `.venv` del progetto:

```
py -3.13 -m venv <cartella-temporanea>\pw
<cartella-temporanea>\pw\Scripts\python.exe -m pip install playwright==1.64.1
```

## Foto e misure
Dalla radice del repository o della worktree (fotografa il codice del ramo in cui sei):

```
<cartella-temporanea>\pw\Scripts\python.exe prove\foto_web\foto.py <cartella-delle-foto> --scene formazione,scheda,impostazioni
```

Avvia e ferma da solo un server di prova con la lega d'esempio, su un indirizzo suo. Opzioni e scene:
`prove/foto_web/LEGGIMI.md`. Di norma: larghezze 390, 768, 1024, 1440 e temi chiaro e scuro. Le foto restano fuori dal
repository.
- Le scene seguono le tre voci della barra: `formazione` (la prima schermata; la scena «oggi» non c'è più), `scheda` (il
  primo titolare), `diario` (la pagina Giornate), `impostazioni`. Le pagine di Impostazioni > La mia lega sono `rosa` (La mia
  squadra) e `regole` (Regole e scadenza); `squadra` e `altro` sono gli indirizzi di prima, che aprono Impostazioni.
- `riepilogo.txt`: per ogni scena violazioni gravi di accessibilità, scorrimento di lato, errori della console. Devono
  essere zero.
- Le tre fasi della giornata (prima della scadenza, in corso, finita) si vedono con gli scenari registrati di
  `ios/fotografie/vero-*.json` e il server finto (`script/ci/server_finto.py`, come fa `script/ci/aspetto_web.py`): la
  Formazione cambia testa con la fase, le altre schermate no.
- L'ingresso di un utente nuovo: `prove/amico_nuovo/percorso.py <cartella-dei-risultati> --locale` (secondi, tocchi ed
  errori per ogni passo; opzioni in `prove/amico_nuovo/LEGGIMI.md`).

## Guardare
Le misure non bastano. Apri le foto (almeno 390 px chiaro e 1440 px chiaro delle scene toccate) e rispondi da utente:
1. Qual è la prima cosa che si legge? È quella che serve per decidere chi schierare?
2. Lo stesso fatto compare più di una volta? C'è un numero o un'etichetta che non si capisce senza spiegazione?
3. Quanti schermi bisogna scorrere per arrivare alla cosa principale?
4. Allineamenti, testo a capo, spazi vuoti grandi su tablet e PC, cose che sembrano toccabili e non lo sono.
5. Stesse parole e stessi numeri delle altre schermate (e dell'iPhone, `docs/COERENZA-WEB-IPHONE.md`).

Ogni difetto si riporta con scena, larghezza, tema e nome della foto. Un difetto vero che non si corregge subito diventa
un'issue.
