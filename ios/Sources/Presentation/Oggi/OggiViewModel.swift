import SwiftUI

/// Le partite di un giorno (titolo come «sabato 31 ottobre» e le partite in ordine di orario).
struct PartiteDelGiorno: Identifiable {
    let titolo: String
    let partite: [Partita]
    var id: String { titolo }
}

/// Logica della schermata Oggi: carica la giornata, chiede il permesso per le notifiche e riprogramma i promemoria.
@MainActor
final class OggiViewModel: ViewModelBase {
    let caricatore: Caricatore<Oggi>
    /// Versione dell'app del server: serve al banner «Novità nell'app».
    let info: Caricatore<InfoServer>
    /// false nei test: niente richiesta del permesso per le notifiche, promemoria, widget.
    private let conPromemoria: Bool

    init(server: any ServerClient, conPromemoria: Bool = true) {
        self.conPromemoria = conPromemoria
        // Il comando «Aggiorna» lo gestisce questo ViewModel (deve anche riprogrammare i promemoria), non il Caricatore.
        caricatore = Caricatore<Oggi>(OggiRepository.percorso, ascolta: false, server: server)
        info = Caricatore<InfoServer>("/api/stato", ascolta: false, server: server)
        super.init()
        osserva(caricatore)
        osserva(info)
        alComandoAggiorna { [weak self] in await self?.carica() }
    }

    var oggi: Oggi? { caricatore.dato }
    var errore: String? { caricatore.errore }
    var datiSalvati: Date? { caricatore.datiSalvati }

    /// Avvisi che riguardano giocatori della formazione.
    var daControllare: [Avviso] { (oggi?.avvisi ?? []).filter { $0.inFormazione == true } }
    /// Altri indisponibili della rosa (infortunati e squalificati).
    var indisponibili: [Avviso] { (oggi?.avvisi ?? []).filter { $0.inFormazione != true && ["infortunato", "squalificato"].contains($0.tipo ?? "") } }
    /// Altri diffidati della rosa.
    var diffidati: [Avviso] { (oggi?.avvisi ?? []).filter { $0.inFormazione != true && $0.tipo == "diffidato" } }

    /// Le partite del turno divise per giorno, in ordine di data.
    var partitePerGiorno: [PartiteDelGiorno] { Self.raggruppa(oggi?.partite ?? []) }

    static func raggruppa(_ partite: [Partita]) -> [PartiteDelGiorno] {
        var perGiorno: [String: [Partita]] = [:]
        var ordine: [String] = []
        let ordinate = partite.sorted { ($0.data ?? "") < ($1.data ?? "") }
        for p in ordinate {
            let titolo = Quando.data(p.data).map { Quando.giorno($0).primaMaiuscola } ?? "Data da definire"
            if perGiorno[titolo] == nil { ordine.append(titolo) }
            perGiorno[titolo, default: []].append(p)
        }
        return ordine.map { PartiteDelGiorno(titolo: $0, partite: perGiorno[$0] ?? []) }
    }

    /// La versione del server da far vedere nel banner, se l'utente non ha ancora guardato le novità (`novitaVista`).
    func novitaDaVedere(ultimaVista: String) -> String? {
        guard let v = info.dato?.versione, !v.isEmpty, v != "?", v != ultimaVista else { return nil }
        return v
    }

    /// Ricarica la giornata e, se i dati sono freschi, riprogramma i promemoria.
    func carica() async {
        await caricatore.ricarica()
        await info.ricarica()
        // Con dati vecchi (server irraggiungibile, o ancora la cache) non si riprogrammano i promemoria: sarebbero su una giornata vecchia.
        guard conPromemoria, !Demo.attivo, let oggi = caricatore.dato, caricatore.datiSalvati == nil, !caricatore.dallaCache else { return }
        let memoria = UserDefaults.standard
        if !memoria.bool(forKey: "permessoChiesto") {
            memoria.set(true, forKey: "permessoChiesto")
            _ = await Notifiche.chiediPermesso()
            await Aggiornamento.riprogrammaScadenza()
        }
        // Promemoria, widget e memoria dell'ultima formazione (per accorgersi dei cambiamenti in background).
        await Aggiornamento.elabora(oggi, avvisaSeCambia: false)
    }
}
