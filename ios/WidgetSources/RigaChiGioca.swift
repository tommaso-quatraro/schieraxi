import SwiftUI

/// Una riga del widget «Chi gioca»: volto e nome; sotto l'avversario e le parole di ogni avviso, in arancione solo se c'è da
/// guardare («Diffidato», «In dubbio · gioca 70%»; «Rigorista» resta grigio): ogni colore e ogni segno ha la sua parola. A destra
/// quando gioca, scritto una volta sola e con il giorno («oggi 18:30»). Testi e colori vengono da `GiocatoreWidget`
/// (`formeChiGioca`, `daGuardare`, `quandoGioca`, provati in `WidgetChiGiocaTests`). Il tocco apre la scheda del giocatore.
struct RigaChiGioca: View {
    let g: GiocatoreWidget
    /// L'istante della voce del widget: dice se la partita è «oggi» o «domani».
    let adesso: Date

    var body: some View {
        Link(destination: Vai.giocatore(g.id)) {
            HStack(spacing: 8) {
                AvatarMini(g: g, lato: 26)
                VStack(alignment: .leading, spacing: 0) {
                    Text(g.nome).font(.subheadline.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.8)
                    let forme = g.formeChiGioca
                    if !forme.isEmpty {
                        TestoCheEntra(forme)
                            .font(.caption2)
                            .foregroundStyle(g.daGuardare ? TintaWidget.attenzione : TintaWidget.testo2)
                    }
                }
                Spacer(minLength: 0)
                Text(g.quandoGioca(adesso: adesso)).font(.subheadline.weight(.semibold)).monospacedDigit().lineLimit(1)
            }
            .frame(minHeight: 30)
        }
        .accessibilityElement(children: .combine)
    }
}
