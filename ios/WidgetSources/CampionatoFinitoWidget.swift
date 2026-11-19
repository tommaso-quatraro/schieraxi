import SwiftUI
import WidgetKit

/// I widget a campionato finito (#727): la frase del server (`campionato_finito` di `/api/widget`, #656) al posto della giornata,
/// con la bandiera a scacchi della giornata finita. Non è un guasto: niente «Nessun dato» né il simbolo della rete. La frase va a
/// capo; dove intera non entra (schermata di blocco, testo grande) resta la sua prima parte («Il campionato è finito»), e nella
/// riga in linea anche solo il simbolo. VoiceOver legge sempre la frase intera. Le forme vengono da
/// `ParoleWidget.formeCampionatoFinito`, provate dai test.
struct CampionatoFinitoWidget: View {
    let testo: String
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }

    /// Lo stesso simbolo della giornata finita negli altri widget.
    private static let simbolo = "flag.checkered"

    var body: some View {
        let forme = ParoleWidget.formeCampionatoFinito(testo)
        contenuto(forme)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(forme.first ?? testo)
    }

    @ViewBuilder
    private func contenuto(_ forme: [String]) -> some View {
        switch famiglia {
        case .accessoryInline:
            // una riga sola: la frase intera o la sua prima parte accanto al simbolo, o il simbolo da solo (mai tagliata)
            PrimaCheEntra(forme.count + 1) { i in
                if i < forme.count {
                    Label(forme[i], systemImage: Self.simbolo)
                } else {
                    Image(systemName: Self.simbolo)
                }
            }
        case .accessoryCircular:
            CerchioWidget {
                Image(systemName: Self.simbolo).font(.title3).widgetAccentable()
            }
        case .accessoryRectangular:
            PrimaCheEntra(forme.count, in: .vertical) { i in
                Text(forme[i]).font(i == 0 ? .caption : .headline)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        default:
            PrimaCheEntra(forme.count, in: .vertical) { i in
                VStack(alignment: .leading, spacing: 6) {
                    Image(systemName: Self.simbolo).font(.title3).widgetAccentable()
                    Text(forme[i]).font(carattere.weight(.semibold))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
    }

    /// La frase nei widget della Home: più piccola nel piccolo, più grande nel grande e nell'extra large dell'iPad.
    private var carattere: Font {
        switch famiglia {
        case .systemSmall: return .footnote
        case .systemLarge, .systemExtraLarge: return .title3
        default: return .subheadline
        }
    }
}
