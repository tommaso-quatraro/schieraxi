import SwiftUI

/// L'ultima riga (vuota e invisibile) di una lista della Lega, solo per le foto `-fondo` (#425): serve un punto fermo dove far
/// scorrere la lista anche quando le righe sotto arrivano dopo i dati. Senza `-DEMO_FONDO`, e nell'app vera, non c'è.
struct RigaFondoDemo: View {
    var body: some View {
        if FondoDemo.richiesto {
            Color.clear
                .frame(height: 1)
                .id(FondoDemo.idRiga)
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
                .listRowInsets(EdgeInsets())
                .accessibilityHidden(true)
        }
    }
}
