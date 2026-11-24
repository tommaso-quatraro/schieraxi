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

    /// Tetto della misura dei pallini della password (issue #857). La casella sta su una riga sola e, quando non ci si scrive,
    /// iOS taglia con «…» quello che non ci sta: con il testo massimo restavano otto pallini. Nelle foto un pallino è largo
    /// circa 0,6 volte la misura del carattere: a XXL 20 pallini (la password forte che propone iOS) sono larghi circa 256
    /// punti e stanno nei 295 della casella sull'iPhone più stretto. Oltre XXL i pallini non crescono più; l'etichetta sopra
    /// la casella resta grande.
    static let tettoPallini: DynamicTypeSize = .xxLarge

    @Environment(\.dynamicTypeSize) private var misuraTesto

    /// Altezza minima della riga di testo nella casella, uguale per tutti i campi: una riga di `.body` alla misura del testo
    /// scelta da chi usa l'app (anche quando i pallini si fermano a `tettoPallini`) più 3 punti. Nelle foto una casella di
    /// testo è alta circa una riga più un punto e mezzo (22 punti col testo normale, 65 col massimo), quella della password
    /// un punto meno: con 3 punti in più vince sempre questa altezza, e le caselle sono alte uguali a ogni misura. Un
    /// `@ScaledMetric` non bastava: cresce meno del carattere (col testo massimo la password restava 83 punti contro 89).
    private var rigaCasella: CGFloat {
        let tratti = UITraitCollection(preferredContentSizeCategory: UIContentSizeCategory(misuraTesto))
        return UIFont.preferredFont(forTextStyle: .body, compatibleWith: tratti).lineHeight + 3
    }

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
                .frame(minHeight: rigaCasella)
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
                .dynamicTypeSize(...Self.tettoPallini)
        } else {
            TextField("", text: $testo)
        }
    }
}
