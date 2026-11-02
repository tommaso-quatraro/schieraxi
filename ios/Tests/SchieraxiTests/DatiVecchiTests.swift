import XCTest
@testable import Schieraxi

/// La striscia «dati salvati» dice il motivo vero, e tornando nell'app dopo un po' si ricarica.
@MainActor
final class DatiVecchiTests: XCTestCase {
    func testSoloReteETempoScadutoSonoNonRaggiungibile() {
        XCTAssertTrue(DatiVecchi.eDiRete(ErroreApi.rete("spento")))
        XCTAssertTrue(DatiVecchi.eDiRete(ErroreApi.timeout))
        XCTAssertTrue(DatiVecchi.eDiRete(URLError(.notConnectedToInternet)))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.troppiTentativi("Hai finito le ricerche di oggi.", riprovaTra: 60)))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.server("Guasto")))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.risposta(500)))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.dati("illeggibile")))
    }

    func testFraseConESenzaMotivo() {
        let rete = DatiVecchi.frase(salvatiIl: "2 nov 2026, 10:00", motivo: nil)
        XCTAssertTrue(rete.hasPrefix("Non riesco a raggiungere SchieraXI."))
        XCTAssertTrue(rete.contains("2 nov 2026, 10:00"))
        let limite = DatiVecchi.frase(salvatiIl: "2 nov 2026, 10:00", motivo: "Hai finito le ricerche di oggi")
        XCTAssertFalse(limite.contains("raggiungere"), "il server ha risposto: non si dice che non è raggiungibile")
        XCTAssertTrue(limite.contains("Hai finito le ricerche di oggi. Quello che vedi"), "punto aggiunto una sola volta")
        let conPunto = DatiVecchi.frase(salvatiIl: "x", motivo: "Errore del server.")
        XCTAssertFalse(conPunto.contains(".."))
        XCTAssertEqual(DatiVecchi.frase(salvatiIl: "x", motivo: "  "), DatiVecchi.frase(salvatiIl: "x", motivo: nil))
    }

    func testIlCaricatoreRicordaIlMotivoSoloSeIlServerHaRisposto() async throws {
        let chiamate = Contatore()
        let server = ServerDiProva { _, _, _ in
            switch chiamate.passo() {
            case 0: return try Fixture.dati("oggi")
            case 1: throw ErroreApi.troppiTentativi("Troppe richieste.", riprovaTra: nil)
            case 2: throw ErroreApi.rete("spento")
            default: return try Fixture.dati("oggi")
            }
        }
        let c = Caricatore<Oggi>("/api/oggi", cache: false, ascolta: false, server: server)
        await c.ricarica()
        XCTAssertNil(c.motivoDatiSalvati)
        await c.ricarica()
        XCTAssertNotNil(c.datiSalvati)
        XCTAssertEqual(c.motivoDatiSalvati, ErroreApi.troppiTentativi("Troppe richieste.", riprovaTra: nil).errorDescription)
        await c.ricarica()
        XCTAssertNotNil(c.datiSalvati)
        XCTAssertNil(c.motivoDatiSalvati, "rete assente: la frase di sempre")
        await c.ricarica()
        XCTAssertNil(c.datiSalvati)
        XCTAssertNil(c.motivoDatiSalvati)
    }

    func testRitornoNellApp() {
        let uscita = Date(timeIntervalSince1970: 1_793_570_000)   // un giorno qualsiasi
        XCTAssertFalse(DatiVecchi.serveAggiornareAlRitorno(uscitaIl: nil, adesso: uscita), "primo avvio: ci pensa già ogni schermata")
        XCTAssertFalse(DatiVecchi.serveAggiornareAlRitorno(uscitaIl: uscita, adesso: uscita.addingTimeInterval(60)))
        XCTAssertTrue(DatiVecchi.serveAggiornareAlRitorno(uscitaIl: uscita, adesso: uscita.addingTimeInterval(DatiVecchi.sogliaRitorno)))
        XCTAssertTrue(DatiVecchi.serveAggiornareAlRitorno(uscitaIl: uscita, adesso: uscita.addingTimeInterval(3 * 3600)))
    }

    func testDopoLaMezzanotteSiRicaricaAncheSubito() throws {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = try XCTUnwrap(TimeZone(identifier: "Europe/Rome"))
        let prima = try XCTUnwrap(cal.date(from: DateComponents(year: 2026, month: 11, day: 2, hour: 23, minute: 58)))
        let dopo = prima.addingTimeInterval(4 * 60)   // 00:02 del giorno dopo, meno della soglia
        XCTAssertTrue(DatiVecchi.serveAggiornareAlRitorno(uscitaIl: prima, adesso: dopo))
    }
}
