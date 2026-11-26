import Foundation
import Testing
@testable import Schieraxi

// «La mia squadra» non ancora scelta (#923, revisione della #945): il selettore parte da «Scegli una squadra», con lo stesso testo
// del catalogo della web (`lega.scegli_squadra`, `sceltaMiaSquadra(squadre, true)` di app.js), invece di una riga vuota. Scelta la
// squadra la voce non c'è più. Nomi inventati.

@MainActor
@Suite("La mia squadra: il selettore parte da «Scegli una squadra», come la web")
struct SelettoreMiaSquadraTests {
    @Test("Finché la mia non è scelta la voce vuota è «Scegli una squadra», il testo della web")
    func segnaposto() {
        #expect(SelettoreMiaSquadra.segnaposto(mia: "") == Catalogo.Lega.scegliSquadra)
        #expect(Catalogo.Lega.scegliSquadra == "Scegli una squadra")
    }

    @Test("Con la mia squadra scelta la voce vuota non c'è")
    func senzaSegnaposto() {
        #expect(SelettoreMiaSquadra.segnaposto(mia: "Squadra Demo") == nil)
    }
}
