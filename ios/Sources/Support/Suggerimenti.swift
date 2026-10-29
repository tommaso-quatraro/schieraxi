import SwiftUI
import TipKit

/// Suggerimenti di TipKit: piccoli riquadri che spiegano un gesto una volta sola e poi spariscono per sempre.
/// Non funzionano in modalità demo (le fotografie non devono averne). Nessun servizio esterno: lo stato dei suggerimenti
/// sta sul telefono.
enum Suggerimenti {
    static let scheda = SuggerimentoScheda()
    static let campo = SuggerimentoCampo()

    private static var configurato = false

    /// Da chiamare una volta all'avvio.
    static func configura() {
        guard !Demo.attivo, !configurato else { return }
        configurato = (try? Tips.configure([.displayFrequency(.daily)])) != nil
    }

    /// Si è aperta una scheda: il suggerimento «tocca un giocatore» ha fatto il suo lavoro.
    static func schedaAperta() {
        guard configurato else { return }
        scheda.invalidate(reason: .actionPerformed)
    }
}

/// «Tocca un giocatore»: compare in Oggi finché non si apre una scheda.
struct SuggerimentoScheda: Tip {
    var title: Text { Text("Tocca un giocatore") }
    var message: Text? { Text("Si apre la sua scheda: previsione, forma, statistiche e confronto con gli altri.") }
    var image: Image? { Image(systemName: "hand.tap") }
}

/// «Tieni premuto» sul campo: in Formazione.
struct SuggerimentoCampo: Tip {
    var title: Text { Text("Il campo è interattivo") }
    var message: Text? { Text("Tocca un giocatore sul campo per aprire la sua scheda. Con «Modifica a mano» scegli tu chi schierare.") }
    var image: Image? { Image(systemName: "sportscourt") }
}
