# API di SchieraXI: contratto per i client

Questo documento descrive le rotte HTTP che usano i client: la web app (`fanta/web/`), l'app iOS (`ios/`) e il widget iOS.
Descrive solo il contratto, cioè cosa mandare e cosa si riceve. Il codice è la fonte di verità: le rotte stanno in `fanta/server.py` (rotte generali) e `fanta/rotte_account.py` (account e amministrazione).

Per cambiare un'API, leggi prima la regola in `MAPPA.md` («Contratti delle API»): non si rompono i campi esistenti, si possono aggiungere.

Sigle usate qui:

- `<indirizzo del server>`: l'indirizzo dell'app, che dà chi la gestisce. Non è scritto nei documenti.
- **sessione**: il login. Il web la tiene nel cookie `fanta_sessione`; le app native la mandano come `Authorization: Bearer <token>`.
- **token del widget**: un token `fw_...` a scopo limitato, vedi sotto.

## 1. Regole generali

1. **Base**: tutte le rotte stanno sotto `<indirizzo del server>/api/`. Corpo e risposta sono JSON, salvo dove dice altro (file, testo, risposte in formato `text/plain`).
2. **Intestazione `X-Fanta: 1`**: obbligatoria in ogni richiesta che non è `GET` o `HEAD`. Senza, risposta `403` con `{"detail": "Richiesta non permessa"}`.
   Le richieste dal browser che arrivano da un altro sito vengono rifiutate con lo stesso 403 (si guarda `Sec-Fetch-Site`, oppure `Origin`).
   Eccezione: `POST /api/squadre/immagine/condivisa` (vedi sezione 6).
3. **Sessione**: con gli account accesi (`FANTA_MULTIUTENTE=1`), ogni `/api/` senza sessione valida risponde `401`:

   ```json
   {"detail": "Accesso richiesto", "multiutente": true, "registrazione": "invito"}
   ```

   Il campo `registrazione` vale `invito`, `email` o `aperta` (come ci si registra, vedi `account_email.py`).
   Le uniche rotte senza sessione sono: `POST /api/account/accedi`, `POST /api/account/registra`, `POST /api/account/registra/conferma`, `POST /api/account/recupero`, `POST /api/account/recupero-email`, `POST /api/account/recupero-email/conferma`, e i file statici della pagina (`/`, `/app.js`, `/stile.css`, `/sw.js`, `/manifest.webmanifest`, `/privacy`, `/termini`, `/crediti`, `/elimina-account`, icone e schermate del manifest `/screenshot-*.png`).
   Con gli account spenti non si fa nessun login: c'è un utente locale implicito (con i poteri dell'amministratore), quindi il server
   risponde SOLO alle richieste dirette dal computer su cui gira (127.0.0.1 o ::1) e senza intestazioni di proxy (`X-Forwarded-*`,
   `Forwarded`, `X-Real-IP`). Tutte le altre, anche i file della pagina, ricevono `403` con
   `{"detail": "Questo server non ha gli account accesi: risponde solo dal computer su cui gira"}`. Un server raggiungibile dai client
   deve avere `FANTA_MULTIUTENTE=1`.
4. **Login per le app native**: `POST /api/account/accedi` (o `registra`) con `"nativo": true`. La risposta contiene `token`; le richieste successive mandano `Authorization: Bearer <token>`.
   Senza `nativo`, il token va nel cookie `fanta_sessione` (HttpOnly, `SameSite=Strict`).
4b. **Dispositivo fidato** (facoltativo, dal 1/11/2026): dopo un accesso o una registrazione con invito riusciti il server dà un
   segreto del dispositivo (43 caratteri). Web: cookie `fanta_dispositivo` (HttpOnly, `SameSite=Strict`, `Path=/api/account/`, 60 giorni),
   il browser lo rimanda da solo. App native (`nativo: true`): campo `dispositivo` nella risposta, nessun cookie; il client lo salva
   (Keychain) e lo rimanda nell'intestazione `X-Fanta-Dispositivo` su `POST /api/account/accedi` e `POST /api/account/recupero`.
   Con il segreto giusto per quel nome utente, il titolare entra anche quando qualcuno sta provando password sul suo nome da altri
   indirizzi (niente tetto per nome e per indirizzo, niente rallentamento). Il server rimanda lo stesso segreto se vale, altrimenti
   uno nuovo: il client salva sempre l'ultimo ricevuto. Un client che lo ignora funziona come prima. Cambio password, recupero
   e «esci da tutti» cancellano tutti i segreti dell'utente (e gli indirizzi noti): il segreto torna al prossimo accesso.
   Quando molti tentativi sbagliati sono in corso, chi non è noto può ricevere subito `429` («Troppi tentativi in questo momento»)
   con `riprova_tra` di pochi secondi: il client riprova dopo `Retry-After`.
5. **Token del widget** (`Authorization: Bearer fw_...`): vale solo per `GET /api/oggi`, `GET /api/widget` e `GET /api/live`. Ogni altra rotta o metodo risponde `403` con `{"detail": "Questo accesso serve solo al widget"}`. Se il token è scaduto, revocato o sbagliato, la richiesta è trattata come una senza token: con gli account accesi, quindi, `401` se non c'è una sessione. Con il token, `/api/oggi` non mostra le voci di `da_fare` riservate all'amministratore. Nasce con `POST /api/account/token-widget` e dura 90 giorni. Cambiare la password o «esci da tutti» lo revoca.
6. **Errori**: sempre `{"detail": "testo in italiano"}`. Vedi la tabella della sezione 8.
7. **ETag e If-Match**: le risorse personali hanno un `ETag` (una impronta del contenuto). Chi scrive può mandare l'ETag letto nell'intestazione `If-Match`. Se nel frattempo è cambiato, `412`. Senza `If-Match` la scrittura va comunque (i client vecchi non si rompono).
   Risorse con ETag: regole, avvisi, osservati, scelta di una giornata, rose (squadre, rosa, scritture delle rose e dei crediti).
7b. **Lingua e cache**: le `GET /api/` con risposta JSON hanno `Vary: Accept-Language`. Con `Accept-Language: en`, se le note sugli infortuni vengono tradotte, l'`ETag` ha il suffisso `-en` (es. `"abc-en"`) e `If-None-Match` si confronta con quello: un ETag preso dalla risposta italiana non dà `304`. Le risposte da scaricare (`/api/backup`) non cambiano. In `If-Match` (scritture) invece `"abc-en"` vale come `"abc"`: è la stessa versione dei dati in un'altra lingua (dal 2/11/2026; prima dava `412`).
8. **304 e Cache-Control**: `GET /api/widget` risponde `304` se mandi `If-None-Match` con l'ETag uguale. Le risposte personali hanno `Cache-Control: private` o `no-store`.
9. **Calcoli pesanti**: se il risultato non è pronto, la rotta risponde `202` (vedi sezione 8). Il client riprova dopo `riprova_tra` secondi (anche in `Retry-After`).
10. **Limiti**:
    - corpo massimo: 12 MB per le rotte generali, 8 KB per quelle degli account (`413`);
    - spazio per utente: 5 MB di dati;
    - lega: massimo 20 squadre e 40 giocatori per squadra;
    - tetti giornalieri per utente (in `fanta/limiti.py`): 10 importazioni di rose, 60 ricerche di scambi (la variabile `FANTA_MAX_SCAMBI` lo cambia; chi amministra non ha limiti), 30 immagini scaricate da un indirizzo web;
    - rotte degli account: tentativi limitati (`429` con `Retry-After`). Il conteggio globale dei tentativi sbagliati (per tipo:
      accesso, recupero, iscrizione) non blocca: oltre la soglia le risposte a chi non è noto arrivano fino a 3 secondi più lente;
    - analisi di scambi (`GET /api/scambi/analizza`): al massimo 20 analisi diverse al minuto per utente (ripetere la stessa
      non conta) e poche alla volta (2 per utente, 3 in tutto il server): oltre, `429` con `Retry-After`.

11. **Lingua dei testi del server**: italiano se non dici nulla. Per l'inglese manda `?lingua=en` oppure `Accept-Language: en` (vince il parametro). Vale per i testi scritti dal server dove la rotta lo dice (per esempio `GET /api/novita`, `GET /api/sotto-il-cofano`, gli avvisi di copertura in `da_fare`, i giudizi degli scambi, le note sugli infortuni). Le note sugli infortuni delle fonti (campo `nota`, e la stessa nota dentro `motivi`) in qualunque risposta `GET /api/` si traducono con un vocabolario; una nota che non si riconosce tutta resta in italiano. Le risposte che cambiano con la lingua hanno `Vary: Accept-Language`. Attenzione: URLSession e OkHttp mandano da soli `Accept-Language` con la lingua del telefono; un client che vuole sempre l'italiano deve mandare `?lingua=it`. I messaggi d'errore (`detail`) restano in italiano; le frasi che cambiano con i dati hanno anche la chiave per tradurle (vedi «Frasi con chiave» più sotto).

## 2. Account (`fanta/rotte_account.py`)

Tutte le rotte sotto `/api/account/` rispondono `404` con `{"detail": "Gli account non sono attivi"}` se gli account sono spenti (tranne `me`, che risponde sempre).

| Metodo e percorso | Corpo | Risposta principale |
|---|---|---|
| `GET /api/account/me` | — | `{multiutente, utente}`; con gli account accesi aggiunge `email`, `email_origine`, `email_in_attesa` e `email_attiva` (dal 2/11/2026: `false` se sul server l'invio delle email è spento, `FANTA_MAIL=spento`; allora i client non propongono di collegare un'email né il recupero via email; c'è anche nella risposta `401`; assente = server vecchio, come `true`). `email` è l'email verificata dell'account; se l'account non ne ha una ma ha Google collegato con un'email verificata, è quella di Google. `email_origine` vale `"account"`, `"google"` o `null` (senza email). Mostra `email` così com'è (con una nota «da Google» se `email_origine` è `"google"`), «nessuna» solo se è `null`. Vale solo per chi chiede: mai l'email di un altro utente |
| `POST /api/account/accedi` | `{nome_utente, password, nativo?}`; intestazione facoltativa `X-Fanta-Dispositivo` | `{multiutente, utente}` + `token` e `dispositivo` se `nativo` (vedi 1.4b) |
| `POST /api/account/registra` | `{nome_utente, password, invito?, email?, accetto_termini?, nativo?}` | con invito: `{multiutente, utente, codice_recupero}` (il codice si vede una volta); se è stata scritta un'email ma la posta è spenta sul server (`email_attiva: false`) l'account nasce lo stesso, l'email non viene salvata né messa «in attesa» e la risposta aggiunge `email_non_salvata: true` (campo facoltativo, dal 2/11/2026). Con email (modi `aperta` e `email`): `{ok, verifica_email, scade_minuti, iscrizione}`; con la posta spenta `503` con `codice: "iscrizione_posta_spenta"` (nessun codice può arrivare), uguale per ogni indirizzo e nome, e non si crea niente (dal 2/11/2026). `accetto_termini` (facoltativo): `true` = l'utente ha spuntato Privacy e Termini d'uso, il server registra data/ora e versione (`VERSIONE_TERMINI`, oggi `2026-11-01`) sull'account; campo assente = client vecchio, si iscrive lo stesso senza traccia; `false` = `400` con "Per iscriverti devi accettare Privacy e Termini d'uso. / To sign up you must accept the Privacy policy and the Terms of use.". I client nuovi lo mandano sempre `true` dopo la casella; con Google (`social/completa`) resta obbligatorio |
| `POST /api/account/registra/conferma` | `{email, codice, iscrizione, nativo?}` | come `registra` (sessione aperta) |
| `PUT /api/account/nome` | `{nome_utente}` | `{utente}`: solo maiuscole e minuscole cambiano |
| `POST /api/account/esci` | — | `{ok: true}` |
| `POST /api/account/esci-da-tutti` | — | `{sessioni_chiuse}` |
| `POST /api/account/cambia-password` | `{attuale, nuova}` | `{multiutente, utente, ok: true}` + nuovo `token` se nativo |
| `POST /api/account/codice-recupero` | `{password}` | `{codice_recupero}` (nuovo, sostituisce il vecchio) |
| `POST /api/account/elimina` | `{password}` | `{ok: true}`: cancella account e dati |
| `POST /api/account/recupero` | `{nome_utente, codice, nuova}` | `{ok, codice_recupero}` |
| `POST /api/account/email` | `{email, password}` | risposta di verifica (stessa in ogni caso). Con la posta spenta sul server (`email_attiva: false`): `503` con `codice: "posta_spenta"`, niente email in attesa (dal 2/11/2026) |
| `POST /api/account/email/conferma` | `{codice}` | `{ok, email}` |
| `POST /api/account/email/togli` | `{password}` | `{ok}` |
| `POST /api/account/recupero-email` | `{email}` | risposta identica se l'indirizzo esiste o no. Con la posta spenta: `503` `posta_spenta`, uguale per ogni indirizzo (dal 2/11/2026) |
| `POST /api/account/recupero-email/conferma` | `{email, codice, nuova}` | `{ok, codice_recupero}` |
| `POST /api/account/token-widget` | — | `{token, scade, etichetta: "widget"}`: il token si vede una volta sola |
| `GET /api/account/token-widget` | — | `{presente: false}` oppure `{presente, valido, etichetta, creato, scade, ultimo_uso}` (mai il token) |
| `DELETE /api/account/token-widget` | — | `{revocato: true/false}` |

### Accesso con Google (`fanta/social.py`)

Il giro con Google lo fa il server (codice di autorizzazione + PKCE); il client apre solo l'indirizzo e riceve un codice monouso. Attivo solo se sul server ci sono `FANTA_GOOGLE_CLIENT_ID`, `FANTA_GOOGLE_CLIENT_SECRET` e `FANTA_GOOGLE_REDIRECT` (indirizzo di ritorno https, uguale a quello registrato presso Google; in `dati/ambiente.env`, mai in git): altrimenti tutte le rotte `social` rispondono `404`. I client controllano il campo `social` (elenco dei servizi accesi, per ora `["google"]`) nella risposta `401` e in `GET /api/account/me`: se è vuoto o manca, niente pulsante. Indirizzo da registrare presso Google e da mettere in `FANTA_GOOGLE_REDIRECT`: `<indirizzo del server>/api/account/social/google/ritorno` (non si ricostruisce mai dall'intestazione Host). L'email di Google vale come verificata (iscrizione, recupero) solo se è `@gmail.com` o di un dominio elencato in `FANTA_GOOGLE_DOMINI` (separati da virgole): un dominio Workspace qualsiasi no.

Il client genera un segreto casuale (`verificatore`, 43-128 caratteri `A-Za-z0-9._~-`), manda solo la sua `sfida` = base64url(SHA-256(verificatore)) senza `=`, e lo mostra al momento di riscattare il codice. Non lo scrive da nessuna parte oltre `sessionStorage` (web) o la memoria (app).

| Metodo e percorso | Sessione | Corpo | Risposta |
|---|---|---|---|
| `POST /api/account/social/google/inizia` | no (per `collega` e `riconferma` sì) | `{scopo: "accedi"\|"collega"\|"riconferma", sfida, piattaforma: "web"\|"ios", password?}`: per `collega` serve la `password` dell'account (se non ne ha, la riconferma di questa sessione); `403` se è sbagliata | `{url, scade_minuti}`: l'indirizzo di Google da aprire (il giro vale 10 minuti) |
| `GET /api/account/social/google/ritorno` | no (non usa il cookie) | `code`, `state`, `error` nell'indirizzo | `302` verso `/?social=<codice>` (web) o `schieraxi://social?codice=<codice>` (iOS); in caso di problema `?social_errore=annullato\|scaduto\|non_valido` (iOS: `schieraxi://social?errore=...`, anche quando il giro è scaduto o bloccato dal limite). Il codice vale 60 secondi, una volta sola |
| `POST /api/account/social/scambio` | solo per `collega` e `riconferma` | `{codice, verificatore, nativo?}` | `{stato:"ok", multiutente, utente}` (+ `token` se `nativo`): sessione aperta. `{stato:"nuovo", iscrizione, provider, nome_suggerito, serve_invito}`: account da creare con `completa`. `{stato:"collegato", accessi}` (se l'account ha un'email verificata arriva un avviso «Google collegato»). Per `collega` e `riconferma` il codice si riscatta solo dalla STESSA sessione (stesso cookie o Bearer) che ha fatto `inizia`; da un'altra, anche dello stesso utente, `403`. `{stato:"riconfermato"}`. Un verificatore sbagliato brucia il codice (`403`) |
| `POST /api/account/social/completa` | no | `{iscrizione, nome_utente, invito?, accetto_termini, nativo?}` | come `ok` sopra; niente `codice_recupero`. Valgono le regole di `FANTA_REGISTRAZIONE`: con `invito`/`email` serve il codice d'invito; con `email`/`aperta` l'indirizzo Google deve essere affidabile (Gmail o Workspace) |
| `GET /api/account/social/accessi` | sì | — | `{password: bool, social: [{provider, email, creata, ultimo_uso}], disponibili: ["google"]}` (lo stesso blocco è in `me` come `accessi`). `email` è `null` se Google non l'ha verificata |
| `DELETE /api/account/social/google` | sì | — | `{accessi}`; `409` con `codice:"ultimo_accesso"` se non resterebbe nessun altro modo di entrare |
| `POST /api/account/imposta-password` | sì | `{password}` | `{ok, codice_recupero}`: per chi è entrato solo con Google, dopo una riconferma |

Errori con `codice` (campo in più accanto a `detail`): `email_gia_usata` (`409`: l'indirizzo ha già un account, si collega da Impostazioni dopo aver fatto l'accesso), `email_non_affidabile` (`403`), `google_gia_collegato` (`409`), `google_diverso` (`403`), `ultimo_accesso` (`409`), `serve_riconferma` (`403`). L'email di Google non collega mai da sola un account che esiste già. Chi è solo Google non ha password: per eliminare l'account, cambiare l'email o mettere una password fa prima `inizia` con `scopo: "riconferma"` (vale 5 minuti, SOLO per la sessione che l'ha fatta); finché non lo fa, queste rotte rispondono `403` con `codice:"serve_riconferma"`. Tetti: 20 avvii all'ora per indirizzo, 60 ritorni, 30 riscatti, 10 `completa`, 2000 giri riusciti al giorno in tutto. `POST /api/account/esci-da-tutti` e il recupero della password (con codice o con email) scollegano anche i Google collegati a chi ha una password (chi è solo Google li tiene: resterebbe chiuso fuori), perché chi fosse entrato avrebbe altrimenti una porta che la nuova password non chiude. Un accesso con Google da un indirizzo nuovo manda l'avviso «dispositivo nuovo» come l'accesso con password. Per le app: nessuna novità per i client che non usano Google (campi nuovi facoltativi).

Amministratore (sessione con ruolo amministratore; altrimenti `403` «Solo per l'amministratore»):

| Metodo e percorso | Corpo | Risposta |
|---|---|---|
| `POST /api/admin/inviti` | `{etichetta, amministratore?, usi?}` | `{codice, etichetta, valido_giorni, usi_max}`. `usi` (1-30, predefinito 1) = quanti amici possono entrare con lo stesso codice; un invito da amministratore è sempre monouso |
| `GET /api/admin/inviti` | — | `{inviti: [{id, etichetta, ruolo, creato, scade, usi, usi_max, stato}]}`, `stato` = `attivo`, `finito`, `scaduto` o `revocato`. I codici non si rileggono |
| `DELETE /api/admin/inviti/{id}` | — | `{ok}`; 404 se non esiste. Chi è già entrato tiene l'account, il codice non vale più |
| `GET /api/admin/utenti` | — | `{utenti, massimo}` |
| `POST /api/admin/utenti/{id}/rose` | `{testo, sostituisci_tutto?}` | Solo amministratore: importa le rose di un utente che l'ha chiesto, nel SUO archivio. Stessa risposta di `POST /api/rose/testo`; non consuma le importazioni al giorno dell'utente; 404 se l'utente non esiste; lascia una riga nel registro di sicurezza (chi, per chi, quante squadre). Corpo fino a 600 KB (le altre rotte admin 8 KB). Al massimo 30 all'ora (429); con `sostituisci_tutto` le rose di prima restano in una copia datata (ultime 5). 409 se gli account non sono attivi sul server |
| `GET /api/admin/registro` | — | contatori, ultimi errori, ultimi eventi di sicurezza (indirizzi nascosti) |
| `GET /api/admin/funzioni` | — | `{funzioni: [{id, nome, serve, acceso, scelta_da, predefinito_pubblico, blocca_rotte}]}`: un interruttore per funzione (vedi «Funzioni» in fondo) |
| `PUT /api/admin/funzioni` | `{funzione, acceso}` (`acceso: null` toglie la scelta) | stesso elenco. Ordine di scelta: amministratore, variabile `FANTA_FUNZIONE_<NOME>`, predefinito (acceso nel codice privato, quello pubblico della tabella nell'esportazione) |
| `POST /api/admin/reset-password` | `{nome_utente}` | `{codice, valido_ore}` |
| `GET /api/admin/fonti` | — | `{fonti: [{id, nome, serve, acceso, scelta_da, messaggio}]}`: un interruttore per fonte esterna (`fantacalcio`, `understat`, `footballdata`, `espn`, `sosfanta`, `foto`) |
| `PUT /api/admin/fonti` | `{fonte, acceso}` (`acceso: null` toglie la scelta) | stesso elenco. Ordine di scelta: amministratore, variabile `FANTA_FONTE_<NOME>`, predefinito (acceso nel codice privato, spento nell'esportazione pubblica; foto sempre spente). `GET /api/stato-dati` ha lo stesso elenco nel campo facoltativo `fonti` |

I nomi degli utenti nelle risposte: per l'utente il nome è UNO solo e i client mostrano sempre `nome_visualizzato` (sempre presente: se l'utente non l'ha mai scelto coincide con `nome_utente`). `nome_utente` è la chiave tecnica minuscola: i client non la mostrano e non parlano di «nome per accedere». `nome_visualizzato` ha sempre le stesse lettere di `nome_utente`, cambiano solo le maiuscole (il server lo garantisce). All'accesso va bene qualsiasi scrittura del nome (`Mario`, `mario`): il client può mandare quello che l'utente ha digitato. `PUT /api/account/nome` (cambiare solo le maiuscole) è facoltativa per i client: se c'è, la schermata modifica lo STESSO nome, non ne propone un secondo né un campo «nome per accedere».
L'email del profilo e quella usata per recuperare la password sono cose diverse: il recupero (`recupero-email`) usa solo l'email verificata dell'account (`email_origine: "account"`); l'email «da Google» è solo da mostrare e non abilita nessun recupero.
`ruolo` vale `amministratore` o `utente`.

### Rotta pubblica per il monitoraggio

`GET /api/salute` (e `HEAD`, stessi header e nessun corpo) non chiede nessun accesso, nemmeno con gli account accesi, e non ha dati personali. Risponde solo `{"ok": true, "ultimo_aggiornamento": "<come in /api/stato>"}` con `Cache-Control: no-store` e senza ETag. Allarmi per il monitor: `ultimo_aggiornamento: null` (nessun aggiornamento registrato) oppure `503` con `{"ok": false, "ultimo_aggiornamento": null}` (database dei dati illeggibile). Limite: 600 richieste all'ora per indirizzo, contate in memoria (poi `429` con `Retry-After`); senza indirizzo visibile (richiesta locale) nessun limite. Il token del widget (`fw_...`) non serve a niente su altre rotte. I controlli esterni usano `/api/account/me` (200, oppure 401 con `multiutente`) per sapere se il sito è vivo e questa rotta per l'età dei dati: `/api/stato` con gli account accesi risponde 401.

## 3. Lettura della lega e della formazione

Tutte le rotte di questa sezione leggono i dati dell'utente (rose, regole, scelte). Con gli account accesi servono la sessione o il token del widget (solo per `oggi`, `widget` e `live`). I calcoli pesanti possono rispondere `202`.

| Metodo e percorso | Parametri | Risposta principale |
|---|---|---|
| `GET /api/stato` | — | stato della lega e dei dati (`errori_ultimo`: per intero solo all'amministratore, agli altri solo `"<passo>: non riuscito"`); campo facoltativo `sorgente` = indirizzo https del codice sorgente AGPL (stringa vuota se non impostato con `FANTA_SORGENTE`): le app lo mostrano come link «Codice sorgente» solo se non è vuoto |
| `GET /api/stato-dati` | — | fonti, errori, affidabilità (solo amministratore). Campo nuovo e facoltativo `uso`: `{giorni: 28, dal, al, richieste, per_funzione: [{funzione, richieste}], per_rotta: [{rotta, richieste}], per_giorno: [{giorno, richieste}], nota}`, conteggio anonimo e aggregato dell'uso (nessun utente, nessun indirizzo; la rotta è quella di modello, per esempio `GET /api/giocatore/{calciatore_id}`), 28 giorni, nel file `dati/uso.json`. I client che non lo conoscono lo ignorano. In `controlli` ci sono anche le righe della sentinella (ogni ora): `sentinella` (riassunto) e `sentinella_<invariante>` con `esito` `ok`, `avviso` o `errore`; il `dettaglio` dice solo «utente N», giornata e campo, mai nomi. Il web mostra le righe `sentinella_*` solo quando non sono a posto |
| `GET /api/aggiorna` | — | stato dell'aggiornamento in corso (solo amministratore con gli account) |
| `POST /api/aggiorna` | — (X-Fanta) | avvia l'aggiornamento dei dati (solo amministratore con gli account) |
| `GET /api/novita` | — | elenco delle versioni: `versione`, `data`, `titolo`, `voci`; con `?lingua=en` o `Accept-Language: en` titolo e voci in inglese dove c'è la traduzione; le versioni senza traduzione hanno un titolo e una voce generici in inglese («Improvements and fixes»), mai l'italiano |
| `GET /api/oggi` | `certificato_giorni?` (da -3650 a 3650) | la schermata Oggi: giornata, conto alla rovescia, formazione (la consigliata; se hai salvato una tua scelta per la giornata, quella, con `formazione.tua_scelta: true`), avvisi, partite e `da_fare` (lista «Da fare», vedi sotto); `fase` della giornata (`prima`, `in_corso`, `finita`) con `in_corso`, `riepilogo`, `prossima` (vedi «fasi della giornata»). `certificato_giorni` lo manda solo l'app iPhone |
| `GET /api/live` | — | risultati in diretta delle partite del turno (cache, stesso per tutti, 304 con ETag). Solo lettura, nessuna richiesta esterna. Eventi: `gol`, `rigore`, `autogol`, `rigore_sbagliato`, `rosso` (niente gialli, niente troncamento; `assist` facoltativo su gol e rigori). Dettagli in `docs/LIVE.md` |
| `GET /api/widget` | — | riassunto compatto per il widget (sotto 18 kB, con ETag). Campi: `giornata`, `scadenza`, `ore_mancanti`, `formazione` (`modulo`, `punti_attesi`, `intervallo`, `titolari`, `panchina`; se l'utente ha salvato una sua scelta per la giornata, `formazione` è quella e porta `tua_scelta: true` e `consigliata` con `modulo` e `punti_attesi` della consigliata; senza scelta i due campi mancano; anche `titolare` di `rosa` segue la formazione mostrata), `avvisi`, `rosa` (ogni giocatore ha anche, dal 2/11/2026 e facoltativo, `p_voto` da 0 a 1: il widget scrive «In dubbio · gioca 55%» come Oggi; se manca, il campo non c'è), `squalificati`, `diffidati`, `rigoristi`, `crediti_residui`, `diario` (ultime 5 giornate finite, dalla più recente: `{giornata, giornata_lega, stagione, attesi, fatti, intervallo}`; `giornata_lega` e `stagione` dal 2/11/2026, gli stessi di `GET /api/diario`: `giornata_lega` è `null` fuori dalla stagione in corso, e il client scrive «Giornata N» con `giornata_lega ?? giornata`, più la stagione per le voci di un'altra stagione), `osservati`, `live` (stato e marcatori delle partite, senza cartellini), `funzioni` (facoltativo: `{live, diario, scambi_trova, seguiti, widget_extra: true|false}`, lo stato per questo utente come in `GET /api/funzioni`, già con «Mostra tutte» e le scelte dell'amministratore; il token del widget non legge `/api/funzioni`; un client vecchio ignora il campo, una chiave assente vale «acceso»). Ogni giocatore compatto ha, se noto, `squadra` (il club, stesso codice di `miei_titolari` di `/api/oggi`). Le parti facoltative (`scambio`, `svincolato`) ci sono solo se già in cache; i nomi di quelle mancanti stanno in `mancano`. Facoltativi, con la stessa forma di `GET /api/oggi` (stessa funzione): `fase` (`prima`, `in_corso`, `finita`) e, solo se non vuoti, `in_corso`, `riepilogo` e `prossima` (vedi «fasi della giornata»); un blocco vuoto qui manca invece di valere `null`, e senza `fase` mancano tutti. L'ETag cambia quando cambiano i punti in corso. Non fa mai partire calcoli. |
| `GET /api/sotto-il-cofano` | — | testi di «Sotto il cofano» con i numeri attuali (ETag, 304; 503 se il file dei testi manca). Contratto in `docs/API-SOTTO-IL-COFANO.md` |
| `GET /api/primo-avvio` e `PUT /api/primo-avvio` | `fatti?`, `saltati?`, `chiuso?` (solo PUT) | a che punto è la configurazione guidata. Vedi la sezione dedicata in `docs/API.md` (in fondo) |
| `GET /api/formazione` | `squadra?`, `giornata?` | `livelli[]` (uno per stile): `stile`, `nome`, `descrizione`, `modulo`, `punteggio_atteso`, `dev`, `intervallo`, `moduli[]` (ciascuno con `titolari[]`, `panchina[]` e `incerti[]`); `stile_consigliato: 0`. `incerti` (dal 2/11/2026, facoltativo: un client vecchio lo ignora, se manca vale vuoto) = `[{titolare, riserva}]` (id): titolare che gioca meno del 50% (`p_voto`) mentre la riserva che entrerebbe al suo posto (la prima dello stesso ruolo nell'ordine della panchina, una per titolare) gioca più dell'80%. Il client lo spiega sotto il campo e nel «Perché questo numero» del titolare: «Titolare anche se incerto (gioca 33%): se non gioca entra Vasquez dalla panchina, e insieme valgono di più.» Non dopo una modifica a mano né a giornata iniziata. Dettagli in `docs/STILI.md`. Senza `squadra` né `giornata`, per chi è entrato dopo la scadenza della giornata in corso senza una formazione (come `senza_formazione` di `/api/oggi`) la risposta è già quella della giornata DOPO e porta `giornata_saltata` e `giornata_saltata_lega` (facoltativi: la giornata in corso che non può più schierare); il client lo dice («La giornata 10 è già iniziata: questa è la formazione per la giornata 11») |
| `GET /api/formazione/testo` | — | la formazione come testo semplice (`text/plain`) |
| `POST /api/formazione/valuta` | `{titolari: [id...], squadra?, giornata?, salva?}` (X-Fanta) | punti attesi della formazione scelta a mano; con `salva: true` la ricorda come scelta della giornata. Formazione non valida (titolari ripetuti o non della rosa, modulo non ammesso): `400` con `{"detail", "codice": "formazione_non_valida"}` (dal 2/11/2026; prima solo `detail`). Se succede rileggendo la scelta salvata, il client NON la cancella da solo: dice «La formazione salvata non è più valida: rifalla o torna alla consigliata». Con `salva: true` dopo la scadenza della lega per quella giornata (`iniziata` di `GET /api/formazione`): `409` con `{"detail": "La giornata è già iniziata: la formazione non si può più cambiare.", "codice": "formazione_chiusa"}`, per tutti (amministratore compreso), niente scritto; senza `salva` la valutazione risponde come sempre. Il client mostra `detail`, ricarica la Formazione e toglie «Modifica a mano» e «Salva» |
| `GET /api/scelta` | `giornata` | la scelta salvata (ETag) oppure `null` se non c'è: `{titolari: [id...], modulo, salvata, tipo}`. `salvata` = data e ora del salvataggio (ora del server, senza fuso, es. `"2026-11-02T21:40:00"`; può mancare nei file vecchi); `tipo` = `manuale` (scelta a mano o «Salva questa») o `consigliata` («ho schierato la consigliata»; può mancare nei file vecchi = `manuale`). La copia automatica del server non si vede mai qui. Nelle giornate importate dal passato può avere in più `panchina` (id in ordine, facoltativo): i client che non lo conoscono lo ignorano. Stato della scelta in Formazione (web e iPhone): si confrontano gli 11 mostrati con `titolari` (ordine non conta) |
| `DELETE /api/scelta` | `giornata` (X-Fanta, If-Match) | torna alla formazione consigliata. Dopo la scadenza della giornata: `409` con `codice: "formazione_chiusa"` (come `POST /api/formazione/valuta`), la scelta resta. Unica rotta che cambia la scelta dopo la scadenza: `POST /api/diario/schierata`, e solo per una giornata finita |
| `GET /api/confronto` | `a`, `b`, `giornata?`, `squadra?`, `modulo?`, `livello?` | confronto tra due giocatori, con le cause della differenza. `consigliato` = l'id da schierare: se `formazione` c'è e uno solo dei due vi è `titolare` (`posto_a`/`posto_b`), è lui (dal 2/11/2026; prima era sempre chi ha più `punti_attesi` da solo e poteva contraddire «Schiera X»); altrimenti chi ha più `punti_attesi`. I client mettono «Consigliato» e il titolo sullo stesso giocatore e mostrano «Titolare» / «Panchina N» da `posto_a`/`posto_b` |
| `GET /api/diario` | — | `giornate[]`: per ogni giornata finita `giornata`, `stagione`, formazione schierata e consigliata con punti attesi (`reale`); ogni voce ha anche `regole` (impronta delle regole usate per i punti fatti, solo informativa: se la lega cambia i bonus la voce si ricalcola da sola). In cima anche `precisione` («Quanto ci abbiamo preso», vedi sotto) |
| `POST /api/diario/schierata` | `{giornata, tipo: "consigliata" o "manuale", titolari?` (11 id, per `manuale`), `modulo?}` (X-Fanta, If-Match) | «Ho schierato la consigliata» (o una formazione a mano, con `titolari`) per una giornata finita: rifà solo quella voce e la risponde. Non conta nei limiti. `400` se la formazione non è valida. Apposta, è l'unica rotta che riscrive la scelta di una giornata già chiusa (non risponde `409 formazione_chiusa`): solo per le giornate finite (`400` le altre), con la formazione schierata davvero nella lega, così il Diario confronta quella vera |
| `GET /api/affidabilita` | — | risultato dell'ultima prova del modello (vuoto se non c'è ancora) |
| `GET /api/stagione` | — | se le rose sono della stagione in corso o di una passata |
| `POST /api/nuova-stagione` | (X-Fanta) | archivia la stagione finita e riparte da rose vuote |
| `GET /api/asta` | `modo?` (`estiva` o `riparazione`) | prezzi consigliati e budget per reparto (stime) |

`GET /api/diario` ha in più, facoltativo, `motivo_vuoto` (`squadra`, `giornate` o `calcolo`: presente solo se `giornate` è vuoto, per dire all'utente cosa manca; i client vecchi lo ignorano). Il tocco su «Ho schierato la consigliata» di una voce `diario` di `da_fare` deve fare `POST /api/diario/schierata` con la `giornata` della voce e poi mostrare quella giornata nel diario (il web lo fa così).

`GET /api/diario` ha in più, facoltativo, `scelte_tue` (i client vecchi lo ignorano): le giornate in cui i tuoi undici erano diversi dai consigliati, e chi ha fatto più punti. Ogni voce di `scelte_tue.per_giornata` ha anche `giornata_lega` (dal 2/11/2026; `null` fuori dalla stagione in corso): i client scrivono «Giornata N» con `giornata_lega ?? giornata`.
`{giornate, meglio_tua, meglio_consigliata, pari, punti_differenza, percentuale_tua, pochi_dati, per_giornata[]}`. `punti_differenza` = somma di (punti tuoi − punti consigliata), positivo se hai avuto ragione tu; `percentuale_tua` = giornate in cui hai fatto più punti, su 100; `pochi_dati` = `true` sotto 8 giornate (il client dice «ancora pochi dati» e non commenta la percentuale). Ogni elemento di `per_giornata` (dalla più recente): `stagione`, `giornata`, `hai_scelto[]` e `consigliava[]` (nomi dei giocatori diversi), `punti_tua`, `punti_consigliata`, `differenza`, `esito` (`tua`, `consigliata`, `pari`). Senza scelte diverse: `{giornate: 0, pochi_dati: true, per_giornata: []}`. Conta solo dove hai dichiarato cosa hai schierato (`sintesi.giornate > 0`).

`GET /api/diario`: ogni voce di `giornate[]` ha in più, facoltativo, `istantanea`: la formazione che SchieraXI consigliava PRIMA della giornata, oppure `null` se non era stata registrata (giornate passate prima di questa novità: il client scrive «consigliata non registrata»). Forma: `{giornata, modulo, titolari[{id, nome, ruolo}] (11), panchina[{id, nome, ruolo}] (in ordine), atteso, stile, calcolata}`; `calcolata` è l'ora italiana ISO senza fuso, `stile` può mancare o essere `null`. Una per giornata (circa 1 KB), si aggiorna ogni volta che l'app chiede `GET /api/formazione` finché manca la prima partita e poi resta com'è. Nessuna rotta nuova: i client che non conoscono il campo lo ignorano. `consigliata` (la ricostruzione di oggi con i dati di allora) resta com'è e porta i punti fatti. `POST /api/diario/schierata` con `tipo: "consigliata"` usa i titolari di `istantanea` se tutti sono ancora nella rosa, altrimenti la ricostruzione. Un client mostra `istantanea` accanto a `schierata` e evidenzia i `titolari[].id` che differiscono.

Campo `intervallo` (in `/api/formazione`, `/api/oggi`, `/api/widget` e `/api/diario`): `{basso, alto, confidenza: 0.8, indicativo}`, la fascia «tra X e Y» mostrata all'utente. Il punteggio cade dentro la fascia circa 8 volte su 10. `dev` è coerente con la fascia; la vecchia deviazione resta in `dev_simulata`. Nessuna rotta nuova: è un campo aggiunto.

### Fantavoto atteso e «Perché questo numero» (facoltativi: un client vecchio li ignora)

**Nome.** Il numero firma dell'app è il **Fantavoto atteso**: il fantavoto che SchieraXI si aspetta da un giocatore in quella partita, SE gioca, con le regole della lega (in inglese «Expected fantasy score»). Nelle schede dei giocatori (`schede[]`, `titolari[]`, `panchina[]`, `fuori[]` di `/api/formazione`, `previsione` di `/api/giocatore/{id}`, `giocatori[]` di `/api/classifica`, `/api/osservati` e `/api/confronto`) è il campo **`fv_atteso`**, sempre accanto a `p_voto` («gioca N%»). Per la squadra si dice **punti attesi** (`punteggio_atteso`, `punti_attesi`). Il campo **`voto_atteso`** è un'altra cosa: il voto in pagella atteso, senza bonus e malus; i client lo chiamano «voto in pagella atteso» e non lo mostrano come numero firma. Nessun nome di campo è cambiato; l'etichetta del fattore `voto` di `/api/confronto` è ora «Voto in pagella atteso» (prima «Voto atteso»).

**Perché questo numero.** Ogni scheda ha in più:

- `perche_numero`: lista di al massimo 3 motivi, dal più pesante: `{chiave, testo, effetto}`. `chiave` è `gioca`, `partita`, `voti`, `gol`, `assist`, `rigori`, `porta` o `altro` (un client può trovarne di nuove). `testo` è una frase italiana semplice («partita favorevole in casa», «segna più della media del ruolo (50% di segnare)», «gioca il 70%: dubbio»); la web app la traduce riconoscendola, un client nativo può mostrarla così com'è. `effetto` è in **fantavoti**, con il segno, rispetto a un giocatore medio dello stesso ruolo che gioca questa giornata (`p_voto` almeno 0,5); è `null` per `gioca`, che non cambia il fantavoto atteso (è già «se gioca»: cambia i punti attesi) e va mostrato senza numero. Lista vuota = nessun motivo spicca. Un motivo compare solo se pesa almeno 0,08.
- `fv_atteso_medio_ruolo`: il fantavoto atteso del giocatore medio del ruolo (il riferimento dei pesi), oppure `null`.

I pesi vengono dai pezzi veri del calcolo (`fanta/perche.py`, usa le colonne `voto_base` e `fattore` aggiunte a `modello.previsioni`): la somma di TUTTI i pezzi è esattamente `fv_atteso` meno `fv_atteso_medio_ruolo` (la provano i test); i tre mostrati sono i più grandi. Nessun numero del modello cambia (`verifica` dà gli stessi risultati di prima). Come lo mostra la web app: nella scheda del giocatore, sotto il numero grande, e come foglio che si apre toccando il numero nella Formazione; ogni motivo è una riga «+1,1 · segna più della media del ruolo». Un client che non trova `perche_numero` (server vecchio) non mostra il riquadro.

**Diario: atteso contro fatto e affidabilità.** `GET /api/diario` ha in più:

- in ogni voce di `giornate[]`, `atteso_vs_fatto`: `{riferimento: "consigliata", atteso, fatti, scarto, nella_fascia, intervallo: {basso, alto}}` (oppure `null`). Sono i punti attesi della formazione consigliata (ricostruita con i dati di allora), quelli fatti, `scarto` = fatti meno attesi (positivo: meglio del previsto) e se i fatti sono caduti dentro la fascia «tra X e Y» (`nella_fascia`, `true`/`false`);
- in cima, `affidabilita`: `{giornate, scarto_medio, errore_medio, punti_medi_attesi, punti_medi_fatti, dentro_fascia, con_fascia, percentuale_dentro, fascia_dichiarata (80), pochi_dati, giornate_minime (8), giudizio}`. `scarto_medio` = media dei |scarti| in punti; `errore_medio` = media degli scarti con segno (negativo: i punti veri sono stati meno dei previsti); `dentro_fascia` su `con_fascia` giornate. `giudizio` è `pochi_dati` (sotto 8 giornate), `in_linea`, `sotto_le_attese` o `sopra_le_attese` (la quota dentro la fascia è sotto il 60%: il periodo è andato peggio, o meglio, del previsto). Tutto si ricalcola dalle voci del diario e va mostrato **anche quando va male**: niente numeri nascosti. Frasi suggerite: «Su 10 giornate i punti fatti sono caduti nella fascia prevista 8 volte (dichiarato: 8 volte su 10). Scarto medio 4,2 punti.» e, per `sotto_le_attese`, «Questo periodo è andato peggio del previsto».

Per l'app iPhone: leggere `perche_numero` e `fv_atteso_medio_ruolo` dalla scheda (stessi campi in `/api/formazione.schede`, `/api/giocatore/{id}.previsione`, `/api/classifica`), `atteso_vs_fatto` per voce e `affidabilita` in `/api/diario`; usare «Fantavoto atteso» al posto di «Voto atteso» nelle etichette.

**Diario: «Quanto ci abbiamo preso» (campo `precisione`).** `GET /api/diario` ha in più, facoltativo (i client vecchi lo ignorano; nessuna rotta nuova), `precisione`, calcolato SOLO dal diario di chi chiede (`fanta/precisione.py`). Tutti i numeri possono essere `null` se manca il dato:

- `giornate` (quante voci), `pochi_dati` (`true` sotto `giornate_minime` = 8: il client mostra «ancora pochi dati»), `fonti`: `{mostrati, ricostruiti}` = in quante giornate i numeri per giocatore sono quelli mostrati allora dall'app o ricostruiti con i soli dati di prima;
- `fantavoto`: `{errore_medio, scostamento, entro_un_punto, voti}` oppure `null`. `errore_medio` = media di |fantavoto vero − fantavoto atteso| sui giocatori che hanno preso voto (in punti); `scostamento` = la stessa media con il segno (positivo: hanno fatto più del previsto); `entro_un_punto` = percentuale di voti entro un punto; `voti` = quanti voti;
- `gioca`: `{giocatori, gruppi[{da, a, giocatori, pochi, detto, giocato}], principale}` oppure `null`. Fasce di «gioca N%»: 0-39, 40-69, 70-89, 90-100 (`a` è escluso, tranne 100); `detto` = media della probabilità detta, `giocato` = quota che ha preso voto davvero, entrambi in percento interi; `pochi` sotto 20 casi; ci sono solo le fasce non vuote. `principale` = indice in `gruppi` della fascia da mettere in evidenza (dal 70% in su, quella con più casi) o `null`. `fonte`: `mostrati` = solo i numeri che l'app ha mostrato davvero prima della scadenza (probabili formazioni comprese), usati quando ci sono almeno 3 giornate così; altrimenti `ricostruiti` = rifatti con i soli dati di prima, SENZA le probabili: il client deve usare un'altra frase («Con i dati disponibili prima di ogni giornata (senza le probabili formazioni), chi davamo al 98% ha giocato 8 volte su 10.», chiave `diario.qp_gioca_ric`, con l'articolo giusto: «all'83%», «all'8%», «all'11%», come `Precisione.alPercento` dell'iPhone); `giornate` = su quante giornate;
- `confronto`: `{giornate}` (0 se non c'è nessuna formazione schierata) oppure `{giornate, meglio_consigliata, meglio_tua, pari, punti, media_consigliata, media_tua}`; `punti` = somma di (consigliata − tua): positivo, seguendo sempre la consigliata avresti fatto più punti;
- `squadra`: `{giornate, punti_medi_attesi, punti_medi_fatti, scarto_medio, errore_medio, dentro_fascia, con_fascia, percentuale_dentro, fascia_dichiarata}` (gli stessi numeri di `affidabilita`) oppure `null`;
- `per_giornata[]` dalla più vecchia alla più recente: `{stagione, giornata, giornata_lega, fonte ("mostrati"|"ricostruiti"|null), errore_fantavoto, voti, attesi, fatti, tua, differenza}`; `attesi`/`fatti` della consigliata, `tua` = punti della schierata o `null`, `differenza` = consigliata − tua o `null`.

Frasi del web (chiavi `diario.qp_*` di `fanta/web/testi.js`, da copiare uguali): «In media il fantavoto atteso dei tuoi giocatori sbaglia di 1,3 punti; 6 voti su 10 sono entro un punto.» (6 = `entro_un_punto` / 10 arrotondato); «Quando diciamo «gioca 98%», ha giocato 8 volte su 10.» (98 = `detto`, 8 = `giocato` / 10 arrotondato, della fascia `principale`; se `giocato` è più di 10 punti sotto `detto` si aggiunge «Qui siamo stati troppo ottimisti», se sopra «troppo prudenti»); «Giornate in cui la consigliata ha fatto meglio della tua: 4 su 6.»; «Punti della consigliata: 72,0 previsti e 73,4 fatti, in media. Giornate dentro la fascia prevista: 5 su 8 (puntiamo a 8 su 10).». Sempre «Calcolato su N giornate» e, se `fonti.ricostruiti` > 0, la nota che quei numeri sono ricostruiti.

Novità collegate: ogni voce di `giornate[]` ha in più, facoltativo, `giocatori[{id, p_voto, fv_atteso, fv}]` (i giocatori della rosa, ricostruiti con i dati di prima; `fv` = fantavoto vero o `null` se non ha preso voto; al massimo 60) e i giocatori di `istantanea.titolari`/`panchina` hanno in più, facoltativi, `p_voto` e `fv_atteso` (quelli mostrati prima della scadenza). Con gli account il comando `affidabilita` aggiorna anche il diario di ogni utente, al massimo per `--minuti` (di norma 10; prima chi ha il diario più vecchio, gli altri al giro dopo); un utente in errore si scrive nel registro solo con il numero e il tipo di errore. Una voce con `schierata` non viene mai sostituita da una senza (blocco anche fra processi), così il comando non cancella un «Ho schierato» arrivato mentre calcolava. `python -m fanta affidabilita --pubblico [--file F]` scrive un riassunto anonimo (tutti i giocatori della Serie A, regole classiche, senza probabili; le formazioni solo con almeno 5 utenti, in percentuale e con `utenti_almeno` a scaglioni 5, 10, 25, 50, 100...; niente nomi, squadre né conteggi esatti) in `dati/affidabilita-pubblica.json`: per ora non va online.

## 4. Giocatori, mercato, calendario

| Metodo e percorso | Parametri | Risposta principale |
|---|---|---|
| `GET /api/giocatori` | `q`, `limite?`, `tutti?` | ricerca nel listone (anche senza accenti, e per nome proprio: «Lautaro»). Ogni elemento può avere `nome_completo` (facoltativo, solo per chi lo ha: nome e cognome per esteso, es. «Lautaro Martínez» per «Martinez L.»): un client che cerca sul dispositivo con `tutti=1` lo usa come secondo nome da confrontare |
| `GET /api/giocatore/{id}` | — | scheda del giocatore: previsione, forma, voti, statistiche (`id` oltre 2147483647: 422) |
| `GET /api/avatar` | — | `{versione: 3, tratti: {"<id>": {p?, c?, a?, b?, f?}}}`: tratti dei volti illustrati di tutti i giocatori che li hanno (dati comuni; vedi «GET /api/avatar» più sotto) |
| `GET /api/mercato` | `squadra?` | Consigliati e proposte di cambio. `proposte` ha solo i cambi che passano il buon senso (campi facoltativi `sensato` = true e `motivo`, una frase); `scartate` (facoltativo, al massimo 5) i cambi che i numeri promuovono ma che un allenatore non farebbe, con `sensato` = false e il `motivo` per cui no. I client vecchi li ignorano |
| `GET /api/classifica` | `ruolo?`, `liberi?`, `limite?` | giocatori della giornata per punti attesi |
| `GET /api/calendario` | — | prossime partite e difficoltà |
| `GET /api/osservati` | — | i giocatori osservati con la previsione (ETag); a giornata iniziata lo stato vero della partita, come la Rosa (vedi «A giornata iniziata») |
| `PUT /api/osservati/{i}` | `i` (X-Fanta, If-Match) | segui il giocatore `i` (da 1 a 2147483647, altrimenti 422). Solo giocatori del listone: un codice che non c'è risponde `404` «Giocatore non trovato nel listone» e non si salva (dal 2/11/2026). I codici non validi già salvati si ignorano in lettura e si tolgono al salvataggio dopo (non occupano i 60 posti) |
| `DELETE /api/osservati/{i}` | `i` (X-Fanta, If-Match) | smetti di seguirlo |

## 5. Scambi, squadre, rose, regole

Gli scambi usano gli id dei giocatori, separati da virgola (per esempio `do=101,205`). Un elenco non valido dà `400`.

| Metodo e percorso | Parametri o corpo | Risposta principale |
|---|---|---|
| `GET /api/scambi/proposte` | `con?`, `due?`, `fino_a?` (2-4) | scambi vantaggiosi per tutti e due. Risposta con `giornate`, `proposte` e `ricerche` (contatore: `restano`, `tetto`). Conta nel tetto giornaliero (60 al giorno per gli utenti normali; l'amministratore non ha limiti); una ricerca identica a una già fatta oggi non conta di nuovo |
| `GET /api/scambi/limite` | — | quante ricerche di scambi restano oggi: `{restano, tetto}`. Entrambi `null` = nessun limite (amministratore o senza account). Non consuma niente |
| `GET /api/scambi/analizza` | `con`, `do`, `ricevo`, `conguaglio?`, `completo?` | analisi di uno scambio. Con `conguaglio` (crediti, positivo = li ricevi tu) o `completo=true`: validità delle rose, panchina, valore dei crediti e giudizio. Vale da 1 a 4 giocatori per parte, anche in numero diverso. Non conta nel tetto. Se il conguaglio non si può fare (`conguaglio.valido: false`: fondi che non bastano o crediti oltre il limite) `conguaglio.dopo` vale `{mio: null, loro: null}`, `valore_mio` e `valore_loro` sono `null` e `netto_*` è uguale a `guadagno_*` (dal 2/11/2026) |
| `POST /api/scambi/da-testo` | `{testo, con?, completo?}` (X-Fanta) | trova i giocatori in un messaggio scritto a parole (risponde sempre anche con `ids` `{do, ricevo}`). Con `completo=true` non fa l'analisi semplice: `analisi` è `null` e l'analisi completa si chiede a `analizza`. Senza `completo`, se l'analisi semplice non si può fare (numero di giocatori o ruoli diversi tra le due parti) `analisi` è quella completa di `analizza` senza conguaglio (stessi campi più `completo`, `valido`, `giudizio`...; prima era un 400, dal 2/11/2026). Se nemmeno così lo scambio si può fare (rose non valide) resta un 400, ora con i motivi: «Così com'è lo scambio non si può fare: ...». L'analisi (semplice o completa) ha gli stessi limiti di `analizza` (`limiti.analisi_scambio`: al minuto per utente e analisi contemporanee): oltre, `429` con `Retry-After` (dal 2/11/2026); con `completo=true` non c'è analisi e non conta |
| `GET /api/squadre` | — | squadre della lega, con crediti e numero di giocatori (ETag) |
| `GET /api/rosa` | `squadra?` | rosa di una squadra (ETag) |
| `PUT /api/mia-squadra` | `{nome}` (X-Fanta, If-Match) | indica la tua squadra |
| `PUT /api/squadre/nome` | `{nome, nuovo}` (X-Fanta, If-Match: lo stesso ETag delle rose) | cambia il nome di una squadra dopo l'importazione (dal 2/11/2026). `nome` = il nome di adesso per intero (maiuscole a parte, niente inizio del nome); `nuovo` = da 1 a 60 caratteri, gli spazi in più diventano uno. Seguono il nome: la squadra nelle rose, «la tua squadra», stemma e maglia; lo storico dei movimenti resta com'era. Risposta `{nome, prima, mia_squadra}` con il nuovo `ETag` delle rose. `400` nome non valido, `404` squadra che non c'è, `409` c'è già una squadra con quel nome (oppure il nome si confonde con quello di un'altra squadra per stemma e maglia, per esempio nomi di soli simboli: il messaggio lo dice), `412` rose cambiate da un altro dispositivo. La squadra ricorda il nome di Leghe (`nome_importato` nel file delle rose): alla reimportazione la squadra con quel nome aggiorna la squadra rinominata (anteprima compresa, che mostra già il nome dell'app), e «la tua squadra» resta giusta. Se il salvataggio non riesce, stemma e maglia tornano al nome di prima |
| `PUT /api/crediti` | `{crediti: {squadra: numero}}` (X-Fanta, If-Match) | crediti residui |
| `POST /api/rose/anteprima` | `{testo, sostituisci_tutto?, correzioni?}` (X-Fanta) | come l'importazione ma **non salva niente**: cosa capirebbe, giocatore per giocatore (vedi «Anteprima delle rose» qui sotto). Risponde con l'`ETag` delle rose da rimandare in `If-Match` all'importazione |
| `POST /api/rose/anteprima/file` | file multipart `file`; `sostituisci_tutto?` (query); campo `correzioni?` (testo JSON) (X-Fanta) | la stessa anteprima per un file (gli stessi formati di `/api/rose/file`) |
| `POST /api/rose/testo` | `{testo, sostituisci_tutto?, correzioni?, mia_squadra?}` (X-Fanta, If-Match) | importa le rose da testo incollato (anche CSV «rosters»). `correzioni` e `mia_squadra` sono facoltativi (dal piano «Ingresso facile»): senza, risponde come sempre |
| `POST /api/rose/file` | file multipart `file`; `sostituisci_tutto?` (query); campi del modulo facoltativi `correzioni` (testo JSON) e `mia_squadra` (X-Fanta, If-Match) | importa da Excel (`.xlsx`) o da testo (CSV, TSV, TXT). Risposta con `riepilogo` (cosa è cambiato). File oltre 5 MB o vuoto: `400`. Con gli account accesi: `.xlsm` (macro) rifiutato e massimo 1500 righe e 60 colonne, con `400` e il motivo in italiano |
| `POST /api/rose/correggi` | `{squadra, nome, id}` (X-Fanta, If-Match) | abbina a mano un giocatore non riconosciuto |
| `GET /api/movimenti` | `limite?` (massimo 300) | storico di scambi, svincoli e tagli, dal più recente |
| `GET /api/regole` | — | regole della lega (ETag) |
| `PUT /api/regole` | corpo = regole complete (X-Fanta, If-Match) | salva le regole, dopo i controlli di `regole.da_dict` |
| `POST /api/regole/riconosci` | `{testo}` (massimo 30000 caratteri) | propone i valori letti dal regolamento incollato. Non salva niente |
| `PUT /api/regole/rinvio` | `{giornata, modo, stagione?}` (X-Fanta, If-Match facoltativo, stesso ETag delle regole) | partite rinviate: decisione per UNA giornata, che vince sulla regola della lega (vedi «Partite rinviate» qui sotto) |

### Anteprima delle rose (`fanta/anteprima_rose.py`)

Flusso per i client: 1) `POST /api/rose/anteprima` (o `/anteprima/file`) con il testo o il file; 2) l'utente sceglie i dubbi e la sua squadra;
3) `POST /api/rose/testo` (o `/file`) con **lo stesso contenuto**, `correzioni`, `mia_squadra` e `If-Match` = l'`ETag` dell'anteprima (se nel frattempo
le rose sono cambiate: `412`). L'anteprima non scrive niente; il testo non va nei log.
Conteggio: anteprima + importazione dello stesso contenuto contano una sola importazione; se quell'importazione fallisce, il
«buono» torna **una volta al giorno** per lo stesso contenuto, poi ogni nuovo tentativo conta come sempre.
File Excel: il server ne legge **uno alla volta** (anteprime e importazioni di tutti insieme); se un altro è in lettura, dopo
qualche secondo risponde `503` con `Retry-After` e il messaggio «riprova tra poco». Quel `503` non consuma niente (né
importazioni né anteprime, né il buono): il client riprova più tardi con la stessa richiesta. I `503` gratuiti sono al massimo
30 all'ora per utente (`limiti.MAX_EXCEL_OCCUPATO_ALL_ORA`): oltre, risposta immediata `429` con `Retry-After` (e
l'importazione tentata conta come le altre).

Risposta dell'anteprima:
- `squadre`: una voce per squadra letta, nell'ordine del testo: `nome`, `nuova` (non c'era tra le rose salvate), `crediti_residui`,
  `sicuri`, `da_controllare`, `non_trovati` (conteggi), `totale` e `attesi` (giocatori letti e quelli della rosa nelle regole),
  `ruoli` (`{"P": n, "D": n, "C": n, "A": n}`), `mancano` e `in_piu` (solo i ruoli che non tornano, es. `{"P": 1}`), `senza_ruolo`,
  `completa` (bool), `avvisi` (frasi brevi senza il nome della squadra), `giocatori`.
- ogni giocatore: `testo` (il nome come scritto nel file: è la chiave per le `correzioni`), `stato`, `metodo` (`esatto`, `abbreviato`,
  `simile`, `ambiguo`, `non trovato`, `manuale`), `id`/`nome`/`ruolo`/`squadra` (il giocatore proposto; `id` e `nome` `null` se nessuno),
  `costo`, `avviso` (es. «squadra diversa: …», può essere vuoto), `alternative` (`[{id, nome, ruolo, squadra}]`: per `da_controllare`
  i candidati, se c'è una proposta è la prima; per `non_trovato` fino a 3 nomi somiglianti da suggerire, nessuno scelto in partenza; vuoto per `sicuro`).
- nomi scritti per esteso: «Lautaro Martinez», «Martinez Lautaro», «Pulisic C.» (iniziale in più) diventano `da_controllare` con la proposta, mai `sicuro`,
  a meno che la riga abbia anche ruolo E squadra di Serie A uguali al listone (vedi sotto).
- `stato`: `sicuro` = nome uguale nel listone con ruolo e squadra compatibili (o scelto a mano), oppure nome abbreviato («Martinez», «Martinez L»,
  «Esposito F.») con ruolo E squadra indicati uguali al listone e un solo giocatore che va bene (`metodo` resta `esatto`);
  `da_controllare` = trovato per somiglianza o abbreviazione, ambiguo tra più giocatori, oppure con ruolo o squadra diversi (con ruolo o squadra
  diversi dal listone non è MAI `sicuro`); `non_trovato` = nessuno (ceduto, nome sbagliato, codice sconosciuto).
- Errori di lettura tollerati (testo da OCR) solo se il nome resta di un giocatore solo del listone: accenti persi o cambiati («Kone M.» per «Koné M.»),
  punti mancanti dopo le iniziali, spazi doppi o persi («NDicka», «Esposito FP»), apostrofi e trattini persi, «0» al posto di «O», «1» al posto di «l»/«i».

### Rose a colonne «ruolo;nome;club;prezzo» (testo incollato)

Formato di testo accettato dal server. È nato per la lettura degli screenshot di Leghe nell'app iPhone (tolta il 2/11/2026) e resta per
il testo incollato. Per `POST /api/rose/anteprima` e `POST /api/rose/testo` (campo `testo`). Una riga per voce, celle separate da `;`, UTF-8:

```
ruolo;nome;club;prezzo
FC Esempio 17,5
P;Ferrandi Jo.;INT;12
D;Brahmeri;Napoli;20
A;Ferrandi L.;Inter;40
crediti;37
Real Esempio
C;Kone M.;Roma;9
```

- **Prima riga** obbligatoria: l'intestazione `ruolo;nome;club;prezzo` (anche `squadra` al posto di `club` e `costo` al posto di `prezzo`;
  il prezzo può mancare: `ruolo;nome;club`). È lei che attiva questo formato a colonne fisse; senza, il testo passa dal lettore generico.
- **Riga con una cella sola** (senza `;`) = nome della fantasquadra, com'è: virgole, numeri e spazi restano («FC Esempio 17,5»).
  Le righe che seguono sono i suoi giocatori fino alla prossima squadra. Il nome della squadra non deve contenere `;`.
- **Giocatore**: `ruolo;nome;club;prezzo`. `ruolo` = `P`, `D`, `C` o `A` (anche `Por`, `Dif`, `Cen`, `Att`); `nome` come lo scrive Leghe
  («Martinez L.», «Martinez Jo.», «Milinkovic-Savic V.», «N'Dicka»); `club` = la squadra di Serie A in sigla («INT») o per esteso
  («Inter», «Hellas Verona»); `prezzo` = crediti d'acquisto, solo cifre (si accettano «12 cr» e la «O» letta al posto dello zero). Club e prezzo
  possono essere vuoti (`D;Brahmeri;;`), ma senza club e ruolo un nome abbreviato resta `da_controllare`.
- `crediti;N` (facoltativa, dopo i giocatori di una squadra) = crediti residui di quella squadra.
- Righe che non tornano (ruolo che non è P/D/C/A, nome vuoto) non si indovinano: finiscono in `avvisi` («Riga N: ignorata (…): mi aspettavo «ruolo;nome;club;prezzo»…», chiave `rose.riga_schermate_ignorata`). Le righe vuote si saltano.
- Niente virgolette da togliere: le celle si leggono così come sono (niente regole CSV).
- Ruolo e squadra servono a riconoscere i nomi: con tutti e due uguali al listone un nome abbreviato è `sicuro`; se uno dei due non torna
  il giocatore è `da_controllare`, con l'avviso «ruolo diverso: indicato X, nel listone Y» / «squadra diversa: indicata X, nel listone Y»,
  oppure un dubbio tra gli omonimi con quello che ha ruolo e squadra giusti per primo.
- Stessi tetti del testo incollato (200 mila caratteri, 1500 righe) e stesse risposte dell'anteprima.
- in tutto: `avvisi` (lettura del file, rose incomplete o con ruoli che non tornano, giocatori in più squadre, «una sola squadra»), `mia_squadra`
  (suggerita: quella già scelta se è tra le lette o se resta com'era perché il file ha solo le rose degli altri, oppure l'unica letta;
  altrimenti `null`; può quindi non essere tra `squadre`: il client la offre comunque nella scelta), `totale_squadre` (dopo l'importazione),
  `sicuri`, `da_controllare`, `non_trovati`, `differenze` e `riepilogo` (come la risposta dell'importazione: cosa cambierebbe).
  `differenze` ha anche `squadre_nuove` e `squadre_tolte` (elenchi di nomi): con squadre aggiunte o tolte `nessuna_differenza` è falso.
  Un giocatore ripetuto nella stessa rosa si tiene una volta sola, con un avviso («… compare due volte, l'ho tenuto una volta sola»).

`correzioni` (anteprima e importazione): `[{squadra, testo, id}]`, al massimo 800; `squadra` e `testo` come nell'anteprima, `id` = codice
del listone oppure `null` per togliere quella riga. Il giocatore scelto entra con il ruolo e la squadra del listone e `riconosciuto: "manuale"`.
Nel multipart il campo `correzioni` è lo stesso elenco scritto come testo JSON (JSON non valido: `422`). Una scelta che non corrisponde più al
testo, o un `id` fuori listone: `400` con il messaggio, e niente si salva. `mia_squadra` che non c'è tra le rose: `400`.
Si può cominciare con la sola propria rosa: una squadra sola non è un errore (solo un avviso, testo `lega.UNA_SQUADRA`: «Con una sola squadra funzionano formazione e consigli; per gli scambi servono le rose degli altri: potrai aggiungerle quando vuoi.»).

Limiti (solo con gli account): l'anteprima conta tra le 10 importazioni al giorno, ma anteprima e importazione dello **stesso** contenuto
(stesso testo o stesso file) contano una volta sola, e rifare l'anteprima dello stesso contenuto (per esempio con le `correzioni`) non conta di
nuovo; se l'importazione pagata dall'anteprima fallisce (`400` sulle scelte, `412`), riprovare con lo stesso contenuto resta gratis;
un'anteprima rifiutata per il tetto (`429`) non paga niente; in più al massimo 30 anteprime all'ora (`429` con `Retry-After`). Stessi tetti di dimensione dell'importazione (200 mila caratteri,
1500 righe, 60 colonne, file fino a 5 MB, `.xlsm` rifiutato) e stessi tetti di squadre e giocatori. Il testo incollato ha il tetto anche senza account.

## 6. Stemma e maglia, condivisione

| Metodo e percorso | Parametri o corpo | Risposta principale |
|---|---|---|
| `GET /api/squadre/immagine` | `squadra`, `tipo` (`stemma` o `maglia`) | l'immagine (`404` se non c'è), con `Cache-Control: private` (dati personali). Dopo un'importazione si tolgono stemmi e maglie di squadre che non ci sono più: una squadra nuova con lo stesso nome non li eredita |
| `POST /api/squadre/immagine` | `squadra`, `tipo`; file multipart `file` (X-Fanta) | carica da file. PNG, JPEG o WebP, massimo 4 MB, riconosciuti dal contenuto |
| `POST /api/squadre/immagine/da-url` | `{squadra, tipo, url}` (X-Fanta) | scarica da un indirizzo `https` pubblico. Niente reti private, massimo 4 MB, 30 al giorno |
| `DELETE /api/squadre/immagine` | `squadra`, `tipo` (X-Fanta) | toglie l'immagine (anche se non c'era: `200`) |
| `POST /api/squadre/immagine/condivisa` | file multipart `immagine` | ricevuta dal menu Condividi del telefono (vedi sotto). Risponde `303` |
| `GET /api/squadre/immagine/in-attesa` | — | l'immagine ricevuta dal menu Condividi, non ancora assegnata (`404` se non c'è) |
| `DELETE /api/squadre/immagine/in-attesa` | (X-Fanta) | scarta l'immagine in attesa |

**Condivisione dal telefono**: il manifest della web app dichiara `share_target` verso `/api/squadre/immagine/condivisa`. Il sistema manda la richiesta senza `X-Fanta` (è l'unica eccezione): serve però la sessione e la richiesta deve venire dallo stesso sito. La risposta è `303` verso `/?condivisa=1` (o `/?condivisa=no` se non è andata bene).

## 7. Avvisi, notifiche, backup, onboarding

| Metodo e percorso | Parametri o corpo | Risposta principale |
|---|---|---|
| `GET /api/avvisi` | — | impostazioni degli avvisi, con lo stato dei canali (ETag). L'ETag cambia solo quando cambiano gli avvisi: «Mostra tutte», il primo avvio e lo scarico del backup non lo toccano, quindi non fanno più comparire un `412` falso al salvataggio |
| `PUT /api/avvisi` | campi facoltativi: `cambi`, `promemoria_60`, `promemoria_15`, `riepilogo`, `copertura` (booleani; `copertura` = avviso «reparto della rosa scoperto o senza ricambi», acceso di base, titolo «SchieraXI · un reparto della rosa è scoperto» o «… è a rischio», una volta sola per giornata, reparto e gravità, tag `no_entry`, quindi `sezione` = `mercato` nella push e `schieraxi://mercato` su ntfy; compare anche nelle impostazioni lette con `GET /api/avvisi`), `app_nativa`, `silenzio` (booleano), `silenzio_da`, `silenzio_a` (ore 0-23), `avviso_prima` (intero: 0, 30, 60 o 90; vedi «Avviso "cambia la formazione"» sotto la tabella; altri valori: 422) (X-Fanta, If-Match) | impostazioni salvate. Si mandano solo i campi cambiati. I promemoria (`promemoria_60`, `promemoria_15`) non partono se per la giornata c'è già una scelta salvata (`/api/scelta`, anche «ho schierato la consigliata») e nessun suo titolare è fuori o in panchina nelle probabili. Con `silenzio` acceso e `silenzio_da` uguale a `silenzio_a`: 422 con messaggio chiaro, niente viene salvato. Se un salvataggio vecchio ha già ore uguali, `GET /api/avvisi` le dà per spente (`silenzio` falso) e aggiunge `ore_tranquille_spente: true` finché non si salva di nuovo; i client che non lo conoscono lo ignorano, quelli nuovi possono mostrare un avviso. L'opzione `cambi` governa anche l'avviso «cambio pronto» (titolo «SchieraXI · cambio pronto», stesso tag `rotating_light` degli altri cambi, quindi `sezione` = `formazione` nella push e `schieraxi://formazione` su ntfy): nessun campo, rotta o tag nuovo, i client non devono fare niente |
| `POST /api/avvisi/prova` | — (X-Fanta) | manda un avviso di prova. `409` se non c'è nessun canale attivo |
| `GET /api/push/chiave` | — | la chiave pubblica per le notifiche web |
| `POST /api/push/iscrivi` | `{endpoint, keys}` (X-Fanta) | iscrive il dispositivo. L'`endpoint` deve essere https sulla porta 443, senza nome utente, con un nome di sito normale (o un IP pubblico) che porta solo a indirizzi pubblici di internet; altrimenti 400. Un servizio ntfy su altra porta o dietro una rete privata non è accettato |
| `POST /api/push/disiscrivi` | `{endpoint}` (X-Fanta) | toglie il dispositivo. Risposta `{dispositivi}` |
| `GET /api/backup` | — | file JSON con regole, rose, scelte, osservati e impostazioni degli avvisi. Niente chiavi né iscrizioni. Con gli account: SOLO i file di chi ha la sessione (nessun parametro). È la rotta di «Impostazioni > Il tuo account > Scarica i tuoi dati» (portabilità, dal 1/11/2026): `{formato, versione, creato, file: {"lega/regole.json": …, "lega/rose.json": …, "lega/movimenti.json": …, "dati/scelte.json": …, "dati/osservati.json": …, "dati/avvisi-impostazioni.json": …}}` (i file che mancano non ci sono); header `Content-Disposition: attachment`. Con gli account c'è in più la sezione facoltativa `account` (fuori da `file`): `{nome_visualizzato, nome_utente, email (o null), email_verificata, creato, ruolo, accesso_con_password, accessi_collegati: [{servizio: "google" | "apple", email (o null), collegato}], termini: {accettati, versione} (null per chi si è iscritto prima), impostazioni: {mostra_tutte_le_funzioni?, procedura_guidata?: {tipo, stato, passo, demo, aggiornata}}}` (i campi con `?` possono mancare). Se il database degli account non si legge, la sezione `account` manca e il resto del file esce lo stesso. Mai hash, token, sessioni, codici, identificativi dei servizi esterni né impronte di indirizzi. `POST /api/backup/ripristina` ignora `account` (l'account non si cambia da qui). Il token del widget riceve 403 |
| `POST /api/backup/ripristina` | il file di backup (X-Fanta) | controlla tutto prima; se qualcosa non va non cambia niente. Salva prima lo stato di prima. Le voci di `dati/scelte.json` delle giornate già chiuse (scadenza passata, come il `409 formazione_chiusa`; stagioni passate comprese) restano come sono sul server, le altre si ripristinano (dal 2/11/2026). Risposta: `{ripristinati: [nomi dei file], formazioni_chiuse_tenute, messaggio}`; `formazioni_chiuse_tenute` (facoltativo, booleano) è vero se il backup avrebbe cambiato una giornata chiusa, e allora `messaggio` (facoltativo, frase per l'utente) lo dice: «Dati ripristinati. Le formazioni delle giornate già chiuse non sono state cambiate.» |
| `GET /api/icona` | — | impostazioni dell'icona della web app |
| `PUT /api/icona` | (X-Fanta) | sceglie il colore dell'icona |
| `GET /api/onboarding` | — (solo con gli account) | a che punto è la procedura guidata di chi chiede |
| `PUT /api/onboarding` | `{passo?, stato?, tipo?}` (X-Fanta) | aggiorna il passo |
| `POST /api/onboarding/regole` | `{testo}` (X-Fanta) | propone le regole da un regolamento incollato, senza salvare |
| `GET /api/onboarding/controlli` | — | le spunte prima della prima formazione: `[{id, titolo, ok, obbligatorio, dettaglio}]`. Dal 2/11/2026 `rose` (obbligatoria) basta con **una** squadra; voce nuova `altre_squadre` (non obbligatoria: un avviso, `dettaglio` = il testo di una squadra sola). I client che mostrano solo le obbligatorie non cambiano niente |
| `POST /api/onboarding/demo` | (X-Fanta) | crea una lega di prova. `409` se hai già rose vere |
| `DELETE /api/onboarding/demo` | (X-Fanta) | toglie la lega di prova (solo se è davvero quella di prova) |

**Avviso "cambia la formazione"** (dal 1/11/2026). Campo `avviso_prima` nelle impostazioni di `GET/PUT /api/avvisi`: da quanti minuti prima della scadenza della formazione il server guarda se il consiglio è cambiato (`0` = spento, `30`, `60`, `90`; di base `60`). Da quel momento, se le ultime probabili cambiano la formazione consigliata rispetto al riferimento (la scelta salvata della giornata, anche «ho schierato la consigliata»; senza scelta, la consigliata com'era prima che si aprisse la finestra) e la nuova vale almeno 1 punto atteso in più (`notifiche.SOGLIA_AVVISO_PUNTI`), parte un avviso: titolo «SchieraXI · cambia la formazione» (con scelta salvata) o «SchieraXI · cambia la formazione consigliata», testo con il motivo in una frase, priorità 4, tag `rotating_light` (come i cambi). Al massimo 2 per giornata, mai lo stesso consiglio due volte, mai nelle ore tranquille (riprova dopo, finché la formazione è aperta); il promemoria della stessa finestra non riparte se l'avviso è arrivato da meno di 20 minuti. Lo manda il giro dei promemoria del server (ogni 10 minuti). Testi in italiano, come gli altri avvisi.
Niente doppioni con l'avviso dei cambi (opzione `cambi`): dentro la finestra il giro dei cambi prova prima l'avviso nuovo; «cambi nelle probabili» e «cambio pronto» sui tuoi giocatori tacciono solo se l'avviso nuovo è partito negli ultimi 15 minuti con i dati di adesso (campo `versione_inviato` nello stato dell'avviso), e lo stato si salva lo stesso, quindi non ripartono dopo; le righe degli osservati sì. Se l'avviso nuovo non parte (già due invii, guadagno sotto un punto, dati più nuovi) i cambi si dicono come sempre; se uno dei due è partito da meno di 15 minuti (`notifiche.DOPPIONE_CAMBI`, campo `inviato` nello stato dei cambi), l'avviso nuovo non ripete la stessa notizia. Con `avviso_prima: 0` i cambi restano come prima.
Le righe dei cambi nelle probabili sono a parole, senza la percentuale della fonte (dal 2/11/2026, come le etichette: all'utente una sola percentuale, «gioca N%»): «dalla formazione titolare alla panchina», «ora titolare», «ora in ballottaggio per partire titolare» e «ora probabile titolare» (un titolare che scende sotto il 60% delle probabili o risale sopra; prima: «probabilità di partire da X% a Y%» a ogni salto di 30 punti).
Dove porta il tocco: Web Push manda `sezione: "formazione"` e (novità) `url: "/?vista=formazione"` per tutti gli avvisi con sezione `formazione`, prima era `"/"`; ntfy (`app_nativa`) apre `schieraxi://formazione`.
**Lingua degli avvisi** (dal 2/11/2026). Campo `lingua` (`"it"` o `"en"`, predefinito `"it"`) nelle impostazioni di `GET/PUT /api/avvisi`: i testi degli avvisi sul telefono (cambi, cambio pronto, promemoria, «cambia la formazione», reparto scoperto, riepilogo, formazione pronta, prova) li scrive il server in questa lingua, perché l'iPhone mostra la notifica così com'è. Vale per ogni utente (le impostazioni sono sue). Un client che cambia lingua manda `PUT /api/avvisi` con `{"lingua": "en"}`: i campi non mandati non cambiano. Un valore diverso da `it`/`en`: 422. La web app lo manda quando l'utente cambia lingua; l'app iPhone, che oggi è solo in italiano, non deve fare niente e le notifiche restano in italiano; quando avrà l'inglese dovrà mandare `lingua` allo stesso modo. La lingua delle notifiche non dipende da `Accept-Language`.

Cosa devono fare gli altri client: **app iPhone** aggiungere `avviso_prima: Int?` (facoltativo) a `ImpostazioniAvvisi` e mostrarlo come scelta a 4 valori («Spento», «30 minuti prima», «1 ora prima», «1 ora e mezza prima»; titolo «Avviso se il consiglio cambia»); se è `nil` (server vecchio) non mostrarlo e non rimandarlo. Il tocco sull'avviso arriva già come `schieraxi://formazione` (gestito oggi): niente da fare. **Android** (UnifiedPush): `sezione` è già `formazione`, niente da fare; la scelta come su iPhone quando l'app riparte. Un client che non conosce il campo non lo manda e il server tiene il valore salvato.

## 8. Codici di risposta ed errori

| Codice | Quando | Corpo e intestazioni |
|---|---|---|
| `200` | risposta normale | — |
| `202` | il risultato non è ancora pronto (calcolo in coda, o widget senza risultato in cache) | `{"calcolo": "in_corso", "detail", "riprova_tra"}` + `Retry-After`. Il client riprova dopo `riprova_tra` secondi |
| `303` | ricezione dal menu Condividi | `Location: /?condivisa=1` |
| `304` | `GET /api/widget` con lo stesso ETag | nessun corpo |
| `400` | valore non valido (per esempio elenco di giocatori sbagliato, o dati non accettati) | `{"detail"}`, a volte con `codice` (`formazione_non_valida`, vedi `POST /api/formazione/valuta`). Se il motivo non è un messaggio pensato per l'utente: `{"detail": "La richiesta non è valida: controlla i dati e riprova.", "id_errore"}` (`id_errore`, 8 caratteri, ritrova il caso nel registro del server; i client possono ignorarlo) |
| `401` | nessuna sessione (con gli account accesi), token del widget scaduto o revocato, password sbagliata | `{"detail": "Accesso richiesto", "multiutente", "registrazione"}` o il messaggio dell'errore |
| `403` | manca `X-Fanta`; richiesta da un altro sito; account spenti e richiesta non diretta dal computer del server; token del widget su una rotta che non è sua; funzione solo per l'amministratore; invito non valido; registrazioni chiuse; password attuale sbagliata | `{"detail"}` |
| `404` | cose che non ci sono (immagine, squadra, giocatore, foto) o account non attivi | `{"detail"}` |
| `409` | azione non possibile adesso (nessuna rosa importata, nessun canale per gli avvisi, lega di prova da togliere o sostituire, formazione già chiusa) | `{"detail"}`; per la formazione chiusa anche `codice: "formazione_chiusa"` (salvare o togliere la scelta dopo la scadenza) |
| `411` | richiesta «chunked» senza lunghezza su rotte degli account | `{"detail"}` |
| `412` | `If-Match` non corrisponde all'ETag attuale: qualcuno ha cambiato i dati | `{"detail": "Questi dati sono stati cambiati da un altro dispositivo..."}` + `ETag` della versione attuale. Il client ricarica e rifà la modifica |
| `413` | corpo troppo grande (12 MB; 8 KB sugli account; 5 MB di dati per utente) | `{"detail"}` |
| `422` | dati non validi. Dal 1/11/2026 `detail` è una frase sola per l'utente; i campi che non vanno (mai i valori, per le password) stanno in `campi` (facoltativo; `corpo` = il corpo non è JSON). Ogni parametro `giornata` (query o corpo: `/api/formazione`, `/api/formazione/valuta`, `/api/scelta`, `/api/diario/schierata`, `/api/confronto`) va da 1 a 100: fuori, `422` con `campi: ["giornata"]` (prima un numero enorme dava `500`, dal 2/11/2026) | `{"detail": "Alcuni dati non sono validi: controlla quello che hai scritto e riprova.", "campi": ["silenzio_da"]}` |
| `429` | troppe richieste, tentativi di accesso, tetto giornaliero raggiunto, richiesta pesante già in corso | `{"detail"}` (sulle rotte degli account anche `riprova_tra`, in secondi) + `Retry-After` (secondi) |
| `500` | errore imprevisto | `{"detail": "Errore interno del server: riprova..."}`. La traccia resta nel registro del server, non nella risposta |
| `503` | database degli account non leggibile, o server occupato | `{"detail"}` + `Retry-After` quando serve |
| `507` | il server ha finito lo spazio su disco e non ha salvato (dal 1/11/2026; prima era un `500`). I dati salvati prima restano intatti | `{"detail": "Il server ha finito lo spazio e non è riuscito a salvare: riprova più tardi. ..."}`. Da mostrare così, senza riprovare da soli |

Per il client: `401` vuol dire «torna all'accesso»; `202` e `429` vogliono dire «riprova dopo `Retry-After`»; `412` vuol dire «ricarica e rifai».

## 9. Client e intestazioni

- **Web app** (`fanta/web/app.js`): cookie di sessione; `X-Fanta: 1` su ogni scrittura; `Accept-Language` con la lingua scelta nell'app (`it` o `en`) su ogni richiesta.
- **App iOS** (`ios/`): `Authorization: Bearer` con il token di sessione (salvato nel Keychain). Il widget usa il token `fw_` salvato nel contenitore condiviso.

Nessun client deve contenere indirizzi del server, chiavi o password nel codice. L'indirizzo lo chiede l'app al primo avvio.
# API di SchieraXI: contratti per i client (web, iOS, Android)

Le regole generali (intestazione `X-Fanta: 1` sulle scritture, errori `{"detail": "..."}`, 202 «sto calcolando», 429, ETag) e l'elenco di tutte le rotte
stanno in `MAPPA.md`, sezione «Contratti delle API». Qui i contratti nuovi o più delicati, uno per sezione. Regola per tutti i client:
si possono aggiungere campi, non togliere né cambiare quelli esistenti; un client ignora i campi che non conosce.

## GET /api/avatar: tratti dei volti, contratto versione 3

Risposta: `{"versione": 3, "tratti": {"<id calciatore>": {...}}}`. Lo stesso oggetto, solo per chi ce l'ha, è nel campo facoltativo `avatar` di ogni elemento di `GET /api/giocatori` e di `GET /api/giocatore/{id}`.
Ogni campo del giocatore è facoltativo; un campo mancante o non valido si ignora (il client non deve mai fallire):
- `p` (intero 0-6): carnagione, indice della tabella «pelle» di `docs/AVATAR.md` (0-6: dalla più chiara alla più scura). Il server oggi manda solo 1-6, a grana grossa.
- `c` (0-7): colore dei capelli. `a` (`"R"`, `"C"`, `"L"`, `"I"`): famiglia di acconciatura. `b` (0 o 1): barba no/sì.
- `f` (0 o 1): barba folta (`1`) o leggera (`0`); ha senso solo con `b = 1` e senza `b = 1` va ignorato.
Novità della versione 3 rispetto alla 2: `p` torna (era stato tolto) e c'è `f`. **Cosa devono fare iOS e Android:** leggere `p` e `f` e applicarli come in `docs/AVATAR.md` sezione 8; per un giocatore senza `p`
la carnagione è SEMPRE quella neutra fissa (indice 2), mai quella estratta dal seme. Un client della versione 2 continua a funzionare (ignora `p` e `f`), ma i suoi volti saranno diversi da quelli del web.
Nella versione pubblica del progetto la risposta ha `tratti` vuoto: tutti i volti hanno la carnagione neutra.

## GET /api/oggi: campo `probabili` (freschezza delle probabili)

Campo nuovo e facoltativo (i client vecchi lo ignorano): `null` se mancano le probabili (`con_probabili: false`) o l'ora di lettura.
Altrimenti `{aggiornate_il, minuti_fa, eta, testo, vecchie, avviso}`:
- `aggiornate_il`: ora italiana dell'ultima lettura, `"2026-10-31 13:05"`;
- `minuti_fa`: intero; `eta`: «2 ore fa» (plurali già giusti); `testo`: «Probabili aggiornate alle 13:05» (anche «ieri alle ...», «il 28/10 alle ...»);
- `vecchie`: `true` se hanno almeno 6 ore e la formazione si chiude entro 24 ore (mai a giornata iniziata); `avviso`: frase pronta da mostrare quando `vecchie` è `true`, altrimenti `null`.
I client mostrano `testo` + `eta` in una riga piccola e, se `vecchie`, `avviso` in evidenza. Lo stesso campo (`null`) c'è in `/api/oggi` senza rose.

## Tempi della lega: scadenza della formazione e prima giornata

Due impostazioni della lega, dentro `GET/PUT /api/regole` (campi nuovi, facoltativi: se un client vecchio rimanda le regole senza, il server tiene i valori che c'erano):
- `scadenza_minuti` (intero 0-720, predefinito 0): la formazione si chiude tanti minuti PRIMA dell'inizio della prima partita della giornata.
- `prima_giornata_lega` (intero 1-38, predefinito 1): la giornata di Serie A da cui parte la lega. Con 4, la giornata 1 della lega è la 4ª di Serie A (giornata di Serie A = giornata della lega + 3). Prima di allora per la lega non esiste nulla.
- `aggiornamenti_vicino_scadenza` (vero/falso, predefinito vero): interruttore degli aggiornamenti più fitti di probabili e infortuni (sotto).
Valori fuori dai limiti: `400`/`422` con il testo del problema.

Dove si vedono (tutti campi aggiunti, i client vecchi li ignorano):
- `GET /api/oggi` (e `/api/widget`): `inizio` resta l'inizio della prima partita del turno (anche se già giocata; una partita rinviata rimasta in calendario con la data vecchia non conta: regola unica di `fanta/turno.py`, la stessa di promemoria e copia automatica; anche `prima_partita` del widget); nuovi `scadenza` (testo `AAAA-MM-GG HH:MM`, inizio meno i minuti) e `minuti_scadenza`. `ore_mancanti` e `iniziata` ora contano dalla scadenza (senza regola coincide con l'inizio, come prima): `iniziata: true` = la formazione non si può più cambiare. Nuovo `giornata_lega` (numero nella lega, `null` se la regola manca o la giornata è prima della lega). `giornata` resta quella di Serie A. In `/api/widget`, `scadenza` è la scadenza vera. `giornata_lega` (facoltativo, `null` se non applicabile) è anche in `GET /api/widget` e, accanto a `giornata`, in `GET /api/formazione` e `POST /api/formazione/valuta`: i client che non lo conoscono lo ignorano e continuano a mostrare `giornata`.
- `GET /api/stato`: `prossima_giornata` non è mai prima della prima giornata della lega; nuovi `prima_giornata_lega` e `prossima_giornata_lega`.
- `GET /api/giocatore/{id}` (in `previsione`, accanto a `giornata`) e `GET /api/confronto` (accanto a `giornata`), dal 2/11/2026: nuovo `giornata_lega`, stesso calcolo e stesso significato delle altre rotte (`null` se la giornata è prima della lega). Facoltativo: i client vecchi lo ignorano. La scheda mostra «Giornata 7 · in trasferta contro …» con `giornata_lega ?? giornata`.
- `GET /api/diario`: la stagione in corso conta solo dalla prima giornata della lega; ogni voce ha `giornata_lega`. `POST /api/diario/schierata` rifiuta (`400`) le giornate precedenti alla lega.
- Promemoria, «cambio pronto», copia automatica della formazione e riepilogo usano la scadenza (non l'inizio della partita).
Aggiornamenti più fitti: il servizio rilegge le probabili (e avvisa dei cambi) anche a 60, 30 e 15 minuti prima della scadenza, oltre ai giri di sempre del server. Nessuna rotta nuova; per spegnerli: `FANTA_PIANIFICATORE=0` nel servizio, oppure `aggiornamenti_vicino_scadenza: false` nelle regole. Le probabili hanno quindi un'ora di rilevazione (`probabili.aggiornate_il` in `/api/oggi`) più recente vicino alla scadenza.
Le app mostrano il numero della lega (`giornata_lega`) quando c'è, altrimenti `giornata`. Cosa devono fare iOS e Android: mostrare il conto alla rovescia verso `scadenza` (se manca, `inizio`) e, nel pannello delle regole, i due valori; se non li conoscono non cambia nulla.

## Partite rinviate: regola della lega ed eccezione per una giornata

**Anticipi** (dal 2/11/2026, regola unica di `fanta/turno.py`): il turno comincia dal gruppo principale della giornata (partite a
meno di 36 ore l'una dall'altra, almeno metà del totale). Una partita da più di 36 ore a meno di 7 giorni prima è un anticipo
(al massimo 2; di più è un turno diviso, come a Pasqua, e vale la regola di prima): non fissa `inizio` né `scadenza` di `/api/oggi` e
`/api/widget` (né promemoria, pianificatore e copia automatica), non è mai `rinviata` e non fa uscire dal turno il posticipo del
lunedì. La formazione resta salvabile fino alla scadenza del gruppo principale; in `GET /api/formazione` (con `iniziata: false`) i
giocatori di un anticipo già cominciato hanno già `stato_partita`, `titolarita: null` ed `etichetta` dello stato vero («Ha giocato»,
«Voto in arrivo»...), come a giornata iniziata. Partite giocate 7 giorni o più prima del gruppo principale (metà giornata giocata e
il resto rinviato) fissano la scadenza come prima.

Una partita della giornata è **rinviata** se non è stata giocata e non sta nel turno (regola unica di `fanta/turno.py`): senza data
o spostata a un recupero, anche settimane dopo. Appena il recupero è giocato non è più rinviata: i suoi voti valgono per la sua
giornata. Cosa fa la lega con i giocatori di quella partita lo dicono tre campi nuovi di `GET/PUT /api/regole` (facoltativi: se un
client vecchio rimanda le regole senza, il server tiene i valori che c'erano):
- `partite_rinviate` (testo, predefinito `"aspetta"`): `aspetta` = la lega aspetta il recupero e conta il voto preso lì (come
  «Attendi il recupero» di Leghe Fantacalcio); `senza_voto` = restano senza voto ed entra la riserva; `voto_ufficio` = tutti
  prendono il voto fisso qui sotto (fantavoto = voto, niente bonus né malus).
- `voto_ufficio_rinviate` (numero 0-10, predefinito 6): il voto d'ufficio.
- `rinvii_giornate` (oggetto, predefinito `{}`): eccezioni decise volta per volta, `{"2026-27/12": "voto_ufficio"}` (stagione e
  giornata **di Serie A**, come `giornata` di `/api/oggi`); vince sulla regola generale. Al massimo 76 voci.
Valori sbagliati: `400` con il testo del problema.

`PUT /api/regole/rinvio` cambia solo l'eccezione di una giornata, senza rimandare tutte le regole. Corpo: `giornata` (1-38, di Serie
A), `modo` (`aspetta`, `senza_voto`, `voto_ufficio`, oppure `null` = torna alla regola della lega; uguale alla regola della lega =
tolta), `stagione?` (`AAAA-AA`, solo quella in corso: un'altra dà `400`). Le eccezioni delle altre stagioni si tolgono. Risponde (con il nuovo
`ETag` delle regole) `{stagione, giornata, modo, valore, predefinito, eccezione}`: `modo` è quello che vale ora, `valore` il voto
d'ufficio (solo con `voto_ufficio`, se no `null`), `predefinito` la regola della lega, `eccezione` se la giornata ne ha una.
Errori: `422` per un corpo sbagliato, `412` con un `If-Match` vecchio. Con il token del widget: `403`.

Dove si vede (tutti campi aggiunti, i client vecchi li ignorano):
- Previsioni (`/api/formazione` in `titolari`, `panchina`, `fuori`, `schede`; `/api/giocatore/{id}.previsione`; `/api/classifica`):
  nuovo campo `rinvio` = il modo che vale per la sua partita, oppure `null` se la partita si gioca. Con `senza_voto`: `p_voto` 0,
  `punti_attesi` 0, `titolarita` `"fuori"` (la formazione consigliata mette chi gioca davvero). Con `voto_ufficio`: `p_voto` 1,
  `fv_atteso` = `voto_atteso` = `punti_attesi` = il voto d'ufficio, gol, assist, rigori, cartellini e porta inviolata a 0. Con
  `aspetta`: i numeri di sempre (probabilità di giocare dalle presenze recenti: per il recupero non ci sono probabili).
  Il primo dei `motivi` e di `perche_numero` (chiave nuova `rinvio`, `effetto: null`; con `frase`/`motivi_frasi`, chiavi
  `rinvio.*` di `fanta/frasi.py`) lo spiega: «partita rinviata: conta il voto
  del recupero del 10/12» (o «(data da definire)»), «partita rinviata: in questa giornata non prende voto», «partita rinviata: voto
  d'ufficio 6». Con `senza_voto` e `voto_ufficio` è l'unico motivo.
- `GET /api/oggi`: nuovo campo `rinvio`, `null` se nella giornata non c'è una partita rinviata (calendario o diretta, cioè
  `partite[].stato == "rinviata"`), altrimenti `{stagione, giornata, giornata_lega, modo, valore, predefinito, eccezione, modi,
  voto_ufficio, partite: [{casa, trasferta, data}], miei: [{id, nome, ruolo, squadra}]}` (`data` = data del recupero o `null`;
  `miei` = i giocatori della tua rosa in quelle partite; `modi` = i valori ammessi, nell'ordine in cui mostrarli; `voto_ufficio`
  = il voto d'ufficio della lega, anche quando non è quello scelto).
- `in_corso` di `/api/oggi` segue la regola della giornata: con `aspetta` chi ha la partita rinviata resta a punteggio (niente
  cambio) e i suoi punti attesi restano in `punti_previsti`; con `senza_voto` esce con un cambio certo (`motivo: "rinviata"`);
  con `voto_ufficio` ha `fantavoto` = il voto d'ufficio, contato subito in `punti_fatti`. `stato` resta `rinviata`.
- `GET /api/diario` (giornate finite): per le partite giocate fuori dal turno (recuperi) i punti `reale` di consigliata e
  schierata usano la regola della giornata: con `aspetta` il voto del recupero, con `senza_voto` nessun voto (entra la riserva),
  con `voto_ufficio` il voto fisso; anche `atteso` è ricalcolato con la stessa regola. `giocatori` (numeri per «Quanto ci abbiamo
  preso») resta quello del modello e dei voti veri. Cambiare la regola di una giornata con partite fuori dal turno (diversa da
  `aspetta`) rifà solo la sua voce. Con `senza_voto` o `voto_ufficio` la giornata entra nel Diario (e in «Ho schierato…» di
  `POST /api/diario/schierata` e in «Da fare») appena sono giocate le partite del turno, senza aspettare il recupero; con
  `aspetta` solo a recupero giocato.

Cosa devono fare iOS e Android: nel pannello delle regole, «Partite rinviate» con le tre scelte e il voto d'ufficio (solo se il
server manda `partite_rinviate`); in Oggi, se `rinvio` non è `null`, un riquadro «Partita rinviata» con le partite, i tuoi
giocatori coinvolti e un menu «Per questa giornata i loro giocatori…» con `modi` (selezionato `modo`) che chiama
`PUT /api/regole/rinvio` e poi ricarica Oggi e la formazione. Mostrare `rinvio` e il motivo nella scheda del giocatore.

## GET /api/oggi: fasi della giornata (`fase`, `in_corso`, `riepilogo`, `prossima`)

Campi nuovi e facoltativi (dal 1/11/2026; i client vecchi li ignorano, nessun campo di prima cambia). Codice: `fanta/fasi.py`.
Leggono solo dati già pronti (calendario, voti, scelte, Diario, cache dei risultati in diretta): mai un calcolo nuovo, mai un 202 in più.

`fase` (sempre presente, anche senza rose):
- `"prima"`: la formazione si può ancora cambiare. Oggi come sempre: scelta, «Da controllare» (`avvisi` con `in_formazione`), migliori, consigli.
- `"in_corso"`: la scadenza è passata (`iniziata: true`) e la giornata non è chiusa (partite in corso o da giocare, anche la domenica sera con i posticipi del lunedì). Il client NON mostra «Da controllare», i migliori né altri consigli su chi schierare; mostra `in_corso`. `da_fare` in questa fase non contiene mai `dubbio`, `formazione`, `copertura`, `svincolato`, `scambio`.
- `"finita"`: la giornata precedente è finita da meno di 48 ore e la prossima si chiude fra più di 24 ore. `giornata`, `scadenza`, `formazione` parlano già della PROSSIMA giornata; il client mostra `riepilogo` e `prossima`, non mostra «Da controllare» né i migliori (le probabili non ci sono ancora). `da_fare` non contiene `dubbio`; coperture, svincolati e scambi solo se superano il buon senso (come sempre).

`partite[].stato` (in ogni partita del turno): `da_giocare`, `in_corso`, `finita`, `rinviata`. Prima il calendario (`giocata`), poi la cache dei risultati in diretta, infine l'orario (110 minuti dopo l'inizio = finita). Ogni partita ha anche `gol_casa` e `gol_trasferta`: il risultato ufficiale del calendario se `giocata` è vero, altrimenti `null` (così i client mostrano i risultati anche senza i risultati in diretta). Per il punteggio in diretta e i marcatori resta `GET /api/live`.

`in_corso` (oggetto o `null`; c'è solo con `fase: "in_corso"` e se si sa quale formazione è stata schierata):

| campo | significato |
|---|---|
| `giornata`, `giornata_lega` | la giornata in corso |
| `formazione_di` | `tua` (la scelta salvata) o `consigliata` (quella congelata alla scadenza, altrimenti la consigliata di adesso) |
| `punti_fatti` | punti già fatti dai giocatori che vanno a punteggio e hanno il voto (con il modificatore della difesa solo quando portiere e difensori hanno tutti il voto) |
| `punti_attesi_restanti` | punti attesi che mancano a fine giornata: stesse simulazioni della formazione (riserve, voto d'ufficio, modificatore) con i fatti già noti fissati; a giornata appena iniziata coincide con i punti attesi di prima |
| `punti_previsti` | `punti_fatti + punti_attesi_restanti` (il numero «a fine giornata, circa») |
| `modificatore` | modificatore della difesa già conteggiato, o `null` |
| `ancora_da_giocare` | quanti di chi va a punteggio devono ancora giocare o stanno giocando (stato `da_giocare` o `in_corso`; non conta chi ha già giocato e aspetta il voto, né chi ha la partita rinviata) |
| `giocatori` | titolari in ordine, poi panchina: `{id, nome, ruolo, squadra, titolare, a_punteggio, stato, fantavoto, data}`. `stato`: `fatto` (ha il voto, `fantavoto` con le regole della lega), `senza_voto` (la sua partita ha i voti, lui no), `attesa_voti` (partita finita, voti non ancora usciti), `in_corso`, `da_giocare` (`data` = ora d'inizio, `AAAA-MM-GG HH:MM`), `rinviata`. `a_punteggio`: va a punteggio con i cambi di adesso |
| `sostituzioni` | `[{esce {id,nome,ruolo}, entra {id,nome,ruolo} o null, certa, motivo}]`, con le regole di panchina della lega. `certa: true` = già scattata (chi esce è senza voto e chi entra ha il voto); `false` = probabile. `motivo`: `senza_voto`, `fuori` (infortunato o squalificato che deve ancora giocare), `rinviata`. `entra: null` = nessun sostituto possibile |
| `partite` | `{in_corso, finite, da_giocare, rinviate}`: quante partite del turno in ogni stato |

`riepilogo` (oggetto o `null`; solo con `fase: "finita"`): `{giornata, giornata_lega, formazione_di, nel_diario, punti_fatti, punti_attesi, intervallo, consigliata, recuperi}`.
La giornata è finita quando sono giocate tutte le partite del turno: una partita rinviata (anche da recuperare settimane dopo)
non la tiene aperta. `recuperi` (lista, facoltativa: un client vecchio la ignora) = le partite rinviate ancora da recuperare
`[{casa, trasferta, data}]`, solo se per quella giornata vale `aspetta`: i loro giocatori restano in formazione senza voto e i
punti possono ancora cambiare (la web app scrive «Manca il recupero di ATA–PAR: i punti possono ancora cambiare»). Con
`senza_voto` o `voto_ufficio` è vuota: i punti sono già quelli finali (riserva o voto d'ufficio). `rinvio` (oggetto o `null`):
c'è finché una partita rinviata della giornata è da recuperare, con gli stessi campi del menu di Oggi (`stagione, giornata,
giornata_lega, modo, valore, predefinito, eccezione, modi, voto_ufficio`): il client mostra lo stesso menu «per questa giornata»
(che chiama `PUT /api/regole/rinvio`) anche nel riepilogo.
Con `nel_diario: true` i numeri sono quelli del Diario (`GET /api/diario`) e `consigliata` = `{punti_fatti, punti_attesi}` della consigliata; con `nel_diario: false` il Diario non ha ancora calcolato la giornata: `punti_fatti` viene dai voti, `punti_attesi` può essere `null`, `consigliata` è `null` (il confronto arriva nel Diario).

`senza_formazione` (facoltativo, dal 2/11/2026; c'è solo se vale `true`, con `fase: "in_corso"`): l'utente è entrato in SchieraXI (account nato) DOPO la scadenza della giornata in corso e non ha nessuna formazione per lei (né salvata da lui né la copia della consigliata vista prima della scadenza). Allora `in_corso` è `null` (niente punti di una formazione che non ha schierato), `miei_titolari` è vuoto e c'è `prossima` = la giornata dopo, da preparare. Il client scrive «Questa giornata è già iniziata: prepara la prossima» con la scadenza della prossima e un pulsante che apre la Formazione (che in questo caso è già quella della prossima: vedi `giornata_saltata` di `GET /api/formazione`). Senza account (interruttore spento) non c'è mai.

`prossima` (oggetto o `null`; con `fase: "finita"`, oppure con `fase: "in_corso"` e `senza_formazione: true`): `{giornata, giornata_lega, scadenza, prepara_da, con_probabili}`. `prepara_da` (`AAAA-MM-GG HH:MM`) = da quando conviene preparare la formazione: adesso se le probabili ci sono già, altrimenti 3 giorni prima della scadenza (di solito escono allora).

Cosa devono fare iOS e Android: leggere `fase` (se manca: comportamento di sempre). Con `in_corso`: al posto di «Da controllare», «I tuoi migliori», «Indisponibili» e «Diffidati» una card con `punti_fatti` grande, `punti_previsti` («a fine giornata, circa») e `formazione.punteggio_atteso` («attesi prima»), l'elenco di chi va a punteggio (fantavoto, oppure l'ora o lo stato) e i cambi dalla panchina («già fatto» / «probabile»). Con `finita`: card del riepilogo (fatti contro attesi, «con la consigliata», pulsante verso il Diario) e la frase sulla prossima giornata; niente «Da controllare» né migliori. Il widget può usare gli stessi campi: sono anche nella risposta letta con il token del widget e in `GET /api/widget` (facoltativi; lì i blocchi vuoti mancano invece di valere `null`).

## GET /api/oggi: campo `da_fare`

`/api/oggi` ha tutti i campi di sempre (`giornata`, `inizio`, `ore_mancanti`, `iniziata`, `con_probabili`, `formazione`, `avvisi`, `migliori`, `partite`)
e in più `da_fare`: lista (anche vuota; i client vecchi la ignorano) di cose da sbrigare, già in ordine di importanza.
Il server la costruisce solo con dati già pronti: nessun calcolo pesante, mai un 202 in più. Se un controllo non riesce viene saltato.

**Senza rose** (account nuovo): `/api/oggi` risponde 200 (prima 409), con gli stessi campi di sempre ma vuoti (`formazione.modulo` "–",
`formazione.punteggio_atteso` null, `avvisi`/`migliori`/`miei_titolari` vuoti, `giornata`/`inizio`/`partite` dal calendario se c'è), più `senza_rose: true`
e in `da_fare` una voce `rose` (priorità 1, azione «Importa le rose», destinazione `lega/rose`) e, se la configurazione guidata non è mai iniziata, `primo_avvio`.
I client controllano `senza_rose`: se è vero mostrano una card di benvenuto con «Importa le rose» (e aprono il primo avvio) invece di Oggi. Le altre rotte
(`/api/formazione`, `/api/mercato`, `/api/scambi/*`, `/api/rosa`...) senza rose restano 409 con «Nessuna rosa importata...»: il client lo mostra come stato vuoto, non come errore.

Parametro facoltativo: `certificato_giorni` (intero da -3650 a 3650) = giorni che restano al certificato dell'app sul telefono. Lo calcola il client
(il server non lo sa): lo manda solo l'app iPhone installata con SideStore; valore negativo = già scaduto. Fuori intervallo o non numerico: 422.
Il token del widget può leggere `/api/oggi` come prima, anche con questo parametro.

Ogni voce:

| campo | tipo | significato |
|---|---|---|
| `id` | testo | stabile fra una chiamata e l'altra (es. `dubbio:123`, `formazione:9`, `rose-vecchie`): serve a non rimostrare una voce già chiusa dall'utente |
| `tipo` | testo | `dubbio`, `formazione`, `svincolato`, `scambio`, `rose`, `certificato`, `diario`, `backup`, `server`, `primo_avvio`, `copertura` (reparto della rosa scoperto, priorità 1, o senza ricambi, priorità 2: campi in più `reparto` = `P`/`D`/`C`/`A` o `null`, `livello` = `scoperto`/`rischio`, `disponibili`, `minimo`; destinazione `mercato`, oppure `formazione` se nessun modulo ammesso si può schierare). Un client può trovarne di nuovi: li mostra con il solo `testo` e `azione` |
| `testo` | testo | frase semplice in italiano, pronta da mostrare |
| `priorita` | 1, 2, 3 | 1 alta (urgente, tinta di allarme), 2 media, 3 bassa. La lista è già ordinata per priorità |
| `azione` | testo | etichetta del pulsante (es. «Sostituisci», «Aggiorna le rose») |
| `destinazione` | oggetto | dove porta il pulsante, vedi sotto |

Altri campi per tipo (facoltativi): `dubbio`: `giocatore` {id, nome} e `alternativa` {id, nome, ruolo, punti_attesi} (il miglior sostituto libero dello stesso ruolo);
`svincolato`: `esce`, `entra` {id, nome}, `guadagno` (punti); `scambio`: `con` (squadra), `guadagno`; `rose`/`backup`/`server`: `giorni`;
`diario`: `giornata` (solo giornate finite la cui formazione si è chiusa dopo la nascita dell'account: chi è appena entrato non riceve domande sulle giornate di prima); `primo_avvio`: `saltati` (passi saltati).

`destinazione`: `scheda` (`oggi`, `formazione`, `mercato`, `scambi`, `lega`, `impostazioni`), `sezione` (o null: `rose`, `diario` per `lega`;
`installazione`, `backup`, `avanzate`, `informazioni` per `impostazioni`), `link` (già pronto: `schieraxi://<scheda>[/<sezione>]`, oppure
`schieraxi://giocatore/<id>` quando c'è un giocatore) e, se serve, `giocatore` (id) o `giornata`. Le app native aprono il `link`; il web usa `scheda` e `sezione`.
La voce `diario` si chiude con `POST /api/diario/schierata` `{"giornata": N, "tipo": "consigliata"}` (nessun limite conta).

Quando compaiono (al massimo 8 voci in tutto; la card di Oggi ne mostra 4):

- `dubbio` (priorità 1 se fuori/infortunato/squalificato, 2 se in dubbio): fra i titolari della TUA formazione salvata, altrimenti della consigliata, prima che si chiuda e non in `fase: "finita"`. Max 3.
- `formazione` (1 se mancano ≤ 3 ore, 2 fino a 12): formazione non ancora salvata a poche ore dalla scadenza.
- `certificato` (1 se ≤ 1 giorno o scaduto, 2 fino a 3 giorni): solo se il client manda `certificato_giorni`.
- `rose` (2): giornata finita dopo l'ultimo aggiornamento delle rose, e rose ferme da 4 giorni o più.
- `svincolato` e `scambio` (3): solo se già in cache e solo se superano il buon senso (`fanta/buon_senso.py`): guadagno di almeno 2-3 punti (secondo il ruolo) sulle prossime 5 giornate e positivo nella maggior parte di esse, chi entra gioca davvero (titolare fisso, non in dubbio), chi esce non è un titolare utile né costoso, crediti sufficienti, nessun giocatore preso o lasciato libero negli ultimi 21 giorni. Campo in più facoltativo `motivo` (una frase: perché conviene), anche dentro il `testo`. Mai calcolati qui. Dubbi, coperture, svincolati e scambi insieme sono al massimo 3 consigli, e nessun giocatore compare in due consigli. Se non c'è niente di utile `da_fare` può essere vuota (i client scrivono «Nessuna azione utile oggi»).
- `diario` (3): fino a 2 delle ultime 3 giornate finite senza formazione dichiarata.
- `backup`: non si genera più dal 1/11/2026 (le app non scaricano più la copia di sicurezza). Un client vecchio che la conosce non riceve niente da mostrare.
- `server` (2): solo per l'amministratore (e per l'app di sempre): dati delle partite fermi da 3 giorni o più.
- `primo_avvio` (3): ci sono passi saltati nella configurazione guidata e non l'ha chiusa.

Offerte di scambio ricevute: in questa versione non esistono (l'app non ha scambi tra utenti), quindi non ci sono voci. L'amministratore non ha limiti:
nessuna voce parla di limiti d'uso, per nessuno.

Il client decide cosa fare delle voci chiuse a mano: la memoria locale per `id` basta; il server non ricorda chi ha «nascosto» cosa.

## Frasi con chiave: `frase`, `X_frase`, `X_frasi` (facoltative: un client vecchio le ignora)

Il testo scritto dal server resta in italiano, nello stesso campo di sempre (`testo`, `motivi`, `avvisi`...): iOS e i widget non cambiano. Le
frasi che cambiano con i dati (nomi, numeri, orari) hanno in più un oggetto per tradurle, accanto al testo:

```json
{"testo": "Rossi è infortunato. Meglio Bianchi.",
 "frase": {"chiave": "dafare.dubbio_infortunato_alt", "param": {"nome": "Rossi", "alt": "Bianchi"}}}
```

- Per un campo di testo `X` l'oggetto sta in `X_frase` (per `testo`: `frase`); per un elenco di testi `X` sta in `X_frasi`, nello stesso ordine
  (un oggetto o `null` per ogni voce: `null` = testo semplice, per esempio la nota di un infortunio delle fonti).
- `chiave` è un nome stabile (`dafare.*`, `senso.*`, `motivo.*`, `perche.*`, `probabili.*`, `confronto.*`, `rose.*`, `tempo.*`, `posto.*`, `nomi.*`);
  `param` sono i pezzi variabili: testo (nomi, squadre), interi, decimali **come testo con il punto e una cifra** (`"1.5"`) e altre frasi
  (`{"chiave", "param"}`) per i pezzi che sono a loro volta frasi (per esempio un orario o il motivo di un consiglio). Per le chiavi che hanno il
  plurale (`x.one` / `x.other` nella web app) c'è il parametro `n`. `elenco` e `elenco_e` (parametri `parti` e `sep`) uniscono più frasi.
- Il web traduce con `fanta/web/testi.js` (`frase.<chiave>`); in italiano mostra sempre il testo del server. Un client che non sa tradurre
  una chiave mostra il testo italiano. Le chiavi si possono aggiungere, mai cambiare di significato; un parametro nuovo si aggiunge in fondo.
- Dove: `da_fare[]` (`frase`, `azione_frase`); `GET /api/oggi` `probabili` (`frase`, `eta_frase`, `avviso_frase`); ogni scheda di giocatore
  (`motivi_frasi`, e dentro `perche_numero[]` il campo `frase`); proposte di `GET /api/mercato` (`motivo_frase`); `GET /api/confronto`
  (`perche_frase` e `formazione.frase`); rose: `avvisi_frasi` in `POST /api/rose/anteprima` e `GET /api/squadre/{nome}`, e
  `giocatori[].avviso_frase` nell'anteprima (le risposte di importazione e correzione non le hanno: l'app non ne mostra i testi).
- I messaggi d'errore (`detail`) non hanno la chiave: il web li riconosce dal testo (chiavi `err.*` di `testi.js`; un test controlla che ogni
  messaggio scritto nel server abbia la sua traduzione).
- Le regole riconosciute da `POST /api/regole/riconosci` hanno `etichetta` in italiano: per tradurla basta la `chiave` della regola (il web usa `regola.et.<chiave>`).

## Primo avvio: GET e PUT /api/primo-avvio

Stato piccolo della configurazione guidata, salvato nelle impostazioni dell'utente sul server (si riprende da un altro dispositivo; funziona anche
senza account, a differenza di `/api/onboarding`, che resta per la procedura degli account nuovi). Non tocca `/api/avvisi`: quella rotta non mostra questi campi.

```
GET /api/primo-avvio  ->  {"primo_avvio": null | {"fatti": [...], "saltati": [...], "chiuso": false, "aggiornato": "2026-10-30T12:00:00"},
                           "passi": ["server","accesso","rose","stemma","squadra","tempi","pwa","widget","avvisi"]}
PUT /api/primo-avvio  {"fatti": [...], "saltati": [...], "chiuso": true}   // tutti facoltativi: si cambiano solo i campi mandati
```

`primo_avvio: null` = l'utente non l'ha mai iniziato. I client lo avviano solo se è null E mancano le rose (chi ha già la lega non lo vede). Passi: stringhe
dell'elenco `passi`; un passo sconosciuto, liste oltre 12 voci o tipi sbagliati: 400/422, e non si salva niente. Un passo non sta mai in `fatti` e `saltati` insieme (vince `fatti`).
Passi che dipendono dal dispositivo (`pwa` solo web, `widget` solo iPhone) li segna e li salta il client giusto; gli altri client li ignorano.
`tempi` (dal 2/11/2026): le due domande sui tempi della lega (`scadenza_minuti` e `prima_giornata_lega`, salvate con `PUT /api/regole`); un client che non lo propone lo ignora.
Ultima scrittura vince (nessun If-Match). Il campo è anche nel backup (dentro le impostazioni degli avvisi) ma non esce da `/api/avvisi`.

Ora `GET /api/backup` ricorda la data dell'ultimo scaricamento (per la voce `backup` di «Da fare»); non cambia la risposta.

## Funzioni: GET e PUT /api/funzioni

Quali funzioni dell'app sono accese per chi chiede (la «dieta»: formazione al centro, il resto dietro un interruttore; nessun codice è cancellato).

```
GET /api/funzioni  ->  {"funzioni": {"live": true, "asta": true, "scambi_trova": true, ...}, "mostra_tutte": false}
PUT /api/funzioni  {"mostra_tutte": true}   ->  stessa risposta
```

- **Predefiniti (dal 31/10/2026)**: anche nel codice privato sono spente di norma `asta` e `crediti` (crediti di tutte le squadre); restano accese `diario`, `live`, scambi e `confronto`. Chi ha una scelta dell'amministratore o una variabile `FANTA_FUNZIONE_<NOME>` la conserva. L'amministratore vede anche le funzioni spente solo di predefinito (non quelle che ha spento lui). Per chi non è amministratore `GET /api/asta` risponde `404` con `funzione: "asta"` (il client la tratta come «non disponibile»); «Mostra tutte» la riapre. Le chiavi `sotto_il_cofano` e `crediti` sono nuove: un client vecchio le ignora.
- **Una chiave che manca vale «acceso»**: client e server vecchi continuano a funzionare. Un client che non conosce una chiave la ignora.
- **Funzioni ritirate**: `sotto_il_cofano` (la guida tecnica) è tolta dalle app dal 1/11/2026. Resta nella risposta, sempre `false` (anche per l'amministratore e con `mostra_tutte`), così un client vecchio non la mostra; non si può più accendere. La rotta `GET /api/sotto-il-cofano` resta per i client vecchi.
- `mostra_tutte` è l'impostazione avanzata «Mostra tutte le funzioni» (spenta di norma, per utente, salvata sul server con le altre impostazioni e nel backup): con lei le chiavi tornano `true`, tranne `live` e `immagini_web` se l'amministratore le ha spente: vale solo per i menu, non riapre le rotte che toccano la rete.
- **Rotte di una funzione spenta**: rispondono `404` `{"detail": "«Nome» non è disponibile in questa versione dell'app.", "funzione": "<id>"}`, tranne per chi ha `mostra_tutte` acceso. Fanno eccezione `live` e `immagini_web`: spente dall'amministratore restano bloccate per tutti, anche con `mostra_tutte`. Solo le rotte esclusive di una funzione si bloccano: `live` (`GET /api/live`), `asta` (`GET /api/asta`), `scambi_trova` (`GET /api/scambi/proposte` e `/limite`), `confronto` (`GET /api/confronto`), `immagini_web` (`POST /api/squadre/immagine/da-url` e `/condivisa`). `GET /api/scambi/analizza` e `POST /api/scambi/da-testo` non si bloccano mai (servono a «Valuta un'offerta»); le altre funzioni (`seguiti`, `diario`, `backup`, `squadre_altrui`, `novita`...) sono solo da nascondere nelle schermate. I client trattano il `404` con il campo `funzione` come «funzione non disponibile», non come errore.
- `live` spenta ferma anche il raccoglitore dei risultati in diretta (si legge all'avvio del servizio); `fonti_ombra` spenta salta i due passi di `aggiorna` che servono solo a misurare il modello.
- Le scelte dell'amministratore sono in `GET/PUT /api/admin/funzioni`. Il token del widget (`fw_...`) non può usare queste rotte (403).
- `movimenti` (nuova): la voce «Movimenti e storico» (storico di acquisti, tagli e scambi della propria rosa). Accesa di norma per tutti, anche nella versione pubblica, perché serve a tenere aggiornata la rosa; l'amministratore può spegnerla da `PUT /api/admin/funzioni` come le altre. È solo da nascondere nelle schermate: le rotte `/api/movimenti` non si bloccano. Un client che non la conosce la ignora; se la chiave manca vale «acceso».
- Id: `stili_ridotti`, `confronto`, `elenco_giocatori`, `seguiti`, `diario`, `movimenti`, `backup`, `squadre_altrui`, `aspetto_avanzato`, `novita`, `live`, `asta`, `scambi_trova`, `scambi_costruisci`, `immagini_web`, `widget_extra`, `fonti_ombra`.

## Giocatori: `stato`, `dubbio`, `percentuale` e formato delle date

Valgono per i giocatori di `/api/oggi`, `/api/formazione`, `/api/giocatore/{id}`, `/api/classifica`, `/api/osservati` e `/api/widget` (dove ci sono).

- `stato` = cosa dicono le probabili formazioni di quel giocatore per la prossima giornata: `titolare`, `panchina`, `non_convocato` (citato solo come diffidato o in dubbio, fuori dai convocati), `infortunato`, `squalificato`. In più possono arrivare `non_citato` (le probabili ci sono ma il giocatore non è nominato) e `null` (probabili non ancora uscite per la sua partita). Un client trova di sicuro valori nuovi in futuro: quello che non conosce lo tratta come `null`.
- `dubbio` (vero/falso): la fonte lo segnala «in dubbio». Può essere vero con `stato` `titolare` o `panchina`; è indipendente da `stato`. `diffidato` (vero/falso) dice solo che un'altra ammonizione vuol dire squalifica.
- `percentuale`: da 0 a 100 (non da 0 a 1), la probabilità indicata dalla fonte per quel giocatore nel suo ruolo di `stato` (per `titolare`, che parta titolare; per `panchina`, che entri). `0` per `infortunato` e `squalificato`; `null` se la fonte non la dà. Da non confondere con `p_voto`, che invece va da 0 a 1 ed è la probabilità di prendere voto calcolata da SchieraXI. L'etichetta semplice per l'utente è `titolarita` (`titolare`, `ballottaggio`, `panchina`, `improbabile`, `fuori`).
- **Una sola percentuale sul giocare** (dal 2/11/2026): all'utente si mostra solo «gioca N%» (`p_voto`). `percentuale` resta nella risposta ma i client non la mostrano: `titolarita` va scritta a parole e senza numero (web: «Probabile titolare», «In ballottaggio», «Probabile panchina», «Improbabile», «Fuori»). Anche i `motivi` non hanno più la percentuale delle probabili: «titolare», «titolare in ballottaggio» (la fonte lo dà titolare sotto il 60%), «parte dalla panchina». `titolarita` è `titolare` anche quando la fonte lo dà titolare e `p_voto` è almeno 0,8 (prima serviva anche che partisse spesso titolare). Per chi è `infortunato` o `squalificato` `motivi` ha solo lo stato e l'eventuale nota, e `perche_numero` solo «… : non gioca» (niente partita, gol, rigori).
- **A giornata iniziata** (dopo la scadenza, la stessa `iniziata` di `/api/oggi`): `GET /api/formazione` ha `iniziata: true` (`false` prima; campo nuovo, facoltativo) e in `titolari[]`, `panchina[]`, `fuori[]`, `schede`, nella `previsione` di `/api/giocatore/{id}`, in `giocatori[].previsione` di `/api/rosa` (dal 2/11/2026) e in `giocatori[]` di `/api/osservati` (i Seguiti, dal 2/11/2026; non quelli con `assente: true`) e di `/api/classifica` (l'elenco dei Giocatori, dal 2/11/2026) ogni giocatore ha `titolarita: null` (resta `fuori` per infortunati e squalificati finché non escono i voti), i `motivi` delle probabili tolti e `stato_partita` (nuovo, facoltativo): `fatto` (ha il voto), `senza_voto`, `attesa_voti` (partita finita, voti non ancora usciti), `in_corso`, `da_giocare`, `rinviata`, come `in_corso.giocatori[].stato` di `/api/oggi`; e `fv_preso` (dal 2/11/2026, facoltativo): il fantavoto preso con le regole della lega quando `stato_partita` è `fatto`, altrimenti `null`. A partita iniziata il client non mostra più «gioca N%»: a partita finita il fantavoto preso (o «Voto in arrivo», «Senza voto»), in corso lo stato. Un client mostra lo stato della partita al posto dell'etichetta delle probabili (o niente) e non segnala più «in ballottaggio» né alternative: la formazione non si può più cambiare.
- **Etichetta di stato pronta** (dal 2/11/2026, campo nuovo e facoltativo `etichetta`): `{"codice": "in_dubbio", "testo": "In dubbio · gioca 55%", "tono": "attenzione"}`.
  I client **devono mostrare `etichetta.testo`** (e il colore da `tono`) invece di comporre lo stato da `titolarita`, `stato_partita`, `stato`, `dubbio`
  o `tipo`: la regola è una sola, sul server (`fanta/etichette.py`), e le parole sono quelle del vocabolario comune (`docs/COERENZA-WEB-IPHONE.md`).
  Il nome non è `stato` perché `stato` c'è già (probabili nelle schede, partita in `in_corso.giocatori[]`) e non cambia.
  - Dove: ogni scheda giocatore (`titolari[]`, `panchina[]`, `fuori[]`, `schede` di `/api/formazione`; `previsione` di `/api/giocatore/{id}`;
    `giocatori[].previsione` di `/api/rosa`; `/api/classifica`, `/api/osservati`, `giocatori[]` di `/api/confronto`; `migliori[]` di `/api/oggi`),
    `in_corso.giocatori[]` e `avvisi[]` di `/api/oggi`. Prima della scadenza dice la titolarità, dopo la scadenza com'è la partita (stessa
    `iniziata` di `/api/oggi`). `null` se non c'è niente da dire. `/api/widget` per ora non lo ha.
  - `testo` è nella lingua della richiesta (`?lingua=en` o `Accept-Language: en`, altrimenti italiano). `codice` non cambia con la lingua:
    serve solo per decidere (per esempio nascondere «gioca N%» a partita iniziata), mai per scrivere. Un codice che il client non conosce si
    mostra lo stesso con `testo`.
  - `tono`: `positivo` (verde), `attenzione` (arancio), `negativo` (rosso), `neutro` (grigio).
  - Codici (italiano / inglese / tono). Prima della scadenza: `titolare` «Probabile titolare» / «Likely starter» / positivo; `ballottaggio`
    «In ballottaggio» / «Contested» / attenzione; `panchina` «Probabile panchina» / «Likely bench» / attenzione; `improbabile` «Improbabile» /
    «Unlikely» / negativo; `in_dubbio` «In dubbio · gioca 55%» / «Doubtful · plays 55%» / attenzione (le probabili lo danno in dubbio; il numero
    è `p_voto`); `infortunato` «Infortunato» / «Injured» / negativo; `squalificato` «Squalificato» / «Suspended» / negativo; `fuori` «Fuori» /
    «Out» / negativo; `rinviata` «Rinviata» / «Postponed» / attenzione (anche prima della scadenza, se c'è `rinvio`). Dopo la scadenza: `voto`
    «Ha giocato» / «Played» / positivo (il numero sta in `fv_preso` o `fantavoto`); `senza_voto` «Senza voto» / «No grade» / attenzione;
    `voto_in_arrivo` «Voto in arrivo» / «Grade coming» / neutro; `in_corso` «Partita in corso» / «Match on» / positivo; `da_giocare`
    «Da giocare» / «Still to play» / neutro; `rinviata`; un infortunato o squalificato resta `infortunato` / `squalificato` finché non escono
    i voti. Solo in `avvisi[]` di Oggi: `diffidato` «Diffidato» / «One yellow from a ban» / attenzione (e `in_dubbio` per gli avvisi `dubbio`).
- **Date e ore**: ora italiana, senza fuso orario. I campi scritti dal server hanno la forma `2026-10-26T23:55:13` (con la `T` e i secondi): per esempio `ultimo_aggiornamento` di `/api/stato`, `/api/salute` e `/api/widget` (dentro `dati`), `aggiornato` di `/api/primo-avvio`. Il giorno di una partita (`data_partita`) arriva dalla fonte nella forma `2026-11-01 18:00` (spazio al posto della `T`, niente secondi), oppure solo `2026-11-01` se l'ora non è nota. Chi legge una data deve accettare la `T` o lo spazio, con o senza secondi, e non aggiungere mai un fuso.
