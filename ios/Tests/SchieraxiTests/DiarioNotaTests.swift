import Foundation
import Testing
@testable import Schieraxi

/// Diario (#614, revisione di #642): la frase sulle giornate senza verdetto la scrive il server (`nota` di `scelte_tue` e di
/// `precisione.confronto`) e l'iPhone la mostra così com'è, come la web (`cartaScelteTue` e `cartaPrecisione`, provate sulle
/// stesse risposte da `tests/test_diario_nota_web.py`). Prima l'iPhone scriveva «Non sappiamo ancora cosa hai schierato» anche a
/// chi l'aveva detto, e nascondeva «Le tue scelte». La fixture `diario-nota.json` è la risposta del server in tre casi (dati
/// inventati, la tiene allineata `tests/test_diario_nota_web.py`): solo giornate senza la consigliata di allora; una sola
/// confrontabile, con gli stessi titolari, e cinque lasciate fuori; una con un verdetto e una lasciata fuori.
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

    @Test("Solo giornate senza la consigliata di allora: «Le tue scelte» c'è e dice quante restano fuori")
    func tutteFuori() throws {
        let d = try casi().tutteFuori
        let nota = "3 giornate non entrano nel confronto: " + Self.salvata
        let scelte = try #require(ScelteTueTesto(d.scelteTue))
        #expect(scelte.soloNota)
        #expect(scelte.nota == nota)
        #expect(scelte.voceRiepilogo == "Le tue scelte. " + nota)
        let p = try #require(TestoPrecisione(d.precisione))
        #expect(p.confronto.numero == "–")
        #expect(p.confronto.frase == nota)
        // nell'andamento i tuoi punti, senza la differenza che il server non manda (prima «(0,0)», come se fossero pari)
        #expect(p.righe.count == 3)
        #expect(p.righe.allSatisfy { $0.hasSuffix(" · tua: 66,0") })
    }

    @Test("Una sola giornata confrontabile, uguale: non dice «finora sempre la consigliata» con cinque giornate lasciate fuori")
    func unaUguale() throws {
        let d = try casi().unaUguale
        let nota = "Hai schierato gli stessi undici della consigliata in tutte le giornate in cui era stata salvata. "
            + "5 giornate non entrano nel confronto: " + Self.salvata
        let scelte = try #require(ScelteTueTesto(d.scelteTue))
        #expect(scelte.soloNota)
        #expect(scelte.nota == nota)
        let p = try #require(TestoPrecisione(d.precisione))
        #expect(p.confronto.frase == nota)
    }

    @Test("Con un verdetto la frase va dopo i numeri, nelle due schede")
    func verdetto() throws {
        let d = try casi().verdetto
        let nota = "1 giornata non entra nel confronto: " + Self.salvata
        let scelte = try #require(ScelteTueTesto(d.scelteTue))
        #expect(!scelte.soloNota)
        #expect(scelte.numeroGrande == "0 su 1")
        #expect(scelte.nota == nota)
        #expect(scelte.voceRiepilogo.hasSuffix(" " + nota))
        let p = try #require(TestoPrecisione(d.precisione))
        #expect(p.confronto.numero == "1 su 1")
        #expect(p.confronto.frase.hasPrefix("Giornate in cui la consigliata ha fatto meglio della tua: 1 su 1."))
        #expect(p.confronto.frase.hasSuffix(" " + nota))
        #expect(p.righe.first?.hasSuffix(" · tua: 66,0 (+4,0)") == true)
        #expect(p.righe.last?.hasSuffix(" · tua: 66,0") == true)
    }

    @Test("Un server di prima, senza la frase: niente scheda senza giornate, il confronto dice la frase di sempre")
    func serverDiPrima() throws {
        let vecchio: ScelteTue = try Decodifica.decodifica(Data(#"{"giornate": 0, "pochi_dati": true, "per_giornata": []}"#.utf8))
        #expect(ScelteTueTesto(vecchio) == nil)
        let p = try #require(TestoPrecisione(PrecisioneDiario(giornate: 2, confronto: .init(giornate: 0))))
        #expect(p.confronto.frase == "Non sappiamo ancora cosa hai schierato: dillo qui sotto in ogni giornata, con «Ho schierato…».")
    }
}
