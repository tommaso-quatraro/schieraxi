import WidgetKit
import SwiftUI

/// Widget «Miglior scambio»: lo scambio che conviene di piu' con un'altra squadra della lega (chi dai, chi ricevi, quanto guadagni tu e loro).
/// Il server lo manda solo se lo aveva gia' calcolato (apri Scambi nell'app): il widget non fa mai partire calcoli.
/// Misure: piccolo (guadagno), medio (chi dai e chi ricevi), grande (con i volti e il confronto), rettangolo, riga.
struct WidgetScambio: Widget {
    let kind = "SchieraxiScambio"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaScambio(voce: voce)
        }
        .configurationDisplayName("Miglior scambio")
        .description("Lo scambio che conviene di piu', con chi lo fai e quanto guadagni.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline])
    }
}

struct VistaScambio: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }
    let voce: Voce

    private var accessorio: Bool { famiglia == .accessoryRectangular || famiglia == .accessoryInline }

    var body: some View {
        Group {
            if let w = voce.completo {
                if let s = w.scambio { contenuto(s) } else { senzaScambio }
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(voce.tocco(Vai.url("scambi")))
    }

    private var senzaScambio: some View {
        VStack(alignment: .leading, spacing: 4) {
            if famiglia == .accessoryInline {
                Label("Scambio: apri SchieraXI", systemImage: "arrow.left.arrow.right")
            } else {
                TitoloBlocco(testo: "Miglior scambio", icona: "arrow.left.arrow.right")
                if !accessorio { Spacer(minLength: 0) }
                Text("Non ancora calcolato").font(.headline)
                Text("Apri Scambi nell'app: poi il widget lo mostra.").font(.caption).foregroundStyle(accessorio ? Color.secondary : TintaWidget.testo2)
                if !accessorio { Spacer(minLength: 0) }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func contenuto(_ s: ScambioWidget) -> some View {
        switch famiglia {
        case .systemMedium: medio(s)
        case .systemLarge: grande(s)
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 1) {
                Text("Scambio \(Formato.conSegno(s.guadagnoMio ?? 0)) punti").font(.headline).lineLimit(1)
                Text("Dai \(s.daiTesto)").font(.caption).lineLimit(1)
                Text("Ricevi \(s.ricevoTesto)").font(.caption).lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        case .accessoryInline:
            // se i nomi non entrano resta il guadagno: mai «Zanvolo, Car…»
            let forme = s.formeInLinea
            PrimaCheEntra(forme.count) { i in
                Label(forme[i], systemImage: "arrow.left.arrow.right")
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(s.frase)
        default: piccolo(s)
        }
    }

    private func guadagno(_ valore: Double?, corpo: CGFloat) -> some View {
        Text(Formato.conSegno(valore ?? 0)).monospacedDigit().fontWidget(corpo, weight: .bold, design: .rounded)
            .lineLimit(1).minimumScaleFactor(0.6)
            .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
    }

    private func piccolo(_ s: ScambioWidget) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            IntestazioneWidget(titolo: "Scambio", icona: "arrow.left.arrow.right")
            Spacer(minLength: 0)
            guadagno(s.guadagnoMio, corpo: 40)
            Text("punti attesi per te").font(.caption2).foregroundStyle(TintaWidget.testo2)
            Text("Dai \(s.daiTesto)").font(.caption).lineLimit(1)
            Text("Ricevi \(s.ricevoTesto)").font(.caption).lineLimit(1)
            PiedeDati(voce: voce)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(s.frase)
    }

    /// Una colonna di giocatori: volto e cognome, o solo il cognome se manca lo spazio.
    private func colonna(_ titolo: String, _ elenco: [GiocatoreScambio]?, lato: CGFloat, massimo: Int, conVolti: Bool = true) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(titolo).font(.caption2.weight(.semibold)).foregroundStyle(TintaWidget.testo2)
            ForEach(Array((elenco ?? []).prefix(massimo).enumerated()), id: \.offset) { _, g in
                let giocatore = g.comeGiocatore
                let riga = HStack(spacing: 6) {
                    if conVolti { AvatarMini(g: giocatore, lato: lato) }
                    VStack(alignment: .leading, spacing: 0) {
                        Text(g.cognome).font(.footnote.weight(.semibold)).lineLimit(1)
                        if let r = g.ruolo { Text(r).font(.caption2).foregroundStyle(TintaWidget.testo2) }
                    }
                }
                if let id = g.id { Link(destination: Vai.giocatore(id)) { riga } } else { riga }
            }
            if (elenco?.count ?? 0) > massimo {
                Text(RiassuntoWidget.altri((elenco?.count ?? 0) - massimo)).font(.caption2).foregroundStyle(TintaWidget.testo2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Medio: il guadagno a sinistra, chi dai e chi ricevi a destra. Il medio dell'iPad e degli iPhone da 6,1" è più stretto:
    /// si tiene la prima forma che entra in larghezza, così i cognomi restano interi (mai «Vlase…»): prima la colonna di sinistra
    /// più stretta (il testo va a capo), poi via i volti, infine chi dai e chi ricevi su due righe di testo.
    private func medio(_ s: ScambioWidget) -> some View {
        PrimaCheEntra(4) { i in
            HStack(alignment: .center, spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    IntestazioneWidget(titolo: "Scambio", icona: "arrow.left.arrow.right")
                    Spacer(minLength: 0)
                    guadagno(s.guadagnoMio, corpo: 36)
                    Text("punti attesi per te").font(.caption2).foregroundStyle(TintaWidget.testo2)
                    // nella colonna stretta il nome della squadra va a capo intero, mai «con Real Madr…»
                    if let a = s.altra { Text("con \(a)").font(.caption2).lineLimit(2) }
                    PiedeDati(voce: voce)
                }
                .frame(width: i == 1 ? 80 : nil, alignment: .leading)
                .frame(maxWidth: 120, alignment: .leading)
                if i < 3 {
                    colonna("Dai", s.do, lato: 26, massimo: 2, conVolti: i < 2)
                    Image(systemName: "arrow.right").font(.caption).foregroundStyle(TintaWidget.testo2).accessibilityHidden(true)
                    colonna("Ricevi", s.ricevo, lato: 26, massimo: 2, conVolti: i < 2)
                } else {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Dai \(s.daiTesto)").font(.footnote.weight(.semibold))
                        Text("Ricevi \(s.ricevoTesto)").font(.footnote.weight(.semibold))
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    private func grande(_ s: ScambioWidget) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                TitoloBlocco(testo: "Miglior scambio", icona: "arrow.left.arrow.right")
                Spacer()
                // un nome di squadra lungo va a capo intero sotto, mai «con Real Madr…»
                if let a = s.altra {
                    Text("con \(a)").font(.caption).foregroundStyle(TintaWidget.testo2).multilineTextAlignment(.trailing)
                }
            }
            HStack(alignment: .top, spacing: 10) {
                colonna("Dai", s.do, lato: 40, massimo: 3)
                Image(systemName: "arrow.right").foregroundStyle(TintaWidget.testo2).padding(.top, 24).accessibilityHidden(true)
                colonna("Ricevi", s.ricevo, lato: 40, massimo: 3)
            }
            Spacer(minLength: 0)
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 0) {
                    guadagno(s.guadagnoMio, corpo: 40)
                    Text("punti attesi per te").font(.caption).foregroundStyle(TintaWidget.testo2)
                }
                VStack(alignment: .leading, spacing: 0) {
                    Text(Formato.conSegno(s.guadagnoLoro ?? 0)).monospacedDigit().fontWidget(40, weight: .bold, design: .rounded).lineLimit(1).minimumScaleFactor(0.5)
                        .lineLimit(1).minimumScaleFactor(0.6)
                    Text("per loro").font(.caption).foregroundStyle(TintaWidget.testo2)
                }
                Spacer(minLength: 0)
            }
            if s.valido == false {
                Label("Le rose dopo lo scambio non sarebbero valide", systemImage: "exclamationmark.triangle.fill")
                    .font(.caption).foregroundStyle(TintaWidget.attenzione)
            }
            PiedeDati(voce: voce)
        }
    }
}
