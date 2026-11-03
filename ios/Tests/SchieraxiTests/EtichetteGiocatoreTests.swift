import Foundation
import Testing
@testable import Schieraxi

/// Le pillole sotto il nome di un giocatore e la riga degli avvisi di Oggi, come la web: se il server manda l'etichetta pronta
/// (`etichetta` = {codice, testo, tono}, `fanta/etichette.py`) si mostra quella; altrimenti le stesse parole del vocabolario.
/// Un dubbio si scrive «In dubbio · gioca 62%» (`oggi.dubbio` di testi.js), mai «Dubbio: affaticamento» né «Dubbio (55%)».
@Suite("Etichette dei giocatori come la web")
struct EtichetteGiocatoreTests {
    private func giocatore(titolarita: String? = "titolare", pVoto: Double = 0.9, _ altro: String = "") throws -> Giocatore {
        let titolo = titolarita.map { #""titolarita": "\#($0)","# } ?? ""
        let json = #"{\#(titolo) \#(altro) "id": 7, "nome": "Rossi", "ruolo": "D", "punti_attesi": 5, "p_voto": \#(pVoto)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    private func avviso(_ altro: String) throws -> Avviso {
        try Decodifica.decodifica(Data(#"{"id": 5, "nome": "Leonel Marteni", "ruolo": "A", \#(altro)}"#.utf8))
    }

    // MARK: etichetta pronta del server

    @Test("L'etichetta del server prende il posto della titolarità")
    func etichettaDelServer() throws {
        let g = try giocatore(titolarita: "ballottaggio", pVoto: 0.62, #"""
            "dubbio": true, "motivi": ["titolare in ballottaggio"],
            "etichetta": {"codice": "in_dubbio", "testo": "In dubbio · gioca 62%", "tono": "attenzione"},
            """#)
        #expect(g.etichette == [Etichetta(testo: "In dubbio · gioca 62%", gravita: .attenzione)])
    }

    /// I toni di `fanta/etichette.py` e il colore che danno (uno sconosciuto vale neutro).
    static let toni: [(String, Etichetta.Gravita)] = [
        ("negativo", .grave), ("attenzione", .attenzione), ("positivo", .normale), ("neutro", .normale), ("strano", .normale),
    ]

    @Test("Il tono del server dà il colore", arguments: EtichetteGiocatoreTests.toni)
    func tono(tono: String, gravita: Etichetta.Gravita) throws {
        let g = try giocatore(#""etichetta": {"codice": "x", "testo": "Qualcosa", "tono": "\#(tono)"},"#)
        #expect(g.etichette.first == Etichetta(testo: "Qualcosa", gravita: gravita))
    }

    @Test("Con l'etichetta del server infortunio e squalifica non si ripetono nei motivi; la nota resta")
    func motiviDiStatoNonRipetuti() throws {
        let g = try giocatore(titolarita: "fuori", #"""
            "stato": "infortunato", "motivi": ["infortunato", "affaticamento muscolare al flessore"],
            "etichetta": {"codice": "infortunato", "testo": "Infortunato", "tono": "negativo"},
            """#)
        #expect(g.etichette.map(\.testo) == ["Infortunato", "Affaticamento muscolare al flessore"])
    }

    @Test("Un'etichetta vuota o di forma strana vale «niente etichetta»", arguments: [
        #""etichetta": {"codice": "titolare", "testo": "  ", "tono": "positivo"},"#,
        #""etichetta": "Probabile titolare","#,
        #""etichetta": null,"#,
    ])
    func etichettaStrana(campo: String) throws {
        let g = try giocatore(titolarita: "titolare", campo)
        #expect(g.etichette.map(\.testo) == ["Probabile titolare"])
    }

    // MARK: senza etichetta (server vecchio, Cambi consigliati)

    @Test("Senza etichetta un dubbio dice anche «gioca N%», come il server")
    func dubbioSenzaEtichetta() throws {
        let g = try giocatore(titolarita: "ballottaggio", pVoto: 0.62, #""dubbio": true,"#)
        #expect(g.etichette == [Etichetta(testo: "In ballottaggio", gravita: .attenzione), Etichetta(testo: "In dubbio · gioca 62%", gravita: .attenzione)])
    }

    @Test("Titolarità a parole, diffida e motivi utili (senza percentuali)")
    func titolaritaEDiffida() throws {
        let g = try giocatore(titolarita: "titolare", #""stato": "titolare", "percentuale": 85.0, "diffidato": true, "motivi": ["titolare al 85%", "squalifica a rischio"],"#)
        #expect(g.etichette.map(\.testo) == ["Probabile titolare", "Diffidato", "Squalifica a rischio"], "solo parole: l'unica percentuale è «gioca N%»")
        #expect(g.etichette.map(\.gravita) == [.normale, .attenzione, .normale])
    }

    @Test("Fuori e infortunato sono gravi; un motivo con una percentuale non diventa un'etichetta")
    func graviEPercentuali() throws {
        let fuori = try giocatore(titolarita: "fuori", #""stato": "infortunato", "percentuale": 0.0, "motivi": ["infortunato"],"#)
        #expect(fuori.etichette.map(\.testo) == ["Fuori", "Infortunato"])
        #expect(fuori.etichette.allSatisfy { $0.gravita == .grave })
        let conNumero = try giocatore(titolarita: "ballottaggio", #""motivi": ["ballottaggio al 55%", "scelta del tecnico"],"#)
        #expect(conNumero.etichette.map(\.testo) == ["In ballottaggio", "Scelta del tecnico"])
    }

    @Test("A giornata iniziata lo stato della partita al posto delle probabili")
    func statoDellaPartita() throws {
        let giocato = try giocatore(titolarita: nil, #""stato_partita": "fatto","#)
        #expect(giocato.etichette.map(\.testo) == ["Ha giocato"])
        let rinviata = try giocatore(titolarita: nil, #""stato_partita": "rinviata","#)
        #expect(rinviata.etichette.first?.gravita == .attenzione)
    }

    // MARK: avvisi di Oggi («Da controllare», indisponibili, diffidati)

    @Test("La riga di un avviso usa il testo del server, se c'è")
    func avvisoConEtichetta() throws {
        let a = try avviso(#""tipo": "dubbio", "p_voto": 0.55, "etichetta": {"codice": "in_dubbio", "testo": "In dubbio · gioca 55%", "tono": "attenzione"}"#)
        #expect(a.descrizione == "In dubbio · gioca 55%")
        #expect(a.gravita == .attenzione)
        let diffidato = try avviso(#""tipo": "diffidato", "etichetta": {"codice": "diffidato", "testo": "Diffidato", "tono": "attenzione"}"#)
        #expect(diffidato.gravita == .attenzione)
    }

    /// Avvisi senza etichetta: campi JSON, testo e colore attesi.
    static let avvisiSenzaEtichetta: [(String, String, Etichetta.Gravita)] = [
        (#""tipo": "dubbio", "p_voto": 0.55"#, "In dubbio · gioca 55%", .attenzione),
        (#""tipo": "dubbio""#, "In dubbio", .attenzione),
        (#""tipo": "infortunato""#, "Infortunato", .grave),
        (#""tipo": "squalificato""#, "Squalificato", .grave),
        (#""tipo": "diffidato""#, "Diffidato", .normale),
    ]

    @Test("Senza etichetta le parole della web (`oggi.*` di testi.js)", arguments: EtichetteGiocatoreTests.avvisiSenzaEtichetta)
    func avvisoSenzaEtichetta(campi: String, testo: String, gravita: Etichetta.Gravita) throws {
        let a = try avviso(campi)
        #expect(a.descrizione == testo)
        #expect(a.gravita == gravita)
    }

    @Test("La frase del dubbio è quella della web (`oggi.dubbio`)")
    func fraseDelDubbioDellaWeb() throws {
        let web = try TestiWeb().italiano("oggi.dubbio").replacingOccurrences(of: "{p}", with: "55%")
        #expect(try avviso(#""tipo": "dubbio", "p_voto": 0.55"#).descrizione == web)
    }

    // MARK: dati di prova (demo e fotografie)

    @Test("Nella demo il dubbio è «In dubbio · gioca 62%» in Formazione e in Oggi, mai «Dubbio: …»")
    func demoDiOggi() async throws {
        let oggi: Oggi = try Decodifica.decodifica(try await FinteServer.demo.richiesta("GET", "/api/oggi", corpo: nil))
        // con i punti attesi veri (gioca × fantavoto, #246) Marténi non è tra i migliori di Oggi: la pillola si guarda in Formazione
        let formazione: Formazione = try Decodifica.decodifica(try await FinteServer.demo.richiesta("GET", "/api/formazione", corpo: nil))
        let marteni = try #require(formazione.titolari.first { $0.id == 120 }, "nella demo Marténi non è titolare")
        #expect(marteni.etichette.map(\.testo).contains("In dubbio · gioca 62%"))
        #expect(!marteni.etichette.contains { $0.testo.hasPrefix("Dubbio") })
        let avviso = try #require(oggi.avvisi?.first { $0.id == 120 && $0.tipo == "dubbio" })
        #expect(avviso.descrizione == "In dubbio · gioca 62%")
    }
}
