import WidgetKit
import SwiftUI

/// Widget «Punti attesi e fatti»: quanto ha fatto la formazione schierata (o la consigliata) contro quanto il modello aveva previsto,
/// giornata per giornata (dal diario). Serve a fidarsi, o no, delle previsioni.
/// Misure: piccolo (ultima giornata), medio (grafico), grande (grafico e tabella), cerchio, rettangolo, riga.
struct WidgetPunti: Widget {
    let kind = "SchieraxiPunti"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaPunti(voce: voce)
        }
        .configurationDisplayName("Punti attesi e fatti")
        .description("Quanto hai fatto contro quanto era previsto, nelle ultime giornate.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct VistaPunti: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }
    let voce: Voce

    private var accessorio: Bool {
        switch famiglia {
        case .accessoryCircular, .accessoryRectangular, .accessoryInline: return true
        default: return false
        }
    }

    var body: some View {
        Group {
            if let w = voce.completo, let ultima = w.giornateGiocate.first {
                contenuto(w, ultima)
            } else if voce.completo != nil {
                vuoto
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(Vai.url("lega"))
    }

    /// Il server c'e' ma non ci sono ancora giornate giocate nel diario.
    private var vuoto: some View {
        VStack(alignment: .leading, spacing: 4) {
            TitoloBlocco(testo: "Attesi e fatti", icona: "chart.bar.fill")
            Spacer(minLength: 0)
            Text("Ancora niente").font(.headline)
            if !accessorio {
                Text("Compare dopo la prima giornata giocata.").font(.caption).foregroundStyle(TintaWidget.testo2)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    private func scartoTesto(_ g: PuntiGiornata) -> String { GraficoPunti.scarto(g).map { Formato.conSegno($0) } ?? "—" }

    @ViewBuilder
    private func contenuto(_ w: RiassuntoWidget, _ g: PuntiGiornata) -> some View {
        switch famiglia {
        case .systemMedium: medio(w, g)
        case .systemLarge: grande(w, g)
        case .accessoryCircular:
            ZStack {
                AccessoryWidgetBackground()
                VStack(spacing: 0) {
                    Text("G\(g.giornata)").fontWidget(10)
                    Text(scartoTesto(g)).font(.headline.bold()).minimumScaleFactor(0.6).lineLimit(1).monospacedDigit()
                    Text("sul previsto").fontWidget(8)
                }
            }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 2) {
                Text("Giornata \(g.giornata): \(Formato.punti(g.fatti)) punti").font(.headline).lineLimit(1)
                Text("attesi \(Formato.punti(g.attesi)) · \(scartoTesto(g))").font(.caption).monospacedDigit()
                GraficoPunti(giornate: w.giornateGiocate, altezza: 14, conEtichette: false)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        case .accessoryInline:
            Label("G\(g.giornata) \(Formato.punti(g.fatti)) fatti, \(Formato.punti(g.attesi)) attesi", systemImage: "chart.bar")
        default: piccolo(w, g)
        }
    }

    private func intestazione(_ g: PuntiGiornata) -> some View {
        IntestazioneWidget(titolo: "Attesi e fatti", icona: "chart.bar.fill", destra: "G\(g.giornata)")
    }

    private func piccolo(_ w: RiassuntoWidget, _ g: PuntiGiornata) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            intestazione(g)
            Spacer(minLength: 0)
            Text(Formato.punti(g.fatti)).font(.system(.largeTitle, design: .rounded).weight(.bold)).monospacedDigit()
                .lineLimit(1).minimumScaleFactor(0.6)
                .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
            Text("fatti, attesi \(Formato.punti(g.attesi))").font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
            Text("\(scartoTesto(g)) sul previsto").font(.caption.weight(.semibold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
            if let f = g.fasciaTesto { Text(f).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
            GraficoPunti(giornate: w.giornateGiocate, altezza: 14, conEtichette: false, massimo: 5).padding(.top, 2).padding(.bottom, 4)
            PiedeDati(voce: voce)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func medio(_ w: RiassuntoWidget, _ g: PuntiGiornata) -> some View {
        HStack(alignment: .center, spacing: 14) {
            VStack(alignment: .leading, spacing: 2) {
                intestazione(g)
                Spacer(minLength: 0)
                Text(Formato.punti(g.fatti)).font(.system(.largeTitle, design: .rounded).weight(.bold)).monospacedDigit()
                    .lineLimit(1).minimumScaleFactor(0.6)
                    .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                Text("fatti, attesi \(Formato.punti(g.attesi))").font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                Text("\(scartoTesto(g)) sul previsto").font(.caption.weight(.semibold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
                if let f = g.fasciaTesto { Text(f).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: 140, alignment: .leading)
            VStack(alignment: .leading, spacing: 4) {
                GraficoPunti(giornate: w.giornateGiocate, altezza: 70)
                legenda
            }
        }
    }

    private var legenda: some View {
        HStack(spacing: 10) {
            Label("attesi", systemImage: "square.fill").foregroundStyle(.white.opacity(0.45))
            Label("fatti", systemImage: "square.fill").foregroundStyle(TintaWidget.accento(modo))
        }
        .fontWidget(9)
        .labelStyle(.titleAndIcon)
        .accessibilityHidden(true)
    }

    private func grande(_ w: RiassuntoWidget, _ g: PuntiGiornata) -> some View {
        let giornate = Array(w.giornateGiocate.prefix(5))
        let scarti = giornate.compactMap(GraficoPunti.scarto)
        let media = scarti.isEmpty ? nil : scarti.reduce(0, +) / Double(scarti.count)
        return VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline) {
                Text(Formato.punti(g.fatti)).font(.system(.largeTitle, design: .rounded).weight(.bold)).monospacedDigit()
                    .lineLimit(1).minimumScaleFactor(0.6)
                    .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                Text("fatti alla giornata \(g.giornata), attesi \(Formato.punti(g.attesi))").font(.subheadline).foregroundStyle(TintaWidget.testo2)
                    .lineLimit(2)
                Spacer(minLength: 0)
            }
            GraficoPunti(giornate: giornate, altezza: 80)
            legenda
            VStack(spacing: 3) {
                ForEach(giornate) { x in
                    HStack {
                        Text("Giornata \(x.giornata)").font(.footnote)
                        if let f = x.fasciaTesto { Text(f).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
                        Spacer()
                        Text("\(Formato.punti(x.fatti)) su \(Formato.punti(x.attesi))").font(.footnote).monospacedDigit()
                        Text(scartoTesto(x)).font(.footnote.weight(.semibold)).monospacedDigit().frame(width: 52, alignment: .trailing)
                    }
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(GraficoPunti.descrizione(x))
                }
            }
            if case let (dentro, su) = RiassuntoWidget.quanteDentro(giornate), su > 0 {
                Text("Dentro la fascia prevista in \(dentro) giornate su \(su).")
                    .font(.caption).foregroundStyle(TintaWidget.testo2)
            }
            if let media {
                Text("In media \(Formato.conSegno(media)) punti sul previsto nelle ultime \(scarti.count) giornate.")
                    .font(.caption).foregroundStyle(TintaWidget.testo2)
            }
            Spacer(minLength: 0)
            PiedeDati(voce: voce)
        }
    }
}
