import SwiftUI

/// La legenda sotto la tabella del Calendario, come la web: «Facile», i cinque colori dal più facile al più difficile, «Dura».
/// VoiceOver la salta: ogni casella della tabella dice già la difficoltà a parole.
struct LegendaCalendario: View {
    var body: some View {
        HStack(spacing: 6) {
            Text(CalendarioView.legenda.facile)
            ForEach(1...5, id: \.self) { difficolta in
                Capsule()
                    .fill(Color.difficolta(Double(difficolta)).opacity(0.85))
                    .frame(width: 22, height: 8)
            }
            Text(CalendarioView.legenda.difficile)
        }
        .font(.caption)
        .foregroundStyle(Color.testoSecondario)
        .frame(maxWidth: .infinity)
        .padding(.top, 4)
        .accessibilityHidden(true)
    }
}
