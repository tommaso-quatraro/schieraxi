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
        .widgetURL(voce.tocco(Vai.url("lega")))
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
            CerchioWidget {
                Text(g.sigla).fontWidget(10)
                Text(scartoTesto(g)).font(.headline.bold()).minimumScaleFactor(0.6).lineLimit(1).monospacedDigit()
                // con il testo grande si rimpicciolisce invece di uscire dal cerchio
                Text("sul previsto").fontWidget(8).lineLimit(1).minimumScaleFactor(0.6)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(g.descrizione)
        case .accessoryRectangular:
            // «Giornata 7: 63,5 punti» → «G7: 63,5 punti» → «G7: 63,5»; un'altra stagione sempre con la stagione («G38 · 2025-26»)
            VStack(alignment: .leading, spacing: 2) {
                TestoCheEntra(g.formeTitolo).font(.headline)
                Text("attesi \(Formato.punti(g.attesi)) · \(scartoTesto(g))").font(.caption).monospacedDigit()
                GraficoPunti(giornate: w.giornateGiocate, altezza: 14, conEtichette: false)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(g.descrizione)
        case .accessoryInline:
            let forme = g.formeInLinea
            PrimaCheEntra(forme.count) { i in
                Label(forme[i], systemImage: "chart.bar")
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(g.descrizione)
        default: piccolo(w, g)
        }
    }

    /// «Attesi e fatti» e a destra la giornata nella forma corta che entra («Giornata 7», poi «G7»; #299).
    private func intestazione(_ g: PuntiGiornata) -> some View {
        IntestazioneWidget(titolo: "Attesi e fatti", icona: "chart.bar.fill", giornata: g.nome, soloCorta: true)
    }

    private func piccolo(_ w: RiassuntoWidget, _ g: PuntiGiornata) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            // testata e numeri: per VoiceOver una frase sola, con i due numeri della giornata (`voceWidget`)
            VStack(alignment: .leading, spacing: 2) {
                intestazione(g)
                Spacer(minLength: 0)
                Text(Formato.punti(g.fatti)).font(.system(.largeTitle, design: .rounded).weight(.bold)).monospacedDigit()
                    .lineLimit(1).minimumScaleFactor(0.6)
                    .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                Text("fatti, attesi \(Formato.punti(g.attesi))").font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                Text("\(scartoTesto(g)) sul previsto").font(.caption.weight(.semibold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
                if let f = g.fasciaTesto { Text(f).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(g.voceWidget)
            GraficoPunti(giornate: w.giornateGiocate, altezza: 14, conEtichette: false, massimo: 5).padding(.top, 2).padding(.bottom, 4)
            PiedeDati(voce: voce)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func medio(_ w: RiassuntoWidget, _ g: PuntiGiornata) -> some View {
        HStack(alignment: .center, spacing: 14) {
            VStack(alignment: .leading, spacing: 2) {
                VStack(alignment: .leading, spacing: 2) {
                    intestazione(g)
                    Spacer(minLength: 0)
                    Text(Formato.punti(g.fatti)).font(.system(.largeTitle, design: .rounded).weight(.bold)).monospacedDigit()
                        .lineLimit(1).minimumScaleFactor(0.6)
                        .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                    Text("fatti, attesi \(Formato.punti(g.attesi))").font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                    Text("\(scartoTesto(g)) sul previsto").font(.caption.weight(.semibold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
                    if let f = g.fasciaTesto { Text(f).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(g.voceWidget)
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
        let (dentro, su) = RiassuntoWidget.quanteDentro(giornate)
        // le frasi di riepilogo, la più utile prima
        let frasi = [su > 0 ? RiassuntoWidget.fraseDentro(dentro: dentro, su: su) : nil,
                     media.map { RiassuntoWidget.fraseMedia($0, giornate: scarti.count) }].compactMap { $0 }
        let prove = DisposizioneWidget.provePuntiGrande(righe: giornate.count, frasi: frasi.count)
        return VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline) {
                Text(Formato.punti(g.fatti)).font(.system(.largeTitle, design: .rounded).weight(.bold)).monospacedDigit()
                    .lineLimit(1).minimumScaleFactor(0.6)
                    .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                // va a capo intera anche con il testo grande: mai «attesi 6…». La giornata in testa con i due numeri (#299)
                Text("\(g.titolo): fatti, attesi \(Formato.punti(g.attesi))")
                    .font(.subheadline).foregroundStyle(TintaWidget.testo2)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityLabel(g.descrizione)
                Spacer(minLength: 0)
            }
            GraficoPunti(giornate: giornate, altezza: 80)
            legenda
            // sotto il grafico quello che entra in altezza: prima via le frasi di riepilogo, poi le righe più vecchie (niente tagli)
            PrimaCheEntra(prove.count, in: .vertical) { i in
                VStack(alignment: .leading, spacing: 5) {
                    tabella(Array(giornate.prefix(prove[i].righe)))
                    ForEach(frasi.prefix(prove[i].frasi), id: \.self) { frase in
                        Text(frase).font(.caption).foregroundStyle(TintaWidget.testo2).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .frame(maxHeight: .infinity, alignment: .top)
            PiedeDati(voce: voce)
        }
    }

    /// La tabella delle ultime giornate, con la stessa forma per tutte le righe: prima «G7» al posto di «Giornata 7», poi via la
    /// fascia, poi solo i fatti (mai «dentro la fa…» né «63,5 su 6…»); VoiceOver legge ogni riga intera.
    private func tabella(_ giornate: [PuntiGiornata]) -> some View {
        PrimaCheEntra(PuntiGiornata.FormaRiga.allCases.count) { i in
            VStack(spacing: 3) {
                ForEach(giornate) { x in
                    RigaTabellaPunti(giornata: x, forma: PuntiGiornata.FormaRiga.allCases[i], scarto: scartoTesto(x))
                }
            }
        }
    }
}
