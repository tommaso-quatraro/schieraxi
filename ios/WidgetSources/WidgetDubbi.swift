import WidgetKit
import SwiftUI

/// Widget «Da controllare»: i giocatori della formazione consigliata con un dubbio, un infortunio o una squalifica.
/// Ogni riga porta alla scheda del giocatore (`schieraxi://giocatore/<id>`), il resto del widget a Oggi.
/// Famiglie: medio e grande (Home, anche su iPad) e rettangolo (Schermata di blocco).
struct WidgetDubbi: Widget {
    let kind = "SchieraxiDubbi"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaDubbi(voce: voce)
        }
        .configurationDisplayName("Da controllare")
        .description("Chi della tua formazione ha un dubbio, un infortunio o una squalifica. Tocca un nome per aprire la sua scheda.")
        .supportedFamilies([.systemMedium, .systemLarge, .accessoryRectangular])
    }
}

struct VistaDubbi: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    let voce: Voce

    private var accessorio: Bool { famiglia == .accessoryRectangular }

    private var massimo: Int {
        switch famiglia {
        case .systemLarge: return 6
        case .systemMedium: return 3
        default: return 2
        }
    }

    var body: some View {
        Group {
            if voce.widget?.acceso(FunzioneWidget.extra) == false {
                spento
            } else if let r = voce.riassunto {
                if accessorio { rettangolare(r) } else { contenuto(r) }
            } else {
                senzaDati
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(voce.tocco(URL(string: "schieraxi://oggi")))
    }

    // MARK: Home

    private func contenuto(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            // con il testo grande il titolo lascia il posto al simbolo (mai «Da contr…»)
            // a giornata finita la testata dice la giornata finita, non la prossima
            IntestazioneWidget(titolo: "Da controllare",
                               icona: r.daControllare > 0 ? "exclamationmark.triangle.fill" : "checkmark.seal.fill",
                               colore: r.daControllare > 0 ? .orange : .white.opacity(0.85),
                               giornata: r.nomeTestata, soloCorta: famiglia == .systemSmall)
            if let titolo = r.titoloFase {
                // formazione chiusa: i dubbi non contano più (i punti stanno in Oggi e nel widget Prossima giornata).
                // Parole della web: «Chiusa» dopo la scadenza, «Giornata 8 · 11ª di Serie A: finita» a giornata finita.
                Spacer(minLength: 0)
                // nel widget piccolo senza «11ª di Serie A» («Giornata 8: finita»); VoiceOver legge i due numeri
                let forme = r.formeTitoloFase ?? [titolo]
                GiornataInRiga(forme: famiglia == .systemSmall && forme.count > 1 ? Array(forme.dropFirst()) : forme,
                               voce: r.voceTitoloFase ?? titolo)
                    .font(.headline).minimumScaleFactor(0.7)
                if let frase = r.fraseFase(adesso: voce.date) {
                    Text(frase).font(.caption).foregroundStyle(.white.opacity(0.8))
                }
                Spacer(minLength: 0)
            } else if r.daControllare == 0 {
                Spacer(minLength: 0)
                Text("Nessun dubbio in formazione").font(.headline)
                Text(r.probabili == false ? "Le probabili non sono ancora uscite." : "Tutti i titolari sono a posto.")
                    .font(.caption).foregroundStyle(.white.opacity(0.8))
                Spacer(minLength: 0)
            } else if let dubbi = r.dubbi, !dubbi.isEmpty {
                // tante righe quante ne entrano in altezza (testo grande, iPad): le altre in «e altri N», mai una riga tagliata in fondo
                let prove = DisposizioneWidget.righeDaProvare(massimo: massimo, totale: dubbi.count)
                PrimaCheEntra(prove.count, in: .vertical) { i in
                    // nel medio righe più strette: così entrano tre giocatori e «e un altro», come prima
                    VStack(alignment: .leading, spacing: famiglia == .systemMedium ? 2 : 6) {
                        ForEach(dubbi.prefix(prove[i])) { d in
                            Link(destination: Vai.giocatore(d.id)) { riga(d) }
                        }
                        if dubbi.count > prove[i] {
                            Text(RiassuntoWidget.altri(dubbi.count - prove[i])).font(.caption2).foregroundStyle(.white.opacity(0.7))
                        }
                    }
                }
                .frame(maxHeight: .infinity, alignment: .top)
            } else {
                Spacer(minLength: 0)
                EtichettaDaControllare(n: r.daControllare).font(.title3.bold())
                Text("Apri SchieraXI per i nomi.").font(.caption).foregroundStyle(.white.opacity(0.8))
                Spacer(minLength: 0)
            }
            if voce.datiSalvati {
                Label("dati delle \(Quando.ora(r.scaricatoIl))", systemImage: "icloud.slash")
                    .font(.caption2).foregroundStyle(.white.opacity(0.7))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func riga(_ d: DubbioRiassunto) -> some View {
        HStack(spacing: 8) {
            Text(d.ruolo ?? "·")
                .font(.caption2.weight(.bold))
                .frame(width: 20, height: 20)
                .background(Circle().fill(.white.opacity(0.18)))
            VStack(alignment: .leading, spacing: 0) {
                Text(d.nome).font(.subheadline.weight(.semibold)).lineLimit(1)
                Text(d.descrizione).font(.caption2).foregroundStyle(.white.opacity(0.75)).lineLimit(1)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.white.opacity(0.5))
        }
        .frame(minHeight: 28)
    }

    // MARK: Schermata di blocco

    private func rettangolare(_ r: RiassuntoOggi) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            // le stesse parole delle altre forme: «4 da controllare», «Chiusa», «Giornata 8: finita», «Titolari a posto»
            if r.daControllare > 0 {
                EtichettaDaControllare(n: r.daControllare).font(.headline)
            } else {
                GiornataInRiga(forme: r.formeTitoloFase ?? ["Titolari a posto"], voce: r.voceTitoloFase ?? "Titolari a posto")
                    .font(.headline).minimumScaleFactor(0.7)
            }
            if let dubbi = r.dubbi, !dubbi.isEmpty {
                ForEach(dubbi.prefix(2)) { d in
                    TestoCheEntra(d.formeRiga).font(.caption2)
                }
            } else {
                GiornataInRiga(forme: r.formeSottotitoloRettangolo, voce: r.voceSottotitoloRettangolo)
                    .font(.caption2).foregroundStyle(.secondary).minimumScaleFactor(0.7)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// «Widget aggiuntivi» spenti dal server per questo utente: un messaggio breve, non un guasto.
    private var spento: some View {
        VStack(spacing: 4) {
            Image(systemName: "moon.zzz")
            Text("Widget spento").font(.caption.bold())
            if !accessorio {
                Text("Non è attivo per il tuo account. Usa Prossima giornata o Formazione.")
                    .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
        }
    }

    /// Non collegato: «Tocca per collegare»; collegato ma senza dati: «Nessun dato».
    private var senzaDati: some View {
        SenzaDatiWidget(voce: voce, compatto: accessorio)
    }
}
