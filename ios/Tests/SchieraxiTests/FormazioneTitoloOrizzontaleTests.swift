import SwiftUI
import Testing
@testable import Schieraxi

/// Foto `iphone_scuro_orizz_formazione` del 26/11: sull'iPhone in orizzontale, all'apertura della Formazione, «Giornata 8» e
/// «Si chiude …» restavano sfocate dietro il titolo della barra. Lì la pagina che scorre ha uno spazio in più in alto e parte
/// sotto il titolo; in verticale e sull'iPad niente. La prova vera è la foto in orizzontale: qui solo la scelta.
@MainActor
@Suite("Formazione in orizzontale: la pagina parte sotto il titolo")
struct FormazioneTitoloOrizzontaleTests {
    @Test("Spazio in più sopra la pagina solo con l'altezza compatta (iPhone in orizzontale)")
    func soloInOrizzontale() {
        #expect(FormazioneView.spazioSottoIlTitolo(verticale: .compact) > 0)
        #expect(FormazioneView.spazioSottoIlTitolo(verticale: .regular) == 0, "iPhone in verticale e iPad: come prima")
        #expect(FormazioneView.spazioSottoIlTitolo(verticale: nil) == 0)
    }
}
