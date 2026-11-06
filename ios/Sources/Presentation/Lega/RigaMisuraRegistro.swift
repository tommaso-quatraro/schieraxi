import SwiftUI

/// Una misura del registro delle giornate: il nome, accanto il verdetto (colorato, ma sempre a parole) e sotto media e soglia.
/// Se non ci sta in una riga (schermo stretto, testo grande) il verdetto va sotto il nome, come in `RigaValore`.
/// Nome, verdetto e dettagli vanno a capo interi, mai con i puntini (`RigaMisuraRegistroInteraTests`).
struct RigaMisuraRegistro: View {
    let nome: String
    let esito: ParoleRegistro.Esito
    /// Media e soglia sotto il nome; nil per una riga senza numeri (il verdetto delle misure insieme dei gol attesi nostri).
    var dettaglio: String? = nil
    /// Le parole accanto al nome quando non sono quelle di `esito` (il colore resta quello di `esito`): «reggono» al plurale.
    var verdetto: String? = nil

    var body: some View {
        let parole = Text(verdetto ?? esito.testo).font(.subheadline).foregroundStyle(colore)
        VStack(alignment: .leading, spacing: 2) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text(nome).fixedSize()
                    Spacer(minLength: 8)
                    parole.fixedSize()
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(nome)
                    parole
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            if let dettaglio {
                Text(dettaglio)
                    .font(.footnote)
                    .foregroundStyle(Color.testoSecondario)
                    .monospacedDigit()
            }
        }
        // Mai tagliata con «…» (#430, come le etichette dei giocatori: #227, #254): la riga prende l'altezza che i testi chiedono per
        // la larghezza che ha, anche quando la lista le propone meno (la VStack stringeva il nome a una riga sola).
        .fixedSize(horizontal: false, vertical: true)
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
