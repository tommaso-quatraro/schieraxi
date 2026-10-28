import SwiftUI

extension Color {
    static let verde = Color(red: 0.19, green: 0.82, blue: 0.50)
    static let ruoloP = Color(red: 0.95, green: 0.68, blue: 0.20)
    static let ruoloD = Color(red: 0.25, green: 0.78, blue: 0.45)
    static let ruoloC = Color(red: 0.30, green: 0.60, blue: 0.95)
    static let ruoloA = Color(red: 0.92, green: 0.35, blue: 0.35)
}

/// Sfondo scuro verde-blu, lo stesso spirito della web app.
struct Sfondo: View {
    var body: some View {
        LinearGradient(
            colors: [Color(red: 0.03, green: 0.10, blue: 0.08), Color(red: 0.05, green: 0.16, blue: 0.12), Color(red: 0.04, green: 0.09, blue: 0.14)],
            startPoint: .top, endPoint: .bottom)
            .ignoresSafeArea()
    }
}

/// Scheda di vetro (materiale di iOS) con un titolo.
struct Carta<Contenuto: View>: View {
    let titolo: String?
    let contenuto: Contenuto

    init(_ titolo: String? = nil, @ViewBuilder contenuto: () -> Contenuto) {
        self.titolo = titolo
        self.contenuto = contenuto()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let titolo {
                Text(titolo).font(.title3.bold())
            }
            contenuto
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.white.opacity(0.12), lineWidth: 1))
    }
}

struct BadgeRuolo: View {
    let ruolo: String

    private var colore: Color {
        switch ruolo {
        case "P": return .ruoloP
        case "D": return .ruoloD
        case "C": return .ruoloC
        default: return .ruoloA
        }
    }

    var body: some View {
        Text(ruolo)
            .font(.caption.bold())
            .foregroundStyle(.white)
            .frame(width: 26, height: 26)
            .background(colore.gradient, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct RigaGiocatore: View {
    let g: Giocatore

    private var sottotitolo: String {
        let mia = g.squadra?.uppercased() ?? ""
        let altra = g.avversario?.uppercased() ?? ""
        if altra.isEmpty { return mia }
        return "\(mia) \(g.inCasa == true ? "vs" : "@") \(altra)"
    }

    var body: some View {
        HStack(spacing: 12) {
            BadgeRuolo(ruolo: g.ruolo)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(g.nome).font(.headline).lineLimit(1)
                    if g.dubbio == true {
                        Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.orange).font(.subheadline)
                    }
                    if g.diffidato == true {
                        Image(systemName: "rectangle.portrait.fill").foregroundStyle(.yellow).font(.caption)
                    }
                }
                Text(sottotitolo).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text((g.puntiAttesi ?? 0).formatted(.number.precision(.fractionLength(1)))).font(.headline).monospacedDigit()
                Text("gioca \(Int(((g.pVoto ?? 0) * 100).rounded()))%").font(.caption2).foregroundStyle(.secondary)
            }
        }
    }
}

/// Striscia in alto che avvisa quando si vedono dati salvati perché il server non risponde.
struct AvvisoSalvati: ViewModifier {
    let data: Date?

    func body(content: Content) -> some View {
        content.safeAreaInset(edge: .top, spacing: 0) {
            if let data {
                Label("Server non raggiungibile. Dati salvati del \(data.formatted(date: .abbreviated, time: .shortened))", systemImage: "icloud.slash")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(.bar)
                    .accessibilityElement(children: .combine)
            }
        }
    }
}

extension View {
    /// Mostra «dati salvati» se `data` non è nil (vedi `Caricatore.datiSalvati`).
    func avvisoDatiSalvati(_ data: Date?) -> some View {
        modifier(AvvisoSalvati(data: data))
    }
}

struct ErroreVista: View {
    let messaggio: String
    let riprova: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "wifi.exclamationmark").font(.largeTitle).foregroundStyle(.orange)
            Text(messaggio).multilineTextAlignment(.center).foregroundStyle(.secondary)
            Button("Riprova", action: riprova).buttonStyle(.borderedProminent)
        }
        .padding(24)
        .frame(maxWidth: .infinity)
    }
}

/// Sezioni non ancora native: dicono come arrivarci intanto.
struct AltroView: View {
    let titolo: String
    let icona: String

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                VStack(spacing: 14) {
                    Image(systemName: icona).font(.system(size: 54)).foregroundStyle(Color.verde)
                    Text("In arrivo nella versione nativa").font(.title3.bold())
                    Text("Per ora questa sezione si usa dalla web app.").foregroundStyle(.secondary)
                    if let url = URL(string: Api.base) {
                        Link("Apri la web app", destination: url).buttonStyle(.borderedProminent)
                    }
                }
                .padding(24)
            }
            .navigationTitle(titolo)
        }
    }
}
