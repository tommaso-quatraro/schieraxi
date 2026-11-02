import Foundation
import Testing
@testable import Schieraxi

/// Il riassunto per il widget «Da controllare»: chi della formazione va guardato, e con quali parole. Le parole sono quelle
/// del server, della web e dell'app («In dubbio · gioca 55%», `docs/COERENZA-WEB-IPHONE.md`): se il server manda
/// `etichetta.testo` si usa quello, altrimenti lo stesso testo calcolato qui.
@Suite("Widget «Da controllare»")
struct DubbiWidgetTests {
    /// Il riassunto di una risposta di «oggi» con questi avvisi (oggetti JSON).
    private func riassunto(_ avvisi: String...) throws -> RiassuntoOggi {
        let corpo = #"{"giornata": 11, "avvisi": [\#(avvisi.joined(separator: ","))]}"#
        let oggi: Oggi = try Decodifica.decodifica(Data(corpo.utf8))
        return RiassuntoOggi(oggi: oggi)
    }

    /// Un dubbio in formazione con questo pezzo di JSON in più (`p_voto`, `etichetta`...).
    private func dubbio(_ altro: String) throws -> DubbioRiassunto {
        let r = try riassunto(#"{"id": 5, "nome": "Leonel Marteni", "ruolo": "A", "tipo": "dubbio", "in_formazione": true, \#(altro)}"#)
        return try #require(r.dubbi?.first)
    }

    @Test("Dagli avvisi di Oggi vengono i dubbi della formazione")
    func dagliAvvisiDiOggi() throws {
        let r = try riassunto(
            #"{"id": 5, "nome": "Leonel Marteni", "ruolo": "A", "squadra": "inter", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.55}"#,
            #"{"id": 6, "nome": "Bastrani", "ruolo": "D", "tipo": "diffidato", "in_formazione": true}"#,
            #"{"id": 7, "nome": "Riserva", "ruolo": "C", "tipo": "infortunato", "in_formazione": false}"#
        )
        #expect(r.daControllare == 2)
        #expect(r.dubbi?.map(\.id) == [5, 6])
        #expect(r.dubbi?.first?.descrizione == "In dubbio · gioca 55%")
        #expect(r.dubbi?.last?.descrizione == "Diffidato")
    }

    @Test("Al massimo sei dubbi nel riassunto, ma il conto è di tutti")
    func alMassimoSei() throws {
        let avvisi = (1...9).map { #"{"id": \#($0), "nome": "G\#($0)", "tipo": "dubbio", "in_formazione": true}"# }
        let corpo = #"{"giornata": 1, "avvisi": [\#(avvisi.joined(separator: ","))]}"#
        let oggi: Oggi = try Decodifica.decodifica(Data(corpo.utf8))
        let r = RiassuntoOggi(oggi: oggi)
        #expect(r.daControllare == 9)
        #expect(r.dubbi?.count == 6)
    }

    @Test("Un riassunto salvato da una versione vecchia, senza dubbi, si legge")
    func riassuntoVecchioSenzaDubbi() throws {
        let vecchio = #"{"giornata": 9, "daControllare": 2, "scaricatoIl": 783000000}"#
        let r = try JSONDecoder().decode(RiassuntoOggi.self, from: Data(vecchio.utf8))
        #expect(r.dubbi == nil)
        #expect(r.daControllare == 2)
    }

    @Test("Un riassunto salvato senza etichetta scrive le parole giuste")
    func riassuntoVecchioSenzaEtichetta() throws {
        let vecchio = #"{"giornata": 9, "daControllare": 1, "scaricatoIl": 783000000, "dubbi": [{"id": 5, "nome": "A", "tipo": "dubbio", "pVoto": 0.55}]}"#
        let r = try JSONDecoder().decode(RiassuntoOggi.self, from: Data(vecchio.utf8))
        #expect(r.dubbi?.first?.descrizione == "In dubbio · gioca 55%")
    }

    @Test("Senza tipo: «Da controllare»")
    func senzaTipo() {
        #expect(DubbioRiassunto(id: 1, nome: "A", ruolo: nil, tipo: nil, pVoto: nil).descrizione == "Da controllare")
    }

    @Test("Il testo dell'etichetta del server vince sul testo calcolato")
    func etichettaDelServer() throws {
        let d = try dubbio(#""p_voto": 0.55, "etichetta": {"codice": "in_dubbio", "testo": "Doubtful · plays 55%", "tono": "attenzione"}"#)
        #expect(d.descrizione == "Doubtful · plays 55%")
    }

    @Test("L'etichetta del server resta nella copia salvata per il widget")
    func etichettaNellaCopia() throws {
        let r = try riassunto(#"{"id": 5, "nome": "A", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.55, "etichetta": {"codice": "in_dubbio", "testo": "Doubtful · plays 55%", "tono": "attenzione"}}"#)
        let copia = try JSONDecoder().decode(RiassuntoOggi.self, from: JSONEncoder().encode(r))
        #expect(copia.dubbi?.first?.descrizione == "Doubtful · plays 55%")
    }

    @Test("Un'etichetta nulla, vuota o con una forma strana non rompe Oggi: vale il testo calcolato", arguments: [
        #""etichetta": null"#,
        #""etichetta": "In dubbio""#,
        #""etichetta": 3"#,
        #""etichetta": {"codice": "in_dubbio"}"#,
        #""etichetta": {"testo": "  "}"#,
        #""etichetta": {"testo": 7, "codice": ["x"]}"#,
    ])
    func etichettaStrana(campo: String) throws {
        let d = try dubbio(#""p_voto": 0.55, \#(campo)"#)
        #expect(d.descrizione == "In dubbio · gioca 55%")
    }

    @Test("«gioca N%» solo con una probabilità vera: mai «gioca 100%» né «gioca 0%» per un dubbio", arguments: [
        ("0.55", "In dubbio · gioca 55%"),
        ("1.0", "In dubbio"),
        ("0", "In dubbio"),
        ("null", "In dubbio"),
    ])
    func percentualeDelDubbio(pVoto: String, attesa: String) throws {
        let d = try dubbio(#""p_voto": \#(pVoto)"#)
        #expect(d.descrizione == attesa)
    }

    @Test("Assenze e diffida senza percentuale, come le scrive il server", arguments: [
        ("infortunato", "Infortunato"),
        ("squalificato", "Squalificato"),
        ("diffidato", "Diffidato"),
    ])
    func altriTipi(tipo: String, attesa: String) {
        #expect(DubbioRiassunto(id: 1, nome: "A", ruolo: nil, tipo: tipo, pVoto: 0.5).descrizione == attesa)
    }

    @Test("Widget completo (/api/widget, senza etichetta): «In dubbio» e «gioca N%» con la stessa regola", arguments: [
        (#""p_voto": 0.7"#, "In dubbio · gioca 70%"),
        (#""p_voto": 1.0"#, "In dubbio"),
        (#""p_voto": 0"#, "In dubbio"),
        (#""percentuale": 60"#, "In dubbio"),
    ])
    func statoDelWidgetCompleto(campo: String, attesa: String) throws {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        let json = #"{"id": 1, "nome": "A", "stato": "titolare", "dubbio": true, \#(campo)}"#
        let g = try d.decode(GiocatoreWidget.self, from: Data(json.utf8))
        #expect(g.descrizioneStato == attesa)
    }
}
