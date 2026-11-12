import Foundation
import Testing
@testable import Schieraxi

/// Il testo in cima al Diario è quello della web: la riga sotto il titolo (`avv.diario_riga`, dalla copia ferma dei testi della
/// web `TestiWeb`) e la spiegazione (`avv.per_ogni_giornata`, dal catalogo comune dal #614) dentro la parte richiudibile
/// «Come si legge» (`mercato.come_legge`, dal catalogo comune).
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

    @Test("La spiegazione dentro «Come si legge» è quella della web e parla della consigliata mostrata")
    func spiegazioneComeLaWeb() {
        #expect(DiarioView.perOgniGiornata == Catalogo.Avv.perOgniGiornata)
        // #614: non più «quella che SchieraXI ti avrebbe consigliato… la panchina la sceglie SchieraXI in entrambi i casi»
        #expect(DiarioView.perOgniGiornata.contains("dalla consigliata che SchieraXI ti ha mostrato prima della scadenza"))
        #expect(DiarioView.perOgniGiornata.contains("quella giornata non entra nel confronto"))
        #expect(!DiarioView.perOgniGiornata.contains("in entrambi i casi"))
    }
}
