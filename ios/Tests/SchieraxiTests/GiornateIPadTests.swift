import Foundation
import Testing
@testable import Schieraxi

/// Giornate sull'iPad (#896): l'elenco a sinistra e a destra la giornata scelta oppure i numeri di «Dettagli», che prima si
/// aprivano dentro la colonna stretta dell'elenco lasciando vuota la metà destra. Sul telefono non cambia niente: «Dettagli» si
/// apre sotto la sua riga. Dati inventati (`diario-giornate.json`).
@MainActor
@Suite("Giornate sull'iPad: a destra la giornata scelta o i Dettagli")
struct GiornateIPadTests {
    private func pagina() throws -> PaginaGiornate {
        PaginaGiornate(try Fixture.decodifica("diario-giornate") as DiarioRisposta)
    }

    @Test("Senza una scelta a destra c'è la giornata più recente")
    func piuRecente() throws {
        let p = try pagina()
        let prima = try #require(p.righe.first?.id)
        #expect(p.aDestra(scelta: nil) == .giornata(prima))
        #expect(p.aDestra(scelta: nil).id == prima)
    }

    @Test("La giornata toccata va a destra; una che non c'è più lascia il posto alla più recente")
    func giornataScelta() throws {
        let p = try pagina()
        let ultima = try #require(p.righe.last?.id)
        #expect(p.aDestra(scelta: ultima) == .giornata(ultima))
        let prima = try #require(p.righe.first?.id)
        #expect(p.aDestra(scelta: "2019-20-1") == .giornata(prima))
    }

    @Test("«Dettagli» toccato: a destra i numeri, e nell'elenco è la sua riga a risultare scelta")
    func dettagli() throws {
        let p = try pagina()
        #expect(p.dettagli != nil)
        #expect(p.aDestra(scelta: PaginaGiornate.idDettagli) == .dettagli)
        #expect(p.aDestra(scelta: PaginaGiornate.idDettagli).id == PaginaGiornate.idDettagli)
    }

    @Test("L'identità di «Dettagli» non può essere quella di una giornata")
    func idDettagliDiverso() throws {
        let p = try pagina()
        #expect(!p.righe.contains { $0.id == PaginaGiornate.idDettagli })
    }

    @Test("Senza i numeri di «Dettagli» a destra resta la giornata più recente; senza giornate niente")
    func senzaDettagli() throws {
        let senza = PaginaGiornate(try Decodifica.decodifica(Data(#"{"giornate": []}"#.utf8)))
        #expect(senza.aDestra(scelta: PaginaGiornate.idDettagli) == .niente)
        #expect(senza.aDestra(scelta: nil) == .niente)
        #expect(senza.aDestra(scelta: nil).id == nil)
        let soloDettagli = PaginaGiornate(try Decodifica.decodifica(
            Data(#"{"giornate": [], "precisione": {"giornate": 2, "fantavoto": null}}"#.utf8)))
        #expect(soloDettagli.aDestra(scelta: nil) == .dettagli, "senza giornate ma con i Dettagli: a destra i Dettagli")
    }

    @Test("La foto `giornate-dettagli` apre i Dettagli anche a destra; «Com'è andata» porta poi a destra la sua giornata")
    func fotoEPoiComeAndata() async throws {
        let json = try Fixture.testo("diario-giornate")
        let vm = GiornateViewModel(server: ServerDiProva { _, _, _ in Data(json.utf8) })
        vm.preparaFoto("giornate-dettagli")
        #expect(vm.dettagliAperti, "sul telefono «Dettagli» aperto sotto la sua riga, come prima")
        #expect(vm.scelta == PaginaGiornate.idDettagli)
        await vm.carica()
        #expect(vm.pagina?.aDestra(scelta: vm.scelta) == .dettagli)
        vm.apri(giornata: 9)
        #expect(vm.scelta == "2026-27-9")
        #expect(vm.pagina?.aDestra(scelta: vm.scelta) == .giornata("2026-27-9"))
    }
}
