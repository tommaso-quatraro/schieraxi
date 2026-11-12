import Foundation
import Testing
@testable import Schieraxi

/// Le frasi della Formazione uguali alla web (#437, riga 52 di `docs/COERENZA-WEB-IPHONE.md`): intestazione con «la tua scelta»,
/// probabili non ancora uscite, panchina, ballottaggio, frase dello stile, riga sotto «Titolari» (✎ sostituisce, ⇄ confronta) e
/// foglio della sostituzione. Dal #495 le frasi vengono dal catalogo comune con la web (`Catalogo.Formazione`, generato da
/// `fanta/testi/formazione.json`): qui si controlla che ogni frase dell'iPhone usi la chiave giusta.
@MainActor
@Suite("Frasi della Formazione come la web")
struct FormazioneComeLaWebTests {
    /// La frase dell'iPhone per una chiave del catalogo (nil = chiave che questo test non conosce).
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
    func intestazione() {
        let g = TempiLega.etichetta(serieA: 11, lega: 8)
        let tua = Catalogo.Formazione.laTuaScelta
        #expect(TempiLega.didascalia(giornata: g, scelta: true, comeConsigliato: false) == "\(g) · \(tua)")
        #expect(TempiLega.didascalia(giornata: g, scelta: true, comeConsigliato: true) == "\(g) · \(tua)",
                "a mano conta la tua scelta, anche se il modulo è quello consigliato")
        #expect(TempiLega.didascalia(giornata: g, scelta: false, comeConsigliato: true) == "\(g) · \(Catalogo.Formazione.moduloConsigliato)")
        #expect(TempiLega.didascalia(giornata: g, scelta: false, comeConsigliato: false) == "\(g) · \(Catalogo.Formazione.moduloScelto)")
    }

    @Test("Le frasi fisse della Formazione e della sostituzione sono quelle del catalogo", arguments: [
        ("formazione.mancano_probabili_formazioni", Catalogo.Formazione.mancanoProbabiliFormazioni),
        ("formazione.quest_ordine_entra", Catalogo.Formazione.questOrdineEntra),
        ("formazione.ballottaggio_alternative_vic", Catalogo.Formazione.ballottaggioAlternativeVic),
        ("formazione.giocatori_dello_stesso", Catalogo.Formazione.giocatoriDelloStesso),
        ("formazione.nessun_altro_giocatore", Catalogo.Formazione.nessunAltroGiocatore),
    ])
    func fraseFissa(chiave: String, catalogo: String) throws {
        let iPhone = try #require(fraseIPhone(chiave), "manca la frase dell'iPhone per \(chiave)")
        #expect(iPhone == catalogo)
    }

    @Test("Sotto «Titolari», in modifica a mano: «Tocca ✎ per sostituire…» (il confronto con ⇄ non c'è più, #634)")
    func rigaTitolari() {
        #expect(FormazioneView.istruzioneTitolari == Catalogo.Formazione.toccaSostituire)
    }

    @Test("Il segno della riga è quello della frase: ✎ (matita) per sostituire")
    func segniDelleRighe() {
        #expect(FormazioneView.simboloSostituisci == "pencil")
        #expect(Catalogo.Formazione.toccaSostituire.contains("✎"))
    }

    @Test("In fondo alla Formazione la nota sui numeri non parla più dell'indice né dell'anello (#634)", arguments: [true, false])
    func notaSenzaIndice(conPerche: Bool) {
        let nota = FormazioneView.legenda(conPerche: conPerche)
        #expect(nota.contains("fantavoto atteso"))
        #expect(nota.contains("Toccalo per sapere perché.") == conPerche)
        for parola in ["indice", "anello", "sul volto"] {
            #expect(!nota.localizedCaseInsensitiveContains(parola), "c'è ancora «\(parola)»")
        }
    }

    @Test("Le frasi di prima non ci sono più (#437)")
    func nienteFrasiVecchie() {
        let tutte = [FormazioneView.testoSenzaProbabili, FormazioneView.testoPanchina, FormazioneView.testoBallottaggio,
                     FormazioneView.istruzioneTitolari, SostituzioneSheet.testoNessunAltro]
        for vecchia in ["Probabili formazioni non ancora uscite", "In quest'ordine", "alternative vicine", "Modulo proposto",
                        "Tocca un titolare per sostituirlo", "Non ci sono altri giocatori"] {
            #expect(!tutte.contains { $0.contains(vecchia) }, "c'è ancora «\(vecchia)»")
        }
    }
}
