import Foundation
import Testing
@testable import Schieraxi

/// Diario (#614), pagina Giornate dal passo 2 di #673: il titolo della consigliata segue `consigliata.origine`, come la web (#617
/// mostra il confronto solo con «mostrata»; `tests/test_diario_nota_web.py` controlla che la fixture abbia i campi del server).
/// Con «mostrata» quei punti sono della consigliata che SchieraXI mostrava prima della scadenza, non di una ricostruzione. Un server
/// di prima non manda `origine`: niente confronto e niente nota.
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

    @Test("Pagina Giornate: la tua formazione si chiama tua, la consigliata rifatta dice che è rifatta")
    func titoliDellaPaginaGiornate() throws {
        let d: DiarioRisposta = try Fixture.decodifica("diario-origine")
        let p = PaginaGiornate(d)
        let tua = try #require(p.dettaglio("2026-27-11"))
        #expect(tua.titolo == Catalogo.Giornate.formazioneTua(modulo: "3-4-3"))
        let ricostruita = try #require(p.dettaglio("2026-27-10"))
        #expect(ricostruita.titolo == Catalogo.Giornate.formazioneRifatta(modulo: "4-4-2"))
        #expect(ricostruita.nota == Catalogo.Giornate.rifattaNota)
        // un server di prima non manda `origine`: niente nota, come la web
        let diPrima = try #require(p.dettaglio("2026-27-8"))
        #expect(diPrima.titolo == Catalogo.Giornate.formazioneRifatta(modulo: "4-3-3"))
        #expect(diPrima.nota == nil)
    }
}
