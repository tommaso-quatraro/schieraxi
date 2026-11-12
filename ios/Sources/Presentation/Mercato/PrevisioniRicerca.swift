import SwiftUI

/// I numeri della giornata per i risultati della ricerca (la lente): come sul web, i risultati si arricchiscono con l'elenco largo
/// dei giocatori della giornata (`/api/classifica`, chi ha almeno il 20% di giocare), scaricato al massimo una volta ogni 5 minuti
/// e senza fermare la ricerca: i risultati compaiono subito, fantavoto atteso e «gioca N%» appena arriva.
/// Se non arriva i risultati restano con volto, ruolo e squadra e si riprova alla ricerca dopo.
@MainActor
final class PrevisioniRicerca: ObservableObject {
    static let percorso = "/api/classifica?liberi=false&limite=800"
    static let durata: TimeInterval = 300

    private let server: any ServerClient
    @Published private(set) var perId: [Int: Giocatore] = [:]
    /// Vero quando l'elenco è arrivato: solo allora chi non c'è si può dire «non gioca».
    @Published private(set) var arrivate = false
    private var quando: Date?
    private var inCorso: Task<Void, Never>?

    init(server: any ServerClient) { self.server = server }

    /// La riga della giornata del giocatore, se è tra quelli dell'elenco largo.
    func di(_ id: Int) -> Giocatore? { perId[id] }

    /// Chiede l'elenco se manca o è vecchio; non aspetta la risposta.
    func avvia() {
        if let quando, Date().timeIntervalSince(quando) < Self.durata { return }
        if inCorso != nil { return }
        inCorso = Task { [weak self] in
            await self?.carica()
        }
    }

    func carica() async {
        defer { inCorso = nil }
        do {
            let elenco: ElencoGiocatori = try await server.get(Self.percorso)
            perId = Dictionary(elenco.giocatori.map { ($0.id, $0) }, uniquingKeysWith: { primo, _ in primo })
            quando = Date()
            arrivate = true
        } catch {
            // niente numeri: si riprova alla prossima ricerca
        }
    }
}
