import SwiftUI

/// I numeri della giornata per i risultati delle ricerche (elenco dei giocatori e lente): come sul web, i risultati si arricchiscono
/// con l'elenco largo dei giocatori della giornata (`/api/classifica`, chi ha almeno il 20% di giocare), scaricato al massimo una
/// volta ogni 5 minuti e senza fermare la ricerca: i risultati compaiono subito, fantavoto atteso, «gioca N%» e indice appena arriva.
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

    /// La riga dell'elenco del giocatore (la stessa dell'elenco dei giocatori), se è tra quelli della giornata.
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

/// La ricerca di Mercato > Cerca, separata dal resto della schermata: mentre si scrive cambia SOLO la vista dei risultati
/// (non tutto Mercato). Pausa di 350 ms dopo l'ultimo tasto, ultime ricerche in memoria, risultati a pagine con «Mostra altri».
/// Ogni risultato ha i numeri della giornata (`PrevisioniRicerca`), così è uguale a una riga dell'elenco.
@MainActor
final class RicercaMercatoViewModel: ViewModelBase {
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
    let previsioni: PrevisioniRicerca

    init(server: any ServerClient) {
        self.server = server
        previsioni = PrevisioniRicerca(server: server)
        super.init()
        osserva(previsioni)
    }

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
            previsioni.avvia()
            imposta(salvati, chiave: chiave)
            return
        }
        cercando = true
        try? await Task.sleep(nanoseconds: Self.pausa)
        if Task.isCancelled { return }
        previsioni.avvia()
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
