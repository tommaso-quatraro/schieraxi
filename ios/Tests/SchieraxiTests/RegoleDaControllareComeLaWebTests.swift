import Foundation
import Testing
@testable import Schieraxi

// «Righe da controllare a mano» come la web (#733; `vistaRegole` in `fanta/web/app.js` dalla #734): dopo «Riconosci le regole» il
// gruppo che si apre ha il titolo `regole.da_controllare` con il numero delle righe di `da_controllare`, le righe nell'ordine in
// cui le manda il server e, sotto una riga dubbia, `regole.da_impostare` con le etichette del server separate da virgole. Con un
// server di prima, che non manda `da_controllare`, resta il gruppo di prima (`regole.non_riconosciute`). Regolamento inventato.

/// Una risposta di `POST /api/regole/riconosci` letta come la legge l'app (chiavi snake_case convertite).
private func risposta(_ json: String) throws -> RiconoscimentoRegole {
    try Decodifica.decodifica(Data(json.utf8))
}

/// Il formato del server dal 19/11/2026 (`docs/API.md`): tre righe nell'ordine del testo, due dubbie e una con numeri non letti.
private let conDaControllare = """
    {"modifiche": [{"chiave": "panchina.numero", "etichetta": "Giocatori in panchina", "valore": 7, "riga": "Panchina: 7 giocatori, non libera"}],
     "non_riconosciute": ["Media 6-6,5: +1"],
     "da_controllare": [
       {"riga": "Panchina: 7 giocatori, non libera", "regole": [{"chiave": "panchina.tipo", "etichetta": "Ordine dei cambi"}]},
       {"riga": "Non è vietato il cambio modulo", "regole": [{"chiave": "panchina.cambio_modulo", "etichetta": "Cambio modulo nelle sostituzioni"}]},
       {"riga": "Media 6-6,5: +1", "regole": []}
     ]}
    """

/// Una risposta senza righe da mostrare.
struct RispostaSenzaRighe: Sendable, CustomTestStringConvertible {
    let nome: String
    let json: String

    var testDescription: String { nome }
}

private let senzaRighe: [RispostaSenzaRighe] = [
    RispostaSenzaRighe(nome: "da_controllare vuoto", json: #"{"modifiche": [], "non_riconosciute": [], "da_controllare": []}"#),
    RispostaSenzaRighe(nome: "server di prima, non_riconosciute vuoto", json: #"{"modifiche": [], "non_riconosciute": []}"#),
    RispostaSenzaRighe(nome: "nessuno dei due campi", json: #"{"modifiche": []}"#),
]

@Suite("Regole: le righe da controllare a mano, come la web")
struct RegoleDaControllareComeLaWebTests {
    @Test("Il server manda `da_controllare`: «Righe da controllare a mano (N)» e le righe nell'ordine del server")
    func titoloERighe() throws {
        let gruppo = try #require(GruppoDaControllare(try risposta(conDaControllare)))
        #expect(gruppo.titolo == "Righe da controllare a mano (3)")
        #expect(gruppo.titolo == Catalogo.Regole.daControllare(n: "3"))
        #expect(gruppo.righe.map(\.testo) == ["Panchina: 7 giocatori, non libera", "Non è vietato il cambio modulo", "Media 6-6,5: +1"])
    }

    @Test("Sotto una riga dubbia «da impostare: <regola>»; niente sotto una riga che non nomina regole")
    func daImpostare() throws {
        let gruppo = try #require(GruppoDaControllare(try risposta(conDaControllare)))
        #expect(gruppo.righe.map(\.daImpostare) == ["da impostare: Ordine dei cambi", "da impostare: Cambio modulo nelle sostituzioni", nil])
        #expect(gruppo.righe.first?.daImpostare == Catalogo.Regole.daImpostare(r: "Ordine dei cambi"))
    }

    @Test("Più regole sotto una riga: le etichette del server separate da virgole, come la web")
    func piuRegole() throws {
        let json = """
            {"modifiche": [], "da_controllare": [{"riga": "Panchina libera e modificatore come l'anno scorso", "regole": [
              {"chiave": "panchina.tipo", "etichetta": "Ordine dei cambi"},
              {"chiave": "modificatore_difesa.attivo", "etichetta": "Modificatore difesa attivo"}]}]}
            """
        let gruppo = try #require(GruppoDaControllare(try risposta(json)))
        #expect(gruppo.titolo == "Righe da controllare a mano (1)")
        #expect(gruppo.righe.map(\.daImpostare) == ["da impostare: Ordine dei cambi, Modificatore difesa attivo"])
    }

    @Test("Server di prima, senza `da_controllare`: resta «Righe con numeri non riconosciute (N)» con le sole righe con numeri")
    func serverDiPrima() throws {
        let json = #"{"modifiche": [], "non_riconosciute": ["Media 6-6,5: +1", "Il bonus vale 3 punti, tranne in coppa"]}"#
        let gruppo = try #require(GruppoDaControllare(try risposta(json)))
        #expect(gruppo.titolo == Catalogo.Regole.nonRiconosciute(n: "2"))
        #expect(gruppo.righe.map(\.testo) == ["Media 6-6,5: +1", "Il bonus vale 3 punti, tranne in coppa"])
        #expect(gruppo.righe.allSatisfy { $0.daImpostare == nil })
    }

    @Test("Niente da controllare: il gruppo non c'è", arguments: senzaRighe)
    func senzaGruppo(caso: RispostaSenzaRighe) throws {
        #expect(GruppoDaControllare(try risposta(caso.json)) == nil)
    }
}
