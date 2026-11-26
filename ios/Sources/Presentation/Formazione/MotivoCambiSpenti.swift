import SwiftUI

/// Sopra le righe spente di «Sostituisci» e di «Metti in campo»: perché adesso il cambio non si può fare, con la frase del
/// catalogo («Sto ancora ricalcolando: un attimo», «La formazione di questa giornata è chiusa: …», da
/// `FormazioneViewModel.motivoCambiSpenti`). VoiceOver la legge quando compare o cambia (collaudo del 26/11).
struct MotivoCambiSpenti: View {
    let motivo: String

    var body: some View {
        Text(motivo)
            .font(.subheadline)
            .foregroundStyle(Color.testoSecondario)
            .fixedSize(horizontal: false, vertical: true)
            .onAppear { AccessibilityNotification.Announcement(motivo).post() }
            .onChange(of: motivo) { _, nuovo in AccessibilityNotification.Announcement(nuovo).post() }
    }
}
