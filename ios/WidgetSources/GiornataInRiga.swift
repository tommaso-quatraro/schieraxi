import SwiftUI

/// La giornata in una riga di un widget (#299): la prima forma che entra, dalla più lunga («Giornata 8 · 11ª di Serie A») alla
/// più corta («Giornata 8», poi «G8»), mai tagliata con «…». Con il simbolo, se c'è. VoiceOver legge sempre i due numeri
/// («Giornata 8, 11ª di Serie A»). Le forme vengono da `NomeGiornata`, provate dai test.
struct GiornataInRiga: View {
    private let forme: [String]
    private let voce: String
    private let simbolo: String?

    init(forme: [String], voce: String, simbolo: String? = nil) {
        self.forme = forme.isEmpty ? [voce] : forme
        self.voce = voce
        self.simbolo = simbolo
    }

    /// `soloCorta`: per i widget piccoli, senza la forma intera («Giornata 8», poi «G8»).
    init(_ nome: NomeGiornata, soloCorta: Bool = false, simbolo: String? = nil) {
        self.init(forme: soloCorta ? nome.formeCorte : nome.forme, voce: nome.voce, simbolo: simbolo)
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
