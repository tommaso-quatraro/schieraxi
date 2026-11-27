import Foundation
import Network

/// Le notizie di iOS sulla rete (`NWPathMonitor`), come l'evento `online` del browser: quando il telefono ritrova la rete e una
/// schermata mostra la copia salvata perché la rete non c'era, l'app manda «Aggiorna» a tutte le schermate, una volta (la regola sta
/// in `AttesaRete`), come `alRitornoDellaRete` di `caricaConCache` in `app.js`. Ogni schermata rilegge a modo suo, come con Cmd+R.
/// Si accende all'apertura dell'app (`SchieraxiApp`, non in demo né nei test); il `Caricatore` dice quando una copia aspetta.
@MainActor
final class RitornoRete {
    static let condiviso = RitornoRete()

    private var attesa = AttesaRete()
    private var monitor: NWPathMonitor?

    /// Comincia ad ascoltare le notizie sulla rete (una volta sola). Arrivano sul thread principale, nell'ordine.
    func avvia() {
        guard monitor == nil else { return }
        let nuovo = NWPathMonitor()
        nuovo.pathUpdateHandler = { percorso in
            let inLinea = percorso.status == .satisfied
            MainActor.assumeIsolated { RitornoRete.condiviso.cambia(inLinea: inLinea) }
        }
        nuovo.start(queue: .main)
        monitor = nuovo
    }

    /// Una schermata mostra la copia salvata perché la rete non c'era: al ritorno della rete si riprova.
    func aspetta() {
        attesa.aspetta()
    }

    private func cambia(inLinea: Bool) {
        guard attesa.cambio(inLinea: inLinea) else { return }
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
    }
}
