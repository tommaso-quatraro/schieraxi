import SwiftUI

/// «Crediti residui» con il campo e «Salva» (`PUT /api/crediti`), in cima alla rosa di una squadra.
///
/// Con il testo normale: titolo, campo e «Salva» sulla stessa riga; se non ci stanno, il titolo sta sopra. Con il testo molto
/// grande (`DisposizioneCrediti.inColonna`, issue #467) titolo, campo e «Salva» vanno uno sotto l'altro e il campo non ha più la
/// larghezza fissa che schiacciava «Salva» fino a spezzarlo lettera per lettera.
struct RigaCreditiResidui: View {
    @Binding var crediti: String
    /// Mentre un salvataggio è in corso «Salva» non si preme.
    let inCorso: Bool
    let salva: () -> Void

    @Environment(\.dynamicTypeSize) private var dimensioneTesto
    /// La larghezza del campo in riga cresce con il testo (una larghezza fissa taglia le cifre con il testo grande).
    @ScaledMetric private var larghezzaCampo: CGFloat = 96

    var body: some View {
        disposizione
            .frame(minHeight: DisposizioneCrediti.latoMinimoTocco)
    }

    @ViewBuilder
    private var disposizione: some View {
        switch DisposizioneCrediti.per(dimensioneTesto) {
        case .inColonna:
            VStack(alignment: .leading, spacing: 8) {
                titolo
                campoInColonna
                pulsanteSalva(larghezzaMinima: DisposizioneCrediti.latoMinimoTocco)
            }
        case .inRiga:
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 12) {
                    titolo
                    Spacer(minLength: 8)
                    campoInRiga
                    pulsanteSalva()
                }
                VStack(alignment: .leading, spacing: 8) {
                    titolo
                    HStack(spacing: 12) {
                        campoInRiga
                        pulsanteSalva()
                    }
                }
            }
        }
    }

    private var titolo: some View {
        Text(ParoleSquadre.creditiResidui)
            .accessibilityHidden(true)   // il campo ha già questo nome per VoiceOver
    }

    private var campo: some View {
        TextField("—", text: $crediti)
            .keyboardType(.numberPad)
            .accessibilityLabel(ParoleSquadre.creditiResidui)
    }

    private var campoInRiga: some View {
        campo
            .multilineTextAlignment(.trailing)
            .frame(width: larghezzaCampo)
            .frame(minHeight: DisposizioneCrediti.latoMinimoTocco)
    }

    private var campoInColonna: some View {
        campo
            .multilineTextAlignment(.leading)
            .frame(maxWidth: .infinity, minHeight: DisposizioneCrediti.latoMinimoTocco, alignment: .leading)
    }

    /// «Salva» sta sempre su una riga (`fixedSize`) e il bersaglio di tocco è nell'etichetta: con lo stile `.borderless` una
    /// cornice messa fuori dal pulsante non allarga la zona che risponde al tocco. `larghezzaMinima` solo nella colonna: in
    /// riga il pulsante resta largo quanto la parola, come prima.
    private func pulsanteSalva(larghezzaMinima: CGFloat? = nil) -> some View {
        Button(action: salva) {
            Text(ParoleSquadre.salva)
                .fixedSize(horizontal: true, vertical: false)
                .frame(minWidth: larghezzaMinima, minHeight: DisposizioneCrediti.latoMinimoTocco)
                .contentShape(Rectangle())
        }
        // il campo e il pulsante stanno nella stessa riga di una lista: senza questo un tocco li attiva come uno solo
        .buttonStyle(.borderless)
        .accessibilityLabel(ParoleSquadre.salvaCreditiResidui)
        .disabled(inCorso)
    }
}

#Preview("Crediti residui") {
    List {
        RigaCreditiResidui(crediti: .constant("41"), inCorso: false) {}
        RigaCreditiResidui(crediti: .constant("41"), inCorso: false) {}
            .dynamicTypeSize(.accessibility5)
    }
}
