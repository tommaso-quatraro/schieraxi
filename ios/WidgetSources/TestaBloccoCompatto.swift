import WidgetKit
import SwiftUI

/// Titolo e guadagno dei blocchi Scambio e Svincolo del Cruscotto. Di solito il titolo sopra e il guadagno grande sotto
/// («+2,4 punti»); nella forma compatta (`ProvaCruscotto.compatto`: iPad, iPhone piccoli) il guadagno sta accanto al titolo
/// corto («Scambio +2,4»), che entra anche nella colonna stretta, e VoiceOver legge comunque «punti».
struct TestaBloccoCompatto: View {
    let titolo: String
    let titoloCorto: String
    let icona: String
    let guadagno: Double
    let compatto: Bool
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }

    private var numero: some View {
        Text(Formato.conSegno(guadagno)).font(.title3.bold()).monospacedDigit()
            .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
    }

    var body: some View {
        if compatto {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                TitoloBlocco(testo: titoloCorto, icona: icona)
                numero.accessibilityLabel("\(Formato.conSegno(guadagno)) punti")
            }
        } else {
            VStack(alignment: .leading, spacing: 2) {
                TitoloBlocco(testo: titolo, icona: icona)
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    numero
                    Text("punti").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
            }
        }
    }
}
