import SwiftUI

/// «probabili non uscite» nel piccolo di Prossima giornata: la prima forma che entra in larghezza. Il simbolo con la frase, poi la
/// frase senza il simbolo (come «punti attesi», che sta nello stesso posto), poi il solo simbolo. Prima era una riga sola con
/// `lineLimit(1)`, e con il testo grande (sull'iPhone SE anche con quello normale) diventava «probabili non usc…». Su due righe non
/// ci sta: con il testo molto grande il piccolo è già pieno. VoiceOver legge sempre la frase intera. Carattere e colore li sceglie
/// chi la usa.
struct ProbabiliNonUscite: View {
    private let frase = ParoleWidget.probabiliNonUscite
    private let simbolo = "clock"

    var body: some View {
        PrimaCheEntra(3) { i in
            if i == 0 {
                Label(frase, systemImage: simbolo).lineLimit(1)
            } else if i == 1 {
                Text(frase).lineLimit(1)
            } else {
                Image(systemName: simbolo)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(frase)
    }
}
