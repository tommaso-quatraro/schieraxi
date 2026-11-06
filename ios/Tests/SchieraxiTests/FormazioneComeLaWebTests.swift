import Foundation
import Testing
@testable import Schieraxi

/// Le frasi della Formazione uguali alla web (#437, riga 52 di `docs/COERENZA-WEB-IPHONE.md`): intestazione con «la tua scelta»,
/// probabili non ancora uscite, panchina, ballottaggio, frase dello stile, riga sotto «Titolari» (✎ sostituisce, ⇄ confronta) e
/// foglio della sostituzione. Ogni frase dell'iPhone si confronta con la sua chiave di `fanta/web/testi.js`, così una frase
/// cambiata su un lato solo fa fallire il test.
@MainActor
@Suite("Frasi della Formazione come la web")
struct FormazioneComeLaWebTests {
    private func web(_ chiave: String, _ valori: [String: String] = [:]) throws -> String {
        var testo = try TestiWeb().italiano(chiave)
        for (nome, valore) in valori { testo = testo.replacingOccurrences(of: "{\(nome)}", with: valore) }
        return testo
    }

    /// La frase dell'iPhone per una chiave di `testi.js` (nil = chiave che questo test non conosce).
    private func fraseIPhone(_ chiave: String) -> String? {
        switch chiave {
        case "formazione.mancano_probabili_formazioni": return FormazioneView.testoSenzaProbabili
        case "formazione.quest_ordine_entra": return FormazioneView.testoPanchina
        case "formazione.ballottaggio_alternative_vic": return FormazioneView.testoBallottaggio
        case "formazione.giocatori_dello_stesso": return SostituzioneSheet.testoStessoRuolo
        case "formazione.nessun_altro_giocatore": return SostituzioneSheet.testoNessunAltro
        default: return nil
        }
    }

    @Test("Intestazione: «· la tua scelta» in modifica a mano, altrimenti «· modulo consigliato» o «· modulo scelto»")
    func intestazione() throws {
        let g = TempiLega.etichetta(serieA: 11, lega: 8)
        let tua = try web("formazione.la_tua_scelta")
        #expect(TempiLega.didascalia(giornata: g, scelta: true, comeConsigliato: false) == "\(g) · \(tua)")
        #expect(TempiLega.didascalia(giornata: g, scelta: true, comeConsigliato: true) == "\(g) · \(tua)",
                "a mano conta la tua scelta, anche se il modulo è quello consigliato")
        #expect(TempiLega.didascalia(giornata: g, scelta: false, comeConsigliato: true) == "\(g) · \(try web("formazione.modulo_consigliato"))")
        #expect(TempiLega.didascalia(giornata: g, scelta: false, comeConsigliato: false) == "\(g) · \(try web("formazione.modulo_scelto"))")
    }

    @Test("Le frasi fisse della Formazione e della sostituzione sono quelle di testi.js",
          arguments: ["formazione.mancano_probabili_formazioni", "formazione.quest_ordine_entra",
                      "formazione.ballottaggio_alternative_vic", "formazione.giocatori_dello_stesso",
                      "formazione.nessun_altro_giocatore"])
    func fraseFissa(chiave: String) throws {
        let iPhone = try #require(fraseIPhone(chiave), "manca la frase dell'iPhone per \(chiave)")
        #expect(iPhone == (try web(chiave)))
    }

    @Test("Sotto «Titolari»: «Tocca ✎ per sostituire…» in modifica a mano, «Tocca ⇄ per confrontarlo…» altrimenti",
          arguments: zip([true, false], ["formazione.tocca_sostituire", "formazione.tocca_confronto"]))
    func rigaTitolari(modificabile: Bool, chiave: String) throws {
        #expect(FormazioneView.istruzioneTitolari(modificabile: modificabile) == (try web(chiave)))
    }

    @Test("Il segno della riga è quello della frase: ✎ (matita) per sostituire, ⇄ per confrontare")
    func segniDelleRighe() throws {
        #expect(FormazioneView.simboloSostituisci == "pencil")
        #expect(FormazioneView.simboloConfronta == "arrow.left.arrow.right")
        #expect(try web("formazione.tocca_sostituire").contains("✎"))
        #expect(try web("formazione.tocca_confronto").contains("⇄"))
    }

    @Test("Stile: «Propone il 3-4-3.» con il modulo dello stile, «Modulo fissato a mano (…)» con un altro modulo")
    func fraseStile() throws {
        #expect(FormazioneView.fraseStile(proposto: "3-4-3", attivo: "3-4-3") == (try web("formazione.propone", ["modulo": "3-4-3"])))
        #expect(FormazioneView.fraseStile(proposto: "3-4-3", attivo: "4-4-2")
                == (try web("formazione.modulo_fissato", ["modulo": "3-4-3"])), "nella frase c'è il modulo dello stile, non quello scelto")
    }

    @Test("Le frasi di prima non ci sono più (#437)")
    func nienteFrasiVecchie() {
        let tutte = [FormazioneView.testoSenzaProbabili, FormazioneView.testoPanchina, FormazioneView.testoBallottaggio,
                     FormazioneView.istruzioneTitolari(modificabile: true), FormazioneView.fraseStile(proposto: "3-4-3", attivo: "3-4-3"),
                     SostituzioneSheet.testoNessunAltro]
        for vecchia in ["Probabili formazioni non ancora uscite", "In quest'ordine", "alternative vicine", "Modulo proposto",
                        "Tocca un titolare per sostituirlo", "Non ci sono altri giocatori"] {
            #expect(!tutte.contains { $0.contains(vecchia) }, "c'è ancora «\(vecchia)»")
        }
    }
}
