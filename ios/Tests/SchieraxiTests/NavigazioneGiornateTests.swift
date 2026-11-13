import Foundation
import SwiftUI
import Testing
@testable import Schieraxi

/// La pagina Giornate è la seconda scheda della barra (#673, passo 2; la web con #671): Formazione, Giornate, Squadra, Altro. Il
/// Diario non è più una voce di Altro: i suoi indirizzi (`schieraxi://diario`, `schieraxi://lega/diario` della voce `diario` di «Da
/// fare»), quello nuovo (`schieraxi://giornate`) e «Com'è andata» della Formazione aprono Giornate.
@MainActor
struct NavigazioneGiornateTests {
    private func vai(_ testo: String) -> Destinazione? {
        URL(string: testo).flatMap { Collegamenti.interpreta($0) }
    }

    @Test("La barra ha quattro schede, in quest'ordine, con i nomi del catalogo per Formazione e Giornate")
    func barra() {
        #expect(Sezione.allCases == [.formazione, .giornate, .squadra, .altro])
        #expect(Sezione.formazione.titolo == Catalogo.Nav.formazione)
        #expect(Sezione.giornate.titolo == Catalogo.Nav.giornate)
        #expect(Sezione.allCases.map(\.scorciatoia) == ["1", "2", "3", "4"])
    }

    @Test("I nomi del Diario e di Giornate aprono Giornate", arguments: ["giornate", "Giornate", "diario"])
    func nomi(nome: String) {
        #expect(Sezione.da(nome: nome) == .giornate)
    }

    @Test("Gli indirizzi del Diario e di Giornate aprono Giornate", arguments: [
        "schieraxi://giornate", "schieraxi://diario", "schieraxi://lega/diario", "schieraxi://altro/diario", "SCHIERAXI://Lega/Diario",
    ])
    func indirizzi(indirizzo: String) {
        #expect(vai(indirizzo) == .sezione(.giornate))
    }

    @Test("Gli altri indirizzi di prima restano dove erano")
    func indirizziDiPrima() {
        #expect(vai("schieraxi://lega") == .sezione(.altro))
        #expect(vai("schieraxi://lega/regole") == .sezione(.altro))
        #expect(vai("schieraxi://oggi") == .sezione(.formazione))
        #expect(vai("schieraxi://mercato") == .sezione(.squadra))
    }

    @Test("L'ultima sezione salvata «giornate» o «diario» riapre Giornate")
    func ultimaSezione() throws {
        let memoria = try #require(UserDefaults(suiteName: "prova-giornate-\(UUID().uuidString)"))
        memoria.set("giornate", forKey: "ultimaSezione")
        #expect(Navigazione.sezioneDiAvvio(memoria) == .giornate)
    }

    @Test("«Com'è andata» apre Giornate con la giornata da aprire")
    func comeAndata() {
        // la navigazione ricorda l'ultima sezione: alla fine si rimette quella di prima
        let prima = UserDefaults.standard.string(forKey: "ultimaSezione")
        defer { UserDefaults.standard.set(prima, forKey: "ultimaSezione") }
        let nav = Navigazione()
        nav.apriGiornate(11)
        #expect(nav.sezione == .giornate)
        #expect(nav.giornataDaAprire == 11)
    }

    @Test("In Altro resta la voce delle Regole: il Diario non è più una voce di menu")
    func altroSenzaDiario() {
        #expect(VoceMenuLega.tutte(.altro).map(\.id) == ["regole"])
        #expect(!VoceMenuLega.tutte(.altro).contains { $0.id == "diario" })
    }
}
