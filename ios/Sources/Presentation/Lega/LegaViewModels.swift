import SwiftUI
import UniformTypeIdentifiers

/// Le pagine che si aprono dalla schermata Lega.
enum PaginaLega: Hashable {
    case importa, squadre, rosa(String), asta, regole, crediti, avvisi, stato, novita
    case movimenti, stagione, diario
    /// Dalla dieta delle funzioni: le pagine che prima erano in Mercato e in Scambi stanno in Squadra e in Altro.
    case cambi, seguiti, elenco, calendario, scambi

    /// In quale scheda sta la pagina: Squadra (la mia squadra, cambi, seguiti, elenco, calendario, rose) oppure Altro (tutto il resto).
    var sezione: Sezione {
        switch self {
        case .importa, .squadre, .rosa, .cambi, .seguiti, .elenco, .calendario: return .squadra
        default: return .altro
        }
    }
}

/// Logica della schermata Lega: stato del server, permesso per le notifiche, aggiornamento in background.
@MainActor
final class LegaViewModel: ViewModelBase {
    let server: any ServerClient
    let info: Caricatore<InfoServer>
    /// Le rose sono della stagione in corso o di una passata? (se passata, compare il passaggio di stagione)
    let stagione: Caricatore<StatoStagione>
    /// L'aggiornamento dei dati del server (tasto «Aggiorna i dati»), con il suo stato.
    let aggiornamento: AggiornaDatiViewModel
    @Published var permesso = "…"
    /// Pagine aperte nella pila di navigazione (nell'AppModel: cambiando sezione si resta dove si era).
    /// Le pagine aperte nella scheda Altro.
    @Published var percorso: [PaginaLega] = []
    /// Le pagine aperte nella scheda Squadra.
    @Published var percorsoSquadra: [PaginaLega] = []

    /// Apre una pagina (e quelle che ci stanno sopra) nella scheda a cui appartiene e dice quale scheda mostrare.
    @discardableResult
    func apri(_ pagine: [PaginaLega]) -> Sezione {
        let dove = pagine.first?.sezione ?? .altro
        if dove == .squadra { percorsoSquadra = pagine } else { percorso = pagine }
        return dove
    }

    init(server: any ServerClient) {
        self.server = server
        info = Caricatore<InfoServer>("/api/stato", server: server)
        stagione = Caricatore<StatoStagione>("/api/stagione", ascolta: false, server: server)
        aggiornamento = AggiornaDatiViewModel(server: server)
        super.init()
        osserva(info)
        osserva(stagione)
        osserva(aggiornamento)
    }

    func carica() async {
        await info.ricarica()
        await stagione.ricarica()
        await aggiornaPermesso()
    }

    /// true quando le rose sono ancora della stagione finita.
    var nuovaStagione: Bool { stagione.dato?.nuova == true }

    func attivaPromemoria() async {
        _ = await Notifiche.chiediPermesso()
        await Aggiornamento.riprogrammaScadenza()
        await aggiornaPermesso()
    }

    func aggiornaPermesso() async {
        if Demo.attivo { permesso = "attive"; return }
        switch await Notifiche.stato() {
        case .authorized, .provisional, .ephemeral: permesso = "attive"
        case .denied: permesso = "negate (Impostazioni di iOS)"
        default: permesso = "da attivare"
        }
    }

    /// Se iOS permette all'app di aggiornarsi in background (Impostazioni > Generali > Aggiornamento app in background).
    var aggiornamentoInBackground: String {
        switch UIApplication.shared.backgroundRefreshStatus {
        case .available: return "attivo"
        case .denied: return "disattivato"
        default: return "limitato"
        }
    }
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

/// Impostazioni degli avvisi del server.
@MainActor
final class AvvisiServerViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<StatoAvvisi>
    @Published var impostazioni: ImpostazioniAvvisi?
    @Published var messaggio: String?
    /// Il server ha spento le ore tranquille (inizio = fine): si dice una volta, finché non si salva di nuovo.
    @Published var oreTranquilleSpente = false

    init(server: any ServerClient) {
        self.server = server
        caricatore = Caricatore<StatoAvvisi>("/api/avvisi", snake: false, cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async {
        await caricatore.ricarica()
        impostazioni = caricatore.dato?.impostazioni
        oreTranquilleSpente = caricatore.dato?.oreTranquilleSpente ?? false
        ricordaOreTranquille()
    }

    /// Le ore tranquille servono anche ai promemoria locali: si ricordano sul telefono.
    private func ricordaOreTranquille() {
        if let i = impostazioni, !Demo.attivo { ArchivioOreTranquille.salva(i.oreTranquille) }
    }

    func salva() async {
        guard let i = impostazioni else { return }
        do {
            let _: StatoAvvisi = try await server.posta("PUT", "/api/avvisi", i, snake: false)
            ricordaOreTranquille()
            oreTranquilleSpente = false
            messaggio = nil
        } catch {
            let conflitto = (error as? ErroreApi)?.eConflitto == true
            if conflitto { await carica() }   // cambiato da un altro dispositivo: si rilegge e si mostra il valore nuovo
            messaggio = error.localizedDescription
        }
    }

    func provaAvviso() async {
        do {
            try await server.invia("POST", "/api/avvisi/prova")
            messaggio = "Avviso di prova inviato."
        } catch {
            messaggio = error.localizedDescription
        }
    }
}

/// Crediti residui di ogni squadra.
@MainActor
final class CreditiViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<[SquadraCrediti]>
    @Published var valori: [String: String] = [:]
    @Published var messaggio: String?

    init(server: any ServerClient) {
        self.server = server
        caricatore = Caricatore<[SquadraCrediti]>("/api/squadre", cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async {
        await caricatore.ricarica()
        for s in caricatore.dato ?? [] { valori[s.nome] = s.creditiResidui.map { String(Formato.intero($0)) } ?? "" }
    }

    func salva() async {
        var crediti: [String: Int] = [:]
        for (nome, testo) in valori { if let n = Int(testo.trimmingCharacters(in: .whitespaces)) { crediti[nome] = n } }
        do {
            _ = try await server.corpoJSON("PUT", "/api/crediti", CreditiSquadre(crediti: crediti))
            messaggio = "Crediti salvati."
            Haptics.esito(riuscito: true)
        } catch {
            let conflitto = (error as? ErroreApi)?.eConflitto == true
            if conflitto { await carica() }   // cambiato da un altro dispositivo: si rilegge e si mostrano i valori nuovi
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
