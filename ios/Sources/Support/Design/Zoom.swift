import SwiftUI

private struct SpazioZoomChiave: EnvironmentKey {
    static let defaultValue: Namespace.ID? = nil
}

extension EnvironmentValues {
    /// Lo spazio dei nomi della transizione a zoom verso la scheda di un giocatore (lo imposta la radice dell'app).
    var spazioZoom: Namespace.ID? {
        get { self[SpazioZoomChiave.self] }
        set { self[SpazioZoomChiave.self] = newValue }
    }
}

extension View {
    /// Questa vista è il punto da cui la scheda del giocatore `id` si apre a zoom (e a cui si richiude).
    @ViewBuilder
    func origineZoom(_ id: Int, _ spazio: Namespace.ID?) -> some View {
        if let spazio {
            self.matchedTransitionSource(id: id, in: spazio)
        } else {
            self
        }
    }
}

extension View {
    /// Questa vista (la scheda del giocatore `id`) si apre con lo zoom dal punto segnato con `origineZoom`.
    @ViewBuilder
    func arrivoZoom(_ id: Int, _ spazio: Namespace.ID?) -> some View {
        if let spazio {
            self.navigationTransition(.zoom(sourceID: id, in: spazio))
        } else {
            self
        }
    }
}
