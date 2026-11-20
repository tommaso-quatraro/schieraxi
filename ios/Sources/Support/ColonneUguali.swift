import SwiftUI

/// Una colonna per ogni vista, tutte della stessa larghezza e allineate in alto, nell'ordine in cui sono scritte (anche per
/// VoiceOver). Ogni colonna si misura una volta sola, con la larghezza che le tocca.
/// Al posto di un `HStack` per le due colonne della Formazione sull'iPad (#846): prima di dividere lo spazio l'`HStack` chiede a
/// ogni colonna anche quanto può stringersi e allargarsi (larghezza 0 e infinita), e con le pedine del campo e le righe dei
/// giocatori (testi che vanno a capo, `ViewThatFits`) la prima disposizione teneva fermo il thread principale per secondi: lo
/// schermo restava sullo scheletro del caricamento anche con i dati già arrivati.
struct ColonneUguali: Layout {
    var spazio: CGFloat

    /// La larghezza di ogni colonna in una larghezza totale data.
    static func larghezzaColonna(totale: CGFloat, colonne: Int, spazio: CGFloat) -> CGFloat {
        guard colonne > 0 else { return 0 }
        return max(0, (totale - spazio * CGFloat(colonne - 1)) / CGFloat(colonne))
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard !subviews.isEmpty else { return .zero }
        let colonne = CGFloat(subviews.count)
        guard let totale = proposal.width, totale.isFinite else {
            // senza una larghezza (misura ideale): ogni colonna larga quanto vuole la più larga
            let ideali = subviews.map { $0.sizeThatFits(.unspecified) }
            let larga = ideali.map(\.width).max() ?? 0
            return CGSize(width: larga * colonne + spazio * (colonne - 1), height: ideali.map(\.height).max() ?? 0)
        }
        let parte = Self.larghezzaColonna(totale: totale, colonne: subviews.count, spazio: spazio)
        let altezza = subviews.map { $0.sizeThatFits(ProposedViewSize(width: parte, height: nil)).height }.max() ?? 0
        return CGSize(width: totale, height: altezza)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let parte = Self.larghezzaColonna(totale: bounds.width, colonne: subviews.count, spazio: spazio)
        var x = bounds.minX
        for colonna in subviews {
            colonna.place(at: CGPoint(x: x, y: bounds.minY), anchor: .topLeading, proposal: ProposedViewSize(width: parte, height: nil))
            x += parte + spazio
        }
    }
}
