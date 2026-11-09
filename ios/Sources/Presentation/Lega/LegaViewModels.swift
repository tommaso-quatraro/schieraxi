import SwiftUI
import UniformTypeIdentifiers

/// Le pagine che si aprono dalla schermata Lega.
enum PaginaLega: Hashable {
    case importa, squadre, rosa(String), regole, crediti, avvisi, stato, novita
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

    /// La riga di Avvisi sul controllo che iOS fa fare all'app quando è chiusa (se cambia la consigliata), in italiano semplice.
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

/// Impostazioni degli avvisi del server.
@MainActor
final class AvvisiServerViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<StatoAvvisi>
    @Published var impostazioni: ImpostazioniAvvisi?
    @Published var messaggio: String?
    /// Il server ha spento le ore tranquille (inizio = fine): si dice una volta, finché non si salva di nuovo.
    @Published var oreTranquilleSpente = false
    /// Un salvataggio non riuscito, detto in parole semplici (si vede in ogni caso, anche con gli account accesi).
    @Published var erroreSalvataggio: String?
    /// Le impostazioni come le ha il server (l'ultima lettura o l'ultimo salvataggio riuscito): se un salvataggio fallisce
    /// gli interruttori tornano qui, così non mostrano una scelta che il server non ha.
    private var salvate: ImpostazioniAvvisi?
    /// Le modifiche che non sono andate (anche quelle fatte mentre si aspettava): «Riprova» le rimanda. L'errore resta
    /// finché un salvataggio riuscito non le contiene tutte.
    private var daRiprovare: ModificaAvvisi?
    /// I promemoria locali di questo telefono (nei test: una versione che annota le chiamate).
    private let promemoria: PromemoriaTelefono

    init(server: any ServerClient, promemoria: PromemoriaTelefono = .veri) {
        self.server = server
        self.promemoria = promemoria
        caricatore = Caricatore<StatoAvvisi>("/api/avvisi", snake: false, cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async {
        await caricatore.ricarica()
        impostazioni = caricatore.dato?.impostazioni
        salvate = impostazioni
        oreTranquilleSpente = caricatore.dato?.oreTranquilleSpente ?? false
        if let i = impostazioni { ricordaSulTelefono(i) }
    }

    /// Ore tranquille e promemoria accesi servono anche ai promemoria locali: si ricordano sul telefono, e quelli spenti si
    /// tolgono subito. Sempre con le impostazioni che ha il server (lette o appena salvate), mai con un tocco ancora in coda.
    private func ricordaSulTelefono(_ i: ImpostazioniAvvisi) {
        guard !Demo.attivo else { return }
        promemoria.ricorda(i)
        promemoria.togliSpenti(i.promemoriaAccesi)
    }

    /// Il salvataggio in corso: i salvataggi vanno uno alla volta. Due interruttori toccati in fretta partivano insieme con la
    /// stessa versione: il secondo riceveva 412 («cambiato da un altro dispositivo», ma era questo) e la modifica si perdeva.
    private var inCoda: Task<Void, Never>?

    func salva() async {
        let prima = inCoda
        let questo = Task { @MainActor [weak self] in
            await prima?.value
            await self?.salvaOra()
        }
        inCoda = questo
        await questo.value
    }

    /// Manda le impostazioni come sono ADESSO (comprese le modifiche fatte mentre si aspettava il salvataggio precedente).
    private func salvaOra() async {
        guard let i = impostazioni else { return }
        guard i != salvate else {
            // Niente da mandare: dopo un errore gli interruttori sono tornati come li ha il server e le modifiche aspettano
            // «Riprova» (mandare questi valori cancellerebbe l'errore e le modifiche). L'errore resta, a meno che il server
            // non abbia già tutto quello che c'era da riprovare.
            if let attesa = daRiprovare, attesa.contenuta(in: i) { daRiprovare = nil; erroreSalvataggio = nil }
            return
        }
        let prima = salvate
        do {
            let _: StatoAvvisi = try await server.posta("PUT", "/api/avvisi", i, snake: false)
            salvate = i
            if daRiprovare?.contenuta(in: i) ?? true {
                daRiprovare = nil
                erroreSalvataggio = nil
            }   // altrimenti una modifica non andata prima manca ancora: errore e «Riprova» restano
            ricordaSulTelefono(i)
            // Un promemoria si è riacceso, o sono cambiate le ore tranquille: i promemoria tornano in programma subito, con le
            // scelte appena ricordate (quelli che ora cadono nel silenzio spariscono, quelli che ne sono usciti tornano).
            let riacceso = prima.map { !i.promemoriaAccesi.subtracting($0.promemoriaAccesi).isEmpty } ?? false
            let oreCambiate = prima.map { i.oreTranquille != $0.oreTranquille } ?? false
            if riacceso || oreCambiate, !Demo.attivo {
                await promemoria.riprogramma()
            }
            oreTranquilleSpente = false
            messaggio = nil
        } catch {
            let conflitto = (error as? ErroreApi)?.eConflitto == true
            if conflitto {
                await carica()   // cambiato da un altro dispositivo: si rilegge e si mostra il valore nuovo
                daRiprovare = nil
            } else {
                // Tutto ciò che il server non ha (questa modifica, quelle fatte mentre si aspettava e quelle di un errore
                // precedente) aspetta «Riprova»; gli interruttori tornano come li ha il server.
                let adesso = impostazioni ?? i
                let voluta = daRiprovare?.applicata(a: adesso) ?? adesso
                daRiprovare = ModificaAvvisi(da: salvate ?? i, a: voluta)
                impostazioni = salvate
            }
            erroreSalvataggio = "Non ho salvato la modifica. " + error.localizedDescription
        }
    }

    /// «Riprova» dopo un salvataggio non riuscito: rimanda le modifiche che non erano andate, sopra le impostazioni di adesso.
    func riprova() async {
        guard let attesa = daRiprovare else { erroreSalvataggio = nil; return }
        impostazioni = attesa.applicata(a: impostazioni ?? attesa.a)
        await salva()
    }

    /// Dopo un errore si può riprovare (non dopo un conflitto: lì i dati sono già quelli nuovi del server).
    var puoRiprovare: Bool { daRiprovare != nil }

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

    /// I valori come li ha il server (l'ultima lettura o l'ultimo salvataggio): servono a capire cosa ha cambiato l'utente.
    private var originali: [String: String] = [:]

    /// Rilegge i crediti. Un valore scritto e non ancora salvato resta (prima cambiare scheda e tornare lo cancellava);
    /// `forza` (cambiati da un altro dispositivo) riparte da quelli del server.
    func carica(forza: Bool = false) async {
        await caricatore.ricarica()
        for s in caricatore.dato ?? [] {
            let delServer = s.creditiResidui.map { String(Formato.intero($0)) } ?? ""
            if forza || valori[s.nome] == nil || valori[s.nome] == originali[s.nome] { valori[s.nome] = delServer }
            originali[s.nome] = delServer
        }
    }

    /// C'è almeno un valore scritto e non salvato.
    var modificati: Bool { valori.contains { nome, testo in originali[nome].map { $0 != testo } ?? false } }

    func salva() async {
        var crediti: [String: Int] = [:]
        for (nome, testo) in valori { if let n = Int(testo.trimmingCharacters(in: .whitespaces)) { crediti[nome] = n } }
        do {
            _ = try await server.corpoJSON("PUT", "/api/crediti", CreditiSquadre(crediti: crediti))
            for (nome, testo) in valori where originali[nome] != nil { originali[nome] = testo }
            messaggio = Catalogo.Lega.creditiSalvati
            Haptics.esito(riuscito: true)
        } catch {
            let conflitto = (error as? ErroreApi)?.eConflitto == true
            if conflitto { await carica(forza: true) }   // cambiato da un altro dispositivo: si rilegge e si mostrano i valori nuovi
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
