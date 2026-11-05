import SwiftUI

/// La riga di un widget sulla schermata di blocco (`accessoryInline`): simbolo e la prima forma del testo che entra
/// (`PrimaCheEntra`), mai un testo tagliato a metà. Le forme vanno dalla più lunga alla più corta e vengono dal modello
/// (provate dai test). VoiceOver legge sempre la prima, intera, come `TestoCheEntra`.
struct RigaInLinea: View {
    private let forme: [String]
    private let icona: String

    init(_ forme: [String], icona: String) {
        self.forme = forme.isEmpty ? [""] : forme
        self.icona = icona
    }

    var body: some View {
        PrimaCheEntra(forme.count) { i in
            Label(forme[i], systemImage: icona)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(forme[0])
    }
}
