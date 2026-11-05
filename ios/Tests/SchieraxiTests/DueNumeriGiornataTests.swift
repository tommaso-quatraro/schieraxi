import Foundation
import Testing
@testable import Schieraxi

/// Issue #299: ogni giornata con i due numeri, come su Leghe e come la web. Dove c'è spazio «Giornata 8 · 11ª di Serie A»;
/// dove si parla solo di Serie A (stagioni passate, `giornata_lega` null, server vecchio) «11ª giornata di Serie A».
/// Una sola regola (`TempiLega`) per tutte le schermate e i widget. Dati inventati: la lega parte dalla 4ª di Serie A.
@Suite("Giornata della lega e di Serie A (#299)")
struct DueNumeriGiornataTests {

    struct Caso: Sendable, CustomTestStringConvertible {
        let serieA: Int
        let lega: Int?
        let atteso: String
        var testDescription: String { atteso }
    }

    @Test("La forma intera dice i due numeri; senza il numero della lega solo quello di Serie A", arguments: [
        Caso(serieA: 11, lega: 8, atteso: "Giornata 8 · 11ª di Serie A"),
        Caso(serieA: 10, lega: 7, atteso: "Giornata 7 · 10ª di Serie A"),
        // lega partita con il campionato: i due numeri coincidono e si scrivono tutti e due, come sempre
        Caso(serieA: 3, lega: 3, atteso: "Giornata 3 · 3ª di Serie A"),
        // stagione passata, prima che la lega parta o server vecchio: solo Serie A, mai un numero della lega inventato
        Caso(serieA: 11, lega: nil, atteso: "11ª giornata di Serie A"),
        Caso(serieA: 11, lega: 0, atteso: "11ª giornata di Serie A"),
        Caso(serieA: 11, lega: -2, atteso: "11ª giornata di Serie A"),
    ])
    func formaIntera(_ caso: Caso) {
        #expect(TempiLega.etichetta(serieA: caso.serieA, lega: caso.lega) == caso.atteso)
    }

    @Test("Dove si parla solo del calendario di Serie A: «11ª giornata di Serie A»")
    func soloSerieA() {
        #expect(TempiLega.serieA(11) == "11ª giornata di Serie A")
        #expect(TempiLega.serieA(1) == "1ª giornata di Serie A")
    }

    @Test("Oggi: la testata dice i due numeri")
    func oggi() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11, "giornata_lega": 8}"#.utf8))
        #expect(o.etichettaGiornata == "Giornata 8 · 11ª di Serie A")
        let vecchio: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11}"#.utf8))
        #expect(vecchio.etichettaGiornata == "11ª giornata di Serie A", "server senza `giornata_lega`")
    }

    @Test("Formazione: intestazione e testo da condividere con i due numeri")
    func formazione() throws {
        let f: Formazione = try Fixture.decodifica("formazione")
        #expect(f.etichettaGiornata == "\(f.giornata)ª giornata di Serie A", "la fixture non ha `giornata_lega`")
        let testo = TestoFormazione.crea(giornata: 11, giornataLega: 8, modulo: "4-3-3", titolari: [], panchina: [])
        #expect(testo.components(separatedBy: "\n").first == "Giornata 8 · 11ª di Serie A · 4-3-3")
    }

    @Test("Diario e «Le tue scelte»: stagione in corso con i due numeri, stagione passata solo Serie A")
    func diario() throws {
        let v: VoceDiario = try Decodifica.decodifica(Data(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27"}"#.utf8))
        #expect(v.titolo == "Giornata 8 · 11ª di Serie A")
        #expect(v.giornata == 11, "al server si manda sempre il numero di Serie A")
        let passata: VoceDiario = try Decodifica.decodifica(Data(#"{"giornata": 38, "giornata_lega": null, "stagione": "2025-26"}"#.utf8))
        #expect(passata.titolo == "38ª giornata di Serie A")
        let s: SceltaGiornata = try Decodifica.decodifica(Data(#"{"stagione": "2026-27", "giornata": 9, "giornata_lega": 6}"#.utf8))
        #expect(s.titolo == "Giornata 6 · 9ª di Serie A")
    }

    @Test("Giornata finita in Oggi: «Giornata 8 · 11ª di Serie A, con la tua formazione»")
    func giornataFinita() {
        #expect(TestiFase.giornata(serieA: 11, lega: 8) == "Giornata 8 · 11ª di Serie A")
        #expect(TestiFase.giornata(serieA: 11, lega: nil) == "11ª giornata di Serie A")
        #expect(TestiFase.giornata(serieA: nil, lega: 8) == nil, "senza Serie A non si inventa niente")
    }

    @Test("Widget: la forma intera dove c'è spazio, «G8» negli spazi strettissimi")
    func widget() throws {
        let w = try #require(RiassuntoWidget.leggi(Data(#"{"giornata": 11, "giornata_lega": 8}"#.utf8)))
        #expect(w.etichettaGiornata == "Giornata 8 · 11ª di Serie A")
        #expect(w.siglaGiornata == "G8")
        #expect(w.comeRiassuntoOggi()?.etichettaGiornata == "Giornata 8 · 11ª di Serie A")
    }

    @Test("Widget «Attesi e fatti»: le voci del diario con i due numeri, quelle di un'altra stagione solo Serie A")
    func widgetDiario() throws {
        let w = try #require(RiassuntoWidget.leggi(Data(#"""
        {"giornata": 6, "giornata_lega": 3, "diario": [
          {"giornata": 5, "giornata_lega": 2, "stagione": "2026-27", "attesi": 66, "fatti": 63.5},
          {"giornata": 38, "giornata_lega": null, "stagione": "2025-26", "attesi": 70, "fatti": 72}]}
        """#.utf8)))
        let g = w.giornateGiocate
        #expect(g.map(\.titolo) == ["Giornata 2 · 5ª di Serie A", "38ª giornata di Serie A · 2025-26"])
        #expect(g.map(\.sigla) == ["G2", "G38"])
    }
}
