import SwiftUI
import UniformTypeIdentifiers

/// Le pagine che si aprono dalle Impostazioni (#673 passo 3: hanno preso anche quelle delle schede Squadra e Altro, come la web).
enum PaginaImpostazioni: Hashable {
    /// La mia lega: Aggiorna le rose, l'elenco delle squadre (Le altre squadre, o la scelta della propria), la rosa di una squadra
    /// (La mia squadra, con stemma e maglia), Regole e scadenza, la nuova stagione.
    case importa, squadre, rosa(String), regole, stagione
    /// Le righe che aprono una pagina loro: Il tuo account, Informazioni, Gestione (solo per chi gestisce il server).
    case account, informazioni, gestione
    /// Pagine aperte da un'altra pagina: stato dei dati (Gestione), crediti e novità (Informazioni), cambio di server.
    case stato, crediti, novita, cambiaServer
}

/// Le parti della pagina Impostazioni che un indirizzo può portare in vista (`?vista=impostazioni&sezione=` della web).
enum ParteImpostazioni: String, Hashable {
    case avvisi, lega, aspetto

    /// L'identificativo della prima riga della parte, dove la pagina scorre (`ScrollViewReader`): una riga, non la sezione (un
    /// modificatore su una Section finisce su ogni sua riga).
    var ancora: String {
        switch self {
        case .avvisi: return "imp-avvisi"
        case .lega: return "imp-rose"
        case .aspetto: return "imp-aspetto"
        }
    }
}

/// Logica delle Impostazioni: stato del server, squadre della lega (per La mia lega), nuova stagione, aggiornamento dei dati.
@MainActor
final class LegaViewModel: ViewModelBase {
    let server: any ServerClient
    let info: Caricatore<InfoServer>
    /// Le rose sono della stagione in corso o di una passata? (se passata, compare il passaggio di stagione)
    let stagione: Caricatore<StatoStagione>
    /// L'aggiornamento dei dati del server (tasto «Aggiorna i dati»), con il suo stato.
    let aggiornamento: AggiornaDatiViewModel
    /// Le squadre della lega: quante sono e qual è la propria (le voci di La mia lega, come `paginaImpostazioni` della web).
    let squadre: Caricatore<[SquadraLega]>
    /// Le pagine aperte nella pila delle Impostazioni (nell'AppModel: cambiando sezione si resta dove si era).
    @Published var percorso: [PaginaImpostazioni] = []

    /// Apre una pagina (e quelle che ci stanno sopra) nelle Impostazioni e dice quale voce della barra mostrare.
    @discardableResult
    func apri(_ pagine: [PaginaImpostazioni]) -> Sezione {
        percorso = pagine
        return .impostazioni
    }

    init(server: any ServerClient) {
        self.server = server
        info = Caricatore<InfoServer>("/api/stato", server: server)
        stagione = Caricatore<StatoStagione>("/api/stagione", ascolta: false, server: server)
        squadre = Caricatore<[SquadraLega]>("/api/squadre", server: server)
        aggiornamento = AggiornaDatiViewModel(server: server)
        super.init()
        osserva(info)
        osserva(stagione)
        osserva(squadre)
        osserva(aggiornamento)
    }

    func carica() async {
        await info.ricarica()
        await stagione.ricarica()
        await squadre.ricarica()
    }

    /// true quando le rose sono ancora della stagione finita.
    var nuovaStagione: Bool { stagione.dato?.nuova == true }

    /// La propria squadra, se scelta.
    var miaSquadra: String? { squadre.dato?.first { $0.mia == true }?.nome }

    /// La riga di Gestione sul controllo che iOS fa fare all'app quando è chiusa (se cambia la consigliata), in italiano semplice.
    static let titoloControlli = "Controllo con l'app chiusa"

    /// Lo stato di quel controllo; se è spento, dove si riaccende (Impostazioni > Generali > Aggiornamento app in background).
    static func statoControlli(_ stato: UIBackgroundRefreshStatus) -> String {
        switch stato {
        case .available: return "attivo"
        case .denied: return "disattivato (Impostazioni di iOS)"
        default: return "limitato"
        }
    }

    /// Se iOS permette all'app di controllare da sola, anche chiusa (aggiornamento app in background).
    var aggiornamentoInBackground: String { Self.statoControlli(UIApplication.shared.backgroundRefreshStatus) }
}

/// Elenco delle squadre; da qui si indica quale è la propria.
@MainActor
final class SquadreViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<[SquadraLega]>
    @Published var errore: String?

    init(server: any ServerClient) {
        self.server = server
        caricatore = Caricatore<[SquadraLega]>("/api/squadre", server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async { await caricatore.ricarica() }

    /// Il nome della mia squadra.
    var mia: String { caricatore.dato?.first { $0.mia == true }?.nome ?? "" }

    func impostaMia(_ nome: String) async {
        do {
            _ = try await server.corpoJSON("PUT", "/api/mia-squadra", NomeSquadra(nome: nome))
            errore = nil
            Haptics.esito(riuscito: true)
        } catch {
            errore = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
        await caricatore.ricarica()
    }
}

