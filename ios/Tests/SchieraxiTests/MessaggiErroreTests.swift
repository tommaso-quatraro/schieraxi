import XCTest
@testable import Schieraxi

/// Messaggi d'errore per chi usa l'app: semplici, senza codici e senza «server acceso»; il «Riprova» resta dove serve.
final class MessaggiErroreTests: XCTestCase {
    func testNienteParoleTecniche() {
        let testi = [ErroreApi.rete("x"), .senzaRete, .timeout, .risposta(500), .risposta(502), .risposta(401), .risposta(403), .server("Nessuna rosa importata")]
            .compactMap(\.errorDescription)
        for t in testi {
            XCTAssertFalse(t.contains("codice"), t)
            XCTAssertFalse(t.contains("acceso"), t)
            XCTAssertFalse(t.hasPrefix("Il server dice"), t)
        }
        XCTAssertEqual(ErroreApi.server("Nessuna rosa importata").errorDescription, "Nessuna rosa importata")
    }

    func testUnSoloMessaggioPerLaReteAssente() {
        XCTAssertEqual(ErroreApi.rete("spenta").errorDescription, ErroreApi.testoNonRaggiungibile)
        XCTAssertEqual(DatiPersonali.testoErrore(ErroreApi.rete("x")), ErroreApi.testoNonRaggiungibile)
        XCTAssertEqual(SchermataAccesso.testoErrore(ErroreApi.rete("x")), ErroreApi.testoNonRaggiungibile)
    }

    /// #830: il server che non risponde con la rete accesa (spento, che riparte, tempo scaduto, la pagina 502-504 del proxy) ha la
    /// frase della web, `comune.server_non_risponde`, ovunque; il telefono senza rete ha l'altra (`comune.rete_no`, prova in
    /// `ServerHTTPTests`). Un 500 resta un guasto del server.
    func testIlServerCheNonRispondeHaLaFraseDellaWeb() {
        let errori = [ErroreApi.rete("spento"), .timeout, .risposta(502), .risposta(503), .risposta(504)]
        for e in errori {
            XCTAssertEqual(e.errorDescription, Catalogo.Comune.serverNonRisponde, "\(e)")
            XCTAssertEqual(SchermataAccesso.testoErrore(e), Catalogo.Comune.serverNonRisponde, "\(e)")
        }
        XCTAssertEqual(ErroreApi.testoNonRaggiungibile, Catalogo.Comune.serverNonRisponde)
        XCTAssertEqual(DatiPersonali.testoErrore(ErroreApi.timeout), Catalogo.Comune.serverNonRisponde)
        XCTAssertEqual(ErroreApi.risposta(500).errorDescription, "SchieraXI ha un problema in questo momento. Riprova tra poco.")
        XCTAssertEqual(ErroreApi.senzaRete.errorDescription, Catalogo.Comune.reteNo)
        XCTAssertEqual(ErroreApi.testoSenzaRete, Catalogo.Comune.reteNo)
        XCTAssertEqual(SchermataAccesso.testoErrore(ErroreApi.senzaRete), Catalogo.Comune.reteNo)
        XCTAssertEqual(DatiPersonali.testoErrore(ErroreApi.senzaRete), Catalogo.Comune.reteNo)
    }

    /// #771: il 412 (dati cambiati da un altro dispositivo) dice la frase della web, `err.conflitto` del catalogo comune, non una
    /// frase scritta a mano nell'app. `localizedDescription` è quello che mostrano le schermate (per esempio la Formazione).
    func testIl412HaLaFraseDelCatalogoComeLaWeb() {
        XCTAssertEqual(ErroreApi.conflitto.errorDescription, Catalogo.Err.conflitto)
        XCTAssertEqual(ErroreApi.conflitto.localizedDescription, Catalogo.Err.conflitto)
    }

    func testIlMessaggioDelLimiteRestaUnaFraseIntera() {
        // il testo vero del server per l'accesso
        XCTAssertEqual(ErroreApi.troppiTentativi("Troppi tentativi sbagliati: aspetta prima di riprovare.", riprovaTra: 45).errorDescription,
                       "Troppi tentativi sbagliati. Riprova tra 45 secondi.")
        XCTAssertEqual(ErroreApi.troppiTentativi("Per oggi basta. Riprova domani.", riprovaTra: 600).errorDescription,
                       "Per oggi basta. Riprova tra 10 minuti.")
        XCTAssertEqual(ErroreApi.troppiTentativi("Prima di riprovare aspetta un attimo.", riprovaTra: 30).errorDescription,
                       "Prima di riprovare aspetta un attimo. Riprova tra 30 secondi.")
    }

    func testRiprovaTraPocoNonEUnLimite() {
        XCTAssertFalse(ErroreVista.eLimite(ErroreApi.timeout.errorDescription ?? ""))
        XCTAssertFalse(ErroreVista.eLimite(ErroreApi.risposta(500).errorDescription ?? ""))
        XCTAssertFalse(ErroreVista.eLimite(ErroreApi.rete("x").errorDescription ?? ""))
        XCTAssertFalse(ErroreVista.eLimite(ErroreApi.senzaRete.errorDescription ?? ""))
        XCTAssertTrue(ErroreVista.eLimite(ErroreApi.troppiTentativi("Troppe ricerche oggi.", riprovaTra: 45).errorDescription ?? ""))
        XCTAssertTrue(ErroreVista.eLimite("Hai finito le ricerche di oggi. Riprova domani."))
    }
}
