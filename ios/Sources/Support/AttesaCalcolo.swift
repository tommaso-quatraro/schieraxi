import Foundation

/// Quante richieste stanno aspettando un calcolo del server (risposta 202, «sto calcolando»), come il contatore `inAttesa` di
/// `mostraCalcolo` della web: finché ce n'è almeno una l'app mostra «Un attimo, mister: ci sto lavorando.» (`AvvisoCalcolo`,
/// #931). Lo aggiorna `ServerHTTP` quando comincia ad aspettare e quando smette (risposta arrivata, errore, tentativi finiti).
@MainActor
final class AttesaCalcolo: ObservableObject {
    /// Quella di tutta l'app; i test ne usano una loro (`ServerHTTP.attesa`).
    static let condivisa = AttesaCalcolo()

    /// Le richieste che aspettano adesso.
    @Published private(set) var attese = 0
    /// Quante attese sono cominciate da quando esiste (per le prove).
    private(set) var cominciate = 0

    /// C'è almeno una richiesta che aspetta un calcolo.
    var inCorso: Bool { attese > 0 }

    func inizia() {
        attese += 1
        cominciate += 1
    }

    /// Mai sotto zero, anche con una fine di troppo.
    func finisce() {
        attese = max(0, attese - 1)
    }
}
