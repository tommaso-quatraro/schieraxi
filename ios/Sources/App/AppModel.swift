import SwiftUI

/// Contenitore dei ViewModel delle sezioni, creato una volta sola all'avvio. Tenerli qui (e non dentro le viste)
/// fa sì che cambiando sezione, soprattutto nella barra laterale dell'iPad, non si perdano dati e modifiche in corso.
@MainActor
final class AppModel: ObservableObject {
    let server: any ServerClient
    let oggi: OggiViewModel
    let formazione: FormazioneViewModel
    let mercato: MercatoViewModel

    init(server: any ServerClient = ServerCorrente.condiviso) {
        self.server = server
        self.oggi = OggiViewModel(server: server)
        self.formazione = FormazioneViewModel(server: server)
        self.mercato = MercatoViewModel(server: server)
    }
}
