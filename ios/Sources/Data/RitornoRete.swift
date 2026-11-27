import Foundation
import Network

/// Le notizie di iOS sulla rete (`NWPathMonitor`), come l'evento `online` del browser: quando il telefono ritrova la rete e una
/// schermata mostra la copia salvata perché la rete non c'era, l'app manda «Aggiorna» a tutte le schermate, una volta (la regola sta
/// in `AttesaRete`), come `alRitornoDellaRete` di `caricaConCache` in `app.js`. Ogni schermata rilegge a modo suo, come con Cmd+R.
/// Si accende all'apertura dell'app (`SchieraxiApp`, non in demo né nei test); il `Caricatore` dice quando una copia aspetta.
@MainActor
final class RitornoRete {
    static let condiviso = RitornoRete()

    private var attesa: AttesaRete
    private var monitor: NWPathMonitor?

    /// `attesa`: da dove si parte (nei test, per esempio, subito dopo un tentativo automatico).
    init(attesa: AttesaRete = AttesaRete()) {
        self.attesa = attesa
    }

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
        attesa.aspetta(adesso: Date())
    }

    /// «Riprova» toccato a mano: se anche questa lettura resta senza rete, al ritorno della rete si riprova da soli, come la web,
    /// anche se l'ultimo tentativo automatico è di meno di 5 minuti fa (#980).
    func riprovaAMano() {
        attesa.riprovaAMano()
    }

    /// Una lettura è riuscita: la copia non è più a video, al ritorno della rete non c'è niente da riprovare (#980).
    func letturaRiuscita() {
        attesa.letturaRiuscita()
    }

    /// true se al ritorno della rete si riproverà (per le prove).
    var inAttesa: Bool { attesa.inAttesa }

    private func cambia(inLinea: Bool) {
        guard attesa.cambio(inLinea: inLinea, adesso: Date()) else { return }
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
    }
}
