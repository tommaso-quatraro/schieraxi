import SwiftUI

// Caricamento, errore, stato vuoto: uguali in tutte le schermate.
// Al posto del cerchio che gira ci sono scheletri con un lampo di luce che scorre (come nelle app Apple e nei siti moderni);
// con «Ridurre movimento» restano fermi. Per VoiceOver c'è una sola frase: «Caricamento in corso».

/// Un lampo di luce che scorre sulla vista (solo sulle parti piene: lo scheletro).
struct Lampo: ViewModifier {
    @State private var fase: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) private var ridotto

    func body(content: Content) -> some View {
        content
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
                guard !ridotto else { return }
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
struct CartaScheletro: View {
    var righe = 3
    var nascosta = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            BloccoScheletro(larghezza: 150, altezza: 18)
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
        .accessibilityLabel("Caricamento in corso")
        .accessibilityHidden(nascosta)
    }
}

/// Più schede finte una sotto l'altra: il segnaposto di una schermata che sta caricando.
struct Scheletro: View {
    var schede = 3
    var righe = 3

    var body: some View {
        ForEach(0..<schede, id: \.self) { i in
            CartaScheletro(righe: righe, nascosta: i > 0)
                .transition(.opacity)
        }
    }
}

/// Un giro di scheletro per liste senza schede (righe dirette sul fondo).
struct ScheletroRighe: View {
    var righe = 6

    var body: some View {
        VStack(spacing: 18) {
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
        ContentUnavailableView {
            Label("Non riesco a caricare", systemImage: "wifi.exclamationmark")
                .symbolEffect(.pulse, options: .repeat(3))
        } description: {
            Text(messaggio)
        } actions: {
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
            Label(titolo, systemImage: icona)
        } description: {
            if let descrizione { Text(descrizione) }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
    }
}
