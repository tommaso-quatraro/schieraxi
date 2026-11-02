# Avvisi sui programmi di terzi

SchieraXI usa programmi aperti scritti da altri. Qui sono elencati con la loro licenza. Questo file è generato da
`script/avvisi_terze_parti.py` a partire da `requirements.in`: non va modificato a mano.
Il server si installa con `pip` e non include il codice di queste librerie; chi le riceve da `pip` riceve anche le loro licenze.

## Dipendenze Python dirette

| Pacchetto | Licenza | A cosa serve |
|---|---|---|
| requests | Apache-2.0 | richieste HTTP alle fonti dati |
| pandas | BSD-3-Clause | calcoli sulle tabelle |
| openpyxl | MIT | lettura di rose in Excel |
| beautifulsoup4 | MIT | lettura delle pagine HTML delle fonti |
| lxml | BSD-3-Clause | analisi HTML e XML |
| fastapi | MIT | il server web |
| uvicorn | BSD-3-Clause | il server web |
| python-multipart | Apache-2.0 | caricamento di file |
| pywebpush | MPL-2.0 | notifiche web push |
| pyjwt | MIT | verifica dell'accesso con Google |

## Dipendenze indirette principali

| Pacchetto | Licenza | A cosa serve |
|---|---|---|
| starlette | BSD-3-Clause | base di FastAPI |
| pydantic | MIT | controllo dei dati ricevuti |
| numpy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | calcoli numerici |
| cryptography | Apache-2.0 OR BSD-3-Clause | cifratura delle notifiche |
| py-vapid | MPL-2.0 | chiavi per le notifiche web push |
| http-ece | MIT | cifratura dei messaggi push |

## Licenze con obblighi particolari

Il codice di **pywebpush** e **py-vapid** è sotto licenza MPL-2.0: i loro file restano sotto quella licenza e il loro sorgente è disponibile su https://pypi.org/project/pywebpush/ e https://pypi.org/project/py-vapid/. SchieraXI non li modifica. La MPL-2.0 nomina l'AGPL-3.0 tra le licenze con cui può essere combinata.

Apache-2.0, BSD e MIT chiedono di conservare l'avviso di copyright e il testo della licenza: restano nei pacchetti installati da `pip`.

## App per iPhone

L'app per iPhone non include librerie di terzi: usa solo i framework di sistema di Apple.

## Font

Il nome disegnato «SchieraXI» (sito e app) usa le lettere del font **Archivo** (Copyright 2020 The Archivo Project Authors, https://github.com/Omnibus-Type/Archivo), sotto licenza SIL Open Font License 1.1. Sito e app contengono solo i tracciati delle lettere, non il font. Un sottoinsieme del font e la sua licenza stanno in `assets/marchio/wordmark/` (`Archivo-sottoinsieme.ttf`, `OFL.txt`).

## Dati e servizi

I nomi dei dati e dei servizi usati sono elencati nella pagina «Crediti e fonti» dell'app (`/crediti`).
