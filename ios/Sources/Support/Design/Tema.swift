import SwiftUI

/// Il «design system» di SchieraXI in un posto solo: misure, animazioni e colori semantici.
/// Le schermate non scrivono numeri o colori a mano: li prendono da qui, così l'app resta coerente.
enum Tema {
    /// Margine laterale delle schermate.
    static let margine: CGFloat = 16
    /// Spazio tra una scheda e la successiva.
    static let spazioSchede: CGFloat = 14
    /// Angoli delle schede (continui, come quelli di iOS).
    static let raggioScheda: CGFloat = 24
    static let raggioPiccolo: CGFloat = 14
    /// Altezza minima di tutto ciò che si tocca (linee guida Apple: 44 pt).
    static let areaTocco: CGFloat = 44

    /// Colori del marchio (punti chiari su fondo scuro, quasi neri su fondo chiaro; capitano lime).
    static let puntiScuro = Color(red: 0.918, green: 0.965, blue: 0.933)
    static let puntiChiaro = Color(red: 0.06, green: 0.12, blue: 0.09)
    static let capitanoScuro = Color(red: 0.831, green: 0.953, blue: 0.290)
    static let capitanoChiaro = Color(red: 0.525, green: 0.659, blue: 0)

    /// Con «Ridurre movimento»: niente spostamenti né rimbalzi, solo dissolvenze brevi (le schermate non restano mai immobili).
    @MainActor static var movimentoRidotto: Bool { UIAccessibility.isReduceMotionEnabled }
    /// La dissolvenza breve che sostituisce ogni animazione di movimento.
    static let quieta: Animation = .easeInOut(duration: 0.3)
    /// Animazione «normale» dell'app: morbida, senza rimbalzo.
    @MainActor static var morbida: Animation { movimentoRidotto ? quieta : .smooth(duration: 0.4) }
    /// Per i cambi di selezione e gli elementi che compaiono: una molla leggera.
    @MainActor static var molla: Animation { movimentoRidotto ? quieta : .spring(duration: 0.45, bounce: 0.22) }
}

extension Color {
    /// Fondo delle schermate (grigio di sistema raggruppato: nero in scuro, grigio chiaro in chiaro).
    static let sfondoBase = Color(uiColor: .systemGroupedBackground)
    /// Fondo delle schede, un gradino sopra lo sfondo.
    static let sfondoScheda = Color(uiColor: .secondarySystemGroupedBackground)
    /// Fondo di campi e pulsanti incassati dentro una scheda.
    static let sfondoIncavo = Color(uiColor: .tertiarySystemFill)

    /// Il lime del capitano (palette di SchieraXI): lime acceso sul fondo scuro, oliva sul fondo chiaro. Per marchio, pillole
    /// selezionate e dettagli: mai per testo piccolo (sul chiaro il contrasto con il bianco è basso).
    static let capitano = Color(uiColor: UIColor { tratti in
        tratti.userInterfaceStyle == .dark ? UIColor(red: 0.831, green: 0.953, blue: 0.290, alpha: 1) : UIColor(red: 0.525, green: 0.659, blue: 0, alpha: 1)
    })

    /// Colori semantici (docs/DESIGN.md, uguali su web e iOS): chiaro sul fondo scuro, scuro sul fondo chiaro, contrasto 4,5:1.
    /// Sempre accompagnati da testo o simbolo, mai solo il colore.
    private static func dinamico(scuro: UInt32, chiaro: UInt32) -> Color {
        func colore(_ n: UInt32) -> UIColor {
            UIColor(red: CGFloat((n >> 16) & 0xff) / 255, green: CGFloat((n >> 8) & 0xff) / 255, blue: CGFloat(n & 0xff) / 255, alpha: 1)
        }
        return Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? colore(scuro) : colore(chiaro) })
    }
    /// Negativo (malus, rischio).
    static let malus = dinamico(scuro: 0xFF6B5E, chiaro: 0xB3261E)
    /// Attenzione (dubbio, diffidato, non bastano i crediti).
    static let attenzione = dinamico(scuro: 0xFFB04A, chiaro: 0x9C5400)
    /// Informazione.
    static let informazione = dinamico(scuro: 0x62A9FF, chiaro: 0x1A5BB5)
    /// Testo secondario sul fondo con sfumatura (più leggibile del grigio di sistema).
    static let testo2 = dinamico(scuro: 0xB3C6BA, chiaro: 0x587064)
    /// Positivo: il colore principale dell'app (verde, o l'accento scelto in Aspetto).
    static var esitoBuono: Color { Color.verde }
    static var esitoAttenzione: Color { Color.attenzione }
    static var esitoMalus: Color { Color.malus }
}

extension View {
    /// Titoli di sezione dentro una scheda (piccoli, in grigio): «Portiere», «Stagione»...
    func titoletto() -> some View {
        font(.subheadline.weight(.semibold))
            .foregroundStyle(.secondary)
            .accessibilityAddTraits(.isHeader)
    }

    /// Un numero che cambia: le cifre scorrono invece di saltare.
    @MainActor
    func numerico(_ valore: Double) -> some View {
        contentTransition(Tema.movimentoRidotto ? .opacity : .numericText(value: valore))
            .animation(Tema.morbida, value: valore)
    }
}

/// Un numero che «sale» da zero al suo valore quando la vista compare, e scorre quando cambia.
/// Per VoiceOver legge subito il valore finale.
struct NumeroCheSale: View {
    let valore: Double
    var formato: (Double) -> String = { Formato.punti($0) }
    @State private var mostrato: Double = 0
    @Environment(\.accessibilityReduceMotion) private var ridotto

    var body: some View {
        // Con «Ridurre movimento» le cifre non scorrono: il numero cambia con una dissolvenza.
        Text(formato(mostrato))
            .monospacedDigit()
            .contentTransition(ridotto ? .opacity : .numericText(value: mostrato))
            .accessibilityLabel(formato(valore))
            .onAppear {
                withAnimation(ridotto ? Tema.quieta : .smooth(duration: 0.9)) { mostrato = valore }
            }
            .onChange(of: valore) { _, nuovo in
                withAnimation(ridotto ? Tema.quieta : .smooth(duration: 0.4)) { mostrato = nuovo }
            }
    }
}

/// Ingresso scaglionato: l'elemento compare con una leggera salita e dissolvenza, un poco dopo il precedente.
/// Con «Ridurre movimento» compare solo con una dissolvenza, senza salire.
struct Ingresso: ViewModifier {
    let ordine: Int
    @State private var visibile = false
    @Environment(\.accessibilityReduceMotion) private var ridotto

    func body(content: Content) -> some View {
        content
            .opacity(visibile ? 1 : 0)
            .offset(y: visibile || ridotto ? 0 : 16)
            .onAppear {
                guard !visibile else { return }
                let ritardo = Double(min(max(ordine, 0), 8)) * (ridotto ? 0.03 : 0.06)
                withAnimation((ridotto ? Tema.quieta : .smooth(duration: 0.5)).delay(ritardo)) { visibile = true }
            }
    }
}

extension View {
    /// Fa comparire la vista con un ingresso morbido, scaglionato secondo `ordine` (0 = per prima).
    func ingresso(_ ordine: Int = 0) -> some View { modifier(Ingresso(ordine: ordine)) }

    /// Le schede che entrano o escono dal bordo dello schermo scorrendo si rimpiccioliscono e si schiariscono appena.
    func entraScorrendo() -> some View {
        scrollTransition(.interactive) { contenuto, fase in
            contenuto
                .opacity(1 - abs(fase.value) * 0.45)
                .scaleEffect(1 - abs(fase.value) * 0.04)
        }
    }
}

/// Una transizione di movimento (scala, scivolata) che con «Ridurre movimento» diventa una semplice dissolvenza.
struct TransizioneQuieta: ViewModifier {
    let normale: AnyTransition
    @Environment(\.accessibilityReduceMotion) private var ridotto

    func body(content: Content) -> some View {
        content.transition(ridotto ? .opacity : normale)
    }
}

extension View {
    func transizione(_ normale: AnyTransition) -> some View { modifier(TransizioneQuieta(normale: normale)) }
}

/// Stile dei pulsanti-riga: nessuna decorazione, ma al tocco la riga si rimpicciolisce appena (come le righe di sistema).
struct StilePressione: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var ridotto

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .opacity(configuration.isPressed ? 0.6 : 1)
            .scaleEffect(configuration.isPressed && !ridotto ? 0.98 : 1)
            .animation(.snappy(duration: 0.18), value: configuration.isPressed)
    }
}

extension Color {
    /// Colore del testo sopra il colore principale pieno: nero sul verde chiaro del tema scuro, bianco sul verde scuro del tema chiaro.
    static let testoSuAccento = Color(uiColor: UIColor { tratti in
        tratti.userInterfaceStyle == .dark ? UIColor.black : UIColor.white
    })
}

extension View {
    /// Una «pillola» di una fila di scelte (moduli, sezioni): quella attiva è lime (il colore del capitano), con testo scuro, e
    /// scivola da una all'altra.
    func pillola(attiva: Bool, spazio: Namespace.ID) -> some View {
        self
            .foregroundStyle(attiva ? Color.black.opacity(0.85) : Color.primary)
            .background {
                ZStack {
                    Capsule().fill(Color.sfondoIncavo)
                    if attiva {
                        Capsule().fill(Color.capitano).matchedGeometryEffect(id: "pillolaAttiva", in: spazio)
                    }
                }
            }
    }
}
