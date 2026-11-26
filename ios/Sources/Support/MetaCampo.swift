import SwiftUI

/// La linea di metà campo e il cerchio, al centro della fascia libera di `DisposizioneCampo`. Le righe arrivano a 4 punti dal
/// bordo della fascia: nel campo, che ha 6 punti di margine ai lati, toccano il rettangolo esterno (a 10 punti dal bordo).
struct MetaCampo: View {
    var body: some View {
        GeometryReader { g in
            let w = g.size.width, h = g.size.height
            Path { p in
                p.move(to: CGPoint(x: 4, y: h / 2))
                p.addLine(to: CGPoint(x: w - 4, y: h / 2))
                p.addEllipse(in: CGRect(x: w / 2 - 34, y: h / 2 - 34, width: 68, height: 68))
            }
            .stroke(Color.white.opacity(0.28), lineWidth: 1.5)
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}
