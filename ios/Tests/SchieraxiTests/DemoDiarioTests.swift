import Foundation
import Testing
@testable import Schieraxi

/// Il Diario dei dati di prova (modalità demo e fotografie) torna con la testata della demo, «Giornata 8» della lega
/// (Serie A 11: la lega parte dalla giornata 4 di Serie A). Le giornate finite sono la 4, 5, 6 e 7 della lega (Serie A 7-10)
/// e ognuna porta il suo `giornata_lega`, come le manda il server (`elenco` e `scelte_tue` di `fanta/diario.py`).
/// Dati inventati: quelli di `DatiDemo.swift`, tutti della stagione in corso.
struct DemoDiarioTests {

    private func dati(_ percorso: String) async throws -> Data {
        try await FinteServer.demo.richiesta("GET", percorso, corpo: nil)
    }

    private func diario() async throws -> DiarioRisposta {
        try Decodifica.decodifica(try await dati("/api/diario"))
    }

    /// Serie A meno lega nella giornata di Oggi della demo.
    private func scarto() async throws -> Int {
        let oggi: Oggi = try Decodifica.decodifica(try await dati("/api/oggi"))
        let serieA = try #require(oggi.giornata)
        let lega = try #require(oggi.giornataLega)
        #expect(serieA != lega, "se i due numeri coincidono il test non distingue più la lega dalla Serie A")
        return serieA - lega
    }

    @Test("Ogni voce del Diario della demo porta il numero della lega giusto",
          arguments: ["giornate", "precisione.per_giornata", "scelte_tue.per_giornata"])
    func numeroDellaLegaInOgniElenco(_ percorso: String) async throws {
        let scarto = try await scarto()
        var nodo: Any? = try JSONSerialization.jsonObject(with: try await dati("/api/diario"))
        for chiave in percorso.split(separator: ".") { nodo = (nodo as? [String: Any])?[String(chiave)] }
        let voci = try #require(nodo as? [[String: Any]], "nel diario della demo manca «\(percorso)»")
        #expect(!voci.isEmpty, "«\(percorso)» è vuoto")
        for voce in voci {
            let serieA = try #require(voce["giornata"] as? Int, "«\(percorso)»: una voce senza giornata")
            let lega = voce["giornata_lega"] as? Int
            let letta = lega.map { String($0) } ?? "nessuna"
            #expect(lega == serieA - scarto,
                    "«\(percorso)»: la giornata \(serieA) di Serie A è la \(serieA - scarto) della lega, non \(letta)")
            #expect(serieA - scarto >= 1, "«\(percorso)»: la giornata \(serieA) di Serie A è prima che la lega partisse")
        }
    }

    @Test("I titoli delle giornate e «Calcolato su…» dicono i numeri della lega")
    func titoliEPrecisioneConINumeriDellaLega() async throws {
        let d = try await diario()
        #expect((d.giornate ?? []).map(\.titolo) == ["Giornata 7", "Giornata 6", "Giornata 5", "Giornata 4"])
        let testo = try #require(TestoPrecisione(d.precisione))
        #expect(testo.calcolatoSu == "Calcolato su 4 giornate, dalla giornata 4 alla 7.")
    }

    @Test("«In sintesi» è quella che il server calcola dalle giornate con la tua formazione")
    func sintesiComeIlServer() async throws {
        let d = try await diario()
        let s = try #require(d.sintesi)
        // come `sintesi` di fanta/diario.py: solo le giornate in cui hai schierato una tua formazione, medie a un decimale
        let con = (d.giornate ?? []).filter { $0.schierata != nil }
        try #require(!con.isEmpty, "nella demo nessuna giornata ha la tua formazione")
        let tue = con.map { $0.schierata?.reale ?? 0 }
        let consigliate = con.map { $0.consigliata?.reale ?? 0 }
        let attesiTue = con.map { $0.schierata?.atteso ?? 0 }
        let meglioTua = zip(tue, consigliate).filter { $0.0 > $0.1 }.count
        let meglioConsigliata = zip(tue, consigliate).filter { $0.0 < $0.1 }.count
        #expect(s.giornate == con.count)
        #expect(s.puntiSchierata == media(tue))
        #expect(s.puntiConsigliata == media(consigliate))
        #expect(s.attesiSchierata == media(attesiTue))
        #expect(s.meglioTua == meglioTua)
        #expect(s.meglioConsigliata == meglioConsigliata)
    }

    /// La media a un decimale, come `round(…, 1)` del server.
    private func media(_ valori: [Double]) -> Double {
        (valori.reduce(0, +) / Double(valori.count) * 10).rounded() / 10
    }
}
