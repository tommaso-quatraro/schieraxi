import Foundation
import Testing
@testable import Schieraxi

/// Stato dei dati, «Ultimi aggiornamenti» come la web (#808): il nome di ogni riga è il campo `etichetta` del server
/// (`fanta/stato_dati.py`); un server di prima, senza il campo, usa i nomi dell'app (`NomiDati.leggibile`). Un passo mai riuscito
/// (senza `quando`) dice «mai» (`sd.mai`), come la web.
@Suite("Stato dei dati: nomi degli aggiornamenti dal server (#808)")
struct StatoDatiNomiTests {
    private func aggiornamento(_ json: String) throws -> AggiornamentoDati {
        let s: StatoDati = try Decodifica.decodifica(Data(#"{"aggiornamenti": [\#(json)]}"#.utf8))
        return try #require(s.aggiornamenti?.first)
    }

    @Test("Il nome è l'etichetta del server, come la web")
    func etichettaDelServer() throws {
        let a = try aggiornamento(#"{"cosa": "listone", "quando": "2026-11-20T08:00:00", "errori": [], "etichetta": "Listone e quotazioni"}"#)
        #expect(a.etichetta == "Listone e quotazioni")
        #expect(NomiDati.nome(a) == "Listone e quotazioni")
    }

    @Test("Un server senza etichetta (o con l'etichetta vuota): i nomi dell'app", arguments: [
        #"{"cosa": "listone", "quando": "2026-11-20T08:00:00", "errori": []}"#,
        #"{"cosa": "listone", "quando": "2026-11-20T08:00:00", "errori": [], "etichetta": "  "}"#,
        #"{"cosa": "listone", "quando": "2026-11-20T08:00:00", "errori": [], "etichetta": null}"#,
    ])
    func senzaEtichetta(json: String) throws {
        let a = try aggiornamento(json)
        #expect(NomiDati.nome(a) == NomiDati.leggibile("listone"))
        #expect(NomiDati.nome(a) == "Elenco dei calciatori")
    }

    @Test("Un passo mai riuscito: «mai», come la web", arguments: [
        #"{"cosa": "risultati-rapido", "quando": null, "errori": [], "etichetta": "Risultati la sera stessa"}"#,
        #"{"cosa": "risultati-rapido", "errori": ["Non riuscito alle 21:30 del 19/11: nessuna risposta"]}"#,
        #"{"cosa": "risultati-rapido", "quando": "", "errori": []}"#,
    ])
    func maiRiuscito(json: String) throws {
        let a = try aggiornamento(json)
        #expect(NomiDati.quando(a) == Catalogo.Sd.mai)
        #expect(NomiDati.quando(a) == "mai")
    }

    @Test("Con la data, la stessa scrittura di prima")
    func conLaData() throws {
        let a = try aggiornamento(#"{"cosa": "voti", "quando": "2026-11-20T08:00:00", "errori": [], "etichetta": "Voti e bonus"}"#)
        #expect(NomiDati.quando(a) == Quando.leggibile("2026-11-20 08:00:00"))
        #expect(NomiDati.quando(a) != Catalogo.Sd.mai)
    }
}
