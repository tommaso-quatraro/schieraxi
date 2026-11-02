# Stemma e divisa dalla lega: studio di fattibilità

Obiettivo: avere nell'app lo stemma e la divisa («maglia») della propria squadra senza caricarli a mano (esempio: lega «Lega Esempio», squadra «Squadra Demo»).
Stato: studio, nessun codice. Etichette: [verificato] = visto davvero, [da verificare] = serve la prova a mano dell'utente.

## 1. Cosa c'è già
- Stemma e maglia esistono già come funzione: `fanta/immagini.py` (PNG/JPEG/WebP, max 4 MB, riconosciuti dal contenuto, una sola immagine per tipo), rotte `GET/POST /api/squadre/immagine?squadra=&tipo=stemma|maglia`, schermata Lega in `app.js` (~riga 1400). [verificato]
- Oggi arrivano **solo da caricamento manuale** dell'utente: nessun codice le scarica da Leghe. [verificato]
- Con più utenti i file stanno già per utente: `Contesto.immagini` = `dati/utenti/<id>/lega/immagini/` (da `contesto.py`). Non serve altro spazio. [verificato]

## 2. Cosa si sa di Leghe Fantacalcio
- Home pubblica `leghe.fantacalcio.it`: nessuna pagina squadra pubblica, nessun stemma/divisa visibile; le immagini pubbliche sono solo notizie e grafica del sito (`content.fantacalcio.it`, `cloudfront.net`). [verificato]
- La pagina della squadra e le immagini caricate dall'utente stanno dietro il login (come gli Excel, che danno 401: `prove/ESITO-FONTI.md`). Gli URL esatti non sono noti. [da verificare con gli strumenti del browser, loggato come utente]
- Termini: `fantacalcio.it/termini-e-condizioni` (versione giugno 2026), l'art. 10 tratta le violazioni; non ho trovato una clausola esplicita sullo scraping, ma non ho letto il testo intero [da verificare]. Per principio: **niente login automatico, niente cookie dell'utente nel server, niente scraping di pagine con accesso riservato.**
- Licenza: stemma e divisa sono creati/scelti dall'utente per la sua squadra; Fantacalcio dice che i loghi si possono scaricare a fine stagione (news del 22/07/2025). Uso personale nella propria app: rischio basso. Per lo store pubblico `docs/archivio/PIANO-STORE.md` dice di non usare stemmi di terzi: qui sono immagini dell'utente, ma non si copiano quelle delle altre squadre. [da verificare]

## 3. Alternative
| Opzione | Costo | Rischio |
|---|---|---|
| A. Importa da file (galleria/File) | già fatto | nessuno |
| B. Condivisione dal sistema (iOS/Android «Condividi» -> SchieraXI) | medio | nessuno: lo fa l'utente |
| C. Incolla un **URL immagine** | basso | funziona solo se l'URL è pubblico; server che scarica = rischio SSRF (da blindare) |
| D. Link alla pagina squadra | alto | richiede login: **scartata** |
| E. Login automatico con le credenziali | alto | vietata: credenziali dell'utente, termini |

## 4. Raccomandazione: C + B, la A resta
Percorso reale per l'utente: nell'app/sito di Leghe tiene premuto sullo stemma -> «Salva immagine» o «Condividi» -> SchieraXI. Il download lo fa il suo telefono (già loggato), non il nostro server.
1. **Condividi verso SchieraXI** (B): la PWA riceve il file con `share_target` nel manifest (POST multipart, iOS Safari lo supporta solo da installata [da verificare]); l'app iOS nativa con una Share Extension; Android con intent `ACTION_SEND` image/*. La destinazione chiede «Stemma o divisa? di quale squadra?» e chiama la rotta già esistente.
2. **URL immagine** (C), solo se l'utente lo incolla: nuova rotta che scarica **solo https**, solo host pubblico (blocca IP privati/loopback/link-local dopo la risoluzione DNS, nessun redirect verso reti private), timeout 10 s, tetto 4 MB letti a pezzi, controllo del contenuto con `estensione_da_contenuto`.

## 5. Design
- API nuova: `POST /api/squadre/immagine/da-url` con `{squadra, tipo, url}` -> stessa risposta della POST esistente. Va dietro `lega_corrente` (quindi per utente) e ai limiti di `limiti.py`. Il file finisce in `dati/utenti/<id>/lega/immagini/<slug>-<tipo>.<ext>`.
- Dimensioni: oggi nessun ridimensionamento. Proposta: lato client (canvas/Swift/Kotlin) riduzione a max 512 px prima dell'invio; il server resta com'è (4 MB, PNG/JPEG/WebP). Niente nuove dipendenze (niente Pillow).
- Web: in Lega, sotto «Stemma/Maglia», due pulsanti: «Scegli file» (c'è) e «Da indirizzo web»; testo guida di 3 righe su come salvare l'immagine da Leghe. Anteprima prima di confermare.
- iOS/Android: stessa schermata Lega (campo URL + foto) e ricezione dal menu Condividi.
- Nessun dato sull'utente di Leghe viene salvato: solo l'immagine finale.

## 6. Passi piccoli (ognuno con «fatto quando»)
1. **Prova a mano** (utente + 5 min): da Leghe, loggato, aprire lo stemma nel browser, copiare l'URL e dire se si apre in una finestra anonima. Fatto quando: sappiamo se l'URL è pubblico.
2. `fanta/scarica_immagine.py`: funzione pura `scarica(url) -> bytes` con tutti i controlli di sicurezza. Fatto quando: test con server finto (host privato, redirect, troppo grande, non immagine) verdi.
3. Rotta `da-url` + test di isolamento tra utenti (`tests/test_isolamento.py`). Fatto quando: l'immagine di A non compare per B.
4. Web: pulsante «Da indirizzo web» + anteprima + testi; alzare `VERSIONE` in `sw.js` e `novita.json`. Fatto quando: provato nel browser con un URL vero.
5. Web: `share_target` nel manifest + pagina di ricezione. Fatto quando: «Condividi» dall'iPhone apre la scelta stemma/divisa.
6. iOS: Share Extension. 7. Android: intent `ACTION_SEND`. Fatto quando: l'immagine condivisa arriva nella Lega.
8. Riduzione a 512 px lato client (web, poi native).

## 7. Decisioni dell'utente
- Fare la prova del passo 1 (serve il suo login).
- Se i passi 6-7 (native) valgono il lavoro o basta la PWA.
- Leggere l'art. 10 dei termini se si vuole andare oltre il caricamento manuale.

Fonti: [Termini Fantacalcio](https://www.fantacalcio.it/termini-e-condizioni), [reset leghe 2025 (loghi)](https://www.fantacalcio.it/news/redazionali/22_07_2025/reset-leghe-fantacalcio-la-data-479711).
