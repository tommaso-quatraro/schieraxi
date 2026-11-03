import Foundation
import Testing
@testable import Schieraxi

// Issue #173. Il 401 di nome o password sbagliati ha solo `detail` (`errore_account` del server). Prima l'app rileggeva da quel
// corpo il modo di registrazione e, non trovandolo, tornava a «invito» (e spegneva «Continua con Google»): dopo una password
// sbagliata la scheda Registrati chiedeva l'invito anche su un server aperto. Come la web (`api()` in `fanta/web/app.js`): da un
// 401 si ricorda solo ciò che il corpo contiene davvero. Ogni test usa UserDefaults suoi: girano in parallelo senza toccarsi.

/// Il corpo del 401 di nome o password sbagliati: solo il messaggio.
private let passwordSbagliata = Data(#"{"detail": "Nome utente o password non corretti"}"#.utf8)

/// Il corpo del 401 «Accesso richiesto», con tutto quello che il server dichiara.
private func accessoRichiesto(_ modo: ModalitaRegistrazione, social: String = #"["google"]"#, posta: Bool = true) -> Data {
    Data(#"{"detail": "Accesso richiesto", "multiutente": true, "registrazione": "\#(modo.rawValue)", "social": \#(social), "email_attiva": \#(posta)}"#.utf8)
}

/// UserDefaults solo per un test, cancellati alla fine.
private func conMemoria(_ prova: (UserDefaults) throws -> Void) throws {
    let nome = "prova-401-\(UUID().uuidString)"
    let memoria = try #require(UserDefaults(suiteName: nome))
    defer { memoria.removePersistentDomain(forName: nome) }
    try prova(memoria)
}

@Suite("Accesso: un 401 cambia solo ciò che dice (#173)")
struct PasswordSbagliataTests {
    @Test("Una password sbagliata lascia il modo di registrazione com'era",
          arguments: [ModalitaRegistrazione.invito, .email, .aperta])
    func modoRestaUguale(modo: ModalitaRegistrazione) throws {
        try conMemoria { memoria in
            ServerHTTP.ricordaDal401(accessoRichiesto(modo), in: memoria)
            #expect(ModalitaRegistrazione.ricordato(in: memoria) == modo)
            ServerHTTP.ricordaDal401(passwordSbagliata, in: memoria)
            #expect(ModalitaRegistrazione.ricordato(in: memoria) == modo)
        }
    }

    @Test("Una password sbagliata non spegne Google e non riaccende la posta")
    func googleEPostaRestano() throws {
        try conMemoria { memoria in
            ServerHTTP.ricordaDal401(accessoRichiesto(.aperta, posta: false), in: memoria)
            ServerHTTP.ricordaDal401(passwordSbagliata, in: memoria)
            #expect(ServiziSociali.googleAcceso(in: memoria))
            #expect(!PostaServer.accesa(in: memoria))
        }
    }

    @Test("Dopo una password sbagliata la scheda Registrati di un server aperto chiede nome, email e password, senza invito")
    func registratiConICampiGiusti() throws {
        try conMemoria { memoria in
            ServerHTTP.ricordaDal401(accessoRichiesto(.aperta), in: memoria)
            ServerHTTP.ricordaDal401(passwordSbagliata, in: memoria)
            let modulo = ModuloAccesso(scheda: .registrati)
            let campi = modulo.campi(ModalitaRegistrazione.ricordato(in: memoria), postaAccesa: PostaServer.accesa(in: memoria))
            #expect(campi == [.nome, .email, .password])
        }
    }

    @Test("Il 401 «Accesso richiesto» aggiorna tutto quello che dichiara")
    func accessoRichiestoAggiornaTutto() throws {
        try conMemoria { memoria in
            ServerHTTP.ricordaDal401(accessoRichiesto(.email, social: "[]", posta: true), in: memoria)
            #expect(ModalitaRegistrazione.ricordato(in: memoria) == .email)
            #expect(!ServiziSociali.googleAcceso(in: memoria), "un elenco vuoto vuol dire: Google spento sul server")
            #expect(PostaServer.accesa(in: memoria))
            ServerHTTP.ricordaDal401(accessoRichiesto(.aperta, posta: false), in: memoria)
            #expect(ModalitaRegistrazione.ricordato(in: memoria) == .aperta)
            #expect(ServiziSociali.googleAcceso(in: memoria))
            #expect(!PostaServer.accesa(in: memoria))
        }
    }

    @Test("Mai saputo: registrazione con l'invito, come sempre")
    func maiSaputo() throws {
        try conMemoria { memoria in
            #expect(ModalitaRegistrazione.ricordato(in: memoria) == .invito)
        }
    }
}

/// Corpi con il campo `registrazione` e il modo che se ne legge (nil = il corpo non lo dice).
private let corpiModo: [(String, ModalitaRegistrazione?)] = [
    (#"{"detail": "Accesso richiesto", "registrazione": "email"}"#, .email),
    (#"{"registrazione": "aperta"}"#, .aperta),
    (#"{"registrazione": "invito"}"#, .invito),
    (#"{"registrazione": "boh"}"#, .invito),       // detto ma sconosciuto: invito, come prima
    (#"{"detail": "Nome utente o password non corretti"}"#, nil),
    (#"{"registrazione": ""}"#, nil),             // come la web: un testo vuoto non conta
    (#"{"registrazione": 5}"#, nil),
    ("<html><body>Wi-Fi</body></html>", nil),
    ("[]", nil),
]

/// Corpi con il campo `social` e l'elenco che se ne legge (nil = il corpo non lo dice).
private let corpiSocial: [(String, [String]?)] = [
    (#"{"social": ["google"]}"#, ["google"]),
    (#"{"social": []}"#, []),
    (#"{"detail": "Nome utente o password non corretti"}"#, nil),
    (#"{"social": "google"}"#, nil),              // come la web: conta solo un elenco
    ("<html><body>Wi-Fi</body></html>", nil),
]

@Suite("Accesso: i campi del 401 si leggono solo se ci sono")
struct CampiDel401Tests {
    @Test("Il modo di registrazione", arguments: corpiModo)
    func modo(corpo: String, atteso: ModalitaRegistrazione?) {
        #expect(ModalitaRegistrazione.letto(corpo: Data(corpo.utf8)) == atteso)
    }

    @Test("I servizi di accesso (Google)", arguments: corpiSocial)
    func social(corpo: String, atteso: [String]?) {
        #expect(ServiziSociali.letti(corpo: Data(corpo.utf8)) == atteso)
    }
}
