import WidgetKit
import SwiftUI

/// Widget «Chi gioca»: i giocatori della mia rosa che scendono in campo a breve, con orario, avversario e stato (dubbio, rigorista).
/// Misure: medio (3 righe), grande (6), extra large per iPad (due colonne da 6), rettangolo e riga per la schermata di blocco.
/// Piccolo e cerchio non hanno senso: servono almeno un nome, un orario e un avversario.
struct WidgetRosa: Widget {
    let kind = "SchieraxiRosaOggi"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaRosa(voce: voce)
        }
        .configurationDisplayName("Chi gioca")
        .description("I tuoi giocatori che scendono in campo a breve, con l'orario. Tocca un nome per la sua scheda.")
        .supportedFamilies([.systemMedium, .systemLarge, .systemExtraLarge, .accessoryRectangular, .accessoryInline])
    }
}

struct VistaRosa: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    let voce: Voce

    private var accessorio: Bool { famiglia == .accessoryRectangular || famiglia == .accessoryInline }

    private var quanti: Int {
        switch famiglia {
        case .systemExtraLarge: return 12
        case .systemLarge: return 6
        case .systemMedium: return 3
        default: return 2
        }
    }

    var body: some View {
        Group {
            if let w = voce.completo, !(w.rosa ?? []).isEmpty {
                contenuto(w)
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(voce.tocco(URL(string: "schieraxi://oggi")))
    }

    @ViewBuilder
    private func contenuto(_ w: RiassuntoWidget) -> some View {
        let giocano = w.giocanoPresto(dopo: voce.date, massimo: quanti)
        switch famiglia {
        case .accessoryInline:
            if let g = giocano.first { Label("\(g.cognome) \(g.oraBreve)", systemImage: "figure.soccer") } else { Label("Nessuno gioca a breve", systemImage: "figure.soccer") }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 2) {
                Text("Chi gioca").font(.headline)
                if giocano.isEmpty { Text("Nessuno a breve").font(.caption) }
                ForEach(giocano.prefix(2)) { g in Text("\(g.cognome) · \(g.oraBreve)").font(.caption).lineLimit(1) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        case .systemExtraLarge:
            VStack(alignment: .leading, spacing: 6) {
                IntestazioneWidget(titolo: "Chi gioca", icona: "figure.soccer", destra: w.etichettaGiornata)
                HStack(alignment: .top, spacing: 24) {
                    colonna(Array(giocano.prefix(6)))
                    colonna(Array(giocano.dropFirst(6)))
                }
                Spacer(minLength: 0)
                PiedeDati(voce: voce)
            }
        default:
            VStack(alignment: .leading, spacing: 6) {
                IntestazioneWidget(titolo: "Chi gioca", icona: "figure.soccer", destra: w.etichettaGiornata)
                if giocano.isEmpty {
                    Spacer(minLength: 0)
                    Text("Nessuno gioca a breve").font(.headline)
                    Spacer(minLength: 0)
                } else {
                    colonna(giocano)
                }
                Spacer(minLength: 0)
                PiedeDati(voce: voce)
            }
        }
    }

    private func colonna(_ lista: [GiocatoreWidget]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(lista) { g in
                Link(destination: URL(string: "schieraxi://giocatore/\(g.id)") ?? URL(fileURLWithPath: "/")) { riga(g) }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func riga(_ g: GiocatoreWidget) -> some View {
        HStack(spacing: 8) {
            AvatarMini(g: g, lato: 26)
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 4) {
                    Text(g.nome).font(.subheadline.weight(.semibold)).lineLimit(1)
                    if g.rigorista == true { Image(systemName: "target").font(.caption2).foregroundStyle(TintaWidget.lime) }
                    if g.titolare == false, g.stato == nil { Text("panchina").fontWidget(9).foregroundStyle(TintaWidget.testo2) }
                }
                let stato = g.descrizioneStato
                Text(stato.isEmpty ? g.partitaBreve : "\(g.partitaBreve) · \(stato)")
                    .font(.caption2)
                    .foregroundStyle(!stato.isEmpty || g.diffidato == true ? TintaWidget.attenzione : TintaWidget.testo2)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
            Text(g.oraBreve).font(.subheadline.weight(.semibold)).monospacedDigit()
        }
        .frame(minHeight: 30)
    }
}
