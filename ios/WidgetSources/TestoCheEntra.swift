import SwiftUI

/// Un testo di una riga che si accorcia di parole intere: la prima forma che entra (le forme vengono da `ParoleWidget`).
/// VoiceOver legge sempre la prima, intera.
struct TestoCheEntra: View {
    private let forme: [String]

    init(_ forme: [String]) {
        self.forme = forme.isEmpty ? [""] : forme
    }

    var body: some View {
        PrimaCheEntra(forme.count) { i in
            Text(forme[i]).lineLimit(1)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(forme[0])
    }
}
