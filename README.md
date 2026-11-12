# SchieraXI

**Schierali. Schiera gli XI.**

![SchieraXI: la prima schermata del sito, con un esempio di formazione](sito/img/schermata-larga.png)

SchieraXI è un'app che consiglia la formazione del fantacalcio per una lega classic di Serie A.
Per ogni giocatore stima il **fantavoto atteso**, cioè il punteggio che ci si può aspettare con le regole della tua lega,
e da lì ricava gli 11 titolari, il modulo e l'ordine della panchina. Le statistiche sono nostre, calcolate dal progetto.
È software libero (AGPL-3.0). Sito: <https://schieraxi.it>.

> **In English:** SchieraXI is free software (AGPL-3.0) that suggests the lineup for a classic Serie A fantasy league,
> based on each player's expected fantasy score (*fantavoto atteso*). The web app is live at <https://app.schieraxi.it>
> (invitation only for now); the iPhone app is a work in progress and Android is planned. Screens and docs are in Italian.

## Come si usa
La web app è su **<https://app.schieraxi.it>**. Per ora si entra su invito.

1. Chiedi un invito a chi gestisce l'app. Apri il link che ti mandano: si apre la registrazione con il codice già scritto.
   Senza link, apri l'indirizzo qui sopra e scrivi il **codice d'invito** nella scheda **Registrati**.
2. Scegli nome utente e password, tocca **Crea l'account** e salva il codice di recupero.
3. Esporta le rose da Leghe (Excel, CSV o testo copiato) e caricale dall'app. Per cominciare basta anche solo la tua squadra.
4. Imposta i tempi della lega: quando si chiude la formazione e da quale giornata è partita la lega.
5. Prima di ogni giornata apri **Oggi**, leggi il consiglio e invia la formazione dove giochi.

Si usa dal browser, su telefono e computer, e si può aggiungere alla schermata Home.
Tutti i passi, schermata per schermata: [`docs/GUIDA-UTENTE.md`](docs/GUIDA-UTENTE.md).

## Cosa fa
- Ogni giornata propone gli 11 titolari, il modulo e la panchina, con il motivo di ogni scelta in una riga.
- Mostra per ogni giocatore il fantavoto atteso e la probabilità che giochi, con una fascia di incertezza.
- Avvisa se cambia qualcosa (infortuni, probabili formazioni, scadenza).
- Nel Diario confronta la formazione schierata con quella consigliata, a giornata finita.
- Durante la giornata mostra i punti fatti finora e quelli attesi a fine giornata.

È una guida, non una garanzia: sono stime. Non fa l'asta e non schiera la squadra al posto tuo.
Come ragiona il modello, con numeri e limiti: [`docs/SOTTO-IL-COFANO.md`](docs/SOTTO-IL-COFANO.md).

## Piattaforme
- **Web**: disponibile ora su <https://app.schieraxi.it>.
- **iPhone**: in lavorazione, in arrivo. Il codice è nella cartella `ios/`.
- **Android**: in programma.

## Avviso
SchieraXI è un progetto indipendente. **Non è affiliata, approvata o sponsorizzata da Fantacalcio.it, da Leghe Fantacalcio
né dalla Lega Serie A.** I nomi citati appartengono ai rispettivi proprietari e servono solo a dire con cosa funziona.
Il progetto non include né ridistribuisce dati di terzi: le rose di prova sono inventate.

## Dove va il progetto
La direzione è scritta in [`docs/superpowers/specs/2026-11-08-prodotto-design.md`](docs/superpowers/specs/2026-11-08-prodotto-design.md):
per questa stagione l'app è per pochi amici su invito, con poche funzioni al servizio della formazione.
Il numero che dice se funziona è la precisione del fantavoto atteso, misurata a ogni giornata. Quattro obiettivi, in quest'ordine:
- [#167](https://github.com/tommaso-quatraro/schieraxi/issues/167) **App semplice, uguale su iPhone e web**: stesse parole e stessi numeri, una giornata intera senza errori, un ambiente di prova online.
- [#168](https://github.com/tommaso-quatraro/schieraxi/issues/168) **Aperta agli amici**: un amico entra da solo dalla web e carica la sua lega. Il pubblico dalla prossima stagione.
- [#165](https://github.com/tommaso-quatraro/schieraxi/issues/165) **Statistiche nostre, affidabili** e [#166](https://github.com/tommaso-quatraro/schieraxi/issues/166) **consiglio giusto e spiegato**: vanno avanti a ogni giornata con le misure, e si cambia il modello solo quando una misura lo chiede.

## Limiti
- Sono stime: il voto vero può cadere lontano dalla previsione, per questo la formazione mostra una fascia.
- Dipende dalle fonti: se un sito cambia, i dati mancano finché non si sistema il lettore. Gli abbinamenti dei nomi tra fonti possono sbagliare.
- Pensata per una lega classic di Serie A.

## Per chi sviluppa
Chi usa l'app non ha bisogno di questa parte.

**Avviarla sul tuo computer.** Servono Python 3.12 (la versione usata dai test) e Git. I comandi sono per Windows;
su macOS e Linux usa `.venv/bin/python` al posto di `.venv\Scripts\python.exe`.

1. Scarica il codice: `git clone https://github.com/tommaso-quatraro/schieraxi.git`, poi `cd schieraxi`.
2. Crea l'ambiente: `python -m venv .venv`.
3. Installa le librerie: `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Avvia il server: `.venv\Scripts\python.exe -m fanta server`.
5. Apri nel browser `http://127.0.0.1:8000`.

Il server ascolta solo sul tuo computer. Usa la lega inventata di `lega/esempio/` (10 squadre finte, regole d'esempio).
Una lega tua, per provare, sta in una cartella fuori dal progetto con `regole.json` e `rose.json`, e si indica con
`FANTA_LEGA=<cartella>`. Non copiare dati veri di una lega dentro il repository.

**Fonti dati: spente di default.** SchieraXI può leggere dati pubblici da siti di terzi (calendario, voti, probabili formazioni,
statistiche dei tiri). Sul tuo computer ogni fonte è spenta finché non la accendi con `FANTA_FONTE_<NOME>=1`
(per esempio `FANTA_FONTE_UNDERSTAT=1`). Prima di accenderla leggi e rispetta le condizioni d'uso del sito: chi la accende se ne
assume la responsabilità. Le richieste sono poche, una alla volta, con pausa e cache locale, e l'agente di rete si presenta
come `SchieraXI/<versione>`. Sul server pubblico le fonti le gestisce chi cura il progetto.

**Test.** Installa anche `requirements-dev.txt`, poi: `.venv\Scripts\python.exe -m pytest -q`.

**Dove sta cosa e come si lavora.**
- `MAPPA.md`: dove sta ogni cosa. `docs/RIFERIMENTO.md`: dettagli dei moduli e contratti.
- `CLAUDE.md`: le regole del repository e il flusso di lavoro.
- `docs/METODO.md`: il metodo di lavoro.
- `CONTRIBUTING.md`: come proporre una modifica (apri prima una issue, fai passi piccoli, niente dati personali).
- `SECURITY.md`: per una falla di sicurezza non aprire una issue pubblica. Si applica anche `CODE_OF_CONDUCT.md`.

Per installarlo su un server: `script/server/LEGGIMI.md`. Chiavi e segreti vanno in `.env` o in `dati/`, mai in git
(nomi delle variabili in `.env.example`).

## Licenza
Il codice è sotto **AGPL-3.0** (file `LICENSE`): puoi usarlo, studiarlo e modificarlo. Se offri una versione modificata a qualcuno
via rete, devi mettere a disposizione anche il codice modificato. Il nome SchieraXI e il logo sono marchi del titolare e
non rientrano nella licenza: vedi `TRADEMARKS.md`, dove trovi anche i contatti. Librerie di terzi: `THIRD-PARTY-NOTICES.md`.
