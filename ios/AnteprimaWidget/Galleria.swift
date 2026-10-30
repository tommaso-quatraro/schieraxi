import SwiftUI
import WidgetKit

/// Le misure dei widget in punti. iPhone 6.1"/6.3" e iPad Pro 11" (le misure vere cambiano di poco da un modello all'altro).
enum MisureWidget {
    static var ipad: Bool { UIDevice.current.userInterfaceIdiom == .pad }

    static func dimensione(_ f: WidgetFamily) -> CGSize {
        switch f {
        case .systemSmall: return ipad ? CGSize(width: 155, height: 155) : CGSize(width: 170, height: 170)
        case .systemMedium: return ipad ? CGSize(width: 329, height: 155) : CGSize(width: 364, height: 170)
        case .systemLarge: return ipad ? CGSize(width: 329, height: 345) : CGSize(width: 364, height: 382)
        case .systemExtraLarge: return CGSize(width: 689, height: 345)
        case .accessoryCircular: return CGSize(width: 76, height: 76)
        case .accessoryRectangular: return CGSize(width: 172, height: 76)
        case .accessoryInline: return CGSize(width: 257, height: 26)
        @unknown default: return CGSize(width: 170, height: 170)
        }
    }

    static func nome(_ f: WidgetFamily) -> String {
        switch f {
        case .systemSmall: return "piccolo"
        case .systemMedium: return "medio"
        case .systemLarge: return "grande"
        case .systemExtraLarge: return "extra large"
        case .accessoryCircular: return "cerchio"
        case .accessoryRectangular: return "rettangolo"
        case .accessoryInline: return "riga"
        @unknown default: return "?"
        }
    }

    static func accessorio(_ f: WidgetFamily) -> Bool {
        switch f {
        case .accessoryCircular, .accessoryRectangular, .accessoryInline: return true
        default: return false
        }
    }
}

/// Dispone le anteprime una dopo l'altra e va a capo quando non c'e' piu' posto.
struct Disposizione: Layout {
    var spazio: CGFloat = 14

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let larghezza = proposal.width ?? 400
        var x: CGFloat = 0, y: CGFloat = 0, riga: CGFloat = 0, massimo: CGFloat = 0
        for s in subviews {
            let d = s.sizeThatFits(.unspecified)
            if x > 0 && x + d.width > larghezza { y += riga + spazio; x = 0; riga = 0 }
            x += d.width + spazio
            riga = max(riga, d.height)
            massimo = max(massimo, x - spazio)
        }
        return CGSize(width: massimo, height: y + riga)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, riga: CGFloat = 0
        for s in subviews {
            let d = s.sizeThatFits(.unspecified)
            if x > bounds.minX && x + d.width > bounds.maxX { y += riga + spazio; x = bounds.minX; riga = 0 }
            s.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(d))
            x += d.width + spazio
            riga = max(riga, d.height)
        }
    }
}

/// Un widget come lo vedrebbe la Home: fondo SchieraXI, angoli stondati, margini interni; sulla schermata di blocco un riquadro scuro.
struct RiquadroWidget<Contenuto: View>: View {
    let famiglia: WidgetFamily
    let contenuto: Contenuto

    init(_ famiglia: WidgetFamily, @ViewBuilder _ contenuto: () -> Contenuto) {
        self.famiglia = famiglia
        self.contenuto = contenuto()
    }

    var body: some View {
        let misura = MisureWidget.dimensione(famiglia)
        let blocco = MisureWidget.accessorio(famiglia)
        contenuto
            .environment(\.famigliaForzata, famiglia)
            .padding(blocco ? 0 : 16)
            .frame(width: misura.width, height: misura.height, alignment: .topLeading)
            .background {
                if blocco {
                    RoundedRectangle(cornerRadius: famiglia == .accessoryCircular ? 38 : 12).fill(.black.opacity(0.55))
                } else {
                    FondoSchieraxi()
                }
            }
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: blocco ? (famiglia == .accessoryCircular ? 38 : 12) : 24, style: .continuous))
    }
}

struct Galleria: View {
    @Environment(\.colorScheme) private var schema
    private let args = UserDefaults.standard

    private var scelta: String { args.string(forKey: "GALLERIA") ?? "cruscotto" }
    private var soloBlocco: Bool { scelta.hasSuffix("-blocco") }
    private var widget: String { soloBlocco ? String(scelta.dropLast("-blocco".count)) : scelta }
    private var render: WidgetRenderingMode {
        switch args.string(forKey: "RENDER") {
        case "accentato": return .accented
        case "vivido": return .vibrant
        default: return .fullColor
        }
    }

    private var voce: Voce { DatiGalleria.voce(args.string(forKey: "DATI") ?? "pieni") }

    var body: some View {
        let famiglie = DatiGalleria.famiglie(widget).filter { MisureWidget.accessorio($0) == soloBlocco && (MisureWidget.ipad || $0 != .systemExtraLarge) }
        ZStack {
            (schema == .dark ? Color(white: 0.12) : Color(white: 0.82)).ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    Text("\(widget)\(soloBlocco ? " (schermata di blocco)" : "") · \(MisureWidget.ipad ? "iPad" : "iPhone")")
                        .font(.footnote.weight(.semibold)).foregroundStyle(.secondary)
                    Disposizione {
                        ForEach(famiglie, id: \.self) { f in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(MisureWidget.nome(f)).font(.caption2).foregroundStyle(.secondary)
                                RiquadroWidget(f) { DatiGalleria.vista(widget, voce: voce) }
                                    .environment(\.renderForzato, render)
                            }
                        }
                    }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}
