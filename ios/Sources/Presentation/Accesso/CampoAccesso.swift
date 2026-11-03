import SwiftUI

/// Un campo del modulo di accesso come sulla web (`campoAccesso` in `fanta/web/app.js`): l'etichetta sopra, che resta mentre
/// si scrive; il campo senza testo d'esempio (il grigio chiaro dentro il campo non arrivava a 3:1); sotto, la spiegazione e il
/// problema. Etichetta e spiegazione nel grigio leggibile dell'app (`Color.testoSecondario`, almeno 4,5:1 sulla scheda in
/// chiaro e in scuro). VoiceOver legge l'etichetta e poi il problema, o la spiegazione (issue #195).
struct CampoAccesso: View {
    let etichetta: String
    @Binding var testo: String
    let campo: ModuloAccesso.Campo
    var focus: FocusState<ModuloAccesso.Campo?>.Binding
    var segreto = false
    var aiuto: String?
    var problema: String?
    /// Cosa legge VoiceOver dopo l'etichetta (`ModuloAccesso.suggerimento`).
    var suggerimento: String?
    /// Per i suggerimenti della tastiera e dei portachiavi (nome utente, password nuova, codice arrivato per posta...).
    var contenuto: UITextContentType?
    var tastiera: UIKeyboardType = .default
    var maiuscole: TextInputAutocapitalization = .never

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(etichetta)
                .font(.subheadline)
                .foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityHidden(true)   // la legge il campo
            casella
                .font(.body)
                .textContentType(contenuto)
                .keyboardType(tastiera)
                .textInputAutocapitalization(maiuscole)
                .autocorrectionDisabled()
                .focused(focus, equals: campo)
                .padding(12)
                .frame(minHeight: Tema.areaTocco)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo))
                .accessibilityLabel(etichetta)
                .accessibilityHint(suggerimento ?? "")
            if let aiuto {
                Text(aiuto)
                    .font(.footnote)
                    .foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityHidden(true)   // la legge il campo, dopo l'etichetta
            }
            if let problema {
                Text(problema)
                    .font(.footnote)
                    .foregroundStyle(Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityLabel("\(etichetta): \(problema)")
            }
        }
    }

    @ViewBuilder
    private var casella: some View {
        if segreto {
            SecureField("", text: $testo)
        } else {
            TextField("", text: $testo)
        }
    }
}
