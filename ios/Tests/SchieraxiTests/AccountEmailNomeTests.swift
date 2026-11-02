import XCTest
@testable import Schieraxi

// Email dell'account: controlli leggeri sul telefono, cosa mostra «Il tuo account» e lettura tollerante della risposta di `/api/account/me`.
// Solo indirizzi finti (example.invalid).

final class AccountEmailNomeTests: XCTestCase {
    func testOrigineDellEmailEFacoltativa() throws {
        let nuovo: RispostaAccount = try Decodifica.decodifica(Data(#"{"multiutente": true, "email": "g@example.invalid", "email_origine": "google"}"#.utf8))
        XCTAssertEqual(nuovo.emailOrigine, "google")
        let vecchio: RispostaAccount = try Decodifica.decodifica(Data(#"{"multiutente": true, "email": "a@example.invalid"}"#.utf8))
        XCTAssertNil(vecchio.emailOrigine)
        let voce: DaFareVoce = try Decodifica.decodifica(Data(#"{"id": "x", "testo": "Ciao", "motivo": "Perché sì"}"#.utf8))
        XCTAssertEqual(voce.motivo, "Perché sì")
        let senza: DaFareVoce = try Decodifica.decodifica(Data(#"{"id": "y", "testo": "Ciao"}"#.utf8))
        XCTAssertNil(senza.motivo)
    }

    func testLEmailDiGoogleCompareDaSola() {
        XCTAssertEqual(ProfiloAccount.email(account: nil, inAttesa: nil, google: "g@example.invalid"), "g@example.invalid")
        XCTAssertEqual(ProfiloAccount.email(account: "a@example.invalid", inAttesa: nil, google: "g@example.invalid"), "a@example.invalid",
                       "l'email dell'account vince su quella di Google")
        XCTAssertEqual(ProfiloAccount.email(account: " ", inAttesa: "x@example.invalid", google: nil), "x@example.invalid (da verificare)")
        XCTAssertNil(ProfiloAccount.email(account: nil, inAttesa: nil, google: ""))
        XCTAssertFalse(ProfiloAccount.mostraVoceEmail(googleCollegato: true), "con Google niente «Aggiungi un'email»")
        XCTAssertTrue(ProfiloAccount.mostraVoceEmail(googleCollegato: false))
    }

    func testLeOpzioniDellAspettoTolteTornanoNormali() throws {
        let nome = "prova-opzioni-\(UUID().uuidString)"
        let memoria = try XCTUnwrap(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        memoria.set("rosso", forKey: "accento")
        memoria.set("comoda", forKey: "densita")
        memoria.set("formazione", forKey: "sezioneAvvio")
        memoria.set("scuro", forKey: "tema")
        OpzioniTolte.pulisci(memoria)
        for chiave in OpzioniTolte.chiavi { XCTAssertNil(memoria.object(forKey: chiave), chiave) }
        XCTAssertEqual(memoria.string(forKey: "tema"), "scuro", "il tema resta: si sceglie ancora")    }

    func testControlloEmail() {
        XCTAssertNil(RegoleAccount.problemaEmail("nome@example.invalid"))
        XCTAssertNotNil(RegoleAccount.problemaEmail(""))
        XCTAssertNotNil(RegoleAccount.problemaEmail("senza-chiocciola"))
        XCTAssertNotNil(RegoleAccount.problemaEmail("a@b"))
        XCTAssertNotNil(RegoleAccount.problemaEmail("a b@example.invalid"))
        XCTAssertNotNil(RegoleAccount.problemaEmail("@example.invalid"))
    }

    func testLaRispostaLeggeEmailEInAttesaConTolleranza() throws {
        let utente = #""utente": {"id": 1, "nome_utente": "mister", "ruolo": "utente", "nome_visualizzato": "Mister"}"#
        func leggi(_ extra: String) throws -> RispostaAccount {
            try Decodifica.decodifica(Data("{\"multiutente\": true, \(utente)\(extra)}".utf8))
        }
        let ok = try leggi(#", "email": "nome@example.invalid", "email_in_attesa": null"#)
        XCTAssertEqual(ok.email, "nome@example.invalid")
        XCTAssertNil(ok.emailInAttesa)
        let attesa = try leggi(#", "email_in_attesa": "altro@example.invalid""#)
        XCTAssertNil(attesa.email)
        XCTAssertEqual(attesa.emailInAttesa, "altro@example.invalid")
        // server vecchio o campo di tipo strano: niente email, ma la risposta si legge lo stesso
        XCTAssertNil(try leggi("").email)
        XCTAssertNil(try leggi(#", "email": 42"#).email)
        XCTAssertEqual(try leggi("").utente?.nome, "Mister")
    }
}
