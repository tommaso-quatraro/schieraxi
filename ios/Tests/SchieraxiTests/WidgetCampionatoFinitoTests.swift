import Foundation
import Testing
@testable import Schieraxi

/// La frase del server a campionato finito (`campionato.finito`, `fanta/testi/frase.json`): la stessa della fixture.
private let fraseCampionatoFinito = "Il campionato è finito: previsioni e consigli ripartono con il calendario della prossima stagione."

/// Il widget a campionato finito (#727, seguito di #656): `GET /api/widget` risponde 200 senza giornata e con `campionato_finito`
/// = {testo, frase}. Prima il riassunto non c'era (`comeRiassuntoOggi` voleva una giornata) e i widget dicevano «Nessun dato · Apri
/// SchieraXI per aggiornare i dati» con il simbolo del Wi-Fi, da fine maggio per tutta l'estate. Ora il riassunto porta la frase
/// del server, che i widget mostrano al posto della giornata. Risposta inventata nella fixture `widget-campionato-finito`.
@Suite("Widget a campionato finito: la frase del server al posto di «Nessun dato»")
struct WidgetCampionatoFinitoTests {
    @Test("`/api/widget` a campionato finito dà un riassunto con la frase del server, senza giornata né «Da controllare»")
    func riassunto() throws {
        let w = try #require(RiassuntoWidget.leggi(try Fixture.dati("widget-campionato-finito")), "la risposta non si legge")
        #expect(w.campionatoFinito == fraseCampionatoFinito)
        let r = try #require(w.comeRiassuntoOggi(), "senza riassunto il widget dice «Nessun dato» con il simbolo del Wi-Fi")
        #expect(r.campionatoFinito == fraseCampionatoFinito)
        #expect(r.giornata == nil)
        #expect(r.daControllare == 0)
    }

    @Test("Senza giornata e senza la frase (rose mancanti, risposta strana) nessun riassunto, come prima")
    func senzaFrase() throws {
        #expect(RiassuntoWidget.leggi(Data(#"{"giornata": null}"#.utf8))?.comeRiassuntoOggi() == nil)
        let strano = try #require(RiassuntoWidget.leggi(Data(#"{"giornata": null, "campionato_finito": {"testo": ""}}"#.utf8)))
        #expect(strano.campionatoFinito == nil)
        #expect(strano.comeRiassuntoOggi() == nil)
        let diverso = try #require(RiassuntoWidget.leggi(Data(#"{"giornata": 9, "campionato_finito": "sì"}"#.utf8)),
                                   "un campo con una forma strana non fa crollare la lettura")
        #expect(diverso.campionatoFinito == nil)
        #expect(diverso.comeRiassuntoOggi()?.giornata == 9)
    }

    @Test("Il riassunto che l'app passa al widget porta la frase, anche salvato e riletto; uno salvato da una versione di prima si legge")
    func riassuntoDellApp() throws {
        let r = RiassuntoOggi(oggi: try Fixture.decodifica("oggi-campionato-finito"))
        #expect(r.campionatoFinito == fraseCampionatoFinito)
        let riletto = try JSONDecoder().decode(RiassuntoOggi.self, from: try JSONEncoder().encode(r))
        #expect(riletto == r)
        let diPrima = try JSONDecoder().decode(RiassuntoOggi.self, from: Data(#"{"daControllare": 0, "scaricatoIl": 0}"#.utf8))
        #expect(diPrima.campionatoFinito == nil)
        #expect(RiassuntoOggi(oggi: try Fixture.decodifica("oggi")).campionatoFinito == nil)
    }

    @Test("Dove la frase intera non entra resta la sua prima parte, fino ai due punti: mai una frase tagliata a metà")
    func forme() {
        #expect(ParoleWidget.formeCampionatoFinito(fraseCampionatoFinito) == [fraseCampionatoFinito, "Il campionato è finito"])
        #expect(ParoleWidget.formeCampionatoFinito("The season is over: forecasts and advice start again with next season's calendar.")
                == ["The season is over: forecasts and advice start again with next season's calendar.", "The season is over"])
        #expect(ParoleWidget.formeCampionatoFinito(" Stagione chiusa. ") == ["Stagione chiusa."])
        #expect(ParoleWidget.formeCampionatoFinito(": niente prima") == [": niente prima"])
    }
}
