import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// I pallini della password senza «…» con il testo grande (issue #857, punto 1). Nella foto
/// `iphone_chiaro_testomassimo_accesso-rete` (corse 44816547478 e quella della #837) la password di 20 caratteri della prova si
/// vedeva come otto pallini e «…»: la casella della password sta su una riga sola e, quando non ci si scrive, iOS taglia con i
/// puntini quello che non ci sta. Con il testo massimo ogni pallino è largo circa 32 punti. Ora i pallini crescono con il testo
/// fino a `CampoAccesso.tettoPallini` (l'ultima misura prima di quelle per l'accessibilità) e non oltre; l'etichetta sopra la
/// casella resta grande.
/// Si misura con UIKit (il carattere della casella, `.body`, alla misura data), non con `ImageRenderer`, che una casella di
/// UIKit non la disegna. I pallini sono «●», quelli che iOS disegna al posto dei caratteri.
@Suite("Pallini della password interi con il testo grande")
struct PalliniPasswordTests {

    /// Lo spazio per il testo nella casella sull'iPhone più stretto (375 punti di larghezza): margine della pagina
    /// (`Tema.margine`, a destra e a sinistra), margine interno della carta (12) e della casella (12).
    private static let larghezzaCasella: CGFloat = 375 - 2 * Tema.margine - 2 * 12 - 2 * 12

    /// Lunga quanto la password forte che propone iOS e quanto quella della prova nelle foto.
    private static let caratteri = 20

    /// Quanto sono larghi `caratteri` pallini nel carattere della casella alla misura del testo data.
    private static func larghezzaPallini(_ taglia: DynamicTypeSize) -> CGFloat {
        let tratti = UITraitCollection(preferredContentSizeCategory: UIContentSizeCategory(taglia))
        let carattere = UIFont.preferredFont(forTextStyle: .body, compatibleWith: tratti)
        let pallini = String(repeating: "●", count: caratteri) as NSString
        return pallini.size(withAttributes: [.font: carattere]).width
    }

    @MainActor
    @Test("Una password di 20 caratteri sta intera nella casella dell'iPhone più stretto, con ogni misura del testo",
          arguments: DynamicTypeSize.allCases)
    func staNellaCasella(taglia: DynamicTypeSize) {
        let usata = min(taglia, CampoAccesso.tettoPallini)
        let larghezza = Self.larghezzaPallini(usata)
        #expect(larghezza > 0)
        #expect(larghezza <= Self.larghezzaCasella,
                "con la misura \(taglia) i pallini (misura \(usata)) sono larghi \(larghezza) punti, la casella \(Self.larghezzaCasella): finirebbero con «…»")
    }

    @MainActor
    @Test("Con le misure normali del testo (fino a XXXL) i pallini crescono come il testo")
    func cresconoConLeMisureNormali() {
        #expect(CampoAccesso.tettoPallini >= .xxxLarge)
    }

    @MainActor
    @Test("Senza il tetto, con il testo massimo, i pallini non ci starebbero (la foto dell'issue #857)")
    func senzaTettoNonCiStanno() {
        let larghezza = Self.larghezzaPallini(.accessibility5)
        #expect(larghezza > Self.larghezzaCasella,
                "con il testo massimo 20 pallini sono larghi \(larghezza) punti, la casella \(Self.larghezzaCasella)")
    }
}
