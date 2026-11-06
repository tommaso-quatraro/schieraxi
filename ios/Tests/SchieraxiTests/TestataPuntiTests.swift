import Testing
@testable import Schieraxi

/// Issue #352: la testata del widget «Attesi e fatti» (piccolo e medio) non taglia mai una scritta. La vista prova le
/// disposizioni nell'ordine di `formeTestata` e tiene la prima che entra: prima il titolo con la giornata sempre più corta,
/// poi, se con il testo grande non entra nemmeno «G7» accanto al titolo, il solo simbolo (il titolo si perde, la giornata no).
@Suite("Testata del widget «Attesi e fatti» (#352)")
struct TestataPuntiTests {

    @Test("Prima il titolo con «Giornata 7» e «G7», poi il solo simbolo con le stesse due forme")
    func ordine() {
        let g = PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66, fatti: 63.5)
        #expect(g.formeTestata == [
            PuntiGiornata.FormaTestata(conTitolo: true, giornata: "Giornata 7"),
            PuntiGiornata.FormaTestata(conTitolo: true, giornata: "G7"),
            PuntiGiornata.FormaTestata(conTitolo: false, giornata: "Giornata 7"),
            PuntiGiornata.FormaTestata(conTitolo: false, giornata: "G7"),
        ])
    }

    @Test("Il titolo ha la precedenza sulla forma lunga della giornata; la giornata non sparisce mai")
    func titoloPrimaDelSimbolo() {
        let g = PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66, fatti: 63.5)
        let forme = g.formeTestata
        let primaSenzaTitolo = forme.firstIndex { !$0.conTitolo }
        #expect(primaSenzaTitolo == forme.count / 2, "tutte le disposizioni con il titolo vengono prima di quelle senza")
        #expect(forme.allSatisfy { !$0.giornata.isEmpty }, "ogni disposizione ha la giornata")
        #expect(forme.last?.giornata == g.sigla, "l'ultimo ripiego è la sigla, la forma più corta")
    }

    @Test("Senza il numero della lega: «10ª di Serie A», poi «G10», mai un numero della lega inventato")
    func senzaNumeroDellaLega() {
        let g = PuntiGiornata(giornata: 10, attesi: 66, fatti: 63.5)
        #expect(g.formeTestata.map(\.giornata) == ["10ª di Serie A", "G10", "10ª di Serie A", "G10"])
        #expect(g.formeTestata.map(\.conTitolo) == [true, true, false, false])
    }
}
