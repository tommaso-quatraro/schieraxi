import SwiftUI

/// Una squadra da toccare in «Qual è la tua squadra?» dell'anteprima delle rose, come le scelte `ar-mia` della web (#880). Il cerchio
/// diventa una spunta quando è scelta (non cambia solo il colore) e VoiceOver la dice selezionata; la larghezza resta la stessa, così
/// al tocco le squadre non si spostano. Un nome lungo con il testo grande va a capo dentro la pillola.
struct PillolaSquadraMia: View {
    let nome: String
    let scelta: Bool
    let scegli: () -> Void

    private var forma: RoundedRectangle { RoundedRectangle(cornerRadius: Tema.areaTocco / 2, style: .continuous) }

    var body: some View {
        Button(action: scegli) {
            HStack(spacing: 6) {
                Image(systemName: scelta ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(scelta ? Color.verde : Color.testoSecondario)
                    .accessibilityHidden(true)
                Text(nome)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .font(.subheadline)
            .padding(.horizontal, 14)
            .padding(.vertical, 6)
            .frame(minHeight: Tema.areaTocco)
            .background(scelta ? Color.verde.opacity(0.35) : Color.primary.opacity(0.08), in: forma)
            .overlay { forma.strokeBorder(scelta ? Color.verde : .clear, lineWidth: 1) }
            .contentShape(forma)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(scelta ? .isSelected : [])
    }
}

#Preview("Qual è la tua squadra?") {
    FilaPillole(spazio: 8) {
        PillolaSquadraMia(nome: "Squadra di prova", scelta: true) {}
        PillolaSquadraMia(nome: "Atletico Pigiama", scelta: false) {}
        PillolaSquadraMia(nome: "Real Fantasia", scelta: false) {}
    }
    .padding()
}
