import SwiftUI

/// Una riga di «Tutti i numeri»: la voce e i valori dei due giocatori, in colonne larghe 1,2 : 1 : 1 della riga, come la
/// tabella della web. Tutte le righe ricevono la stessa larghezza, quindi le colonne stanno una sotto l'altra.
/// Senza una larghezza proposta (è la misura di `ViewThatFits`) la riga dice quanto deve essere larga perché la parola più
/// lunga di ogni cella stia intera nella sua colonna (`TestoCella`): se la scheda è più stretta, al posto della tabella c'è
/// l'elenco (`NumeriInElenco`), invece di parole spezzate con il trattino o tagliate.
struct RigaTreColonne: Layout {
    var spazio: CGFloat = 10

    /// Le parti della larghezza: voce, primo giocatore, secondo giocatore.
    static let parti: [CGFloat] = [1.2, 1, 1]

    /// Le larghezze delle tre colonne in una riga larga `larghezza`.
    static func colonne(larghezza: CGFloat, spazio: CGFloat) -> [CGFloat] {
        let totale = parti.reduce(0, +)
        let utile = max(0, larghezza - spazio * CGFloat(parti.count - 1))
        return parti.map { utile * $0 / totale }
    }

    /// Quanto deve essere larga la riga perché ogni colonna sia larga almeno quanto chiede la sua cella (`minime`).
    static func larghezzaNecessaria(minime: [CGFloat], spazio: CGFloat) -> CGFloat {
        let totale = parti.reduce(0, +)
        let utile = zip(minime, parti).map { minima, parte in minima * totale / parte }.max() ?? 0
        return utile + spazio * CGFloat(parti.count - 1)
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let larghezza: CGFloat
        if let proposta = proposal.width, proposta.isFinite {
            larghezza = proposta
        } else {
            // la larghezza ideale di una `TestoCella` è quella della sua parola più lunga
            larghezza = Self.larghezzaNecessaria(minime: subviews.map { $0.sizeThatFits(.unspecified).width }, spazio: spazio)
        }
        let altezza = zip(subviews, Self.colonne(larghezza: larghezza, spazio: spazio))
            .map { pezzo, colonna in pezzo.sizeThatFits(ProposedViewSize(width: colonna, height: nil)).height }
            .max() ?? 0
        return CGSize(width: larghezza, height: altezza)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX
        for (pezzo, colonna) in zip(subviews, Self.colonne(larghezza: bounds.width, spazio: spazio)) {
            pezzo.place(at: CGPoint(x: x, y: bounds.minY), anchor: .topLeading,
                        proposal: ProposedViewSize(width: colonna, height: nil))
            x += colonna + spazio
        }
    }
}
