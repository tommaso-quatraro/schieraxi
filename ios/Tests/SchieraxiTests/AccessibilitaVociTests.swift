import Foundation
import Testing
@testable import Schieraxi

/// Le frasi lette da VoiceOver e le parole che non lasciano il colore da solo (#882): la scadenza a parole intere in cima alla
/// Formazione, la testata del widget Formazione in una frase sola anche nel cerchio della schermata di blocco, la difficoltà delle
/// prossime partite scritta nella casella (le parole della web), il posto in panchina come il numero davanti al nome della web.
/// Dati inventati, ora fissa.
@Suite("Accessibilità: frasi di VoiceOver e difficoltà a parole")
struct AccessibilitaVociTests {
    /// sabato 31 ottobre 2026, 11:40 (ora italiana): 3 h 10 min prima della scadenza delle 14:50.
    private static func adesso() throws -> Date { try #require(Quando.data("2026-10-31 11:40")) }

    private static func formazione() throws -> Formazione {
        try Decodifica.decodifica(Data(#"""
        {"giornata": 11, "giornata_lega": 8, "modulo": "4-3-3", "punteggio_atteso": 70.0, "titolari": [], "panchina": []}
        """#.utf8))
    }

    // MARK: testa della Formazione

    @Test("In cima alla Formazione VoiceOver legge «fra 3 ore e 10 minuti», non «fra 3 h 10 min»; sullo schermo resta la forma corta")
    func scadenzaAParole() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 14:50", "fase": "prima"}"#.utf8))
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t.manca == "fra 3\u{00A0}h 10\u{00A0}min")
        #expect(t.voceScadenza == "Si chiude oggi 14:50 fra 3 ore e 10 minuti")
        #expect(t.voceScadenza == "\(Catalogo.Formazione.siChiude(quando: "oggi 14:50")) \(Catalogo.Formazione.fra(tempo: "3 ore e 10 minuti"))")
    }

    @Test("Scadenza passata: VoiceOver legge «Formazione chiusa», senza conto alla rovescia")
    func scadenzaPassata() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11, "scadenza": "2026-10-31 09:00"}"#.utf8))
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t.voceScadenza == Catalogo.Formazione.chiusaBreve)
    }

    @Test("Senza scadenza da mostrare (giornata in corso) niente frase della scadenza")
    func senzaScadenza() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"""
        {"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 09:00", "fase": "in_corso",
         "in_corso": {"punti_fatti": 40, "ancora_da_giocare": 2}}
        """#.utf8))
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t.chiude == nil)
        #expect(t.voceScadenza == nil)
    }

    // MARK: widget Formazione

    @Test("Widget Formazione: la testata in una frase sola, la stessa per il grande e per il cerchio della schermata di blocco")
    func testataWidgetParlata() throws {
        let json = #"""
        {"giornata": 11, "giornata_lega": 8,
         "formazione": {"modulo": "3-4-3", "punti_attesi": 72.7, "intervallo": {"basso": 65, "alto": 81}, "titolari": []}}
        """#
        let w = try #require(RiassuntoWidget.leggi(Data(json.utf8)))
        let f = try #require(w.formazione)
        #expect(f.testataParlata(giornata: w.nomeGiornata) == "3-4-3, 72,7 punti attesi, tra 65 e 81, Giornata 8, 11ª di Serie A")
        #expect(f.testataParlata(giornata: nil) == "3-4-3, 72,7 punti attesi, tra 65 e 81")
    }

    // MARK: prossime partite della scheda

    @Test("Prossime partite: in ogni casella la difficoltà anche a parole, le stesse della web (`diff.1`…`diff.5`)", arguments: 1...5)
    func difficoltaAParole(d: Int) throws {
        let p: PartitaCalendario = try Decodifica.decodifica(Data(#"{"giornata": 12, "avversario": "como", "in_casa": true, "difficolta": \#(d)}"#.utf8))
        let parolaWeb = try TestiWeb().italiano("diff.\(d)")
        #expect(ProssimePartite.parola(p) == parolaWeb)
    }

    // MARK: panchina

    @Test("Panchina: VoiceOver dice anche il posto, come il numero davanti al nome della web («2. Mario Prova»)")
    func postoInPanchina() throws {
        let g: Giocatore = try Decodifica.decodifica(Data(#"{"id": 7, "nome": "Mario Prova", "ruolo": "C", "squadra": "genoa", "fv_atteso": 6.5, "p_voto": 0.9}"#.utf8))
        #expect(RigaGiocatore.voce(g, posizione: 2) == "2. " + RigaGiocatore.voce(g))
        #expect(RigaGiocatore.voce(g).hasPrefix("Mario Prova, "), "fuori dalla panchina niente numero")
    }
}
