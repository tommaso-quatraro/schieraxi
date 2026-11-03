import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// Etichette dei giocatori sempre intere (issue #227). In orizzontale la colonna dei titolari della Formazione è stretta e
/// le etichette si leggevano «In dubbio · gio…» e «Probabile titol…»: la pillola si stringeva alla larghezza della riga con il
/// testo su una riga sola. Ora un'etichetta più larga della riga va a capo dentro la sua pillola: niente puntini e niente
/// testo rimpicciolito.
/// Si misura con `ImageRenderer` (come `TitoloPaginaTests`): con una larghezza proposta l'immagine ha la misura che la vista
/// si prende, e l'altezza dice su quante righe sta il testo. L'altezza di una riga la dà UIKit, non il codice che si prova.
@Suite("Etichette dei giocatori intere, anche nelle righe strette")
struct EtichetteIntereTests {

    /// Altezza di una riga di testo `.caption2` (il carattere delle etichette) alla taglia del testo data.
    private static func riga(_ categoria: UIContentSizeCategory) -> CGFloat {
        let tratti = UITraitCollection(preferredContentSizeCategory: categoria)
        return UIFont.preferredFont(forTextStyle: .caption2, compatibleWith: tratti).lineHeight
    }

    /// La misura delle pillole quando la riga è larga `larghezza` punti (nil: tutto lo spazio che vogliono).
    @MainActor
    private static func misura(_ testi: [String], larghezza: CGFloat?, taglia: DynamicTypeSize = .large) -> CGSize {
        let etichette = testi.map { Etichetta(testo: $0, gravita: .attenzione) }
        let disegno = ImageRenderer(content: PilloleEtichette(etichette: etichette).dynamicTypeSize(taglia))
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: nil)
        disegno.scale = 1
        return disegno.uiImage?.size ?? .zero
    }

    @MainActor
    @Test("In una riga stretta (Formazione in orizzontale) l'etichetta va a capo invece di finire con i puntini",
          arguments: ["In dubbio · gioca 62%", "Probabile titolare"])
    func vaACapoNellaRigaStretta(testo: String) {
        let riga = Self.riga(.large)
        let stretta = Self.misura([testo], larghezza: 90)
        #expect(riga > 0)
        #expect(stretta.height >= riga * 1.8,
                "«\(testo)» in 90 punti deve stare su due righe, non su una tagliata (alta \(stretta.height), una riga \(riga))")
        #expect(stretta.width <= 90.5, "la pillola non deve uscire dalla riga (larga \(stretta.width))")
    }

    @MainActor
    @Test("Se c'è posto l'etichetta resta su una riga, e due etichette corte stanno affiancate")
    func unaRigaSeCePosto() {
        let riga = Self.riga(.large)
        let una = Self.misura(["In dubbio · gioca 62%"], larghezza: 400)
        let due = Self.misura(["Probabile titolare", "Diffidato"], larghezza: 400)
        #expect(una.height > riga, "la pillola si vede (alta \(una.height))")
        #expect(una.height < riga * 1.5, "c'è posto: una riga sola (alta \(una.height), una riga \(riga))")
        #expect(due.height < riga * 1.5, "c'è posto: le due pillole stanno sulla stessa riga (alte \(due.height))")
    }

    @MainActor
    @Test("Con il testo grandissimo l'etichetta va a capo dentro la riga invece di tagliarsi")
    func testoGrandissimo() {
        let riga = Self.riga(.accessibilityExtraExtraExtraLarge)
        let misura = Self.misura(["In dubbio · gioca 62%"], larghezza: 300, taglia: .accessibility5)
        #expect(misura.height >= riga * 1.8, "alta \(misura.height), una riga \(riga)")
        #expect(misura.width <= 300.5, "larga \(misura.width)")
    }

    @Test("Si va a capo tra i pezzi: «gioca 62%» resta intero; un testo senza «·» resta com'è")
    func righeTraIPezzi() {
        #expect(PillolaEtichetta.righe("In dubbio · gioca 62%") == ["In dubbio ·", "gioca 62%"])
        #expect(PillolaEtichetta.righe("Probabile titolare") == ["Probabile titolare"])
    }
}
