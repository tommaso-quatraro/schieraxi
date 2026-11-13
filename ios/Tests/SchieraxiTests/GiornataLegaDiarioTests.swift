import Foundation
import Testing
@testable import Schieraxi

/// Il Diario e il widget «Attesi e fatti» usano il numero della giornata della lega accanto a quello di Serie A, come Oggi e la
/// web («Giornata 8 · 11ª di Serie A», #299).
struct GiornataLegaDiarioTests {
    private func voce(_ json: String) throws -> VoceDiario {
        try Decodifica.decodifica(Data(json.utf8))
    }

    private func widget(_ json: String) throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(Data(json.utf8)))
    }

    @Test("Il Diario mostra il numero della lega e al server manda quello di Serie A")
    func ilDiarioMostraIlNumeroDellaLega() throws {
        let v = try voce(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27"}"#)
        #expect(v.titolo == "Giornata 8 · 11ª di Serie A", "come la web: i due numeri (#299)")
        #expect(v.numero == 8)
        #expect(v.giornata == 11, "al server si manda sempre il numero di Serie A")
    }

    @Test("Senza numero di lega resta quello di Serie A, mai «Giornata 0»")
    func senzaNumeroDiLegaRestaQuelloDiSerieA() throws {
        let v = try voce(#"{"giornata": 11}"#)
        #expect(v.titolo == "11ª giornata di Serie A")
        #expect(v.numero == 11)
        #expect(try voce(#"{"giornata": 11, "giornata_lega": null}"#).numero == 11)
        #expect(try voce("{}").titolo == "Giornata", "mai «Giornata 0»")
    }

    @Test("Widget: le giornate del diario con lo scarto della giornata attuale")
    func ilWidgetRiportaLeGiornateDelDiarioAlNumeroDellaLega() throws {
        // giornata 11 di Serie A = giornata 8 della lega: la lega è partita alla giornata 4 di Serie A
        let w = try widget(#"""
        {"giornata": 11, "giornata_lega": 8, "diario": [
          {"giornata": 10, "attesi": 66, "fatti": 63.5},
          {"giornata": 9, "attesi": 67, "fatti": 70},
          {"giornata": 4, "attesi": 62, "fatti": 58}]}
        """#)
        #expect(w.giornateGiocate.map(\.numero) == [7, 6, 1])
        #expect(w.giornateGiocate.map(\.giornata) == [10, 9, 4], "la giornata di Serie A resta, per «10ª di Serie A»")
        #expect(w.numeroDiLega(11) == 8)
        let senza = try widget(#"{"giornata": 11, "diario": [{"giornata": 10, "attesi": 66, "fatti": 63.5}]}"#)
        #expect(senza.giornateGiocate.map(\.numero) == [10], "senza numero di lega resta quello di Serie A")
        #expect(senza.giornateGiocate.map(\.titolo) == ["10ª giornata di Serie A"])
    }

    @Test("Widget: una giornata giocata prima che la lega partisse non diventa una giornata della lega")
    func unaGiornataPrimaDellaLegaNonSiConfonde() throws {
        // Serie A 3 con la lega partita alla 4: come «3» si scontrerebbe con la vera giornata 3 della lega (Serie A 6)
        let w = try widget(#"""
        {"giornata": 11, "giornata_lega": 8, "diario": [
          {"giornata": 10, "attesi": 66, "fatti": 63.5},
          {"giornata": 6, "attesi": 67, "fatti": 70},
          {"giornata": 3, "attesi": 60, "fatti": 61}]}
        """#)
        #expect(w.giornateGiocate.map(\.numero) == [7, 3])
        #expect(w.numeroDiLega(3) == nil)
    }

    @Test("Widget: a inizio stagione le giornate della stagione prima restano col numero di Serie A")
    func aInizioStagioneLaStagionePrimaRestaDiSerieA() throws {
        // la lega parte alla giornata 4 di Serie A: prima della sua prima giornata il server manda giornata 4 e giornata_lega 1
        let w = try widget(#"""
        {"giornata": 4, "giornata_lega": 1, "diario": [
          {"giornata": 38, "attesi": 70, "fatti": 72},
          {"giornata": 37, "attesi": 68, "fatti": 60},
          {"giornata": 36, "attesi": 69, "fatti": 75},
          {"giornata": 35, "attesi": 71, "fatti": 66},
          {"giornata": 34, "attesi": 70, "fatti": 70}]}
        """#)
        #expect(w.giornateGiocate.map(\.numero) == [38, 37, 36, 35, 34], "non «Giornata 35» al posto della 38")
        #expect(w.giornateGiocate.first?.titolo == "38ª giornata di Serie A", "la stagione prima: solo Serie A")
    }

    @Test("Widget: la stagione in corso viene prima delle giornate dell'anno prima")
    func laStagioneInCorsoVienePrima() throws {
        // dopo due giornate della lega (Serie A 4 e 5) il diario ha ancora le ultime giornate della stagione prima
        let w = try widget(#"""
        {"giornata": 6, "giornata_lega": 3, "diario": [
          {"giornata": 5, "attesi": 66, "fatti": 63.5},
          {"giornata": 4, "attesi": 67, "fatti": 70},
          {"giornata": 38, "attesi": 70, "fatti": 72},
          {"giornata": 37, "attesi": 68, "fatti": 60},
          {"giornata": 36, "attesi": 69, "fatti": 75}]}
        """#)
        #expect(w.giornateGiocate.map(\.numero) == [2, 1, 38, 37, 36],
                "la più recente è la giornata 2 della lega, non la 38 dell'anno prima")
    }

    @Test("«In sintesi»: plurale giusto delle giornate", arguments: zip([1, 4], ["1 giornata", "4 giornate"]))
    func pluraleDelleGiornateInSintesi(numero: Int, testo: String) {
        #expect(Formato.giornate(numero) == testo)
    }
}
