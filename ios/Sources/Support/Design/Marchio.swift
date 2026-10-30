import SwiftUI

/// Il marchio di SchieraXI: undici punti in formazione 4-3-3 (portiere in basso) e il punto del capitano in evidenza.
/// Disegnato su una griglia 120 x 120, come nell'app web (`PUNTI_MARCHIO` in `fanta/web/app.js`): non si deforma,
/// non si ruota, non si aggiungono punti. Regole complete in `MARCHIO.md` del repository dell'app web.
///
/// Con `muove` i punti passano dal 4-3-3 al 3-5-2 e tornano (2,6 secondi, un punto dopo l'altro) e il capitano pulsa:
/// è il movimento dei caricamenti. Con «Ridurre movimento» di iOS i punti non si spostano: restano al loro posto e il marchio
/// resta vivo con un'onda di opacità (dissolvenza leggera, un punto dopo l'altro), senza spostamenti.
struct Marchio: View {
    /// Lato del quadrato in cui è disegnato.
    var lato: CGFloat = 54
    var muove = false
    /// Solo per le prove (fotografie): blocca il marchio a un momento del ciclo, da 0 a 1 (0,5 = tutto in 3-5-2).
    var fermoAllaFase: Double? = nil
    @Environment(\.accessibilityReduceMotion) private var ridotto
    @Environment(\.colorScheme) private var schema

    /// x, y e spostamento (dx, dy) verso il 3-5-2, per ognuno dei dieci punti di movimento.
    static let punti: [(x: Double, y: Double, dx: Double, dy: Double)] = [
        (34, 28, 11, 0), (60, 25, 15, 3), (86, 28, 14, 22), (30, 50, -10, 0), (90, 50, -10, 0),
        (24, 72, 6, 2), (47, 74, -7, -24), (73, 74, -13, 0), (96, 72, -6, 2), (60, 95, 0, 0),
    ]
    static let raggioPunto = 6.5
    static let raggioCapitano = 9.0
    static let durata = 2.6
    static let ritardoPerPunto = 0.045

    /// Quanto il punto è andato verso il 3-5-2 (0 = 4-3-3, 1 = 3-5-2) a un certo momento del ciclo (0...1):
    /// fermo fino al 16%, in 3-5-2 dal 44% al 66%, di nuovo in 4-3-3 dal 94%.
    static func spostamento(fase p: Double) -> Double {
        func morbida(_ x: Double) -> Double { x < 0.5 ? 4 * x * x * x : 1 - pow(-2 * x + 2, 3) / 2 }
        switch p {
        case ..<0.16: return 0
        case ..<0.44: return morbida((p - 0.16) / 0.28)
        case ..<0.66: return 1
        case ..<0.94: return 1 - morbida((p - 0.66) / 0.28)
        default: return 0
        }
    }

    /// Opacità dell'onda per «Ridurre movimento»: tra `minimo` e 1, un ciclo ogni 2,6 secondi, con un ritardo per ogni punto.
    static func opacitaOnda(_ t: Double, ritardo: Double, minimo: Double = 0.45) -> Double {
        let p = fase(t, ritardo: ritardo)
        return minimo + (1 - minimo) * (1 + cos(2 * .pi * p)) / 2
    }

    /// Fase (0...1) del ciclo al tempo `t`, con il ritardo di un punto.
    static func fase(_ t: Double, ritardo: Double = 0) -> Double {
        let x = (t - ritardo) / durata
        return x - floor(x)
    }

    private var colorePunti: Color { schema == .dark ? Tema.puntiScuro : Tema.puntiChiaro }
    private var coloreCapitano: Color { schema == .dark ? Tema.capitanoScuro : Tema.capitanoChiaro }

    var body: some View {
        TimelineView(.animation(minimumInterval: ridotto ? 1.0 / 15.0 : 1.0 / 30.0, paused: !muove || fermoAllaFase != nil)) { contesto in
            let attivo = fermoAllaFase != nil || (muove && !ridotto)
            // Con «Ridurre movimento»: nessuno spostamento, solo un'onda di opacità.
            let onda = muove && ridotto && fermoAllaFase == nil
            let t: Double = fermoAllaFase.map { $0 * Self.durata } ?? ((attivo || onda) ? contesto.date.timeIntervalSinceReferenceDate : 0)
            Canvas { disegno, dimensione in
                let k = Double(min(dimensione.width, dimensione.height)) / 120
                for (i, p) in Self.punti.enumerated() {
                    let f = attivo ? Self.spostamento(fase: Self.fase(t, ritardo: Double(i) * Self.ritardoPerPunto)) : 0
                    let cx = (p.x + p.dx * f) * k
                    let cy = (p.y + p.dy * f) * k
                    let r = Self.raggioPunto * k
                    let opacita = onda ? Self.opacitaOnda(t, ritardo: Double(i) * 0.12) : 1
                    disegno.fill(Path(ellipseIn: CGRect(x: cx - r, y: cy - r, width: 2 * r, height: 2 * r)), with: .color(colorePunti.opacity(opacita)))
                }
                let pulsa = attivo ? 1 + 0.18 * (1 - cos(2 * .pi * Self.fase(t))) / 2 : 1
                let rc = Self.raggioCapitano * k * pulsa
                let opacitaCapitano = onda ? Self.opacitaOnda(t, ritardo: 0, minimo: 0.7) : 1
                disegno.fill(Path(ellipseIn: CGRect(x: 60 * k - rc, y: 50 * k - rc, width: 2 * rc, height: 2 * rc)), with: .color(coloreCapitano.opacity(opacitaCapitano)))
            }
        }
        .frame(width: lato, height: lato)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("SchieraXI")
    }
}

/// Il marchio con il nome accanto, il nome è sempre «SchieraXI» con la U maiuscola, in carattere arrotondato.
struct MarchioConNome: View {
    var lato: CGFloat = 44
    var body: some View {
        HStack(spacing: 10) {
            Marchio(lato: lato)
            Text("SchieraXI")
                .font(.system(size: lato * 0.72, weight: .semibold, design: .rounded))
                .accessibilityHidden(true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("SchieraXI")
    }
}
