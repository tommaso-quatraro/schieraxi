import SwiftUI

/// Il conto alla rovescia alla scadenza della formazione, come la web: «2 giorni 3 h», «6 h 44 min», «12 min»
/// (`Quando.contoAllaRovescia`), e a voce con le parole intere. Lo usano il riquadro principale di Oggi e l'accessorio sotto la
/// barra delle schede, dentro un `TimelineView` che lo ridisegna. Chi lo usa controlla prima che il conto ci sia
/// (`Quando.contoAllaRovescia` non nil): altrimenti la formazione è chiusa.
struct TestoConto: View {
    let inizio: Date
    let adesso: Date

    var body: some View {
        let testo = Quando.contoAllaRovescia(fino: inizio, adesso: adesso) ?? "0 min"
        Text(testo)
            .monospacedDigit()
            .accessibilityLabel(Quando.contoAllaRovesciaParlato(fino: inizio, adesso: adesso) ?? testo)
    }
}
