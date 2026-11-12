import Foundation
import Testing
@testable import Schieraxi

/// Diario (#614): l'etichetta dei punti della consigliata segue `consigliata.origine`, come sulla web
/// (`etichettaConsigliataDiario` di `fanta/web/app.js`, provata sulle stesse voci da `tests/test_diario_origine_web.py`).
/// Con «mostrata» quei punti sono della consigliata che SchieraXI mostrava prima della scadenza, non di una ricostruzione: prima
/// la riga diceva «Ricostruita oggi» ogni volta che c'era l'istantanea. Un server di prima non manda `origine`: resta com'era.
/// La fixture `diario-origine.json` (dati inventati) ha le voci nelle due forme: giornate 11, 10 e 9 con `origine` (server
/// nuovo), giornate 8 e 7 senza (server di prima).
@MainActor
struct DiarioOrigineTests {
    private func voce(_ giornata: Int) throws -> VoceDiario {
        let d: DiarioRisposta = try Fixture.decodifica("diario-origine")
        let voci = try #require(d.giornate)
        return try #require(voci.first { $0.giornata == giornata })
    }

    @Test("Si legge l'origine della consigliata; un server di prima non la manda e il resto si legge lo stesso")
    func decodifica() throws {
        let mostrata = try voce(11)
        let ricostruita = try voce(10)
        let diPrima = try voce(8)
        #expect(mostrata.consigliata?.origine == "mostrata")
        #expect(mostrata.consigliata?.reale == 64.5)
        #expect(mostrata.consigliata?.atteso == 72.5)
        #expect(mostrata.schierata?.reale == 66.0)
        #expect(ricostruita.consigliata?.origine == "ricostruita")
        #expect(diPrima.consigliata?.origine == nil)
        #expect(diPrima.consigliata?.reale == 78.5)
    }

    @Test("Con la consigliata mostrata i punti non si chiamano «Ricostruita oggi»")
    func mostrata() throws {
        let v = try voce(11)
        let etichetta = DiarioView.etichettaConsigliata(v)
        #expect(etichetta == "La consigliata (3-4-3)")
        #expect(etichetta == Catalogo.Diario.laConsigliata(modulo: "3-4-3"))
    }

    @Test("La ricostruita resta detta ricostruita: con la consigliata di allora che non si può più schierare, o non registrata")
    func ricostruita() throws {
        let conIstantanea = try voce(10)
        let senzaIstantanea = try voce(9)
        #expect(DiarioView.etichettaConsigliata(conIstantanea) == "Ricostruita oggi (4-4-2)")
        #expect(DiarioView.etichettaConsigliata(senzaIstantanea) == "Di SchieraXI (4-4-2)")
    }

    @Test("Con un server di prima, senza il campo, resta com'era")
    func serverDiPrima() throws {
        let conIstantanea = try voce(8)
        let senzaIstantanea = try voce(7)
        #expect(DiarioView.etichettaConsigliata(conIstantanea) == "Ricostruita oggi (4-3-3)")
        #expect(DiarioView.etichettaConsigliata(senzaIstantanea) == "Di SchieraXI (4-3-3)")
    }

    @Test("Senza consigliata non c'è la riga dei suoi punti")
    func senzaConsigliata() throws {
        let v: VoceDiario = try Decodifica.decodifica(Data(#"{"giornata": 6, "stagione": "2026-27"}"#.utf8))
        #expect(DiarioView.etichettaConsigliata(v) == nil)
    }
}
