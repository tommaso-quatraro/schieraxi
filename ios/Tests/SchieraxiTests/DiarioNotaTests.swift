import Foundation
import Testing
@testable import Schieraxi

/// Diario (#614, revisione di #642): la frase sulle giornate senza verdetto la scrive il server (`nota` di `precisione.confronto`) e
/// l'iPhone la mostra così com'è, in fondo ai «Dettagli» della pagina Giornate, come la web (`dettagliPrecisione`, #671). La voce
/// «la consigliata contro la tua» c'è solo con almeno una giornata con un verdetto, e la frase non le si attacca più dietro.
/// La fixture `diario-nota.json` è la risposta del server in tre casi (dati inventati, la tiene allineata
/// `tests/test_diario_nota_web.py`): solo giornate senza la consigliata di allora; una sola confrontabile, con gli stessi titolari,
/// e cinque lasciate fuori; una con un verdetto e una lasciata fuori.
@MainActor
struct DiarioNotaTests {
    private struct Casi: Decodable {
        let tutteFuori: DiarioRisposta
        let unaUguale: DiarioRisposta
        let verdetto: DiarioRisposta
    }

    private struct FileNota: Decodable {
        let casi: Casi
    }

    private func casi() throws -> Casi {
        let f: FileNota = try Fixture.decodifica("diario-nota")
        return f.casi
    }

    private static let salvata = "la consigliata di allora non era stata salvata."

    @Test("Solo giornate senza la consigliata di allora: niente voce del confronto, la frase del server in fondo")
    func tutteFuori() throws {
        let d = try casi().tutteFuori
        let nota = "3 giornate non entrano nel confronto: " + Self.salvata
        let p = try #require(TestoPrecisione(d.precisione))
        #expect(p.confronto == nil)
        #expect(p.voci.count == 3)
        #expect(p.nota == nota)
        // giornata per giornata solo l'errore e i punti della consigliata, come la web
        #expect(p.righe.count == 3)
        #expect(p.righe.allSatisfy { !$0.contains("tua") })
        #expect(PaginaGiornate(d).dettagli?.nota == nota)
    }

    @Test("Una sola giornata confrontabile, uguale: la frase del server dice anche le cinque lasciate fuori")
    func unaUguale() throws {
        let d = try casi().unaUguale
        let nota = "Hai schierato gli stessi undici della consigliata in tutte le giornate in cui era stata salvata. "
            + "5 giornate non entrano nel confronto: " + Self.salvata
        let p = try #require(TestoPrecisione(d.precisione))
        #expect(p.confronto == nil)
        #expect(p.nota == nota)
    }

    @Test("Con un verdetto la voce del confronto c'è, e la frase sta in fondo, non dietro ai numeri")
    func verdetto() throws {
        let d = try casi().verdetto
        let nota = "1 giornata non entra nel confronto: " + Self.salvata
        let p = try #require(TestoPrecisione(d.precisione))
        let cf = try #require(p.confronto)
        #expect(cf.numero == "1 su 1")
        #expect(cf.frase.hasPrefix("Giornate in cui la consigliata ha fatto meglio della tua: 1 su 1."))
        #expect(!cf.frase.contains(nota))
        #expect(p.nota == nota)
        #expect(p.righe.allSatisfy { !$0.contains("tua") })
    }

    @Test("Senza consigliate mostrate nella pagina la voce del confronto non c'è, anche con un verdetto")
    func senzaConsigliataMostrata() throws {
        let d = try casi().verdetto
        #expect(TestoPrecisione(d.precisione, conConfronto: false)?.confronto == nil)
    }

    @Test("Un server di prima, senza la frase: niente voce del confronto e niente frase")
    func serverDiPrima() throws {
        let p = try #require(TestoPrecisione(PrecisioneDiario(giornate: 2, confronto: .init(giornate: 0))))
        #expect(p.confronto == nil)
        #expect(p.nota == nil)
    }
}
