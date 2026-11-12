"""«gioca N%» con le stesse soglie sulla web e sull'iPhone (#616, #673): si mostra sotto l'80%, arancio fra 50 e 79, rosso sotto
50, e si decide sul numero arrotondato al centesimo. Sulla web `SOGLIA_GIOCA`, `SOGLIA_BASSA` e `giocaLetto` di `fanta/web/app.js`;
sull'iPhone `SogliaGioca` (`ios/Sources/Domain/SogliaGioca.swift`), usata da scheda, pedina e righe. Se una delle due cambia da
sola, questo test fallisce: si cambiano insieme."""
import re
from pathlib import Path

import codice_web

RADICE = Path(__file__).resolve().parent.parent
SWIFT = RADICE / "ios" / "Sources" / "Domain" / "SogliaGioca.swift"


def soglie_web(js: str) -> dict:
    """{"alta", "bassa"} da `SOGLIA_GIOCA` e `SOGLIA_BASSA` di app.js (None se una manca)."""
    leggi = lambda nome: (m := re.search(rf"\b{nome}\s*=\s*([0-9.]+)", js)) and float(m.group(1))
    return {"alta": leggi("SOGLIA_GIOCA"), "bassa": leggi("SOGLIA_BASSA")}


def soglie_iphone(swift: str) -> dict:
    """{"alta", "bassa"} da `static let alta` e `static let bassa` di SogliaGioca.swift (None se una manca)."""
    leggi = lambda nome: (m := re.search(rf"static let {nome}\s*=\s*([0-9.]+)", swift)) and float(m.group(1))
    return {"alta": leggi("alta"), "bassa": leggi("bassa")}


def differenze(js: str, swift: str) -> list[str]:
    """Cosa non torna fra web e iPhone: soglie diverse o che mancano, arrotondamento al centesimo che manca da una parte."""
    web, iphone = soglie_web(js), soglie_iphone(swift)
    errori = [f"soglia {k}: web {web[k]}, iPhone {iphone[k]}" for k in ("alta", "bassa") if web[k] is None or web[k] != iphone[k]]
    if not re.search(r"giocaLetto\s*=.*Math\.round\(.*\* 100\)\s*/\s*100", js):
        errori.append("web: `giocaLetto` non arrotonda più al centesimo")
    if not re.search(r"\(p \* 100\)\.rounded\(\) / 100", swift):
        errori.append("iPhone: `SogliaGioca.letta` non arrotonda più al centesimo")
    return errori


def test_soglie_uguali_sulla_web_e_sull_iphone():
    js, swift = codice_web.app(), SWIFT.read_text(encoding="utf-8")
    assert soglie_web(js) == {"alta": 0.8, "bassa": 0.5}, "le soglie della web non si leggono più: aggiorna questo test"
    assert differenze(js, swift) == []


def test_il_controllo_vede_una_soglia_cambiata_da_una_parte_sola():
    js, swift = codice_web.app(), SWIFT.read_text(encoding="utf-8")
    assert differenze(js, swift.replace("static let alta = 0.8", "static let alta = 0.7")) == ["soglia alta: web 0.8, iPhone 0.7"]
    assert differenze(js.replace("SOGLIA_BASSA = 0.5", "SOGLIA_BASSA = 0.4"), swift) == ["soglia bassa: web 0.4, iPhone 0.5"]
    senza = swift.replace("(p * 100).rounded() / 100", "p")
    assert differenze(js, senza) == ["iPhone: `SogliaGioca.letta` non arrotonda più al centesimo"]
