import SwiftUI

/// Un salvataggio della formazione non riuscito quando eri già su un'altra scheda (#726, come `nonSalvata` della web, #667): un
/// avviso in basso, sopra la barra delle schede, con la frase scelta dal ViewModel (`FormazioneViewModel.avvisoAltrove`:
/// `formazione.non_salvata_rete` o `formazione.non_salvata`). VoiceOver lo legge; resta 8 secondi, come gli avvisi brevi della
/// Formazione, e tornando sulla Formazione sparisce (lo toglie il ViewModel). Va sulle schede diverse dalla Formazione: le schede
/// non aperte restano in memoria, per questo lo mostra solo quella aperta (`attiva`).
struct AvvisoNonSalvata: ViewModifier {
    @ObservedObject var vm: FormazioneViewModel
    /// Questa è la scheda aperta, e non è la Formazione.
    let attiva: Bool

    /// Quanto resta a video.
    static let durata: Duration = .seconds(8)

    private var testo: String? { attiva ? vm.avvisoAltrove : nil }

    func body(content: Content) -> some View {
        content
            .safeAreaInset(edge: .bottom, spacing: 0) {
                if let testo {
                    Label(testo, systemImage: "exclamationmark.triangle")
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(.primary)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .vetro(in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous),
                               tinta: Color.attenzione.opacity(0.35))
                        .padding(.horizontal, Tema.margine)
                        .padding(.bottom, 8)
                        .frame(maxWidth: .infinity)
                        .accessibilityElement(children: .combine)
                        .transizione(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(Tema.molla, value: testo)
            .task(id: testo) {
                guard let testo else { return }
                AccessibilityNotification.Announcement(testo).post()
                try? await Task.sleep(for: Self.durata)
                guard !Task.isCancelled else { return }
                vm.avvisoAltrove = nil
            }
    }
}

extension View {
    /// L'avviso di un salvataggio della formazione non riuscito a scheda lasciata (`AvvisoNonSalvata`).
    func avvisoNonSalvata(_ vm: FormazioneViewModel, attiva: Bool) -> some View {
        modifier(AvvisoNonSalvata(vm: vm, attiva: attiva))
    }
}
