import Foundation
import Testing
@testable import Schieraxi

/// Una partita di cui il server sa solo il giorno (`data_partita` «2026-11-01»: l'ora non è ancora fissata) si scrive come
/// `quando` della web dopo #785: il giorno come per le altre date («oggi», «domani», «dom 1», oltre la settimana «dom 8 nov»),
/// senza ora, mai un «00:00» che sembra una partita a mezzanotte (#789). Una data con l'ora resta com'era. Dati inventati.
@Suite("Partite di cui si sa solo il giorno, come la web")
struct GiornoSenzaOraTests {
    /// «Adesso» fisso: giovedì 29 ottobre 2026, ore 9 (ora italiana).
    private func adesso() throws -> Date { try #require(Quando.data("2026-10-29 09:00")) }

    /// Il giorno e come lo scrive `quando` della web, contato da giovedì 29 ottobre.
    static let giorni: [(String, String)] = [
        ("2026-10-29", "oggi"),
        ("2026-10-30", "domani"),
        ("2026-10-28", "ieri"),
        ("2026-11-01", "dom 1"),          // entro la settimana: giorno e numero
        ("2026-11-04", "mer 4"),          // 6 giorni avanti: ancora senza mese
        ("2026-10-23", "ven 23"),         // 6 giorni indietro, prima del cambio dell'ora
        ("2026-11-05", "gio 5 nov"),      // oltre la settimana anche il mese
        ("2026-11-08", "dom 8 nov"),
        ("2026-10-22", "gio 22 ott"),
        ("2027-01-10", "dom 10 gen"),
    ]

    @Test("Solo il giorno: «oggi», «domani», «dom 1», oltre la settimana con il mese, senza ora", arguments: GiornoSenzaOraTests.giorni)
    func soloIlGiorno(data: String, atteso: String) throws {
        let ora = try adesso()
        #expect(Quando.leggibile(data, adesso: ora) == atteso)
    }

    @Test("Con l'ora tutto come prima: «dom 1 18:30», anche con la «T» e i secondi; la mezzanotte scritta resta «00:00»")
    func conLOraComePrima() throws {
        let ora = try adesso()
        #expect(Quando.leggibile("2026-11-01 18:30", adesso: ora) == "dom 1 18:30")
        #expect(Quando.leggibile("2026-11-01T20:45:00", adesso: ora) == "dom 1 20:45")
        #expect(Quando.leggibile("2026-10-30 00:00", adesso: ora) == "domani 00:00")
        #expect(Quando.leggibile("2026-11-08 15:00", adesso: ora) == "dom 8 nov 15:00")
    }

    @Test("Il giorno si conta sul calendario italiano: alle 23:50 il giorno dopo è «domani», dopo mezzanotte «oggi»")
    func mezzanotteDiRoma() throws {
        let sera = try #require(Quando.data("2026-10-31 23:50"))
        let notte = try #require(Quando.data("2026-11-01 00:10"))
        #expect(Quando.leggibile("2026-11-01", adesso: sera) == "domani")
        #expect(Quando.leggibile("2026-11-01", adesso: notte) == "oggi")
    }

    @Test("Un testo che non è una data resta com'è; `Quando.data` continua a volere l'ora (widget e scadenze contano su quella)")
    func testoStrano() {
        #expect(Quando.leggibile("2026-11-1") == "2026-11-1")
        #expect(Quando.leggibile("2026-02-30") == "2026-02-30", "un giorno che non c'è non diventa il 2 marzo")
        #expect(Quando.leggibile("boh") == "boh")
        #expect(Quando.data("2026-11-01") == nil)
    }

    // MARK: dove la web lo mostra

    /// Un giocatore inventato del Venezia che gioca in casa contro l'Inter, con questo pezzo di JSON in più.
    private func giocatore(_ altro: String) throws -> Giocatore {
        let json = #"{"id": 7, "nome": "Mario Prova", "ruolo": "C", "fv_atteso": 6.5, "squadra": "venezia", "avversario": "inter", "in_casa": true, \#(altro)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    @Test("Riga del giocatore e panchina: «VEN vs INT · dom 1», come `partitaBreve` della web")
    func riga() throws {
        let ora = try adesso()
        let soloGiorno = try giocatore(#""data_partita": "2026-11-01""#)
        let conOra = try giocatore(#""data_partita": "2026-11-01T20:45:00""#)
        let strana = try giocatore(#""data_partita": "domani sera""#)
        #expect(RigaGiocatore.sottotitolo(soloGiorno, adesso: ora) == "VEN vs INT · dom 1")
        #expect(RigaGiocatore.sottotitolo(conOra, adesso: ora) == "VEN vs INT · dom 1 20:45")
        #expect(RigaGiocatore.sottotitolo(strana, adesso: ora) == "VEN vs INT", "un testo che non è una data non si scrive")
    }

    @Test("Pedina a formazione chiusa, per chi deve ancora giocare: «domani», come `pedina` della web")
    func pedina() throws {
        let g = try giocatore(#""stato_partita": "da_giocare", "data_partita": "2026-10-30""#)
        let ora = try adesso()
        let c = LetturaPedina.contenuto(g, adesso: ora)
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: "domani", tono: .parola)])
        #expect(c.voce == "Mario Prova, fantavoto atteso 6,5, domani")
    }

    @Test("Scheda: «In casa contro Inter · dom 1» (`formazione.partita_casa`), non «–»")
    func scheda() throws {
        let g = try giocatore(#""data_partita": "2026-11-01""#)
        let ora = try adesso()
        #expect(LetturaScheda.partita(g, adesso: ora) == Catalogo.Formazione.partitaCasa(avv: "Inter", quando: "dom 1"))
    }

    @Test("Partita rinviata: «recupero dom 8 nov» (`oggi.rinvio_recupero`), non «recupero da definire»")
    func recupero() throws {
        let p = PartitaRinviata(casa: "udinese", trasferta: "milan", data: "2026-11-08")
        let ora = try adesso()
        #expect(TestiRinvio.recupero(p, adesso: ora) == Catalogo.Oggi.rinvioRecupero(quando: "dom 8 nov"))
    }
}
