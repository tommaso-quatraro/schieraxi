import Foundation
import Testing
@testable import Schieraxi

// Accesso uguale alla web (`mostraAccesso` e `campiAccesso` in `fanta/web/app.js`, testi `accesso.*` e `account.*`):
// testi, posta spenta sul server, passi del modulo, recupero della password con l'email e con il codice.
// Solo nomi e indirizzi finti (example.invalid); le password sono di prova. Ogni test usa oggetti suoi (server finto,
// UserDefaults e archivio dei token propri): i test girano in parallelo senza toccarsi.

private let passwordBuona = "Prova-Finta-Zero"

/// Un modulo di registrazione pronto da mandare (manca solo la casella).
private func registrazione(_ modo: ModalitaRegistrazione = .invito) -> ModuloAccesso {
    var m = ModuloAccesso(scheda: .registrati)
    m.nome = "mister.rossi"
    m.password = passwordBuona
    if modo.invitoObbligatorio { m.invito = "INV-123" }
    if modo.chiedeEmail { m.email = "nome@example.invalid" }
    return m
}

/// Corpi di risposte 401 (e altro) con il valore di `email_attiva` che se ne legge.
private let corpiPosta: [(String, Bool?)] = [
    (#"{"detail": "Accesso richiesto", "multiutente": true, "email_attiva": false}"#, false),
    (#"{"detail": "Accesso richiesto", "email_attiva": true}"#, true),
    (#"{"detail": "Nome utente o password non corretti"}"#, nil),   // campo assente: resta quello di prima
    (#"{"email_attiva": 0}"#, nil),                                  // non è vero o falso: come la web, non conta
    (#"{"email_attiva": "no"}"#, nil),
    ("<html><body>Wi-Fi</body></html>", nil),
    ("[]", nil),
]

/// Risposte al recupero senza un nuovo codice di recupero valido (o illeggibili).
private let risposteSenzaCodice: [String] = [
    #"{"ok": true}"#,
    #"{"ok": true, "codice_recupero": ""}"#,
    #"{"ok": true, "codice_recupero": "<b>ciao</b> ciao"}"#,
    #"{"ok": true, "codice_recupero": 5}"#,
    "<html><body>Benvenuto</body></html>",
]

/// I due passi del recupero con l'email.
enum PassoEmail: String, CaseIterable, Sendable {
    case chiediCodice, conferma
}

// MARK: - testi

@Suite("Accesso: testi della web")
struct TestiAccessoTests {
    @Test("Casella non spuntata: la frase di `accesso.spunta_letto`, con l'età")
    func spuntaLetto() {
        #expect(TestiAccesso.spuntaLetto == "Per registrarti spunta la casella: hai letto Privacy e Termini d'uso e hai almeno 14 anni")
    }

    @Test("Cambia la password: «Ripeti la nuova password» e «Le due password non coincidono.» come la web")
    func ripetiPassword() {
        #expect(TestiAccount.ripetiPassword == "Ripeti la nuova password")
        #expect(TestiAccount.passwordDiverse == "Le due password non coincidono.")
    }

    @Test("Risposta incompleta: la frase di `accesso.risposta_incompleta`")
    @MainActor
    func rispostaIncompleta() {
        #expect(TestiAccesso.rispostaIncompleta == "Qualcosa non ha funzionato: riprova")
        #expect(SessioneAccount.Errore.rispostaIncompleta.errorDescription == TestiAccesso.rispostaIncompleta)
    }
}

// MARK: - posta spenta

@Suite("Accesso: posta spenta sul server (`email_attiva`)")
struct PostaSpentaTests {
    @Test("Il campo si legge solo se è vero o falso", arguments: corpiPosta)
    func leggi(corpo: String, atteso: Bool?) {
        #expect(PostaServer.leggi(corpo: Data(corpo.utf8)) == atteso)
    }

    @Test("Si ricorda solo quando il server lo dice; mai saputo = accesa")
    func siRicorda() throws {
        let nome = "prova-posta-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        #expect(PostaServer.accesa(in: memoria))
        PostaServer.salva(corpo: Data(#"{"detail": "Accesso richiesto", "email_attiva": false}"#.utf8), in: memoria)
        #expect(!PostaServer.accesa(in: memoria))
        PostaServer.salva(corpo: Data(#"{"detail": "Nome utente o password non corretti"}"#.utf8), in: memoria)
        #expect(!PostaServer.accesa(in: memoria), "un 401 di un accesso sbagliato (senza il campo) non la riaccende")
        PostaServer.salva(corpo: Data(#"{"email_attiva": true}"#.utf8), in: memoria)
        #expect(PostaServer.accesa(in: memoria))
    }

    @Test("Registrazione con l'invito e posta spenta: niente campo email, come la web")
    func registrazioneSenzaEmail() {
        var m = registrazione(.invito)
        #expect(m.campi(.invito, postaAccesa: false) == [.invito, .nome, .password])
        #expect(m.campi(.invito, postaAccesa: true) == [.invito, .nome, .email, .password])
        // un'email scritta prima di sapere che la posta è spenta: il campo non c'è più, quindi non conta e non parte
        m.email = "non-una-email"
        #expect(m.pronto(.invito, postaAccesa: false))
        #expect(m.emailDaMandare(.invito, postaAccesa: false) == "")
        #expect(!m.pronto(.invito, postaAccesa: true))
        m.email = "nome@example.invalid"
        #expect(m.emailDaMandare(.invito, postaAccesa: true) == "nome@example.invalid")
    }

    @Test("Con i modi «email» e «aperta» il campo resta (la web lo toglie solo con l'invito)",
          arguments: [ModalitaRegistrazione.email, .aperta])
    func modiConEmail(modo: ModalitaRegistrazione) {
        let m = registrazione(modo)
        #expect(m.campi(modo, postaAccesa: false).contains(.email))
        #expect(m.emailDaMandare(modo, postaAccesa: false) == "nome@example.invalid")
    }

    @Test("Password dimenticata con la posta spenta: solo il codice di recupero, niente «Con l'email»")
    func recuperoSoloConIlCodice() {
        var m = ModuloAccesso(scheda: .accedi)
        m.vai(.recupera, modo: .aperta, postaAccesa: false)
        #expect(m.metodo == .codice)
        #expect(m.passo == .recuperoCodice)
        #expect(!m.mostraMetodi(postaAccesa: false))
        #expect(m.mostraMetodi(postaAccesa: true))
        #expect(MetodoRecupero.iniziale(.aperta, postaAccesa: true) == .email)
        #expect(MetodoRecupero.iniziale(.aperta, postaAccesa: false) == .codice)
        #expect(MetodoRecupero.iniziale(.invito, postaAccesa: true) == .codice)
    }
}

// MARK: - passi del modulo

@Suite("Accesso: passi del modulo come la web")
struct PassiModuloTests {
    @Test("Tornando ad Accedi il recupero si dimentica (codici e indirizzo)")
    func accediDimenticaIlRecupero() {
        var m = ModuloAccesso(scheda: .recupera, metodo: .email)
        m.emailRecupero = "nome@example.invalid"
        m.codiceEmail = "123456"
        m.codice = "AAAAA-BBBBB"
        m.vai(.accedi, modo: .email)
        #expect(m.codice == "")
        #expect(m.codiceEmail == "")
        #expect(m.emailRecupero == nil)
        #expect(m.passo == .accedi)
    }

    @Test("Tornando a Registrati si riparte dal modulo (la web riapre il modulo)")
    func registratiRipartiDalModulo() {
        var m = ModuloAccesso(scheda: .registrati)
        m.iscrizione = IscrizioneInAttesa(email: "nome@example.invalid", iscrizione: "finta")
        m.codiceEmail = "123456"
        #expect(m.passo == .verificaIscrizione)
        m.vai(.registrati, modo: .email)
        #expect(m.iscrizione == nil)
        #expect(m.codiceEmail == "")
        #expect(m.passo == .registra)
    }

    @Test("Codice per posta partito: si passa al secondo passo, e la password scritta non resta")
    func codiceInviato() {
        var m = ModuloAccesso(scheda: .recupera, metodo: .email)
        m.password = "scritta"
        m.codiceEmail = "1"
        #expect(m.codiceInviato(a: "nome@example.invalid", daPasso: .recuperoEmail))
        #expect(m.passo == .recuperoEmailCodice)
        #expect(m.emailRecupero == "nome@example.invalid")
        #expect(m.password == "")
        #expect(m.codiceEmail == "")
    }

    @Test("Codice partito mentre si è tornati all'accesso: si resta dove si è")
    func codiceInviatoDopoIlCambioDiPasso() {
        var m = ModuloAccesso(scheda: .recupera, metodo: .email)
        m.vai(.accedi, modo: .email)
        #expect(!m.codiceInviato(a: "nome@example.invalid", daPasso: .recuperoEmail))
        #expect(m.passo == .accedi)
        #expect(m.emailRecupero == nil)
    }

    @Test("Invio dalla tastiera: la casella si controlla prima di tutto, anche con il modulo a metà (come la web)")
    func casellaPrimaDiTutto() {
        var vuoto = ModuloAccesso(scheda: .registrati)
        #expect(vuoto.primaDellInvio(.invito) == .avvisa(TestiAccesso.spuntaLetto))
        vuoto.accetto = true
        #expect(vuoto.primaDellInvio(.invito) == .aspetta, "il resto lo dicono i campi: il pulsante resta spento")
        var pronto = registrazione(.invito)
        #expect(pronto.primaDellInvio(.invito) == .avvisa(TestiAccesso.spuntaLetto))
        pronto.accetto = true
        #expect(pronto.primaDellInvio(.invito) == .manda)
        var accesso = ModuloAccesso(scheda: .accedi)
        #expect(accesso.primaDellInvio(.invito) == .aspetta)
        accesso.nome = "mister.rossi"
        accesso.password = "x"
        #expect(accesso.primaDellInvio(.invito) == .manda, "la casella conta solo per registrarsi")
    }
}

// MARK: - recupero della password e registrazione (SessioneAccount)

/// Tiene ferma una risposta del server finto finché il test non la lascia andare.
private actor Cancello {
    private var aperto = false
    private var attese: [CheckedContinuation<Void, Never>] = []

    func aspetta() async {
        if aperto { return }
        await withCheckedContinuation { attese.append($0) }
    }

    func apri() {
        aperto = true
        attese.forEach { $0.resume() }
        attese = []
    }
}

/// Quello che l'app manda per confermare il recupero con l'email.
private struct ConfermaMandata: Decodable, Equatable {
    let email: String
    let codice: String
    let nuova: String
}

/// Il campo della casella nel corpo della registrazione (assente = nil).
private struct TerminiMandati: Decodable {
    let accettoTermini: Bool?
    enum CodingKeys: String, CodingKey { case accettoTermini = "accetto_termini" }
}

private struct EmailMandata: Decodable {
    let email: String
}

@MainActor
@Suite("Accesso: recupero della password e registrazione")
struct RecuperoTests {
    private func sessione(_ server: ServerDiProva) throws -> SessioneAccount {
        let memoria = try #require(UserDefaults(suiteName: "prova-recupero-\(UUID().uuidString)"))
        return SessioneAccount(server: server, archivio: MemoriaToken(), memoria: memoria, pulisci: {})
    }

    private func esegui(_ passo: PassoEmail, _ s: SessioneAccount) async throws {
        switch passo {
        case .chiediCodice: try await s.chiediCodiceEmail("nome@example.invalid")
        case .conferma: _ = try await s.recuperaConEmail(email: "nome@example.invalid", codice: "123456", nuovaPassword: passwordBuona)
        }
    }

    @Test("Con l'email, primo passo: la rotta della web con l'indirizzo pulito")
    func chiediCodice() async throws {
        let server = ServerDiProva { _, _, _ in Data(#"{"ok": true, "scade_minuti": 15}"#.utf8) }
        let s = try sessione(server)
        try await s.chiediCodiceEmail(" nome@example.invalid ")
        let corpo = try #require(server.corpiInviati(a: "POST /api/account/recupero-email").first)
        #expect(try JSONDecoder().decode(EmailMandata.self, from: corpo).email == "nome@example.invalid")
        #expect(!s.inCorso)
    }

    @Test("Con l'email, primo passo: una pagina HTML (200) non vuol dire «codice in arrivo»",
          arguments: ["<html><body>Benvenuto</body></html>", "[]", #"{"ok": false}"#])
    func chiediCodiceRispostaStrana(corpo: String) async throws {
        let s = try sessione(ServerDiProva { _, _, _ in Data(corpo.utf8) })
        await #expect(throws: SessioneAccount.Errore.serverNonValido) {
            try await s.chiediCodiceEmail("nome@example.invalid")
        }
        #expect(!s.inCorso)
    }

    @Test("Con l'email, secondo passo: i campi della web e il nuovo codice di recupero")
    func conferma() async throws {
        let server = ServerDiProva { _, _, _ in Data(#"{"ok": true, "codice_recupero": "GGGGG-HHHHH-JJJJJ"}"#.utf8) }
        let s = try sessione(server)
        let nuovo = try await s.recuperaConEmail(email: " nome@example.invalid ", codice: " 123456 ", nuovaPassword: passwordBuona)
        #expect(nuovo == "GGGGG-HHHHH-JJJJJ")
        let corpo = try #require(server.corpiInviati(a: "/recupero-email/conferma").first)
        #expect(try JSONDecoder().decode(ConfermaMandata.self, from: corpo)
                == ConfermaMandata(email: "nome@example.invalid", codice: "123456", nuova: passwordBuona))
        #expect(!s.inCorso)
    }

    @Test("Con l'email: risposta illeggibile o senza un codice valido = «Qualcosa non ha funzionato: riprova»",
          arguments: risposteSenzaCodice)
    func confermaSenzaCodice(corpo: String) async throws {
        let s = try sessione(ServerDiProva { _, _, _ in Data(corpo.utf8) })
        await #expect(throws: SessioneAccount.Errore.rispostaIncompleta) {
            try await s.recuperaConEmail(email: "nome@example.invalid", codice: "123456", nuovaPassword: passwordBuona)
        }
        #expect(!s.inCorso)
    }

    @Test("Con il codice di recupero: senza un nuovo codice valido non si dice «Password cambiata»",
          arguments: risposteSenzaCodice)
    func recuperoConIlCodiceSenzaCodice(corpo: String) async throws {
        let s = try sessione(ServerDiProva { _, _, _ in Data(corpo.utf8) })
        await #expect(throws: SessioneAccount.Errore.rispostaIncompleta) {
            try await s.recupera(nomeUtente: "mister.rossi", codice: "AAAAA-BBBBB", nuovaPassword: passwordBuona)
        }
        #expect(!s.inCorso)
    }

    @Test("Con l'email: il messaggio d'errore del server arriva uguale",
          arguments: PassoEmail.allCases, [
              ErroreApi.server("Codice sbagliato o scaduto"),
              ErroreApi.codificato(codice: "posta_spenta",
                                   messaggio: "Su questo server l'invio delle email è spento: il codice non può arrivare. Per la password usa il codice di recupero."),
          ])
    func messaggioDelServer(passo: PassoEmail, errore: ErroreApi) async throws {
        let s = try sessione(ServerDiProva { _, _, _ in throw errore })
        do {
            try await esegui(passo, s)
            Issue.record("doveva lanciare l'errore del server")
        } catch {
            let atteso: String
            switch errore {
            case .server(let m), .codificato(_, let m): atteso = m
            default: atteso = ""
            }
            #expect(SchermataAccesso.testoErrore(error) == atteso)
        }
        #expect(!s.inCorso)
    }

    @Test("Con l'email: «troppi tentativi» tiene i secondi da aspettare", arguments: PassoEmail.allCases)
    func troppiTentativi(passo: PassoEmail) async throws {
        let s = try sessione(ServerDiProva { _, _, _ in
            throw ErroreApi.troppiTentativi("Troppi tentativi: aspetta prima di riprovare.", riprovaTra: 120)
        })
        do {
            try await esegui(passo, s)
            Issue.record("doveva lanciare «troppi tentativi»")
        } catch {
            guard case .troppiTentativi(_, let attesa)? = error as? ErroreApi else {
                Issue.record("errore sbagliato: \(error)")
                return
            }
            #expect(attesa == 120)
        }
        #expect(!s.inCorso)
    }

    @Test("Con l'email: una richiesta alla volta (passa da «in corso»)", .timeLimit(.minutes(1)))
    func unaAllaVolta() async throws {
        let cancello = Cancello()
        let s = try sessione(ServerDiProva { _, percorso, _ in
            if percorso == "/api/account/recupero-email" { await cancello.aspetta() }
            return Data(#"{"ok": true, "codice_recupero": "GGGGG-HHHHH-JJJJJ"}"#.utf8)
        })
        let primo = Task { try await s.chiediCodiceEmail("nome@example.invalid") }
        for _ in 0..<1000 where !s.inCorso { await Task.yield() }
        #expect(s.inCorso)
        await #expect(throws: SessioneAccount.Errore.occupato) {
            try await s.recuperaConEmail(email: "nome@example.invalid", codice: "123456", nuovaPassword: passwordBuona)
        }
        await cancello.apri()
        try await primo.value
        #expect(!s.inCorso)
    }

    @Test("Registrazione senza la casella: al server va «accetto_termini»: false")
    func registraSenzaCasella() async throws {
        let server = ServerDiProva { _, _, _ in throw ErroreApi.server("Per iscriverti devi accettare Privacy e Termini d'uso.") }
        let s = try sessione(server)
        await #expect(throws: (any Error).self) {
            try await s.registra(nomeUtente: "mister.rossi", password: passwordBuona, invito: "INV-123", accettoTermini: false)
        }
        let corpo = try #require(server.corpiInviati(a: "/api/account/registra").first)
        #expect(try JSONDecoder().decode(TerminiMandati.self, from: corpo).accettoTermini == false)
        #expect(s.utente == nil)
    }
}
