"""I limiti di riserva dell'iPhone uguali al file dei limiti del server (#889, dopo la #886).

L'editor delle regole dell'iPhone legge i limiti dei numeri da `/limiti-regole.json` (`fanta/web/limiti-regole.json`, lo stesso
file con cui il server controlla le regole e da cui la web prende i limiti di − e +). Con un server di prima, che non ha il file,
usa i limiti di riserva scritti in `LimitiRegole.riserva` (`ios/Sources/Presentation/Lega/LimitiRegole.swift`): devono essere gli
stessi del file, chiave per chiave. Se il file cambia, si cambia anche la riserva (e viceversa). I test Swift non leggono i file
della web (`ios/Tests/file-esterni.txt`): il confronto si fa qui."""
import json
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
FILE_LIMITI = RADICE / "fanta" / "web" / "limiti-regole.json"
SWIFT = RADICE / "ios" / "Sources" / "Presentation" / "Lega" / "LimitiRegole.swift"
_VOCE = re.compile(r'"([\w.]+)":\s*Limite\(min:\s*(-?[\d_.]+),\s*max:\s*(-?[\d_.]+)\)')


def riserva_iphone(swift: str) -> dict[str, dict[str, float]]:
    """{chiave: {min, max}} dalle voci `"chiave": Limite(min: …, max: …)` di `static let riserva` in LimitiRegole.swift."""
    inizio = swift.index("static let riserva")
    blocco = swift[inizio:swift.index("])", inizio)]
    return {k: {"min": float(a.replace("_", "")), "max": float(b.replace("_", ""))} for k, a, b in _VOCE.findall(blocco)}


def differenze(file: dict, riserva: dict) -> list[str]:
    """Le chiavi che mancano da una parte e i limiti diversi, in ordine di chiave."""
    errori = []
    for chiave in sorted(set(file) | set(riserva)):
        if chiave not in riserva:
            errori.append(f"{chiave}: manca nella riserva dell'iPhone")
        elif chiave not in file:
            errori.append(f"{chiave}: c'è nella riserva dell'iPhone ma non nel file del server")
        elif {k: float(v) for k, v in file[chiave].items()} != riserva[chiave]:
            errori.append(f"{chiave}: file {file[chiave]}, iPhone {riserva[chiave]}")
    return errori


def test_la_riserva_dell_iphone_e_il_file_del_server():
    file = json.loads(FILE_LIMITI.read_text(encoding="utf-8"))
    riserva = riserva_iphone(SWIFT.read_text(encoding="utf-8"))
    assert len(riserva) == len(file), "la riserva dell'iPhone non si legge più come prima: aggiorna questo test"
    assert differenze(file, riserva) == []


def test_il_controllo_vede_un_limite_cambiato_da_una_parte_sola():
    file = json.loads(FILE_LIMITI.read_text(encoding="utf-8"))
    swift = SWIFT.read_text(encoding="utf-8")
    cambiato = swift.replace('"bonus.assist": Limite(min: 0, max: 20)', '"bonus.assist": Limite(min: 0, max: 15)')
    assert cambiato != swift
    assert differenze(file, riserva_iphone(cambiato)) == ["bonus.assist: file {'min': 0, 'max': 20}, iPhone {'min': 0.0, 'max': 15.0}"]
    senza = {k: v for k, v in file.items() if k != "rosa.P"}
    assert differenze(senza, riserva_iphone(swift)) == ["rosa.P: c'è nella riserva dell'iPhone ma non nel file del server"]
