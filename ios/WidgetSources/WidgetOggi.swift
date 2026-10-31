import WidgetKit
import SwiftUI
import UIKit

/// Widget «Prossima giornata»: conto alla rovescia alla prima partita, modulo e punti attesi.
/// Famiglie: piccolo e medio (Schermata Home), cerchio, rettangolo e riga (Schermata di blocco).

struct WidgetOggi: Widget {
    let kind = "SchieraxiOggi"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaWidget(voce: voce)
        }
        .configurationDisplayName("Prossima giornata")
        .description("Conto alla rovescia alla scadenza della formazione, modulo consigliato e punti attesi.")
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
                .modifier(TestoSuSfondoSchieraxi())
                .containerBackground(for: .widget) {
                    FondoSchieraxi()
                }
        }
    }
}

struct VistaWidget: View {
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
            Image(systemName: voce.indirizzoMancante ? "server.rack" : voce.accessoRichiesto ? "person.crop.circle.badge.questionmark" : "wifi.exclamationmark")
            Text(voce.indirizzoMancante ? "Manca il server" : voce.accessoRichiesto ? "Serve l'accesso" : "Nessun dato").font(.caption.bold())
            if !accessorio {
                Text(voce.indirizzoMancante ? "Impostazioni > Widget > Copia il codice, poi Modifica widget" : voce.accessoRichiesto ? "Impostazioni > Widget > Copia il codice, poi Modifica widget" : "Apri SchieraXI per aggiornare i dati")
                    .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
                if let d = voce.diagnostica {
                    Text(d).fontWidget(8).foregroundStyle(.secondary).multilineTextAlignment(.center).lineLimit(2)
                }
            }
        }
    }

    // MARK: Schermata Home

    private func piccolo(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label(r.etichettaGiornata, systemImage: "calendar").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).lineLimit(1).minimumScaleFactor(0.7)
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
            if voce.datiSalvati || (r.daControllare == 0 && r.probabili != false) {
                Text(voce.datiSalvati ? "dati delle \(r.scaricatoIl.formatted(date: .omitted, time: .shortened))" : "punti attesi").font(.caption2).foregroundStyle(.white.opacity(0.75))
            }
            if r.daControllare > 0 {
                Label("\(r.daControllare) da controllare", systemImage: "exclamationmark.triangle.fill").font(.caption2).foregroundStyle(TintaWidget.attenzione).lineLimit(1)
            } else if r.probabili == false {
                Label("probabili non uscite", systemImage: "clock").font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var conDubbi: Bool { !(voce.completo?.daControllare.isEmpty ?? true) }

    private func medio(_ r: RiassuntoOggi) -> some View {
        HStack(alignment: .top, spacing: 16) {
            // a sinistra (conto alla rovescia) si apre Oggi, a destra (formazione) la Formazione
            Link(destination: URL(string: "schieraxi://oggi") ?? URL(fileURLWithPath: "/")) {
            VStack(alignment: .leading, spacing: 4) {
                Label(r.etichettaGiornata, systemImage: "calendar").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).lineLimit(1).minimumScaleFactor(0.7)
                conto(r)
                    .font(.system(.largeTitle, design: .rounded).weight(.bold))
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text(r.inizio.map { "alla scadenza, \(Quando.leggibile($0))" } ?? "")
                    .font(.caption).foregroundStyle(.white.opacity(0.8))
                Spacer(minLength: 0)
                if voce.datiSalvati {
                    Label("dati delle \(r.scaricatoIl.formatted(date: .omitted, time: .shortened))", systemImage: "icloud.slash").font(.caption2).foregroundStyle(.secondary)
                }
            }
            }
            Link(destination: URL(string: "schieraxi://formazione") ?? URL(fileURLWithPath: "/")) {
            VStack(alignment: conDubbi ? .leading : .trailing, spacing: conDubbi ? 2 : 4) {
                Label("Formazione", systemImage: "sportscourt").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
                if conDubbi {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(r.modulo ?? "—").font(.system(.title2, design: .rounded).weight(.bold))
                        Text("\(puntiTesto(r)) punti").font(.caption).monospacedDigit().foregroundStyle(.white.opacity(0.9))
                    }
                } else {
                    Text(r.modulo ?? "—").font(.system(.title, design: .rounded).weight(.bold))
                    Text("\(puntiTesto(r)) punti attesi").font(.caption).monospacedDigit().foregroundStyle(.white.opacity(0.9))
                }
                Spacer(minLength: 0)
                if let w = voce.completo, !w.daControllare.isEmpty {
                    // i miei titolari con un dubbio, un infortunio o una squalifica (dati di /api/widget)
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(w.daControllare.prefix(2)) { g in RigaGiocatoreWidget(g: g, lato: 28, conLink: false) }
                        if w.daControllare.count > 2 {
                            Text("e altri \(w.daControllare.count - 2)").font(.caption2).foregroundStyle(TintaWidget.testo2)
                        }
                    }
                } else if r.daControllare > 0 {
                    Label("\(r.daControllare) da controllare", systemImage: "exclamationmark.circle.fill")
                        .font(.caption).foregroundStyle(.orange)
                } else if r.probabili == false {
                    Label("probabili non uscite", systemImage: "clock").font(.caption2).foregroundStyle(.secondary)
                }
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
                Text(r.siglaGiornata).font(.caption2)
                Text(r.modulo ?? "—").font(.caption.bold()).minimumScaleFactor(0.6).lineLimit(1)
                Text(puntiTesto(r)).font(.caption2).monospacedDigit()
            }
        }
    }

    private func rettangolare(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(r.etichettaGiornata).font(.caption2).foregroundStyle(.secondary).lineLimit(1).minimumScaleFactor(0.7)
            conto(r).font(.headline).lineLimit(1).minimumScaleFactor(0.7)
            Text("\(r.modulo ?? "—") · \(puntiTesto(r)) punti attesi").font(.caption2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func riga(_ r: RiassuntoOggi) -> some View {
        Label("SchieraXI \(r.modulo ?? "—"), \(puntiTesto(r)) punti", systemImage: "sportscourt")
    }
}

/// Colore del testo sul fondo SchieraXI. A colori pieni (Home, StandBy) e' bianco, come prima; nella modalita' colorata
/// (tinted/accented) e nello StandBy notturno non si forza il bianco: ci pensa il sistema, che tinge i numeri segnati con `widgetAccentable`.
private struct TestoSuSfondoSchieraxi: ViewModifier {
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    @Environment(\.showsWidgetContainerBackground) private var conSfondo

    func body(content: Content) -> some View {
        if (modoForzato ?? modoSistema) == .fullColor && conSfondo {
            content.foregroundStyle(.white)
        } else {
            content.foregroundStyle(.primary)
        }
    }
}
