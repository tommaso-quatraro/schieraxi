import SwiftUI

/// La riga di un widget sulla schermata di blocco (`accessoryInline`): simbolo e la prima forma del testo che entra
/// (`PrimaCheEntra`), mai un testo tagliato a metà. Le forme vanno dalla più lunga alla più corta e vengono dal modello
/// (provate dai test). VoiceOver legge `voce` se c'è (per esempio il conto alla rovescia a parole intere), altrimenti la prima
/// forma, intera, come `TestoCheEntra`.
struct RigaInLinea: View {
    private let forme: [String]
    private let icona: String
    private let voce: String?

    init(_ forme: [String], icona: String, voce: String? = nil) {
        self.forme = forme.isEmpty ? [""] : forme
        self.icona = icona
        self.voce = voce
    }

    var body: some View {
        PrimaCheEntra(forme.count) { i in
            Label(forme[i], systemImage: icona)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(voce ?? forme[0])
    }
}
