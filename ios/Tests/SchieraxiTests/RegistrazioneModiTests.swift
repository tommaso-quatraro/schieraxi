import XCTest
@testable import Schieraxi

// Modi di registrazione (invito, email, aperta) e iscrizione con il codice per posta. Solo indirizzi finti.

final class RegistrazioneModiTests: XCTestCase {
    func testIlModoSiLeggeDalCorpoDel401() {
        func modo(_ json: String) -> ModalitaRegistrazione { ModalitaRegistrazione.leggi(corpo: Data(json.utf8)) }
        XCTAssertEqual(modo(#"{"detail": "Accesso richiesto", "registrazione": "email"}"#), .email)
        XCTAssertEqual(modo(#"{"registrazione": "aperta"}"#), .aperta)
        XCTAssertEqual(modo(#"{"registrazione": "invito"}"#), .invito)
        XCTAssertEqual(modo(#"{"registrazione": "boh"}"#), .invito, "sconosciuto = invito")
        XCTAssertEqual(modo("<html>"), .invito, "non JSON = invito")
        XCTAssertEqual(modo(#"{"registrazione": 5}"#), .invito)
    }

    func testCosaChiedeOgniModo() {
        XCTAssertTrue(ModalitaRegistrazione.invito.invitoObbligatorio)
        XCTAssertFalse(ModalitaRegistrazione.invito.chiedeEmail)
        XCTAssertTrue(ModalitaRegistrazione.email.invitoObbligatorio)
        XCTAssertTrue(ModalitaRegistrazione.email.chiedeEmail)
        XCTAssertFalse(ModalitaRegistrazione.aperta.invitoObbligatorio)
        XCTAssertTrue(ModalitaRegistrazione.aperta.chiedeEmail)
    }

    func testLaRispostaDellIscrizioneConEmailSiLegge() throws {
        let r: RispostaAccount = try Decodifica.decodifica(Data(#"{"ok": true, "verifica_email": true, "scade_minuti": 15, "iscrizione": "abc"}"#.utf8))
        XCTAssertEqual(r.verificaEmail, true)
        XCTAssertEqual(r.iscrizione, "abc")
        let vecchia: RispostaAccount = try Decodifica.decodifica(Data("{}".utf8))
        XCTAssertNil(vecchia.verificaEmail)
    }

    @MainActor
    func testRegistrazioneConEmailRestituisceLIscrizioneEPoiSiConferma() async throws {
        let server = ServerDiProva { _, percorso, _ in
            if percorso == "/api/account/registra" { return Data(#"{"ok": true, "verifica_email": true, "iscrizione": "segreto-finto"}"#.utf8) }
            return Data(#"{"multiutente": true, "utente": {"id": 1, "nome_utente": "mister", "ruolo": "utente", "nome_visualizzato": "Mister"}, "token": "fw_non_usato"}"#.utf8)
        }
        let s = SessioneAccount(server: server)
        let attesa = try await s.registra(nomeUtente: "Mister", password: "Prova-Finta-Zero", invito: "", email: " nome@example.invalid ")
        XCTAssertEqual(attesa, IscrizioneInAttesa(email: "nome@example.invalid", iscrizione: "segreto-finto"))
        XCTAssertNil(s.utente, "senza il codice l'account non c'è")
        let corpo = String(decoding: try XCTUnwrap(server.corpiInviati(a: "/api/account/registra").first), as: UTF8.self)
        XCTAssertTrue(corpo.contains("nome@example.invalid"))
        XCTAssertFalse(corpo.contains("\"invito\""), "invito vuoto: non si manda")
    }
}
