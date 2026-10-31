import WidgetKit
import SwiftUI

// Pezzi comuni dei widget di SchieraXI: avatar illustrati, intestazioni, testo di stato e un messaggio per quando mancano i dati.

/// L'avatar illustrato di un giocatore, nel suo cerchio.
struct AvatarMini: View {
    let g: GiocatoreWidget
    var lato: CGFloat = 28
    var squadra: String? = nil

    var body: some View {
        AvatarVolto(id: g.id, squadra: squadra, portiere: g.ruolo?.uppercased() == "P", tratti: g.avatar)
            .frame(width: lato, height: lato)
            .accessibilityHidden(true)
    }
}

/// Il colore di un esito: lime per l'azione, arancio per l'attenzione, rosso per il male (come nell'app).
enum TintaWidget {
    static let lime = Color(red: 0.831, green: 0.953, blue: 0.290)
    static let attenzione = Color(red: 1.0, green: 0.69, blue: 0.29)
    static let malus = Color(red: 1.0, green: 0.42, blue: 0.37)
    static let testo2 = Color.white.opacity(0.75)
}

/// L'intestazione piccola di un widget: icona, titolo, giornata a destra.
struct IntestazioneWidget: View {
    let titolo: String
    let icona: String
    var destra: String? = nil
    var colore: Color = .white.opacity(0.85)

    var body: some View {
        HStack(spacing: 4) {
            Label(titolo, systemImage: icona).font(.caption.weight(.semibold)).foregroundStyle(colore).lineLimit(1)
            Spacer(minLength: 0)
            if let destra { Text(destra).font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1) }
        }
    }
}

/// «dati delle 14:32» quando il widget mostra una copia, niente quando i dati sono freschi.
struct PiedeDati: View {
    let voce: Voce

    var body: some View {
        if voce.datiSalvati, let r = voce.riassunto {
            Label("dati delle \(r.scaricatoIl.formatted(date: .omitted, time: .shortened))", systemImage: "icloud.slash")
                .font(.caption2).foregroundStyle(TintaWidget.testo2)
        }
    }
}

/// Quando il widget non ha niente da mostrare: dice cosa fare (e, in piccolo, la diagnostica).
struct SenzaDatiWidget: View {
    let voce: Voce
    var compatto = false

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: voce.indirizzoMancante ? "server.rack" : voce.accessoRichiesto ? "person.crop.circle.badge.questionmark" : "wifi.exclamationmark")
            Text(voce.indirizzoMancante ? "Manca il server" : voce.accessoRichiesto ? "Serve l'accesso" : "Nessun dato").font(.caption.bold())
            if !compatto {
                Text("Lega > Widget > Copia il codice, poi Modifica widget")
                    .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
                if let d = voce.diagnostica { Text(d).fontWidget(8).foregroundStyle(.secondary).multilineTextAlignment(.center).lineLimit(2) }
            }
        }
    }
}

extension Voce {
    /// Il riassunto completo, o nil se il server non lo ha ancora (si ricade sui widget «vecchi»).
    var completo: RiassuntoWidget? { widget }
}

// Solo per l'app di anteprima (galleria per gli screenshot): `widgetFamily` e `widgetRenderingMode` di WidgetKit si possono solo leggere,
// quindi la galleria passa la misura voluta con queste due chiavi. Dentro un widget vero restano vuote e vale il valore del sistema.
private struct ChiaveFamigliaForzata: EnvironmentKey { static let defaultValue: WidgetFamily? = nil }
private struct ChiaveRenderForzato: EnvironmentKey { static let defaultValue: WidgetRenderingMode? = nil }

extension EnvironmentValues {
    var famigliaForzata: WidgetFamily? {
        get { self[ChiaveFamigliaForzata.self] }
        set { self[ChiaveFamigliaForzata.self] = newValue }
    }
    var renderForzato: WidgetRenderingMode? {
        get { self[ChiaveRenderForzato.self] }
        set { self[ChiaveRenderForzato.self] = newValue }
    }
}

/// Carattere a misura che segue il testo grande del sistema (Dynamic Type): alla misura normale resta quella di prima.
private struct FontWidgetScalabile: ViewModifier {
    @ScaledMetric private var misura: CGFloat
    let peso: Font.Weight
    let design: Font.Design

    init(_ base: CGFloat, peso: Font.Weight, design: Font.Design) {
        let stile: Font.TextStyle = base <= 9 ? .caption2 : (base <= 12 ? .caption : (base >= 28 ? .largeTitle : .title3))
        _misura = ScaledMetric(wrappedValue: base, relativeTo: stile)
        self.peso = peso
        self.design = design
    }

    func body(content: Content) -> some View {
        content.font(.system(size: misura, weight: peso, design: design))
    }
}

extension View {
    /// Al posto di `.font(.system(size:))`: la misura cresce col testo grande di sistema.
    func fontWidget(_ misura: CGFloat, weight: Font.Weight = .regular, design: Font.Design = .default) -> some View {
        modifier(FontWidgetScalabile(misura, peso: weight, design: design))
    }
}
