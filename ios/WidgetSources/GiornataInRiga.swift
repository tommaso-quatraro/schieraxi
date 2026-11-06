import SwiftUI

/// La giornata in una riga di un widget (#299): la prima forma che entra, dalla più lunga («Giornata 8 · 11ª di Serie A») alla
/// più corta («Giornata 8»), mai «G8». Con il simbolo, se c'è. VoiceOver legge sempre i due numeri («Giornata 8, 11ª di Serie
/// A»). Le forme vengono da `ParoleWidget.formeGiornata`, provate dai test; dove anche «Giornata 8» può non entrare, chi la usa
/// aggiunge `minimumScaleFactor`.
struct GiornataInRiga: View {
    private let forme: [String]
    private let voce: String
    private let simbolo: String?

    init(forme: [String], voce: String, simbolo: String? = nil) {
        self.forme = forme.isEmpty ? [voce] : forme
        self.voce = voce
        self.simbolo = simbolo
    }

    /// `soloCorta`: per i widget piccoli, senza la forma intera (solo «Giornata 8»).
    init(_ nome: NomeGiornata, soloCorta: Bool = false, simbolo: String? = nil) {
        self.init(forme: soloCorta ? [nome.corto] : ParoleWidget.formeGiornata(nome), voce: nome.voce, simbolo: simbolo)
    }

    var body: some View {
        PrimaCheEntra(forme.count) { i in
            if let simbolo {
                Label(forme[i], systemImage: simbolo).lineLimit(1)
            } else {
                Text(forme[i]).lineLimit(1)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(voce)
    }
}
