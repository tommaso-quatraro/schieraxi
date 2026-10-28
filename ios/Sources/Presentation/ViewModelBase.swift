import SwiftUI
import Combine

/// Base dei ViewModel: una classe `ObservableObject` sul thread principale che sa inoltrare i cambiamenti
/// dei `Caricatore` che contiene (SwiftUI non guarda gli oggetti annidati) e reagire al comando «Aggiorna».
@MainActor
class ViewModelBase: ObservableObject {
    private var osservati = Set<AnyCancellable>()

    /// Quando `altro` cambia, cambia anche questo ViewModel: la vista si ridisegna.
    func osserva<O: ObservableObject>(_ altro: O) where O.ObjectWillChangePublisher == ObservableObjectPublisher {
        altro.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &osservati)
    }

    /// Esegue `azione` quando l'utente preme Cmd+R (comando «Aggiorna»).
    func alComandoAggiorna(_ azione: @escaping @MainActor () async -> Void) {
        NotificationCenter.default.publisher(for: .aggiornaTutto)
            .receive(on: DispatchQueue.main)
            .sink { _ in Task { await azione() } }
            .store(in: &osservati)
    }
}
