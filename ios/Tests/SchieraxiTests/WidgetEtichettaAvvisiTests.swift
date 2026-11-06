import Foundation
import Testing
@testable import Schieraxi

/// Widget «Da controllare» con le parole della Formazione (#282): dal 5/11/2026 gli `avvisi` di `/api/widget` hanno anche
/// `etichetta` = {codice, testo, tono}, la stessa di Oggi. Il widget la legge per prima: un titolare al 2% è «Improbabile», non
/// «In dubbio · gioca 2%». Senza etichetta (server vecchio) restano le parole di prima. Dati inventati.
@Suite("Widget: l'etichetta degli avvisi dal server")
struct WidgetEtichettaAvvisiTests {
    private let web: TestiWeb

    init() throws { web = try TestiWeb() }

    /// Un avviso di `/api/widget` in formazione, con questo pezzo di JSON in più.
    private func avviso(_ altro: String) throws -> GiocatoreWidget {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        let json = #"{"id": 5, "nome": "Dario Lerri", "ruolo": "D", "squadra": "como", "tipo": "dubbio", "in_formazione": true, \#(altro)}"#
        return try d.decode(GiocatoreWidget.self, from: Data(json.utf8))
    }

    /// Il riassunto completo con questi avvisi.
    private func riassunto(_ avvisi: String) throws -> RiassuntoWidget {
        let corpo = #"{"giornata": 11, "giornata_lega": 8, "scadenza": "2026-11-07 14:50", "fase": "prima", "avvisi": [\#(avvisi)]}"#
        return try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
    }

    /// Il codice dell'etichetta, la chiave di testi.js con la stessa parola (`fanta/etichette.py`) e `p_voto`.
    static let etichette: [(String, String, Double)] = [
        ("improbabile", "tit.improbabile", 0.02), ("panchina", "tit.panchina", 0.3), ("ballottaggio", "tit.ballottaggio", 0.55),
    ]

    @Test("Il testo dell'etichetta del server, come la Formazione e Oggi", arguments: WidgetEtichettaAvvisiTests.etichette)
    func etichettaDelServer(codice: String, chiave: String, pVoto: Double) throws {
        let parola = try web.italiano(chiave)
        let g = try avviso(#""p_voto": \#(pVoto), "etichetta": {"codice": "\#(codice)", "testo": "\#(parola)", "tono": "attenzione"}"#)
        #expect(g.descrizioneStato == parola)
        #expect(!g.descrizioneStato.contains("In dubbio"))
    }

    @Test("«In dubbio · gioca 55%» solo se lo dice il server (`oggi.dubbio`)")
    func inDubbioDalServer() throws {
        let parola = try web.italiano("oggi.dubbio").replacingOccurrences(of: "{p}", with: "55%")
        let g = try avviso(#""p_voto": 0.55, "etichetta": {"codice": "in_dubbio", "testo": "\#(parola)", "tono": "attenzione"}"#)
        #expect(g.descrizioneStato == parola)
    }

    @Test("Il testo del server vale anche in inglese")
    func inglese() throws {
        let g = try avviso(#""p_voto": 0.02, "etichetta": {"codice": "improbabile", "testo": "Unlikely", "tono": "negativo"}"#)
        #expect(g.descrizioneStato == "Unlikely")
    }

    @Test("Server vecchio o etichetta strana: le parole di prima", arguments: [
        #""p_voto": 0.55"#,
        #""p_voto": 0.55, "etichetta": null"#,
        #""p_voto": 0.55, "etichetta": "Improbabile""#,
        #""p_voto": 0.55, "etichetta": 3"#,
        #""p_voto": 0.55, "etichetta": {"codice": "improbabile"}"#,
        #""p_voto": 0.55, "etichetta": {"codice": "improbabile", "testo": "  "}"#,
        #""p_voto": 0.55, "etichetta": {"testo": 7}"#,
    ])
    func senzaEtichetta(campi: String) throws {
        let g = try avviso(campi)
        #expect(g.descrizioneStato == "In dubbio · gioca 55%")
    }

    @Test("Le altre parti del riassunto restano leggibili anche con un'etichetta strana")
    func riassuntoTollerante() throws {
        let w = try riassunto(#"{"id": 5, "nome": "Dario Lerri", "ruolo": "D", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.02, "etichetta": [1, 2]}"#)
        #expect(w.giornata == 11)
        #expect(w.daControllare.map(\.id) == [5])
    }

    @Test("«Da controllare»: le righe del widget con le parole del server")
    func daControllare() throws {
        let improbabile = try web.italiano("tit.improbabile"), panchina = try web.italiano("tit.panchina")
        let w = try riassunto("""
            {"id": 5, "nome": "Dario Lerri", "ruolo": "D", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.02,
             "etichetta": {"codice": "improbabile", "testo": "\(improbabile)", "tono": "negativo"}},
            {"id": 6, "nome": "Ivo Merlo", "ruolo": "C", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.3,
             "etichetta": {"codice": "panchina", "testo": "\(panchina)", "tono": "attenzione"}},
            {"id": 7, "nome": "Alvise Bastrani", "ruolo": "D", "tipo": "diffidato", "in_formazione": true,
             "etichetta": {"codice": "diffidato", "testo": "Diffidato", "tono": "attenzione"}}
            """)
        #expect(w.daControllare.map(\.descrizioneStato) == [improbabile, panchina, "Diffidato"])
        // il riassunto per i widget «Prossima giornata» e «Da controllare» porta lo stesso testo
        let r = try #require(w.comeRiassuntoOggi())
        #expect(r.dubbi?.map(\.descrizione) == [improbabile, panchina, "Diffidato"])
        #expect(r.dubbi?.first?.formeRiga.first == "Dario Lerri · \(improbabile)")
    }

    @Test("L'etichetta resta nella copia salvata dei widget «vecchi»")
    func copiaSalvata() throws {
        let w = try riassunto(#"{"id": 5, "nome": "Dario Lerri", "ruolo": "D", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.02, "etichetta": {"codice": "improbabile", "testo": "Improbabile", "tono": "negativo"}}"#)
        let r = try #require(w.comeRiassuntoOggi())
        let copia = try JSONDecoder().decode(RiassuntoOggi.self, from: JSONEncoder().encode(r))
        #expect(copia.dubbi?.first?.descrizione == "Improbabile")
    }
}
