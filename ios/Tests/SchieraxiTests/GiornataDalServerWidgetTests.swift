import Foundation
import Testing
@testable import Schieraxi

/// Widget «Attesi e fatti» e Cruscotto con `giornata_lega` e `stagione` per ogni voce del diario (server dal 2/11/2026, issue #170):
/// gli stessi numeri dell'app e della web («Giornata 6 · 9ª di Serie A», #299), e la stagione accanto alle voci di
/// un'altra stagione («38ª giornata di Serie A · 2025-26»). Il calcolo con lo scarto della giornata attuale resta solo per un server vecchio, che non manda i due campi.
struct GiornataDalServerWidgetTests {
    private func widget(_ json: String) throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(Data(json.utf8)))
    }

    /// Inizio di stagione: due giornate della lega (Serie A 4 e 5, la lega parte dalla 4) e le ultime due della stagione prima.
    private let inizioStagione = #"""
    {"giornata": 6, "giornata_lega": 3, "diario": [
      {"giornata": 5, "giornata_lega": 2, "stagione": "2026-27", "attesi": 66, "fatti": 63.5},
      {"giornata": 4, "giornata_lega": 1, "stagione": "2026-27", "attesi": 67, "fatti": 70},
      {"giornata": 38, "giornata_lega": null, "stagione": "2025-26", "attesi": 70, "fatti": 72},
      {"giornata": 37, "giornata_lega": null, "stagione": "2025-26", "attesi": 68, "fatti": 60}]}
    """#

    @Test("Con giornata_lega dal server il widget usa quel numero, anche quando il calcolo locale darebbe altro")
    func usaIlNumeroDelServer() throws {
        // numeri inventati apposta: con lo scarto della giornata attuale (11 → 8) la 10 diventerebbe 7 e la 9 diventerebbe 6
        let w = try widget(#"""
        {"giornata": 11, "giornata_lega": 8, "diario": [
          {"giornata": 10, "giornata_lega": 6, "stagione": "2026-27", "attesi": 66, "fatti": 63.5},
          {"giornata": 9, "giornata_lega": 5, "stagione": "2026-27", "attesi": 67, "fatti": 70}]}
        """#)
        let g = w.giornateGiocate
        #expect(g.map(\.numero) == [6, 5])
        #expect(g.map(\.titolo) == ["Giornata 6 · 10ª di Serie A", "Giornata 5 · 9ª di Serie A"], "la stagione in corso non porta la stagione")
        #expect(g.map(\.sigla) == ["G6", "G5"])
        #expect(g.first?.descrizione == "Giornata 6, 10ª di Serie A: 63,5 punti fatti, 66,0 attesi", "VoiceOver legge i due numeri")
    }

    @Test("Voce di un'altra stagione: numero di Serie A e stagione accanto, come il Diario dell'app e della web")
    func altraStagioneConLaStagione() throws {
        let g = try widget(inizioStagione).giornateGiocate
        #expect(g.map(\.numero) == [2, 1, 38, 37], "dalla più recente, come le manda il server")
        #expect(g.map(\.titolo) == ["Giornata 2 · 5ª di Serie A", "Giornata 1 · 4ª di Serie A",
                                    "38ª giornata di Serie A · 2025-26", "37ª giornata di Serie A · 2025-26"])
        #expect(g.map(\.sigla) == ["G2", "G1", "G38", "G37"], "negli spazi stretti solo il numero")
        #expect(g.dropFirst(2).first?.descrizione == "38ª giornata di Serie A del 2025-26: 72,0 punti fatti, 70,0 attesi",
                "VoiceOver dice anche la stagione")
    }

    @Test("Voce di un'altra stagione con un numero più basso della giornata attuale: resta quello di Serie A")
    func altraStagioneNonPrendeLoScarto() throws {
        // il calcolo locale la crederebbe della stagione in corso (9 ≤ 11) e la scriverebbe «Giornata 6 · 9ª di Serie A»
        let w = try widget(#"""
        {"giornata": 11, "giornata_lega": 8, "diario": [
          {"giornata": 9, "giornata_lega": null, "stagione": "2025-26", "attesi": 70, "fatti": 72}]}
        """#)
        let g = w.giornateGiocate
        #expect(g.map(\.numero) == [9])
        #expect(g.map(\.titolo) == ["9ª giornata di Serie A · 2025-26"])
    }

    @Test("Server vecchio (senza i due campi): i numeri di oggi, senza stagione")
    func serverVecchioIRipieghiDiOggi() throws {
        let w = try widget(#"""
        {"giornata": 11, "giornata_lega": 8, "diario": [
          {"giornata": 10, "attesi": 66, "fatti": 63.5},
          {"giornata": 9, "attesi": 67, "fatti": 70},
          {"giornata": 3, "attesi": 60, "fatti": 61}]}
        """#)
        let g = w.giornateGiocate
        #expect(g.map(\.numero) == [7, 6], "lo scarto della giornata attuale; la giornata prima della lega non c'è")
        #expect(g.map(\.titolo) == ["Giornata 7 · 10ª di Serie A", "Giornata 6 · 9ª di Serie A"])
        #expect(g.map(\.sigla) == ["G7", "G6"])
        #expect(g.first?.descrizione == "Giornata 7, 10ª di Serie A: 63,5 punti fatti, 66,0 attesi")
    }

    @Test("Il grafico va dalla più vecchia alla più recente: la 38 dell'anno prima sta prima della giornata 1")
    func ilGraficoSegueIlTempo() throws {
        let g = try widget(inizioStagione).giornateGiocate
        #expect(PuntiGiornata.perGrafico(g, massimo: 5).map(\.titolo)
                == ["37ª giornata di Serie A · 2025-26", "38ª giornata di Serie A · 2025-26",
                    "Giornata 1 · 4ª di Serie A", "Giornata 2 · 5ª di Serie A"])
        #expect(PuntiGiornata.perGrafico(g, massimo: 3).map(\.sigla) == ["G38", "G1", "G2"], "le più recenti")
        #expect(PuntiGiornata.perGrafico(g, massimo: 0).isEmpty)
    }

    @Test("Campi con la forma sbagliata: la voce resta, i campi si ignorano")
    func campiStraniNonRomponoLaVoce() throws {
        let w = try widget(#"""
        {"giornata": 11, "giornata_lega": 8, "diario": [
          {"giornata": 10, "giornata_lega": "sette", "stagione": 2026, "attesi": 66, "fatti": 63.5}]}
        """#)
        #expect(w.diario?.count == 1)
        #expect(w.giornateGiocate.map(\.titolo) == ["Giornata 7 · 10ª di Serie A"], "senza campi validi vale il ripiego")
    }
}
