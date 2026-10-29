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

    /// Animazione «normale» dell'app: morbida, senza rimbalzo.
    static let morbida: Animation = .smooth(duration: 0.4)
    /// Per i cambi di selezione e gli elementi che compaiono: una molla leggera.
    static let molla: Animation = .spring(duration: 0.45, bounce: 0.22)
}

extension Color {
    /// Fondo delle schermate (grigio di sistema raggruppato: nero in scuro, grigio chiaro in chiaro).
    static let sfondoBase = Color(uiColor: .systemGroupedBackground)
    /// Fondo delle schede, un gradino sopra lo sfondo.
    static let sfondoScheda = Color(uiColor: .secondarySystemGroupedBackground)
    /// Fondo di campi e pulsanti incassati dentro una scheda.
    static let sfondoIncavo = Color(uiColor: .tertiarySystemFill)

    /// Esiti: bene, attenzione, male. Sempre accompagnati da testo o simbolo, mai solo il colore.
    static let esitoBuono = Color.green
    static let esitoAttenzione = Color.orange
    static let esitoMalus = Color.red
}

extension View {
    /// Titoli di sezione dentro una scheda (piccoli, in grigio): «Portiere», «Stagione»...
    func titoletto() -> some View {
        font(.subheadline.weight(.semibold))
            .foregroundStyle(.secondary)
            .accessibilityAddTraits(.isHeader)
    }

    /// Un numero che cambia: le cifre scorrono invece di saltare.
    func numerico(_ valore: Double) -> some View {
        contentTransition(.numericText(value: valore))
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
        Text(formato(ridotto ? valore : mostrato))
            .monospacedDigit()
            .contentTransition(.numericText(value: mostrato))
            .accessibilityLabel(formato(valore))
            .onAppear {
                withAnimation(.smooth(duration: 0.9)) { mostrato = valore }
            }
            .onChange(of: valore) { _, nuovo in
                withAnimation(Tema.morbida) { mostrato = nuovo }
            }
    }
}

/// Ingresso scaglionato: l'elemento compare con una leggera salita e dissolvenza, un poco dopo il precedente.
/// Con «Ridurre movimento» compare subito.
struct Ingresso: ViewModifier {
    let ordine: Int
    @State private var visibile = false
    @Environment(\.accessibilityReduceMotion) private var ridotto

    func body(content: Content) -> some View {
        content
            .opacity(visibile || ridotto ? 1 : 0)
            .offset(y: visibile || ridotto ? 0 : 16)
            .onAppear {
                guard !visibile else { return }
                withAnimation(.smooth(duration: 0.5).delay(Double(min(max(ordine, 0), 8)) * 0.06)) { visibile = true }
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
    /// Una «pillola» di una fila di scelte (moduli, sezioni): quella attiva ha il colore principale, che scivola da una all'altra.
    func pillola(attiva: Bool, spazio: Namespace.ID) -> some View {
        self
            .foregroundStyle(attiva ? Color.testoSuAccento : Color.primary)
            .background {
                ZStack {
                    Capsule().fill(Color.sfondoIncavo)
                    if attiva {
                        Capsule().fill(Color.verde).matchedGeometryEffect(id: "pillolaAttiva", in: spazio)
                    }
                }
            }
    }
}
