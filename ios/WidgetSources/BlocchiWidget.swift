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

/// Conto alla rovescia alla scadenza come la web: «2 giorni 3 h», «6 h 44 min», «12 min» (`Quando.contoAllaRovescia`, senza secondi);
/// «Chiusa» dopo la scadenza, come la web (`ParoleWidget.conto`). Il testo è quello dell'istante della voce: le voci per ogni minuto
/// le prepara il `Fornitore` (`conConto`), senza ricaricare il widget.
struct ContoWidget: View {
    let inizio: Date?
    let adesso: Date

    var body: some View {
        let testo = ParoleWidget.conto(fino: inizio, adesso: adesso)
        Text(testo)
            .monospacedDigit()
            .accessibilityLabel(inizio.flatMap { Quando.contoAllaRovesciaParlato(fino: $0, adesso: adesso) } ?? testo)
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

    private var dati: [PuntiGiornata] { PuntiGiornata.perGrafico(giornate, massimo: massimo) }

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
                        Text(g.sigla).fontWidget(9).foregroundStyle(TintaWidget.testo2)
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
/// Le righe di un elenco si mettono con `RigheDaControllare`, che sceglie la forma che entra.
struct RigaGiocatoreWidget: View {
    /// Quanto spazio c'è: tutto; senza il volto; cognome e stato corto («gioca 70%»).
    enum Forma: CaseIterable { case completa, senzaVolto, breve }

    let g: GiocatoreWidget
    var lato: CGFloat = 26
    /// false dentro un altro Link (un Link dentro un Link non funziona): la riga e' solo testo.
    var conLink = true
    var forma = Forma.completa

    /// Lo stato intero, o la partita se non c'è niente da guardare.
    private var stato: String { g.descrizioneStato.isEmpty ? g.partitaBreve : g.descrizioneStato }

    private var statoMostrato: String {
        guard forma == .breve, !g.descrizioneStato.isEmpty else { return stato }
        return ParoleWidget.stato(stato).last ?? stato
    }

    private var riga: some View {
        HStack(spacing: 8) {
            if forma != .senzaVolto { AvatarMini(g: g, lato: lato) }
            // 1 pt di aria tra nome e stato: le due righe non si toccano
            VStack(alignment: .leading, spacing: 1) {
                Text(forma == .breve ? g.cognome : g.nome).font(.footnote.weight(.semibold)).lineLimit(1)
                Text(statoMostrato)
                    .font(.caption2).foregroundStyle(g.descrizioneStato.isEmpty ? TintaWidget.testo2 : TintaWidget.attenzione).lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .frame(minHeight: forma == .senzaVolto ? nil : lato)
    }

    var body: some View {
        Group {
            if conLink { Link(destination: Vai.giocatore(g.id)) { riga } } else { riga }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(g.nome), \(stato)")
    }
}

/// Il miglior scambio in poco spazio: con chi, chi dai e chi ricevi, quanto guadagni. I nomi vanno a capo interi nella colonna
/// stretta (mai «Ricevi Lumb…»); `compatto` toglie la squadra e mette il guadagno accanto al titolo (`ProvaCruscotto`).
struct ScambioCompatto: View {
    let scambio: ScambioWidget?
    var compatto = false

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            if let s = scambio {
                TestaBloccoCompatto(titolo: "Miglior scambio", titoloCorto: "Scambio", icona: "arrow.left.arrow.right",
                                    guadagno: s.guadagnoMio ?? 0, compatto: compatto)
                Text("Dai \(s.daiTesto)").font(.caption2)
                Text("Ricevi \(s.ricevoTesto)").font(.caption2)
                if !compatto, let a = s.altra { Text("con \(a)").fontWidget(9).foregroundStyle(TintaWidget.testo2) }
            } else {
                TitoloBlocco(testo: compatto ? "Scambio" : "Miglior scambio", icona: "arrow.left.arrow.right")
                Text("Non ancora calcolato").font(.footnote.weight(.semibold))
                Text("Apri Scambi").font(.caption2).foregroundStyle(TintaWidget.testo2)
            }
        }
        // dentro un Link il testo su più righe andrebbe al centro
        .multilineTextAlignment(.leading)
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// Il miglior svincolo in poco spazio: chi entra, al posto di chi, quanto guadagni. Come `ScambioCompatto`, i testi vanno a capo
/// interi (mai «Apri Squadra > Cambi co…»).
struct SvincoloCompatto: View {
    let svincolo: SvincolatoWidget?
    var compatto = false

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            if let s = svincolo, let entra = s.entra {
                TestaBloccoCompatto(titolo: "Miglior svincolo", titoloCorto: "Svincolo", icona: "arrow.triangle.swap",
                                    guadagno: s.guadagno ?? 0, compatto: compatto)
                Text("Prendi \(entra.cognome)").font(.caption2)
                if let esce = s.esce { Text("al posto di \(esce.cognome)").font(.caption2) }
                if s.fattibile == false {
                    Label("crediti insufficienti", systemImage: "exclamationmark.triangle.fill")
                        .fontWidget(9).foregroundStyle(TintaWidget.attenzione)
                }
            } else {
                TitoloBlocco(testo: compatto ? "Svincolo" : "Miglior svincolo", icona: "arrow.triangle.swap")
                Text("Non ancora calcolato").font(.footnote.weight(.semibold))
                Text("Apri Squadra > Cambi consigliati").font(.caption2).foregroundStyle(TintaWidget.testo2)
            }
        }
        .multilineTextAlignment(.leading)
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

