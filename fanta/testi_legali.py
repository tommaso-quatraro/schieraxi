"""Pagine «Privacy», «Termini d'uso», «Crediti e fonti» ed «Elimina il tuo account» (servite a /privacy, /termini, /crediti,
/elimina-account, senza accesso).

Tutte le frasi stanno in `TESTI` (lingua -> chiave -> testo): per tradurre basta aggiungere una lingua con le stesse chiavi.
Si configurano con variabili d'ambiente:
  FANTA_TITOLARE   chi è il titolare del trattamento (nome e recapito); senza, la pagina dice «chi gestisce l'app»;
  FANTA_CONTATTO   a chi scrivere per privacy, richieste e segnalazioni (per esempio un indirizzo email);
  FANTA_SORGENTE   indirizzo https del codice sorgente (AGPL); vuoto nel codice privato;
  FANTA_BACKUP_GIORNI  per quanti giorni restano le copie di sicurezza (se non indicato: «un tempo limitato»).
Il testo cambia da solo secondo il modo di iscrizione (FANTA_REGISTRAZIONE). Nessuna promessa su ricavi o scopo di lucro.
"""
from __future__ import annotations

import html
import os
import re

LINGUA = "it"
ETA_MINIMA = 14          # in Italia 14 anni è l'età per dare il consenso al trattamento dei dati online

# Ogni pagina è una lista di blocchi: ("h", titolo), ("p", testo), ("li", [voci]), ("sorgente",).
# Nei testi {contatto}, {titolare}, {eta}, {iscrizione}, {email}, {backup} sono sostituiti.
TESTI: dict[str, dict] = {
    "it": {
        "indietro": "Torna a SchieraXI",
        "altra_privacy": "Privacy",
        "altra_termini": "Termini d'uso",
        "altra_crediti": "Crediti e fonti",
        "altra_elimina": "Elimina il tuo account",
        "contatto_manca": "chi gestisce l'app (di solito la persona che ti ha dato il codice d'invito)",
        "titolare_manca": "chi gestisce questa copia dell'app (la persona o l'organizzazione indicata da chi te l'ha proposta)",
        "backup_manca": "un tempo limitato",
        "backup_giorni": "al massimo {n} giorni",
        "iscrizione_invito": "Per iscriverti serve un codice d'invito. L'account è personale: non darlo ad altri.",
        "iscrizione_email": "Per iscriverti serve un codice d'invito e un indirizzo email, che verifichi con un codice. L'account è personale: non darlo ad altri.",
        "iscrizione_aperta": "Per iscriverti serve un indirizzo email, che verifichi con un codice (oppure un codice d'invito). L'account è personale: non darlo ad altri.",
        "email_invito": "L'email è facoltativa: puoi aggiungerla per recuperare l'accesso. Se la aggiungi la tratteremo solo per mandarti i codici di verifica e di recupero.",
        "email_email": "L'indirizzo email è richiesto per iscriverti e per recuperare l'accesso: lo usiamo solo per mandarti i codici di verifica e di recupero.",
        "email_aperta": "L'indirizzo email è richiesto per iscriverti e per recuperare l'accesso: lo usiamo solo per mandarti i codici di verifica e di recupero.",
        "titolo_privacy": "Privacy: quali dati raccoglie SchieraXI",
        "titolo_termini": "Termini d'uso di SchieraXI",
        "titolo_crediti": "Crediti e fonti",
        "titolo_elimina": "Elimina il tuo account",
        "aggiornato": "Ultimo aggiornamento: 1 novembre 2026",
        "fonti_tue": "Le rose, le regole della lega, gli stemmi e le maglie che inserisci tu.",
        "sorgente_con": "Il codice sorgente di SchieraXI è pubblicato con licenza AGPL-3.0:",
        "sorgente_senza": "Il codice sorgente di SchieraXI è disponibile con licenza AGPL-3.0 dove indicato da chi gestisce questa copia dell'app.",
        "privacy": [
            ("p", "SchieraXI è un'app che consiglia la formazione per il fantacalcio. Questa pagina dice, in modo semplice, "
                  "quali dati tuoi tiene, perché e per quanto tempo. Se qualcosa non è chiaro, scrivi a {contatto}."),
            ("h", "Chi è il titolare del trattamento"),
            ("p", "Il titolare del trattamento dei tuoi dati è {titolare}. Per qualunque richiesta sulla privacy puoi scrivere a {contatto}."),
            ("h", "Quali dati tiene"),
            ("li", [
                "Il tuo nome utente e il nome che scegli di mostrare.",
                "La password, ma solo sotto forma di «impronta» (hash): nessuno, nemmeno chi gestisce l'app, può leggerla. Lo stesso vale per il codice di recupero.",
                "La tua lega: regole, rose, la squadra che hai scelto, le tue scelte di formazione e i giocatori che osservi.",
                "Se qualcuno te l'ha offerto, chi gestisce l'app può importare le tue rose al posto tuo, su tua richiesta, e il fatto resta nel registro di sicurezza "
                "(chi, per chi, quante squadre: mai il testo). Quando sostituisce tutte le rose, tiene le ultime 5 copie delle rose di prima: stanno nella tua cartella "
                "e si cancellano insieme al tuo account.",
                "Le iscrizioni alle notifiche del tuo dispositivo (se le attivi) e le impostazioni degli avvisi.",
                "Le sessioni aperte (un codice casuale conservato come hash, il tipo di dispositivo, quando le hai usate l'ultima volta) e quindi la data dell'ultimo accesso.",
                "Un registro di sicurezza con accessi falliti, blocchi e simili: contiene il nome utente e l'indirizzo di rete accorciato (senza la parte che indica il singolo apparecchio), mai password né codici. "
                "Per riconoscere i tuoi dispositivi (così chi prova password sul tuo nome non ti chiude fuori) il server tiene, per 60 giorni dall'ultimo accesso, solo un'impronta degli indirizzi di rete e di un segreto casuale salvato sul dispositivo, calcolata con una chiave segreta del server: senza quella chiave non si risale all'indirizzo. "
                "Queste impronte si cancellano quando cambi o recuperi la password e quando usi «Esci da tutti i dispositivi». Anche il registro delle richieste del server scrive l'indirizzo di rete solo accorciato.",
                "Statistiche d'uso aggregate e anonime: ogni giorno si conta quante volte è stata usata ciascuna schermata o funzione dell'app. "
                "Sono solo numeri complessivi per tutti gli utenti insieme: non contengono nome utente, indirizzo di rete né altro che riguardi te, "
                "e si cancellano dopo 28 giorni. Non sono dati personali e non servono a pubblicità.",
                "Se entri con Google (dove il server lo permette): l'identificativo che Google ci dà per il tuo account, l'indirizzo email che Google ci comunica e se Google lo ha verificato. "
                "Non riceviamo né conserviamo il tuo nome, la tua foto, i tuoi contatti né alcun codice di accesso di Google. L'accesso con Google è soggetto anche all'informativa privacy di Google. "
                "Puoi scollegare Google da Impostazioni > Il tuo account > Accessi e togliere il permesso dal tuo Account Google, in Sicurezza > Accedi con Google.",
                "{email}",
            ]),
            ("h", "Perché li usiamo e su quale base"),
            ("li", [
                "Per darti il servizio che hai chiesto (account, lega, consigli, avvisi): è necessario per eseguire il servizio che hai richiesto iscrivendoti.",
                "Per mantenere l'app sicura (registro di sicurezza, blocchi dopo troppi tentativi): è un interesse legittimo di chi gestisce l'app.",
                "Per le notifiche sul dispositivo: solo se le attivi tu, e puoi disattivarle quando vuoi.",
            ]),
            ("h", "Con chi li condividiamo"),
            ("p", "Non vendiamo né cediamo i tuoi dati a nessuno e non li usiamo per fare pubblicità. Possono trattarli, solo per far funzionare l'app, "
                  "il fornitore del server dove l'app gira, il servizio che spedisce le email (se sono attive) e i servizi di notifica del tuo dispositivo o del tuo browser "
                  "(per esempio quelli di Apple, Google e Mozilla), che ricevono avvisi cifrati. Se uno di questi servizi ha sede fuori dall'Unione europea, "
                  "il trasferimento avviene con le garanzie previste dalla legge (per esempio le clausole contrattuali standard o la decisione di adeguatezza)."),
            ("h", "Dove stanno i dati e per quanto tempo"),
            ("li", [
                "I dati stanno sul server di chi gestisce l'app. Le copie di sicurezza (backup) possono stare su un altro computer o servizio di chi gestisce l'app.",
                "Account, lega e scelte restano finché non elimini il tuo account. Eliminandolo si cancella anche il collegamento con Google.",
                "Le sessioni si chiudono dopo 30 giorni senza usarle e in ogni caso dopo 180 giorni.",
                "Il registro di sicurezza si cancella da solo: ogni riga resta al massimo 30 giorni.",
                "Le copie di sicurezza si conservano per {backup}.",
            ]),
            ("h", "Cosa NON facciamo"),
            ("li", [
                "Nessuna pubblicità al momento. Se un giorno ci sarà, lo diremo prima e aggiorneremo questa pagina.",
                "Nessun tracciamento: niente Google Analytics, niente pixel, niente strumenti che ti seguono su altri siti. "
                "L'unico conteggio sono le statistiche d'uso anonime descritte sopra, che non possono risalire a te.",
                "Nessun cookie di marketing. Esiste un solo cookie tecnico, quello della sessione, che ti tiene dentro l'app.",
            ]),
            ("h", "Cancellazione e copia dei dati"),
            ("p", "Da Impostazioni > Il tuo account, con «Scarica i tuoi dati», ricevi subito un file (JSON, leggibile anche da altri programmi) con i tuoi dati: "
                  "quelli dell'account (nome, email, accessi collegati, termini accettati) e quelli della lega (regole, rose, scelte, giocatori seguiti, "
                  "impostazioni delle notifiche). La password e gli altri codici segreti non ci sono mai. Con «Elimina il mio account» li cancelli tutti dal server. "
                  "Per altre richieste scrivi a {contatto}. "
                  "L'eliminazione è definitiva. Nelle copie di sicurezza i tuoi dati possono restare fino alla scadenza della copia ({backup}). "
                  "Se non riesci ad accedere, leggi la pagina «Elimina il tuo account»."),
            ("h", "I tuoi diritti"),
            ("p", "Puoi chiedere di accedere ai tuoi dati e riceverne una copia, di correggerli, di cancellarli, di limitarne o di opporti al trattamento, e di avere i dati "
                  "in un formato leggibile da un altro servizio (portabilità). Per le notifiche puoi ritirare il consenso quando vuoi. "
                  "La copia dei tuoi dati la scarichi da solo da Impostazioni > Il tuo account > «Scarica i tuoi dati»; per qualunque altra richiesta scrivi a {contatto}. Puoi anche fare reclamo al Garante per la protezione dei dati personali."),
            ("h", "Età minima"),
            ("p", "L'app è per persone con almeno {eta} anni."),
            ("h", "Cambiamenti"),
            ("p", "Se questa pagina cambia in modo importante, lo scriviamo nelle novità dell'app."),
        ],
        "termini": [
            ("p", "Usando SchieraXI accetti queste regole. Sono poche e semplici."),
            ("h", "Cos'è SchieraXI"),
            ("p", "Un aiuto per il fantacalcio: propone formazioni, mostra statistiche e analizza scambi. "
                  "Non è collegato a Leghe Fantacalcio, a Fantacalcio.it, alla Lega Serie A né a nessuna squadra o lega di calcio, che non lo approvano né lo sostengono. "
                  "Se in futuro ci saranno pubblicità o pagamenti lo diremo prima e aggiorneremo questi termini."),
            ("h", "I consigli sono stime"),
            ("p", "Le formazioni e i voti previsti sono calcoli statistici: non garantiscono nessun risultato. "
                  "La scelta finale è tua e il servizio è offerto «così com'è», senza garanzie e senza responsabilità per punti persi o partite perse."),
            ("h", "Fonti dei dati"),
            ("p", "I dati arrivano da fonti di terzi (per esempio siti di calendario, voti, probabili formazioni, statistiche) oppure da file che inserisci tu. "
                  "Ogni fonte ha le sue condizioni d'uso e chi gestisce l'app può accenderla o spegnerla. "
                  "Non sono dati ufficiali: possono essere in ritardo, incompleti o sbagliati. Nomi, marchi, voti e statistiche appartengono ai rispettivi proprietari. "
                  "Le fonti usate sono elencate nella pagina «Crediti e fonti»."),
            ("h", "Immagini e file che carichi"),
            ("p", "Se carichi o indichi uno stemma, una maglia o un altro file, garantisci di averne il diritto e che non viola diritti di altri. "
                  "Lo usiamo solo per mostrarlo a te e alla tua lega. Se qualcuno segnala un problema, o ce lo chiedi tu, lo togliamo: scrivi a {contatto}. "
                  "Possiamo togliere file che sembrano illeciti o dannosi."),
            ("h", "Il tuo account"),
            ("li", [
                "{iscrizione}",
                "Scegli una password lunga e conserva il codice di recupero. Se entri con Google, proteggi bene anche il tuo Account Google: chi lo usa può entrare nel tuo account SchieraXI.",
                "Hai almeno {eta} anni.",
                "Non usare l'app per disturbare il servizio, cercare di entrare nei dati di altri o caricare file dannosi: l'accesso può essere chiuso.",
            ]),
            ("h", "Disponibilità"),
            ("p", "L'app può fermarsi, cambiare o chiudere in qualunque momento. Se ti servono, scarica ogni tanto i tuoi dati da Impostazioni > Il tuo account > «Scarica i tuoi dati». "
                  "Per capire cosa tenere in primo piano contiamo, in forma anonima e aggregata, quante volte è usata ogni funzione (vedi la pagina Privacy)."),
            ("h", "Privacy e contatti"),
            ("p", "Come trattiamo i tuoi dati è scritto nella pagina Privacy. Per domande o segnalazioni scrivi a {contatto}."),
        ],
        "crediti": [
            ("p", "SchieraXI si appoggia al lavoro di altri. Qui trovi da dove arrivano i dati e quali programmi aperti usiamo."),
            ("h", "Fonti dei dati"),
            ("p", "Sono elencate solo le fonti accese in questa copia dell'app. Ogni fonte resta di chi la pubblica e vale con le sue condizioni d'uso."),
            ("fonti",),
            ("p", "I nomi di giocatori, squadre e campionati sono usati solo per indicarli. «Serie A», «Fantacalcio» e i nomi dei club appartengono ai rispettivi proprietari; "
                  "SchieraXI non è affiliata a loro."),
            ("h", "Programmi aperti"),
            ("p", "SchieraXI usa, fra gli altri, questi programmi liberi, ognuno con la sua licenza (l'elenco completo con i testi è nel file THIRD-PARTY-NOTICES.md del codice):"),
            ("li", [
                "FastAPI, Starlette, Uvicorn, Pydantic, httpx, pandas, NumPy, lxml: licenze BSD e MIT.",
                "requests, cryptography (Apache-2.0 o BSD), python-multipart: licenza Apache-2.0.",
                "pywebpush e py-vapid: licenza MPL-2.0 (il loro sorgente resta disponibile su PyPI).",
                "openpyxl, Beautiful Soup, http-ece: licenza MIT. Pillow: licenza MIT-CMU.",
            ]),
            ("h", "Codice sorgente"),
            ("sorgente",),
        ],
        "elimina": [
            ("p", "Puoi cancellare il tuo account in qualunque momento. La cancellazione è definitiva."),
            ("h", "Dall'app"),
            ("li", [
                "Apri SchieraXI e accedi.",
                "Vai in Impostazioni > Il tuo account.",
                "Tocca «Elimina il mio account» e conferma con la tua password (se entri solo con Google, ti chiede di confermare con Google).",
            ]),
            ("p", "Vengono cancellati subito il tuo account, le sessioni aperte, la tua lega con rose, scelte e osservati, le iscrizioni alle notifiche e le impostazioni degli avvisi."),
            ("h", "Se non riesci ad accedere"),
            ("pc", "Scrivi a {contatto} da un indirizzo email collegato al tuo account, o indicando il tuo nome utente. "
                   "Ti risponderemo e cancelleremo l'account appena possibile.",
                   "Chi gestisce questa copia dell'app non ha ancora indicato un recapito pubblico. Chiedi la cancellazione alla persona che ti ha dato "
                   "l'accesso, indicando il tuo nome utente: potrà cancellare l'account per te."),
            ("h", "Cosa può restare"),
            ("li", [
                "Le copie di sicurezza (backup): i tuoi dati scompaiono quando la copia scade ({backup}).",
                "Il registro di sicurezza, che contiene il nome utente e l'indirizzo di rete accorciato: ogni riga si cancella da sola entro 30 giorni.",
            ]),
            ("p", "Altri dettagli sono nella pagina Privacy."),
        ],
    },
    "en": {
        "indietro": "Back to SchieraXI",
        "altra_privacy": "Privacy",
        "altra_termini": "Terms of use",
        "altra_crediti": "Credits and sources",
        "altra_elimina": "Delete your account",
        "contatto_manca": "whoever runs the app (usually the person who gave you the invitation code)",
        "titolare_manca": "whoever runs this copy of the app (the person or organisation named by whoever offered it to you)",
        "backup_manca": "a limited time",
        "backup_giorni": "at most {n} days",
        "iscrizione_invito": "To sign up you need an invitation code. The account is personal: do not give it to others.",
        "iscrizione_email": "To sign up you need an invitation code and an email address, which you verify with a code. The account is personal: do not give it to others.",
        "iscrizione_aperta": "To sign up you need an email address, which you verify with a code (or an invitation code). The account is personal: do not give it to others.",
        "email_invito": "The email is optional: you can add it to recover your access. If you add it we will use it only to send you verification and recovery codes.",
        "email_email": "The email address is required to sign up and to recover your access: we use it only to send you verification and recovery codes.",
        "email_aperta": "The email address is required to sign up and to recover your access: we use it only to send you verification and recovery codes.",
        "titolo_privacy": "Privacy: what data SchieraXI collects",
        "titolo_termini": "SchieraXI terms of use",
        "titolo_crediti": "Credits and sources",
        "titolo_elimina": "Delete your account",
        "aggiornato": "Last updated: 1 November 2026",
        "traduzione_nota": "This is an English translation provided for convenience. The Italian text is the one that applies and it is the reference in case of doubt.",
        "versione_italiana": "Read the Italian version",
        "fonti_tue": "The rosters, the league rules, the crests and the shirts that you enter yourself.",
        "sorgente_con": "The source code of SchieraXI is published under the AGPL-3.0 licence:",
        "sorgente_senza": "The source code of SchieraXI is available under the AGPL-3.0 licence where indicated by whoever runs this copy of the app.",
        "privacy": [
            ("p", "SchieraXI is an app that recommends lineups for fantasy football. This page says, in simple terms, "
                  "what data of yours it keeps, why and for how long. If anything is unclear, write to {contatto}."),
            ("h", "Who is the data controller"),
            ("p", "The controller of your data is {titolare}. For any privacy request you can write to {contatto}."),
            ("h", "What data it keeps"),
            ("li", [
                "Your username and the name you choose to show.",
                "Your password, but only as a «fingerprint» (hash): nobody, not even whoever runs the app, can read it. The same goes for the recovery code.",
                "Your league: rules, rosters, the team you chose, your lineup choices and the players you watch.",
                "If someone has offered it to you, whoever runs the app can import your rosters for you, at your request, and this is recorded in the security log "
                "(who, for whom, how many teams: never the text). When it replaces all the rosters, it keeps the last 5 copies of the previous rosters: they are in your folder "
                "and are deleted together with your account.",
                "The notification subscriptions of your device (if you turn them on) and the alert settings.",
                "Open sessions (a random code stored as a hash, the type of device, when you last used them) and therefore the date of your last sign-in.",
                "A security log with failed sign-ins, blocks and the like: it contains the username and the shortened network address (without the part that identifies a single device), never passwords or codes. "
                "To recognise your devices (so that someone trying passwords on your name cannot lock you out) the server keeps, for 60 days after your last sign-in, only a fingerprint of your network addresses and of a random secret stored on the device, computed with a secret key of the server: without that key the address cannot be recovered. "
                "These fingerprints are deleted when you change or recover your password and when you use «Sign out of all devices». The server's request log also writes the network address only in shortened form.",
                "Aggregated, anonymous usage statistics: every day we count how many times each screen or feature of the app was used. "
                "They are only overall numbers for all users together: they contain no username, no network address and nothing else about you, "
                "and are deleted after 28 days. They are not personal data and are not used for advertising.",
                "If you sign in with Google (where the server offers it): the identifier Google gives us for your account, the email address Google tells us, and whether Google has verified it. "
                "We do not receive or keep your name, photo, contacts or any Google token. Signing in with Google is also subject to Google's own privacy policy. "
                "You can unlink Google in Settings > Your account > Sign-in methods, and revoke the access in your Google Account under Security > Sign in with Google.",
                "{email}",
            ]),
            ("h", "Why we use it and on what basis"),
            ("li", [
                "To give you the service you asked for (account, league, advice, alerts): it is necessary to perform the service you requested by signing up.",
                "To keep the app secure (security log, blocks after too many attempts): it is a legitimate interest of whoever runs the app.",
                "For notifications on your device: only if you turn them on, and you can turn them off whenever you like.",
            ]),
            ("h", "Who we share it with"),
            ("p", "We do not sell or give your data to anyone and we do not use it for advertising. It may be processed, only to make the app work, "
                  "by the provider of the server where the app runs, the service that sends emails (if active) and the notification services of your device or browser "
                  "(for example Apple, Google and Mozilla), which receive encrypted alerts. If one of these services is based outside the European Union, "
                  "the transfer takes place with the safeguards required by law (for example standard contractual clauses or an adequacy decision)."),
            ("h", "Where the data is and for how long"),
            ("li", [
                "The data is on the server of whoever runs the app. Backup copies may be on another computer or service of whoever runs the app.",
                "Account, league and choices stay until you delete your account. Deleting it also removes the link with Google.",
                "Sessions end after 30 days without use and in any case after 180 days.",
                "The security log deletes itself: each line is kept for at most 30 days.",
                "Backup copies are kept for {backup}.",
            ]),
            ("h", "What we do NOT do"),
            ("li", [
                "No advertising at the moment. If there is one day, we will say so beforehand and update this page.",
                "No tracking: no Google Analytics, no pixels, no tools that follow you on other sites. "
                "The only counting is the anonymous usage statistics described above, which cannot be traced back to you.",
                "No marketing cookies. There is only one technical cookie, the session one, which keeps you inside the app.",
            ]),
            ("h", "Deletion and a copy of your data"),
            ("p", "From Settings > Your account, with «Download your data», you get a file right away (JSON, readable by other programs too) with your data: "
                  "your account (name, email, linked sign-ins, accepted terms) and your league (rules, squads, choices, followed players, "
                  "notification settings). The password and other secret codes are never in it. With «Delete my account» you delete all of it from the server. "
                  "For other requests write to {contatto}. "
                  "Deletion is final. In backup copies your data may remain until the copy expires ({backup}). "
                  "If you cannot sign in, read the page «Delete your account»."),
            ("h", "Your rights"),
            ("p", "You can ask to access your data and receive a copy, to correct it, to delete it, to restrict or object to its processing, and to have the data "
                  "in a format readable by another service (portability). For notifications you can withdraw your consent at any time. "
                  "You can download a copy of your data yourself from Settings > Your account > «Download your data»; for any other request write to {contatto}. You can also complain to the data protection authority."),
            ("h", "Minimum age"),
            ("p", "The app is for people aged {eta} or over."),
            ("h", "Changes"),
            ("p", "If this page changes in an important way, we will say so in the app's news."),
        ],
        "termini": [
            ("p", "By using SchieraXI you accept these rules. They are few and simple."),
            ("h", "What SchieraXI is"),
            ("p", "A helper for fantasy football: it proposes lineups, shows statistics and analyses trades. "
                  "It is not connected to Leghe Fantacalcio, Fantacalcio.it, Lega Serie A or any football team or league, which neither approve nor endorse it. "
                  "If advertising or payments come in the future we will say so beforehand and update these terms."),
            ("h", "The advice is an estimate"),
            ("p", "The lineups and forecast grades are statistical calculations: they guarantee no result. "
                  "The final choice is yours and the service is offered «as is», without warranties and without liability for points or matches lost."),
            ("h", "Data sources"),
            ("p", "The data comes from third-party sources (for example calendar, grades, probable lineups and statistics sites) or from files you enter yourself. "
                  "Each source has its own terms of use and whoever runs the app can turn it on or off. "
                  "It is not official data: it may be late, incomplete or wrong. Names, trademarks, grades and statistics belong to their respective owners. "
                  "The sources used are listed on the «Credits and sources» page."),
            ("h", "Images and files you upload"),
            ("p", "If you upload or point to a crest, a shirt or another file, you guarantee that you have the right to do so and that it does not infringe the rights of others. "
                  "We use it only to show it to you and your league. If someone reports a problem, or you ask us, we remove it: write to {contatto}. "
                  "We may remove files that look unlawful or harmful."),
            ("h", "Your account"),
            ("li", [
                "{iscrizione}",
                "Choose a long password and keep the recovery code. If you sign in with Google, protect your Google Account well too: whoever uses it can enter your SchieraXI account.",
                "You are at least {eta} years old.",
                "Do not use the app to disturb the service, try to get into other people's data or upload harmful files: access may be closed.",
            ]),
            ("h", "Availability"),
            ("p", "The app may stop, change or close at any time. If you need it, download your data now and then from Settings > Your account > «Download your data». "
                  "To understand what to keep in the foreground we count, anonymously and in aggregate, how many times each feature is used (see the Privacy page)."),
            ("h", "Privacy and contacts"),
            ("p", "How we process your data is written on the Privacy page. For questions or reports write to {contatto}."),
        ],
        "crediti": [
            ("p", "SchieraXI builds on the work of others. Here you find where the data comes from and which open programs we use."),
            ("h", "Data sources"),
            ("p", "Only the sources turned on in this copy of the app are listed. Each source remains its publisher's and applies with its own terms of use."),
            ("fonti",),
            ("p", "The names of players, teams and leagues are used only to identify them. «Serie A», «Fantacalcio» and the club names belong to their respective owners; "
                  "SchieraXI is not affiliated with them."),
            ("h", "Open programs"),
            ("p", "SchieraXI uses, among others, these free programs, each with its own licence (the full list with the texts is in the THIRD-PARTY-NOTICES.md file of the code):"),
            ("li", [
                "FastAPI, Starlette, Uvicorn, Pydantic, httpx, pandas, NumPy, lxml: BSD and MIT licences.",
                "requests, cryptography (Apache-2.0 or BSD), python-multipart: Apache-2.0 licence.",
                "pywebpush and py-vapid: MPL-2.0 licence (their source remains available on PyPI).",
                "openpyxl, Beautiful Soup, http-ece: MIT licence. Pillow: MIT-CMU licence.",
            ]),
            ("h", "Source code"),
            ("sorgente",),
        ],
        "elimina": [
            ("p", "You can delete your account at any time. Deletion is final."),
            ("h", "From the app"),
            ("li", [
                "Open SchieraXI and sign in.",
                "Go to Settings > Your account.",
                "Tap «Delete my account» and confirm with your password (if you sign in only with Google, you are asked to confirm with Google).",
            ]),
            ("p", "Your account, open sessions, your league with rosters, choices and watched players, notification subscriptions and alert settings are deleted immediately."),
            ("h", "If you cannot sign in"),
            ("pc", "Write to {contatto} from an email address linked to your account, or stating your username. "
                   "We will reply and delete the account as soon as possible.",
                   "Whoever runs this copy of the app has not yet given a public contact. Ask for deletion from the person who gave you "
                   "access, stating your username: they can delete the account for you."),
            ("h", "What may remain"),
            ("li", [
                "Backup copies: your data disappears when the copy expires ({backup}).",
                "The security log, which contains the username and the shortened network address: each line deletes itself within 30 days.",
            ]),
            ("p", "More details are on the Privacy page."),
        ],
    },
}

LINGUE = ("it", "en")


def lingua_valida(valore: str | None) -> str:
    """La lingua chiesta con ?lingua=: solo quelle che abbiamo, altrimenti l'italiano."""
    return valore if valore in LINGUE else LINGUA


PAGINE = ("privacy", "termini", "crediti", "elimina")
PERCORSI = {"privacy": "/privacy", "termini": "/termini", "crediti": "/crediti", "elimina": "/elimina-account"}


def t(chiave: str, lingua: str = LINGUA) -> str:
    return TESTI.get(lingua, TESTI[LINGUA]).get(chiave) or TESTI[LINGUA][chiave]


def contatto() -> str:
    """Il contatto di chi gestisce l'app (FANTA_CONTATTO), oppure una frase generica."""
    valore = os.environ.get("FANTA_CONTATTO", "").strip()[:200]
    return valore or t("contatto_manca")


def titolare() -> str:
    """Il titolare del trattamento (FANTA_TITOLARE, per esempio «<TITOLARE>» fino a quando non si decide), oppure una frase generica."""
    valore = os.environ.get("FANTA_TITOLARE", "").strip()[:200]
    return valore or t("titolare_manca")


def sorgente() -> str:
    """Indirizzo https del codice sorgente (FANTA_SORGENTE); vuoto se non impostato o non valido. Usato anche da /api/stato."""
    valore = os.environ.get("FANTA_SORGENTE", "").strip()
    return valore if re.fullmatch(r"https://[^\s<>\"']{3,300}", valore) else ""


def _backup() -> str:
    try:
        n = int(os.environ.get("FANTA_BACKUP_GIORNI", ""))
    except ValueError:
        n = 0
    return t("backup_giorni").replace("{n}", str(n)) if 0 < n <= 3650 else t("backup_manca")


FONTI_TESTO = {
    "fantacalcio": "Fantacalcio.it: listone e quotazioni, calendario, voti e probabili formazioni.",
    "understat": "Understat: statistiche avanzate (gol e assist attesi, rigori).",
    "footballdata": "football-data.co.uk: statistiche di squadra (tiri, angoli, cartellini), usate solo per misure.",
    "espn": "ESPN: risultati in diretta.",
    "sosfanta": "Sosfanta: seconda fonte di probabili formazioni, usata solo per misure.",
}


def _fonti_accese() -> list[str]:
    """Le fonti esterne accese in questa copia dell'app (se il modulo degli interruttori non c'è, tutte quelle note)."""
    try:
        from . import fonti_attive
    except ImportError:
        return list(FONTI_TESTO)
    return [k for k in FONTI_TESTO if k in fonti_attive.FONTI and fonti_attive.acceso(k)]


def _modo() -> str:
    try:
        from .account_email import modo_registrazione
        return modo_registrazione()
    except Exception:  # noqa: BLE001 - una pagina di testo non deve mai fermarsi per questo
        return "invito"


def pagina(quale: str, lingua: str = LINGUA) -> str:
    """HTML completo della pagina `privacy`, `termini`, `crediti` o `elimina`. I valori ricevuti dall'ambiente sono sempre protetti (niente HTML)."""
    if quale not in PAGINE:
        raise ValueError(quale)
    modo = _modo()
    valori = {"{contatto}": contatto(), "{titolare}": titolare(), "{eta}": str(ETA_MINIMA), "{backup}": _backup(),
              "{iscrizione}": t(f"iscrizione_{modo}", lingua), "{email}": t(f"email_{modo}", lingua)}

    def testo(s: str) -> str:
        s = html.escape(s, quote=False)
        for chiave, valore in valori.items():
            s = s.replace(chiave, html.escape(valore, quote=False))
        return s

    corpo = []
    for blocco in TESTI.get(lingua, TESTI[LINGUA])[quale]:
        tipo = blocco[0]
        if tipo == "h":
            corpo.append(f"<h2>{testo(blocco[1])}</h2>")
        elif tipo == "p":
            corpo.append(f"<p>{testo(blocco[1])}</p>")
        elif tipo == "pc":                    # paragrafo con due versioni: con e senza un recapito indicato
            corpo.append(f"<p>{testo(blocco[1] if os.environ.get('FANTA_CONTATTO', '').strip() else blocco[2])}</p>")
        elif tipo == "fonti":
            voci = [FONTI_TESTO[k] for k in _fonti_accese() if k in FONTI_TESTO]
            voci.append(t("fonti_tue", lingua))
            corpo.append("<ul>" + "".join(f"<li>{html.escape(v)}</li>" for v in voci) + "</ul>")
        elif tipo == "sorgente":
            link = sorgente()
            corpo.append(f'<p>{html.escape(t("sorgente_con", lingua))} <a href="{html.escape(link)}" rel="noopener">{html.escape(link)}</a></p>'
                         if link else f"<p>{html.escape(t('sorgente_senza', lingua))}</p>")
        else:
            corpo.append("<ul>" + "".join(f"<li>{testo(v)}</li>" for v in blocco[1]) + "</ul>")
    titolo = t(f"titolo_{quale}", lingua)
    suffisso = "" if lingua == LINGUA else f"?lingua={lingua}"                       # i link restano nella lingua scelta
    altre = "".join(f'<a href="{PERCORSI[a]}{suffisso}">{html.escape(t("altra_" + a, lingua))}</a> ' for a in PAGINE if a != quale)
    nota = ("" if lingua == LINGUA else f'<p class="debole piccolo">{html.escape(t("traduzione_nota", lingua))} <a href="{PERCORSI[quale]}">{html.escape(t("versione_italiana", lingua))}</a></p>')
    return f"""<!doctype html>
<html lang="{lingua}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="robots" content="noindex">
  <title>{html.escape(titolo)} · SchieraXI</title>
  <meta name="theme-color" content="#07100b">
  <link rel="icon" href="/icona.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/stile.css">
  <script src="/legale.js"></script>
</head>
<body class="pagina-testo">
  <main class="carta testo-lungo" id="contenuto">
    <p><a href="/">{html.escape(t("indietro", lingua))}</a></p>
    <h1>{html.escape(titolo)}</h1>
    <p class="debole piccolo">{html.escape(t("aggiornato", lingua))}</p>
    {nota}
    {"".join(corpo)}
    <nav class="piede-legale" aria-label="Documenti">
      {altre}
    </nav>
  </main>
</body>
</html>
"""
