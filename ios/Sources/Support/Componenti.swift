import SwiftUI

extension Color {
    /// Colore principale dell'app: di solito il verde, ma si cambia in Lega > Aspetto (`Accento`). Chiaro sul fondo scuro,
    /// più scuro sul fondo chiaro (per restare leggibile). Si legge a ogni uso: cambiando scelta l'app si ridisegna (vedi `RadiceView`).
    static var verde: Color {
        Color(uiColor: UIColor { tratti in
            let accento = Accento.corrente
            return tratti.userInterfaceStyle == .dark ? accento.scuro : accento.chiaro
        })
    }
    static let ruoloP = Color(red: 0.95, green: 0.68, blue: 0.20)
    static let ruoloD = Color(red: 0.25, green: 0.78, blue: 0.45)
    static let ruoloC = Color(red: 0.30, green: 0.60, blue: 0.95)
    static let ruoloA = Color(red: 0.92, green: 0.35, blue: 0.35)
}

/// Dispone le schede in 1, 2 o 3 colonne secondo la larghezza disponibile:
/// una sull'iPhone in verticale, due o tre sull'iPad e sui telefoni in orizzontale.
/// Le schede restano nell'ordine in cui sono scritte (si leggono prima la colonna di sinistra, poi quella di destra) e le colonne sono equilibrate in altezza.
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
        // Le schede restano in ORDINE DI LETTURA: la prima colonna prende le prime schede dall'alto in basso, la seconda quelle dopo.
        // (Mettere ogni scheda nella colonna più bassa le sparpagliava: sull'iPad Portiere e Centrocampisti a sinistra,
        // Difensori e Attaccanti a destra.) Il punto di taglio è il centro della scheda rispetto all'altezza totale divisa per le colonne.
        let misure = subviews.map { $0.sizeThatFits(ProposedViewSize(width: l, height: nil)) }
        let totale = misure.reduce(CGFloat(0)) { $0 + max(0, $1.height) + ($1.height > 0 ? spazio : 0) }
        let bersaglio = max(1, totale / CGFloat(n))
        var percorsa: CGFloat = 0
        for indice in subviews.indices {
            let misura = misure[indice]
            let centro = percorsa + max(0, misura.height) / 2
            let colonna = n == 1 ? 0 : max(0, min(n - 1, Int(centro / bersaglio)))
            percorsa += max(0, misura.height) + (misura.height > 0 ? spazio : 0)
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
    var piccolo = false
    // Cresce con la dimensione del testo scelta nelle Impostazioni di iOS (Dynamic Type).
    @ScaledMetric(relativeTo: .caption) private var latoNormale: CGFloat = 26
    @ScaledMetric(relativeTo: .caption) private var latoPiccolo: CGFloat = 20
    private var lato: CGFloat { piccolo ? latoPiccolo : latoNormale }

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
            .font((piccolo ? Font.caption2 : Font.caption).bold())
            .foregroundStyle(.white)
            .frame(width: lato, height: lato)
            .background(colore.gradient, in: RoundedRectangle(cornerRadius: piccolo ? 6 : 8, style: .continuous))
            .accessibilityLabel(nomeRuolo(ruolo))
    }
}

/// Striscia in alto che avvisa quando si vedono dati salvati perché il server non risponde.
struct AvvisoSalvati: ViewModifier {
    let data: Date?

    func body(content: Content) -> some View {
        content
            .safeAreaInset(edge: .top, spacing: 0) {
                if let data {
                    Label("Server non raggiungibile. Dati salvati del \(data.formatted(date: .abbreviated, time: .shortened))", systemImage: "icloud.slash")
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(.primary)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .vetro(in: Capsule(), tinta: Color.orange.opacity(0.35))
                        .padding(.horizontal, Tema.margine)
                        .padding(.bottom, 6)
                        .frame(maxWidth: .infinity)
                        .accessibilityElement(children: .combine)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .animation(Tema.molla, value: data != nil)
    }
}

extension View {
    /// Mostra «dati salvati» se `data` non è nil (vedi `Caricatore.datiSalvati`).
    func avvisoDatiSalvati(_ data: Date?) -> some View {
        modifier(AvvisoSalvati(data: data))
    }
}
