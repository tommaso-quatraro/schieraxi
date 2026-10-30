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
    /// Quanti giocatori al massimo per lato nelle proposte: 1 (solo 1 contro 1), 2, 3 o 4 (serve una squadra scelta).
    @Published var fino = 1
    /// Compatibilità: «anche 2 contro 2» = fino a 2.
    var due: Bool {
        get { fino >= 2 }
        set { fino = newValue ? max(fino, 2) : 1 }
    }
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
        // `ascolta: false`: le proposte si cercano SOLO su richiesta dell'utente (il server conta ogni ricerca): non si rilanciano da sole
        // al comando «Aggiorna», dopo un'importazione delle rose o cambiando scheda.
        proposte = Caricatore<ProposteScambi>("/api/scambi/proposte", ascolta: false, server: server)
        super.init()
        osserva(squadre)
        osserva(proposte)
    }

    /// Le altre squadre della lega (non la mia).
    var altre: [SquadraLega] { (squadre.dato ?? []).filter { $0.mia != true } }

    var indirizzoProposte: String {
        // Il 2 contro 2 si chiede solo con una squadra scelta (senza, il server risponde 400).
        let grandi = con != "Tutte" && fino >= 2
        var p = "/api/scambi/proposte?due=\(grandi ? "true" : "false")"
        if con != "Tutte" { p += "&con=\(IndirizzoServer.codifica(con))" }
        if grandi && fino >= 3 { p += "&fino_a=\(min(fino, 4))" }
        return p
    }

    func caricaSquadre() async { await squadre.ricarica() }
    /// Per quanto tempo si ricordano le proposte degli stessi parametri (senza chiedere di nuovo al server).
    static let validitaProposte: TimeInterval = 15 * 60

    /// Cerca gli scambi. Una ricerca alla volta; con gli stessi parametri di poco fa si mostrano quelli già trovati
    /// (`forza: true` solo dal «tira per aggiornare»).
    func caricaProposte(forza: Bool = false) async {
        if proposte.inCorso { return }
        if !forza, proposte.haDatiRecenti(per: indirizzoProposte, entro: Self.validitaProposte) { return }
        await proposte.ricarica(indirizzoProposte)
    }

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
    /// Crediti scambiati, scritti dall'utente: positivo = li ricevi tu, negativo = li paghi tu.
    @Published var conguaglio = ""

    static let massimoPerLato = 4

    init(server: any ServerClient) {
        self.server = server
        squadre = Caricatore<[SquadraLega]>("/api/squadre", server: server)
        miaRosa = Caricatore<Rosa>("/api/rosa", server: server)
        super.init()
        osserva(squadre)
        osserva(miaRosa)
    }

    var altre: [SquadraLega] { (squadre.dato ?? []).filter { $0.mia != true } }

    var puoAnalizzare: Bool {
        !altra.isEmpty && !doIds.isEmpty && !ricevoIds.isEmpty && !inCorso && troppi == nil && conguaglioValido
    }

    /// Più di 4 giocatori per lato il server non li analizza: lo si dice prima.
    var troppi: String? {
        if doIds.count > Self.massimoPerLato || ricevoIds.count > Self.massimoPerLato {
            return "Al massimo \(Self.massimoPerLato) giocatori per lato."
        }
        return nil
    }

    /// Il conguaglio: vuoto = nessuno; altrimenti un intero (anche negativo).
    var creditiConguaglio: Int? {
        let t = conguaglio.trimmingCharacters(in: .whitespaces)
        return t.isEmpty ? 0 : Int(t.replacingOccurrences(of: "−", with: "-").replacingOccurrences(of: "+", with: ""))
    }

    var conguaglioValido: Bool { creditiConguaglio.map { abs($0) <= 100_000 } ?? false }

    /// L'indirizzo dell'analisi: sempre completa (rose valide, crediti, giudizio), col conguaglio se c'è.
    var indirizzoAnalisi: String {
        let a = doIds.sorted().map(String.init).joined(separator: ",")
        let b = ricevoIds.sorted().map(String.init).joined(separator: ",")
        var p = "/api/scambi/analizza?con=\(IndirizzoServer.codifica(altra))&do=\(a)&ricevo=\(b)&completo=true"
        if let c = creditiConguaglio, c != 0 { p += "&conguaglio=\(c)" }
        return p
    }

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
        do {
            let analisi: PropostaScambio = try await server.get(indirizzoAnalisi)
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
