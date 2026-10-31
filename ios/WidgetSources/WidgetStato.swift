import WidgetKit
import SwiftUI

/// Widget «Stato dati»: quando sono stati aggiornati i dati del server e se sono uscite le probabili. Serve a colpo d'occhio e per la
/// diagnosi. Misure: piccolo, rettangolo, cerchio e riga. Le misure grandi non servono: è un'informazione sola.
struct WidgetStato: Widget {
    let kind = "SchieraxiStato"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaStato(voce: voce)
        }
        .configurationDisplayName("Stato dei dati")
        .description("Quando il server ha aggiornato i dati e se sono uscite le probabili formazioni.")
        .supportedFamilies([.systemSmall, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct VistaStato: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    let voce: Voce

    private var accessorio: Bool { famiglia != .systemSmall }

    private var aggiornato: Date? { Quando.data(voce.completo?.dati?.ultimoAggiornamento) }

    private var oraDati: String { aggiornato.map { Quando.ora($0) } ?? "—" }

    private var probabili: String {
        switch voce.completo?.conProbabili ?? voce.riassunto?.probabili {
        case true?: return "probabili uscite"
        case false?: return "probabili non uscite"
        default: return "—"
        }
    }

    var body: some View {
        Group {
            if voce.completo != nil || voce.riassunto != nil {
                contenuto
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(URL(string: "schieraxi://lega"))
    }

    @ViewBuilder
    private var contenuto: some View {
        switch famiglia {
        case .accessoryInline:
            Label("Dati delle \(oraDati) · \(probabili)", systemImage: "externaldrive")
        case .accessoryCircular:
            ZStack {
                AccessoryWidgetBackground()
                VStack(spacing: 0) {
                    Image(systemName: "externaldrive").font(.caption2)
                    Text(oraDati).font(.caption.bold()).monospacedDigit().minimumScaleFactor(0.6)
                }
            }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 2) {
                Text("Dati delle \(oraDati)").font(.headline)
                Text(probabili).font(.caption)
                if let g = voce.completo?.etichettaGiornata ?? voce.riassunto?.etichettaGiornata { Text(g).font(.caption2).foregroundStyle(.secondary).lineLimit(1) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        default:
            VStack(alignment: .leading, spacing: 3) {
                IntestazioneWidget(titolo: "Dati", icona: "externaldrive")
                Spacer(minLength: 0)
                Text(oraDati).monospacedDigit().fontWidget(40, weight: .bold, design: .rounded).minimumScaleFactor(0.6)
                Text(aggiornato.map { $0.formatted(.relative(presentation: .named)) } ?? "aggiornamento sconosciuto")
                    .font(.caption).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                Label(probabili, systemImage: voce.completo?.conProbabili == true ? "checkmark.circle.fill" : "clock")
                    .font(.caption2).foregroundStyle(voce.completo?.conProbabili == true ? TintaWidget.lime : TintaWidget.attenzione)
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
