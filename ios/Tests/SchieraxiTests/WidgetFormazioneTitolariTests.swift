import Foundation
import Testing
@testable import Schieraxi

/// Il widget «Formazione» (misura extra large, iPad): accanto a ogni titolare lo stesso numero degli elenchi dei titolari
/// nell'app, il fantavoto atteso (`fv_atteso`), con il suo nome sopra la colonna dove c'è spazio e sempre per VoiceOver (#240).
/// Da un server senza `fv_atteso` restano i punti attesi di prima, con il loro nome: mai «Fantavoto atteso» sopra un altro
/// numero. Dati inventati.
@Suite("Widget «Formazione»: il numero accanto ai titolari")
struct WidgetFormazioneTitolariTests {
    /// Due titolari senza la graffa finale: ogni test aggiunge i campi che vuole (o solo «}»).
    private static let marteni = #"{"id": 120, "nome": "Leonel Marténi", "ruolo": "A", "p_voto": 0.62, "punti_attesi": 4.71"#
    private static let bastrani = #"{"id": 3, "nome": "Alvise Bastrani", "ruolo": "D", "p_voto": 0.97, "punti_attesi": 5.84"#

    /// La formazione del widget con quei titolari, letta come la legge il widget.
    private func formazione(_ titolari: [String]) throws -> FormazioneWidget {
        let elenco = titolari.joined(separator: ", ")
        let json = #"{"giornata": 11, "formazione": {"modulo": "3-4-3", "punti_attesi": 73.7, "titolari": [\#(elenco)]}}"#
        return try #require(RiassuntoWidget.leggi(Data(json.utf8))?.formazione)
    }

    @Test("Con `fv_atteso` il numero è il fantavoto atteso, con il nome dell'app e della web")
    func fantavotoAtteso() throws {
        let f = try formazione([Self.marteni + #", "fv_atteso": 7.62}"#, Self.bastrani + #", "fv_atteso": 6.04}"#])
        let tit = try #require(f.titolari)
        #expect(tit.map(f.numeroTitolare) == ["7,6", "6,0"])
        let nomeWeb = try TestiWeb().italiano("mercato.fantavoto_atteso")      // «Fantavoto atteso»
        #expect(FantavotoAtteso.nome == nomeWeb)
        #expect(f.nomeNumeroTitolari == [FantavotoAtteso.nome, ""])            // se il nome non entra, solo i numeri
        #expect(f.voceTitolare(tit[0]) == "Leonel Marténi, fantavoto atteso 7,6")
    }

    @Test("Senza `fv_atteso` per tutti (server vecchio): i punti attesi di prima, con il loro nome", arguments: [
        ("}", "}"),
        (#", "fv_atteso": null}"#, #", "fv_atteso": null}"#),
        (#", "fv_atteso": 7.62}"#, "}"),        // uno solo senza: tutta la colonna resta sui punti attesi
    ])
    func puntiAttesiDaServerVecchio(fineMarteni: String, fineBastrani: String) throws {
        let f = try formazione([Self.marteni + fineMarteni, Self.bastrani + fineBastrani])
        let tit = try #require(f.titolari)
        #expect(tit.map(f.numeroTitolare) == ["4,7", "5,8"])
        #expect(f.nomeNumeroTitolari == ["Punti attesi", ""])
        #expect(f.voceTitolare(tit[0]) == "Leonel Marténi, punti attesi 4,7")
        let testi = f.nomeNumeroTitolari + tit.map(f.voceTitolare)
        #expect(testi.allSatisfy { !$0.localizedCaseInsensitiveContains("fantavoto") })
    }
}
