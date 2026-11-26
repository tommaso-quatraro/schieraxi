import SwiftUI
import Testing
@testable import Schieraxi

/// Foto `iphone_scuro_orizz_formazione` del 26/11: sull'iPhone in orizzontale, all'apertura della Formazione, «Giornata 8» e
/// «Si chiude …» restavano sfocate sotto la barra del titolo. Lì la Formazione usa il titolo piccolo, come Cerca e la scheda
/// del giocatore, che in orizzontale partono sotto la barra; in verticale e sull'iPad resta il titolo grande. La prova vera è la
/// foto in orizzontale: qui solo la scelta.
@MainActor
@Suite("Formazione in orizzontale: titolo piccolo nella barra")
struct FormazioneTitoloOrizzontaleTests {
    @Test("Titolo piccolo solo con l'altezza compatta (iPhone in orizzontale)")
    func soloInOrizzontale() {
        #expect(FormazioneView.titoloPiccolo(verticale: .compact))
        #expect(!FormazioneView.titoloPiccolo(verticale: .regular), "iPhone in verticale e iPad: il titolo grande di sempre")
        #expect(!FormazioneView.titoloPiccolo(verticale: nil))
    }
}
