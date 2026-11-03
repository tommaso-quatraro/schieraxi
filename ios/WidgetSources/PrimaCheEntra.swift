import SwiftUI

/// Mostra la prima forma che entra, dalla più lunga alla più corta (al più sei): i widget hanno misure fisse, e così dove non c'è
/// spazio il testo perde parole intere invece di finire con «…». Le forme le decide `ParoleWidget` (provato dai test); qui si sceglie
/// solo quale entra, misurando. Se non ne entra nessuna resta l'ultima.
struct PrimaCheEntra<Contenuto: View>: View {
    private let ultima: Int
    private let assi: Axis.Set
    private let forma: (Int) -> Contenuto

    /// `forme`: quante forme ci sono; `forma(i)` disegna la forma `i` (0 = la più lunga), sempre con `i` tra 0 e `forme - 1`.
    init(_ forme: Int, in assi: Axis.Set = .horizontal, @ViewBuilder forma: @escaping (Int) -> Contenuto) {
        self.ultima = max(forme, 1) - 1
        self.assi = assi
        self.forma = forma
    }

    var body: some View {
        ViewThatFits(in: assi) {
            forma(0)
            forma(min(1, ultima))
            forma(min(2, ultima))
            forma(min(3, ultima))
            forma(min(4, ultima))
            forma(min(5, ultima))
        }
    }
}
