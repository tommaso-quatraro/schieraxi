import SwiftUI
import UniformTypeIdentifiers

/// Le pagine che si aprono dalla schermata Lega.
enum PaginaLega: Hashable {
    case importa, squadre, rosa(String), asta, regole, crediti, avvisi, stato, novita
}

/// Logica della schermata Lega: stato del server, permesso per le notifiche, aggiornamento in background.
@MainActor
final class LegaViewModel: ViewModelBase {
    let server: any ServerClient
    let info: Caricatore<InfoServer>
    @Published var permesso = "…"
    /// Pagine aperte nella pila di navigazione (nell'AppModel: cambiando sezione si resta dove si era).
    @Published var percorso: [PaginaLega] = []

    init(server: any ServerClient) {
        self.server = server
        info = Caricatore<InfoServer>("/api/stato", server: server)
        super.init()
        osserva(info)
    }

    func carica() async {
        await info.ricarica()
        await aggiornaPermesso()
    }

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

/// Editor delle regole della lega (JSON generico, rimandato al server con le stesse chiavi).
@MainActor
final class RegoleEditorViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<JSONValue>
    @Published var valore: JSONValue = .nullo
    @Published var caricato = false
    @Published var esito: String?
    @Published var inCorso = false

    init(server: any ServerClient) {
        self.server = server
        // Dati che si modificano: niente cache (non si deve ripartire da una copia vecchia).
        caricatore = Caricatore<JSONValue>("/api/regole", snake: false, cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async {
        await caricatore.ricarica()
        if let d = caricatore.dato { valore = d; caricato = true }
    }

    func salva() async {
        inCorso = true
        defer { inCorso = false }
        do {
            let nuove: JSONValue = try await server.posta("PUT", "/api/regole", valore, snake: false)
            valore = nuove
            esito = "Regole salvate."
            Haptics.esito(riuscito: true)
        } catch {
            esito = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

/// Impostazioni degli avvisi del server.
@MainActor
final class AvvisiServerViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<StatoAvvisi>
    @Published var impostazioni: ImpostazioniAvvisi?
    @Published var messaggio: String?

    init(server: any ServerClient) {
        self.server = server
        caricatore = Caricatore<StatoAvvisi>("/api/avvisi", snake: false, cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async {
        await caricatore.ricarica()
        impostazioni = caricatore.dato?.impostazioni
    }

    func salva() async {
        guard let i = impostazioni else { return }
        do {
            let _: StatoAvvisi = try await server.posta("PUT", "/api/avvisi", i, snake: false)
            messaggio = nil
        } catch {
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
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

/// Importazione delle rose da un Excel di Leghe.
@MainActor
final class ImportaExcelViewModel: ViewModelBase {
    private let server: any ServerClient
    /// Dimensione massima accettata: un Excel delle rose è di poche decine di KB.
    private static let massimoByte = 5 * 1024 * 1024

    @Published var inCorso = false
    @Published var esito: EsitoImportazione?
    @Published var errore: String?

    init(server: any ServerClient) {
        self.server = server
        super.init()
    }

    /// Solo fogli di calcolo (.xlsx e simili).
    var tipiAmmessi: [UTType] {
        var tipi: [UTType] = [.spreadsheet]
        if let xlsx = UTType(filenameExtension: "xlsx") { tipi.append(xlsx) }
        return tipi
    }

    func importa(_ risultato: Result<[URL], Error>) async {
        guard case .success(let urls) = risultato, let url = urls.first else {
            if case .failure(let e) = risultato { errore = e.localizedDescription }
            return
        }
        inCorso = true
        defer { inCorso = false }
        let accesso = url.startAccessingSecurityScopedResource()
        defer { if accesso { url.stopAccessingSecurityScopedResource() } }
        guard ["xlsx", "xls", "xlsm"].contains(url.pathExtension.lowercased()) else {
            esito = nil
            errore = "Il file deve essere un Excel (.xlsx)."
            return
        }
        let grandezza = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        guard grandezza <= Self.massimoByte else {
            esito = nil
            errore = "Il file è troppo grande (massimo 5 MB): non sembra un Excel delle rose."
            return
        }
        do {
            let dati = try Data(contentsOf: url)
            esito = try await server.caricaFile("/api/rose/file", nome: url.lastPathComponent, dati: dati)
            errore = nil
            Haptics.esito(riuscito: true)
        } catch {
            esito = nil
            errore = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
