import Foundation
import Testing
@testable import Schieraxi

/// Il testo in cima al Diario è quello della web: la riga sotto il titolo (`avv.diario_riga`) e la spiegazione
/// (`avv.per_ogni_giornata`), dalla copia ferma dei testi della web (`TestiWeb`), dentro la parte richiudibile «Come si legge»
/// (`mercato.come_legge`, dal catalogo comune).
@MainActor
struct DiarioIntroComeLaWebTests {

    @Test("La riga in cima al Diario è quella della web")
    func rigaComeLaWeb() throws {
        let web = try TestiWeb().italiano("avv.diario_riga")
        #expect(DiarioView.rigaIntro == web)
    }

    @Test("La parte richiudibile si chiama come sulla web")
    func titoloComeLaWeb() {
        #expect(DiarioView.comeSiLegge == Catalogo.Mercato.comeLegge)
    }

    @Test("La spiegazione dentro «Come si legge» è quella della web")
    func spiegazioneComeLaWeb() throws {
        let web = try TestiWeb().italiano("avv.per_ogni_giornata")
        #expect(DiarioView.perOgniGiornata == web)
    }
}
