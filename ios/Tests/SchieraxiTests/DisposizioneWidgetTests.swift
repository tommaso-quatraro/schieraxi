import SwiftUI
import Testing
@testable import Schieraxi

/// Le scelte di disposizione dei widget che cambiano con il testo grande (Dynamic Type): misure fisse, quindi meno righe.
@Suite("Disposizione dei widget con il testo grande")
struct DisposizioneWidgetTests {
    @Test("Prossima giornata, misura media: due giocatori da controllare, uno solo dal testo più grande del normale")
    func righeDubbi() {
        #expect(DisposizioneWidget.righeDubbi(.xSmall) == 2)
        #expect(DisposizioneWidget.righeDubbi(.large) == 2)
        #expect(DisposizioneWidget.righeDubbi(.xLarge) == 1)
        #expect(DisposizioneWidget.righeDubbi(.xxLarge) == 1)
        #expect(DisposizioneWidget.righeDubbi(.accessibility3) == 1)
    }

    @Test("Cruscotto in linea (Schermata di blocco): con il testo grande via il modulo, mai «2 da contr…»")
    func rigaInLinea() {
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 2, testo: .large) == "3-4-3 · 2 da controllare")
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 0, testo: .large) == "3-4-3 · titolari a posto")
        #expect(DisposizioneWidget.rigaInLinea(modulo: nil, dubbi: 1, testo: .large) == "— · 1 da controllare")
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 2, testo: .xLarge) == "2 da controllare")
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 0, testo: .accessibility3) == "titolari a posto")
    }

    // MARK: Cruscotto grande ed extra large (#249): il widget tiene la prima prova che entra, niente esce dal bordo

    private typealias Prova = DisposizioneWidget.ProvaCruscotto

    @Test("Cruscotto prima della scadenza: via la prossima partita, poi la forma compatta, poi il grafico, infine un dubbio solo")
    func proveCruscottoPrimaDellaScadenza() {
        #expect(DisposizioneWidget.proveCruscotto(partitePrima: false, dubbi: 2) == [
            Prova(dubbi: 2),
            Prova(partite: false, dubbi: 2),
            Prova(partite: false, compatto: true, dubbi: 2),
            Prova(partite: false, compatto: true, grafico: false, dubbi: 2),
            Prova(partite: false, compatto: true, grafico: false, dubbi: 1),
        ])
    }

    @Test("Durante le partite (o a formazione chiusa) il blocco delle partite resta in ogni prova")
    func proveCruscottoConLePartite() {
        let prove = DisposizioneWidget.proveCruscotto(partitePrima: true, dubbi: 3)
        // con una chiusura, non con `\.partite`: dentro #expect il percorso come funzione fa credere che la chiamata lanci errori
        #expect(prove.allSatisfy { $0.partite })
        #expect(prove == [
            Prova(dubbi: 3),
            Prova(compatto: true, dubbi: 3),
            Prova(compatto: true, grafico: false, dubbi: 3),
            Prova(compatto: true, grafico: false, dubbi: 1),
        ])
    }

    @Test("Cruscotto: la prima prova è quella completa, al più sei prove, mai dubbi sotto zero", arguments: [true, false])
    func proveCruscottoLimiti(partitePrima: Bool) {
        for dubbi in [-3, 0, 1, 2, 3, 6] {
            let prove = DisposizioneWidget.proveCruscotto(partitePrima: partitePrima, dubbi: dubbi)
            #expect(prove.first == Prova(dubbi: max(dubbi, 0)))
            #expect((1...6).contains(prove.count))
            #expect(prove.allSatisfy { $0.dubbi >= 0 })
        }
        // con un dubbio solo, o nessuno, non c'è la prova con un dubbio solo
        #expect(DisposizioneWidget.proveCruscotto(partitePrima: partitePrima, dubbi: 1).allSatisfy { $0.dubbi == 1 })
        #expect(DisposizioneWidget.proveCruscotto(partitePrima: partitePrima, dubbi: -3).allSatisfy { $0.dubbi == 0 })
    }

    @Test("Le partite vengono prima di tutto se ce n'è una in gioco o la formazione è chiusa, non prima della scadenza")
    func partiteInPrimoPiano() throws {
        func riassunto(_ corpo: String) throws -> RiassuntoWidget { try #require(RiassuntoWidget.leggi(Data(corpo.utf8))) }
        let prima = try riassunto(#"""
        {"giornata": 11, "live": {"partite": [{"casa": "lazio", "trasferta": "juve", "data": "2026-10-31 20:45", "stato": "da_giocare"}]}}
        """#)
        #expect(prima.partiteInPrimoPiano == false)
        let inGioco = try riassunto(#"""
        {"giornata": 11, "live": {"partite": [{"casa": "inter", "trasferta": "roma", "data": "2026-10-31 15:00",
          "stato": "secondo_tempo", "minuto": "63'", "gol_casa": 2, "gol_trasferta": 0}]}}
        """#)
        #expect(inGioco.partiteInPrimoPiano)
        #expect(try riassunto(#"{"giornata": 11, "fase": "in_corso"}"#).partiteInPrimoPiano)
        #expect(try riassunto(#"{"giornata": 12, "fase": "finita"}"#).partiteInPrimoPiano == false)
        #expect(try riassunto(#"{"giornata": 11}"#).partiteInPrimoPiano == false)
    }
}
