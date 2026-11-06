"""Genera THIRD-PARTY-NOTICES.md: licenze delle dipendenze Python dirette (requirements.in) e di quelle che porta con sé il server.

Uso (dalla radice del repository):
    python script/avvisi_terze_parti.py            scrive THIRD-PARTY-NOTICES.md
    python script/avvisi_terze_parti.py --controlla  esce con 1 se il file non è aggiornato o manca una licenza nella tabella
    python script/avvisi_terze_parti.py --metadati   confronta la tabella con le licenze dei pacchetti installati (informativo)

La tabella LICENZE è scritta a mano (letta dai metadati dei pacchetti il 31/10/2026): un pacchetto nuovo in requirements.in senza
riga qui fa fallire il controllo, così nessuna dipendenza resta senza licenza dichiarata. Il file non contiene versioni.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
FILE_REQUISITI = RADICE / "requirements.in"          # elenco scritto a mano (requirements.txt ha anche le indirette, con hash)
FILE_USCITA = RADICE / "THIRD-PARTY-NOTICES.md"

# pacchetto -> (licenza SPDX, a cosa serve, "d" se solo per sviluppo e prove)
LICENZE: dict[str, tuple[str, str, str]] = {
    "requests": ("Apache-2.0", "richieste HTTP alle fonti dati", ""),
    "pandas": ("BSD-3-Clause", "calcoli sulle tabelle", ""),
    "openpyxl": ("MIT", "lettura di rose in Excel", ""),
    "beautifulsoup4": ("MIT", "lettura delle pagine HTML delle fonti", ""),
    "lxml": ("BSD-3-Clause", "analisi HTML e XML", ""),
    "python-dotenv": ("BSD-3-Clause", "lettura del file .env", ""),
    "fastapi": ("MIT", "il server web", ""),
    "uvicorn": ("BSD-3-Clause", "il server web", ""),
    "python-multipart": ("Apache-2.0", "caricamento di file", ""),
    "pywebpush": ("MPL-2.0", "notifiche web push", ""),
    "pyjwt": ("MIT", "verifica dell'accesso con Google", ""),
    "httpx": ("BSD-3-Clause", "client HTTP (anche nei test)", ""),
    "pillow": ("MIT-CMU", "elaborazione delle immagini", ""),
    "pytest": ("MIT", "test", "d"),
    "pytest-xdist": ("MIT", "test in parallelo", "d"),
}
# dipendenze che i pacchetti qui sopra portano con sé e che vale la pena nominare
INDIRETTE: dict[str, tuple[str, str, str]] = {
    "starlette": ("BSD-3-Clause", "base di FastAPI", "fastapi"),
    "pydantic": ("MIT", "controllo dei dati ricevuti", "fastapi"),
    "numpy": ("BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0", "calcoli numerici", "pandas"),
    "cryptography": ("Apache-2.0 OR BSD-3-Clause", "cifratura delle notifiche", "pywebpush"),
    "py-vapid": ("MPL-2.0", "chiavi per le notifiche web push", "pywebpush"),
    "http-ece": ("MIT", "cifratura dei messaggi push", "pywebpush"),
}

TESTO_MPL = ("Il codice di **pywebpush** e **py-vapid** è sotto licenza MPL-2.0: i loro file restano sotto quella licenza e il loro sorgente "
             "è disponibile su https://pypi.org/project/pywebpush/ e https://pypi.org/project/py-vapid/. SchieraXI non li modifica. "
             "La MPL-2.0 nomina l'AGPL-3.0 tra le licenze con cui può essere combinata.")


def nomi_requisiti(testo: str) -> list[str]:
    """Nomi dei pacchetti in requirements.in (senza versioni, commenti, righe vuote)."""
    nomi = []
    for riga in testo.splitlines():
        riga = riga.split("#", 1)[0].strip()
        if riga and not riga.startswith("-"):
            nomi.append(re.split(r"[<>=!~;\[ ]", riga, maxsplit=1)[0].lower().replace("_", "-"))
    return nomi


def mancanti(nomi: list[str]) -> list[str]:
    return [n for n in nomi if n not in LICENZE]


def genera(nomi: list[str]) -> str:
    righe = [
        "# Avvisi sui programmi di terzi",
        "",
        "SchieraXI usa programmi aperti scritti da altri. Qui sono elencati con la loro licenza. Questo file è generato da",
        "`script/avvisi_terze_parti.py` a partire da `requirements.in`: non va modificato a mano.",
        "Il server si installa con `pip` e non include il codice di queste librerie; chi le riceve da `pip` riceve anche le loro licenze.",
        "",
        "## Dipendenze Python dirette",
        "",
        "| Pacchetto | Licenza | A cosa serve |",
        "|---|---|---|",
    ]
    for n in nomi:
        lic, uso, sviluppo = LICENZE[n]
        righe.append(f"| {n} | {lic} | {uso}{' (solo sviluppo)' if sviluppo else ''} |")
    usati = [n for n in INDIRETTE if INDIRETTE[n][2] in nomi]
    if usati:
        righe += ["", "## Dipendenze indirette principali", "", "| Pacchetto | Licenza | A cosa serve |", "|---|---|---|"]
        for n in usati:
            lic, uso, _ = INDIRETTE[n]
            righe.append(f"| {n} | {lic} | {uso} |")
    righe += ["", "## Licenze con obblighi particolari", "", TESTO_MPL,
              "", "Apache-2.0, BSD e MIT chiedono di conservare l'avviso di copyright e il testo della licenza: restano nei pacchetti installati da `pip`.",
              "", "## App per iPhone", "",
              "L'app per iPhone non include librerie di terzi: usa solo i framework di sistema di Apple.",
              "", "## Font", "",
              "Il nome disegnato «SchieraXI» (sito e app) usa le lettere del font **Archivo** (Copyright 2020 The Archivo Project Authors, "
              "https://github.com/Omnibus-Type/Archivo), sotto licenza SIL Open Font License 1.1. Nel nome disegnato ci sono solo i tracciati "
              "delle lettere, non il font. Un sottoinsieme del font e la sua licenza stanno in `assets/marchio/wordmark/` "
              "(`Archivo-sottoinsieme.ttf`, `OFL.txt`).",
              "",
              "La web app serve anche un sottoinsieme di Archivo per numeri e titoli (larghezza semi-stretta, latino occidentale, cifre "
              "tabellari), con la licenza accanto: `fanta/web/caratteri/` (`archivo.woff2`, `OFL.txt`). Copyright e licenza restano anche "
              "dentro il file del font. Si rifà con `script/carattere_web.py`.",
              "", "## Dati e servizi", "", "I nomi dei dati e dei servizi usati sono elencati nella pagina «Crediti e fonti» dell'app (`/crediti`).", ""]
    return "\n".join(righe)


def principale(argv: list[str]) -> int:
    nomi = nomi_requisiti(FILE_REQUISITI.read_text(encoding="utf-8"))
    manca = mancanti(nomi)
    if manca:
        print("Manca la licenza in script/avvisi_terze_parti.py per:", ", ".join(manca), file=sys.stderr)
        return 1
    testo = genera(nomi)
    if "--metadati" in argv:
        from importlib import metadata
        for n, (lic, _, _) in {**LICENZE, **{k: v for k, v in INDIRETTE.items()}}.items():
            try:
                m = metadata.metadata(n)
            except metadata.PackageNotFoundError:
                print(f"{n}: non installato")
                continue
            dichiarata = m.get("License-Expression") or m.get("License") or ""
            print(f"{n}: tabella {lic} / pacchetto {dichiarata[:50] or '?'}")
        return 0
    if "--controlla" in argv:
        attuale = FILE_USCITA.read_text(encoding="utf-8") if FILE_USCITA.exists() else ""
        if attuale.replace("\r\n", "\n") != testo:
            print("THIRD-PARTY-NOTICES.md non è aggiornato: lancia python script/avvisi_terze_parti.py", file=sys.stderr)
            return 1
        return 0
    FILE_USCITA.write_text(testo, encoding="utf-8", newline="\n")
    print(f"Scritto {FILE_USCITA.name} ({len(nomi)} pacchetti)")
    return 0


if __name__ == "__main__":
    sys.exit(principale(sys.argv[1:]))
