import SwiftUI
import Combine

/// Contenitore dei ViewModel delle sezioni, creato una volta sola all'avvio. Tenerli qui (e non dentro le viste)
/// fa sì che cambiando sezione, soprattutto nella barra laterale dell'iPad, non si perdano dati e modifiche in corso.
@MainActor
final class AppModel: ObservableObject {
    let server: any ServerClient
    let oggi: OggiViewModel
    let formazione: FormazioneViewModel
    /// Cambi consigliati, seguiti, elenco e calendario: pagine della scheda Squadra.
    let mercato: MercatoViewModel
    /// Scambi: pagina della scheda Altro.
    let scambi: ScambiViewModel
    /// Rose, regole e le altre pagine di Squadra e Altro.
    let lega: LegaViewModel
    /// Le funzioni accese (la dieta): cambiando, la radice ridisegna le schede.
    let funzioni: ArchivioFunzioni
    private var ascoltoFunzioni: AnyCancellable?

    init(server: any ServerClient = ServerCorrente.condiviso) {
        self.server = server
        self.oggi = OggiViewModel(server: server)
        self.formazione = FormazioneViewModel(server: server)
        self.mercato = MercatoViewModel(server: server)
        self.scambi = ScambiViewModel(server: server)
        self.lega = LegaViewModel(server: server)
        self.funzioni = ArchivioFunzioni(server: server)
        ascoltoFunzioni = funzioni.objectWillChange.sink { [weak self] _ in self?.objectWillChange.send() }
    }
}
