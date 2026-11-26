import Foundation
import Testing
@testable import Schieraxi

// Regole e scadenza (#923): con il testo al massimo il nome della lega si leggeva «Lega degli a…», perché il campo stava su una
// riga sola. Ora il campo va a capo; il nome però resta una riga: un a capo arrivato con «Invio» o con un testo incollato si toglie,
// e l'«Invio» da solo non conta come modifica. Nomi inventati.

@Suite("Regole: il nome della lega va a capo ma resta una riga")
struct NomeLegaUnaRigaTests {
    /// Revisione della #945: «Invio» a metà del nome, dopo o prima di uno spazio, lasciava due spazi («Lega  degli amici»).
    @Test("Gli a capo diventano uno spazio solo, quelli in fondo si tolgono; senza a capo il testo non cambia", arguments: [
        ("Lega degli amici", "Lega degli amici"),
        ("Lega degli amici\n", "Lega degli amici"),
        ("Lega degli amici \n", "Lega degli amici"),
        ("Lega degli\namici", "Lega degli amici"),
        ("Lega degli \namici", "Lega degli amici"),
        ("Lega degli\n amici", "Lega degli amici"),
        ("Lega degli \n amici", "Lega degli amici"),
        ("Lega\r\n\ndegli amici", "Lega degli amici"),
        ("Lega ", "Lega "),
        ("\n", ""),
        ("", ""),
    ])
    func suUnaRiga(scritto: String, atteso: String) {
        #expect(RegoleLogica.suUnaRiga(scritto) == atteso)
    }

    @MainActor
    @Test("«Invio» senza cambiare il nome non è una modifica da salvare; un nome nuovo sì")
    func invioNonModifica() async throws {
        let vm = RegoleEditorViewModel(server: ServerDiProva.conFixture(["/api/regole": "regole"]))
        await vm.carica()
        let nome = vm.nomeLega.wrappedValue
        #expect(!vm.modificato)
        vm.nomeLega.wrappedValue = nome + "\n"                 // «Invio» in fondo: la vista poi lo toglie
        vm.nomeLega.wrappedValue = RegoleLogica.suUnaRiga(vm.nomeLega.wrappedValue)
        #expect(vm.nomeLega.wrappedValue == nome)
        #expect(!vm.modificato, "l'«Invio» da solo non cambia il nome")
        vm.nomeLega.wrappedValue = nome + " nuova"
        #expect(vm.modificato)
    }
}
