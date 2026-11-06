import WidgetKit
import SwiftUI
import UIKit

/// Widget «Prossima giornata»: conto alla rovescia alla prima partita, modulo e punti attesi.
/// Famiglie: piccolo e medio (Schermata Home), cerchio, rettangolo e riga (Schermata di blocco).

struct WidgetOggi: Widget {
    let kind = "SchieraxiOggi"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore(conConto: true)) { voce in
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
            self.dynamicTypeSize(...TestoWidget.massimo)
                .containerBackground(for: .widget) { Color.clear }
        } else {
            self
                // Un widget ha misure fisse: con le dimensioni di accessibilità del testo i numeri diventavano «3-… 7…» e le righe
                // si sovrapponevano. Il testo cresce fino a «molto grande», poi si ferma (come i widget di sistema).
                .dynamicTypeSize(...TestoWidget.massimo)
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
    @Environment(\.dynamicTypeSize) private var dimensioneTesto

    private var accessorio: Bool {
        switch famiglia {
        case .accessoryCircular, .accessoryRectangular, .accessoryInline: return true
        default: return false
        }
    }

    var body: some View {
        Group {
            if let r = voce.riassunto, r.mostraFase {
                // giornata in corso (punti fatti e previsti) o appena finita (riepilogo e prossima): niente «Da controllare»
                vistaFase(r)
            } else if let r = voce.riassunto {
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
        // Un tocco sul widget apre l'app sulla formazione (o su «Collega il widget» se non è collegato); durante la giornata
        // in corso o appena finita apre Oggi, dove ci sono i punti fatti e il riepilogo.
        .widgetURL(voce.tocco(URL(string: voce.riassunto?.mostraFase == true ? "schieraxi://oggi" : "schieraxi://formazione")))
    }

    // MARK: giornata in corso o appena finita

    private func vistaFase(_ r: RiassuntoOggi) -> some View {
        Group {
            switch famiglia {
            case .systemMedium: faseMedio(r)
            case .accessoryCircular: faseCircolare(r)
            case .accessoryRectangular: faseRettangolare(r)
            case .accessoryInline: faseRiga(r)
            default: fasePiccolo(r)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(r.descrizioneFase ?? r.voceGiornata)
    }

    /// «Giornata 8 · 11ª di Serie A» (in corso) o «Giornata 7 · 10ª di Serie A» (appena finita), con il simbolo della fase; se non
    /// entra «Giornata 8», mai «G8». Nel widget piccolo (`corta`) solo «Giornata 8» (#299).
    private func titoloFase(_ r: RiassuntoOggi, corta: Bool = false) -> some View {
        let nome = r.inCorso ? r.nomeGiornata : r.nomeGiornataChiusa
        let ripiego = r.inCorso ? r.etichettaGiornata : r.etichettaGiornataChiusa
        return GiornataInRiga(forme: nome.map { corta ? [$0.corto] : ParoleWidget.formeGiornata($0) } ?? [ripiego], voce: nome?.voce ?? ripiego,
                              simbolo: r.inCorso ? "dot.radiowaves.left.and.right" : "flag.checkered")
            .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).minimumScaleFactor(0.7)
    }

    private func puntiFattiGrandi(_ r: RiassuntoOggi, stile: Font.TextStyle) -> some View {
        Text(r.puntiFattiTesto)
            .font(.system(stile, design: .rounded).weight(.bold)).monospacedDigit()
            .minimumScaleFactor(0.5).lineLimit(1)
            .widgetAccentable()
    }

    /// Sotto i numeri: copia vecchia o widget da ricollegare.
    @ViewBuilder
    private func statoDati(_ r: RiassuntoOggi) -> some View {
        if voce.accessoRichiesto {
            Label("Tocca per ricollegare", systemImage: "link").font(.caption2.bold()).foregroundStyle(.white.opacity(0.75)).lineLimit(1)
        } else if voce.datiSalvati {
            Label("dati delle \(Quando.ora(r.scaricatoIl))", systemImage: "icloud.slash")
                .font(.caption2).foregroundStyle(.white.opacity(0.75)).lineLimit(1)
        }
    }

    /// «Prossima: 3 giorni 3 h» (conto alla rovescia alla scadenza della prossima giornata).
    private func prossimaBreve(_ r: RiassuntoOggi) -> some View {
        HStack(spacing: 3) {
            Text("Prossima:")
            conto(r).monospacedDigit()
        }
        .lineLimit(1).minimumScaleFactor(0.6)
    }

    private func fasePiccolo(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            titoloFase(r, corta: true)
            Text(r.inCorso ? ParoleWidget.chiusa : "Finita").font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.75))
            Spacer(minLength: 0)
            puntiFattiGrandi(r, stile: .largeTitle)
            Text("punti fatti").font(.caption2).foregroundStyle(.white.opacity(0.8))
            if let fine = r.puntiFineTesto {
                Text(fine).font(.caption2.weight(.semibold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
            }
            if r.finita, r.inizio != nil {
                prossimaBreve(r).font(.caption2).foregroundStyle(.white.opacity(0.8))
            }
            statoDati(r)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func faseMedio(_ r: RiassuntoOggi) -> some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                titoloFase(r)
                Text(r.inCorso ? ParoleWidget.chiusa : "Finita").font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.75))
                Spacer(minLength: 0)
                puntiFattiGrandi(r, stile: .largeTitle)
                Text("punti fatti").font(.caption).foregroundStyle(.white.opacity(0.8))
                if r.finita, let fine = r.puntiFineTesto {
                    Text(fine).font(.caption.weight(.semibold)).monospacedDigit().foregroundStyle(.white.opacity(0.9))
                }
                Spacer(minLength: 0)
                statoDati(r)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            VStack(alignment: .leading, spacing: 4) {
                if r.inCorso {
                    Label("A fine giornata", systemImage: "chart.line.uptrend.xyaxis").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
                        .lineLimit(1).minimumScaleFactor(0.7)
                    Text(r.puntiFine.map { "circa \(Formato.punti($0))" } ?? "—")
                        .font(.system(.title2, design: .rounded).weight(.bold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.6)
                    if r.punti != nil {
                        Text("attesi prima: \(puntiTesto(r))").font(.caption).monospacedDigit().foregroundStyle(.white.opacity(0.85))
                            .lineLimit(1).minimumScaleFactor(0.7)
                    }
                    Spacer(minLength: 0)
                    if let a = r.ancoraDaGiocareTesto {
                        Text(a).font(.caption2).foregroundStyle(.white.opacity(0.8)).lineLimit(2)
                    }
                } else {
                    GiornataInRiga(forme: r.formeGiornata, voce: r.voceGiornata, simbolo: "calendar")
                        .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).minimumScaleFactor(0.7)
                    conto(r).font(.system(.title2, design: .rounded).weight(.bold)).lineLimit(1).minimumScaleFactor(0.5)
                    if let inizio = r.inizio {
                        Text(allaScadenza(inizio)).font(.caption2).foregroundStyle(.white.opacity(0.8)).lineLimit(2)
                    }
                    Spacer(minLength: 0)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func faseCircolare(_ r: RiassuntoOggi) -> some View {
        CerchioWidget {
            // «Giornata 8», rimpicciolita se serve, mai «G8» (#299)
            Text(ParoleWidget.giornataNelCerchio(r.inCorso ? r.nomeGiornata : r.nomeGiornataChiusa))
                .font(.caption2).lineLimit(1).minimumScaleFactor(0.5)
                .accessibilityLabel(r.inCorso ? r.voceGiornata : r.voceGiornataChiusa)
            Text(r.puntiFattiTesto).font(.caption.bold()).monospacedDigit().minimumScaleFactor(0.6).lineLimit(1).widgetAccentable()
            Text("fatti").font(.caption2)
        }
    }

    private func faseRettangolare(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(r.testaRettangoloFase).font(.caption2).foregroundStyle(.secondary).lineLimit(1).minimumScaleFactor(0.7)
            Text("\(r.puntiFattiTesto) punti fatti").font(.headline).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7).widgetAccentable()
            if r.finita, r.inizio != nil {
                prossimaBreve(r).font(.caption2)
            } else if let fine = r.puntiFineTesto {
                Text(fine).font(.caption2).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func faseRiga(_ r: RiassuntoOggi) -> some View {
        // si accorcia di parole intere, mai la giornata: «Giornata 8: 41,5 punti fatti finora» → … → «Giornata 8: 41,5»
        RigaInLinea(r.formeRigaInLineaFase, icona: r.inCorso ? "dot.radiowaves.left.and.right" : "flag.checkered")
    }

    // MARK: pezzi comuni

    private func inCorso(_ r: RiassuntoOggi) -> Bool {
        guard let inizio = r.inizio else { return false }
        return inizio <= voce.date
    }

    private func puntiTesto(_ r: RiassuntoOggi) -> String {
        Formato.punti(r.punti)
    }

    /// Conto alla rovescia come la web («6 h 44 min», «2 giorni 3 h»); «Chiusa» a scadenza passata.
    private func conto(_ r: RiassuntoOggi) -> some View {
        ContoWidget(inizio: r.inizio, adesso: voce.date)
    }

    /// «alla scadenza, oggi 05:30» / «… ven 6 03:32»: la data come `quando` della web, contata dall'istante della voce.
    private func allaScadenza(_ inizio: Date) -> String {
        "alla scadenza, \(Quando.relativa(inizio, adesso: voce.date))"
    }

    /// Non collegato: «Tocca per collegare»; collegato ma senza dati: «Nessun dato».
    private var senzaDati: some View {
        SenzaDatiWidget(voce: voce, compatto: accessorio)
    }

    // MARK: Schermata Home

    private func piccolo(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            // nel widget piccolo solo «Giornata 8»; VoiceOver legge anche «11ª di Serie A» (#299)
            GiornataInRiga(forme: r.nomeGiornata.map { [$0.corto] } ?? r.formeGiornata, voce: r.voceGiornata, simbolo: "calendar")
                .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).minimumScaleFactor(0.7)
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
                Text(voce.accessoRichiesto ? "Tocca per ricollegare" : voce.datiSalvati ? "dati delle \(Quando.ora(r.scaricatoIl))" : "punti attesi").font(.caption2).foregroundStyle(.white.opacity(0.75))
            }
            if r.daControllare > 0 {
                EtichettaDaControllare(n: r.daControllare).font(.caption2).foregroundStyle(TintaWidget.attenzione).lineLimit(1)
            } else if r.probabili == false {
                Label("probabili non uscite", systemImage: "clock").font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var conDubbi: Bool { !(voce.completo?.daControllare.isEmpty ?? true) }

    /// Quanti giocatori da controllare stanno nel widget medio (la regola, provata dai test, sta in `DisposizioneWidget`).
    private var righeDubbi: Int { DisposizioneWidget.righeDubbi(dimensioneTesto) }

    private func medio(_ r: RiassuntoOggi) -> some View {
        HStack(alignment: .top, spacing: 16) {
            // a sinistra (conto alla rovescia) si apre Oggi, a destra (formazione) la Formazione
            Link(destination: voce.tocco(URL(string: "schieraxi://oggi")) ?? URL(fileURLWithPath: "/")) {
            VStack(alignment: .leading, spacing: 4) {
                GiornataInRiga(forme: r.formeGiornata, voce: r.voceGiornata, simbolo: "calendar")
                    .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).minimumScaleFactor(0.7)
                conto(r)
                    .font(.system(.largeTitle, design: .rounded).weight(.bold))
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text(r.inizio.map(allaScadenza) ?? "")
                    .font(.caption).foregroundStyle(.white.opacity(0.8))
                Spacer(minLength: 0)
                if voce.accessoRichiesto {
                    Label("Tocca per ricollegare", systemImage: "link").font(.caption2.bold()).foregroundStyle(.secondary)
                } else if voce.datiSalvati {
                    Label("dati delle \(Quando.ora(r.scaricatoIl))", systemImage: "icloud.slash").font(.caption2).foregroundStyle(.secondary)
                }
            }
            }
            Link(destination: voce.tocco(URL(string: "schieraxi://formazione")) ?? URL(fileURLWithPath: "/")) {
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
                        // stato intero anche su iPad: se non entra via i volti, poi «gioca 70%» (mai «In dubbio · gioc…»)
                        RigheDaControllare(giocatori: Array(w.daControllare.prefix(righeDubbi)), lato: 28, conLink: false, spazio: 2)
                        if w.daControllare.count > righeDubbi {
                            Text(RiassuntoWidget.altri(w.daControllare.count - righeDubbi)).font(.caption2).foregroundStyle(TintaWidget.testo2)
                        }
                    }
                } else if r.daControllare > 0 {
                    EtichettaDaControllare(n: r.daControllare, icona: "exclamationmark.circle.fill")
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
        CerchioWidget {
            Text(ParoleWidget.giornataNelCerchio(r.nomeGiornata)).font(.caption2).lineLimit(1).minimumScaleFactor(0.5)
                .accessibilityLabel(r.voceGiornata)
            Text(r.modulo ?? "—").font(.caption.bold()).minimumScaleFactor(0.6).lineLimit(1)
            Text(puntiTesto(r)).font(.caption2).monospacedDigit()
        }
    }

    private func rettangolare(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            GiornataInRiga(forme: r.formeGiornata, voce: r.voceGiornata).font(.caption2).foregroundStyle(.secondary).minimumScaleFactor(0.7)
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

/// Fin dove cresce il testo nei widget (misure fisse): oltre, con le dimensioni di accessibilità, i numeri si troncavano e le righe
/// si sovrapponevano. Chi ha bisogno del testo molto grande ha le stesse informazioni, intere, aprendo l'app.
enum TestoWidget {
    static let massimo: DynamicTypeSize = .xxLarge
}
