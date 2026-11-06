import WidgetKit
import SwiftUI
import AppIntents

// Widget «Giocatore osservato»: scegli tu quale (tra i tuoi osservati e i tuoi giocatori: tieni premuto > Modifica widget > Giocatore).
// Mostra punti attesi, fantavoto atteso (`fv_atteso`; da un server vecchio il voto in pagella atteso), la partita con il giorno e
// l'ora come la web e il widget Live («vs ROM · oggi 20:45»: `GiocatoreWidget.formePartita`) e se e' in dubbio. Misure: piccolo, medio, cerchio, rettangolo, riga.
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
        // solo i giocatori della copia del collegamento di adesso: mai quelli di un account di prima (#482)
        guard let dove = ScaricaOggi.destinazione(codice: ""),
              let w = MemoriaWidget.leggi(per: MemoriaWidget.impronta(indirizzo: dove.indirizzo, token: dove.token))?.riassunto else { return [] }
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
    static var title: LocalizedStringResource = "Giocatore seguito"
    static var description = IntentDescription("Il giocatore da seguire. Senza scelta si vede il primo dei tuoi seguiti.")

    @Parameter(title: "Giocatore")
    var giocatore: GiocatoreScelto?

    // Il collegamento è automatico (come negli altri widget): il codice compare solo con «Collegamento manuale».
    @Parameter(title: "Collegamento manuale", default: false)
    var manuale: Bool

    @Parameter(title: "Codice di collegamento", default: "")
    var codice: String

    static var parameterSummary: some ParameterSummary {
        When(\.$manuale, .equalTo, true) {
            Summary("Giocatore seguito") {
                \.$giocatore
                \.$manuale
                \.$codice
            }
        } otherwise: {
            Summary("Giocatore seguito") {
                \.$giocatore
                \.$manuale
            }
        }
    }
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
        base.manuale = configuration.manuale
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
        .configurationDisplayName("Giocatore seguito")
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
                // senza giocatore: «Nessun giocatore», o «Apri l'app per vederli» se il server ha tolto i seguiti per il peso
                if let g = w.osservato(scelto) { contenuto(g) } else { OsservatoSenzaGiocatore(vuoto: w.vuotoOsservato, famiglia: famiglia) }
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(voce.tocco(Vai.url("mercato")))
    }

    private func punti(_ g: GiocatoreWidget) -> String { Formato.punti(g.puntiAttesi) }

    /// «In dubbio · gioca 55%», «Infortunato»; nil se e' tutto a posto.
    private func avviso(_ g: GiocatoreWidget) -> String? {
        let s = g.descrizioneStato
        return s.isEmpty ? nil : s
    }

    @ViewBuilder
    private func contenuto(_ g: GiocatoreWidget) -> some View {
        switch famiglia {
        case .systemMedium: medio(g)
        case .accessoryCircular:
            CerchioWidget {
                // il cognome intero, rimpicciolito se è lungo (come i cognomi sul campo, CampoMini): mai tagliato a metà
                Text(g.cognome).fontWidget(9).lineLimit(1).minimumScaleFactor(0.6)
                Text(punti(g)).font(.headline.bold()).monospacedDigit().minimumScaleFactor(0.6).lineLimit(1)
                Text("attesi").fontWidget(8)
            }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 1) {
                Text("\(g.cognome) · \(punti(g)) punti").font(.headline).lineLimit(1)
                TestoCheEntra(g.formePartita(adesso: voce.date)).font(.caption)
                if let a = avviso(g) { Text(a).font(.caption2).lineLimit(1) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        case .accessoryInline:
            // con il giorno la riga è più lunga: prima via l'avversario (e «oggi»), poi la partita (mai «domani 1…»)
            RigaInLinea(g.formeInLineaSeguito(adesso: voce.date), icona: "eye")
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
            Text(punti(g)).monospacedDigit().fontWidget(36, weight: .bold, design: .rounded).lineLimit(1).minimumScaleFactor(0.5)
                .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
            Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
            TestoCheEntra(g.formePartita(adesso: voce.date)).font(.caption)
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
                TitoloBlocco(testo: "Seguito", icona: "eye")
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(punti(g)).monospacedDigit().fontWidget(38, weight: .bold, design: .rounded).lineLimit(1).minimumScaleFactor(0.5)
                        .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                    Text("punti attesi").font(.caption).foregroundStyle(TintaWidget.testo2)
                }
                if let forme = g.rigaVotoAtteso { TestoCheEntra(forme).font(.caption).monospacedDigit() }
                TestoCheEntra(g.formePartita(adesso: voce.date)).font(.subheadline.weight(.semibold))
                // una sola percentuale, come l'app: l'avviso del server («In dubbio · gioca 55%»), altrimenti «gioca 90%» da p_voto
                if let riga = g.statoOGioca {
                    if avviso(g) != nil {
                        Label(riga, systemImage: "exclamationmark.triangle.fill").font(.caption).foregroundStyle(TintaWidget.attenzione).lineLimit(1)
                    } else {
                        Text(riga).font(.caption).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                    }
                }
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
