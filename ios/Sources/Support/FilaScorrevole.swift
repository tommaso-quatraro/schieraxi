import SwiftUI

/// Una fila di scelte (stili, moduli) che scorre di lato. Quando a destra o a sinistra c'è altro da vedere,
/// compare una sfumatura con una freccia: la barra non sembra «finita» quando non lo è.
struct FilaScorrevole<Contenuto: View>: View {
    @ViewBuilder let contenuto: () -> Contenuto
    @State private var altroDopo = false
    @State private var altroPrima = false

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) { contenuto() }
        }
        .onScrollGeometryChange(for: Bool.self) { $0.contentOffset.x + $0.containerSize.width < $0.contentSize.width - 2 } action: { _, nuovo in
            altroDopo = nuovo
        }
        .onScrollGeometryChange(for: Bool.self) { $0.contentOffset.x > 2 } action: { _, nuovo in
            altroPrima = nuovo
        }
        .overlay(alignment: .trailing) { if altroDopo { indicatore("chevron.right", verso: .trailing) } }
        .overlay(alignment: .leading) { if altroPrima { indicatore("chevron.left", verso: .leading) } }
        .animation(.easeInOut(duration: 0.15), value: altroDopo)
        .animation(.easeInOut(duration: 0.15), value: altroPrima)
    }

    private func indicatore(_ simbolo: String, verso: Edge) -> some View {
        Image(systemName: simbolo)
            .font(.caption.weight(.bold))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 6)
            .frame(maxHeight: .infinity)
            .background(
                LinearGradient(colors: [Color.sfondoScheda.opacity(0), Color.sfondoScheda],
                               startPoint: verso == .trailing ? .leading : .trailing,
                               endPoint: verso == .trailing ? .trailing : .leading)
            )
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}
