import WidgetKit
import SwiftUI

/// Widget «Formazione consigliata»: modulo, punti attesi e i titolari sul campo (con i volti illustrati).
/// Misure: piccolo (modulo e punti), medio (dato + campo mini), grande (campo con i cognomi), extra large per iPad (campo e lista),
/// schermata di blocco: cerchio, rettangolo, riga. Ogni volto apre la scheda del giocatore, il resto la Formazione.
struct WidgetFormazione: Widget {
    let kind = "SchieraxiFormazione"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaFormazione(voce: voce)
        }
        .configurationDisplayName("Formazione consigliata")
        .description("Il modulo, i punti attesi e i tuoi undici titolari. Tocca un volto per aprire la sua scheda.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .systemExtraLarge,
                            .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

/// I titolari disposti per reparto: portiere in alto, attaccanti in basso (come nel campo dell'app).
struct CampoMini: View {
    let titolari: [GiocatoreWidget]
    var lato: CGFloat = 22
    var conNomi = false

    private var righe: [[GiocatoreWidget]] {
        ["P", "D", "C", "A"].map { r in titolari.filter { ($0.ruolo ?? "").uppercased() == r } }.filter { !$0.isEmpty }
    }

    var body: some View {
        VStack(spacing: conNomi ? 6 : 3) {
            ForEach(Array(righe.enumerated()), id: \.offset) { _, riga in
                HStack(spacing: conNomi ? 8 : 4) {
                    ForEach(riga) { g in
                        Link(destination: URL(string: "schieraxi://giocatore/\(g.id)") ?? URL(fileURLWithPath: "/")) {
                            VStack(spacing: 1) {
                                AvatarMini(g: g, lato: lato)
                                if conNomi {
                                    Text(g.cognome).font(.system(size: 9, weight: .semibold)).lineLimit(1).minimumScaleFactor(0.7)
                                }
                            }
                            .frame(maxWidth: .infinity)
                        }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity)
    }
}

struct VistaFormazione: View {
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
            if let w = voce.completo, let f = w.formazione, let tit = f.titolari, !tit.isEmpty {
                contenuto(w, f, tit)
            } else if let r = voce.riassunto, r.modulo != nil {
                // un server senza /api/widget: solo modulo e punti
                contenutoMinimo(r)
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(URL(string: "schieraxi://formazione"))
    }

    private func punti(_ f: FormazioneWidget) -> String { Formato.punti(f.puntiAttesi) }

    @ViewBuilder
    private func contenuto(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        switch famiglia {
        case .systemSmall: piccolo(w, f)
        case .systemMedium: medio(w, f, tit)
        case .systemLarge: grande(w, f, tit)
        case .systemExtraLarge: grandissimo(w, f, tit)
        case .accessoryCircular: circolare(f)
        case .accessoryRectangular: rettangolare(w, f)
        case .accessoryInline: Label("SchieraXI \(f.modulo ?? "—") · \(punti(f))", systemImage: "sportscourt")
        default: piccolo(w, f)
        }
    }

    private func contenutoMinimo(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            IntestazioneWidget(titolo: "Formazione", icona: "sportscourt", destra: "G\(r.giornata)")
            Spacer(minLength: 0)
            Text(r.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold))
            Text("\(Formato.punti(r.punti)) punti attesi").font(.caption).foregroundStyle(TintaWidget.testo2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Home

    private func piccolo(_ w: RiassuntoWidget, _ f: FormazioneWidget) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            IntestazioneWidget(titolo: "Formazione", icona: "sportscourt", destra: w.giornata.map { "G\($0)" })
            Spacer(minLength: 0)
            Text(f.modulo ?? "—").font(.system(size: 38, weight: .bold, design: .rounded)).minimumScaleFactor(0.6).lineLimit(1)
            Text(punti(f)).font(.title3.bold()).monospacedDigit()
            Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
            if !w.daControllare.isEmpty {
                Label("\(w.daControllare.count) da controllare", systemImage: "exclamationmark.triangle.fill")
                    .font(.caption2).foregroundStyle(TintaWidget.attenzione)
            } else {
                PiedeDati(voce: voce)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func medio(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                IntestazioneWidget(titolo: "Formazione", icona: "sportscourt")
                Spacer(minLength: 0)
                Text(f.modulo ?? "—").font(.system(size: 36, weight: .bold, design: .rounded)).minimumScaleFactor(0.6).lineLimit(1)
                Text(punti(f)).font(.title3.bold()).monospacedDigit()
                Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
                Spacer(minLength: 0)
                if !w.daControllare.isEmpty {
                    Label("\(w.daControllare.count) da controllare", systemImage: "exclamationmark.triangle.fill")
                        .font(.caption2).foregroundStyle(TintaWidget.attenzione)
                } else { PiedeDati(voce: voce) }
            }
            .frame(maxWidth: 120, alignment: .leading)
            CampoMini(titolari: tit, lato: 24)
        }
    }

    private func grande(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        VStack(spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(f.modulo ?? "—").font(.system(size: 34, weight: .bold, design: .rounded))
                Text("\(punti(f)) punti attesi").font(.subheadline).monospacedDigit().foregroundStyle(TintaWidget.testo2)
                Spacer()
                if let g = w.giornata { Text("Giornata \(g)").font(.caption).foregroundStyle(TintaWidget.testo2) }
            }
            CampoMini(titolari: tit, lato: 40, conNomi: true)
            HStack {
                if !w.daControllare.isEmpty {
                    Label("\(w.daControllare.count) da controllare", systemImage: "exclamationmark.triangle.fill").foregroundStyle(TintaWidget.attenzione)
                }
                Spacer()
                if let n = f.panchina?.count { Text("\(n) in panchina").foregroundStyle(TintaWidget.testo2) }
            }
            .font(.caption)
            PiedeDati(voce: voce)
        }
    }

    private func grandissimo(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        HStack(alignment: .top, spacing: 20) {
            VStack(spacing: 8) {
                HStack(alignment: .firstTextBaseline) {
                    Text(f.modulo ?? "—").font(.system(size: 40, weight: .bold, design: .rounded))
                    Text("\(punti(f)) punti attesi").font(.headline).monospacedDigit().foregroundStyle(TintaWidget.testo2)
                    Spacer()
                }
                CampoMini(titolari: tit, lato: 48, conNomi: true)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("Titolari").font(.caption.weight(.semibold)).foregroundStyle(TintaWidget.testo2)
                ForEach(tit) { g in
                    Link(destination: URL(string: "schieraxi://giocatore/\(g.id)") ?? URL(fileURLWithPath: "/")) {
                        HStack(spacing: 8) {
                            AvatarMini(g: g, lato: 22)
                            Text(g.nome).font(.subheadline).lineLimit(1)
                            Spacer(minLength: 4)
                            Text(Formato.punti(g.puntiAttesi)).font(.subheadline.weight(.semibold)).monospacedDigit()
                        }
                    }
                }
                Spacer(minLength: 0)
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: 300)
        }
    }

    // MARK: Schermata di blocco

    private func circolare(_ f: FormazioneWidget) -> some View {
        ZStack {
            AccessoryWidgetBackground()
            VStack(spacing: 0) {
                Text(f.modulo ?? "—").font(.caption.bold()).minimumScaleFactor(0.6).lineLimit(1)
                Text(punti(f)).font(.caption2).monospacedDigit()
            }
        }
    }

    private func rettangolare(_ w: RiassuntoWidget, _ f: FormazioneWidget) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Formazione \(f.modulo ?? "—")").font(.headline)
            Text("\(punti(f)) punti attesi").font(.caption).monospacedDigit()
            if !w.daControllare.isEmpty {
                Text("\(w.daControllare.count) da controllare").font(.caption2)
            } else if let g = w.giornata {
                Text("Giornata \(g)").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
