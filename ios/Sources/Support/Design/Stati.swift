import SwiftUI

// Caricamento, errore, stato vuoto: uguali in tutte le schermate.
// Al posto del cerchio che gira ci sono scheletri con un lampo di luce che scorre (come nelle app Apple e nei siti moderni);
// con «Ridurre movimento» lo scheletro respira piano (opacità) e il marchio pulsa senza spostarsi. Per VoiceOver c'è una sola frase: «Caricamento in corso».

/// Un lampo di luce che scorre sulla vista (solo sulle parti piene: lo scheletro).
struct Lampo: ViewModifier {
    @State private var fase: CGFloat = 0
    @State private var respiro = false
    @Environment(\.accessibilityReduceMotion) private var ridotto

    func body(content: Content) -> some View {
        content
            // Con «Ridurre movimento» il lampo non scorre: lo scheletro respira piano (solo opacità).
            .opacity(ridotto && respiro ? 0.55 : 1)
            .overlay {
                if !ridotto {
                    GeometryReader { g in
                        let larghezza = g.size.width
                        LinearGradient(colors: [.clear, Color.white.opacity(0.30), .clear], startPoint: .leading, endPoint: .trailing)
                            .frame(width: max(40, larghezza * 0.6))
                            .offset(x: -larghezza * 0.6 + fase * larghezza * 1.8)
                    }
                    .mask { content }
                    .allowsHitTesting(false)
                }
            }
            .onAppear {
                if ridotto {
                    withAnimation(.easeInOut(duration: 1.3).repeatForever(autoreverses: true)) { respiro = true }
                    return
                }
                withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) { fase = 1 }
            }
    }
}

/// Un rettangolo grigio al posto di un testo o di un'immagine che sta arrivando.
struct BloccoScheletro: View {
    var larghezza: CGFloat? = nil
    var altezza: CGFloat = 14
    var raggio: CGFloat = 6

    var body: some View {
        RoundedRectangle(cornerRadius: raggio, style: .continuous)
            .fill(Color.primary.opacity(0.10))
            .frame(width: larghezza, height: altezza)
    }
}

/// Una scheda finta con un titolo e qualche riga (avatar, due testi, un numero).
/// Con `testo` la scheda comincia con il marchio di SchieraXI in movimento (4-3-3 → 3-5-2) e una frase da spogliatoio.
struct CartaScheletro: View {
    var righe = 3
    var nascosta = false
    var testo: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let testo {
                VStack(spacing: 8) {
                    Marchio(lato: 58, muove: true)
                    Text(testo).font(.subheadline.weight(.medium)).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.bottom, 4)
            } else {
                BloccoScheletro(larghezza: 150, altezza: 18)
            }
            ForEach(0..<righe, id: \.self) { _ in
                HStack(spacing: 12) {
                    Circle().fill(Color.primary.opacity(0.10)).frame(width: 44, height: 44)
                    VStack(alignment: .leading, spacing: 8) {
                        BloccoScheletro(altezza: 14)
                        BloccoScheletro(larghezza: 110, altezza: 10)
                    }
                    Spacer(minLength: 8)
                    BloccoScheletro(larghezza: 36, altezza: 20)
                }
            }
        }
        .modifier(Lampo())
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.sfondoScheda, in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(testo ?? "Caricamento in corso")
        .accessibilityHidden(nascosta)
    }
}

/// Più schede finte una sotto l'altra: il segnaposto di una schermata che sta caricando.
/// La prima porta il marchio animato e la frase `testo` («Scelgo gli undici…»).
struct Scheletro: View {
    var schede = 3
    var righe = 3
    var testo = "Un attimo, mister…"

    var body: some View {
        ForEach(0..<schede, id: \.self) { i in
            CartaScheletro(righe: righe, nascosta: i > 0, testo: i == 0 ? testo : nil)
                .transition(.opacity)
        }
    }
}

/// Un giro di scheletro per liste senza schede (righe dirette sul fondo).
struct ScheletroRighe: View {
    var righe = 6

    var body: some View {
        VStack(spacing: 18) {
            Marchio(lato: 44, muove: true).accessibilityHidden(true)
            ForEach(0..<righe, id: \.self) { _ in
                HStack(spacing: 12) {
                    Circle().fill(Color.primary.opacity(0.10)).frame(width: 44, height: 44)
                    VStack(alignment: .leading, spacing: 8) {
                        BloccoScheletro(altezza: 14)
                        BloccoScheletro(larghezza: 120, altezza: 10)
                    }
                    Spacer(minLength: 8)
                    BloccoScheletro(larghezza: 36, altezza: 20)
                }
            }
        }
        .modifier(Lampo())
        .padding(Tema.margine)
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Caricamento in corso")
    }
}

/// Il server non risponde o la richiesta è fallita: spiega e offre «Riprova».
struct ErroreVista: View {
    let messaggio: String
    let riprova: () -> Void
    @State private var tentativi = 0

    var body: some View {
        if messaggio.dicePerNessunaRosa {
            ConfiguraLegaVista()
        } else {
            errore
        }
    }

    /// Un limite di richieste (429): il messaggio dice già quando riprovare e un pulsante «Riprova» sarebbe inutile.
    private var eLimite: Bool {
        messaggio.localizedCaseInsensitiveContains("Riprova tra") || messaggio.localizedCaseInsensitiveContains("Riprova domani")
            || messaggio.localizedCaseInsensitiveContains("troppi tentativi") || messaggio.localizedCaseInsensitiveContains("già fatto")
    }

    private var errore: some View {
        ContentUnavailableView {
            Label(eLimite ? "Limite raggiunto" : "Qualcosa non va", systemImage: eLimite ? "hourglass" : "wifi.exclamationmark")
                .symbolEffect(.pulse, options: .repeat(3))
        } description: {
            // Il testo è quello dell'errore, una volta sola (i messaggi di rete dicono già di controllare la connessione).
            Text(messaggio)
        } actions: {
            if !eLimite {
                Button {
                    tentativi += 1
                    riprova()
                } label: {
                    Label("Riprova", systemImage: "arrow.clockwise").frame(minHeight: Tema.areaTocco)
                }
                .pulsanteVetro(prominente: true)
                .sensoryFeedback(.impact(weight: .light), trigger: tentativi)
                .accessibilityHint("Riprova a contattare il server")
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }
}

/// Stato vuoto: un simbolo, un titolo, una frase.
struct VistaVuota: View {
    let titolo: String
    let icona: String
    var descrizione: String? = nil

    var body: some View {
        ContentUnavailableView {
            VStack(spacing: 10) {
                Marchio(lato: 52).accessibilityHidden(true)
                Text(titolo).font(.title2.bold()).multilineTextAlignment(.center)
            }
            .accessibilityElement(children: .combine)
        } description: {
            if let descrizione { Text(descrizione) }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
    }
}
