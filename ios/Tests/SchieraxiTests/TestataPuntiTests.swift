import Testing
@testable import Schieraxi

/// Issue #352: la testata del widget «Attesi e fatti» (piccolo e medio) non taglia mai una scritta. La vista prova le
/// disposizioni nell'ordine di `formeTestata` e tiene la prima che entra: prima il titolo con «Giornata 7», poi, se con il testo
/// grande non entrano insieme, il solo simbolo (il titolo si perde, la giornata no). Mai «G7» (#299).
@Suite("Testata del widget «Attesi e fatti» (#352)")
struct TestataPuntiTests {

    @Test("Prima il titolo con «Giornata 7», poi il solo simbolo con «Giornata 7»")
    func ordine() {
        let g = PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66, fatti: 63.5)
        #expect(g.formeTestata == [
            PuntiGiornata.FormaTestata(conTitolo: true, giornata: "Giornata 7"),
            PuntiGiornata.FormaTestata(conTitolo: false, giornata: "Giornata 7"),
        ])
    }

    @Test("Il titolo ha la precedenza sulla forma lunga della giornata; la giornata non sparisce mai")
    func titoloPrimaDelSimbolo() {
        let g = PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66, fatti: 63.5)
        let forme = g.formeTestata
        let primaSenzaTitolo = forme.firstIndex { !$0.conTitolo }
        #expect(primaSenzaTitolo == forme.count / 2, "tutte le disposizioni con il titolo vengono prima di quelle senza")
        #expect(forme.allSatisfy { !$0.giornata.isEmpty }, "ogni disposizione ha la giornata")
        #expect(forme.last?.giornata == "Giornata 7", "l'ultimo ripiego è «Giornata 7»")
        #expect(!forme.contains { $0.giornata == g.sigla }, "mai «\(g.sigla)»")
    }

    @Test("Senza il numero della lega: «10ª di Serie A», mai «G10» né un numero della lega inventato")
    func senzaNumeroDellaLega() {
        let g = PuntiGiornata(giornata: 10, attesi: 66, fatti: 63.5)
        #expect(g.formeTestata.map(\.giornata) == ["10ª di Serie A", "10ª di Serie A"])
        #expect(g.formeTestata.map(\.conTitolo) == [true, false])
    }
}
