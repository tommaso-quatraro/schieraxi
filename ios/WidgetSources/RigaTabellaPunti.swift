import SwiftUI

/// Una riga della tabella del widget «Punti attesi e fatti» (misura grande): giornata, fascia, fatti su attesi, scarto.
/// La forma (`PuntiGiornata.FormaRiga`) la sceglie chi mette le righe, uguale per tutte; VoiceOver legge sempre la riga intera.
struct RigaTabellaPunti: View {
    let giornata: PuntiGiornata
    let forma: PuntiGiornata.FormaRiga
    /// «−2,5», già scritto come nel grafico.
    let scarto: String

    var body: some View {
        let pezzi = giornata.riga(forma)
        HStack {
            Text(pezzi.titolo).font(.footnote).lineLimit(1)
            if let fascia = pezzi.fascia {
                Text(fascia).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
            }
            Spacer(minLength: 6)
            Text(pezzi.punti).font(.footnote).monospacedDigit().lineLimit(1)
            Text(scarto).font(.footnote.weight(.semibold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
                .frame(width: 52, alignment: .trailing)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(GraficoPunti.descrizione(giornata))
    }
}
