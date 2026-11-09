import Foundation
import Testing
import UIKit
@testable import Schieraxi

/// Frasi di Nuova stagione e di Avvisi uguali alla web (`fanta/web/testi.js`) e al vocabolario comune
/// (`docs/COERENZA-WEB-IPHONE.md`): «seguiti», mai «osservati»; niente parole inglesi come «background».
@Suite("Parole come la web")
@MainActor
struct ParoleComeLaWebTests {
    @Test("Nuova stagione: la frase della web (`lega.rose_ancora_quelle`), con «seguiti»")
    func roseAncoraQuelle() throws {
        let web = Catalogo.Lega.roseAncoraQuelle(s: "2025-26")
        #expect(StagioneView.testoRoseAncoraQuelle("2025-26") == web)
        #expect(StagioneView.testoRoseAncoraQuelle("2025-26").contains("scelte e seguiti"))
    }

    @Test("Nuova stagione: nessuna frase dice «osservati»")
    func maiOsservati() {
        let testi = [StagioneView.testoRoseAncoraQuelle("2025-26"), StagioneView.testoArchivioConferma]
        #expect(testi.allSatisfy { !$0.localizedCaseInsensitiveContains("osservat") })
        #expect(StagioneView.testoArchivioConferma.contains("seguiti"))
    }

    @Test("Ore tranquille spente dal server: la frase della web (`avv.avevi_scelto_ore`)")
    func oreTranquilleSpente() throws {
        let web = try TestiWeb().italiano("avv.avevi_scelto_ore")
        #expect(AvvisiServerView.testoOreTranquilleSpente == web)
    }

    @Test("La riga dei controlli con l'app chiusa è in italiano")
    func controlliConAppChiusa() {
        #expect(!LegaViewModel.titoloControlli.localizedCaseInsensitiveContains("background"))
        #expect(LegaViewModel.titoloControlli == "Controllo con l'app chiusa")
    }

    @Test("Lo stato dei controlli dice cosa fare se sono spenti")
    func statoControlli() {
        #expect(LegaViewModel.statoControlli(.available) == "attivo")
        #expect(LegaViewModel.statoControlli(.denied) == "disattivato (Impostazioni di iOS)")
        #expect(LegaViewModel.statoControlli(.restricted) == "limitato")
    }
}
