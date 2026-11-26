import SwiftUI

/// Giornate sull'iPad (#896), come la web larga (`.gn` da 768 px): l'elenco a sinistra, largo metà dello spazio e al massimo 420
/// punti, e a destra, nel resto, la giornata scelta. Due viste, nell'ordine in cui sono scritte (anche per VoiceOver), ognuna
/// alta quanto la pagina e con il suo scorrimento. Prima era una `NavigationSplitView` dentro la barra laterale: elenco stretto
/// (titoli su due righe) e, in orizzontale, tre colonne con due pulsanti uguali per la barra.
struct ElencoEDettaglio: Layout {
    /// L'elenco non supera questa larghezza (la colonna di sinistra della web da 1024 px).
    static let elencoMassimo: CGFloat = 420
    /// La giornata a destra non supera questa larghezza (la colonna di destra della web da 1024 px).
    static let dettaglioMassimo: CGFloat = 620

    /// La larghezza dell'elenco in uno spazio largo `totale`: metà, al massimo `elencoMassimo`.
    static func larghezzaElenco(totale: CGFloat) -> CGFloat {
        guard totale.isFinite, totale > 0 else { return 0 }
        return min(elencoMassimo, (totale / 2).rounded(.down))
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        proposal.replacingUnspecifiedDimensions()
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let sinistra = Self.larghezzaElenco(totale: bounds.width)
        var x = bounds.minX
        for (i, vista) in subviews.enumerated() {
            let larghezza = i == 0 ? sinistra : max(0, bounds.maxX - x)
            vista.place(at: CGPoint(x: x, y: bounds.minY), anchor: .topLeading,
                        proposal: ProposedViewSize(width: larghezza, height: bounds.height))
            x += larghezza
        }
    }
}
