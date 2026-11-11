import Foundation
import Testing
@testable import Schieraxi

// Issue #590 (parte di #167). Dopo #589 il cambio della password restituisce un codice di recupero nuovo (`codice_recupero`)
// e quello di prima smette di valere. Il server chiude anche tutte le sessioni, questa compresa, e alle app manda un `token`
// nuovo nella risposta. La web mostra subito il codice e l'avviso «Password cambiata. Gli altri dispositivi sono stati
// scollegati e il codice di recupero è nuovo: salvalo.» (`collegaAccount` in `fanta/web/app.js`); senza codice (server più
// vecchio) solo «Password cambiata. Gli altri dispositivi sono stati scollegati.». L'iPhone fa lo stesso e tiene la sessione
// nuova: prima scartava la risposta, perdeva il codice e alla richiesta dopo tornava all'accesso.
// Solo nomi, token e codici inventati; ogni test usa UserDefaults suoi.

/// Un utente finto, come lo manda il server accanto a `ok`.
private let utenteFinto = #"{"id": 7, "nome_utente": "mister.rossi", "ruolo": "utente", "creato": "2026-11-01"}"#

/// La risposta del server nuovo: utente, `ok`, codice nuovo e token nuovo (l'app manda «Bearer», quindi il token è nel corpo).
private let rispostaCompleta =
    #"{"multiutente": true, "utente": \#(utenteFinto), "ok": true, "codice_recupero": "KKKKK-LLLLL-MMMMM", "token": "tok-nuovo-prova"}"#

/// Quante volte la sessione ha svuotato i dati del telefono.
@MainActor
private final class Contatore {
    var volte = 0
}

@MainActor
@Suite("Cambio della password: il nuovo codice di recupero, come la web (#590)")
struct CambioPasswordCodiceTests {
    /// Una sessione già connessa (token «tok-vecchio») con un server finto che al cambio della password risponde `risposta`.
    private struct Prova {
        let sessione: SessioneAccount
        let archivio: MemoriaToken
        let server: ServerDiProva
        let pulizie: Contatore
        let memoria: UserDefaults
        let nome: String

        var token: String? { archivio.leggi(server: server.indirizzo) }
        func chiudi() { memoria.removePersistentDomain(forName: nome) }
    }

    private func prova(risposta: String, attesa: UInt64 = 0) throws -> Prova {
        let nome = "prova-cambio-password-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        let server = ServerDiProva { _, percorso, _ in
            guard percorso == "/api/account/cambia-password" else { return Data("{}".utf8) }
            if attesa > 0 { try await Task.sleep(nanoseconds: attesa) }
            return Data(risposta.utf8)
        }
        let archivio = MemoriaToken()
        archivio.salva("tok-vecchio", server: server.indirizzo)
        let pulizie = Contatore()
        let sessione = SessioneAccount(server: server, archivio: archivio, memoria: memoria, pulisci: { pulizie.volte += 1 })
        return Prova(sessione: sessione, archivio: archivio, server: server, pulizie: pulizie, memoria: memoria, nome: nome)
    }

    /// Una risposta con questo codice e questo token, scritti come JSON vero (virgolette e caratteri strani compresi).
    private func rispostaCon(codice: String, token: String) throws -> String {
        let campi: [String: Any] = ["ok": true, "codice_recupero": codice, "token": token]
        return String(decoding: try JSONSerialization.data(withJSONObject: campi), as: UTF8.self)
    }

    @Test("Il codice nuovo della risposta arriva a chi mostra la schermata")
    func codiceNuovo() async throws {
        let p = try prova(risposta: rispostaCompleta)
        defer { p.chiudi() }
        let codice = try await p.sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12")
        #expect(codice == "KKKKK-LLLLL-MMMMM")
        #expect(!p.sessione.inCorso)
    }

    @Test("Il token nuovo prende il posto di quello chiuso dal server: si resta dentro, senza svuotare il telefono")
    func tieneLaSessioneNuova() async throws {
        let p = try prova(risposta: rispostaCompleta)
        defer { p.chiudi() }
        let generazione = p.sessione.generazione
        try await p.sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12")
        #expect(p.token == "tok-nuovo-prova", "il token di prima il server l'ha chiuso: alla richiesta dopo si tornerebbe all'accesso")
        #expect(p.sessione.utente != nil)
        #expect(p.pulizie.volte == 0, "è lo stesso utente: i dati del telefono restano")
        #expect(p.sessione.generazione == generazione, "le schermate non si ricostruiscono (il foglio con il codice resta aperto)")
    }

    @Test("Server più vecchio, senza codice nuovo: la password è cambiata e non c'è niente da mostrare",
          arguments: [
              #"{"ok": true}"#,
              #"{"multiutente": true, "utente": \#(utenteFinto), "ok": true, "codice_recupero": null}"#,
              #"{"multiutente": true, "utente": \#(utenteFinto), "ok": true, "codice_recupero": ""}"#,
          ])
    func senzaCodice(risposta: String) async throws {
        let p = try prova(risposta: risposta)
        defer { p.chiudi() }
        let codice = try await p.sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12")
        #expect(codice == nil)
        #expect(p.token == "tok-vecchio", "senza un token nuovo resta quello di prima")
    }

    @Test("Un codice che non è un codice non si mostra, ma la sessione nuova si tiene (la password è già cambiata)",
          arguments: ["<b>ciao</b>", "AAAAA BBBBB", String(repeating: "A", count: 101)])
    func codiceNonValido(codice: String) async throws {
        let p = try prova(risposta: rispostaCon(codice: codice, token: "tok-nuovo-prova"))
        defer { p.chiudi() }
        await #expect(throws: SessioneAccount.Errore.rispostaIncompleta) {
            try await p.sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12")
        }
        #expect(p.token == "tok-nuovo-prova")
        #expect(!p.sessione.inCorso)
    }

    @Test("Un token che non è un token non entra nel Keychain", arguments: ["", "con spazio", String(repeating: "t", count: 513)])
    func tokenNonValido(token: String) async throws {
        let p = try prova(risposta: rispostaCon(codice: "KKKKK-LLLLL-MMMMM", token: token))
        defer { p.chiudi() }
        let codice = try await p.sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12")
        #expect(codice == "KKKKK-LLLLL-MMMMM")
        #expect(p.token == "tok-vecchio")
    }

    @Test("Uscito mentre la richiesta era in corso: il token nuovo non riapre la sessione")
    func uscitaDurante() async throws {
        let p = try prova(risposta: rispostaCompleta, attesa: 300_000_000)
        defer { p.chiudi() }
        let sessione = p.sessione
        let lenta = Task { try? await sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12") }
        try await Task.sleep(nanoseconds: 50_000_000)
        await sessione.esci()
        _ = await lenta.value
        #expect(sessione.stato == .daAccedere)
        #expect(p.token == nil, "dopo «Esci» nessun token deve restare sul telefono")
    }

    @Test("L'avviso dopo il cambio: le frasi della web, dal catalogo comune")
    func avviso() {
        #expect(TestiAccount.esitoCambioPassword(codiceNuovo: true) == Catalogo.Account.passwordCambiataCodice)
        #expect(TestiAccount.esitoCambioPassword(codiceNuovo: false) == Catalogo.Account.passwordCambiataOk)
        #expect(Catalogo.Account.passwordCambiataCodice.contains("codice di recupero è nuovo"))
    }
}
