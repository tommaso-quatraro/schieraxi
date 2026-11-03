import SwiftUI
import WidgetKit

/// Un widget rotondo della schermata di blocco: il fondo del sistema e le righe una sotto l'altra, sempre al centro del cerchio
/// (anche nella galleria delle foto, dove il fondo del sistema non occupa spazio e il contenuto finiva in alto a sinistra).
struct CerchioWidget<Contenuto: View>: View {
    @ViewBuilder let contenuto: Contenuto

    var body: some View {
        ZStack {
            AccessoryWidgetBackground()
            // un po' di margine ai lati: le righe in alto e in basso stanno dove il cerchio è più stretto
            VStack(spacing: 0) { contenuto }
                .padding(.horizontal, 8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
