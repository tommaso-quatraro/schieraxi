import Foundation
import Testing
@testable import Schieraxi

/// «Le tue scelte» del Diario scrive «Giornata N» con il numero della lega, come la web (`giornata_lega || giornata` in
/// `cartaScelteTue` di fanta/web/app.js) e come le voci del Diario sotto (#200). Dati inventati.
struct ScelteTueGiornataLegaTests {

    /// I titoli delle righe di un blocco `scelte_tue` con una sola giornata.
    private func titoli(_ voce: String) throws -> [String] {
        let json = #"{"giornate": 1, "meglio_consigliata": 1, "per_giornata": [\#(voce)]}"#
        let s: ScelteTue = try Decodifica.decodifica(Data(json.utf8))
        return try #require(ScelteTueTesto(s)).righe.map(\.titolo)
    }

    @Test("La riga dice i due numeri (#299); senza numero della lega (null, assente o strano) solo quello di Serie A",
          arguments: [
            (#"{"stagione": "2026-27", "giornata": 9, "giornata_lega": 6, "esito": "consigliata"}"#, "Giornata 6 · 9ª di Serie A"),
            // fuori dalla stagione in corso il server manda null
            (#"{"stagione": "2025-26", "giornata": 9, "giornata_lega": null, "esito": "consigliata"}"#, "9ª giornata di Serie A"),
            // server vecchio: il campo non c'è
            (#"{"stagione": "2026-27", "giornata": 9, "esito": "consigliata"}"#, "9ª giornata di Serie A"),
            (#"{"stagione": "2026-27", "giornata": 9, "giornata_lega": 0, "esito": "consigliata"}"#, "9ª giornata di Serie A"),
            // un formato che l'app non conosce non fa sparire la scheda
            (#"{"stagione": "2026-27", "giornata": 9, "giornata_lega": "sei", "esito": "consigliata"}"#, "9ª giornata di Serie A"),
          ])
    func titoloDellaRiga(_ voce: String, _ atteso: String) throws {
        #expect(try titoli(voce) == [atteso])
    }

    @Test("Senza giornata la riga non dice «Giornata 0»")
    func senzaGiornataNienteZero() throws {
        #expect(try titoli(#"{"hai_scelto": ["Orsetti"], "consigliava": ["Dunfrey"], "esito": "tua"}"#) == ["Giornata"])
    }

    @Test("Demo: ogni riga ha lo stesso titolo della sua giornata nel Diario")
    func demoComeIlDiario() async throws {
        let dati = try await FinteServer.demo.richiesta("GET", "/api/diario", corpo: nil)
        let d: DiarioRisposta = try Decodifica.decodifica(dati)
        let scelte = try #require(d.scelteTue?.perGiornata)
        try #require(!scelte.isEmpty, "nella demo «Le tue scelte» non ha giornate")
        let righe = try #require(ScelteTueTesto(d.scelteTue)).righe
        try #require(righe.count == scelte.count)
        let voci = d.giornate ?? []
        for (riga, scelta) in zip(righe, scelte) {
            let voce = try #require(voci.first { $0.giornata == scelta.giornata && $0.stagione == scelta.stagione },
                                    "la giornata \(scelta.giornata ?? 0) di «Le tue scelte» manca nel Diario della demo")
            #expect(riga.titolo == voce.titolo, "«Le tue scelte» e il Diario sotto devono dire la stessa giornata")
        }
        #expect(righe.map(\.titolo) == ["Giornata 6 · 9ª di Serie A", "Giornata 5 · 8ª di Serie A"],
                "demo: Serie A 9 e 8 sono le giornate 6 e 5 della lega")
    }
}
