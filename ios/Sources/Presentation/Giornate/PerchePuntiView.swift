import SwiftUI

/// Giornate, da dove vengono i punti (#900): sotto la tabella degli 11, una riga per frase del server (riserve entrate,
/// modificatore difesa, partita rinviata; `DettaglioGiornata.perche`), così com'è e nel suo ordine, come l'elenco `gn-perche` della
/// web: testo piccolo nel colore del testo, ogni frase intera e a capo. VoiceOver trova l'elenco con il nome della web, «Da dove
/// vengono i punti», e legge una frase alla volta.
struct PerchePuntiView: View {
    let frasi: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(Array(frasi.enumerated()), id: \.offset) { _, frase in
                Text(frase)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .font(.footnote)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(Catalogo.Giornate.perchePunti)
    }
}

#Preview("Da dove vengono i punti") {
    List {
        PerchePuntiView(frasi: ["Orsetti (7,0) è entrato dalla panchina al posto di Lemão.",
                                "Al posto di Sorvani non è entrato nessuno dalla panchina.",
                                "Modificatore difesa: +1,5."])
    }
}
