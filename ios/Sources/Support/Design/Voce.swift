import SwiftUI

/// Una voce di elenco con l'icona in un quadratino colorato, come nelle Impostazioni di iOS.
struct StileVoce: LabelStyle {
    let colore: Color

    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 12) {
            configuration.icon
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 30, height: 30)
                .background(colore.gradient, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                .accessibilityHidden(true)
            configuration.title
        }
    }
}

extension LabelStyle where Self == StileVoce {
    static func voce(_ colore: Color) -> StileVoce { StileVoce(colore: colore) }
}
