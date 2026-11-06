import SwiftUI

/// La sigla a inizio riga del Calendario, con il pallino verde se in quella squadra gioca uno dei miei (come la web).
/// Il posto del pallino c'è sempre, così le sigle restano in colonna; VoiceOver dice a parole che è una delle tue squadre.
struct SiglaCalendario: View {
    let squadra: String
    let mia: Bool

    /// La larghezza della colonna delle sigle (anche dell'angolo vuoto sopra).
    static let larghezza: CGFloat = 50

    var body: some View {
        let sigla = ColoriSquadra.sigla(squadra)
        HStack(spacing: 3) {
            Circle()
                .fill(Color.verde)
                .frame(width: 6, height: 6)
                .opacity(mia ? 1 : 0)
            Text(sigla)
                .font(.caption.bold())
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(width: Self.larghezza, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(mia ? "\(sigla), tra le tue squadre" : sigla)
    }
}
