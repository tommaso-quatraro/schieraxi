# SchieraXI

**Schierali. Schiera gli XI.**

![SchieraXI: la schermata Oggi](sito/img/schermata-larga.png)

SchieraXI è un'app web che consiglia la formazione del fantacalcio per una lega classic di Serie A.
Per ogni giocatore stima il **fantavoto atteso**, cioè il punteggio che ci si può aspettare con le regole della tua lega,
e da lì ricava gli 11 titolari, il modulo e l'ordine della panchina. Le statistiche sono nostre, calcolate dal progetto.
È software libero (AGPL-3.0). Sito: <https://schieraxi.it>.

> **In English:** SchieraXI is free software (AGPL-3.0) that suggests the lineup for a classic Serie A fantasy league,
> based on each player's expected fantasy score (*fantavoto atteso*). Web app (PWA) available now; the iPhone app is a work in
> progress and Android is planned. You run the server yourself. Data sources are **off by default**. Screens and docs are in Italian.

## Cosa fa
- Ogni giornata propone gli 11 titolari, il modulo e la panchina, con il motivo di ogni scelta in una riga.
- Mostra per ogni giocatore il fantavoto atteso e la probabilità che giochi, con una fascia di incertezza.
- Aiuta con gli scambi e avvisa se cambia qualcosa (infortuni, probabili formazioni, scadenza).
- Nel Diario confronta la formazione schierata con quella consigliata, a giornata finita.
- Mostra i risultati in diretta durante la giornata.

È una guida, non una garanzia: sono stime. Non fa l'asta e non schiera la squadra al posto tuo.
Come si usa: `docs/GUIDA-UTENTE.md`. Come ragiona il modello, con numeri e limiti: `docs/SOTTO-IL-COFANO.md`.

## Avviso
SchieraXI è un progetto indipendente. **Non è affiliata, approvata o sponsorizzata da Fantacalcio.it, da Leghe Fantacalcio
né dalla Lega Serie A.** I nomi citati appartengono ai rispettivi proprietari e servono solo a dire con cosa funziona.
Il progetto non include né ridistribuisce dati di terzi: le rose di prova sono inventate.

## Piattaforme
- **Web**: disponibile ora. Si usa dal browser e si può installare come app (PWA).
- **iPhone**: in lavorazione, in arrivo. Il codice è nella cartella `ios/`.
- **Android**: pianificata per il futuro.

## Come provarla
Hai due strade.

### 1. Web, sul tuo computer
Servono Python 3.11 e Git. I comandi sono per Windows. Su macOS e Linux usa `.venv/bin/python` al posto di `.venv\Scripts\python.exe`.

1. Scarica il codice: `git clone https://github.com/tommaso-quatraro/schieraxi.git`, poi `cd schieraxi`.
2. Crea l'ambiente: `python -m venv .venv`.
3. Installa le librerie: `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Avvia il server: `.venv\Scripts\python.exe -m fanta server`.
5. Apri nel browser `http://127.0.0.1:8000`. Dal browser puoi installarla come app (PWA).

Il server ascolta solo sul tuo computer. Non aprire la porta su internet senza protezione.

### 2. Un server tutto tuo (Linux)
1. Scarica il codice in una cartella dell'utente e prepara l'ambiente come sopra (`python3 -m venv .venv`,
   poi `.venv/bin/python -m pip install -r requirements.txt`).
2. Copia `script/server/fantacalcio.service` in `/etc/systemd/system/`, sostituisci `<utente>` e controlla i percorsi.
3. Attiva il servizio: `sudo systemctl daemon-reload`, poi `sudo systemctl enable --now fantacalcio`.
4. Controlla che risponda: `curl -i http://127.0.0.1:8000/api/stato`. Va bene `200`, e anche `401` (gli account sono attivi e manca l'accesso).
5. Per aprirla fuori casa metti davanti un proxy con HTTPS. Quella configurazione non è nel repository.

Il servizio di esempio usa il modo con account (`FANTA_MULTIUTENTE=1`), obbligatorio su un server raggiungibile da altri.
Script di manutenzione: `script/server/LEGGIMI.md`. Nomi delle variabili: `.env.example`. Chiavi e segreti vanno in `.env` o in `dati/`, mai in git.

## La tua lega
In `lega/esempio/` c'è una lega **inventata** (10 squadre finte): serve a provare l'app.
Per la tua, crea una cartella fuori dal progetto con `regole.json` e `rose.json` e avvia il server con `FANTA_LEGA=<cartella>`.
Le regole non sono scritte nel codice: bonus, malus, moduli, panchina e scadenza stanno in quel file.
Non copiare dati veri di una lega dentro il repository.

## Fonti dati: spente di default
SchieraXI può leggere dati pubblici da siti di terzi (calendario, voti, probabili formazioni, statistiche dei tiri).
- Ogni fonte ha un interruttore ed è **spenta di default**. Si accende con `FANTA_FONTE_<NOME>=1` (per esempio `FANTA_FONTE_UNDERSTAT=1`).
- Prima di accenderla leggi e rispetta le condizioni d'uso del sito: chi la accende se ne assume la responsabilità.
- Le richieste sono poche, una alla volta, con pausa e cache locale. L'agente di rete si presenta come `SchieraXI/<versione>`.

## Dove va il progetto
Quattro obiettivi, in quest'ordine di lavoro: 3, 1, 2, 4.
- [#167](https://github.com/tommaso-quatraro/schieraxi/issues/167) **App semplice, uguale su iPhone e web**: poche schermate, stesse parole e stessi numeri (`docs/COERENZA-WEB-IPHONE.md`).
- [#165](https://github.com/tommaso-quatraro/schieraxi/issues/165) **Statistiche nostre, affidabili**: gol e assist attesi, minuti e probabilità di giocare calcolati dal progetto, con una misura a ogni giornata.
- [#166](https://github.com/tommaso-quatraro/schieraxi/issues/166) **Consiglio di formazione giusto, e spiegato**: la formazione consigliata deve valere almeno quella schierata, senza cambi insensati.
- [#168](https://github.com/tommaso-quatraro/schieraxi/issues/168) **Aperta agli altri**: prima pochi amici, poi il pubblico.

## Limiti
- Sono stime: il voto vero può cadere lontano dalla previsione, per questo la formazione mostra una fascia.
- Dipende dalle fonti: se un sito cambia, i dati mancano finché non si sistema il lettore. Gli abbinamenti dei nomi tra fonti possono sbagliare.
- Pensata per una lega classic di Serie A.

## Struttura delle cartelle
- `fanta/`: il server Python (FastAPI) e la logica; `fanta/web/` è la web app.
- `ios/`: l'app per iPhone (SwiftUI), in lavorazione.
- `lega/esempio/`: la lega inventata.
- `tests/`: i test automatici (`.venv\Scripts\python.exe -m pytest -q`).
- `docs/`: guide per chi usa l'app e per chi sviluppa.
- `script/`: manutenzione del server e controlli.
- `sito/`: il sito <https://schieraxi.it>.

Elenco completo, comandi e regole di lavoro: `MAPPA.md` e `CLAUDE.md`.

## Contribuire
Le proposte sono benvenute: leggi `CONTRIBUTING.md` (apri prima una issue, fai passi piccoli, niente dati personali).
Il metodo di lavoro è in `docs/METODO.md`. Per una falla di sicurezza non aprire una issue pubblica: leggi `SECURITY.md`.
Si applica `CODE_OF_CONDUCT.md`. Le versioni pubblicate sono nella pagina **Releases**.

## Licenza
Il codice è sotto **AGPL-3.0** (file `LICENSE`): puoi usarlo, studiarlo e modificarlo. Se offri una versione modificata a qualcuno
via rete, devi mettere a disposizione anche il codice modificato. Il nome SchieraXI e il logo sono marchi del titolare e
non rientrano nella licenza: vedi `TRADEMARKS.md`, dove trovi anche i contatti. Librerie di terzi: `THIRD-PARTY-NOTICES.md`.
