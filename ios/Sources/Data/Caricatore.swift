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
    /// Quante risposte del server sono arrivate. Cresce solo con una risposta nuova: non con la copia salvata, né quando una
    /// lettura annullata rimette lo stato di prima. Chi deve usare solo dati appena arrivati confronta questo numero.
    private(set) var risposte = 0
    /// Perché l'ultimo aggiornamento non è riuscito: nil se il server non era raggiungibile (rete, tempo scaduto) o se è andato bene;
    /// altrimenti il messaggio dell'errore (limite, guasto del server...), da mostrare nella striscia dei dati salvati.
    private(set) var motivoDatiSalvati: String?
    /// Cresce a ogni lettura che parte: una lettura annullata rimette lo stato di prima solo se nel frattempo non ne è partita
    /// un'altra (decide quella).
    private var letture = 0
    /// L'ultimo punto fermo: lo stato a cui è arrivata una lettura (risposta, errore), con la data e l'origine dei dati.
    private var fermo = Fermo()

    /// Uno stato a cui è arrivata una lettura, con quello che lo accompagna. Una lettura annullata dalla schermata lo rimette
    /// com'era, anche un errore o la copia salvata con la sua data (`ricarica`).
    private struct Fermo {
        var stato: Stato<T> = .idle
        /// La richiesta di quello stato: nil prima della prima lettura.
        var richiesta: String?
        var percorsoDelDato: String?
        var scaricatoIl: Date?
        var dallaCache = false
        var motivo: String?
    }

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

    func ricarica(_ nuovoPercorso: String) async {
        percorso = nuovoPercorso
        await ricarica()
    }

    func ricarica() async {
        let richiesto = percorso
        letture += 1
        let questa = letture
        // Dati già a video della stessa risorsa (altrimenti niente: non si mostrano dati di un'altra richiesta). I giorni del
        // certificato non contano: `/api/oggi?certificato_giorni=5` e `=4` sono la stessa giornata, come per la copia salvata.
        var inAttesa: T? = stessaRisorsa(percorsoDelDato, richiesto) ? stato.dato : nil
        var copiaLetta: (dato: T, data: Date)?
        stato = .loading(inAttesa)
        // Subito l'ultima copia salvata, se non c'è già qualcosa da mostrare.
        if inAttesa == nil, usaCache,
           let salvato = await Cache.leggi(richiesto, indirizzo: server.indirizzo), richiesto == percorso,
           let vecchio: T = try? Decodifica.decodifica(salvato.dati, snake: snake) {
            inAttesa = vecchio
            copiaLetta = (vecchio, salvato.data)
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
            motivoDatiSalvati = nil
            risposte += 1
            stato = .loaded(nuovo)
            ricordaFermo(richiesto)
            if usaCache { Cache.salva(dati, richiesto, indirizzo: server.indirizzo) }
        } catch {
            guard richiesto == percorso else { return }
            if Task.isCancelled || error is CancellationError {
                // Annullata dalla schermata (per esempio il telefono bloccato durante un aggiornamento): non è una risposta né un
                // errore. Se nel frattempo è partita un'altra lettura decide quella; altrimenti torna lo stato di prima, anche un
                // errore o la copia salvata con la sua data e la sua striscia. Prima tornavano i dati di prima come appena
                // arrivati, e la striscia «dati salvati» spariva.
                guard questa == letture else { return }
                rimettiFermo(richiesto, copiaLetta: copiaLetta)
                return
            }
            motivoDatiSalvati = DatiVecchi.eDiRete(error) ? nil : error.localizedDescription
            stato = .failed(error.localizedDescription, inAttesa)   // restano gli ultimi dati, con la loro data
            ricordaFermo(richiesto)
            // senza rete resta la copia: quando il telefono ritrova la rete si riprova da soli, una volta, come la web
            if inAttesa != nil, DatiVecchi.eDiRete(error) { RitornoRete.condiviso.aspetta() }
        }
    }

    private func ricordaFermo(_ richiesta: String) {
        fermo = Fermo(stato: stato, richiesta: richiesta, percorsoDelDato: percorsoDelDato, scaricatoIl: scaricatoIl,
                      dallaCache: dallaCache, motivo: motivoDatiSalvati)
    }

    /// Dopo una lettura annullata: lo stato fermo di prima, se era della stessa risorsa (altrimenti niente, come all'inizio). Se
    /// prima non c'era niente da mostrare e intanto si è letta la copia del telefono, resta quella, come copia (`dallaCache`):
    /// accanto all'errore di prima, se c'era, con la data della copia.
    private func rimettiFermo(_ richiesto: String, copiaLetta: (dato: T, data: Date)?) {
        var prima = stessaRisorsa(fermo.richiesta, richiesto) ? fermo : Fermo()
        if prima.stato.dato == nil, let copia = copiaLetta {
            prima.percorsoDelDato = richiesto
            prima.scaricatoIl = copia.data
            prima.dallaCache = true
            if let errore = prima.stato.errore { prima.stato = .failed(errore, copia.dato) } else { prima.stato = .loaded(copia.dato) }
        }
        percorsoDelDato = prima.percorsoDelDato
        scaricatoIl = prima.scaricatoIl
        dallaCache = prima.dallaCache
        motivoDatiSalvati = prima.motivo
        stato = prima.stato          // una volta sola: chi segue lo stato non vede passaggi in mezzo
        ricordaFermo(richiesto)
    }
}

/// Due indirizzi della stessa risorsa: uguali a meno dei giorni del certificato (`Cache.percorsoStabile`).
private func stessaRisorsa(_ a: String?, _ b: String) -> Bool {
    guard let a else { return false }
    return Cache.percorsoStabile(a) == Cache.percorsoStabile(b)
}
