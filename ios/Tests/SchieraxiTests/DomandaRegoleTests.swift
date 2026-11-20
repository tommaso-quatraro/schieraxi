import Foundation
import Testing
@testable import Schieraxi

/// Regole con modifiche non salvate (#808): una pagina aperta da fuori (dalla Formazione «Vedi la rosa», «Aggiungi la tua divisa»,
/// un file da importare) non chiude le Regole in silenzio. `LegaViewModel.apri` tiene da parte le pagine chieste e la pagina delle
/// regole chiede cosa fare: salvate o lasciate si aprono le pagine chieste, «Continua a modificare» lascia tutto com'è.
@MainActor
@Suite("Regole non salvate: si chiede prima di lasciarle (#808)")
struct DomandaRegoleTests {
    private func lega() -> LegaViewModel {
        LegaViewModel(server: ServerDiProva.chePrecipita())
    }

    @Test("Senza modifiche alle regole una pagina chiesta da fuori si apre subito")
    func senzaModifiche() {
        let vm = lega()
        vm.percorso = [.regole]
        #expect(vm.apri([.rosa("Real Fantasia")]) == .impostazioni)
        #expect(vm.percorso == [.rosa("Real Fantasia")])
        #expect(vm.pagineInAttesa == nil)
    }

    @Test("Con le regole da salvare «Vedi la rosa» non le chiude: aspetta la risposta")
    func conModificheAspetta() {
        let vm = lega()
        vm.percorso = [.regole]
        vm.regoleNonSalvate = true
        #expect(vm.apri([.rosa("Real Fantasia")]) == .impostazioni, "si va nelle Impostazioni, dove ci sono le regole")
        #expect(vm.percorso == [.regole], "le regole restano aperte, con le modifiche")
        #expect(vm.pagineInAttesa == [.rosa("Real Fantasia")])
    }

    @Test("Regole salvate o «Esci senza salvare»: si apre la pagina chiesta")
    func dopoLaRisposta() {
        let vm = lega()
        vm.percorso = [.regole]
        vm.regoleNonSalvate = true
        _ = vm.apri([.rosa("Real Fantasia")])
        vm.apriDopoLaDomanda([.rosa("Real Fantasia")])
        #expect(vm.percorso == [.rosa("Real Fantasia")])
        #expect(vm.pagineInAttesa == nil)
        #expect(!vm.regoleNonSalvate, "le regole non sono più aperte")
    }

    @Test("«Continua a modificare»: le regole restano e la pagina non si apre")
    func continuaAModificare() {
        let vm = lega()
        vm.percorso = [.regole]
        vm.regoleNonSalvate = true
        _ = vm.apri([.importa])
        vm.lasciaPagineInAttesa()
        #expect(vm.percorso == [.regole])
        #expect(vm.pagineInAttesa == nil)
        #expect(vm.regoleNonSalvate, "le modifiche ci sono ancora")
    }

    @Test("Le regole non sono tra le pagine aperte: si apre subito")
    func regoleGiaChiuse() {
        let vm = lega()
        vm.percorso = [.squadre]
        vm.regoleNonSalvate = true
        _ = vm.apri([.importa])
        #expect(vm.percorso == [.importa])
        #expect(vm.pagineInAttesa == nil)
    }
}
