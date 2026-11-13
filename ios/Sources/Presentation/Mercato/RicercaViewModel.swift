import SwiftUI

/// Logica della ricerca di un giocatore per nome (la voce Cerca della barra), come la web: al massimo 12 risultati da
/// `/api/giocatori`, con ruolo, nome, club e quotazione.
@MainActor
final class RicercaViewModel: ViewModelBase {
    /// Quanti risultati, come `cercaGiocatori(q, 12)` della web.
    nonisolated static let limite = 12
    /// Sotto le due lettere non si cerca: lo si dice (`avv.scrivi_almeno_due`).
    static let testoVuoto = Catalogo.Avv.scriviAlmenoDue
    /// Nessun risultato (`avv.nessun_giocatore_trovato`).
    static let testoNessuno = Catalogo.Avv.nessunGiocatoreTrovato

    private let server: any ServerClient
    @Published var testo = ""
    @Published var risultati: [GiocatoreBreve] = []
    @Published var errore: String?
    @Published var cercando = false

    init(server: any ServerClient) {
        self.server = server
        super.init()
        if Demo.attivo, let t = Demo.argomento("DEMO_CERCA") { testo = t }   // solo per le fotografie del simulatore
    }

    nonisolated static func percorso(_ scritto: String) -> String {
        "/api/giocatori?limite=\(limite)&q=\(IndirizzoServer.codifica(scritto))"
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
        cercando = true
        defer { cercando = false }
        do {
            let trovati: [GiocatoreBreve] = try await server.get(Self.percorso(scritto))
            if Task.isCancelled { return }
            risultati = trovati
            errore = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            errore = error.localizedDescription
        }
    }
}
