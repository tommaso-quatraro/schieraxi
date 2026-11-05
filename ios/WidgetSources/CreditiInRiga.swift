import WidgetKit
import SwiftUI

/// I crediti residui su una riga («Crediti … 12 residui»): nel Cruscotto, quando in fondo non c'è posto per il grafico e il
/// numero grande dei crediti (`ProvaCruscotto.grafico`). Il tocco (Mercato) lo mette chi la usa.
struct CreditiInRiga: View {
    let crediti: Double?
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            TitoloBlocco(testo: "Crediti", icona: ParoleWidget.simboloCrediti)
            Spacer(minLength: 8)
            Text(crediti.map { String(Formato.intero($0)) } ?? "—")
                .font(.headline).monospacedDigit()
                .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
            Text("residui").font(.caption2).foregroundStyle(TintaWidget.testo2)
        }
        .accessibilityElement(children: .combine)
    }
}
