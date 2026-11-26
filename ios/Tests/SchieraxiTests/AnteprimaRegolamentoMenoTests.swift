import Foundation
import Testing
@testable import Schieraxi

// L'anteprima del regolamento incollato scriveva «Ammonizione: -0,5» con il trattino corto, mentre il resto dell'app scrive i
// numeri negativi con il meno tipografico «−» (U+2212): `Formato.conSegno`, `CampiRegole.cifra`, la frase dei punteggi comuni
// «ammonizione −0,5» (#911). Il valore è un numero del server: l'app sceglie solo come scriverlo. La riga incollata resta com'è.

@Suite("Regole: il meno tipografico nell'anteprima del regolamento (#911)")
struct AnteprimaRegolamentoMenoTests {
    @Test("«Ammonizione: −0,5» con il meno lungo; la riga incollata resta com'è")
    func ammonizione() throws {
        let esito: RiconoscimentoRegole = try Decodifica.decodifica(Data(#"""
            {"modifiche": [{"chiave": "bonus.ammonizione", "etichetta": "Ammonizione", "valore": -0.5, "riga": "Ammonizione: -0.5"}],
             "non_applicabili": [{"chiave": "malus.autogol", "etichetta": "Autogol", "valore": -2, "riga": "Autogol: -2",
                                  "motivo": "Fuori dai limiti."}]}
            """#.utf8))
        let anteprima = AnteprimaRegolamento(esito)
        #expect(anteprima.riconosciuti.map(\.testo) == ["Ammonizione: \u{2212}0,5"])
        #expect(anteprima.riconosciuti.first?.daRiga == "da: «Ammonizione: -0.5»", "la riga incollata è dell'utente: non si tocca")
        #expect(anteprima.nonApplicati.map(\.testo) == ["Autogol: \u{2212}2"])
    }

    @Test("I numeri negativi con «−», i positivi e lo zero senza segno", arguments: [
        (-0.5, "\u{2212}0,5"), (-1.0, "\u{2212}1"), (-0.25, "\u{2212}0,25"), (-1.5, "\u{2212}1,5"),
        (0.5, "0,5"), (3.0, "3"), (0.0, "0"),
    ])
    func decimali(valore: Double, testo: String) {
        #expect(RegoleLogica.descrivi(.decimale(valore)) == testo)
        #expect(!RegoleLogica.descrivi(.decimale(valore)).contains("-"), "mai il trattino corto")
    }

    @Test("Gli interi negativi con «−»", arguments: [(-2, "\u{2212}2"), (-10, "\u{2212}10"), (0, "0"), (7, "7")])
    func interi(valore: Int, testo: String) {
        #expect(RegoleLogica.descrivi(.intero(valore)) == testo)
    }

    @Test("Dentro un elenco, come ogni altro valore")
    func elenco() {
        #expect(RegoleLogica.descrivi(.lista([.decimale(-0.5), .intero(-1)])) == "\u{2212}0,5, \u{2212}1")
    }

    @Test("Un numero così piccolo che arrotondato vale zero resta senza segno, come «0,0» di `Formato.conSegno`")
    func quasiZero() {
        #expect(RegoleLogica.descrivi(.decimale(-0.001)) == "0,00")
    }
}
