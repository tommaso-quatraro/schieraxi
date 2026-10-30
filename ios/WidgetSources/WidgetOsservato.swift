import WidgetKit
import SwiftUI
import AppIntents

// Widget «Giocatore osservato»: scegli tu quale (tra i tuoi osservati e i tuoi giocatori: tieni premuto > Modifica widget > Giocatore).
// Mostra punti attesi, voto atteso, la partita con l'orario e se e' in dubbio. Misure: piccolo, medio, cerchio, rettangolo, riga.
// L'elenco dei giocatori tra cui scegliere viene dall'ultimo riassunto salvato dal widget (si riempie al primo aggiornamento).

/// Un giocatore che si puo' scegliere nelle impostazioni del widget.
struct GiocatoreScelto: AppEntity {
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Giocatore"
    static var defaultQuery = QueryGiocatori()

    var id: Int
    var nome: String
    var ruolo: String?

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: LocalizedStringResource(stringLiteral: nome),
                              subtitle: ruolo.map { LocalizedStringResource(stringLiteral: $0) })
    }
}

struct QueryGiocatori: EntityQuery {
    /// Prima gli osservati, poi i miei giocatori, senza doppioni.
    private func elenco() -> [GiocatoreScelto] {
        guard let w = MemoriaWidget.leggi()?.riassunto else { return [] }
        var visti = Set<Int>()
        return ((w.osservati ?? []) + (w.rosa ?? [])).compactMap { g in
            guard visti.insert(g.id).inserted else { return nil }
            return GiocatoreScelto(id: g.id, nome: g.nome, ruolo: g.ruolo)
        }
    }

    func entities(for identifiers: [Int]) async throws -> [GiocatoreScelto] { elenco().filter { identifiers.contains($0.id) } }
    func suggestedEntities() async throws -> [GiocatoreScelto] { elenco() }
}

struct ConfigurazioneOsservato: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Giocatore osservato"
    static var description = IntentDescription("Il giocatore da seguire. Senza scelta si vede il primo dei tuoi osservati.")

    @Parameter(title: "Giocatore")
    var giocatore: GiocatoreScelto?

    @Parameter(title: "Indirizzo del server (solo se manca)", default: "")
    var indirizzo: String

    @Parameter(title: "Codice di collegamento", default: "")
    var codice: String
}

struct VoceOsservato: TimelineEntry {
    let date: Date
    let voce: Voce
    let scelto: Int?
}

/// Stessi dati e stessa cadenza degli altri widget: si usa il loro fornitore e si aggiunge solo la scelta.
struct FornitoreOsservato: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> VoceOsservato {
        VoceOsservato(date: Date(), voce: Voce(date: Date(), riassunto: .esempio, datiSalvati: false), scelto: nil)
    }

    func snapshot(for configuration: ConfigurazioneOsservato, in context: Context) async -> VoceOsservato {
        if context.isPreview { return placeholder(in: context) }
        let t = await timeline(for: configuration, in: context)
        return t.entries.first ?? placeholder(in: context)
    }

    func timeline(for configuration: ConfigurazioneOsservato, in context: Context) async -> Timeline<VoceOsservato> {
        var base = ConfigurazioneWidget()
        base.indirizzo = configuration.indirizzo
        base.codice = configuration.codice
        let t = await Fornitore().timeline(for: base, in: context)
        let id = configuration.giocatore?.id
        return Timeline(entries: t.entries.map { VoceOsservato(date: $0.date, voce: $0, scelto: id) }, policy: t.policy)
    }
}

struct WidgetOsservato: Widget {
    let kind = "SchieraxiOsservato"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneOsservato.self, provider: FornitoreOsservato()) { e in
            VistaOsservato(voce: e.voce, scelto: e.scelto)
        }
        .configurationDisplayName("Giocatore osservato")
        .description("Un giocatore a tua scelta: punti attesi, partita, dubbi.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct VistaOsservato: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }
    let voce: Voce
    var scelto: Int? = nil

    private var accessorio: Bool {
        switch famiglia {
        case .accessoryCircular, .accessoryRectangular, .accessoryInline: return true
        default: return false
        }
    }

    var body: some View {
        Group {
            if let w = voce.completo {
                if let g = w.osservato(scelto) { contenuto(g) } else { vuoto }
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(Vai.url("mercato"))
    }

    private var vuoto: some View {
        VStack(alignment: .leading, spacing: 3) {
            if famiglia == .accessoryInline {
                Label("Nessun osservato", systemImage: "eye")
            } else {
                TitoloBlocco(testo: "Osservato", icona: "eye")
                Text("Nessun giocatore").font(.headline)
                Text("Aggiungi osservati in Mercato, poi scegli qui.").font(.caption).foregroundStyle(accessorio ? Color.secondary : TintaWidget.testo2)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    private func punti(_ g: GiocatoreWidget) -> String { Formato.punti(g.puntiAttesi) }

    /// «Dubbio 55%», «Infortunato»; nil se e' tutto a posto.
    private func avviso(_ g: GiocatoreWidget) -> String? {
        let s = g.descrizioneStato
        return (s.isEmpty || s == "Disponibile") ? nil : s
    }

    @ViewBuilder
    private func contenuto(_ g: GiocatoreWidget) -> some View {
        switch famiglia {
        case .systemMedium: medio(g)
        case .accessoryCircular:
            ZStack {
                AccessoryWidgetBackground()
                VStack(spacing: 0) {
                    Text(String(g.cognome.prefix(5))).font(.system(size: 9))
                    Text(punti(g)).font(.headline.bold()).monospacedDigit().minimumScaleFactor(0.6)
                    Text("attesi").font(.system(size: 8))
                }
            }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 1) {
                Text("\(g.cognome) · \(punti(g)) punti").font(.headline).lineLimit(1)
                Text(g.partitaBreve).font(.caption).lineLimit(1)
                if let a = avviso(g) { Text(a).font(.caption2).lineLimit(1) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        case .accessoryInline:
            Label("\(g.cognome) \(punti(g)) · \(g.partitaBreve)", systemImage: "eye")
        default: piccolo(g)
        }
    }

    private func piccolo(_ g: GiocatoreWidget) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
                AvatarMini(g: g, lato: 30)
                VStack(alignment: .leading, spacing: 0) {
                    Text(g.cognome).font(.subheadline.weight(.semibold)).lineLimit(1)
                    Text(g.ruolo ?? "").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
            }
            Spacer(minLength: 0)
            Text(punti(g)).font(.system(size: 36, weight: .bold, design: .rounded)).monospacedDigit()
                .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
            Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
            Text(g.partitaBreve).font(.caption).lineLimit(1)
            if let a = avviso(g) {
                Label(a, systemImage: "exclamationmark.triangle.fill").font(.caption2).foregroundStyle(TintaWidget.attenzione).lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func medio(_ g: GiocatoreWidget) -> some View {
        HStack(alignment: .center, spacing: 14) {
            VStack(spacing: 4) {
                AvatarMini(g: g, lato: 64)
                Text(g.nome).font(.caption.weight(.semibold)).lineLimit(2).multilineTextAlignment(.center)
            }
            .frame(maxWidth: 110)
            VStack(alignment: .leading, spacing: 3) {
                TitoloBlocco(testo: "Osservato", icona: "eye")
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(punti(g)).font(.system(size: 38, weight: .bold, design: .rounded)).monospacedDigit()
                        .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                    Text("punti attesi").font(.caption).foregroundStyle(TintaWidget.testo2)
                }
                if let v = g.votoAtteso { Text("voto atteso \(Formato.punti(v))").font(.caption).monospacedDigit() }
                Text(g.partitaBreve).font(.subheadline.weight(.semibold)).lineLimit(1)
                if let a = avviso(g) {
                    Label(a, systemImage: "exclamationmark.triangle.fill").font(.caption).foregroundStyle(TintaWidget.attenzione).lineLimit(1)
                } else if let p = g.percentuale {
                    Text("gioca al \(Formato.intero(p))%").font(.caption).foregroundStyle(TintaWidget.testo2)
                }
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
