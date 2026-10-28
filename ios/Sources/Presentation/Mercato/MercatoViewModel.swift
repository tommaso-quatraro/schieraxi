import SwiftUI

enum SezioneMercato: String, CaseIterable, Identifiable {
    case consigliati = "Consigliati"
    case classifica = "Classifica"
    case calendario = "Calendario"
    case osservati = "Osservati"
    case cerca = "Cerca"
    var id: String { rawValue }
}

struct IdGiocatore: Identifiable { let id: Int }

/// Logica della schermata Mercato: consigliati, classifica, calendario, osservati, ricerca.
@MainActor
final class MercatoViewModel: ViewModelBase {
    let server: any ServerClient
    let consigliati: Caricatore<Mercato>
    let classifica: Caricatore<ElencoGiocatori>
    let calendario: Caricatore<Calendario>
    let osservati: Caricatore<ElencoGiocatori>

    @Published var sezione: SezioneMercato = .consigliati
    /// Giocatore di cui si mostra la scheda (sheet).
    @Published var schedaAperta: IdGiocatore?
    // classifica
    @Published var ruolo = "Tutti"
    @Published var soloLiberi = true
    // ricerca
    @Published var testoRicerca = ""
    @Published var risultati: [GiocatoreBreve] = []
    @Published var erroreRicerca: String?
    // osservati
    @Published var messaggioOsservati: String?

    init(server: any ServerClient) {
        self.server = server
        consigliati = Caricatore<Mercato>("/api/mercato", server: server)
        classifica = Caricatore<ElencoGiocatori>("/api/classifica?limite=60&liberi=true", server: server)
        calendario = Caricatore<Calendario>("/api/calendario", server: server)
        osservati = Caricatore<ElencoGiocatori>("/api/osservati", server: server)
        super.init()
        osserva(consigliati)
        osserva(classifica)
        osserva(calendario)
        osserva(osservati)
    }

    func apri(_ id: Int) { schedaAperta = IdGiocatore(id: id) }

    // MARK: classifica

    var percorsoClassifica: String {
        var p = "/api/classifica?limite=60&liberi=\(soloLiberi ? "true" : "false")"
        if ruolo != "Tutti" { p += "&ruolo=\(IndirizzoServer.codifica(ruolo))" }
        return p
    }

    func caricaClassifica() async { await classifica.ricarica(percorsoClassifica) }

    // MARK: osservati

    func caricaOsservati() async {
        await osservati.ricarica()
        // Gli osservati compaiono anche nella ricerca di iOS (Spotlight), ma solo se i dati sono freschi.
        if !Demo.attivo, let d = osservati.dato, osservati.datiSalvati == nil, !osservati.dallaCache {
            Spotlight.indicizza(d.giocatori)
        }
    }

    func togliOsservato(_ id: Int) async {
        do {
            try await server.invia("DELETE", "/api/osservati/\(id)")
            messaggioOsservati = nil
            Haptics.selezione()
        } catch {
            messaggioOsservati = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
        await caricaOsservati()
    }

    // MARK: ricerca

    /// Cerca dopo una breve pausa (se si continua a scrivere, la ricerca vecchia viene annullata dalla vista con `.task(id:)`).
    func cerca() async {
        let testo = testoRicerca
        guard testo.count >= 2 else {
            risultati = []
            erroreRicerca = nil
            return
        }
        try? await Task.sleep(nanoseconds: 300_000_000)
        if Task.isCancelled { return }
        do {
            let trovati: [GiocatoreBreve] = try await server.get("/api/giocatori?limite=25&q=\(IndirizzoServer.codifica(testo))")
            if Task.isCancelled { return }
            risultati = trovati
            erroreRicerca = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }   // si è continuato a scrivere: vale la ricerca nuova
            erroreRicerca = error.localizedDescription
        }
    }
}
