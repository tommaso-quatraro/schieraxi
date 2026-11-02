# SchieraXI

> **In short (English):** SchieraXI is a personal, free software (AGPL-3.0) app for fantasy football (fantacalcio) in a
> "classic" Serie A league. It estimates the expected fantasy score of each player, picks the 11 starters, the formation
> and the bench order for every matchday, helps with trades and checks its own past advice. It is a guide, not a
> guarantee, and it does not run the auction. It runs on your own computer or Raspberry Pi, with a web app (PWA),
> a native iPhone app (an Android app is paused). Data sources are **off by default** in this copy: read their terms before you turn them on.

Versione: 1.310. Licenza: AGPL-3.0 (file `LICENSE`).

## Cosa fa SchieraXI
- Ogni giornata consiglia 11 titolari, il modulo e l'ordine della panchina, con i punti attesi di ogni giocatore.
- Tiene d'occhio infortuni, squalifiche e probabili formazioni.
- Propone scambi con le altre squadre della lega e dice se un'offerta che ricevi conviene.
- Ti avvisa sul telefono quando la formazione consigliata cambia.
- Confronta la formazione che hai schierato con quella consigliata (il diario delle giornate).
- Usa le regole della tua lega (bonus, malus, moduli, panchina). Le regole non sono scritte nel codice: stanno in un file di configurazione.

Non fa: l'asta vera (la scheda Asta dà solo prezzi consigliati) e non schiera la squadra al posto tuo.

## Come funziona, in breve
Raccoglie dati pubblici (calendario, voti, probabili formazioni, statistiche attese dei tiri). Per ogni giocatore
stima la probabilità che giochi e il fantavoto atteso. Poi sceglie la formazione con il punteggio atteso più alto.
Si controlla da solo: rifà i conti sulle giornate passate usando solo i dati che c'erano allora.
Formule, parametri e limiti sono spiegati in `docs/SOTTO-IL-COFANO.md`.

## Le schermate, a parole
Le schede in basso sono cinque.
- **Oggi**: il conto alla rovescia alla prossima partita, la lista «Da fare», la formazione consigliata, i giocatori da
  controllare, gli indisponibili e i diffidati, e le partite del turno con i risultati in diretta.
- **Formazione**: il modulo, i titolari e la panchina. Tocchi un giocatore e vedi da cosa nasce il suo punteggio atteso.
  Puoi cambiare lo stile della formazione (più prudente o più rischioso) o cambiare un titolare a mano.
- **Mercato**: giocatori liberi da prendere al posto di chi non rende, tutti i giocatori ordinati per punti attesi,
  i giocatori che segui e il calendario.
- **Scambi**: tre modi in un posto solo. «Trova per me» cerca scambi utili a tutte e due le squadre. «Costruisci» lo
  scambio a mano. «Valuta un'offerta» legge il messaggio che ti ha mandato un altro allenatore.
- **Lega**: importi le rose, scegli la tua squadra, vedi le altre squadre, le regole, i movimenti e il diario.

Ogni schermata è descritta passo per passo in `docs/GUIDA-UTENTE.md`.

## Provarla sul tuo computer
Servono Python 3.11 e Git. I comandi sono per Windows (dalla cartella del progetto).

1. Scarica il codice: `git clone https://github.com/tommaso-quatraro/schieraxi.git` poi `cd schieraxi`.
2. Crea l'ambiente: `python -m venv .venv`.
3. Installa le librerie: `.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt`.
4. Prova i test (facoltativo): `.venv\Scripts\python.exe -m pytest -q`.
5. Avvia il server: `.venv\Scripts\python.exe -m fanta server`.
6. Apri nel browser `http://127.0.0.1:8000`. Su macOS o Linux usa `.venv/bin/python` al posto di `.venv\Scripts\python.exe`.

Il server ascolta solo su questo computer. Per il telefono serve un collegamento sicuro (per esempio una VPN privata): non aprire
la porta su internet.

## Installarla su un Raspberry Pi (Linux)
Stessi passi, in una cartella di casa, per esempio `/home/<utente>/schieraxi`. Requisiti: Python 3.11 (come nei controlli del progetto).

1. Scarica il codice con `git clone https://github.com/tommaso-quatraro/schieraxi.git` in `/home/<utente>/schieraxi`, poi nella stessa
   cartella: `python3 -m venv .venv`, e `.venv/bin/python -m pip install -r requirements.txt`.
2. Crea il file del servizio `/etc/systemd/system/schieraxi.service` con questo contenuto (sostituisci `<utente>`):

   ```
   [Unit]
   Description=SchieraXI - formazione del fantacalcio
   After=network-online.target
   Wants=network-online.target

   [Service]
   User=<utente>
   WorkingDirectory=/home/<utente>/schieraxi
   ExecStart=/home/<utente>/schieraxi/.venv/bin/python -m fanta server --host 127.0.0.1 --porta 8000
   Restart=on-failure
   RestartSec=5
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```

3. Attiva il servizio: `sudo systemctl daemon-reload`, poi `sudo systemctl enable --now schieraxi`.
4. Controlla che risponda: `curl -i http://127.0.0.1:8000/api/stato`. Una riga `HTTP/1.1 200` o `401` vuol dire che il
   server è acceso (il 401 arriva quando sono attivi gli account e manca l'accesso).

Le variabili di configurazione (per esempio `FANTA_LEGA`, `FANTA_LIVE`) si mettono nel servizio con una riga
`Environment=NOME=valore`. Le chiavi, se mai ne servissero, vanno in `.env` o nella cartella `dati/`, mai in git.

## La tua lega
Il progetto contiene una lega **inventata** in `lega/esempio/` (10 squadre finte, regole d'esempio): serve a provare l'app.
Per la tua lega crea una cartella fuori dal progetto con `regole.json` e `rose.json`, poi avvia il server con
`FANTA_LEGA=/percorso/della/cartella`. Non copiare dati veri di una lega dentro il repository.

## Fonti dati: spente di default, rispetta i loro termini
SchieraXI legge dati da siti di terzi. Non ridistribuisce i loro dati: i file di prova in `tests/dati/` sono inventati.
- Ogni fonte (Fantacalcio.it, Understat, football-data.co.uk, ESPN, Sosfanta, foto) ha un interruttore proprio ed è spenta
  di default. Si accende con `FANTA_FONTE_<NOME>=1` (per esempio `FANTA_FONTE_UNDERSTAT=1`) o dalle impostazioni dell'amministratore.
  Prima di accenderla leggi e rispetta le condizioni d'uso del sito: chi la accende se ne assume la responsabilità.
- Stemma e maglia si possono scaricare solo da un indirizzo https pubblico che indichi tu.
- Le richieste sono poche, una alla volta e con pausa, e si salvano in una cache locale. L'agente di rete si
  presenta come `SchieraXI/<versione>`.

## Limiti
- Sono stime, non certezze. Il voto vero può cadere lontano dalla previsione. Per questo la formazione mostra una fascia.
- Sulle giornate passate il modello fa un po' meglio di chi sceglie solo con la media dei voti, ma di poco e su campioni piccoli.
  I numeri aggiornati stanno in `docs/SOTTO-IL-COFANO.md`.
- Dipende dalle fonti: se un sito cambia o sparisce, i dati mancano finché non si sistema il lettore.
- Gli abbinamenti dei nomi tra fonti possono sbagliare: controlla i giocatori segnalati.
- È pensata per una lega classic di Serie A. Le altre modalità non sono previste.
- L'app per iPhone si installa a mano con SideStore (vedi `docs/INSTALLAZIONE-IPHONE.md`); l'app web si installa dal browser.

## Cosa c'è nel repository
- `fanta/`: il server Python (FastAPI) e la logica (modello, formazione, scambi, account).
- `fanta/web/`: la web app (HTML, CSS e JavaScript senza librerie).
- `ios/`: l'app per iPhone (SwiftUI).
- `tests/`: test automatici. `docs/`: guide per chi usa l'app e per chi sviluppa.
- `lega/esempio/`: la lega inventata.

## Contribuire, sicurezza, licenza
- `CONTRIBUTING.md`: come proporre modifiche.
- `SECURITY.md`: come segnalare un problema di sicurezza in privato. Non aprire una issue pubblica per una falla.
- `CODE_OF_CONDUCT.md`: come trattiamo le persone nel progetto.
- `LICENSE`: licenza AGPL-3.0. Puoi usare, studiare e modificare il codice. Se offri una versione modificata a
  qualcuno via rete, devi mettere a disposizione anche il codice modificato.
