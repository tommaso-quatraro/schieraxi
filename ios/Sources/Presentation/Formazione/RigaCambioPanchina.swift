import SwiftUI

/// Un cambio dalla panchina a giornata in corso: «Rossi → Bianchi» e l'etichetta «già fatto» (verde) o «probabile» (arancio), come
/// la web (`cardInCorso`, #436). VoiceOver legge «Esce Rossi, entra Bianchi, già fatto».
struct RigaCambioPanchina: View {
    let cambio: CambioPanchina

    var body: some View {
        HStack(alignment: .center, spacing: 10) {
            Text(TestiFase.cambio(cambio) ?? "").font(.subheadline.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 6)
            Capsula(testo: TestiFase.etichettaCambio(cambio), colore: cambio.certa ? Color.verde : Color.attenzione)
        }
        .frame(minHeight: Tema.areaTocco)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(TestiFase.cambioVoce(cambio) ?? "")
    }
}
