import SwiftUI

/// Pulsanti larghi uguali in fila; se anche una sola etichetta non ci sta intera nella sua parte, tutti uno sotto l'altro,
/// larghi quanto la riga. Così una parola non va mai a capo con il trattino («Regi-strati» con il testo massimo, issue #191).
/// `ViewThatFits` non basta: misura la fila intera, e la fila può starci anche quando una delle due metà è troppo stretta.
struct FilaOColonna: Layout {
    var spazio: CGFloat = 6

    /// In fila se l'etichetta più larga sta nella parte che tocca a ciascuno. Senza una larghezza proposta: in fila.
    static func inFila(larghezze: [CGFloat], spazio: CGFloat, disponibile: CGFloat?) -> Bool {
        guard let disponibile, let piuLarga = larghezze.max() else { return true }
        let quanti = CGFloat(larghezze.count)
        return piuLarga <= (disponibile - spazio * (quanti - 1)) / quanti
    }

    private func larghezzeIdeali(_ pezzi: Subviews) -> [CGFloat] {
        pezzi.map { $0.sizeThatFits(.unspecified).width }
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard !subviews.isEmpty else { return .zero }
        let ideali = larghezzeIdeali(subviews)
        let quanti = CGFloat(subviews.count)
        if Self.inFila(larghezze: ideali, spazio: spazio, disponibile: proposal.width) {
            let larghezza = proposal.width ?? ((ideali.max() ?? 0) * quanti + spazio * (quanti - 1))
            let parte = (larghezza - spazio * (quanti - 1)) / quanti
            let altezza = subviews.map { $0.sizeThatFits(ProposedViewSize(width: parte, height: nil)).height }.max() ?? 0
            return CGSize(width: larghezza, height: altezza)
        }
        let larghezza = proposal.width ?? (ideali.max() ?? 0)
        let altezze = subviews.map { $0.sizeThatFits(ProposedViewSize(width: larghezza, height: nil)).height }
        return CGSize(width: larghezza, height: altezze.reduce(0, +) + spazio * (quanti - 1))
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard !subviews.isEmpty else { return }
        let quanti = CGFloat(subviews.count)
        if Self.inFila(larghezze: larghezzeIdeali(subviews), spazio: spazio, disponibile: bounds.width) {
            let parte = (bounds.width - spazio * (quanti - 1)) / quanti
            var x = bounds.minX
            for pezzo in subviews {
                pezzo.place(at: CGPoint(x: x, y: bounds.minY), anchor: .topLeading,
                            proposal: ProposedViewSize(width: parte, height: bounds.height))
                x += parte + spazio
            }
        } else {
            var y = bounds.minY
            for pezzo in subviews {
                let altezza = pezzo.sizeThatFits(ProposedViewSize(width: bounds.width, height: nil)).height
                pezzo.place(at: CGPoint(x: bounds.minX, y: y), anchor: .topLeading,
                            proposal: ProposedViewSize(width: bounds.width, height: altezza))
                y += altezza + spazio
            }
        }
    }
}
