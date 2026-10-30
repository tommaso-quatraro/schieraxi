import SwiftUI

/// La ricerca di Mercato > Cerca, separata dal resto della schermata: mentre si scrive cambia SOLO la vista dei risultati
/// (non tutto Mercato). Pausa di 350 ms dopo l'ultimo tasto, ultime ricerche in memoria, risultati a pagine con «Mostra altri».
@MainActor
final class RicercaMercatoViewModel: ObservableObject {
    /// Quanti risultati si chiedono al server e quanti se ne mostrano per volta.
    static let daChiedere = 60
    static let perPagina = 20
    static let pausa: UInt64 = 350_000_000
    static let ricerchePossibili = 20

    private let server: any ServerClient
    @Published var testo = ""
    @Published private(set) var trovati: [GiocatoreBreve] = []
    @Published private(set) var mostrati = RicercaMercatoViewModel.perPagina
    @Published private(set) var errore: String?
    @Published private(set) var cercando = false
    /// La ricerca di cui sono i risultati (il testo ripulito): evita di rifare la stessa richiesta.
    private var ultimaChiave: String?
    private var memoria: [String: [GiocatoreBreve]] = [:]
    private var ordine: [String] = []

    init(server: any ServerClient) { self.server = server }

    /// Il testo pronto per la ricerca: senza spazi ai bordi e in minuscolo.
    static func chiave(_ testo: String) -> String {
        testo.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    var scritto: String { Self.chiave(testo) }
    var abbastanzaLungo: Bool { scritto.count >= 2 }
    var visibili: [GiocatoreBreve] { Array(trovati.prefix(mostrati)) }
    var ciSonoAltri: Bool { trovati.count > mostrati }
    /// «Nessun risultato»: si cercava davvero, ha risposto e non c'è niente.
    var nessunRisultato: Bool { abbastanzaLungo && !cercando && errore == nil && ultimaChiave == scritto && trovati.isEmpty }

    func mostraAltri() { mostrati = min(trovati.count, mostrati + Self.perPagina) }

    /// Da chiamare con `.task(id: testo)`: se si continua a scrivere la vecchia ricerca viene annullata durante la pausa.
    func cerca() async {
        let chiave = scritto
        guard chiave.count >= 2 else {
            trovati = []
            ultimaChiave = nil
            errore = nil
            cercando = false
            mostrati = Self.perPagina
            return
        }
        if chiave == ultimaChiave { return }
        if let salvati = memoria[chiave] {
            imposta(salvati, chiave: chiave)
            return
        }
        cercando = true
        try? await Task.sleep(nanoseconds: Self.pausa)
        if Task.isCancelled { return }
        do {
            let risposta: [GiocatoreBreve] = try await server.get("/api/giocatori?limite=\(Self.daChiedere)&q=\(IndirizzoServer.codifica(chiave))")
            if Task.isCancelled { return }
            ricorda(risposta, chiave: chiave)
            imposta(risposta, chiave: chiave)
        } catch {
            if Task.isCancelled || error is CancellationError { return }   // si è continuato a scrivere: vale la ricerca nuova
            cercando = false
            errore = error.localizedDescription
        }
    }

    private func imposta(_ risposta: [GiocatoreBreve], chiave: String) {
        trovati = risposta
        mostrati = Self.perPagina
        ultimaChiave = chiave
        errore = nil
        cercando = false
    }

    private func ricorda(_ risposta: [GiocatoreBreve], chiave: String) {
        memoria[chiave] = risposta
        ordine.removeAll { $0 == chiave }
        ordine.append(chiave)
        while ordine.count > Self.ricerchePossibili { memoria[ordine.removeFirst()] = nil }
    }
}
