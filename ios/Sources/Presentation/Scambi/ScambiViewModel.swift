import SwiftUI

/// Le pagine che si aprono dalla schermata Scambi.
enum PaginaScambi: Hashable {
    case analizza
}

/// Logica della schermata Scambi: proposte del modello, filtro per squadra e per scambi 2 contro 2.
@MainActor
final class ScambiViewModel: ViewModelBase {
    let server: any ServerClient
    let squadre: Caricatore<[SquadraLega]>
    let proposte: Caricatore<ProposteScambi>

    /// Pagine aperte nella pila di navigazione.
    @Published var percorso: [PaginaScambi] = []
    @Published var con = "Tutte"
    @Published var due = false
    @Published var selezionata: PropostaScambio?
    /// «Ho ricevuto un'offerta»: il messaggio incollato e cosa ne ha capito il server.
    @Published var testoOfferta = ""
    @Published var esitoOfferta: OffertaRiconosciuta?
    @Published var erroreOfferta: String?
    @Published var offertaInCorso = false
    /// Gli scambi analizzati a mano, ricordati su questo telefono.
    @Published var archivio: [VoceArchivioScambi] = []
    @Published var messaggio: String?
    /// Il giudizio da mostrare nel dettaglio dello scambio aperto (solo per le offerte ricevute).
    @Published var giudizioSelezionata: String?

    init(server: any ServerClient) {
        self.server = server
        squadre = Caricatore<[SquadraLega]>("/api/squadre", server: server)
        proposte = Caricatore<ProposteScambi>("/api/scambi/proposte", server: server)
        super.init()
        osserva(squadre)
        osserva(proposte)
    }

    /// Le altre squadre della lega (non la mia).
    var altre: [SquadraLega] { (squadre.dato ?? []).filter { $0.mia != true } }

    var indirizzoProposte: String {
        // Il 2 contro 2 si chiede solo con una squadra scelta (senza, il server risponde 400).
        var p = "/api/scambi/proposte?due=\(due && con != "Tutte" ? "true" : "false")"
        if con != "Tutte" { p += "&con=\(IndirizzoServer.codifica(con))" }
        return p
    }

    func caricaSquadre() async { await squadre.ricarica() }
    func caricaProposte() async { await proposte.ricarica(indirizzoProposte) }

    /// Le squadre che accettano più volentieri (se ce ne sono almeno due con scambi proposti).
    var propense: [ScambiLogica.SquadraPropensa] { ScambiLogica.squadrePropense(proposte.dato?.proposte ?? []) }

    func caricaArchivio() { archivio = ArchivioScambi.leggi() }

    func svuotaArchivio() {
        ArchivioScambi.svuota()
        archivio = []
    }

    /// Copia negli appunti la bozza del messaggio per l'altro allenatore.
    func copiaBozza(_ p: PropostaScambio) {
        UIPasteboard.general.string = ScambiLogica.bozza(p)
        messaggio = "Bozza copiata: incollala nel gruppo o in privato."
        Haptics.esito(riuscito: true)
    }

    /// Manda il messaggio incollato al server: trova i giocatori e, se può, analizza lo scambio.
    func valutaOfferta() async {
        let testo = testoOfferta.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !testo.isEmpty else {
            erroreOfferta = "Incolla prima il messaggio."
            return
        }
        offertaInCorso = true
        defer { offertaInCorso = false }
        do {
            esitoOfferta = try await server.posta("POST", "/api/scambi/da-testo", RichiestaOfferta(testo: testo, con: nil))
            erroreOfferta = nil
            Haptics.esito(riuscito: true)
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            esitoOfferta = nil
            erroreOfferta = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

/// Logica dell'analisi di uno scambio scelto a mano: due rose, i giocatori scelti, l'esito.
@MainActor
final class AnalizzaScambioViewModel: ViewModelBase {
    private let server: any ServerClient
    let squadre: Caricatore<[SquadraLega]>
    let miaRosa: Caricatore<Rosa>

    @Published var altra = ""
    @Published var loro: Rosa?
    @Published var doIds: Set<Int> = []
    @Published var ricevoIds: Set<Int> = []
    @Published var esito: PropostaScambio?
    @Published var errore: String?
    @Published var inCorso = false

    init(server: any ServerClient) {
        self.server = server
        squadre = Caricatore<[SquadraLega]>("/api/squadre", server: server)
        miaRosa = Caricatore<Rosa>("/api/rosa", server: server)
        super.init()
        osserva(squadre)
        osserva(miaRosa)
    }

    var altre: [SquadraLega] { (squadre.dato ?? []).filter { $0.mia != true } }

    var puoAnalizzare: Bool { !altra.isEmpty && !doIds.isEmpty && !ricevoIds.isEmpty && !inCorso }

    func carica() async {
        await squadre.ricarica()
        await miaRosa.ricarica()
        // Solo per le fotografie della demo: parte già con uno scambio scelto.
        if Demo.schermata == "scambi-analizza", altra.isEmpty {
            if let id = miaRosa.dato?.giocatori.first(where: { $0.ruolo == "A" })?.id { doIds = [id] }
            altra = altre.first?.nome ?? ""
        }
    }

    /// Quando si sceglie un'altra squadra: si azzerano le scelte e si carica la sua rosa.
    func caricaRosaAltra() async {
        ricevoIds = []
        esito = nil
        loro = nil   // la rosa della squadra precedente non deve restare a video
        guard !altra.isEmpty else { return }
        do {
            let rosa: Rosa = try await server.get("/api/rosa?squadra=\(IndirizzoServer.codifica(altra))")
            if Task.isCancelled { return }
            loro = rosa
            errore = nil
            if Demo.schermata == "scambi-analizza", !doIds.isEmpty, let id = rosa.giocatori.first(where: { $0.ruolo == "A" })?.id {
                ricevoIds = [id]
                await analizza()
            }
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            errore = error.localizedDescription
        }
    }

    func analizza() async {
        inCorso = true
        defer { inCorso = false }
        let a = doIds.sorted().map(String.init).joined(separator: ",")
        let b = ricevoIds.sorted().map(String.init).joined(separator: ",")
        do {
            let analisi: PropostaScambio = try await server.get("/api/scambi/analizza?con=\(IndirizzoServer.codifica(altra))&do=\(a)&ricevo=\(b)")
            esito = analisi
            ArchivioScambi.registra(analisi)   // come la web app: gli scambi analizzati restano nell'archivio
            errore = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            esito = nil
            errore = error.localizedDescription
        }
    }
}
