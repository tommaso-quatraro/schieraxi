import XCTest
@testable import Schieraxi

/// La striscia «dati salvati» dice il motivo vero, e tornando nell'app dopo un po' si ricarica.
@MainActor
final class DatiVecchiTests: XCTestCase {
    func testSoloReteETempoScadutoSonoNonRaggiungibile() {
        XCTAssertTrue(DatiVecchi.eDiRete(ErroreApi.rete("spento")))
        XCTAssertTrue(DatiVecchi.eDiRete(ErroreApi.timeout))
        XCTAssertTrue(DatiVecchi.eDiRete(ErroreApi.senzaRete), "il telefono senza rete (#830)")
        XCTAssertTrue(DatiVecchi.eDiRete(URLError(.notConnectedToInternet)))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.troppiTentativi("Hai finito le ricerche di oggi.", riprovaTra: 60)))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.server("Guasto")))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.risposta(500)))
        XCTAssertFalse(DatiVecchi.eDiRete(ErroreApi.dati("illeggibile")))
    }

    /// Un istante preciso dell'ora italiana: i simulatori di GitHub non sono sul fuso italiano.
    private func oraItaliana(giorno: Int, ora: Int, minuto: Int) throws -> Date {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = try XCTUnwrap(TimeZone(identifier: "Europe/Rome"))
        return try XCTUnwrap(cal.date(from: DateComponents(year: 2026, month: 11, day: giorno, hour: ora, minute: minuto)))
    }

    func testFraseConESenzaMotivo() throws {
        let salvata = try oraItaliana(giorno: 2, ora: 10, minuto: 0)
        let rete = DatiVecchi.frase(salvatiIl: salvata, motivo: nil)
        XCTAssertEqual(rete, "Non riesco a collegarmi: questi sono i dati salvati il 2 nov alle 10:00.",
                       "senza motivo la frase della web (`comune.cache_offline`), con giorno e ora scritti come nella nota con il motivo")
        let limite = DatiVecchi.frase(salvatiIl: salvata, motivo: "Hai finito le ricerche di oggi")
        XCTAssertFalse(limite.contains("collegarmi"), "il server ha risposto: non si dice che non è raggiungibile")
        let conPunto = DatiVecchi.frase(salvatiIl: salvata, motivo: "Errore del server.")
        XCTAssertFalse(conPunto.contains(".."))
        XCTAssertEqual(DatiVecchi.frase(salvatiIl: salvata, motivo: "  "), DatiVecchi.frase(salvatiIl: salvata, motivo: nil))
    }

    /// Con il motivo (il server ha risposto con un errore, per esempio la pagina 502 del proxy) la frase della web nello stesso caso
    /// (`comune.cache_errore` in `app.js`): il motivo in testa e la nota fra parentesi, con il giorno e l'ora della copia. Lo stesso
    /// istante e la stessa frase del test della web (`tests/browser/test_copia_salvata.py`). Prima «Non ho potuto aggiornare: Il
    /// server non risponde: riprova fra poco. …», con due «:» di fila (#830); poi la nota senza la data della copia (#845).
    func testIlMotivoVaInTestaComeSullaWeb() throws {
        let salvata = try oraItaliana(giorno: 17, ora: 10, minuto: 5)
        let proxy = DatiVecchi.frase(salvatiIl: salvata, motivo: Catalogo.Comune.serverNonRisponde)
        XCTAssertEqual(proxy, "Il server non risponde: riprova fra poco (dati salvati il 17 nov alle 10:05, potrebbero non essere aggiornati).")
        let primaDellaNota = proxy.components(separatedBy: " (").first ?? proxy
        XCTAssertEqual(primaDellaNota.filter { $0 == ":" }.count, 1, "prima della nota un solo «:», quello del motivo")
        XCTAssertEqual(DatiVecchi.frase(salvatiIl: salvata, motivo: "  Hai finito le ricerche di oggi "),
                       "Hai finito le ricerche di oggi (dati salvati il 17 nov alle 10:05, potrebbero non essere aggiornati).")
    }

    /// Giorno e ora della copia sono quelli italiani, come sulla web: le 00:30 del 17 sono ancora il 16 per un telefono in UTC.
    /// Lo stesso orologio con e senza motivo: prima, con il telefono a Londra, la stessa copia era «alle 10:05» con il 502 e
    /// «09:05» senza rete (revisione della #852).
    func testGiornoEOraDellaCopiaSonoQuelliItaliani() throws {
        let notte = try oraItaliana(giorno: 17, ora: 0, minuto: 30)
        XCTAssertEqual(DatiVecchi.frase(salvatiIl: notte, motivo: "Guasto"),
                       "Guasto (dati salvati il 17 nov alle 00:30, potrebbero non essere aggiornati).")
        XCTAssertEqual(DatiVecchi.frase(salvatiIl: notte, motivo: nil),
                       "Non riesco a collegarmi: questi sono i dati salvati il 17 nov alle 00:30.")
    }

    /// «l'8 nov», «l'11 nov», mai «il 8» o «il 11» (si legge «l'otto», «l'undici»), come la web (`elidiGiorno` in `testi.js`).
    /// Le altre date restano: «il 18 nov», «il 1 nov».
    func testApostrofoDavantiAll8EAll11() throws {
        let otto = try oraItaliana(giorno: 8, ora: 10, minuto: 5)
        XCTAssertEqual(DatiVecchi.frase(salvatiIl: otto, motivo: Catalogo.Comune.serverNonRisponde),
                       "Il server non risponde: riprova fra poco (dati salvati l'8 nov alle 10:05, potrebbero non essere aggiornati).")
        let undici = try oraItaliana(giorno: 11, ora: 10, minuto: 5)
        XCTAssertEqual(DatiVecchi.frase(salvatiIl: undici, motivo: nil),
                       "Non riesco a collegarmi: questi sono i dati salvati l'11 nov alle 10:05.")
        let diciotto = try oraItaliana(giorno: 18, ora: 10, minuto: 5)
        XCTAssertTrue(DatiVecchi.frase(salvatiIl: diciotto, motivo: "Guasto").contains("(dati salvati il 18 nov alle 10:05,"))
        let primo = try oraItaliana(giorno: 1, ora: 10, minuto: 5)
        XCTAssertTrue(DatiVecchi.frase(salvatiIl: primo, motivo: "Guasto").contains("(dati salvati il 1 nov alle 10:05,"))
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
