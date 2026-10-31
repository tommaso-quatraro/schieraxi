import WidgetKit
import SwiftUI

// I blocchi che i widget nuovi (Cruscotto, Punti attesi e fatti, Miglior scambio) si scambiano: fondo SchieraXI, indirizzi dell'app,
// conto alla rovescia, grafico a barre dei punti, righe di giocatori, scambio e svincolo in versione compatta.

/// Gli indirizzi `schieraxi://` che l'app sa aprire (oggi, formazione, mercato, scambi, lega, giocatore/<id>).
enum Vai {
    static func url(_ percorso: String) -> URL { URL(string: "schieraxi://\(percorso)") ?? URL(fileURLWithPath: "/") }
    static func giocatore(_ id: Int) -> URL { url("giocatore/\(id)") }
}

/// Il fondo dei widget SchieraXI (verde profondo): usato dai widget e dalla galleria di anteprima.
struct FondoSchieraxi: View {
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato

    var body: some View {
        // Con i widget «tinted» (accentato) o vibranti il fondo lo mette il sistema: il verde sparisce, restano testo e forme.
        if (modoForzato ?? modoSistema) == .fullColor {
            LinearGradient(colors: [Color(red: 0.05, green: 0.42, blue: 0.30), Color(red: 0.02, green: 0.22, blue: 0.26)],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
        } else {
            Color.clear
        }
    }
}

extension TintaWidget {
    /// Il lime solo a colori pieni: con i widget «tinted» di iOS 18 lo colora il sistema (testo normale + `widgetAccentable`).
    static func accento(_ modo: WidgetRenderingMode) -> Color { modo == .fullColor ? lime : .white }
}

/// Conto alla rovescia vivo: ore, minuti e secondi se manca meno di un giorno (lo aggiorna iOS da solo, senza ricaricare il widget),
/// altrimenti giorni e ore; «In corso» a partita iniziata.
struct ContoWidget: View {
    let inizio: Date?
    let adesso: Date

    var body: some View {
        if let inizio, inizio > adesso {
            if inizio.timeIntervalSince(adesso) < 24 * 3600 {
                Text(timerInterval: adesso...inizio, countsDown: true).monospacedDigit()
            } else {
                Text(inizio, style: .relative)
            }
        } else {
            Text(inizio == nil ? "—" : "In corso")
        }
    }
}

/// Un titolo di blocco: piccolo, in maiuscoletto leggero.
struct TitoloBlocco: View {
    let testo: String
    var icona: String? = nil
    var colore: Color = TintaWidget.testo2

    var body: some View {
        Group {
            if let icona { Label(testo, systemImage: icona) } else { Text(testo) }
        }
        .font(.caption2.weight(.semibold))
        .foregroundStyle(colore)
        .lineLimit(1)
    }
}

/// Punti attesi contro punti fatti nelle ultime giornate: due barre per giornata (attesi chiari, fatti in lime se vanno meglio del previsto)
/// e, sotto, lo scarto. Le barre partono da un po' sotto il minimo, altrimenti scarti da 3 punti su 70 non si vedrebbero.
struct GraficoPunti: View {
    let giornate: [PuntiGiornata]
    var altezza: CGFloat = 44
    var conEtichette = true
    var massimo = 5
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }

    private var dati: [PuntiGiornata] {
        Array(giornate.filter { $0.fatti != nil || $0.attesi != nil }.sorted { $0.giornata < $1.giornata }.suffix(massimo))
    }

    private var scala: (base: Double, tetto: Double) {
        let valori = dati.flatMap { [$0.attesi, $0.fatti].compactMap { $0 } }
        guard let alto = valori.max(), let basso = valori.min() else { return (0, 1) }
        let base = max(0, basso - max(1, (alto - basso) * 0.8))
        return (base, max(alto, base + 1))
    }

    private func frazione(_ v: Double?) -> CGFloat {
        guard let v else { return 0 }
        let s = scala
        return CGFloat(min(1, max(0.06, (v - s.base) / (s.tetto - s.base))))
    }

    static func scarto(_ g: PuntiGiornata) -> Double? { g.scarto }

    static func descrizione(_ g: PuntiGiornata) -> String { g.descrizione }

    var body: some View {
        HStack(alignment: .bottom, spacing: 6) {
            ForEach(dati) { g in
                VStack(spacing: 2) {
                    HStack(alignment: .bottom, spacing: 2) {
                        barra(g.attesi, colore: .white.opacity(0.35), accentata: false)
                        barra(g.fatti, colore: (Self.scarto(g) ?? 0) >= 0 ? TintaWidget.accento(modo) : .white.opacity(0.9), accentata: true)
                    }
                    .frame(height: altezza, alignment: .bottom)
                    if conEtichette {
                        Text(Self.scarto(g).map { Formato.conSegno($0) } ?? "—")
                            .monospacedDigit().fontWidget(10, weight: .semibold).lineLimit(1).minimumScaleFactor(0.7)
                        Text("G\(g.giornata)").fontWidget(9).foregroundStyle(TintaWidget.testo2)
                    }
                }
                .frame(maxWidth: .infinity)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Self.descrizione(g))
            }
        }
    }

    private func barra(_ v: Double?, colore: Color, accentata: Bool) -> some View {
        RoundedRectangle(cornerRadius: 2.5)
            .fill(colore)
            .frame(maxWidth: 12)
            .frame(height: max(2, altezza * frazione(v)))
            .widgetAccentable(accentata)
    }
}

/// Una riga con il volto, il nome e (in arancio) cosa c'è da controllare. Un tocco apre la scheda del giocatore.
struct RigaGiocatoreWidget: View {
    let g: GiocatoreWidget
    var lato: CGFloat = 26
    /// false dentro un altro Link (un Link dentro un Link non funziona): la riga e' solo testo.
    var conLink = true

    private var riga: some View {
        HStack(spacing: 8) {
            AvatarMini(g: g, lato: lato)
            VStack(alignment: .leading, spacing: 0) {
                Text(g.nome).font(.footnote.weight(.semibold)).lineLimit(1)
                Text(g.descrizioneStato.isEmpty ? g.partitaBreve : g.descrizioneStato)
                    .font(.caption2).foregroundStyle(g.descrizioneStato.isEmpty ? TintaWidget.testo2 : TintaWidget.attenzione).lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .frame(minHeight: lato)
    }

    var body: some View {
        Group {
            if conLink { Link(destination: Vai.giocatore(g.id)) { riga } } else { riga }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Il miglior scambio in poco spazio: con chi, chi dai e chi ricevi, quanto guadagni.
struct ScambioCompatto: View {
    let scambio: ScambioWidget?
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            TitoloBlocco(testo: "Miglior scambio", icona: "arrow.left.arrow.right")
            if let s = scambio {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(Formato.conSegno(s.guadagnoMio ?? 0)).font(.title3.bold()).monospacedDigit()
                        .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                    Text("punti").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
                Text("Dai \(s.daiTesto)").font(.caption2).lineLimit(1)
                Text("Ricevi \(s.ricevoTesto)").font(.caption2).lineLimit(1)
                if let a = s.altra { Text("con \(a)").fontWidget(9).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
            } else {
                Text("Non ancora calcolato").font(.footnote.weight(.semibold))
                Text("Apri Scambi").font(.caption2).foregroundStyle(TintaWidget.testo2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// Il miglior svincolo in poco spazio: chi entra, al posto di chi, quanto guadagni.
struct SvincoloCompatto: View {
    let svincolo: SvincolatoWidget?
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            TitoloBlocco(testo: "Miglior svincolo", icona: "arrow.triangle.swap")
            if let s = svincolo, let entra = s.entra {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(Formato.conSegno(s.guadagno ?? 0)).font(.title3.bold()).monospacedDigit()
                        .foregroundStyle(TintaWidget.accento(modo)).widgetAccentable()
                    Text("punti").font(.caption2).foregroundStyle(TintaWidget.testo2)
                }
                Text("Prendi \(entra.cognome)").font(.caption2).lineLimit(1)
                if let esce = s.esce { Text("al posto di \(esce.cognome)").font(.caption2).lineLimit(1) }
                if s.fattibile == false {
                    Label("crediti insufficienti", systemImage: "exclamationmark.triangle.fill")
                        .fontWidget(9).foregroundStyle(TintaWidget.attenzione).lineLimit(1)
                }
            } else {
                Text("Non ancora calcolato").font(.footnote.weight(.semibold))
                Text("Apri Squadra > Cambi consigliati").font(.caption2).foregroundStyle(TintaWidget.testo2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

