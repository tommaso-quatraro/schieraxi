import SwiftUI

/// Logica della schermata Oggi: carica la giornata, chiede il permesso per le notifiche e riprogramma i promemoria.
@MainActor
final class OggiViewModel: ViewModelBase {
    let caricatore: Caricatore<Oggi>

    init(server: any ServerClient) {
        // Il comando «Aggiorna» lo gestisce questo ViewModel (deve anche riprogrammare i promemoria), non il Caricatore.
        caricatore = Caricatore<Oggi>(OggiRepository.percorso, ascolta: false, server: server)
        super.init()
        osserva(caricatore)
        alComandoAggiorna { [weak self] in await self?.carica() }
    }

    var oggi: Oggi? { caricatore.dato }
    var errore: String? { caricatore.errore }
    var datiSalvati: Date? { caricatore.datiSalvati }

    /// Avvisi che riguardano giocatori della formazione.
    var daControllare: [Avviso] { (oggi?.avvisi ?? []).filter { $0.inFormazione == true } }
    /// Altri indisponibili della rosa.
    var indisponibili: [Avviso] { (oggi?.avvisi ?? []).filter { $0.inFormazione != true } }

    /// Ricarica la giornata e, se i dati sono freschi, riprogramma i promemoria.
    func carica() async {
        await caricatore.ricarica()
        // Con dati vecchi (server irraggiungibile, o ancora la cache) non si riprogrammano i promemoria: sarebbero su una giornata vecchia.
        guard let oggi = caricatore.dato, caricatore.datiSalvati == nil, !caricatore.dallaCache else { return }
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
