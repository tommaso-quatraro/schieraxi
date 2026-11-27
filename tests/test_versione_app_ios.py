"""La versione leggibile dell'app per iPhone («1.0.N», con N il numero della build) sta scritta in tre posti che devono dire la stessa
cosa: la compilazione (`MARKETING_VERSION` di ipa.yml, quella che Impostazioni › Informazioni mostra come «Versione dell'app»), il
sorgente di SideStore (`ios/scripts/genera_sorgente.py`) e l'avviso «C'è una versione nuova» dell'app (`NuovaVersione.versione`).
Se uno cambia e gli altri no, l'avviso o SideStore dicono una versione che l'utente non trova sul telefono."""
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent

POSTI = {
    ".github/workflows/ipa.yml": r'MARKETING_VERSION="([0-9.]+)\$BUILD_N"',
    "ios/scripts/genera_sorgente.py": r'"version":\s*f"([0-9.]+)\{build\}"',
    "ios/Sources/Support/NuovaVersione.swift": r'"([0-9.]+)\\\(build\)"',
}


def _prima_del_numero(percorso: str, schema: str) -> str:
    """Quello che il file scrive prima del numero della build: deve esserci una volta sola."""
    trovati = re.findall(schema, (RADICE / percorso).read_text(encoding="utf-8"))
    assert len(trovati) == 1, f"{percorso}: attesa una sola versione «…N», trovate {trovati}"
    return trovati[0]


def test_la_versione_dell_app_e_la_stessa_in_compilazione_sorgente_e_avviso():
    trovate = {percorso: _prima_del_numero(percorso, schema) for percorso, schema in POSTI.items()}
    assert len(set(trovate.values())) == 1, f"versioni diverse: {trovate}"
    assert next(iter(trovate.values())).endswith("."), trovate
