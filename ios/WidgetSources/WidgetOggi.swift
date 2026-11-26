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
            switch voce.caso {
            case .campionatoFinito(let testo):
                // campionato finito (#727): la frase del server, niente giornata né «Nessun dato»
                CampionatoFinitoWidget(testo: testo)
            case .senzaFormazione(let r):
                // entrato a giornata già iniziata senza una formazione (#687): niente consigliata né punti di questa giornata, la
                // prossima da preparare (la stessa vista di Formazione consigliata e Da controllare, #752)
                SenzaFormazioneWidget(riassunto: r, voce: voce)
            case .normale:
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
        }
        .sfondoWidget(accessorio: accessorio)
        // Un tocco sul widget apre l'app sulla formazione (o su «Collega il widget» se non è collegato); durante la giornata
        // in corso o appena finita apre Oggi, dove ci sono i punti fatti e il riepilogo. Per chi è entrato a giornata iniziata
        // (niente punti fatti, `mostraFase` falso) la formazione, che è già quella della prossima.
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

    /// Sotto i numeri: l'ora della copia salvata, con il giorno se non è di oggi (`RigaCopia`, #834).
    @ViewBuilder
    private func statoDati(_ r: RiassuntoOggi) -> some View {
        if voce.datiSalvati {
            RigaCopia(scaricatoIl: r.scaricatoIl, adesso: voce.date)
                .font(.caption2).foregroundStyle(.white.opacity(0.75))
        }
    }

    /// «Prossima: 3 giorni 3 h» (conto alla rovescia alla scadenza della prossima giornata), in un testo solo (#871).
    private func prossimaBreve(_ r: RiassuntoOggi) -> ProssimaConto {
        ProssimaConto(scadenza: r.scadenzaDelConto, adesso: voce.date)
    }

    private func fasePiccolo(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            titoloFase(r, corta: true)
            Text(r.inCorso ? ParoleWidget.chiusa : "Finita").font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.75))
            Spacer(minLength: 0)
            puntiFattiGrandi(r, stile: .largeTitle)
            Text(paroleSottoPunti(r)).font(.caption2).foregroundStyle(.white.opacity(0.8))
            if let fine = r.puntiFineTesto {
                Text(fine).font(.caption2.weight(.semibold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
            }
            if r.finita, r.inizio != nil {
                // con il testo grande il conto va a capo intero sotto «Prossima:»; se nemmeno così c'è posto, tutto più piccolo
                prossimaBreve(r).font(.caption2).foregroundStyle(.white.opacity(0.8)).lineLimit(2).minimumScaleFactor(0.8)
            }
            statoDati(r)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Il medio a giornata in corso o finita. A giornata in corso la frase del server su cosa manca (`in_corso.situazione`, #900:
    /// «Hanno giocato tutti tranne Glauco Brevisi, Teo Kloosmeijer e Cesare Pulinski, che aspettano il recupero; mancano anche i voti
    /// ufficiali.») può essere lunga: va nella colonna di destra se ci sta alla sua misura, se no a tutta larghezza sotto le due
    /// colonne, se no nella colonna di destra rimpicciolita. Si misura (`ViewThatFits`): la frase non si taglia mai con «…».
    @ViewBuilder
    private func faseMedio(_ r: RiassuntoOggi) -> some View {
        if r.inCorso, let frase = r.ancoraDaGiocareTesto {
            ViewThatFits(in: .vertical) {
                colonneMedio(r, frase: frase, stretta: false)
                VStack(alignment: .leading, spacing: 6) {
                    colonneMedio(r, frase: nil, stretta: false)
                    fraseIntera(frase)
                }
                colonneMedio(r, frase: frase, stretta: true)
            }
        } else {
            colonneMedio(r, frase: nil, stretta: false)
        }
    }

    /// La frase su cosa manca alla sua misura, su tutte le righe che servono (così `faseMedio` la misura intera).
    private func fraseIntera(_ frase: String) -> some View {
        Text(frase).font(.caption2).foregroundStyle(.white.opacity(0.8)).fixedSize(horizontal: false, vertical: true)
    }

    /// Le due colonne del medio; `frase` (solo a giornata in corso) va in fondo a quella di destra: intera o, con `stretta` (l'ultima
    /// scelta di `faseMedio`), rimpicciolita fino a entrare in 4 righe, partendo dalla misura normale del testo anche con il testo
    /// grande: così ci sta sempre.
    private func colonneMedio(_ r: RiassuntoOggi, frase: String?, stretta: Bool) -> some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                titoloFase(r)
                Text(r.inCorso ? ParoleWidget.chiusa : "Finita").font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.75))
                Spacer(minLength: 0)
                puntiFattiGrandi(r, stile: .largeTitle)
                Text(paroleSottoPunti(r)).font(.caption).foregroundStyle(.white.opacity(0.8))
                if r.finita, let fine = r.puntiFineTesto {
                    Text(fine).font(.caption.weight(.semibold)).monospacedDigit().foregroundStyle(.white.opacity(0.9))
                }
                Spacer(minLength: 0)
                statoDati(r)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            VStack(alignment: .leading, spacing: 4) {
                if r.inCorso {
                    // «circa 75 a fine giornata» (`formazione.circa_fine`) in mezza larghezza non entra con il numero grande: sopra
                    // «A fine giornata», sotto il numero senza decimali come la testa della Formazione («Differenze ammesse», #774)
                    Label(Catalogo.Oggi.aFineGiornata, systemImage: "chart.line.uptrend.xyaxis").font(.caption.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.8)).lineLimit(1).minimumScaleFactor(0.7)
                    Text(r.puntiFine.map { "circa \(Formato.decimali($0, cifre: 0))" } ?? "—")
                        .font(.system(.title2, design: .rounded).weight(.bold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.6)
                    if r.punti != nil {
                        Text(Catalogo.Oggi.attesiPrima(n: puntiTesto(r))).font(.caption).monospacedDigit()
                            .foregroundStyle(.white.opacity(0.85)).lineLimit(1).minimumScaleFactor(0.7)
                    }
                    Spacer(minLength: 0)
                    if let frase {
                        if stretta {
                            Text(frase).font(.caption2).foregroundStyle(.white.opacity(0.8))
                                .dynamicTypeSize(...DynamicTypeSize.large).lineLimit(4).minimumScaleFactor(0.6)
                        } else {
                            fraseIntera(frase)
                        }
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
            Text("\(r.puntiFattiTesto) \(paroleSottoPunti(r))").font(.headline).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7).widgetAccentable()
            if r.finita, r.inizio != nil {
                // una riga sola nel rettangolo: un testo solo, che si rimpicciolisce tutto insieme
                prossimaBreve(r).font(.caption2).lineLimit(1).minimumScaleFactor(0.6)
            } else if let fine = r.puntiFineTesto {
                Text(fine).font(.caption2).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func faseRiga(_ r: RiassuntoOggi) -> some View {
        // si accorcia di parole intere, mai la giornata: «Giornata 8: 41,5 punti finora» → «Giornata 8: 41,5»
        RigaInLinea(r.formeRigaInLineaFase, icona: r.inCorso ? "dot.radiowaves.left.and.right" : "flag.checkered")
    }

    // MARK: pezzi comuni

    /// Accanto ai punti fatti: a giornata in corso «punti finora», come la testa della Formazione (#774); a giornata finita
    /// «punti fatti». Nel cerchio della schermata di blocco ci sta solo «fatti» («Differenze ammesse»).
    private func paroleSottoPunti(_ r: RiassuntoOggi) -> String {
        r.inCorso ? Catalogo.Formazione.puntiFinora : Catalogo.Oggi.puntiFatti
    }

    private func inCorso(_ r: RiassuntoOggi) -> Bool {
        guard let inizio = r.inizio else { return false }
        return inizio <= voce.date
    }

    private func puntiTesto(_ r: RiassuntoOggi) -> String {
        Formato.punti(r.punti)
    }

    /// Conto alla rovescia come la web («6 h 44 min», «2 giorni 3 h»); «Chiusa» a scadenza passata. Per chi è entrato a giornata
    /// iniziata va alla scadenza della prossima (`scadenzaDelConto`), altrimenti è `inizio`.
    private func conto(_ r: RiassuntoOggi) -> some View {
        ContoWidget(inizio: r.scadenzaDelConto, adesso: voce.date)
    }

    /// «alla scadenza, oggi 05:30» / «… ven 6 03:32»: la data come `quando` della web, contata dall'istante della voce, con
    /// giorno e ora uniti (si va a capo dopo la virgola, #871).
    private func allaScadenza(_ inizio: Date) -> String {
        ParoleWidget.allaScadenza(inizio, adesso: voce.date)
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
            if voce.datiSalvati {
                // la copia salvata, con il giorno se non è di oggi (#834); con i dati freschi «punti attesi» sotto i punti
                RigaCopia(scaricatoIl: r.scaricatoIl, adesso: voce.date).font(.caption2).foregroundStyle(.white.opacity(0.75))
            } else if r.daControllare == 0 && r.probabili != false {
                Text("punti attesi").font(.caption2).foregroundStyle(.white.opacity(0.75))
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
                // a capo allineata a sinistra: dentro un Link le righe si centravano («alla scadenza, oggi / 12:20», #787)
                Text(r.inizio.map(allaScadenza) ?? "")
                    .font(.caption).foregroundStyle(.white.opacity(0.8)).multilineTextAlignment(.leading)
                Spacer(minLength: 0)
                if voce.datiSalvati {
                    RigaCopia(scaricatoIl: r.scaricatoIl, adesso: voce.date).font(.caption2).foregroundStyle(.secondary)
                }
            }
            }
            Link(destination: voce.tocco(URL(string: "schieraxi://formazione")) ?? URL(fileURLWithPath: "/")) {
            VStack(alignment: conDubbi ? .leading : .trailing, spacing: conDubbi ? 2 : 4) {
                Label("Formazione", systemImage: "sportscourt").font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
                if conDubbi {
                    // il modulo è il dato principale e resta intero; i punti accanto perdono «punti» se non c'è posto (#787)
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(r.modulo ?? "—").font(.system(.title2, design: .rounded).weight(.bold))
                            .lineLimit(1).fixedSize()
                        TestoCheEntra(ParoleWidget.punti(r.punti)).font(.caption).monospacedDigit().foregroundStyle(.white.opacity(0.9))
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

    /// La giornata e il conto alla rovescia, il motivo del widget (#871: c'erano modulo e punti, come nella Formazione). Lo
    /// stesso cerchio di chi è entrato a giornata iniziata (`SenzaFormazioneWidget`).
    private func circolare(_ r: RiassuntoOggi) -> some View {
        CerchioWidget {
            Image(systemName: "calendar").font(.caption2).accessibilityHidden(true)
            Text(ParoleWidget.giornataNelCerchio(r.nomeGiornata)).font(.caption2).lineLimit(1).minimumScaleFactor(0.5)
                .accessibilityLabel(r.voceGiornata)
            conto(r).font(.caption.bold()).lineLimit(1).minimumScaleFactor(0.5).widgetAccentable()
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

    /// «Giornata 8: 17 h 50 min», e dove non entra il solo conto alla rovescia (`RiassuntoOggi.formeRigaInLineaConto`): prima
    /// era «3-4-3 · 72,7 punti», la stessa riga della Formazione consigliata (#871). VoiceOver legge il conto a parole intere.
    private func riga(_ r: RiassuntoOggi) -> some View {
        RigaInLinea(r.formeRigaInLineaConto(adesso: voce.date), icona: "calendar", voce: r.voceRigaInLineaConto(adesso: voce.date))
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
