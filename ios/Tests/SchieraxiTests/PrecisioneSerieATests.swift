import Foundation
import Testing
@testable import Schieraxi

/// «Quanto ci abbiamo preso», la riga su tutta la Serie A (campo `precisione.serie_a` di `/api/diario`, issue #374).
/// Il testo lo scrive il server (`fanta/precisione.py`, `serie_a`; frasi `diario.serie_a*` di `fanta/frasi.py`) e l'iPhone lo
/// mostra così com'è, come la web in italiano: qui i testi sono quelli che il server scrive con un registro finto di 2 e di 3
/// giornate (gli stessi di `tests/test_precisione_serie_a.py`). Dati inventati.
@Suite("Diario: la riga su tutta la Serie A")
struct PrecisioneSerieATests {

    static let dueGiornate: String = "Su tutta la Serie A serve ancora 1 giornata per dire quanto ci prendiamo."
    static let treGiornate: String = "Su tutta la Serie A, nelle ultime 3 giornate: il fantavoto atteso ha sbagliato il 18% in meno della "
        + "fantamedia; quando diciamo «gioca 95%», ha giocato 9 volte su 10."

    /// Una risposta del Diario con una giornata e il campo `serie_a` scritto così com'è (`nil`: il campo non c'è).
    private static func risposta(serieA: String?) throws -> DiarioRisposta {
        let campo = serieA.map { #", "serie_a": \#($0)"# } ?? ""
        let json = #"""
        {"giornate": [], "precisione": {"giornate": 1, "pochi_dati": true, "giornate_minime": 8,
          "fantavoto": {"errore_medio": 1.0, "scostamento": 1.0, "entro_un_punto": 100, "voti": 5}\#(campo)}}
        """#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    @Test("Registro di 2 giornate: «serve ancora 1 giornata», senza numeri")
    func dueGiornateServonoAncora() throws {
        let d = try Self.risposta(serieA: #"""
            {"giornate": 2, "giornate_minime": 3, "mancano": 1, "testo": "\#(Self.dueGiornate)",
             "frase": {"chiave": "diario.serie_a_attesa", "param": {"n": 1}}}
            """#)
        let s = try #require(d.precisione?.serieA)
        #expect(s.giornate == 2 && s.giornateMinime == 3 && s.mancano == 1)
        let t = try #require(TestoPrecisione(d.precisione))
        #expect(t.serieA == Self.dueGiornate)
    }

    @Test("Registro di 3 giornate: la riga con i numeri, uguale al testo del server")
    func treGiornateRigaConINumeri() throws {
        let d = try Self.risposta(serieA: #"""
            {"giornate": 3, "giornate_minime": 3, "mancano": 0, "voti": 300, "errore_fantavoto": 1.0, "errore_fantamedia": 1.225,
             "rispetto_fantamedia": -18, "gioca": {"giocatori": 300, "principale": 1, "gruppi": [
               {"da": 0, "a": 40, "giocatori": 150, "pochi": false, "detto": 15, "giocato": 16},
               {"da": 90, "a": 100, "giocatori": 150, "pochi": false, "detto": 95, "giocato": 94}]},
             "testo": "\#(Self.treGiornate)",
             "frase": {"chiave": "diario.serie_a", "param": {"n": 3}}}
            """#)
        #expect(d.precisione?.serieA?.mancano == 0)
        let t = try #require(TestoPrecisione(d.precisione))
        #expect(t.serieA == Self.treGiornate)
    }

    @Test("Niente riga con un server vecchio, un registro vuoto o un campo strano; il resto della carta resta", arguments: [
        String?.none, "null", #"{"giornate": 0}"#, #"{"testo": ""}"#, #"{"testo": 5}"#, #""Su tutta la Serie A""#, "[]",
    ])
    func senzaRiga(_ campo: String?) throws {
        let p = try Self.risposta(serieA: campo).precisione
        let t = try #require(TestoPrecisione(p))
        #expect(t.serieA == nil)
        #expect(t.fantavoto.numero == "1,0")
    }
}
