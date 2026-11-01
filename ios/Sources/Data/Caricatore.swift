import SwiftUI
import Combine

/// Stato di una risorsa del server, uguale per tutte le schermate.
/// `loading` e `failed` portano con sé gli ultimi dati noti (dalla cache o da un caricamento precedente), se ci sono.
enum Stato<T> {
    case idle
    case loading(T?)
    case loaded(T)
    case failed(String, T?)

    var dato: T? {
        switch self {
        case .idle: return nil
        case .loading(let d): return d
        case .loaded(let d): return d
        case .failed(_, let d): return d
        }
    }

    var errore: String? {
        if case .failed(let messaggio, _) = self { return messaggio }
        return nil
    }

    var inCorso: Bool {
        if case .loading = self { return true }
        return false
    }
}

extension Notification.Name {
    /// Il comando «Aggiorna» (Cmd+R) chiede a tutte le schermate di ricaricare.
    static let aggiornaTutto = Notification.Name("it.schieraxi.app.aggiornaTutto")
}

/// Carica un dato dal server e tiene lo stato per le schermate.
/// Mostra subito l'ultima risposta salvata (cache) mentre ricarica; se il server non risponde resta quella,
/// e `datiSalvati` dice di quando è.
@MainActor
final class Caricatore<T: Decodable>: ObservableObject {
    @Published private(set) var stato: Stato<T> = .idle
    var percorso: String
    let snake: Bool

    private let server: any ServerClient
    private let usaCache: Bool
    private var percorsoDelDato: String?
    private var scaricatoIl: Date?
    private var ascolto: AnyCancellable?
    /// true finché i dati mostrati vengono dalla cache e non da una risposta fresca del server.
    private(set) var dallaCache = false

    var dato: T? { stato.dato }
    var errore: String? { stato.errore }
    var inCorso: Bool { stato.inCorso }

    /// Valorizzato solo quando il server NON ha risposto e si vedono dati vecchi: è la data in cui erano stati scaricati.
    /// Durante il caricamento normale (cache mostrata in attesa della risposta) resta nil.
    var datiSalvati: Date? {
        if case .failed(_, let ultimi) = stato, ultimi != nil { return scaricatoIl ?? Date() }
        return nil
    }

    /// `snake: false` per i dati che vanno rimandati al server con le stesse chiavi (regole, impostazioni degli avvisi).
    /// `cache: false` per i dati che si modificano e si rimandano (non si deve ripartire da una copia vecchia).
    /// `ascolta: false` se la schermata gestisce da sola il comando «Aggiorna» (come Oggi, che deve anche riprogrammare i promemoria).
    init(_ percorso: String, snake: Bool = true, cache: Bool = true, ascolta: Bool = true,
         server: any ServerClient = ServerCorrente.condiviso) {
        self.percorso = percorso
        self.snake = snake
        self.usaCache = cache
        self.server = server
        guard ascolta else { return }
        ascolto = NotificationCenter.default.publisher(for: .aggiornaTutto)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                guard let self else { return }
                Task { await self.ricarica() }
            }
    }

    /// Ci sono già dati di QUESTO indirizzo scaricati da poco? (per non rifare una ricerca che il server conta, con gli stessi parametri)
    func haDatiRecenti(per indirizzo: String, entro secondi: TimeInterval, adesso: Date = Date()) -> Bool {
        guard percorsoDelDato == indirizzo, stato.dato != nil, !dallaCache, let quando = scaricatoIl else { return false }
        return adesso.timeIntervalSince(quando) < secondi
    }

    func ricarica(_ nuovoPercorso: String) async {
        percorso = nuovoPercorso
        await ricarica()
    }

    func ricarica() async {
        let richiesto = percorso
        // Dati già a video di questo stesso indirizzo (altrimenti niente: non si mostrano dati di un'altra richiesta).
        var inAttesa: T? = percorsoDelDato == richiesto ? stato.dato : nil
        stato = .loading(inAttesa)
        // Subito l'ultima copia salvata, se non c'è già qualcosa da mostrare.
        if inAttesa == nil, usaCache,
           let salvato = await Cache.leggi(richiesto, indirizzo: server.indirizzo), richiesto == percorso,
           let vecchio: T = try? Decodifica.decodifica(salvato.dati, snake: snake) {
            inAttesa = vecchio
            percorsoDelDato = richiesto
            scaricatoIl = salvato.data
            dallaCache = true
            stato = .loading(vecchio)
        }
        do {
            let dati = try await server.grezzo(richiesto)
            let nuovo: T = try Decodifica.decodifica(dati, snake: snake)
            guard richiesto == percorso else { return }   // nel frattempo la schermata ha chiesto un altro indirizzo
            percorsoDelDato = richiesto
            scaricatoIl = Date()
            dallaCache = false
            stato = .loaded(nuovo)
            if usaCache { Cache.salva(dati, richiesto, indirizzo: server.indirizzo) }
        } catch {
            guard richiesto == percorso else { return }
            if Task.isCancelled || error is CancellationError {
                // Richiesta annullata dalla schermata: non è un errore, si torna a mostrare quello che c'era.
                stato = inAttesa.map { Stato.loaded($0) } ?? .idle
                return
            }
            stato = .failed(error.localizedDescription, inAttesa)   // restano gli ultimi dati, con la loro data
        }
    }
}
