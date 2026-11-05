import SwiftUI
import Testing
@testable import Schieraxi

/// In cima a «Chi schierare?», sotto ogni nome, il posto nella formazione del sistema, come la web (`intest` di `apriConfronto`,
/// issue #311): «Titolare» in una pillola verde, «Panchina 2» e «Non schierato» in una grigia, con le parole di `testoPosto`.
/// Il posto è quello del server (`posto_a` / `posto_b` della risposta del confronto), mai ricalcolato. Lo legge anche VoiceOver.
/// Senza formazione (i due non sono della stessa rosa) niente pillola. Nomi inventati.
@Suite("Posto in formazione sotto i nomi del Confronto")
struct PostoNelDuelloTests {
    private static func giocatore(_ id: Int, _ nome: String) -> String {
        #"""
        {"id": \#(id), "nome": "\#(nome)", "ruolo": "C", "squadra": "genoa", "avversario": "como", "in_casa": true,
         "p_voto": 0.8, "fv_atteso": 6.4, "punti_attesi": 5.12, "indice": 72}
        """#
    }

    /// Una risposta di `/api/confronto` con i due giocatori e, se c'è, la formazione del sistema.
    private static func confronto(formazione: String?) throws -> Confronto {
        let f = formazione.map { #", "formazione": \#($0)"# } ?? ""
        let json = #"""
        {"giornata": 9, "giocatori": [\#(giocatore(1, "Aldo Pinarotti")), \#(giocatore(2, "Bruno Castelmare"))],
         "consigliato": 1, "fattori": []\#(f)}
        """#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    // MARK: il posto dal server

    @Test("Il posto di ognuno dei due dalla risposta del server: `posto_a` per il primo, `posto_b` per il secondo")
    func postoDeiDue() throws {
        let c = try Self.confronto(formazione: #"{"modulo": "4-3-3", "posto_a": "panchina 2", "posto_b": "titolare", "testo": "Prova."}"#)
        try #require(c.giocatori.count == 2)
        #expect(c.codicePosto(di: c.giocatori[0]) == "panchina 2")
        #expect(c.codicePosto(di: c.giocatori[1]) == "titolare")
    }

    @Test("Senza formazione (i due non sono della stessa rosa) nessun posto")
    func senzaFormazione() throws {
        let c = try Self.confronto(formazione: nil)
        try #require(c.giocatori.count == 2)
        #expect(c.codicePosto(di: c.giocatori[0]) == nil)
        #expect(c.codicePosto(di: c.giocatori[1]) == nil)
    }

    // MARK: la pillola

    @Test("Le parole di `testoPosto`, come la web: «Titolare», «Panchina 2», «Non schierato»")
    func paroleComeLaWeb() throws {
        let web = try TestiWeb()
        let titolare = try web.italiano("mercato.posto_titolare")
        let panchina = try web.italiano("mercato.panchina_n").replacingOccurrences(of: "{n}", with: "2")
        let fuori = try web.italiano("mercato.posto_fuori")
        #expect(ColonnaDuello.etichettaPosto("titolare")?.testo == titolare)
        #expect(ColonnaDuello.etichettaPosto("panchina 2")?.testo == panchina)
        #expect(ColonnaDuello.etichettaPosto("fuori")?.testo == fuori)
    }

    @Test("«Titolare» nella pillola verde, gli altri posti in quella grigia (`etichetta` ed `etichetta neutra` della web)")
    func coloriComeLaWeb() {
        #expect(ColonnaDuello.etichettaPosto("titolare")?.tono == .positivo)
        #expect(ColonnaDuello.etichettaPosto("panchina 2")?.tono == .neutro)
        #expect(ColonnaDuello.etichettaPosto("fuori")?.tono == .neutro)
    }

    @Test("Senza posto o con un codice che non conosce: niente pillola", arguments: [nil, "", "strano"] as [String?])
    func nientePillola(codice: String?) {
        #expect(ColonnaDuello.etichettaPosto(codice) == nil)
    }

    // MARK: sullo schermo e a voce

    @MainActor
    @Test("VoiceOver legge il posto subito dopo il nome e il ruolo")
    func vocePerVoiceOver() throws {
        let c = try Self.confronto(formazione: nil)
        try #require(c.giocatori.count == 2)
        let conPosto = ColonnaDuello(g: c.giocatori[0], scelto: true, posto: "panchina 2").voce
        #expect(conPosto.hasPrefix("Aldo Pinarotti, centrocampista, Panchina 2, indice 72, "))
        #expect(conPosto.hasSuffix(", consigliato"))
        let senzaPosto = ColonnaDuello(g: c.giocatori[1], scelto: false, posto: nil).voce
        #expect(senzaPosto.hasPrefix("Bruno Castelmare, centrocampista, indice 72, "))
    }

    /// L'altezza della colonna larga quanto metà riga di un iPhone (390 punti: margini, «VS» e due colonne).
    @MainActor
    private static func altezza(_ colonna: ColonnaDuello) -> CGFloat {
        let disegno = ImageRenderer(content: colonna)
        disegno.proposedSize = ProposedViewSize(width: 160, height: nil)
        disegno.scale = 1
        return disegno.uiImage?.size.height ?? 0
    }

    @MainActor
    @Test("La pillola si vede: con il posto la colonna cresce di una riga, senza posto resta com'era")
    func pillolaSiVede() throws {
        let c = try Self.confronto(formazione: nil)
        try #require(c.giocatori.count == 2)
        let g = c.giocatori[0]
        let senza = Self.altezza(ColonnaDuello(g: g, scelto: false, posto: nil))
        let con = Self.altezza(ColonnaDuello(g: g, scelto: false, posto: "titolare"))
        let ignoto = Self.altezza(ColonnaDuello(g: g, scelto: false, posto: "strano"))
        #expect(senza > 0)
        #expect(con - senza >= 12, "la pillola del posto non c'è: \(con) contro \(senza)")
        #expect(ignoto == senza, "un codice che non si conosce non lascia una pillola vuota")
    }
}
