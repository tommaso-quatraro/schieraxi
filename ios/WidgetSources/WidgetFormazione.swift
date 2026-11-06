import WidgetKit
import SwiftUI

/// Widget «Formazione consigliata»: modulo, punti attesi e i titolari sul campo (con i volti illustrati).
/// Misure: piccolo (modulo e punti), medio (dato + campo mini), grande (campo con i cognomi), extra large per iPad (campo e lista
/// dei titolari con il fantavoto atteso, come l'app),
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
                                    Text(g.cognome).fontWidget(9, weight: .semibold).lineLimit(1).minimumScaleFactor(0.7)
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
        .widgetURL(voce.tocco(URL(string: "schieraxi://formazione")))
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
            IntestazioneWidget(titolo: "Formazione", icona: "sportscourt", giornata: r.nomeGiornata, soloCorta: true)
            Spacer(minLength: 0)
            Text(r.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold))
            Text("\(Formato.punti(r.punti)) punti attesi").font(.caption).foregroundStyle(TintaWidget.testo2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Home

    private func piccolo(_ w: RiassuntoWidget, _ f: FormazioneWidget) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            IntestazioneWidget(titolo: f.tuaScelta == true ? "La tua scelta" : "Formazione", icona: "sportscourt",
                               giornata: w.nomeGiornata, soloCorta: true)
            Spacer(minLength: 0)
            Text(f.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold)).minimumScaleFactor(0.5).lineLimit(1)
            Text(punti(f)).font(.title3.bold()).monospacedDigit()
            Text(f.intervallo?.testo.map { "attesi · \($0)" } ?? "punti attesi")
                .font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1).minimumScaleFactor(0.8)
            if !w.daControllare.isEmpty {
                EtichettaDaControllare(n: w.daControllare.count)
                    .font(.caption2).foregroundStyle(TintaWidget.attenzione).lineLimit(1).minimumScaleFactor(0.8)
            } else {
                PiedeDati(voce: voce)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func medio(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                IntestazioneWidget(titolo: f.tuaScelta == true ? "La tua scelta" : "Formazione", icona: "sportscourt")
                Spacer(minLength: 0)
                Text(f.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold)).minimumScaleFactor(0.5).lineLimit(1)
                Text(punti(f)).font(.title3.bold()).monospacedDigit()
                Text("punti attesi").font(.caption2).foregroundStyle(TintaWidget.testo2)
                if let t = f.intervallo?.testo { Text(t).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
                Spacer(minLength: 0)
                if !w.daControllare.isEmpty {
                    EtichettaDaControllare(n: w.daControllare.count)
                        .font(.caption2).foregroundStyle(TintaWidget.attenzione)
                } else { PiedeDati(voce: voce) }
            }
            .frame(maxWidth: 120, alignment: .leading)
            CampoMini(titolari: tit, lato: 24)
        }
    }

    /// La frase intera della testata per VoiceOver (sullo schermo la testata si accorcia: «Giornata 8», «73,7 attesi»).
    private func testataParlata(_ w: RiassuntoWidget, _ f: FormazioneWidget) -> String {
        [f.modulo ?? "—", ParoleWidget.puntiAttesi(f.puntiAttesi, tuaScelta: f.tuaScelta == true)[0], f.intervallo?.testo, w.nomeGiornata?.voce]
            .compactMap { $0 }.joined(separator: ", ")
    }

    private func grande(_ w: RiassuntoWidget, _ f: FormazioneWidget, _ tit: [GiocatoreWidget]) -> some View {
        // Accanto al modulo due righe (#391): sopra i punti, sotto la fascia e la giornata. Ogni riga mostra la prima forma che
        // entra: «73,7 punti attesi · la tua scelta» → «73,7 attesi», «Giornata 8 · 11ª di Serie A» → «Giornata 8» → «G8».
        // La giornata non sta più sulla riga dei punti: «G8» solo se «Giornata 8» non entra nemmeno accanto alla fascia.
        let testata = TestataFormazioneGrande(puntiAttesi: f.puntiAttesi, tuaScelta: f.tuaScelta == true,
                                              fascia: f.intervallo?.testo, giornata: w.nomeGiornata)
        return VStack(spacing: 8) {
            HStack(alignment: .center, spacing: 8) {
                Text(f.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold)).lineLimit(1).minimumScaleFactor(0.5)
                VStack(alignment: .leading, spacing: 0) {
                    TestoCheEntra(testata.formePunti).font(.subheadline).monospacedDigit()
                    HStack(alignment: .firstTextBaseline, spacing: 0) {
                        // la fascia sempre intera; alla giornata lo spazio che resta (come la testata dei widget piccoli)
                        if let fascia = testata.fascia { Text(fascia).font(.caption).lineLimit(1).fixedSize() }
                        Spacer(minLength: 8)
                        if !testata.formeGiornata.isEmpty {
                            TestoCheEntra(testata.formeGiornata).font(.caption2).layoutPriority(1)
                        }
                    }
                }
                .foregroundStyle(TintaWidget.testo2)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(testataParlata(w, f))
            CampoMini(titolari: tit, lato: 40, conNomi: true)
            HStack {
                if !w.daControllare.isEmpty {
                    EtichettaDaControllare(n: w.daControllare.count).foregroundStyle(TintaWidget.attenzione)
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
                // «73,7 punti attesi» → «73,7 attesi», poi via la fascia: mai «73,7 punti…»
                let pezzi = ParoleWidget.puntiAttesi(f.puntiAttesi, tuaScelta: f.tuaScelta == true)
                PrimaCheEntra(pezzi.count + 1) { i in
                    HStack(alignment: .firstTextBaseline) {
                        Text(f.modulo ?? "—").fontWidget(40, weight: .bold, design: .rounded).lineLimit(1).minimumScaleFactor(0.6)
                        Text(pezzi[min(i, pezzi.count - 1)]).font(.headline).monospacedDigit().foregroundStyle(TintaWidget.testo2).lineLimit(1)
                        if i < pezzi.count, let t = f.intervallo?.testo {
                            Text(t).font(.subheadline).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                        }
                        Spacer(minLength: 0)
                    }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(testataParlata(w, f))
                CampoMini(titolari: tit, lato: 48, conNomi: true)
            }
            VStack(alignment: .leading, spacing: 4) {
                // sopra i numeri il loro nome («Fantavoto atteso», come l'app); se non entra restano i numeri, VoiceOver lo legge sempre
                let nomi = f.nomeNumeroTitolari
                PrimaCheEntra(nomi.count) { i in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text("Titolari")
                        Spacer(minLength: 0)
                        Text(nomi[i])
                    }
                    .lineLimit(1)
                }
                .font(.caption.weight(.semibold)).foregroundStyle(TintaWidget.testo2)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Titolari, \(nomi.first ?? "")")
                .accessibilityAddTraits(.isHeader)
                ForEach(tit) { g in
                    Link(destination: URL(string: "schieraxi://giocatore/\(g.id)") ?? URL(fileURLWithPath: "/")) {
                        HStack(spacing: 8) {
                            AvatarMini(g: g, lato: 22)
                            Text(g.nome).font(.subheadline).lineLimit(1)
                            Spacer(minLength: 4)
                            Text(f.numeroTitolare(g)).font(.subheadline.weight(.semibold)).monospacedDigit()
                        }
                    }
                    .accessibilityLabel(f.voceTitolare(g))
                }
                Spacer(minLength: 0)
                PiedeDati(voce: voce)
            }
            .frame(maxWidth: 300)
        }
    }

    // MARK: Schermata di blocco

    private func circolare(_ f: FormazioneWidget) -> some View {
        CerchioWidget {
            Text(f.modulo ?? "—").font(.caption.bold()).minimumScaleFactor(0.6).lineLimit(1)
            Text(punti(f)).font(.caption2).monospacedDigit()
        }
    }

    private func rettangolare(_ w: RiassuntoWidget, _ f: FormazioneWidget) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            // con il testo grande resta il modulo: mai «Formazione 3-4…»
            TestoCheEntra(ParoleWidget.titoloFormazione(f.modulo, tuaScelta: f.tuaScelta == true)).font(.headline)
            TestoCheEntra(ParoleWidget.puntiConFascia(f.puntiAttesi, fascia: f.intervallo?.testo))
                .font(.caption).monospacedDigit()
            if !w.daControllare.isEmpty {
                EtichettaDaControllare(n: w.daControllare.count).font(.caption2)
            } else if let g = w.nomeGiornata {
                GiornataInRiga(g).minimumScaleFactor(0.7).font(.caption2).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
