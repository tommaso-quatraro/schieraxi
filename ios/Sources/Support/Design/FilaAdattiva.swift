import SwiftUI

/// Una fila che con il testo molto grande (le misure «Accessibilità» di Dynamic Type) diventa una colonna.
/// Con il testo normale è un `HStack`; con il testo grandissimo i pezzi vanno uno sotto l'altro, allineati a sinistra,
/// invece di schiacciarsi fino a spezzare le parole lettera per lettera (visto nelle foto con testo XXXL su iPhone SE).
struct FilaAdattiva<Contenuto: View>: View {
    var allineamento: VerticalAlignment = .center
    var spazio: CGFloat? = nil
    let contenuto: Contenuto
    init(allineamento: VerticalAlignment = .center, spazio: CGFloat? = nil, @ViewBuilder _ contenuto: () -> Contenuto) {
        self.allineamento = allineamento; self.spazio = spazio; self.contenuto = contenuto()
    }
    @Environment(\.dynamicTypeSize) private var taglia

    var body: some View {
        let layout = taglia.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: spazio))
            : AnyLayout(HStackLayout(alignment: allineamento, spacing: spazio))
        layout { contenuto }
    }
}

#Preview("Fila adattiva") {
    VStack(spacing: 20) {
        FilaAdattiva { Text("Aldo Pinarotti").font(.headline); Spacer(minLength: 0); Text("Sassuolo").foregroundStyle(.secondary) }
        FilaAdattiva { Text("Aldo Pinarotti").font(.headline); Spacer(minLength: 0); Text("Sassuolo").foregroundStyle(.secondary) }
            .dynamicTypeSize(.accessibility5)
    }
    .padding()
}
