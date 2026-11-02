import XCTest
@testable import Schieraxi

/// Privacy e Termini dal server, codice sorgente, prova con dati di esempio e manifest della privacy.
final class InformazioniLegaliTests: XCTestCase {
    func testPagineDelServerSiComponganoConLIndirizzo() {
        XCTAssertEqual(InformazioniLegali.indirizzo(.privacy, server: "https://schieraxi.example")?.absoluteString, "https://schieraxi.example/privacy")
        XCTAssertEqual(InformazioniLegali.indirizzo(.termini, server: "https://schieraxi.example/")?.absoluteString, "https://schieraxi.example/termini")
        XCTAssertEqual(InformazioniLegali.indirizzo(.privacy, server: " https://schieraxi.example:8443// ")?.absoluteString, "https://schieraxi.example:8443/privacy")
    }

    func testSenzaIndirizzoValidoNonCeCollegamento() {
        XCTAssertNil(InformazioniLegali.indirizzo(.privacy, server: ""))
        XCTAssertNil(InformazioniLegali.indirizzo(.privacy, server: "schieraxi.example"))
        XCTAssertNil(InformazioniLegali.indirizzo(.termini, server: "http://schieraxi.example"))   // testo in chiaro solo verso questo computer
        XCTAssertNil(InformazioniLegali.indirizzo(.termini, server: "https://utente:segreto@schieraxi.example"))
    }

    func testSorgenteSoloHttpsPulito() {
        XCTAssertEqual(InformazioniLegali.sorgente("https://codice.example/schieraxi")?.absoluteString, "https://codice.example/schieraxi")
        XCTAssertNil(InformazioniLegali.sorgente(nil))
        XCTAssertNil(InformazioniLegali.sorgente(""))
        XCTAssertNil(InformazioniLegali.sorgente("http://codice.example/schieraxi"))
        XCTAssertNil(InformazioniLegali.sorgente("javascript:alert(1)"))
        XCTAssertNil(InformazioniLegali.sorgente("https://utente:pw@codice.example"))
        XCTAssertNil(InformazioniLegali.sorgente("https://" + String(repeating: "a", count: 400) + ".example"))
    }

    func testCampoSorgenteFacoltativoNelloStato() throws {
        let senza: StatoSorgente = try Fixture.decodifica("stato")
        XCTAssertNil(senza.sorgente)
        let con = try JSONDecoder().decode(StatoSorgente.self, from: Data(#"{"sorgente":"https://codice.example/schieraxi","altro":1}"#.utf8))
        XCTAssertEqual(con.sorgente, "https://codice.example/schieraxi")
    }

    @MainActor
    func testProvaConDatiDiEsempioSiAccendeESiSpegne() async throws {
        let prima = ServerCorrente.condiviso
        defer { ProvaEsempio.esci(); ServerCorrente.condiviso = prima }
        XCTAssertFalse(ProvaEsempio.attiva)
        ProvaEsempio.avvia()
        XCTAssertTrue(ProvaEsempio.attiva)
        XCTAssertTrue(Demo.attivo)
        XCTAssertFalse(IndirizzoServer.manca, "in prova c'è un indirizzo finto: l'app non chiede il server")
        XCTAssertTrue(IndirizzoServer.attuale.contains(".invalid"))
        // i dati di esempio rispondono senza rete
        let stato: StatoSorgente = try await ServerCorrente.condiviso.get("/api/stato")
        XCTAssertNil(stato.sorgente)
        ProvaEsempio.esci()
        XCTAssertFalse(ProvaEsempio.attiva)
        XCTAssertFalse(Demo.attivo)
    }

    func testManifestDellaPrivacyDichiaraNienteTracciamento() throws {
        let url = try XCTUnwrap(Bundle(for: SessioneAccount.self).url(forResource: "PrivacyInfo", withExtension: "xcprivacy"), "PrivacyInfo.xcprivacy manca dall'app")
        let dati = try Data(contentsOf: url)
        let radice = try XCTUnwrap(try PropertyListSerialization.propertyList(from: dati, format: nil) as? [String: Any])
        XCTAssertEqual(radice["NSPrivacyTracking"] as? Bool, false)
        XCTAssertEqual((radice["NSPrivacyTrackingDomains"] as? [Any])?.count, 0)
        let api = try XCTUnwrap(radice["NSPrivacyAccessedAPITypes"] as? [[String: Any]])
        let ud = try XCTUnwrap(api.first { $0["NSPrivacyAccessedAPIType"] as? String == "NSPrivacyAccessedAPICategoryUserDefaults" })
        XCTAssertTrue((ud["NSPrivacyAccessedAPITypeReasons"] as? [String] ?? []).contains("CA92.1"))
        let raccolti = try XCTUnwrap(radice["NSPrivacyCollectedDataTypes"] as? [[String: Any]])
        XCTAssertFalse(raccolti.isEmpty)
        for voce in raccolti {
            XCTAssertEqual(voce["NSPrivacyCollectedDataTypeTracking"] as? Bool, false)
        }
    }
}
