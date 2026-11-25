import Foundation
import Testing
@testable import Schieraxi

/// La riga sulla schermata di blocco (`accessoryInline`) del widget «Formazione consigliata»: «3-4-3 · 72,7 punti»
/// (`ParoleWidget.moduloEPunti`, #819). Nelle foto del 20/11 la Formazione diceva «SchieraXI 3-4-3 · 72,7». Prossima giornata,
/// che aveva la stessa riga, dal #871 mostra il conto alla rovescia (`WidgetGiornataEContoTests`). Dati inventati.
@Suite("Widget Formazione: la riga della schermata di blocco, modulo e punti")
struct RigaInLineaFormazioneTests {

    private func formazione(_ json: String) throws -> FormazioneWidget {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return try d.decode(FormazioneWidget.self, from: Data(json.utf8))
    }

    @Test("«3-4-3 · 72,7 punti», e dove non entra «3-4-3 · 72,7»: niente «SchieraXI» davanti")
    func forme() throws {
        let f = try formazione(#"{"modulo": "3-4-3", "punti_attesi": 72.7}"#)
        #expect(f.formeInLinea == ["3-4-3 · 72,7 punti", "3-4-3 · 72,7"])
        #expect(f.formeInLinea.allSatisfy { !$0.contains("SchieraXI") })
    }

    @Test("Le forme di `ParoleWidget.moduloEPunti` senza fascia, anche quando il server la manda")
    func moduloEPuntiSenzaFascia() throws {
        let f = try formazione(#"{"modulo": "4-3-3", "punti_attesi": 68.25, "intervallo": {"basso": 60, "alto": 76}}"#)
        #expect(f.formeInLinea == ParoleWidget.moduloEPunti("4-3-3", punti: 68.25, fascia: nil))
    }

    @Test("Senza modulo resta la lineetta, mai una riga vuota")
    func senzaModulo() throws {
        let f = try formazione(#"{"punti_attesi": 70}"#)
        #expect(f.formeInLinea.first == "— · 70,0 punti")
    }
}
