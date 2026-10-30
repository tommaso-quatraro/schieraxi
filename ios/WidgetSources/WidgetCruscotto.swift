import WidgetKit
import SwiftUI

/// Widget «Cruscotto»: tutto quello che serve prima di una giornata, in un colpo d'occhio.
/// Grande (iPhone, iPad): scadenza con conto alla rovescia, formazione sul campo, dubbi, scambio e svincolo, punti attesi e fatti, crediti.
/// Extra large (iPad): le stesse cose in due colonne, con i cognomi sul campo.
/// Ogni blocco e' un tocco: scadenza -> Oggi, modulo -> Formazione, volti -> scheda del giocatore, scambio -> Scambi,
/// svincolo e crediti -> Mercato, grafico -> Lega.
struct WidgetCruscotto: Widget {
    let kind = "SchieraxiCruscotto"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaCruscotto(voce: voce)
        }
        .configurationDisplayName("Cruscotto")
        .description("Scadenza, formazione, dubbi, scambio e svincolo, punti attesi e fatti, crediti: ogni blocco apre la sua schermata.")
        .supportedFamilies([.systemLarge, .systemExtraLarge, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct VistaCruscotto: View {
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
            if let w = voce.completo, let f = w.formazione, let tit = f.titolari, !tit.isEmpty {
                if accessorio { schermataDiBlocco(w, f) } else if famiglia == .systemExtraLarge { largo(w, f, tit) } else { alto(w, f, tit) }
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(Vai.url("oggi"))
    }

    // MARK: schermata di blocco

    @ViewBuilder
    private func schermataDiBlocco(_ w: RiassuntoWidget, _ f: FormazioneWidget) -> some View {
        let dubbi = w.daControllare.count
        let intervallo: String = f.intervallo?.testo.map { " · " + $0 } ?? ""
        switch famiglia {
        case .accessoryCircular:
            ZStack {
                AccessoryWidgetBackground()
                VStack(spacing: 0) {
                    Text(w.giornata.map { "G\($0)" } ?? "G").font(.system(size: 10))
                    Text(f.modulo ?? "—").font(.caption.bold()).minimumScaleFactor(0.6).lineLimit(1)
                    Text(dubbi > 0 ? "\(dubbi) dubbi" : "ok").font(.system(size: 9))
                }
            }
        case .accessoryInline:
            Label("\(f.modulo ?? "—") · \(dubbi > 0 ? "\(dubbi) da controllare" : "titolari a posto")", systemImage: "sportscourt")
        default:
            VStack(alignment: .leading, spacing: 1) {
                ContoWidget(inizio: w.inizio, adesso: voce.date).font(.headline).lineLimit(1).minimumScaleFactor(0.7)
                Text("\(f.modulo ?? "—") · \(Formato.punti(f.puntiAttesi)) punti\(intervallo)")
                    .font(.caption).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
                if let p = w.partiteInGioco.first {
                    Text("\(ColoriSquadra.sigla(p.casa)) \(p.punteggio) \(ColoriSquadra.sigla(p.trasferta)) \(p.etichetta)").font(.caption2).lineLimit(1)
                } else {
                    Text(dubbi > 0 ? "\(dubbi) da controllare" : "Titolari a posto").font(.caption2).lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: blocchi

    /// Scadenza: il numero grande e' il tempo che manca.
    private func scadenza(_ w: RiassuntoWidget, grande: CGFloat) -> some View {
        Link(destination: Vai.url("oggi")) {
            VStack(alignment: .leading, spacing: 0) {
                TitoloBlocco(testo: w.giornata.map { "Giornata \($0)" } ?? "Giornata", icona: "calendar")
                ContoWidget(inizio: w.inizio, adesso: voce.date)
                    .font(.system(size: grande, weight: .bold, design: .rounded)).lineLimit(1).minimumScaleFactor(0.5)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text(sottoscadenza(w)).font(.caption2).foregroundStyle(w.conProbabili == false ? TintaWidget.attenzione : TintaWidget.testo2).lineLimit(1)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func sottoscadenza(_ w: RiassuntoWidget) -> String {
        guard let inizio = w.inizio else { return "scadenza non nota" }
        let quando = inizio > voce.date ? "alla prima partita, \(Quando.leggibile(inizio))" : "la giornata e' iniziata"
        return w.conProbabili == false ? "probabili non uscite · \(quando)" : quando
    }

    /// Modulo e punti attesi.
    private func formazione(_ f: FormazioneWidget, allineato: HorizontalAlignment = .trailing) -> some View {
        Link(destination: Vai.url("formazione")) {
            VStack(alignment: allineato, spacing: 0) {
                TitoloBlocco(testo: "Formazione", icona: "sportscourt")
                Text(f.modulo ?? "—").font(.system(size: 30, weight: .bold, design: .rounded)).lineLimit(1).minimumScaleFactor(0.6)
                HStack(spacing: 3) {
                    Text(Formato.punti(f.puntiAttesi)).font(.footnote.weight(.bold)).monospacedDigit()
                        .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                    Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
                if let t = f.intervallo?.testo {
                    Text(t).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

    /// I dubbi, gli infortuni e le squalifiche tra i titolari.
    private func dubbi(_ w: RiassuntoWidget, massimo: Int, lato: CGFloat = 24) -> some View {
        let elenco = w.daControllare
        return VStack(alignment: .leading, spacing: 3) {
            TitoloBlocco(testo: elenco.isEmpty ? "Titolari a posto" : "Da controllare (\(elenco.count))",
                         icona: elenco.isEmpty ? "checkmark.seal.fill" : "exclamationmark.triangle.fill",
                         colore: elenco.isEmpty ? TintaWidget.testo2 : TintaWidget.attenzione)

            if elenco.isEmpty {
                Text(w.conProbabili == false ? "Le probabili non sono ancora uscite." : "Nessun dubbio in formazione.")
                    .font(.caption2).foregroundStyle(TintaWidget.testo2)
            } else {
                ForEach(elenco.prefix(massimo)) { g in RigaGiocatoreWidget(g: g, lato: lato) }
                if elenco.count > massimo {
                    Text("e altri \(elenco.count - massimo)").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func scambioESvincolo(_ w: RiassuntoWidget) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Link(destination: Vai.url("scambi")) { ScambioCompatto(scambio: w.scambio) }
            Link(destination: Vai.url("mercato")) { SvincoloCompatto(svincolo: w.svincolato) }
        }
    }

    /// Le partite in corso (con i miei titolari) o, se non ce ne sono, la prossima da giocare.
    @ViewBuilder
    private func live(_ w: RiassuntoWidget, lato: CGFloat = 15) -> some View {
        let inGioco = w.partiteInGioco
        let mostra: [PartitaLive] = inGioco.isEmpty ? (w.prossimaPartita(dopo: voce.date).map { [$0] } ?? []) : Array(inGioco.prefix(2))
        if !mostra.isEmpty {
            VStack(alignment: .leading, spacing: 3) {
                TitoloBlocco(testo: inGioco.isEmpty ? "Prossima partita" : "In corso", icona: "soccerball")
                ForEach(mostra) { p in
                    RigaPartitaLive(p: p, miei: inGioco.isEmpty ? [] : w.mieiTitolari(in: p), lato: lato, compatto: true)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// Durante le partite il posto di scambio e svincolo lo prende il live.
    @ViewBuilder
    private func liveOScambio(_ w: RiassuntoWidget) -> some View {
        if w.partiteInGioco.isEmpty {
            live(w)
            scambioESvincolo(w)
        } else {
            live(w)
        }
    }

    private func punti(_ w: RiassuntoWidget, altezza: CGFloat) -> some View {
        Link(destination: Vai.url("lega")) {
            VStack(alignment: .leading, spacing: 3) {
                TitoloBlocco(testo: "Attesi e fatti", icona: "chart.bar.fill")
                if w.giornateGiocate.isEmpty {
                    Text("Compare dopo la prima giornata giocata.").font(.caption2).foregroundStyle(TintaWidget.testo2)
                } else {
                    GraficoPunti(giornate: w.giornateGiocate, altezza: altezza)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func crediti(_ w: RiassuntoWidget) -> some View {
        Link(destination: Vai.url("mercato")) {
            VStack(alignment: .trailing, spacing: 0) {
                TitoloBlocco(testo: "Crediti", icona: "eurosign.circle")
                Text(w.creditiResidui.map { String(Formato.intero($0)) } ?? "—")
                    .font(.system(size: 30, weight: .bold, design: .rounded)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.6)
                    .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                Text("residui").font(.caption2).foregroundStyle(TintaWidget.testo2)
            }
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: grande (iPhone, iPad)

    private func alto(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                scadenza(w, grande: 30)
                Spacer(minLength: 8)
                formazione(f)
            }
            HStack(alignment: .top, spacing: 10) {
                CampoMini(titolari: tit, lato: 20)
                    .frame(width: 150)
                dubbi(w, massimo: 2, lato: 22)
            }
            liveOScambio(w)
            HStack(alignment: .bottom, spacing: 12) {
                punti(w, altezza: 26)
                crediti(w)
            }
            PiedeDati(voce: voce)
        }
    }

    // MARK: extra large (iPad)

    private func largo(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        HStack(alignment: .top, spacing: 20) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .top) {
                    scadenza(w, grande: 34)
                    Spacer(minLength: 8)
                    formazione(f)
                }
                CampoMini(titolari: tit, lato: 40, conNomi: true)
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity)
            VStack(alignment: .leading, spacing: 10) {
                dubbi(w, massimo: 3, lato: 28)
                liveOScambio(w)
                HStack(alignment: .bottom, spacing: 12) {
                    punti(w, altezza: 44)
                    crediti(w)
                }
                Spacer(minLength: 0)
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: .infinity)
        }
    }
}
