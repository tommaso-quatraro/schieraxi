import SwiftUI

extension Color {
    /// Verde dell'app: chiaro sul fondo scuro, più scuro sul fondo chiaro (per restare leggibile).
    static let verde = Color(uiColor: UIColor { tratti in
        tratti.userInterfaceStyle == .dark
            ? UIColor(red: 0.19, green: 0.82, blue: 0.50, alpha: 1)
            : UIColor(red: 0.04, green: 0.50, blue: 0.27, alpha: 1)
    })
    static let ruoloP = Color(red: 0.95, green: 0.68, blue: 0.20)
    static let ruoloD = Color(red: 0.25, green: 0.78, blue: 0.45)
    static let ruoloC = Color(red: 0.30, green: 0.60, blue: 0.95)
    static let ruoloA = Color(red: 0.92, green: 0.35, blue: 0.35)
}

/// Sfondo verde-blu come la web app: scuro in modalità scura, chiaro in modalità chiara (segue il sistema).
struct Sfondo: View {
    @Environment(\.colorScheme) private var schema

    var body: some View {
        LinearGradient(
            colors: schema == .dark
                ? [Color(red: 0.03, green: 0.10, blue: 0.08), Color(red: 0.05, green: 0.16, blue: 0.12), Color(red: 0.04, green: 0.09, blue: 0.14)]
                : [Color(red: 0.93, green: 0.98, blue: 0.95), Color(red: 0.89, green: 0.96, blue: 0.93), Color(red: 0.91, green: 0.95, blue: 0.98)],
            startPoint: .top, endPoint: .bottom)
            .ignoresSafeArea()
    }
}

/// Dispone le schede in 1, 2 o 3 colonne secondo la larghezza disponibile:
/// una sull'iPhone in verticale, due o tre sull'iPad e sui telefoni in orizzontale.
/// Ogni scheda va nella colonna più bassa, così le colonne restano equilibrate.
struct Colonne: Layout {
    var spazio: CGFloat = 14
    var larghezzaMinima: CGFloat = 340
    var massimo: Int = 3

    private struct Disposizione {
        var posizioni: [CGPoint] = []
        var dimensioni: [CGSize] = []
        var larghezzaColonna: CGFloat = 0
        var altezza: CGFloat = 0
    }

    private func disponi(_ larghezza: CGFloat, _ subviews: Subviews) -> Disposizione {
        var n = 1
        if subviews.count > 1 {
            n = Int(max(0, larghezza + spazio) / (larghezzaMinima + spazio))
            n = max(1, min(massimo, min(n, subviews.count)))
        }
        let l = (larghezza - spazio * CGFloat(n - 1)) / CGFloat(n)
        var altezze = Array(repeating: CGFloat(0), count: n)
        var d = Disposizione()
        d.larghezzaColonna = l
        for sub in subviews {
            let misura = sub.sizeThatFits(ProposedViewSize(width: l, height: nil))
            var colonna = 0
            for i in altezze.indices where altezze[i] < altezze[colonna] { colonna = i }
            let vuota = misura.height <= 0
            let y = (altezze[colonna] > 0 && !vuota) ? altezze[colonna] + spazio : altezze[colonna]
            let x = CGFloat(colonna) * (l + spazio) + max(0, (l - misura.width) / 2)   // centrata nella colonna
            d.posizioni.append(CGPoint(x: x, y: y))
            d.dimensioni.append(misura)
            altezze[colonna] = y + misura.height
        }
        d.altezza = altezze.max() ?? 0
        return d
    }

    private func larghezzaUsabile(_ proposta: ProposedViewSize) -> CGFloat {
        let w = proposta.width ?? 400
        return w.isFinite ? w : 400
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let w = larghezzaUsabile(proposal)
        return CGSize(width: w, height: disponi(w, subviews).altezza)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let d = disponi(bounds.width, subviews)
        for (i, sub) in subviews.enumerated() {
            let p = d.posizioni[i]
            sub.place(at: CGPoint(x: bounds.minX + p.x, y: bounds.minY + p.y), anchor: .topLeading,
                      proposal: ProposedViewSize(width: d.larghezzaColonna, height: nil))
        }
    }
}

extension View {
    /// Effetto del puntatore (iPad con mouse o trackpad) sulle schede che si possono toccare.
    func puntatore() -> some View {
        contentShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
            .hoverEffect(.lift)
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
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.primary.opacity(0.12), lineWidth: 1))
    }
}

extension String {
    /// Solo la prima lettera maiuscola («listone e quotazioni» → «Listone e quotazioni»); `capitalized` le metterebbe a ogni parola.
    var primaMaiuscola: String {
        guard let prima = first else { return self }
        return prima.uppercased() + dropFirst()
    }
}

/// Riga «titolo a sinistra, valore a destra» di elenchi e impostazioni. Se con il testo grande non ci stanno
/// sulla stessa riga, il valore va sotto il titolo (invece di spezzare le parole a metà).
struct RigaValore: View {
    let titolo: String
    let valore: String
    var cifreFisse = false

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) {
                Text(titolo).fixedSize()
                Spacer(minLength: 8)
                testoValore.fixedSize()
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(titolo)
                testoValore.multilineTextAlignment(.leading)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private var testoValore: some View {
        if cifreFisse {
            Text(valore).foregroundStyle(.secondary).monospacedDigit()
        } else {
            Text(valore).foregroundStyle(.secondary).multilineTextAlignment(.trailing)
        }
    }
}

/// Nome esteso del ruolo, per VoiceOver.
func nomeRuolo(_ ruolo: String) -> String {
    switch ruolo {
    case "P": return "portiere"
    case "D": return "difensore"
    case "C": return "centrocampista"
    case "A": return "attaccante"
    default: return "ruolo sconosciuto"
    }
}

struct BadgeRuolo: View {
    let ruolo: String
    // Cresce con la dimensione del testo scelta nelle Impostazioni di iOS (Dynamic Type).
    @ScaledMetric(relativeTo: .caption) private var lato: CGFloat = 26

    private var colore: Color {
        switch ruolo {
        case "P": return .ruoloP
        case "D": return .ruoloD
        case "C": return .ruoloC
        case "A": return .ruoloA
        default: return .gray
        }
    }

    var body: some View {
        Text(ruolo)
            .font(.caption.bold())
            .foregroundStyle(.white)
            .frame(width: lato, height: lato)
            .background(colore.gradient, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .accessibilityLabel(nomeRuolo(ruolo))
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

    private var puntiTesto: String { (g.puntiAttesi ?? 0).formatted(.number.precision(.fractionLength(1))) }
    private var giocaPercento: Int { Formato.percento(g.pVoto) }

    /// Frase letta da VoiceOver per tutta la riga.
    private var descrizioneVoce: String {
        var parti = [g.nome, nomeRuolo(g.ruolo)]
        if !sottotitolo.isEmpty { parti.append(sottotitolo.replacingOccurrences(of: "@", with: "in trasferta contro")) }
        if g.assente == true {
            parti.append("assente")
        } else {
            parti.append("punti attesi \(puntiTesto)")
            parti.append("gioca al \(giocaPercento) per cento")
        }
        if g.dubbio == true { parti.append("in dubbio") }
        if g.diffidato == true { parti.append("diffidato") }
        return parti.joined(separator: ", ")
    }

    var body: some View {
        HStack(spacing: 12) {
            BadgeRuolo(ruolo: g.ruolo)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(g.nome).font(.headline).lineLimit(1)
                    if g.dubbio == true {
                        Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.orange).font(.subheadline)
                            .accessibilityLabel("In dubbio")
                    }
                    if g.diffidato == true {
                        Image(systemName: "rectangle.portrait.fill").foregroundStyle(.yellow).font(.caption)
                            .accessibilityLabel("Diffidato")
                    }
                }
                Text(sottotitolo).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if g.assente == true {
                // Un assente non ha previsione: niente «0.0 punti, gioca 0%».
                Label("Assente", systemImage: "xmark.circle.fill").font(.caption.bold()).foregroundStyle(.red)
            } else {
                VStack(alignment: .trailing, spacing: 2) {
                    Text(puntiTesto).font(.headline).monospacedDigit()
                    Text("gioca \(giocaPercento)%").font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(descrizioneVoce)
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
            Image(systemName: "wifi.exclamationmark").font(.largeTitle).foregroundStyle(.orange).accessibilityHidden(true)
            Text(messaggio).multilineTextAlignment(.center).foregroundStyle(.secondary)
            Button("Riprova", action: riprova)
                .buttonStyle(.borderedProminent)
                .frame(minHeight: 44)
                .accessibilityHint("Riprova a contattare il server")
        }
        .padding(24)
        .frame(maxWidth: .infinity)
    }
}

/// Stato vuoto (come ContentUnavailableView di iOS 17, ma disponibile anche su iOS 16).
struct VistaVuota: View {
    let titolo: String
    let icona: String
    var descrizione: String? = nil

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icona).font(.largeTitle).foregroundStyle(.secondary).accessibilityHidden(true)
            Text(titolo).font(.headline)
            if let descrizione {
                Text(descrizione).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(24)
        .accessibilityElement(children: .combine)
    }
}
