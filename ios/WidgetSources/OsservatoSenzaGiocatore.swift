import SwiftUI
import WidgetKit

/// Il widget «Osservato» senza un giocatore da mostrare: invita ad aggiungere un seguito oppure, se il server ha tolto i seguiti
/// perché la risposta era troppo grande (`mancano`), dice di aprire l'app per vederli invece di restare vuoto. Le parole vengono
/// da `VuotoOsservato` (provate in `WidgetOsservatoTests`); il tocco del widget apre l'app.
struct OsservatoSenzaGiocatore: View {
    let vuoto: VuotoOsservato
    let famiglia: WidgetFamily

    private var accessorio: Bool {
        switch famiglia {
        case .accessoryCircular, .accessoryRectangular, .accessoryInline: return true
        default: return false
        }
    }

    var body: some View {
        switch famiglia {
        case .accessoryInline:
            Label(vuoto.riga, systemImage: "eye")
        case .accessoryCircular:
            CerchioWidget {
                Image(systemName: "eye").font(.caption2)
                Text(vuoto.cerchio).fontWidget(9).multilineTextAlignment(.center).lineLimit(2).minimumScaleFactor(0.7)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(vuoto.titolo). \(vuoto.frase)")
        default:
            VStack(alignment: .leading, spacing: 3) {
                TitoloBlocco(testo: "Seguito", icona: "eye")
                Text(vuoto.titolo).font(.headline)
                Text(vuoto.frase).font(.caption).foregroundStyle(accessorio ? Color.secondary : TintaWidget.testo2)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        }
    }
}
