import WidgetKit
import SwiftUI

/// Widget «Da controllare»: i giocatori della formazione consigliata con un dubbio, un infortunio o una squalifica.
/// Ogni riga porta alla scheda del giocatore (`schieraxi://giocatore/<id>`), il resto del widget a Oggi.
/// Famiglie: medio e grande (Home, anche su iPad) e rettangolo (Schermata di blocco).
struct WidgetDubbi: Widget {
    let kind = "SchieraxiDubbi"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaDubbi(voce: voce)
        }
        .configurationDisplayName("Da controllare")
        .description("Chi della tua formazione ha un dubbio, un infortunio o una squalifica. Tocca un nome per aprire la sua scheda.")
        .supportedFamilies([.systemMedium, .systemLarge, .accessoryRectangular])
    }
}

struct VistaDubbi: View {
    @Environment(\.widgetFamily) private var famiglia
    let voce: Voce

    private var accessorio: Bool { famiglia == .accessoryRectangular }

    private var massimo: Int {
        switch famiglia {
        case .systemLarge: return 6
        case .systemMedium: return 3
        default: return 2
        }
    }

    var body: some View {
        Group {
            if let r = voce.riassunto {
                if accessorio { rettangolare(r) } else { contenuto(r) }
            } else {
                senzaDati
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(URL(string: "schieraxi://oggi"))
    }

    // MARK: Home

    private func contenuto(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Label("Da controllare", systemImage: r.daControllare > 0 ? "exclamationmark.triangle.fill" : "checkmark.seal.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(r.daControllare > 0 ? Color.orange : .white.opacity(0.85))
                Spacer()
                Text("Giornata \(r.giornata)").font(.caption2).foregroundStyle(.white.opacity(0.7))
            }
            if r.daControllare == 0 {
                Spacer(minLength: 0)
                Text("Nessun dubbio in formazione").font(.headline)
                Text(r.probabili == false ? "Le probabili non sono ancora uscite." : "Tutti i titolari sono a posto.")
                    .font(.caption).foregroundStyle(.white.opacity(0.8))
                Spacer(minLength: 0)
            } else if let dubbi = r.dubbi, !dubbi.isEmpty {
                ForEach(dubbi.prefix(massimo)) { d in
                    Link(destination: URL(string: "schieraxi://giocatore/\(d.id)") ?? URL(fileURLWithPath: "/")) { riga(d) }
                }
                if dubbi.count > massimo {
                    Text("e altri \(dubbi.count - massimo)").font(.caption2).foregroundStyle(.white.opacity(0.7))
                }
                Spacer(minLength: 0)
            } else {
                Spacer(minLength: 0)
                Text("\(r.daControllare) da controllare").font(.title3.bold())
                Text("Apri SchieraXI per i nomi.").font(.caption).foregroundStyle(.white.opacity(0.8))
                Spacer(minLength: 0)
            }
            if voce.datiSalvati {
                Label("dati delle \(r.scaricatoIl.formatted(date: .omitted, time: .shortened))", systemImage: "icloud.slash")
                    .font(.caption2).foregroundStyle(.white.opacity(0.7))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func riga(_ d: DubbioRiassunto) -> some View {
        HStack(spacing: 8) {
            Text(d.ruolo ?? "·")
                .font(.caption2.weight(.bold))
                .frame(width: 20, height: 20)
                .background(Circle().fill(.white.opacity(0.18)))
            VStack(alignment: .leading, spacing: 0) {
                Text(d.nome).font(.subheadline.weight(.semibold)).lineLimit(1)
                Text(d.descrizione).font(.caption2).foregroundStyle(.white.opacity(0.75)).lineLimit(1)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.white.opacity(0.5))
        }
        .frame(minHeight: 32)
    }

    // MARK: Schermata di blocco

    private func rettangolare(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(r.daControllare > 0 ? "Da controllare: \(r.daControllare)" : "Formazione a posto").font(.headline)
            if let dubbi = r.dubbi, !dubbi.isEmpty {
                ForEach(dubbi.prefix(2)) { d in
                    Text("\(d.nome) · \(d.descrizione)").font(.caption2).lineLimit(1)
                }
            } else {
                Text("Giornata \(r.giornata)").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var senzaDati: some View {
        VStack(spacing: 4) {
            Image(systemName: voce.indirizzoMancante ? "server.rack" : "wifi.exclamationmark")
            Text(voce.indirizzoMancante ? "Manca il server" : "Nessun dato").font(.caption.bold())
            if !accessorio {
                Text("Lega > Widget > Copia il codice, poi Modifica widget")
                    .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
        }
    }
}
