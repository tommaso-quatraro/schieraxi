import SwiftUI

/// Logica della schermata Oggi: carica la giornata, chiede il permesso per le notifiche e riprogramma i promemoria.
@MainActor
final class OggiViewModel: ViewModelBase {
    let caricatore: Caricatore<Oggi>
    /// false nei test: niente richiesta del permesso per le notifiche, promemoria, widget.
    private let conPromemoria: Bool
    private let server: any ServerClient
    /// Partite rinviate: la scelta «per questa giornata» è in viaggio (il menu si blocca) e l'eventuale errore da mostrare.
    @Published private(set) var rinvioInCorso = false
    @Published var erroreRinvio: String?

    init(server: any ServerClient, conPromemoria: Bool = true) {
        self.conPromemoria = conPromemoria
        self.server = server
        // Il comando «Aggiorna» lo gestisce questo ViewModel (deve anche riprogrammare i promemoria), non il Caricatore.
        caricatore = Caricatore<Oggi>(OggiRepository.percorso, ascolta: false, server: server)
        super.init()
        osserva(caricatore)
        alComandoAggiorna { [weak self] in
            await self?.carica()
        }
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

    /// Ogni quanto si rilegge Oggi durante la giornata (i voti escono a fine partita: non serve di più).
    static let ripassoGiornata: TimeInterval = 300

    /// Fase `in_corso`: rilegge Oggi ogni 5 minuti (punti fatti, cambi), finché la schermata è visibile e la giornata è in corso.
    /// Solo la lettura: niente promemoria né permessi. La vista annulla il lavoro quando sparisce.
    func seguiGiornata() async {
        while !Task.isCancelled {
            do { try await Task.sleep(nanoseconds: UInt64(Self.ripassoGiornata * 1_000_000_000)) } catch { return }
            guard !Task.isCancelled else { return }
            await caricatore.ricarica()
            guard oggi?.faseGiornata == .inCorso else { return }
        }
    }

    /// Ricarica la giornata e, se i dati sono freschi, riprogramma i promemoria.
    /// Partite rinviate, decisione per una sola giornata (`PUT /api/regole/rinvio`): la stessa scelta della regola della lega
    /// toglie l'eccezione. Poi si ricarica tutto (consigli, formazione, Oggi) come dopo un salvataggio delle regole.
    func cambiaRinvio(_ scelta: SceltaRinvio, modo: String) async {
        guard modo != scelta.modo, !rinvioInCorso else { return }
        rinvioInCorso = true
        defer { rinvioInCorso = false }
        do {
            let corpo = CorpoRinvio(giornata: scelta.giornata, modo: modo == scelta.predefinito ? nil : modo, stagione: scelta.stagione)
            _ = try await server.corpoJSON("PUT", "/api/regole/rinvio", corpo)
            erroreRinvio = nil
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            erroreRinvio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }

    func carica() async {
        await caricatore.ricarica()
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
