import SwiftUI

/// Pillole una dopo l'altra, a capo quando la riga è piena (come le etichette della web).
/// Una pillola più larga di tutta la riga riceve la larghezza della riga e va a capo dentro di sé, diventando più alta.
/// Prima si stringeva alla riga con il testo su una riga sola e finiva con i puntini («In dubbio · gio…», issue #227).
struct FilaPillole: Layout {
    var spazio: CGFloat = 4

    /// Per ogni pillola: la proposta con cui misurarla e posarla, e la sua misura.
    private struct Disposizione {
        var larghezza: CGFloat = 0
        var proposte: [ProposedViewSize] = []
        var misure: [CGSize] = []
    }

    /// Le pillole in una riga larga `proposta` (nil: tutta la larghezza che vogliono). Chi ci sta ha la sua misura naturale;
    /// chi è più larga della riga riceve tutta la riga (e va a capo dentro di sé). La stessa proposta serve per posarla.
    private func disponi(_ subviews: Subviews, larghezza proposta: CGFloat?) -> Disposizione {
        let naturali = subviews.map { $0.sizeThatFits(.unspecified) }
        var d = Disposizione()
        d.larghezza = proposta ?? naturali.reduce(CGFloat(0)) { $0 + $1.width + spazio }
        for (sub, naturale) in zip(subviews, naturali) {
            if naturale.width <= d.larghezza {
                d.proposte.append(.unspecified)
                d.misure.append(naturale)
            } else {
                let stretta = ProposedViewSize(width: d.larghezza, height: nil)
                let misura = sub.sizeThatFits(stretta)
                d.proposte.append(stretta)
                d.misure.append(CGSize(width: min(misura.width, d.larghezza), height: misura.height))
            }
        }
        return d
    }

    private func righe(_ larghezza: CGFloat, _ misure: [CGSize]) -> [[Int]] {
        var risultato: [[Int]] = [[]]
        var x: CGFloat = 0
        for (i, m) in misure.enumerated() {
            if x > 0, x + m.width > larghezza {
                risultato.append([])
                x = 0
            }
            risultato[risultato.count - 1].append(i)
            x += m.width + spazio
        }
        return risultato
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let d = disponi(subviews, larghezza: proposal.width)
        var altezza: CGFloat = 0
        var massima: CGFloat = 0
        for riga in righe(d.larghezza, d.misure) {
            let alta = riga.map { d.misure[$0].height }.max() ?? 0
            altezza += alta + (altezza > 0 ? spazio : 0)
            let lunga = riga.reduce(CGFloat(0)) { $0 + d.misure[$1].width } + spazio * CGFloat(max(0, riga.count - 1))
            massima = max(massima, lunga)
        }
        return CGSize(width: min(massima, d.larghezza), height: altezza)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let d = disponi(subviews, larghezza: bounds.width)
        var y = bounds.minY
        for riga in righe(bounds.width, d.misure) {
            var x = bounds.minX
            let alta = riga.map { d.misure[$0].height }.max() ?? 0
            for i in riga {
                subviews[i].place(at: CGPoint(x: x, y: y), proposal: d.proposte[i])
                x += d.misure[i].width + spazio
            }
            y += alta + spazio
        }
    }
}
