import SwiftUI

/// Logica del confronto tra due giocatori («Chi schierare?»): chiede al server la spiegazione con le cause.
@MainActor
final class ConfrontoViewModel: ViewModelBase {
    let a: Int
    let b: Int
    let caricatore: Caricatore<Confronto>

    /// L'indirizzo del confronto: con il contesto della formazione (stile, modulo, squadra) il server spiega la scelta dentro quella formazione.
    static func percorso(a: Int, b: Int, contesto: ContestoConfronto?) -> String {
        var p = "/api/confronto?a=\(a)&b=\(b)"
        if let c = contesto {
            p += "&livello=\(c.livello)&modulo=\(IndirizzoServer.codifica(c.modulo))"
            if let s = c.squadra { p += "&squadra=\(IndirizzoServer.codifica(s))" }
        }
        return p
    }

    init(a: Int, b: Int, contesto: ContestoConfronto?, server: any ServerClient) {
        self.a = a
        self.b = b
        caricatore = Caricatore<Confronto>(Self.percorso(a: a, b: b, contesto: contesto), server: server)
        super.init()
        osserva(caricatore)
    }

    var confronto: Confronto? { caricatore.dato }
    var errore: String? { caricatore.errore }

    func carica() async { await caricatore.ricarica() }
}

/// Logica della scelta del giocatore della rosa con cui confrontare quello aperto.
@MainActor
final class SceltaDallaRosaViewModel: ViewModelBase {
    let id: Int
    let formazione: Caricatore<Formazione>

    init(id: Int, server: any ServerClient) {
        self.id = id
        formazione = Caricatore<Formazione>("/api/formazione", ascolta: false, server: server)
        super.init()
        osserva(formazione)
    }

    func carica() async { await formazione.ricarica() }

    var base: Giocatore? { formazione.dato?.schede?[String(id)] }

    /// Gli altri della rosa: prima quelli dello stesso ruolo, per punti attesi.
    var candidati: [Giocatore] {
        guard let schede = formazione.dato?.schede else { return [] }
        let ruolo = base?.ruolo
        return schede.values.filter { $0.id != id }.sorted {
            let a = $0.ruolo == ruolo ? 0 : 1
            let b = $1.ruolo == ruolo ? 0 : 1
            if a != b { return a < b }
            return ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0)
        }
    }

    /// Titolare, panchina o fuori nella formazione consigliata.
    func posto(_ idGiocatore: Int) -> String {
        guard let f = formazione.dato else { return "" }
        if f.titolari.contains(where: { $0.id == idGiocatore }) { return "Titolare" }
        if let k = f.panchina.firstIndex(where: { $0.id == idGiocatore }) { return "Panchina \(k + 1)" }
        return "Fuori"
    }
}

/// Logica della ricerca di un giocatore per nome (ricerca globale e scelta dell'altro giocatore del confronto).
@MainActor
final class RicercaViewModel: ViewModelBase {
    private let server: any ServerClient
    @Published var testo = ""
    @Published var risultati: [GiocatoreBreve] = []
    @Published var errore: String?
    @Published var cercando = false

    init(server: any ServerClient) {
        self.server = server
        super.init()
        if Demo.attivo, let t = Demo.argomento("DEMO_CERCA") { testo = t }   // solo per le fotografie del simulatore
    }

    /// Cerca dopo una breve pausa: se si continua a scrivere, la vista annulla questa ricerca (`.task(id:)`) e ne parte una nuova.
    func cerca() async {
        let scritto = testo.trimmingCharacters(in: .whitespaces)
        guard scritto.count >= 2 else {
            risultati = []
            errore = nil
            cercando = false
            return
        }
        try? await Task.sleep(nanoseconds: 300_000_000)
        if Task.isCancelled { return }
        cercando = true
        defer { cercando = false }
        do {
            let trovati: [GiocatoreBreve] = try await server.get("/api/giocatori?limite=25&q=\(IndirizzoServer.codifica(scritto))")
            if Task.isCancelled { return }
            risultati = trovati
            errore = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            errore = error.localizedDescription
        }
    }
}
