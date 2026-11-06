import SwiftUI

/// Il titolo piccolo della barra, intero (#293). Il titolo di sistema della barra piccola sta su una riga: con il testo
/// normale tagliava un nome di squadra oltre ~22 lettere («Gli Amici del Bar Spo…»). Qui il nome sta su una riga, come il
/// titolo di sistema, se ci sta; se no va a capo su due righe, un po' più piccolo, e si stringe appena (fino all'80%) solo
/// se due righe non bastano. Limite: un nome che non sta in due righe nemmeno all'80% (oltre ~40-45 lettere con il testo
/// grande) si accorcia con «…». iPhone in orizzontale: una riga sola (sotto). `ModificatoreTitoloPagina` lo mette al posto
/// del titolo di sistema nelle pagine con `piccoloInBarra`, sotto `TitoloPagina.soglia` (`TitoloPagina.interoInBarra`).
struct TitoloInBarra: View {
    let titolo: String
    @Environment(\.verticalSizeClass) private var classeVerticale

    var body: some View {
        Group {
            if classeVerticale == .compact {
                // iPhone in orizzontale: la barra piccola è alta ~32 punti e due righe non ci stanno; in larghezza c'è molto
                // più posto, quindi una riga sola che si stringe appena (fino all'80%) solo se serve
                Text(titolo)
                    .font(.headline)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            } else {
                ViewThatFits(in: .horizontal) {
                    // lo stesso carattere del titolo piccolo di sistema
                    Text(titolo)
                        .font(.headline)
                        .lineLimit(1)
                    Text(titolo)
                        .font(.subheadline.weight(.semibold))
                        .lineLimit(2)
                        .minimumScaleFactor(0.8)
                        .multilineTextAlignment(.center)
                        // la barra può proporre l'altezza di una riga sola: due righe vere, non una riga tagliata
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        // VoiceOver lo legge come il titolo della pagina, come quello di sistema che sostituisce
        .accessibilityAddTraits(.isHeader)
    }
}

extension View {
    /// Con un titolo, la barra mostra `TitoloInBarra` al posto del titolo di sistema (che resta per il pulsante «indietro»
    /// della pagina dopo e per l'elenco delle pagine aperte). Con `nil` la barra resta quella di sistema.
    @ViewBuilder
    func titoloInteroInBarra(_ titolo: String?) -> some View {
        if #available(iOS 26.0, *) {
            self.toolbar {
                if let titolo {
                    // su iOS 26 gli elementi della barra stanno su una pillola di vetro: il titolo no, come quello di sistema
                    ToolbarItem(id: "titolo-intero", placement: .principal) {
                        TitoloInBarra(titolo: titolo)
                    }
                    .sharedBackgroundVisibility(.hidden)
                }
            }
        } else {
            self.toolbar {
                if let titolo {
                    ToolbarItem(placement: .principal) {
                        TitoloInBarra(titolo: titolo)
                    }
                }
            }
        }
    }
}

#Preview("Nome lungo: due righe nella barra") {
    NavigationStack {
        List {
            Text("Portieri")
        }
        .titoloPagina("Gli Amici del Bar Sport Centrale", piccoloInBarra: true)
    }
}

#Preview("Nome corto: una riga") {
    NavigationStack {
        List {
            Text("Portieri")
        }
        .titoloPagina("Real Madrink", piccoloInBarra: true)
    }
}
