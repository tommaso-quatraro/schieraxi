import Foundation
import Testing
@testable import Schieraxi

/// «Chi schierare?» con le parole della web (#281): il posto in formazione è «Titolare», «Panchina 2» o «Non schierato»
/// (`testoPosto` di app.js, chiavi `mercato.posto_*` di testi.js), mai «Fuori», che è una parola della titolarità; i numeri
/// negativi delle cause hanno il meno tipografico («−1,12», `numMeno` di app.js). Dati inventati (`Tests/Fixtures`).
@Suite("Confronto come la web")
struct ConfrontoComeLaWebTests {
    // MARK: posto in formazione

    @Test("Il posto a parole, con le chiavi della web")
    func testoPosto() throws {
        let web = try TestiWeb()
        let titolare = try web.italiano("mercato.posto_titolare")
        let panchina = try web.italiano("mercato.panchina_n").replacingOccurrences(of: "{n}", with: "2")
        let fuori = try web.italiano("mercato.posto_fuori")
        #expect(SceltaDallaRosaViewModel.testoPosto("titolare") == titolare)
        #expect(SceltaDallaRosaViewModel.testoPosto("panchina 2") == panchina)
        #expect(SceltaDallaRosaViewModel.testoPosto("fuori") == fuori)
        #expect(SceltaDallaRosaViewModel.testoPosto("fuori") != "Fuori", "«Fuori» è la titolarità di chi è infortunato o squalificato")
        #expect(SceltaDallaRosaViewModel.testoPosto("") == "")
        #expect(SceltaDallaRosaViewModel.testoPosto("strano") == "")
    }

    @Test("Nella scelta del confronto: titolare, panchina e chi non è schierato")
    @MainActor
    func postoNellaScelta() async throws {
        let server = ServerDiProva { _, _, _ in try Fixture.dati("formazione") }
        let vm = SceltaDallaRosaViewModel(id: 7575, server: server)
        await vm.carica()
        try #require(vm.formazione.dato != nil)
        #expect(vm.posto(7575) == "Titolare")
        #expect(vm.posto(7481) == "Panchina 1")
        #expect(vm.posto(5678) == "Non schierato", "nella rosa ma né titolare né in panchina")
    }

    // MARK: numeri delle cause

    private static func fattore(percentuale: Bool? = nil) -> FattoreConfronto {
        FattoreConfronto(chiave: "porta", etichetta: "Porta inviolata", a: nil, b: nil, effetto: 0.3, percentuale: percentuale)
    }

    /// Il valore e come lo scrive la web (`numMeno(v, 2)`): il meno tipografico, niente «+», «0,00» senza segno, «–» se manca.
    static let valori: [(Double?, String)] = [
        (-1.12, "\u{2212}1,12"), (1.12, "1,12"), (-0.001, "0,00"), (0, "0,00"), (nil, "–"), (-0.5, "\u{2212}0,50"),
    ]

    @Test("I valori delle cause con il meno tipografico, come la web", arguments: ConfrontoComeLaWebTests.valori)
    func valoreDellaCausa(valore: Double?, atteso: String) {
        let testo = Confronto.valoreFattore(Self.fattore(), valore)
        #expect(testo == atteso)
        #expect(!testo.contains("-"), "mai il trattino al posto del meno")
    }

    @Test("Le percentuali restano percentuali")
    func percentuale() {
        #expect(Confronto.valoreFattore(Self.fattore(percentuale: true), 0.45) == "45%")
    }
}
