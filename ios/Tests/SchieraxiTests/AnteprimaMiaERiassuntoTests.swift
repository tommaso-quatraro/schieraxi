import Foundation
import Testing
@testable import Schieraxi

/// Aggiorna le rose, l'anteprima come la web (#808): la squadra suggerita dal server compare già scelta anche quando non è nel
/// file (`nomiMia` di `anteprima.js`: si aggiornano solo le rose degli altri), e il riassunto in cima si rifà dopo ogni scelta
/// (`arRiassuntoScelte`: conta solo i dubbi decisi dall'utente). Squadre e giocatori INVENTATI.
@Suite("Aggiorna le rose: la tua squadra e il riassunto come la web (#808)")
struct AnteprimaMiaERiassuntoTests {
    /// Solo le rose degli altri: la squadra suggerita dal server («Real Fantasia») non è nel file.
    static let soloAltri = #"""
    {"squadre": [
      {"nome": "Atletico Pigiama", "giocatori": [
        {"testo": "Oddone", "riga": 0, "stato": "sicuro", "id": 906, "nome": "Oddone Brivio", "ruolo": "A", "squadra": "napoli"}
      ]}
    ],
    "mia_squadra": "Real Fantasia", "sicuri": 1, "da_controllare": 0, "non_trovati": 0}
    """#

    private func anteprima(_ json: String = AnteprimaRoseTests.risposta) throws -> AnteprimaRose {
        try Decodifica.decodifica(Data(json.utf8))
    }

    // MARK: la tua squadra

    @Test("La squadra suggerita che non è nel file si elenca per prima ed è già scelta")
    func suggeritaFuoriDalFile() throws {
        let r = try anteprima(Self.soloAltri)
        #expect(AnteprimaLogica.nomiMia(r) == ["Real Fantasia", "Atletico Pigiama"])
        #expect(AnteprimaLogica.mia(decisa: nil, r) == "Real Fantasia")
        #expect(AnteprimaLogica.mia(decisa: "Atletico Pigiama", r) == "Atletico Pigiama", "la scelta dell'utente vince")
        #expect(AnteprimaLogica.mia(decisa: "Non c'è", r) == "", "una squadra né letta né suggerita non si propone")
    }

    @Test("La squadra suggerita è nel file, o non c'è: le squadre lette, una volta sola")
    func suggeritaNelFile() throws {
        let r = try anteprima()
        #expect(AnteprimaLogica.nomiMia(r) == ["Real Fantasia", "Atletico Pigiama"])
        let senza = AnteprimaRose(squadre: r.squadre)
        #expect(AnteprimaLogica.nomiMia(senza) == ["Real Fantasia", "Atletico Pigiama"])
        #expect(AnteprimaLogica.mia(decisa: nil, senza) == "")
    }

    // MARK: il riassunto

    @Test("Senza scelte il riassunto è quello di prima")
    func senzaScelte() throws {
        let r = try anteprima()
        #expect(AnteprimaLogica.riassunto(r, scelte: [:]) == AnteprimaLogica.riassunto(r))
        #expect(AnteprimaLogica.riassunto(r, scelte: [:])
                == "2 squadre: 3 giocatori riconosciuti, 2 da controllare, 1 non trovato. Sistema i dubbi qui sotto, poi conferma.")
    }

    @Test("Un giocatore scelto sale tra i riconosciuti; «Toglilo» esce soltanto dal suo conto")
    func sceltaETogli() throws {
        let r = try anteprima()
        let scelte: [String: SceltaDubbio] = [
            AnteprimaLogica.chiave("Real Fantasia", "Bertolazzi"): .giocatore(905),
            AnteprimaLogica.chiave("Real Fantasia", "Quintavalle"): .togli,
        ]
        #expect(AnteprimaLogica.riassunto(r, scelte: scelte)
                == "2 squadre: 4 giocatori riconosciuti, 1 da controllare. Sistema i dubbi qui sotto, poi conferma.")
    }

    @Test("Tutti i dubbi decisi: niente invito a sistemarli")
    func tuttiDecisi() throws {
        let r = try anteprima()
        let scelti: [String: SceltaDubbio] = [
            AnteprimaLogica.chiave("Real Fantasia", "Mancuzzi"): .giocatore(903),
            AnteprimaLogica.chiave("Real Fantasia", "Bertolazzi"): .giocatore(904),
            AnteprimaLogica.chiave("Real Fantasia", "Quintavalle"): .giocatore(999),
        ]
        #expect(AnteprimaLogica.riassunto(r, scelte: scelti) == "2 squadre: 6 giocatori riconosciuti.")
        let tolti: [String: SceltaDubbio] = [
            AnteprimaLogica.chiave("Real Fantasia", "Mancuzzi"): .togli,
            AnteprimaLogica.chiave("Real Fantasia", "Bertolazzi"): .togli,
            AnteprimaLogica.chiave("Real Fantasia", "Quintavalle"): .togli,
        ]
        #expect(AnteprimaLogica.riassunto(r, scelte: tolti) == "2 squadre: 3 giocatori riconosciuti.")
    }

    @Test("La proposta del server non toccata, «Scegli chi è» e una scelta su un riconosciuto non cambiano i conti")
    func sceltaCheNonConta() throws {
        let r = try anteprima()
        let scelte: [String: SceltaDubbio] = [
            AnteprimaLogica.chiave("Real Fantasia", "Bertolazzi"): .lascia,
            AnteprimaLogica.chiave("Real Fantasia", "Pirlotti"): .togli,
        ]
        #expect(AnteprimaLogica.riassunto(r, scelte: scelte) == AnteprimaLogica.riassunto(r))
    }

    @Test("Due omonimi nella stessa rosa: si conta la scelta di ognuno")
    func omonimi() throws {
        let r = try anteprima(AnteprimaRoseTests.omonimi)
        let primo = try #require(r.squadre.first?.giocatori.first { $0.riga == 1 })
        let scelte: [String: SceltaDubbio] = [AnteprimaLogica.chiave("Real Fantasia", primo): .giocatore(904)]
        #expect(AnteprimaLogica.riassunto(r, scelte: scelte)
                == "1 squadra: 2 giocatori riconosciuti, 1 da controllare, 1 non trovato. Sistema i dubbi qui sotto, poi conferma.")
    }
}

/// Il ViewModel dell'importazione con le rose degli altri: la tua squadra resta scelta e parte con «Conferma e salva».
@MainActor
@Suite("Aggiorna le rose: la tua squadra con le rose degli altri (#808)")
struct AnteprimaMiaViewModelTests {
    @Test("Importando le rose degli altri la tua squadra è già scelta e si salva")
    func soloAltriTieneLaMia() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/rose/anteprima") { return Data(AnteprimaMiaERiassuntoTests.soloAltri.utf8) }
            return Data(#"{"squadre_importate": ["Atletico Pigiama"], "totale_squadre": 2, "riepilogo": "Fatto"}"#.utf8)
        }
        let vm = ImportaExcelViewModel(server: s)
        vm.testoRose = "Atletico Pigiama\nOddone"
        await vm.importaTesto()
        #expect(vm.mia == "Real Fantasia", "la squadra suggerita dal server è già scelta")
        await vm.conferma()
        let dati = try #require(s.corpiInviati(a: "POST /api/rose/testo").last)
        let corpo = try #require(try JSONSerialization.jsonObject(with: dati) as? [String: Any])
        #expect(corpo["mia_squadra"] as? String == "Real Fantasia", "scegliere un'altra squadra non succede per sbaglio")
    }
}
