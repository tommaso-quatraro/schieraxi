import Foundation
import Testing
@testable import Schieraxi

// Issue #590 (parte di #167). Dopo #589 il cambio della password restituisce un codice di recupero nuovo (`codice_recupero`)
// e quello di prima smette di valere. Il server chiude anche tutte le sessioni, questa compresa, e alle app manda un `token`
// nuovo nella risposta. La web mostra subito il codice e l'avviso «Password cambiata. Gli altri dispositivi sono stati
// scollegati e il codice di recupero è nuovo: salvalo.» (`collegaAccount` in `fanta/web/app.js`); senza codice (server più
// vecchio) solo «Password cambiata. Gli altri dispositivi sono stati scollegati.». L'iPhone fa lo stesso e tiene la sessione
// nuova: prima scartava la risposta, perdeva il codice e alla richiesta dopo tornava all'accesso.
// Il server toglie anche il token del widget: l'app ne chiede uno nuovo, senza buttare riassunto e copie del widget, e non lo
// tiene se nel frattempo si è usciti. Solo nomi, token e codici inventati; ogni test usa UserDefaults suoi e un widget finto
// (token e Keychain condiviso in memoria, cartella del gruppo temporanea): mai il Keychain o i file veri.

/// Un utente finto, come lo manda il server accanto a `ok`.
private let utenteFinto = #"{"id": 7, "nome_utente": "mister.rossi", "ruolo": "utente", "creato": "2026-11-01"}"#

/// La risposta del server nuovo: utente, `ok`, codice nuovo e token nuovo (l'app manda «Bearer», quindi il token è nel corpo).
private let rispostaCompleta =
    #"{"multiutente": true, "utente": \#(utenteFinto), "ok": true, "codice_recupero": "KKKKK-LLLLL-MMMMM", "token": "tok-nuovo-prova"}"#

/// Il token del widget che il server finto dà dopo il cambio (inventato).
private let rispostaTokenWidget = #"{"token": "fw_nuovoDiProva123456", "scade": "2027-02-01T12:00:00"}"#

/// Quante volte la sessione ha svuotato i dati del telefono.
@MainActor
private final class ContatorePulizie {
    var volte = 0
}

/// Quante volte si è ripassato il collegamento al widget (dal lavoro in sottofondo: protetto da un blocco).
private final class ContaSincronizzazioni: @unchecked Sendable {
    private let blocco = NSLock()
    private var conto = 0
    func una() { blocco.lock(); conto += 1; blocco.unlock() }
    var volte: Int { blocco.lock(); defer { blocco.unlock() }; return conto }
}

/// Il widget finto: token in memoria, cartella del gruppo temporanea, Keychain condiviso in memoria. Mai i file veri.
private struct WidgetFinto {
    let archivio = MemoriaToken()
    let portachiavi = MemoriaCollegamento()
    let sincronizzazioni = ContaSincronizzazioni()
    let cartella: URL
    let memoria: UserDefaults

    init(memoria: UserDefaults) throws {
        cartella = FileManager.default.temporaryDirectory.appendingPathComponent("cambio-password-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        self.memoria = memoria
    }

    var luoghi: TokenWidget.Luoghi {
        let cartella = cartella, conta = sincronizzazioni
        return TokenWidget.Luoghi(archivio: archivio, memoria: memoria, cartella: { cartella }, portachiavi: portachiavi,
                                  sincronizza: { conta.una() })
    }

    func chiudi() { try? FileManager.default.removeItem(at: cartella) }
}

@MainActor
@Suite("Cambio della password: il nuovo codice di recupero, come la web (#590)")
struct CambioPasswordCodiceTests {
    /// Una sessione già connessa (token «tok-vecchio») con un server finto che al cambio della password risponde `risposta`
    /// e alla richiesta del token del widget `tokenWidget` (dopo `attesaWidget`, anche se il lavoro viene annullato).
    private struct Prova {
        let sessione: SessioneAccount
        let archivio: MemoriaToken
        let server: ServerDiProva
        let pulizie: ContatorePulizie
        let widget: WidgetFinto
        let memoria: UserDefaults
        let nome: String

        var token: String? { archivio.leggi(server: server.indirizzo) }
        func chiudi() {
            widget.chiudi()
            memoria.removePersistentDomain(forName: nome)
        }
    }

    private func prova(risposta: String, attesa: UInt64 = 0, tokenWidget: String = rispostaTokenWidget,
                       attesaWidget: UInt64 = 0) throws -> Prova {
        let nome = "prova-cambio-password-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        let server = ServerDiProva { _, percorso, _ in
            switch percorso {
            case "/api/account/cambia-password":
                if attesa > 0 { try await Task.sleep(nanoseconds: attesa) }
                return Data(risposta.utf8)
            case "/api/account/token-widget":
                if attesaWidget > 0 { try? await Task.sleep(nanoseconds: attesaWidget) }
                return Data(tokenWidget.utf8)
            default:
                return Data("{}".utf8)
            }
        }
        let archivio = MemoriaToken()
        archivio.salva("tok-vecchio", server: server.indirizzo)
        let pulizie = ContatorePulizie()
        let widget = try WidgetFinto(memoria: memoria)
        let sessione = SessioneAccount(server: server, archivio: archivio, memoria: memoria, pulisci: { pulizie.volte += 1 },
                                       widget: widget.luoghi)
        return Prova(sessione: sessione, archivio: archivio, server: server, pulizie: pulizie, widget: widget, memoria: memoria, nome: nome)
    }

    /// Una risposta con questo codice e questo token, scritti come JSON vero (virgolette e caratteri strani compresi).
    private func rispostaCon(codice: String, token: String) throws -> String {
        let campi: [String: Any] = ["ok": true, "codice_recupero": codice, "token": token]
        return try String(decoding: JSONSerialization.data(withJSONObject: campi), as: UTF8.self)
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

    // MARK: il token del widget (il server lo toglie insieme alle sessioni)

    @Test("Dopo il cambio si chiede il token nuovo del widget: via solo quello vecchio, riassunto e copia del widget restano")
    func tokenDelWidgetDopoIlCambio() async throws {
        let p = try prova(risposta: rispostaCompleta)
        defer { p.chiudi() }
        let indirizzo = p.server.indirizzo
        let w = p.widget
        // il widget collegato con il token di prima, che ancora non scadeva: senza il cambio non si chiederebbe di nuovo
        w.archivio.salva("fw_vecchioDiProva1234", server: indirizzo)
        p.memoria.set("2099-01-01T00:00:00", forKey: "tokenWidgetScade|" + indirizzo)
        Condiviso.aggiorna(cartella: w.cartella) {
            $0.indirizzo = indirizzo
            $0.token = "fw_vecchioDiProva1234"
            $0.tokenPerIndirizzo = indirizzo
            $0.riassunto = .esempio
        }
        MemoriaWidget.salva(CopiaWidget(dati: Data("{}".utf8), etag: nil, scaricatoIl: Date(), chi: "copia-di-prova"),
                            cartella: w.cartella, memoria: p.memoria)
        let collegamento = try JSONEncoder().encode(CodiceWidget.Contenuto(i: indirizzo, t: "fw_vecchioDiProva1234"))
        _ = w.portachiavi.scrivi(collegamento, gruppi: ["prova"])

        try await p.sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12")
        let lavoro = try #require(p.sessione.rinnovoWidget, "dopo il cambio si chiede il token del widget")
        await lavoro.value

        #expect(p.server.quante("POST /api/account/token-widget") == 1)
        #expect(w.archivio.leggi(server: indirizzo) == "fw_nuovoDiProva123456")
        #expect(w.sincronizzazioni.volte == 1, "il token nuovo si ripassa al widget")
        let condiviso = Condiviso.leggi(cartella: w.cartella)
        #expect(condiviso.token(per: indirizzo) == nil, "il token revocato non resta nel file del gruppo")
        #expect(condiviso.riassunto != nil, "il riassunto è dello stesso utente: resta")
        #expect(MemoriaWidget.leggi(per: "copia-di-prova", cartella: w.cartella, memoria: p.memoria) != nil, "la copia del widget resta")
        #expect(w.portachiavi.leggi() == nil, "il token revocato non resta nel Keychain condiviso")
    }

    @Test("Il token del widget che arriva durante «Esci» non si tiene")
    func tokenDelWidgetDuranteLUscita() async throws {
        let p = try prova(risposta: rispostaCompleta, attesaWidget: 300_000_000)
        defer { p.chiudi() }
        let indirizzo = p.server.indirizzo
        try await p.sessione.cambiaPassword(attuale: "vecchia-prova-1", nuova: "nuova-prova-12")
        let lavoro = try #require(p.sessione.rinnovoWidget)
        await p.sessione.esci()
        await lavoro.value
        #expect(p.sessione.stato == .daAccedere)
        #expect(p.token == nil)
        #expect(p.widget.archivio.leggi(server: indirizzo) == nil, "dopo «Esci» nessun token del widget sul telefono")
        #expect(p.widget.sincronizzazioni.volte == 0, "niente da ripassare al widget")
    }

    @Test("La sessione cambia mentre si aspetta il token del widget: il token non si tiene",
          arguments: [nil, "tok-di-un-altro"] as [String?])
    func sessioneCambiataDuranteLAttesa(dopo: String?) async throws {
        let nome = "prova-impronta-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        let w = try WidgetFinto(memoria: memoria)
        defer { w.chiudi(); memoria.removePersistentDomain(forName: nome) }
        let indirizzo = "https://prova-impronta-\(UUID().uuidString).invalid"
        let sessione = MemoriaToken()
        sessione.salva("tok-di-prima", server: indirizzo)
        let server = ServerDiProva(indirizzo: indirizzo) { _, percorso, _ in
            // l'uscita (o un altro accesso) arriva mentre il server prepara il token
            if percorso == "/api/account/token-widget" {
                if let dopo { sessione.salva(dopo, server: indirizzo) } else { sessione.cancella(server: indirizzo) }
            }
            return Data(rispostaTokenWidget.utf8)
        }
        await TokenWidget.assicura(server: server, luoghi: w.luoghi, sessione: sessione)
        #expect(server.quante("POST /api/account/token-widget") == 1)
        #expect(w.archivio.leggi(server: indirizzo) == nil)
        #expect(w.sincronizzazioni.volte == 0)
    }

    @Test("Con la stessa sessione il token del widget si tiene (la prova sopra può fallire)")
    func stessaSessione() async throws {
        let nome = "prova-impronta-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        let w = try WidgetFinto(memoria: memoria)
        defer { w.chiudi(); memoria.removePersistentDomain(forName: nome) }
        let indirizzo = "https://prova-impronta-\(UUID().uuidString).invalid"
        let sessione = MemoriaToken()
        sessione.salva("tok-di-prima", server: indirizzo)
        let server = ServerDiProva(indirizzo: indirizzo) { _, _, _ in Data(rispostaTokenWidget.utf8) }
        await TokenWidget.assicura(server: server, luoghi: w.luoghi, sessione: sessione)
        #expect(w.archivio.leggi(server: indirizzo) == "fw_nuovoDiProva123456")
        #expect(w.sincronizzazioni.volte == 1)
    }
}
