import SwiftUI

/// «Prossima: 4 giorni 1 h»: il conto alla rovescia alla prossima scadenza in un testo solo, quindi della stessa grandezza
/// (#871: erano due testi, e con il testo molto grande il conto usciva più piccolo di «Prossima:»). Il conto non si spezza:
/// dove non entra va a capo intero (`ParoleWidget.prossima`). Righe e rimpicciolimento li sceglie chi lo usa. VoiceOver legge
/// il conto a parole intere («Prossima: 4 giorni e 1 ora»).
struct ProssimaConto: View {
    let scadenza: Date?
    let adesso: Date

    var body: some View {
        Text(ParoleWidget.prossima(fino: scadenza, adesso: adesso))
            .monospacedDigit()
            .accessibilityLabel(ParoleWidget.voceProssima(fino: scadenza, adesso: adesso))
    }
}
