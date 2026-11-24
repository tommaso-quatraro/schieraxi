import SwiftUI
import WidgetKit

/// I widget per chi è entrato in SchieraXI a giornata già iniziata senza una formazione per lei (`senza_formazione`, #687, #752),
/// come la web: la giornata già iniziata con «Questa giornata è già iniziata», l'invito «Prepara la prossima» e il conto alla
/// rovescia alla scadenza della prossima. Niente consigliata, punti o dubbi di quella giornata (non l'ha schierata). Lo mostrano
/// Prossima giornata, Formazione consigliata e Da controllare, in ogni misura; il caso lo sceglie `CasoWidget`, le parole e le
/// forme vengono da `RiassuntoOggi` e `ParoleWidget` (provate dai test).
struct SenzaFormazioneWidget: View {
    let riassunto: RiassuntoOggi
    let voce: Voce
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }

    var body: some View {
        contenuto
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(riassunto.descrizioneSenzaFormazione ?? ParoleWidget.preparaProssima)
    }

    @ViewBuilder
    private var contenuto: some View {
        switch famiglia {
        case .systemMedium: medio
        // solo Formazione consigliata e Da controllare: tutto in alto, raggruppato
        case .systemLarge, .systemExtraLarge: grande
        case .accessoryCircular: circolare
        case .accessoryRectangular: rettangolare
        // «Prepara la prossima: 4 giorni 2 h» → «Prepara la prossima», mai tagliata
        case .accessoryInline: RigaInLinea(riassunto.formeRigaInLineaSenzaFormazione(adesso: voce.date), icona: "calendar")
        default: colonna(corta: true, invito: .headline, conConto: true)
        }
    }

    /// La giornata già iniziata, «Questa giornata è già iniziata» e «Prepara la prossima» (`conConto`: sotto, «Prossima: 4 giorni
    /// 2 h»). Dove con il testo grande non entra tutto va via la riga «Questa giornata è già iniziata» (VoiceOver la legge
    /// comunque): mai una riga tagliata.
    private func colonna(corta: Bool, invito: Font, conConto: Bool) -> some View {
        PrimaCheEntra(2, in: .vertical) { i in
            VStack(alignment: .leading, spacing: 2) {
                titolo(corta: corta)
                if i == 0 {
                    Text(ParoleWidget.giaIniziata).font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.75))
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
                Text(ParoleWidget.preparaProssima).font(invito)
                    .fixedSize(horizontal: false, vertical: true)
                    .widgetAccentable()
                if conConto, riassunto.scadenzaDelConto != nil {
                    // con il testo grande il conto va a capo intero sotto «Prossima:», della stessa grandezza (#871)
                    prossimaBreve.font(.caption2).foregroundStyle(.white.opacity(0.8))
                        .fixedSize(horizontal: false, vertical: true)
                }
                statoDati
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private var medio: some View {
        HStack(alignment: .top, spacing: 16) {
            colonna(corta: false, invito: .system(.title3, design: .rounded).weight(.bold), conConto: false)
            // a destra la prossima come a giornata finita: la giornata, il conto alla rovescia e quando si chiude
            VStack(alignment: .leading, spacing: 4) {
                if let prossima = riassunto.prossimaDaPreparare {
                    GiornataInRiga(forme: riassunto.formeProssimaDaPreparare, voce: riassunto.voceProssimaDaPreparare, simbolo: "calendar")
                        .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).minimumScaleFactor(0.7)
                    conto.font(.system(.title2, design: .rounded).weight(.bold)).lineLimit(1).minimumScaleFactor(0.5)
                    if let scadenza = prossima.scadenza {
                        Text(allaScadenza(scadenza)).font(.caption2).foregroundStyle(.white.opacity(0.8)).lineLimit(2)
                    }
                }
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Grande ed extra large: tutto in alto e raggruppato, la giornata già iniziata, «Prepara la prossima» e subito sotto la prossima
    /// giornata con il conto alla rovescia e quando si chiude; lo spazio libero resta sotto, mai in mezzo. Se con il testo grande
    /// non entra tutto va via per prima la riga «Questa giornata è già iniziata» (VoiceOver la legge comunque): mai una riga tagliata.
    private var grande: some View {
        PrimaCheEntra(2, in: .vertical) { i in
            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    titolo(corta: false)
                    if i == 0 {
                        Text(ParoleWidget.giaIniziata).font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.75))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Text(ParoleWidget.preparaProssima).font(.system(.title2, design: .rounded).weight(.bold))
                    .fixedSize(horizontal: false, vertical: true)
                    .widgetAccentable()
                if let prossima = riassunto.prossimaDaPreparare {
                    VStack(alignment: .leading, spacing: 4) {
                        GiornataInRiga(forme: riassunto.formeProssimaDaPreparare, voce: riassunto.voceProssimaDaPreparare, simbolo: "calendar")
                            .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).minimumScaleFactor(0.7)
                        conto.font(.system(.title, design: .rounded).weight(.bold)).lineLimit(1).minimumScaleFactor(0.5)
                        if let scadenza = prossima.scadenza {
                            Text(allaScadenza(scadenza)).font(.caption).foregroundStyle(.white.opacity(0.8))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                statoDati
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private var circolare: some View {
        CerchioWidget {
            Image(systemName: "calendar").font(.caption2)
            // la prossima: «Giornata 9», rimpicciolita se serve, mai «G9» (#299)
            Text(ParoleWidget.giornataNelCerchio(riassunto.prossimaDaPreparare?.nomeGiornata)).font(.caption2).lineLimit(1).minimumScaleFactor(0.5)
            if riassunto.scadenzaDelConto != nil {
                conto.font(.caption.bold()).lineLimit(1).minimumScaleFactor(0.5).widgetAccentable()
            }
        }
    }

    private var rettangolare: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(ParoleWidget.giaIniziata).font(.caption2).foregroundStyle(.secondary).lineLimit(1).minimumScaleFactor(0.7)
            Text(ParoleWidget.preparaProssima).font(.headline).lineLimit(1).minimumScaleFactor(0.7).widgetAccentable()
            if riassunto.scadenzaDelConto != nil {
                // una riga sola nel rettangolo: un testo solo, che si rimpicciolisce tutto insieme
                prossimaBreve.font(.caption2).lineLimit(1).minimumScaleFactor(0.6)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: pezzi comuni

    /// La giornata già iniziata con il simbolo della giornata in corso: «Giornata 8 · 11ª di Serie A», se non entra «Giornata 8»
    /// (nel piccolo, `corta`, solo questa), mai «G8» (#299). VoiceOver legge i due numeri.
    private func titolo(corta: Bool) -> some View {
        let nome = riassunto.nomeGiornata
        let ripiego = riassunto.etichettaGiornata
        return GiornataInRiga(forme: nome.map { corta ? [$0.corto] : ParoleWidget.formeGiornata($0) } ?? [ripiego],
                              voce: nome?.voce ?? ripiego, simbolo: "dot.radiowaves.left.and.right")
            .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.8)).minimumScaleFactor(0.7)
    }

    /// Conto alla rovescia alla scadenza della prossima (`scadenzaDelConto`), come la web («4 giorni 2 h»).
    private var conto: some View {
        ContoWidget(inizio: riassunto.scadenzaDelConto, adesso: voce.date)
    }

    /// «Prossima: 4 giorni 2 h», in un testo solo (#871).
    private var prossimaBreve: ProssimaConto {
        ProssimaConto(scadenza: riassunto.scadenzaDelConto, adesso: voce.date)
    }

    /// «alla scadenza, lun 23 20:35»: la data come `quando` della web, contata dall'istante della voce, con giorno e ora uniti
    /// (si va a capo dopo la virgola, #871).
    private func allaScadenza(_ scadenza: Date) -> String {
        ParoleWidget.allaScadenza(scadenza, adesso: voce.date)
    }

    /// Sotto l'invito: l'ora della copia salvata, con il giorno se non è di oggi (`RigaCopia`, #834).
    @ViewBuilder
    private var statoDati: some View {
        if voce.datiSalvati {
            RigaCopia(scaricatoIl: riassunto.scaricatoIl, adesso: voce.date)
                .font(.caption2).foregroundStyle(.white.opacity(0.75))
        }
    }
}
