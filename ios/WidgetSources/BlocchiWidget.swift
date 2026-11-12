import WidgetKit
import SwiftUI

// I blocchi che i widget si scambiano: fondo SchieraXI, indirizzi dell'app, conto alla rovescia, righe di giocatori.

/// Gli indirizzi `schieraxi://` che l'app sa aprire (oggi, formazione, squadra, altro, giocatore/<id>).
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

