import SwiftUI

/// Le pagine che si aprono dentro la scheda di un giocatore.
enum PassoScheda: Hashable {
    /// La scheda di un giocatore.
    case scheda(Int)
    case confronto(a: Int, b: Int)
    /// Scegli con quale giocatore della tua rosa confrontare questo (l'id).
    case sceltaDallaRosa(Int)
    /// Scegli un qualsiasi altro giocatore (ricerca) con cui confrontare questo (l'id).
    case sceltaAltro(Int)
}

/// In che formazione si sta guardando (stile, modulo, squadra): il confronto spiega la scelta dentro quella formazione.
struct ContestoConfronto: Equatable {
    let livello: Int
    let modulo: String
    let squadra: String?
}

/// Logica della scheda di un giocatore: dati, prossime partite, osservato sì/no, rosa della formazione.
@MainActor
final class SchedaGiocatoreViewModel: ViewModelBase {
    let id: Int
    let caricatore: Caricatore<SchedaGiocatore>
    let calendario: Caricatore<Calendario>
    let osservati: Caricatore<ElencoGiocatori>
    let formazione: Caricatore<Formazione>
    private let server: any ServerClient
    @Published var messaggio: String?
    /// nil finché non si sa; poi vero o falso (anche dopo un tocco su «Osserva»).
    @Published var osservato: Bool?

    init(id: Int, server: any ServerClient) {
        self.id = id
        self.server = server
        caricatore = Caricatore<SchedaGiocatore>("/api/giocatore/\(id)", server: server)
        calendario = Caricatore<Calendario>("/api/calendario", server: server)
        // L'elenco degli osservati e la formazione servono solo a sapere «osservato sì/no» e «è nella mia rosa»: nessuna copia vecchia.
        osservati = Caricatore<ElencoGiocatori>("/api/osservati", cache: false, ascolta: false, server: server)
        formazione = Caricatore<Formazione>("/api/formazione", ascolta: false, server: server)
        super.init()
        osserva(caricatore)
        osserva(calendario)
        osserva(formazione)
    }

    func carica() async {
        await caricatore.ricarica()
        await calendario.ricarica()
        await osservati.ricarica()
        osservato = osservati.dato?.giocatori.contains { $0.id == id }
        await formazione.ricarica()
    }

    /// Le prossime partite della squadra del giocatore (dal calendario).
    var prossime: [PartitaCalendario] {
        guard let s = caricatore.dato,
              let slug = s.previsione?.squadra ?? s.calciatore.squadraSlug,
              let sq = calendario.dato?.squadre.first(where: { $0.squadra == slug }) else { return [] }
        return sq.partite
    }

    /// Il giocatore è nella rosa che sta guardando la Formazione: si può confrontare con gli altri della stessa rosa.
    var inFormazione: Bool { formazione.dato?.schede?[String(id)] != nil }

    /// Gli altri giocatori della rosa, per scegliere con chi confrontarlo (stesso ruolo per primi).
    var altriDellaRosa: [Giocatore] {
        guard let schede = formazione.dato?.schede, let base = schede[String(id)] else { return [] }
        return schede.values.filter { $0.id != id }.sorted {
            let a = $0.ruolo == base.ruolo ? 0 : 1
            let b = $1.ruolo == base.ruolo ? 0 : 1
            if a != b { return a < b }
            return ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0)
        }
    }

    func alternaOsservato() async {
        let eraOsservato = osservato == true
        do {
            try await server.invia(eraOsservato ? "DELETE" : "PUT", "/api/osservati/\(id)")
            osservato = !eraOsservato
            messaggio = eraOsservato ? "Non lo osservi più." : "Lo osservi: lo trovi in Mercato > Osservati."
            Haptics.esito(riuscito: true)
        } catch {
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
