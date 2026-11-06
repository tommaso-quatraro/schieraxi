import SwiftUI

/// Una misura del registro delle giornate: il nome, accanto il verdetto (colorato, ma sempre a parole) e sotto media e soglia.
/// Se non ci sta in una riga (schermo stretto, testo grande) il verdetto va sotto il nome, come in `RigaValore`.
struct RigaMisuraRegistro: View {
    let nome: String
    let esito: ParoleRegistro.Esito
    let dettaglio: String

    var body: some View {
        let verdetto = Text(esito.testo).font(.subheadline).foregroundStyle(colore)
        VStack(alignment: .leading, spacing: 2) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text(nome).fixedSize()
                    Spacer(minLength: 8)
                    verdetto.fixedSize()
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(nome)
                    verdetto
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            Text(dettaglio)
                .font(.footnote)
                .foregroundStyle(Color.testoSecondario)
                .monospacedDigit()
        }
        .accessibilityElement(children: .combine)
    }

    private var colore: Color {
        switch esito {
        case .regge: return Color.esitoBuono
        case .nonRegge: return Color.esitoMalus
        case .servono, .senzaDati: return Color.testoSecondario
        }
    }
}
