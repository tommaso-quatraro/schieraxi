import SwiftUI

/// Le pagine che si aprono dentro un `NavigationStack` di giocatori (la ricerca).
enum PassoScheda: Hashable {
    /// La scheda di un giocatore.
    case scheda(Int)
}

/// Logica della scheda di un giocatore: dati e prossime partite.
@MainActor
final class SchedaGiocatoreViewModel: ViewModelBase {
    let id: Int
    let caricatore: Caricatore<SchedaGiocatore>
    let calendario: Caricatore<Calendario>

    init(id: Int, server: any ServerClient) {
        self.id = id
        caricatore = Caricatore<SchedaGiocatore>("/api/giocatore/\(id)", server: server)
        calendario = Caricatore<Calendario>("/api/calendario", server: server)
        super.init()
        osserva(caricatore)
        osserva(calendario)
    }

    /// Le due letture partono insieme (prima una dopo l'altra: la scheda arrivava tardi).
    func carica() async {
        async let scheda: Void = caricatore.ricarica()
        async let partite: Void = calendario.ricarica()
        _ = await (scheda, partite)
    }

    /// Le prossime partite della squadra del giocatore (dal calendario).
    var prossime: [PartitaCalendario] {
        guard let s = caricatore.dato,
              let slug = s.previsione?.squadra ?? s.calciatore.squadraSlug,
              let sq = calendario.dato?.squadre.first(where: { $0.squadra == slug }) else { return [] }
        return sq.partite
    }
}
