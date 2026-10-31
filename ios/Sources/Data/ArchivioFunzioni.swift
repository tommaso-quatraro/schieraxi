import SwiftUI
import Combine

/// Tiene le funzioni accese lette dal server. All'inizio (e se il server non risponde) è tutto acceso.
@MainActor
final class ArchivioFunzioni: ObservableObject {
    @Published private(set) var stato = StatoFunzioni.tutteAccese
    /// Vero mentre si salva «Mostra tutte le funzioni».
    @Published private(set) var inSalvataggio = false
    @Published private(set) var errore: String?

    private let server: any ServerClient
    private var ascolto: AnyCancellable?

    init(server: any ServerClient) {
        self.server = server
        ascolto = NotificationCenter.default.publisher(for: .funzioneSpenta)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] n in
                guard let self, let id = n.userInfo?["funzione"] as? String, !id.isEmpty else { return }
                Task { @MainActor in self.stato = self.stato.spenta(id) }
            }
    }

    /// `GET /api/funzioni`. Se non risponde si lascia quello che c'è (all'inizio: tutto acceso).
    func carica() async {
        do {
            let r: RispostaFunzioni = try await server.get("/api/funzioni", snake: false)
            stato = r.stato
        } catch {
            // server vecchio, rete assente o risposta strana: niente da nascondere
        }
    }

    /// `PUT /api/funzioni` con «Mostra tutte le funzioni». Vale solo per questo utente e sta sul server.
    func impostaMostraTutte(_ valore: Bool) async {
        inSalvataggio = true
        errore = nil
        defer { inSalvataggio = false }
        do {
            let dati = try await server.corpoJSON("PUT", "/api/funzioni", CorpoMostraTutte(mostraTutte: valore))
            let r: RispostaFunzioni = try Decodifica.decodifica(dati, snake: false)
            var nuovo = r.stato
            nuovo.mostraTutte = r.mostraTutte ?? valore
            stato = nuovo
        } catch {
            errore = error.localizedDescription
            await carica()
        }
    }
}
