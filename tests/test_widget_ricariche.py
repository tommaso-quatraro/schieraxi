"""La finestra delle partite in cui il widget dell'iPhone si ricarica ogni 15 minuti (`RicaricaWidget.dopoIlCalcio`, in
ios/Sources/Support/WidgetRiassunto.swift) deve coprire l'ultimo giro dei risultati del server (`pianificatore.GIRI_RISULTATI`:
2 ore e 30 dopo il calcio d'inizio e, se mancano ancora i voti, 4 ore), più una ricarica. Altrimenti i punti di quel giro arrivano
quando il widget è già tornato a ricaricarsi ogni mezz'ora. L'app non legge il pianificatore: il valore sta nel suo codice, e
questo test lo confronta con quello del server."""
import math
import re
from datetime import timedelta
from pathlib import Path

from fanta import pianificatore

SWIFT = Path(__file__).resolve().parent.parent / "ios" / "Sources" / "Support" / "WidgetRiassunto.swift"
UNA_RICARICA = timedelta(minutes=15)          # `RicaricaWidget.minutiPartite`


def _secondi(espressione: str) -> int:
    """Una somma di prodotti di interi, la forma della costante Swift: «4 * 3600 + 15 * 60»."""
    return sum(math.prod(int(f) for f in termine.split("*")) for termine in espressione.split("+"))


def test_la_finestra_del_widget_copre_l_ultimo_giro_dei_risultati():
    m = re.search(r"static let dopoIlCalcio: TimeInterval = ([\d *+]+)\r?$", SWIFT.read_text(encoding="utf-8"), re.M)
    assert m, "RicaricaWidget.dopoIlCalcio non trovato in WidgetRiassunto.swift"
    ultimo_giro = max(ritardo for _, ritardo in pianificatore.GIRI_RISULTATI)
    assert timedelta(seconds=_secondi(m.group(1))) >= ultimo_giro + UNA_RICARICA


def test_la_somma_di_prodotti():
    assert _secondi("4 * 3600 + 15 * 60") == 15300
    assert _secondi("3 * 3600") == 10800
