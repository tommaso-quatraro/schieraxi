import Foundation
import Testing
@testable import Schieraxi

/// La frase breve del widget medio (#911): a giornata in corso, con chi aspetta il recupero, `/api/widget` manda anche
/// `in_corso.situazione_breve` («3 giocatori aspettano il recupero; mancano i voti ufficiali.»), che nel medio sta intera al posto
/// della riga con i nomi. Facoltativa: senza (server di prima, riassunto da `/api/oggi`, riassunto salvato da una versione di prima)
/// resta la riga di sempre. VoiceOver legge sempre la riga intera, con i nomi. Dati inventati.
@Suite("Widget medio: la frase breve del server sul recupero (#911)")
struct WidgetFraseBreveTests {
    static let lunga = "Hanno giocato tutti tranne Glauco Brevisi, Teo Kloosmeijer e Cesare Pulinski, che aspettano il recupero; mancano anche i voti ufficiali."
    static let breve = "3 giocatori aspettano il recupero; mancano i voti ufficiali."

    /// `/api/widget` a giornata in corso con la riga lunga e `extra` (JSON) in più dentro `in_corso`.
    static func widget(_ extra: String = "") throws -> RiassuntoWidget {
        let corpo = #"""
        {"giornata": 11, "giornata_lega": 8, "fase": "in_corso", "scadenza": "2026-11-21 14:30",
         "formazione": {"modulo": "3-4-3", "punti_attesi": 73.7},
         "in_corso": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 61.5, "punti_previsti": 66, "ancora_da_giocare": 0,
                      "situazione": "\#(Self.lunga)",
                      "situazione_frase": {"chiave": "in_corso.voti_e_recupero", "param": {"n": 3}}\#(extra)}}
        """#
        return try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
    }

    static let conBreve = #", "situazione_breve": "\#(WidgetFraseBreveTests.breve)", "situazione_breve_frase": {"chiave": "in_corso.voti_e_recupero_breve", "param": {"n": 3}}"#

    @Test("Con la frase breve il medio mostra quella; VoiceOver e il resto la riga intera con i nomi")
    func conLaBreve() throws {
        let w = try Self.widget(Self.conBreve)
        #expect(w.faseGiornata.inCorso?.situazioneBreve == Self.breve)
        let r = try #require(w.comeRiassuntoOggi())
        #expect(r.fraseDelMedio == Self.breve)
        #expect(r.ancoraDaGiocareTesto == Self.lunga, "la riga di sempre resta")
        #expect(r.descrizioneFase?.hasSuffix(Self.lunga) == true, "VoiceOver legge la riga intera, con i nomi")
    }

    @Test("Senza la frase breve (server di prima o riga già corta) il medio mostra la riga di sempre")
    func senzaLaBreve() throws {
        let r = try #require(try Self.widget().comeRiassuntoOggi())
        #expect(r.situazioneBreve == nil)
        #expect(r.fraseDelMedio == Self.lunga)
    }

    @Test("Una frase breve vuota o con la forma sbagliata non conta, e il resto si legge", arguments: [
        #""situazione_breve": "   ""#, #""situazione_breve": 3"#, #""situazione_breve": null"#, #""situazione_breve": {"testo": "x"}"#,
    ])
    func breveStrana(campo: String) throws {
        let r = try #require(try Self.widget(", " + campo).comeRiassuntoOggi())
        #expect(r.fraseDelMedio == Self.lunga)
        #expect(r.puntiFatti == 61.5)
        #expect(r.inCorso)
    }

    @Test("La copia salvata tiene la frase breve; un riassunto salvato senza (versione di prima) si legge con la riga di sempre")
    func copiaSalvata() throws {
        let r = try #require(try Self.widget(Self.conBreve).comeRiassuntoOggi())
        let salvato = try JSONDecoder().decode(RiassuntoOggi.self, from: JSONEncoder().encode(r))
        #expect(salvato.fraseDelMedio == Self.breve)
        var vecchio = try JSONSerialization.jsonObject(with: JSONEncoder().encode(r)) as? [String: Any] ?? [:]
        let tolta = vecchio.removeValue(forKey: "situazioneBreve") as? String
        #expect(tolta == Self.breve, "la copia salvata la scrive con questo nome")
        let letto = try JSONDecoder().decode(RiassuntoOggi.self, from: JSONSerialization.data(withJSONObject: vecchio))
        #expect(letto.situazioneBreve == nil)
        #expect(letto.fraseDelMedio == Self.lunga)
    }

    @Test("Dal riassunto di `/api/oggi` (senza la frase breve) la riga di sempre")
    func daOggi() throws {
        let r = RiassuntoOggi(oggi: try BordiGiornataComeLaWebTests.oggiInCorso(situazione: "\"\(Self.lunga)\""))
        #expect(r.situazioneBreve == nil)
        #expect(r.fraseDelMedio == Self.lunga)
    }
}
