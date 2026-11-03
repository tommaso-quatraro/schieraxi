import Foundation
import Testing
@testable import Schieraxi

/// Il widget «Giocatore osservato»: una sola percentuale, «gioca N%» da `p_voto` con le parole dell'app (#205), mai la
/// `percentuale` delle probabili; e quando il server toglie i seguiti per il peso (`mancano` contiene «osservati», #206) il
/// widget lo dice invece di restare vuoto. Dati inventati.
@Suite("Widget «Osservato»")
struct WidgetOsservatoTests {
    private func giocatore(_ campi: String) throws -> GiocatoreWidget {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        let json = #"{"id": 31, "nome": "Marzio Zaviani", "ruolo": "C", "avversario": "juventus", "in_casa": true, \#(campi)}"#
        return try d.decode(GiocatoreWidget.self, from: Data(json.utf8))
    }

    private func riassunto(_ altro: String) throws -> RiassuntoWidget {
        let json = #"{"giornata": 11, "giornata_lega": 8, "rosa": [{"id": 120, "nome": "Leonel Marténi", "ruolo": "A", "p_voto": 0.62}]\#(altro)}"#
        return try #require(RiassuntoWidget.leggi(Data(json.utf8)))
    }

    @Test("«gioca N%» viene da p_voto, con lo stesso testo dell'app; la percentuale delle probabili non si mostra", arguments: [
        (#""p_voto": 0.9, "percentuale": 92"#, "gioca 90%" as String?),
        (#""p_voto": 0.55, "percentuale": 60"#, "gioca 55%"),
        (#""p_voto": 0.996"#, "gioca 100%"),
        (#""percentuale": 92"#, nil),
    ])
    func giocaDaPVoto(campi: String, atteso: String?) throws {
        let g = try giocatore(campi)
        #expect(g.giocaTesto == atteso)
        #expect(g.giocaTesto == LetturaPedina.gioca(g.pVoto))
    }

    @Test("La riga del widget: prima l'avviso del server, altrimenti «gioca N%»", arguments: [
        (#""stato": "titolare", "dubbio": true, "p_voto": 0.55, "percentuale": 60"#, "In dubbio · gioca 55%" as String?),
        (#""stato": "infortunato", "p_voto": 0, "percentuale": 0"#, "Infortunato"),
        (#""stato": "titolare", "p_voto": 0.9, "percentuale": 92"#, "gioca 90%"),
        (#""stato": "titolare", "percentuale": 92"#, nil),
    ])
    func rigaDelWidget(campi: String, atteso: String?) throws {
        #expect(try giocatore(campi).statoOGioca == atteso)
    }

    @Test("Seguiti tolti dal server per il peso: «Apri l'app per vederli», non «Nessun giocatore»")
    func seguitiTolti() throws {
        let w = try riassunto(#", "mancano": ["scambio", "osservati"]"#)
        #expect(w.osservato(nil) == nil)
        #expect(w.vuotoOsservato == .seguitiNellApp)
        #expect(w.vuotoOsservato.titolo == "Apri l'app per vederli")
        #expect(w.vuotoOsservato.riga == "Seguiti: apri l'app")
    }

    @Test("Senza seguiti (o se manca solo un'altra parte) il widget invita ad aggiungerne uno", arguments: [
        #", "osservati": []"#,
        #", "osservati": [], "mancano": ["scambio"]"#,
        "",
    ])
    func nessunSeguito(altro: String) throws {
        let w = try riassunto(altro)
        #expect(w.osservato(nil) == nil)
        #expect(w.vuotoOsservato == .nessunSeguito)
        #expect(w.vuotoOsservato.titolo == "Nessun giocatore")
    }

    @Test("Con i seguiti tolti, un giocatore scelto dalla rosa si vede lo stesso")
    func sceltoDallaRosa() throws {
        let w = try riassunto(#", "mancano": ["osservati"]"#)
        #expect(w.osservato(120)?.nome == "Leonel Marténi")
    }
}
