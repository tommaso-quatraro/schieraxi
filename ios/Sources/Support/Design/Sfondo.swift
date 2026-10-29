import SwiftUI

/// Sfondo delle schermate: il grigio di sistema (nero in scuro) con un alone morbido del colore principale in alto,
/// che sfuma verso il basso. Con le barre di iOS 26 i contenuti scorrono sotto e l'alone si vede attraverso il vetro.
struct Sfondo: View {
    @Environment(\.colorScheme) private var schema

    var body: some View {
        ZStack(alignment: .top) {
            Color.sfondoBase
            MeshGradient(width: 3, height: 3, points: Self.punti, colors: colori)
                .frame(height: 380)
                .mask { LinearGradient(colors: [.black, .black.opacity(0.0)], startPoint: .top, endPoint: .bottom) }
                .opacity(schema == .dark ? 0.34 : 0.28)
                .accessibilityHidden(true)
        }
        .ignoresSafeArea()
    }

    private static let punti: [SIMD2<Float>] = [
        SIMD2(0, 0), SIMD2(0.5, 0), SIMD2(1, 0),
        SIMD2(0, 0.5), SIMD2(0.62, 0.42), SIMD2(1, 0.5),
        SIMD2(0, 1), SIMD2(0.5, 1), SIMD2(1, 1),
    ]

    private var colori: [Color] {
        let principale: Color = Color.verde
        let freddo: Color = principale.mix(with: .blue, by: 0.45)
        let caldo: Color = principale.mix(with: .yellow, by: 0.25)
        let riga1: [Color] = [principale, freddo, principale]
        let riga2: [Color] = [caldo, principale, freddo]
        let riga3: [Color] = [.clear, .clear, .clear]
        return riga1 + riga2 + riga3
    }
}

/// Sfondo vivo del riquadro principale di «Oggi»: una rete di colori che si muove piano (ferma con «Ridurre movimento»).
struct MagiaColori: View {
    @Environment(\.accessibilityReduceMotion) private var ridotto

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 20.0, paused: ridotto)) { contesto in
            let t = ridotto ? 0 : contesto.date.timeIntervalSinceReferenceDate
            MeshGradient(width: 3, height: 3, points: punti(t), colors: Self.colori)
        }
        .accessibilityHidden(true)
    }

    /// I nove punti della rete: quelli centrali ondeggiano piano.
    private func punti(_ t: Double) -> [SIMD2<Float>] {
        let a: Float = Float(sin(t * 0.55)) * 0.08
        let b: Float = Float(cos(t * 0.43)) * 0.08
        let alto: [SIMD2<Float>] = [SIMD2(0, 0), SIMD2(0.5 + a, 0), SIMD2(1, 0)]
        let medio: [SIMD2<Float>] = [SIMD2(0, 0.5 - b), SIMD2(0.5 + b, 0.5 + a), SIMD2(1, 0.5 + b)]
        let basso: [SIMD2<Float>] = [SIMD2(0, 1), SIMD2(0.5 - a, 1), SIMD2(1, 1)]
        return alto + medio + basso
    }

    private static let colori: [Color] = {
        let righe: [[Color]] = [
            [Color(red: 0.02, green: 0.28, blue: 0.20), Color(red: 0.03, green: 0.38, blue: 0.30), Color(red: 0.02, green: 0.22, blue: 0.30)],
            [Color(red: 0.05, green: 0.45, blue: 0.28), Color(red: 0.08, green: 0.55, blue: 0.40), Color(red: 0.04, green: 0.35, blue: 0.45)],
            [Color(red: 0.01, green: 0.16, blue: 0.14), Color(red: 0.02, green: 0.26, blue: 0.22), Color(red: 0.02, green: 0.15, blue: 0.24)],
        ]
        return righe.flatMap { $0 }
    }()
}
