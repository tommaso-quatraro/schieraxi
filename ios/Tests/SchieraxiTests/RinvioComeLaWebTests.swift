import Foundation
import Testing
@testable import Schieraxi

/// Oggi, riquadro «Partita rinviata», come la web (`cardRinvio` di app.js, #284): la partita come quelle del turno («UDI vs MIL»,
/// prima la squadra di casa, mai «UDI–MIL») e la data del recupero come `quando` della web («recupero mer 18 nov 20:45»).
/// Le frasi sono quelle del catalogo comune con la web (`Catalogo.Oggi`, #494): `TestiRinvio` le ha ancora scritte a mano e qui
/// si confrontano. Dati inventati.
@Suite("Carta del rinvio come la web")
struct RinvioComeLaWebTests {
    /// Un momento fisso, ora italiana: giovedì 5 novembre 2026.
    private func adesso() throws -> Date { try #require(Quando.data("2026-11-05 10:00")) }

    @Test("La partita con le sigle e «vs», come le partite del turno")
    func partitaConVs() {
        #expect(TestiRinvio.partita(PartitaRinviata(casa: "udinese", trasferta: "milan", data: nil)) == "UDI vs MIL")
        #expect(TestiRinvio.partita(PartitaRinviata(casa: "atalanta", trasferta: "parma", data: "2026-11-25 20:45")) == "ATA vs PAR")
        #expect(!TestiRinvio.partita(PartitaRinviata(casa: "udinese", trasferta: "milan", data: nil)).contains("–"))
    }

    @Test("VoiceOver legge i nomi interi, come le partite del turno")
    func partitaAVoce() {
        #expect(TestiRinvio.partitaAVoce(PartitaRinviata(casa: "udinese", trasferta: "milan", data: nil)) == "Udinese contro Milan")
    }

    /// La data del recupero e come la scrive `quando` della web, con «adesso» giovedì 5 novembre.
    static let recuperi: [(String, String)] = [
        ("2026-11-18 20:45", "mer 18 nov 20:45"),     // oltre la settimana: con il mese
        ("2026-11-08 15:00", "dom 8 15:00"),          // entro la settimana
        ("2026-11-06 18:30", "domani 18:30"),
        ("2026-11-05 20:45", "oggi 20:45"),
    ]

    @Test("La data del recupero come la web (`oggi.rinvio_recupero` con `quando`, dal catalogo)", arguments: RinvioComeLaWebTests.recuperi)
    func dataDelRecupero(data: String, quando: String) throws {
        let atteso = Catalogo.Oggi.rinvioRecupero(quando: quando)
        let p = PartitaRinviata(casa: "udinese", trasferta: "milan", data: data)
        let ora = try adesso()
        #expect(TestiRinvio.recupero(p, adesso: ora) == atteso)
    }

    @Test("Senza data: «recupero da definire» (`oggi.rinvio_da_definire`)", arguments: [nil, "", "data strana"] as [String?])
    func senzaData(data: String?) throws {
        let atteso = Catalogo.Oggi.rinvioDaDefinire
        let p = PartitaRinviata(casa: "udinese", trasferta: "milan", data: data)
        let ora = try adesso()
        #expect(TestiRinvio.recupero(p, adesso: ora) == atteso)
    }

    @Test("Titolo e giocatori coinvolti con le frasi della web")
    func titoloEGiocatori() {
        #expect(TestiRinvio.titolo(1) == Catalogo.Oggi.rinvioTitolo1)
        #expect(TestiRinvio.titolo(2) == Catalogo.Oggi.rinvioTitoloN)
        let s = SceltaRinvio(giornata: 10, modo: ModoRinvio.aspetta, miei: [GiocatoreRinviato(id: 1, nome: "Ruben Tescari")])
        let miei = Catalogo.Oggi.rinvioMiei(nomi: "Ruben Tescari")
        #expect(TestiRinvio.miei(s) == miei)
    }
}
