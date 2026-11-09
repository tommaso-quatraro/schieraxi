import Foundation
import Testing
@testable import Schieraxi

/// Seguiti come la web (issue #441, parte di #167). Le tre frasi vengono dal catalogo comune (#496; vocabolario «Giocatori
/// seguiti» di `docs/COERENZA-WEB-IPHONE.md`): dopo «Segui» la scheda dice «Lo segui: ti avviso se cambia qualcosa», dopo il
/// secondo tocco «Non lo segui più», e la pagina senza seguiti dice solo «Nessun giocatore seguito.», senza una riga in più.
@MainActor
@Suite("Seguiti come la web: le frasi della scheda e della pagina vuota (#441)")
struct SeguitiComeLaWebTests {

    @Test("Le tre frasi sono quelle del catalogo")
    func frasi() {
        #expect(ParoleSeguiti.loSegui == Catalogo.Mercato.osserviAvviso)
        #expect(ParoleSeguiti.nonLoSeguiPiu == Catalogo.Mercato.nonOsservi)
        #expect(ParoleSeguiti.nessunGiocatore == Catalogo.Mercato.nessunGiocatoreOsservato)
    }

    @Test("La frase non manda a cercare i Seguiti in un altro posto: niente «Squadra >» e niente invito a toccare «Segui»")
    func senzaIndicazioniInPiu() {
        #expect(!ParoleSeguiti.loSegui.contains(">"))
        #expect(!ParoleSeguiti.nessunGiocatore.contains("Segui"))
    }

    @Test("Dalla scheda: «Segui» e poi di nuovo il tocco danno le frasi della web")
    func dallaScheda() async throws {
        let server = ServerDiProva.conFixture(["/api/giocatore/": "giocatore", "/api/calendario": "calendario",
                                               "/api/osservati": "osservati", "/api/formazione": "formazione"])
        let vm = SchedaGiocatoreViewModel(id: 5585, server: server)
        await vm.carica()
        #expect(vm.osservato == false)
        await vm.alternaOsservato()
        #expect(vm.osservato == true)
        #expect(vm.messaggio == Catalogo.Mercato.osserviAvviso)
        await vm.alternaOsservato()
        #expect(vm.osservato == false)
        #expect(vm.messaggio == Catalogo.Mercato.nonOsservi)
    }
}
