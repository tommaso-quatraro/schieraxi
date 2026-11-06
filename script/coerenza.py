#!/usr/bin/env python3
"""Coerenza web-iPhone come dati.

`docs/COERENZA-WEB-IPHONE.md` si genera dai dati in `docs/coerenza/`:
  testa.md, giornata.md, differenze-oggi.md, coda.md   parti di testo fisse
  vocabolario.json                                     {"righe": [{cosa, forma, mai}]}
  ammesse.json                                         {"introduzione", "voci": [{titolo, [precisazione], testo, motivo}]}
  schermate/<schermata>.json                           {"righe": [{id, schermata, web, iphone, forma, chi, stato}]}

Uso:
  python script/coerenza.py --scrivi      rigenera il documento dai dati
  python script/coerenza.py --controlla   controlla i dati e che il documento sia quello generato

Uscite: 0 tutto a posto; 1 dati sbagliati o documento diverso da quello generato; 2 uso sbagliato o file illeggibili.
Solo libreria standard. Un conflitto sul documento si risolve unendo i dati e rigenerandolo con --scrivi.
"""
import argparse
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DOCUMENTO = Path("docs") / "COERENZA-WEB-IPHONE.md"
DATI = Path("docs") / "coerenza"
STATI = ("da-fare", "fatto", "da-decidere")
CAMPI_SCHERMATA = ("schermata", "web", "iphone", "forma", "chi", "stato")
CAMPI_VOCABOLARIO = ("cosa", "forma", "mai")
CAMPI_AMMESSE = ("titolo", "testo", "motivo")
NOTA = (
    "> File generato: si cambiano i dati in docs/coerenza/, poi `python script/coerenza.py --scrivi`. "
    "Un conflitto su questo file si risolve unendo i dati e rigenerandolo."
)
INTESTAZIONE_SCHERMATE = "| # | Schermata | Web | iPhone | Forma giusta | Chi la sistema |\n|---|---|---|---|---|---|"
INTESTAZIONE_VOCABOLARIO = "| Cosa | Forma giusta | Mai |\n|---|---|---|"


class ErroreDati(Exception):
    """File dei dati mancante o non leggibile."""


def _leggi(percorso):
    try:
        return percorso.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError as e:
        raise ErroreDati(f"{percorso}: {e}") from e


def _leggi_json(percorso):
    try:
        return json.loads(_leggi(percorso))
    except json.JSONDecodeError as e:
        raise ErroreDati(f"{percorso}: JSON non valido ({e})") from e


def carica(radice):
    """Legge tutti i dati. Le schermate sono in ordine di id."""
    d = Path(radice) / DATI
    dati = {
        "parti": {n: _leggi(d / f"{n}.md").rstrip("\n") for n in ("testa", "giornata", "differenze-oggi", "coda")},
        "vocabolario": _leggi_json(d / "vocabolario.json"),
        "ammesse": _leggi_json(d / "ammesse.json"),
        "schermate": [],
    }
    for f in sorted((d / "schermate").glob("*.json")):
        for riga in _leggi_json(f).get("righe", []):
            dati["schermate"].append((f.name, riga))
    return dati


def valida(dati):
    """Elenco dei problemi trovati (vuoto = dati a posto)."""
    errori = []

    def campi_mancanti(dove, riga, campi):
        for c in campi:
            if not isinstance(riga.get(c), str) or not riga[c].strip():
                errori.append(f"{dove}: manca il campo «{c}»")

    viste = {}
    for dove, riga in ((f"vocabolario.json riga {i + 1}", r) for i, r in enumerate(dati["vocabolario"].get("righe", []))):
        campi_mancanti(dove, riga, CAMPI_VOCABOLARIO)
        if riga.get("cosa") in viste:
            errori.append(f"{dove}: riga ripetuta (stessa «cosa» di {viste[riga.get('cosa')]})")
        viste.setdefault(riga.get("cosa"), dove)

    viste = {}
    for i, riga in enumerate(dati["ammesse"].get("voci", [])):
        dove = f"ammesse.json voce {i + 1}"
        campi_mancanti(dove, riga, CAMPI_AMMESSE)
        if riga.get("titolo") in viste:
            errori.append(f"{dove}: riga ripetuta (stesso titolo di {viste[riga.get('titolo')]})")
        viste.setdefault(riga.get("titolo"), dove)
    if not isinstance(dati["ammesse"].get("introduzione"), str):
        errori.append("ammesse.json: manca «introduzione»")

    ids = {}
    contenuti = {}
    for file, riga in dati["schermate"]:
        dove = f"{file} id {riga.get('id')}"
        if not isinstance(riga.get("id"), int) or isinstance(riga.get("id"), bool):
            errori.append(f"{file}: una riga non ha l'«id» numerico")
        elif riga["id"] in ids:
            errori.append(f"{dove}: id doppio (c'è già in {ids[riga['id']]})")
        else:
            ids[riga["id"]] = file
        campi_mancanti(dove, riga, CAMPI_SCHERMATA)
        if riga.get("stato") not in STATI and isinstance(riga.get("stato"), str) and riga["stato"].strip():
            errori.append(f"{dove}: stato sconosciuto «{riga['stato']}» (ammessi: {', '.join(STATI)})")
        chiave = tuple(riga.get(c) for c in CAMPI_SCHERMATA)
        if chiave in contenuti:
            errori.append(f"{dove}: riga ripetuta (uguale a quella con id {contenuti[chiave]})")
        contenuti.setdefault(chiave, riga.get("id"))
    return errori


def genera(dati):
    """Il testo del documento (a capo `\\n`, ultima riga con a capo)."""
    p = dati["parti"]
    prima, _, resto = p["testa"].partition("\n")
    testa = f"{prima}\n\n{NOTA}" + (f"\n{resto}" if resto else "")

    voc = [INTESTAZIONE_VOCABOLARIO] + [
        f"| {r['cosa']} | {r['forma']} | {r['mai']} |" for r in dati["vocabolario"]["righe"]
    ]
    voci = []
    for v in dati["ammesse"]["voci"]:
        prec = f" {v['precisazione']}" if v.get("precisazione") else ""
        voci.append(f"- **{v['titolo']}**{prec}: {v['testo']} Motivo: {v['motivo']}")
    righe = sorted((r for _, r in dati["schermate"]), key=lambda r: r["id"])
    tab = [INTESTAZIONE_SCHERMATE] + [
        f"| {r['id']} | {r['schermata']} | {r['web']} | {r['iphone']} | {r['forma']} | {r['chi']} |" for r in righe
    ]
    blocchi = [
        testa,
        "## Vocabolario comune\n" + "\n".join(voc),
        p["giornata"],
        "## Differenze ammesse\n" + dati["ammesse"]["introduzione"] + "\n" + "\n".join(voci),
        p["differenze-oggi"],
        "\n".join(tab),
        p["coda"],
    ]
    return "\n\n".join(blocchi) + "\n"


def _documento_attuale(radice):
    try:
        return (Path(radice) / DOCUMENTO).read_bytes().decode("utf-8").replace("\r\n", "\n")
    except OSError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    gruppo = ap.add_mutually_exclusive_group(required=True)
    gruppo.add_argument("--scrivi", action="store_true", help="rigenera docs/COERENZA-WEB-IPHONE.md dai dati")
    gruppo.add_argument("--controlla", action="store_true", help="controlla i dati e che il documento sia quello generato")
    ap.add_argument("--radice", default=str(RADICE), help="cartella del repository (per i test)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # console Windows con pagina di codici stretta

    try:
        dati = carica(a.radice)
    except ErroreDati as e:
        print(f"Dati illeggibili: {e}")
        return 2
    errori = valida(dati)
    if errori:
        print("Dati della coerenza da correggere:")
        for e in errori:
            print(f"  - {e}")
        return 1
    testo = genera(dati)

    if a.scrivi:
        with open(Path(a.radice) / DOCUMENTO, "w", encoding="utf-8", newline="\n") as f:
            f.write(testo)
        print(f"Scritto {DOCUMENTO.as_posix()}.")
        return 0
    if _documento_attuale(a.radice) != testo:
        print(f"{DOCUMENTO.as_posix()} non è quello generato dai dati: non si modifica a mano.")
        print("Cambia i dati in docs/coerenza/ e lancia: python script/coerenza.py --scrivi")
        return 1
    print("Coerenza a posto: dati validi e documento aggiornato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
