import SwiftUI

/// Mostra la prima forma che entra, dalla più lunga alla più corta (al più sei): i widget hanno misure fisse, e così dove non c'è
/// spazio il testo perde parole intere invece di finire con «…». Le forme le decide `ParoleWidget` (provato dai test); qui si sceglie
/// solo quale entra, misurando. Se non ne entra nessuna resta l'ultima.
/// Si preparano solo le forme che ci sono (prima erano sempre sei, con l'ultima ripetuta): la scelta è la stessa, ma un
/// `PrimaCheEntra` dentro un altro (Cruscotto) non moltiplica le copie da misurare.
struct PrimaCheEntra<Contenuto: View>: View {
    private let ultima: Int
    private let assi: Axis.Set
    private let forma: (Int) -> Contenuto

    /// `forme`: quante forme ci sono; `forma(i)` disegna la forma `i` (0 = la più lunga), sempre con `i` tra 0 e `forme - 1`.
    init(_ forme: Int, in assi: Axis.Set = .horizontal, @ViewBuilder forma: @escaping (Int) -> Contenuto) {
        self.ultima = min(max(forme, 1), 6) - 1
        self.assi = assi
        self.forma = forma
    }

    var body: some View {
        switch ultima {
        case 0:
            ViewThatFits(in: assi) { forma(0) }
        case 1:
            ViewThatFits(in: assi) { forma(0); forma(1) }
        case 2:
            ViewThatFits(in: assi) { forma(0); forma(1); forma(2) }
        case 3:
            ViewThatFits(in: assi) { forma(0); forma(1); forma(2); forma(3) }
        case 4:
            ViewThatFits(in: assi) { forma(0); forma(1); forma(2); forma(3); forma(4) }
        default:
            ViewThatFits(in: assi) { forma(0); forma(1); forma(2); forma(3); forma(4); forma(5) }
        }
    }
}
