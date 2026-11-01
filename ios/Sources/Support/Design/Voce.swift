import SwiftUI

/// Una voce di elenco con l'icona in un quadratino colorato, come nelle Impostazioni di iOS.
struct StileVoce: LabelStyle {
    let colore: Color

    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 12) {
            IconaVoce(icona: configuration.icon, colore: colore)
            configuration.title
        }
    }
}

/// Il quadratino dell'icona: cresce con Dynamic Type, ma fino a un tetto (a 1,6 volte) per non sformare le righe.
private struct IconaVoce<Icona: View>: View {
    let icona: Icona
    let colore: Color
    @ScaledMetric(relativeTo: .body) private var lato: CGFloat = 30
    @ScaledMetric(relativeTo: .body) private var corpo: CGFloat = 15

    var body: some View {
        icona
            .font(.system(size: min(corpo, 24), weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: min(lato, 48), height: min(lato, 48))
            .background(colore.gradient, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .accessibilityHidden(true)
    }
}

extension LabelStyle where Self == StileVoce {
    static func voce(_ colore: Color) -> StileVoce { StileVoce(colore: colore) }
}
