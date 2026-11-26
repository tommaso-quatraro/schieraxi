import Foundation
import Testing
@testable import Schieraxi

/// Giornate, da dove vengono i punti (#900, riga 106 di `docs/COERENZA-WEB-IPHONE.md`): nella giornata aperta, sotto la tabella
/// degli 11, le frasi del server su riserve entrate, modificatore difesa e partita rinviata (`spiegazione_punti.righe` di ogni voce
/// di `GET /api/diario`), così come sono e nel loro ordine, come `dettaglioGiornata` della web; `null` (niente da spiegare) o assente
/// (server di prima): niente. L'app non scrive frasi sue e non rifà conti. Dati inventati: la giornata 11 di `diario-giornate.json`
/// ha due frasi, la 10 `null`, le altre (e tutto `diario-giornate-vecchio.json`) non hanno il campo.
@MainActor
struct SpiegazionePuntiGiornateTests {
    private func pagina(_ fixture: String) throws -> PaginaGiornate {
        PaginaGiornate(try Fixture.decodifica(fixture) as DiarioRisposta)
    }

    /// Una pagina con la sola giornata 11 di Serie A e `campo` (JSON) come `spiegazione_punti`.
    private func paginaCon(_ campo: String) throws -> PaginaGiornate {
        let json = #"""
            {"giornate": [{"stagione": "2026-27", "giornata": 11, "giornata_lega": 8,
                           "schierata": {"modulo": "3-4-3", "atteso": 71.0, "reale": 70.0,
                                         "titolari": [{"id": 1, "nome": "Portiere Uno", "ruolo": "P"}]},
                           "spiegazione_punti": \#(campo)}]}
            """#
        return PaginaGiornate(try Decodifica.decodifica(Data(json.utf8)) as DiarioRisposta)
    }

    @Test("Sotto la tabella le frasi del server, così come sono e nel loro ordine")
    func frasiDelServer() throws {
        let d = try #require(try pagina("diario-giornate").dettaglio("2026-27-11"))
        #expect(d.perche == ["Al posto di Attaccante Cinque non è entrato nessuno dalla panchina.", "Modificatore difesa: +1,5."])
        #expect(d.titolari.count == 3, "la tabella resta quella di prima")
    }

    @Test("Con `spiegazione_punti` null niente frasi")
    func nullNienteFrasi() throws {
        #expect(try pagina("diario-giornate").dettaglio("2026-27-10")?.perche == [])
    }

    @Test("Un server di prima, che non manda `spiegazione_punti`, non ha frasi: la giornata si legge come prima")
    func serverDiPrima() throws {
        let p = try pagina("diario-giornate-vecchio")
        try #require(!p.righe.isEmpty, "la fixture del server di prima non ha giornate: il test non prova niente")
        for r in p.righe {
            let d = try #require(p.dettaglio(r.id))
            #expect(d.perche == [], "\(r.nome): niente frasi")
        }
        #expect(try pagina("diario-giornate").dettaglio("2026-27-9")?.perche == [], "anche una voce senza il campo")
    }

    @Test("Frasi vuote, solo spazi o che non sono testo si saltano, come `filter` della web; un campo storto vale «niente»",
          arguments: [
              (#"{"righe": ["", "   ", 3, null, "Modificatore difesa: +1,0."]}"#, ["Modificatore difesa: +1,0."]),
              (#"{"formazione": "schierata", "righe": "Modificatore difesa: +1,0."}"#, []),
              (#"{"formazione": "schierata"}"#, []),
              (#""Modificatore difesa: +1,0.""#, []),
              (#"[]"#, []),
          ])
    func tollerante(_ campo: String, _ attese: [String]) throws {
        let p = try paginaCon(campo)
        let r = try #require(p.righe.first, "un campo storto non deve far sparire la giornata")
        #expect(r.punti == "70,0")
        let d = try #require(p.dettaglio(r.id))
        #expect(d.perche == attese)
        #expect(d.titolari.map(\.nome) == ["Portiere Uno"])
    }
}
