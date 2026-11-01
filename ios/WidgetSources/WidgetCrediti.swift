import WidgetKit
import SwiftUI

/// Widget «Crediti e svincolo»: i crediti residui e il miglior svincolo (entra uno svincolato, esce uno dei tuoi) se il server ce l'ha già.
/// Misure: piccolo (crediti), medio (crediti e svincolo), cerchio, rettangolo, riga. Grande ed extra large non servono: è un dato solo.
struct WidgetCrediti: Widget {
    let kind = "SchieraxiCrediti"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaCrediti(voce: voce)
        }
        .configurationDisplayName("Crediti e svincolo")
        .description("I tuoi crediti residui e lo svincolo che conviene di più.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct VistaCrediti: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    let voce: Voce

    private var accessorio: Bool {
        switch famiglia {
        case .accessoryCircular, .accessoryRectangular, .accessoryInline: return true
        default: return false
        }
    }

    var body: some View {
        Group {
            if let w = voce.completo, let crediti = w.creditiResidui {
                contenuto(w, crediti)
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(voce.tocco(URL(string: "schieraxi://mercato")))
    }

    private func intero(_ x: Double) -> String { String(Formato.intero(x)) }

    @ViewBuilder
    private func contenuto(_ w: RiassuntoWidget, _ crediti: Double) -> some View {
        switch famiglia {
        case .systemMedium: medio(w, crediti)
        case .accessoryCircular:
            ZStack {
                AccessoryWidgetBackground()
                VStack(spacing: 0) {
                    Text(intero(crediti)).font(.headline.bold()).minimumScaleFactor(0.6)
                    Text("crediti").fontWidget(9)
                }
            }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 2) {
                Text("Crediti \(intero(crediti))").font(.headline)
                if let s = w.svincolato, let e = s.entra, let g = s.guadagno {
                    Text("Svincolo: \(e.cognome) \(Formato.conSegno(g))").font(.caption).lineLimit(1)
                } else {
                    Text("Nessuno svincolo calcolato").font(.caption).foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        case .accessoryInline:
            Label("Crediti \(intero(crediti))", systemImage: "eurosign.circle")
        default: piccolo(w, crediti)
        }
    }

    private func piccolo(_ w: RiassuntoWidget, _ crediti: Double) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            IntestazioneWidget(titolo: "Crediti", icona: "eurosign.circle")
            Spacer(minLength: 0)
            Text(intero(crediti)).fontWidget(44, weight: .bold, design: .rounded).minimumScaleFactor(0.5).lineLimit(1).monospacedDigit()
            Text("crediti residui").font(.caption2).foregroundStyle(TintaWidget.testo2)
            if let g = w.svincolato?.guadagno {
                Label("svincolo \(Formato.conSegno(g))", systemImage: "arrow.triangle.swap").font(.caption2).foregroundStyle(TintaWidget.lime)
            } else { PiedeDati(voce: voce) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func medio(_ w: RiassuntoWidget, _ crediti: Double) -> some View {
        HStack(alignment: .center, spacing: 14) {
            VStack(alignment: .leading, spacing: 2) {
                IntestazioneWidget(titolo: "Crediti", icona: "eurosign.circle")
                Spacer(minLength: 0)
                Text(intero(crediti)).fontWidget(44, weight: .bold, design: .rounded).minimumScaleFactor(0.5).lineLimit(1).monospacedDigit()
                Text("crediti residui").font(.caption2).foregroundStyle(TintaWidget.testo2)
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: 130, alignment: .leading)
            Link(destination: URL(string: "schieraxi://mercato") ?? URL(fileURLWithPath: "/")) { svincolo(w) }
        }
    }

    @ViewBuilder
    private func svincolo(_ w: RiassuntoWidget) -> some View {
        if let s = w.svincolato, let entra = s.entra {
            VStack(alignment: .leading, spacing: 4) {
                Text("Svincolo consigliato").font(.caption.weight(.semibold)).foregroundStyle(TintaWidget.testo2)
                HStack(spacing: 8) {
                    AvatarMini(g: entra, lato: 34)
                    VStack(alignment: .leading, spacing: 0) {
                        Text(entra.nome).font(.subheadline.weight(.semibold)).lineLimit(1)
                        if let esce = s.esce {
                            Text("al posto di \(esce.cognome)").font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                        }
                    }
                }
                HStack {
                    Text(Formato.conSegno(s.guadagno ?? 0)).font(.title3.bold()).foregroundStyle(TintaWidget.lime).monospacedDigit()
                    Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
                if s.fattibile == false {
                    Label("i crediti non bastano", systemImage: "exclamationmark.triangle.fill").font(.caption2).foregroundStyle(TintaWidget.attenzione)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            VStack(alignment: .leading, spacing: 4) {
                Text("Svincolo consigliato").font(.caption.weight(.semibold)).foregroundStyle(TintaWidget.testo2)
                Text("Apri Squadra > Cambi consigliati").font(.subheadline)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
