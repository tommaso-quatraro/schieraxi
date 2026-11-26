import SwiftUI

/// «Un attimo, mister: ci sto lavorando.» con il marchio che si muove, sopra la barra, mentre una richiesta aspetta un calcolo del
/// server (risposta 202), come il riquadro `#calcolo` della web (`mostraCalcolo`, `comune.calcolo_attesa`, #931). Non si tocca:
/// i tocchi passano alla schermata sotto. VoiceOver lo legge quando compare, come il `role="status"` della web.
struct AvvisoCalcolo: View {
    @ObservedObject private var attesa = AttesaCalcolo.condivisa
    @Environment(\.accessibilityReduceMotion) private var ridotto

    var body: some View {
        ZStack {
            if attesa.inCorso {
                HStack(spacing: 12) {
                    Marchio(lato: 34, muove: true).accessibilityHidden(true)
                    Text(Catalogo.Comune.calcoloAttesa)
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .frame(maxWidth: 540)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .padding(.horizontal, 18)
                // sopra la barra delle schede, come la web (che lo tiene sopra la sua barra)
                .padding(.bottom, 72)
                .accessibilityElement(children: .combine)
                .transition(.opacity)
                .onAppear { AccessibilityNotification.Announcement(Catalogo.Comune.calcoloAttesa).post() }
            }
        }
        .animation(ridotto ? nil : .easeInOut(duration: 0.2), value: attesa.inCorso)
        .allowsHitTesting(false)
    }
}
