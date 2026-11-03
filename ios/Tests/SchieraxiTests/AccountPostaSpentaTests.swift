import Foundation
import Testing
@testable import Schieraxi

// Issue #174. Con la posta spenta sul server (`email_attiva: false`) «Il tuo account» della web mostra solo la frase
// `account.email_spenta` (`htmlEmailAccount` in `fanta/web/app.js`) al posto dell'email e di «Aggiungi un'email»: nessun codice
// può arrivare per posta. Con un'email già collegata resta tutto (si può ancora toglierla). L'iPhone fa lo stesso.
// Solo nomi e indirizzi finti (example.invalid); ogni test usa UserDefaults suoi.

/// Le email dell'account (sua e di Google) e se al posto della voce dell'email va la frase della posta spenta.
struct CasoPostaSpenta: Sendable, CustomTestStringConvertible {
    let postaAccesa: Bool
    let account: String?
    let google: String?
    let soloFrase: Bool

    var testDescription: String {
        "posta \(postaAccesa ? "accesa" : "spenta"), account \(account ?? "nessuna"), Google \(google ?? "nessuna")"
    }
}

private let casiPostaSpenta: [CasoPostaSpenta] = [
    CasoPostaSpenta(postaAccesa: false, account: nil, google: nil, soloFrase: true),
    CasoPostaSpenta(postaAccesa: false, account: "", google: "  ", soloFrase: true),                      // vuote = nessuna email
    CasoPostaSpenta(postaAccesa: false, account: "nome@example.invalid", google: nil, soloFrase: false),  // ha un'email: resta «Gestisci l'email», come la web
    CasoPostaSpenta(postaAccesa: false, account: nil, google: "nome@example.invalid", soloFrase: false),  // l'email di Google
    CasoPostaSpenta(postaAccesa: true, account: nil, google: nil, soloFrase: false),                      // posta accesa: «Aggiungi un'email»
    CasoPostaSpenta(postaAccesa: true, account: "nome@example.invalid", google: nil, soloFrase: false),
]

@Suite("Il tuo account: posta spenta sul server (#174)")
struct AccountPostaSpentaTests {
    @Test("La frase della web, `account.email_spenta` di `testi.js`")
    func frase() {
        #expect(TestiAccount.emailSpenta
                == "Su questo server l'invio delle email è spento: per ora non puoi collegare un'email. Se dimentichi la password ti serve il codice di recupero.")
    }

    @Test("Solo la frase quando la posta è spenta e l'account non ha un'email", arguments: casiPostaSpenta)
    func soloFrase(caso: CasoPostaSpenta) {
        #expect(ProfiloAccount.soloPostaSpenta(postaAccesa: caso.postaAccesa, account: caso.account, google: caso.google) == caso.soloFrase)
    }
}

/// Un utente finto per `/api/account/me`.
private let utente = #"{"id": 7, "nome_utente": "mister.rossi", "ruolo": "utente", "creato": "2026-11-01"}"#

@MainActor
@Suite("Il tuo account: la posta si legge anche da /api/account/me, come la web")
struct PostaDalProfiloTests {
    /// Fa leggere alla sessione un `/api/account/me` con questo pezzo in più e dice se la posta risulta accesa.
    private func accesaDopo(_ pezzo: String, primaAccesa: Bool) async throws -> Bool {
        let nome = "prova-posta-me-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        memoria.set(primaAccesa, forKey: PostaServer.chiave)
        let server = ServerDiProva { _, percorso, _ in
            percorso == "/api/account/me"
                ? Data(#"{"multiutente": true, "utente": \#(utente)\#(pezzo)}"#.utf8)
                : Data("{}".utf8)
        }
        let archivio = MemoriaToken()
        archivio.salva("tok", server: server.indirizzo)
        let sessione = SessioneAccount(server: server, archivio: archivio, memoria: memoria, pulisci: {})
        await sessione.verifica()
        #expect(sessione.utente?.nomeUtente == "mister.rossi", "la risposta finta deve essere letta")
        return PostaServer.accesa(in: memoria)
    }

    @Test("`email_attiva: false` spegne la posta")
    func spenta() async throws {
        let accesa = try await accesaDopo(#", "email_attiva": false"#, primaAccesa: true)
        #expect(!accesa)
    }

    @Test("`email_attiva: true` la riaccende")
    func riaccesa() async throws {
        let accesa = try await accesaDopo(#", "email_attiva": true"#, primaAccesa: false)
        #expect(accesa)
    }

    @Test("Server vecchio senza il campo: accesa, come la web")
    func senzaCampo() async throws {
        let accesa = try await accesaDopo("", primaAccesa: false)
        #expect(accesa)
    }
}
