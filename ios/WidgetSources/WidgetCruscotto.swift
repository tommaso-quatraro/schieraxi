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
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore(conConto: true)) { voce in
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
    @Environment(\.dynamicTypeSize) private var dimensioneTesto
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
        .widgetURL(voce.tocco(Vai.url("oggi")))
    }

    // MARK: schermata di blocco

    @ViewBuilder
    private func schermataDiBlocco(_ w: RiassuntoWidget, _ f: FormazioneWidget) -> some View {
        let dubbi = w.daControllare.count
        switch famiglia {
        case .accessoryCircular:
            // le stesse parole delle altre forme: «4 da controllare» (nel cerchio «⚠ 4»), «titolari a posto» (nel cerchio «a posto»)
            CerchioWidget {
                // «Giornata 8», rimpicciolita se serve, mai «G8» (#299)
                Text(ParoleWidget.giornataNelCerchio(w.nomeGiornata)).fontWidget(10).lineLimit(1).minimumScaleFactor(0.5)
                    .accessibilityLabel(w.nomeGiornata?.voce ?? "Giornata")
                Text(f.modulo ?? "—").font(.caption.bold()).minimumScaleFactor(0.6).lineLimit(1)
                if dubbi > 0 {
                    EtichettaDaControllare(n: dubbi).fontWidget(9)
                } else {
                    TestoCheEntra(ParoleWidget.daControllare(0)).fontWidget(9)
                }
            }
        case .accessoryInline:
            // una riga sola, solo testo e simbolo: con il testo grande senza il modulo (mai «2 da contr…»)
            Label(DisposizioneWidget.rigaInLinea(modulo: f.modulo, dubbi: dubbi, testo: dimensioneTesto), systemImage: "sportscourt")
        default:
            VStack(alignment: .leading, spacing: 1) {
                ContoWidget(inizio: w.inizio, adesso: voce.date).font(.headline).lineLimit(1).minimumScaleFactor(0.7)
                TestoCheEntra(ParoleWidget.moduloEPunti(f.modulo, punti: f.puntiAttesi, fascia: f.intervallo?.testo))
                    .font(.caption).monospacedDigit()
                if let p = w.partiteInGioco.first {
                    // la stessa riga del widget Partite live: «INT 2–1 ROM 63'», senza punteggio «INT vs ROM · …» (#391)
                    Text(p.formeRiga(adesso: voce.date).first ?? p.squadre)
                        .font(.caption2).lineLimit(1)
                } else if dubbi > 0 {
                    EtichettaDaControllare(n: dubbi).font(.caption2)
                } else {
                    Text("Titolari a posto").font(.caption2).lineLimit(1)
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
                GiornataInRiga(forme: w.nomeGiornata.map { ParoleWidget.formeGiornata($0) } ?? ["Giornata"],
                               voce: w.nomeGiornata?.voce ?? "Giornata", simbolo: "calendar")
                    .font(.caption2.weight(.semibold)).foregroundStyle(TintaWidget.testo2)
                ContoWidget(inizio: w.inizio, adesso: voce.date)
                    .fontWidget(grande, weight: .bold, design: .rounded).lineLimit(1).minimumScaleFactor(0.5)
                    .frame(maxWidth: .infinity, alignment: .leading)
                // dopo la scadenza come la web: sopra «Chiusa», sotto quando si è chiusa; se non entra resta l'avviso, mai «…»
                TestoCheEntra(ParoleWidget.sottoScadenza(w.inizio, adesso: voce.date, conProbabili: w.conProbabili))
                    .font(.caption2).foregroundStyle(w.conProbabili == false ? TintaWidget.attenzione : TintaWidget.testo2)
            }
        }
        .accessibilityElement(children: .combine)
    }

    /// Modulo e punti attesi; la fascia («tra 66 e 82») solo se c'è posto.
    private func formazione(_ f: FormazioneWidget, conFascia: Bool = true) -> some View {
        Link(destination: Vai.url("formazione")) {
            VStack(alignment: .trailing, spacing: 0) {
                TitoloBlocco(testo: "Formazione", icona: "sportscourt")
                Text(f.modulo ?? "—").fontWidget(30, weight: .bold, design: .rounded).lineLimit(1).minimumScaleFactor(0.6)
                HStack(spacing: 3) {
                    Text(Formato.punti(f.puntiAttesi)).font(.footnote.weight(.bold)).monospacedDigit()
                        .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                    Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
                if conFascia, let t = f.intervallo?.testo {
                    Text(t).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

    /// I dubbi, gli infortuni e le squalifiche tra i titolari. Righe staccate (6 punti): lo stato non tocca il nome sotto.
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
                RigheDaControllare(giocatori: Array(elenco.prefix(massimo)), lato: lato, spazio: 6)
                if elenco.count > massimo {
                    Text(RiassuntoWidget.altri(elenco.count - massimo)).font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func scambioESvincolo(_ w: RiassuntoWidget, compatto: Bool) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Link(destination: Vai.url("scambi")) { ScambioCompatto(scambio: w.scambio, compatto: compatto) }
            Link(destination: Vai.url("mercato")) { SvincoloCompatto(svincolo: w.svincolato, compatto: compatto) }
        }
    }

    /// Le partite in corso (con i miei titolari) o, se non ce ne sono, la prossima da giocare.
    @ViewBuilder
    private func live(_ w: RiassuntoWidget, lato: CGFloat = 15) -> some View {
        let inGioco = w.partiteInGioco
        let mostra: [PartitaLive] = inGioco.isEmpty ? (w.prossimaPartita(dopo: voce.date).map { [$0] } ?? []) : Array(inGioco.prefix(2))
        if !mostra.isEmpty {
            VStack(alignment: .leading, spacing: 3) {
                // «Partite in corso»: «In corso» da solo sembrava la giornata (che dopo la scadenza è «Chiusa»)
                TitoloBlocco(testo: inGioco.isEmpty ? "Prossima partita" : "Partite in corso", icona: "soccerball")
                ForEach(mostra) { p in
                    RigaPartitaLive(p: p, miei: inGioco.isEmpty ? [] : w.mieiTitolari(in: p), adesso: voce.date, lato: lato, compatto: true)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// Le partite (se la prova le tiene) e, quando nessuna è in gioco, scambio e svincolo: durante le partite il loro posto lo
    /// prende il live.
    @ViewBuilder
    private func partiteEScambio(_ w: RiassuntoWidget, _ prova: DisposizioneWidget.ProvaCruscotto) -> some View {
        if prova.partite { live(w) }
        if w.partiteInGioco.isEmpty { scambioESvincolo(w, compatto: prova.compatto) }
    }

    /// In fondo il grafico «Attesi e fatti» con i crediti accanto; senza posto per il grafico, i crediti su una riga.
    @ViewBuilder
    private func fondo(_ w: RiassuntoWidget, _ prova: DisposizioneWidget.ProvaCruscotto, altezza: CGFloat) -> some View {
        if prova.grafico {
            HStack(alignment: .bottom, spacing: 12) {
                punti(w, altezza: altezza)
                crediti(w)
            }
        } else {
            Link(destination: Vai.url("mercato")) { CreditiInRiga(crediti: w.creditiResidui) }
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
                TitoloBlocco(testo: "Crediti", icona: ParoleWidget.simboloCrediti)
                Text(w.creditiResidui.map { String(Formato.intero($0)) } ?? "—")
                    .monospacedDigit().fontWidget(30, weight: .bold, design: .rounded).lineLimit(1).minimumScaleFactor(0.6)
                    .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                Text("residui").font(.caption2).foregroundStyle(TintaWidget.testo2)
            }
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: grande (iPhone, iPad)

    /// Il widget grande è alto da circa 270 punti (iPad mini, iPhone SE) a 350 (iPhone grandi): si tiene la prima prova che entra
    /// in altezza (`DisposizioneWidget.proveCruscotto`), così niente esce dal bordo (su iPad mancavano «Giornata 8» in alto e le
    /// giornate del grafico in basso).
    private func alto(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        let prove = DisposizioneWidget.proveCruscotto(partitePrima: w.partiteInPrimoPiano, dubbi: 2)
        return PrimaCheEntra(prove.count, in: .vertical) { i in
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .top) {
                    scadenza(w, grande: 30)
                    Spacer(minLength: 8)
                    formazione(f, conFascia: !prove[i].compatto)
                }
                // su iPad (widget più stretto) il campo si stringe, così «In dubbio · gioca 70%» resta intero accanto al volto
                PrimaCheEntra(2) { j in
                    HStack(alignment: .top, spacing: 10) {
                        CampoMini(titolari: tit, lato: 20)
                            .frame(width: j == 0 ? 150 : 116)
                        dubbi(w, massimo: prove[i].dubbi, lato: 22)
                    }
                }
                partiteEScambio(w, prove[i])
                fondo(w, prove[i], altezza: 26)
                PiedeDati(voce: voce)
            }
        }
    }

    // MARK: extra large (iPad)

    /// Due colonne, ognuna con la prima prova che entra in altezza: a sinistra il campo più grande che sta sotto scadenza e
    /// formazione, a destra le stesse prove del grande.
    private func largo(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        let lati: [CGFloat] = [40, 34, 28]
        let prove = DisposizioneWidget.proveCruscotto(partitePrima: w.partiteInPrimoPiano, dubbi: 3)
        return HStack(alignment: .top, spacing: 20) {
            PrimaCheEntra(lati.count, in: .vertical) { i in
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .top) {
                        scadenza(w, grande: 34)
                        Spacer(minLength: 8)
                        formazione(f)
                    }
                    CampoMini(titolari: tit, lato: lati[i], conNomi: true)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            PrimaCheEntra(prove.count, in: .vertical) { i in
                VStack(alignment: .leading, spacing: 10) {
                    dubbi(w, massimo: prove[i].dubbi, lato: 28)
                    partiteEScambio(w, prove[i])
                    fondo(w, prove[i], altezza: 36)
                    Spacer(minLength: 0)
                    PiedeDati(voce: voce)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        }
    }
}
