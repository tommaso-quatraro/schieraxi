import SwiftUI

/// Logica della ricerca di un giocatore per nome (la lente accanto al titolo di ogni schermata).
@MainActor
final class RicercaViewModel: ViewModelBase {
    private let server: any ServerClient
    @Published var testo = ""
    @Published var risultati: [GiocatoreBreve] = []
    @Published var errore: String?
    @Published var cercando = false
    /// Fantavoto atteso e «gioca N%» dei risultati, dall'elenco largo della giornata.
    let previsioni: PrevisioniRicerca

    init(server: any ServerClient) {
        self.server = server
        previsioni = PrevisioniRicerca(server: server)
        super.init()
        osserva(previsioni)
        if Demo.attivo, let t = Demo.argomento("DEMO_CERCA") { testo = t }   // solo per le fotografie del simulatore
    }

    /// Cerca dopo una breve pausa: se si continua a scrivere, la vista annulla questa ricerca (`.task(id:)`) e ne parte una nuova.
    func cerca() async {
        let scritto = testo.trimmingCharacters(in: .whitespaces)
        guard scritto.count >= 2 else {
            risultati = []
            errore = nil
            cercando = false
            return
        }
        try? await Task.sleep(nanoseconds: 300_000_000)
        if Task.isCancelled { return }
        previsioni.avvia()
        cercando = true
        defer { cercando = false }
        do {
            let trovati: [GiocatoreBreve] = try await server.get("/api/giocatori?limite=25&q=\(IndirizzoServer.codifica(scritto))")
            if Task.isCancelled { return }
            risultati = trovati
            errore = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            errore = error.localizedDescription
        }
    }
}
