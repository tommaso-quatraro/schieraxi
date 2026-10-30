import WidgetKit
import SwiftUI
import UIKit

/// Widget «Prossima giornata»: conto alla rovescia alla prima partita, modulo e punti attesi.
/// Famiglie: piccolo e medio (Schermata Home), cerchio, rettangolo e riga (Schermata di blocco).
@main
struct WidgetOggi: Widget {
    let kind = "SchieraxiOggi"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Fornitore()) { voce in
            VistaWidget(voce: voce)
        }
        .configurationDisplayName("Prossima giornata")
        .description("Conto alla rovescia alla prima partita, modulo consigliato e punti attesi.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

extension View {
    /// Sfondo del widget: sulla Home un gradiente verde profondo con testo bianco (lo stesso del riquadro di «Oggi» nell'app),
    /// sulla schermata di blocco niente sfondo (lo mette iOS).
    @ViewBuilder
    func sfondoWidget(accessorio: Bool) -> some View {
        if accessorio {
            self.containerBackground(for: .widget) { Color.clear }
        } else {
            self
                .foregroundStyle(.white)
                .containerBackground(for: .widget) {
                    LinearGradient(
                        colors: [Color(red: 0.05, green: 0.42, blue: 0.30), Color(red: 0.02, green: 0.22, blue: 0.26)],
                        startPoint: .topLeading, endPoint: .bottomTrailing)
                }
        }
    }
}

struct VistaWidget: View {
    @Environment(\.widgetFamily) private var famiglia
    let voce: Voce

    private var accessorio: Bool {
        switch famiglia {
        case .accessoryCircular, .accessoryRectangular, .accessoryInline: return true
        default: return false
        }
    }

    var body: some View {
        Group {
            if let r = voce.riassunto {
                switch famiglia {
                case .systemMedium: medio(r)
                case .accessoryCircular: circolare(r)
                case .accessoryRectangular: rettangolare(r)
                case .accessoryInline: riga(r)
                default: piccolo(r)
                }
            } else {
                senzaDati
            }
        }
        .sfondoWidget(accessorio: accessorio)
        // Un tocco sul widget apre l'app sulla formazione.
        .widgetURL(URL(string: "schieraxi://formazione"))
    }

    // MARK: pezzi comuni

    private func inCorso(_ r: RiassuntoOggi) -> Bool {
        guard let inizio = r.inizio else { return false }
        return inizio <= voce.date
    }

    private func puntiTesto(_ r: RiassuntoOggi) -> String {
        Formato.punti(r.punti)
    }

    /// Conto alla rovescia: ore, minuti e secondi se manca meno di un giorno, altrimenti giorni e ore.
    @ViewBuilder
    private func conto(_ r: RiassuntoOggi) -> some View {
        if let inizio = r.inizio, inizio > voce.date {
            if inizio.timeIntervalSince(voce.date) < 24 * 3600 {
                Text(timerInterval: voce.date...inizio, countsDown: true).monospacedDigit()
            } else {
                Text(inizio, style: .relative)
            }
        } else {
            Text(r.inizio == nil ? "—" : "In corso")
        }
    }

    private var senzaDati: some View {
        VStack(spacing: 4) {
            Image(systemName: voce.accessoRichiesto ? "person.crop.circle.badge.questionmark" : "wifi.exclamationmark")
            Text(voce.accessoRichiesto ? "Serve l'accesso" : "Nessun dato").font(.caption.bold())
            if !accessorio {
                Text(voce.accessoRichiesto ? "Apri SchieraXI per accedere" : "Apri SchieraXI con rete privata acceso")
                    .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
        }
    }

    // MARK: Schermata Home

    private func piccolo(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Giornata \(r.giornata)", systemImage: "calendar").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
            conto(r)
                .font(.system(.title, design: .rounded).weight(.bold))
                .minimumScaleFactor(0.5)
                .lineLimit(1)
            Spacer(minLength: 0)
            HStack(alignment: .firstTextBaseline) {
                Text(r.modulo ?? "—").font(.headline)
                Spacer()
                Text(puntiTesto(r)).font(.title3.bold()).monospacedDigit()
            }
            Text(voce.datiSalvati ? "dati salvati" : "punti attesi").font(.caption2).foregroundStyle(.white.opacity(0.75))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func medio(_ r: RiassuntoOggi) -> some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Label("Giornata \(r.giornata)", systemImage: "calendar").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
                conto(r)
                    .font(.system(.largeTitle, design: .rounded).weight(.bold))
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text(r.inizio.map { "alla prima partita, \(Quando.leggibile($0))" } ?? "")
                    .font(.caption).foregroundStyle(.white.opacity(0.8))
                Spacer(minLength: 0)
                if voce.datiSalvati {
                    Label("dati salvati", systemImage: "icloud.slash").font(.caption2).foregroundStyle(.secondary)
                }
            }
            VStack(alignment: .trailing, spacing: 4) {
                Label("Formazione", systemImage: "sportscourt").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
                Text(r.modulo ?? "—").font(.system(.title, design: .rounded).weight(.bold))
                Text("\(puntiTesto(r)) punti attesi").font(.caption).monospacedDigit().foregroundStyle(.white.opacity(0.9))
                Spacer(minLength: 0)
                if r.daControllare > 0 {
                    Label("\(r.daControllare) da controllare", systemImage: "exclamationmark.circle.fill")
                        .font(.caption).foregroundStyle(.orange)
                } else if r.probabili == false {
                    Label("probabili non uscite", systemImage: "clock").font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Schermata di blocco

    private func circolare(_ r: RiassuntoOggi) -> some View {
        ZStack {
            AccessoryWidgetBackground()
            VStack(spacing: 0) {
                Text("G\(r.giornata)").font(.caption2)
                Text(r.modulo ?? "—").font(.caption.bold()).minimumScaleFactor(0.6).lineLimit(1)
                Text(puntiTesto(r)).font(.caption2).monospacedDigit()
            }
        }
    }

    private func rettangolare(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Giornata \(r.giornata)").font(.caption2).foregroundStyle(.secondary)
            conto(r).font(.headline).lineLimit(1).minimumScaleFactor(0.7)
            Text("\(r.modulo ?? "—") · \(puntiTesto(r)) punti attesi").font(.caption2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func riga(_ r: RiassuntoOggi) -> some View {
        Label("SchieraXI \(r.modulo ?? "—"), \(puntiTesto(r)) punti", systemImage: "sportscourt")
    }
}
