import CoreGraphics
import Testing
@testable import Schieraxi

// Accesso: ogni campo ha l'etichetta sopra, breve, che resta mentre si scrive (come `campoAccesso` in `fanta/web/app.js`); le
// spiegazioni stanno sotto il campo; VoiceOver legge l'etichetta e poi il problema (o la spiegazione). Le schede «Accedi» e
// «Registrati» stanno in fila solo se ogni parola ci sta intera (issue #195 e #191).
// Solo nomi e indirizzi finti (example.invalid); le password sono di prova.

private let passwordBuona = "Prova-Finta-Zero"

/// Un modulo di registrazione pronto da mandare (manca solo la casella).
private func registrazione(_ modo: ModalitaRegistrazione) -> ModuloAccesso {
    var m = ModuloAccesso(scheda: .registrati)
    m.nome = "mister.rossi"
    m.password = passwordBuona
    if modo.invitoObbligatorio { m.invito = "INV-123" }
    if modo.chiedeEmail { m.email = "nome@example.invalid" }
    return m
}

/// Ogni passo della schermata di accesso, per provare i campi di tutti.
enum PassoDelModulo: String, CaseIterable, Sendable {
    case accedi, registra, verificaIscrizione, recuperoCodice, recuperoEmail, recuperoEmailCodice

    var modulo: ModuloAccesso {
        switch self {
        case .accedi:
            return ModuloAccesso(scheda: .accedi)
        case .registra:
            return ModuloAccesso(scheda: .registrati)
        case .verificaIscrizione:
            var m = ModuloAccesso(scheda: .registrati)
            m.iscrizione = IscrizioneInAttesa(email: "nome@example.invalid", iscrizione: "finta")
            return m
        case .recuperoCodice:
            return ModuloAccesso(scheda: .recupera, metodo: .codice)
        case .recuperoEmail:
            return ModuloAccesso(scheda: .recupera, metodo: .email)
        case .recuperoEmailCodice:
            var m = ModuloAccesso(scheda: .recupera, metodo: .email)
            m.emailRecupero = "nome@example.invalid"
            return m
        }
    }
}

/// Larghezze ideali delle etichette delle schede (spazio fra le due: 6 punti), spazio disponibile e risposta attesa.
struct CasoFila: Sendable, CustomTestStringConvertible {
    let larghezze: [CGFloat]
    let disponibile: CGFloat?
    let inFila: Bool
    var testDescription: String { "\(larghezze) in \(disponibile.map { "\($0)" } ?? "nessuna larghezza")" }
}

private let casiFila: [CasoFila] = [
    CasoFila(larghezze: [80, 110], disponibile: 364, inFila: true),     // testo normale
    CasoFila(larghezze: [120, 145], disponibile: 364, inFila: true),    // testo grande (accessibility-large)
    CasoFila(larghezze: [170, 179], disponibile: 364, inFila: true),    // giusto giusto: metà = (364 - 6) / 2 = 179
    // le due insieme ci starebbero, ma «Registrati» nella sua metà no: andava a capo con il trattino («Regi-strati»)
    CasoFila(larghezze: [100, 180], disponibile: 364, inFila: false),
    CasoFila(larghezze: [181, 231], disponibile: 364, inFila: false),   // testo massimo: una sotto l'altra
    CasoFila(larghezze: [500, 600], disponibile: nil, inFila: true),    // nessuna larghezza proposta: in fila
    CasoFila(larghezze: [], disponibile: 300, inFila: true),
]

@Suite("Accesso: etichette dei campi come la web")
struct EtichetteCampiTests {
    @Test("Ogni campo di ogni passo ha un'etichetta breve sopra; le spiegazioni non stanno nell'etichetta",
          arguments: PassoDelModulo.allCases, [ModalitaRegistrazione.invito, .email, .aperta])
    func etichetteBrevi(passo: PassoDelModulo, modo: ModalitaRegistrazione) {
        let m = passo.modulo
        for posta in [true, false] {
            for campo in m.campi(modo, postaAccesa: posta) {
                let etichetta = m.etichetta(campo, modo)
                #expect(!etichetta.isEmpty, "\(passo) \(campo)")
                #expect(!etichetta.contains(":"), "\(passo) \(campo): «\(etichetta)», la spiegazione va sotto il campo")
                #expect(etichetta.count <= 36, "\(passo) \(campo): «\(etichetta)» è troppo lunga")
                if campo != .email { #expect(m.aiuto(campo, modo) == nil, "\(passo) \(campo): niente spiegazione sotto") }
            }
        }
    }

    @Test("Registrati con l'invito: «Email (facoltativa)» sopra e «Serve a recuperare la password.» sotto")
    func emailFacoltativa() {
        let m = registrazione(.invito)
        #expect(m.etichetta(.email, .invito) == "Email (facoltativa)")
        #expect(m.aiuto(.email, .invito) == "Serve a recuperare la password.")
    }

    @Test("Email obbligatoria per registrarsi: «Email», senza spiegazione", arguments: [ModalitaRegistrazione.email, .aperta])
    func emailObbligatoria(modo: ModalitaRegistrazione) {
        let m = registrazione(modo)
        #expect(m.etichetta(.email, modo) == "Email")
        #expect(m.aiuto(.email, modo) == nil)
    }

    @Test("Password dimenticata con l'email: «Email», senza spiegazione")
    func emailDelRecupero() {
        let m = ModuloAccesso(scheda: .recupera, metodo: .email)
        #expect(m.etichetta(.email, .invito) == "Email")
        #expect(m.aiuto(.email, .invito) == nil)
    }

    @Test("Le etichette di sempre restano uguali alla web (e ai test dell'interfaccia)")
    func etichetteDellaWeb() {
        let accesso = ModuloAccesso(scheda: .accedi)
        #expect(accesso.etichetta(.nome, .invito) == "Nome utente")
        #expect(accesso.etichetta(.password, .invito) == "Password")
        let registra = registrazione(.invito)
        #expect(registra.etichetta(.invito, .invito) == "Codice d'invito")
        #expect(registra.etichetta(.password, .invito) == "Password (almeno 10 caratteri)")
        let recupero = ModuloAccesso(scheda: .recupera, metodo: .codice)
        #expect(recupero.etichetta(.codice, .invito) == "Codice")
        #expect(recupero.etichetta(.password, .invito) == "Nuova password (almeno 10 caratteri)")
        #expect(PassoDelModulo.verificaIscrizione.modulo.etichetta(.codiceEmail, .email) == "Codice a 6 cifre ricevuto per email")
    }

    @Test("Con l'invito l'email è facoltativa, ma se c'è deve essere giusta")
    func emailFacoltativaMaGiusta() {
        var m = registrazione(.invito)
        #expect(m.pronto(.invito), "senza email si può")
        m.email = "non-una-email"
        #expect(m.problemaEmail != nil)
        #expect(!m.pronto(.invito))
        m.email = " nome@example.invalid "
        #expect(m.problemaEmail == nil)
        #expect(m.pronto(.invito))
    }
}

@Suite("Accesso: cosa legge VoiceOver dopo l'etichetta")
struct SuggerimentoCampiTests {
    @Test("Il problema di ogni campo è quello che si vede sotto il campo")
    func problemaDelCampo() {
        var m = registrazione(.invito)
        m.nome = "ab"
        m.email = "non-una-email"
        m.password = "corta"
        #expect(m.problema(.nome) != nil)
        #expect(m.problema(.nome) == m.problemaNome)
        #expect(m.problema(.email) != nil)
        #expect(m.problema(.email) == m.problemaEmail)
        #expect(m.problema(.password) != nil)
        #expect(m.problema(.password) == m.problemaPassword)
        #expect(m.problema(.invito) == nil)
        #expect(m.problema(.codice) == nil)
        #expect(m.problema(.codiceEmail) == nil)
    }

    @Test("Prima il problema, se c'è; altrimenti la spiegazione; altrimenti niente")
    func suggerimento() throws {
        var m = registrazione(.invito)
        #expect(m.suggerimento(.email, .invito) == "Serve a recuperare la password.")
        #expect(m.suggerimento(.nome, .invito) == nil)
        m.email = "non-una-email"
        let problema = try #require(m.problema(.email))
        #expect(m.suggerimento(.email, .invito) == problema)
        m.nome = "ab"
        #expect(m.suggerimento(.nome, .invito) == m.problemaNome)
    }
}

@Suite("Accesso: schede «Accedi» e «Registrati»")
struct SchedeAccessoTests {
    @Test("In fila solo se ogni etichetta sta intera nella sua metà; se no una sotto l'altra, senza parole spezzate",
          arguments: casiFila)
    @MainActor
    func inFila(caso: CasoFila) {
        #expect(FilaOColonna.inFila(larghezze: caso.larghezze, spazio: 6, disponibile: caso.disponibile) == caso.inFila)
    }
}
