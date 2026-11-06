import SwiftUI

/// Il titolo piccolo della barra, sempre intero: mai tagliato con «…» mentre lo stesso titolo è intero nella pagina.
/// `ModificatoreTitoloPagina` lo mette al posto del titolo di sistema, che sta su una riga e taglia.
///
/// - Testo normale (`TitoloPagina.interoInBarra`, pagine con `piccoloInBarra`, #293): il nome sta su una riga, come il
///   titolo di sistema, se ci sta; se no va a capo su due righe, un po' più piccolo, e si stringe appena (fino all'80%) solo
///   se due righe non bastano. Limite: un nome che non sta in due righe nemmeno all'80% (oltre ~40-45 lettere con il testo
///   grande) si accorcia con «…». iPhone in orizzontale: una riga sola.
/// - Testo grande (`soloSeCiSta`, `TitoloPagina.inBarraSeCiSta`, tutte le pagine, #419): il titolo intero sta già nella
///   pagina (`TitoloNellaPagina`), quindi la barra lo mostra solo se ci sta intero su una riga; se no non mostra niente.
///   VoiceOver salta la barra e legge il titolo nella pagina, come intestazione (`TitoloPagina.voceNellaPagina`).
struct TitoloInBarra: View {
    let titolo: String
    /// Testo grande: una riga se il titolo ci sta intero, se no niente (il titolo intero è nella pagina).
    var soloSeCiSta = false
    @Environment(\.verticalSizeClass) private var classeVerticale

    var body: some View {
        Group {
            if soloSeCiSta {
                // Testo grande: il titolo su una riga, intero, oppure niente. `ViewThatFits` prende la prima vista che ci sta in
                // larghezza: se il titolo non ci sta, l'ultima, vuota e alta zero (nessun riquadro vuoto per VoiceOver o Zoom).
                // In orizzontale vale lo stesso: con il tetto una riga sta anche nella barra bassa.
                ViewThatFits(in: .horizontal) {
                    Text(titolo)
                        .font(.headline)
                        .lineLimit(1)
                    Color.clear
                        .frame(width: 0, height: 0)
                        .accessibilityHidden(true)
                }
                // cresce come il titolo piccolo di sistema, non oltre: la barra resta alta come nelle altre pagine
                .dynamicTypeSize(...TitoloPagina.tettoBarra)
            } else if classeVerticale == .compact {
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
        // VoiceOver lo legge come il titolo della pagina, come quello di sistema che sostituisce. Con il testo grande no
        // (`soloSeCiSta`): VoiceOver lo legge nella pagina, come intestazione, dove è sempre intero; qui lo ripeterebbe
        // quando il titolo ci sta (`TitoloPagina.voceNellaPagina`)
        .accessibilityAddTraits(.isHeader)
        .accessibilityHidden(soloSeCiSta)
    }
}

extension View {
    /// Con un titolo, la barra mostra quel `TitoloInBarra` al posto del titolo di sistema. Con `nil` la barra resta quella
    /// di sistema. Il titolo di sistema (`navigationTitle`) resta impostato per il pulsante «indietro» della pagina dopo e
    /// per l'elenco delle pagine aperte, ma esce dalla barra (`toolbar(removing: .title)`): sotto `TitoloInBarra` non si
    /// vede, però VoiceOver lo trovava lo stesso (#419), tagliato in un riquadro su una zona vuota con il testo grande e
    /// come secondo titolo con il testo normale.
    @ViewBuilder
    func titoloInBarra(_ titolo: TitoloInBarra?) -> some View {
        let titoloDiSistema: ToolbarDefaultItemKind? = titolo == nil ? nil : .title
        if #available(iOS 26.0, *) {
            self.toolbar {
                if let titolo {
                    // su iOS 26 gli elementi della barra stanno su una pillola di vetro: il titolo no, come quello di sistema
                    ToolbarItem(id: "titolo-intero", placement: .principal) {
                        titolo
                    }
                    .sharedBackgroundVisibility(.hidden)
                }
            }
            .toolbar(removing: titoloDiSistema)
        } else {
            self.toolbar {
                if let titolo {
                    ToolbarItem(placement: .principal) {
                        titolo
                    }
                }
            }
            .toolbar(removing: titoloDiSistema)
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

#Preview("Testo grande, nome lungo: niente nella barra, intero nella pagina") {
    NavigationStack {
        List {
            TitoloNellaPagina()
            Text("Portieri")
        }
        .titoloPagina("Gli Amici del Bar Sport Centrale", piccoloInBarra: true)
    }
    .dynamicTypeSize(.accessibility3)
}
