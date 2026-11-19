import Foundation
import Testing
@testable import Schieraxi

/// «Formazione consigliata» e «Da controllare» per chi è entrato in SchieraXI a giornata già iniziata senza una formazione per lei
/// (#752, seguito di #687). `GET /api/widget` manda ancora `formazione` e `avvisi` della giornata già iniziata: prima «Formazione
/// consigliata» mostrava la consigliata di una giornata che non si può più schierare e «Da controllare» «Chiusa · La formazione si
/// è chiusa … I punti fatti sono in Oggi.», punti che per lui non ci sono. Ora i tre widget mostrano la stessa cosa di «Prossima
/// giornata»: «Questa giornata è già iniziata», «Prepara la prossima» e il conto alla rovescia alla scadenza della prossima. Il caso
/// lo sceglie `CasoWidget`, nello stesso ordine per i tre widget: prima il campionato finito (#727, #745), poi questo, poi il widget
/// di sempre. Dati inventati (`widget-senza-formazione`, `widget-in-corso`).
@Suite("Formazione consigliata e Da controllare per chi è entrato a giornata iniziata: la prossima da preparare (#752)")
struct WidgetAltriSenzaFormazioneTests {
    /// La frase del server a campionato finito (`campionato.finito`), come in `widget-campionato-finito`.
    private static let fraseCampionatoFinito = "Il campionato è finito: previsioni e consigli ripartono con il calendario della prossima stagione."
    /// La prossima giornata da preparare, nella forma di `/api/widget` e `/api/oggi`.
    private static let prossima = #""prossima": {"giornata": 11, "giornata_lega": 8, "scadenza": "2026-11-14 14:50", "prepara_da": "2026-11-11 14:50", "con_probabili": false}"#

    private func risposta(_ fixture: String) throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(try Fixture.dati(fixture)), "la risposta \(fixture) non si legge")
    }

    private func leggi(_ corpo: String) throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(Data(corpo.utf8)), "la risposta non si legge")
    }

    @Test("Con `senza_formazione` i widget mostrano la prossima da preparare, non la consigliata della giornata già iniziata")
    func senzaFormazione() throws {
        let w = try risposta("widget-senza-formazione")
        let caso = CasoWidget.di(riassunto: w.comeRiassuntoOggi(), widget: w)
        #expect(caso.nelCasoSenzaFormazione, "«Formazione consigliata» mostrava la consigliata della giornata già iniziata: \(caso)")
        #expect(caso.prossima?.giornata == 11)
        #expect(caso.prossima?.scadenza == Quando.data("2026-11-14 14:50"))
        // la sola risposta completa, senza riassunto: la sua `formazione` è ancora quella della giornata iniziata
        #expect(CasoWidget.di(riassunto: nil, widget: w).nelCasoSenzaFormazione)
        // il solo riassunto (una copia salvata, senza la risposta completa)
        #expect(CasoWidget.di(riassunto: w.comeRiassuntoOggi(), widget: nil).nelCasoSenzaFormazione)
    }

    @Test("Dal riassunto che l'app passa al widget (`/api/oggi`), senza la risposta completa: lo stesso caso")
    func dallApp() throws {
        let corpo = """
        {"giornata": 10, "giornata_lega": 7, "scadenza": "2026-11-08 14:30", "iniziata": true, "fase": "in_corso",
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 71.5}, "in_corso": null, "senza_formazione": true, \(Self.prossima)}
        """
        let r = RiassuntoOggi(oggi: try Decodifica.decodifica(Data(corpo.utf8)))
        let caso = CasoWidget.di(riassunto: r, widget: nil)
        #expect(caso.nelCasoSenzaFormazione, "con la copia dell'app «Formazione consigliata» mostrava 3-4-3 e 71,5 della giornata iniziata")
        #expect(caso.prossima?.giornata == 11)
    }

    @Test("Chi c'era già prima della scadenza (`in_corso`), una risposta senza dati e nessuna risposta: il widget di sempre")
    func comePrima() throws {
        let w = try risposta("widget-in-corso")
        #expect(CasoWidget.di(riassunto: w.comeRiassuntoOggi(), widget: w) == .normale)
        let primaDellaScadenza = try leggi(#"{"giornata": 10, "scadenza": "2026-11-08 14:30", "fase": "prima"}"#)
        #expect(CasoWidget.di(riassunto: primaDellaScadenza.comeRiassuntoOggi(), widget: primaDellaScadenza) == .normale)
        #expect(CasoWidget.di(riassunto: nil, widget: nil) == .normale, "senza dati ciascun widget dice «Nessun dato» o «Tocca per collegare»")
    }

    @Test("A campionato finito vince la frase del server, anche con `senza_formazione` (#727, #745)")
    func campionatoFinitoPrima() throws {
        let finito = #""campionato_finito": {"testo": "\#(Self.fraseCampionatoFinito)", "frase": {"chiave": "campionato.finito", "param": {}}}"#
        let w = try leggi(#"{"giornata": 10, "scadenza": "2026-11-08 14:30", "fase": "in_corso", "senza_formazione": true, \#(Self.prossima), \#(finito)}"#)
        #expect(CasoWidget.di(riassunto: w.comeRiassuntoOggi(), widget: w) == .campionatoFinito(Self.fraseCampionatoFinito))
        // la frase nel riassunto dell'app vince sulla risposta completa senza formazione
        let senza = try risposta("widget-senza-formazione")
        var r = try #require(senza.comeRiassuntoOggi())
        r.campionatoFinito = Self.fraseCampionatoFinito
        #expect(CasoWidget.di(riassunto: r, widget: senza) == .campionatoFinito(Self.fraseCampionatoFinito))
        let soloFinito = try risposta("widget-campionato-finito")
        #expect(CasoWidget.di(riassunto: soloFinito.comeRiassuntoOggi(), widget: soloFinito) == .campionatoFinito(Self.fraseCampionatoFinito))
    }

    @Test("`senza_formazione` vale solo a giornata in corso e con un sì vero, come «Prossima giornata»")
    func soloAGiornataInCorso() throws {
        let finita = try leggi(#"{"giornata": 11, "scadenza": "2026-11-14 14:50", "fase": "finita", "senza_formazione": true, \#(Self.prossima)}"#)
        #expect(CasoWidget.di(riassunto: finita.comeRiassuntoOggi(), widget: finita) == .normale)
        let senzaFase = try leggi(#"{"giornata": 10, "scadenza": "2026-11-08 14:30", "senza_formazione": true, \#(Self.prossima)}"#)
        #expect(CasoWidget.di(riassunto: senzaFase.comeRiassuntoOggi(), widget: senzaFase) == .normale)
        let strano = try leggi(#"{"giornata": 10, "scadenza": "2026-11-08 14:30", "fase": "in_corso", "senza_formazione": "sì", \#(Self.prossima)}"#)
        #expect(CasoWidget.di(riassunto: strano.comeRiassuntoOggi(), widget: strano) == .normale, "un valore strano vale «no»")
        // ultima giornata della stagione: niente prossima, ma l'invito resta (senza conto alla rovescia)
        let ultima = try leggi(#"{"giornata": 38, "scadenza": "2027-05-23 14:30", "fase": "in_corso", "senza_formazione": true}"#)
        let caso = CasoWidget.di(riassunto: ultima.comeRiassuntoOggi(), widget: ultima)
        #expect(caso.nelCasoSenzaFormazione)
        #expect(caso.prossima == nil)
    }

    @Test("Il tocco su «Da controllare» apre la Formazione (già quella della prossima) per chi è entrato a giornata iniziata, Oggi negli altri casi")
    func toccoDaControllare() throws {
        let w = try risposta("widget-senza-formazione")
        #expect(CasoWidget.di(riassunto: w.comeRiassuntoOggi(), widget: w).indirizzoDaControllare == "schieraxi://formazione",
                "apriva Oggi, dove non ci sono punti né dubbi da guardare: l'invito è preparare la prossima")
        #expect(CasoWidget.normale.indirizzoDaControllare == "schieraxi://oggi")
        #expect(CasoWidget.campionatoFinito(Self.fraseCampionatoFinito).indirizzoDaControllare == "schieraxi://oggi")
    }
}

private extension CasoWidget {
    /// true nel caso «entrato a giornata iniziata senza formazione».
    var nelCasoSenzaFormazione: Bool {
        if case .senzaFormazione = self { return true }
        return false
    }

    /// La giornata da preparare in quel caso; nil negli altri o se il server non la manda.
    var prossima: ProssimaDaPreparare? {
        if case .senzaFormazione(let r) = self { return r.prossimaDaPreparare }
        return nil
    }
}
