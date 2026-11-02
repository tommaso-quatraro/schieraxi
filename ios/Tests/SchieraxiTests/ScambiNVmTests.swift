import XCTest
@testable import Schieraxi

/// Scambi N contro M con conguaglio di crediti (server 1.62): indirizzi, limiti e lettura dell'analisi completa.
@MainActor
final class ScambiNVmTests: XCTestCase {
    private func vm(_ server: any ServerClient = ServerDiProva { _, _, _ in Data("{}".utf8) }) -> AnalizzaScambioViewModel {
        AnalizzaScambioViewModel(server: server)
    }

    func testIndirizzoDellAnalisiCompletaSenzaConguaglio() {
        let v = vm()
        v.altra = "Real Madrink"
        v.doIds = [7, 3]
        v.ricevoIds = [9]
        XCTAssertEqual(v.indirizzoAnalisi, "/api/scambi/analizza?con=Real%20Madrink&do=3,7&ricevo=9&completo=true")
    }

    func testIlConguaglioPositivoENegativoVaNellIndirizzo() {
        let v = vm()
        v.altra = "X"
        v.doIds = [1]
        v.ricevoIds = [2]
        v.conguaglio = "12"
        XCTAssertTrue(v.indirizzoAnalisi.hasSuffix("&completo=true&conguaglio=12"), v.indirizzoAnalisi)
        v.conguaglio = "-5"
        XCTAssertTrue(v.indirizzoAnalisi.hasSuffix("&conguaglio=-5"))
        v.conguaglio = "−7"   // il segno meno tipografico della tastiera
        XCTAssertEqual(v.creditiConguaglio, -7)
        v.conguaglio = "+3"
        XCTAssertEqual(v.creditiConguaglio, 3)
        v.conguaglio = "0"
        XCTAssertFalse(v.indirizzoAnalisi.contains("conguaglio"), "zero crediti = nessun conguaglio")
        v.conguaglio = ""
        XCTAssertEqual(v.creditiConguaglio, 0)
        XCTAssertTrue(v.conguaglioValido)
    }

    func testUnConguaglioNonNumericoNonSiManda() {
        let v = vm()
        v.altra = "X"
        v.doIds = [1]
        v.ricevoIds = [2]
        for cattivo in ["abc", "1,5", "12 crediti", "99999999999999999999", "1000000", "-1000000", "-9223372036854775808"] {
            v.conguaglio = cattivo
            XCTAssertFalse(v.conguaglioValido, cattivo)
            XCTAssertFalse(v.puoAnalizzare, cattivo)
        }
        v.conguaglio = "10"
        XCTAssertTrue(v.puoAnalizzare)
    }

    func testAlMassimoQuattroPerLato() {
        let v = vm()
        v.altra = "X"
        v.doIds = [1, 2, 3, 4]
        v.ricevoIds = [5, 6, 7, 8]
        XCTAssertNil(v.troppi)
        XCTAssertTrue(v.puoAnalizzare)
        v.ricevoIds = [5, 6, 7, 8, 9]
        XCTAssertNotNil(v.troppi)
        XCTAssertFalse(v.puoAnalizzare)
    }

    func testLeProposteGrandiChiedonoFinoA() {
        let s = ScambiViewModel(server: ServerDiProva { _, _, _ in Data(#"{"proposte": []}"#.utf8) })
        XCTAssertEqual(s.indirizzoProposte, "/api/scambi/proposte?due=false")
        s.fino = 3
        XCTAssertEqual(s.indirizzoProposte, "/api/scambi/proposte?due=false", "senza una squadra scelta non si cercano scambi grandi")
        s.con = "Real Madrink"
        XCTAssertEqual(s.indirizzoProposte, "/api/scambi/proposte?due=true&con=Real%20Madrink&fino_a=3")
        s.fino = 4
        XCTAssertTrue(s.indirizzoProposte.hasSuffix("&fino_a=4"))
        s.fino = 2
        XCTAssertEqual(s.indirizzoProposte, "/api/scambi/proposte?due=true&con=Real%20Madrink", "il 2 contro 2 come prima")
        XCTAssertTrue(s.due)
        s.due = false
        XCTAssertEqual(s.fino, 1)
    }

    func testLAnalisiCompletaSiLegge() async throws {
        let corpo = #"""
        {"mia": "Io", "altra": "Loro", "do": [{"id": 1, "nome": "A", "ruolo": "C", "squadra": "inter", "quotazione": 10}],
         "ricevo": [{"id": 2, "nome": "B", "ruolo": "C", "squadra": "milan", "quotazione": 12}, {"id": 3, "nome": "C", "ruolo": "A", "squadra": "roma", "quotazione": 9}],
         "guadagno_mio": 2.4, "guadagno_loro": 1.1, "completo": true, "valido": false,
         "problemi": ["Loro avrebbe 4 portieri su un massimo di 3: ne dovrebbe liberare 1"],
         "rose": {"mio": {"squadra": "Io", "valida": true, "problemi": [], "modulo": "3-4-3", "conteggio": {"P": 3, "D": 8}},
                  "loro": {"squadra": "Loro", "valida": false, "problemi": ["troppi portieri"], "modulo": null}},
         "valore_rosa": {"mio": {"prima": 64.5, "dopo": 66.9, "variazione": 2.4, "percentuale": 3.7}, "loro": {"prima": 61, "dopo": 62.1, "variazione": 1.1, "percentuale": 1.8}},
         "panchina": {"mio": {"prima": 8, "dopo": 8.3, "variazione": 0.3}, "loro": {"prima": 7.5, "dopo": 7.4, "variazione": -0.1}},
         "conguaglio": {"crediti": 5, "valido": false, "problema": "Loro non ha abbastanza crediti", "residui": {"mio": 12, "loro": null},
                        "dopo": {"mio": 17, "loro": -2}, "chi_paga": "loro", "tasso_mio": 0.12, "tasso_loro": null, "valore_mio": 0.6, "valore_loro": null},
         "netto_mio": 3.0, "netto_loro": 0.6,
         "giudizio": {"chi": "nessuno", "testo": "Non valido", "soglia": 0.5, "spiegazione": ["riga 1", "riga 2"]}}
        """#
        let p: PropostaScambio = try Decodifica.decodifica(Data(corpo.utf8))
        XCTAssertEqual(p.ricevo.count, 2)
        XCTAssertEqual(p.valido, false)
        XCTAssertEqual(p.problemi?.count, 1)
        XCTAssertEqual(p.rose?.loro?.valida, false)
        XCTAssertNil(p.rose?.loro?.modulo)
        XCTAssertEqual(p.valoreRosa?.mio?.variazione, 2.4)
        XCTAssertEqual(p.panchina?.loro?.variazione, -0.1)
        XCTAssertEqual(p.conguaglio?.crediti, 5)
        XCTAssertEqual(p.conguaglio?.chiPaga, "loro")
        XCTAssertNil(p.conguaglio?.residui?.loro, "un credito sconosciuto resta vuoto")
        XCTAssertEqual(p.nettoMio, 3.0)
        XCTAssertEqual(p.giudizio?.spiegazione, ["riga 1", "riga 2"])
    }

    func testUnServerVecchioSenzaICampiNuoviSiLegge() throws {
        let corpo = #"{"altra": "Loro", "do": [], "ricevo": [], "guadagno_mio": 1.0, "guadagno_loro": 0.5}"#
        let p: PropostaScambio = try Decodifica.decodifica(Data(corpo.utf8))
        XCTAssertNil(p.completo)
        XCTAssertNil(p.conguaglio)
        XCTAssertNil(p.giudizio)
    }

    func testAnalizzaMandaTuttoAlServerEMostraIlGiudizio() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scambi/analizza") {
                return Data(#"{"altra": "Loro", "do": [], "ricevo": [], "guadagno_mio": 1.0, "guadagno_loro": 0.5, "completo": true, "valido": true, "giudizio": {"testo": "Conviene a tutti e due: proponilo."}}"#.utf8)
            }
            throw ErroreApi.server("niente")
        }
        let v = vm(s)
        v.altra = "Loro"
        v.doIds = [1, 2]
        v.ricevoIds = [3]
        v.conguaglio = "4"
        await v.analizza()
        XCTAssertEqual(s.quante("GET /api/scambi/analizza?con=Loro&do=1,2&ricevo=3&completo=true&conguaglio=4"), 1)
        XCTAssertEqual(v.esito?.giudizio?.testo, "Conviene a tutti e due: proponilo.")
        XCTAssertNil(v.errore)
    }
}

/// I tre modi degli scambi e il contatore delle ricerche.
@MainActor
final class ScambiModiTests: XCTestCase {
    func testIlContatoreInParole() {
        XCTAssertEqual(LimiteRicerche(restano: 3, tetto: 20).testo, "Ne restano 3 oggi su 20")
        XCTAssertEqual(LimiteRicerche(restano: 1, tetto: 20).testo, "Ne resta 1 oggi su 20")
        XCTAssertEqual(LimiteRicerche(restano: 0, tetto: 20).testo, "Ne restano 0 oggi su 20")
        XCTAssertNil(LimiteRicerche(restano: nil, tetto: nil).testo, "l'amministratore non ha un limite: nessun contatore")
        XCTAssertNil(LimiteRicerche(restano: 3, tetto: nil).testo)
    }

    func testIlContatoreSiLegge() async {
        let s = ServerDiProva { _, percorso, _ in
            if percorso == "/api/scambi/limite" { return Data(#"{"restano": 17, "tetto": 20}"#.utf8) }
            throw ErroreApi.server("niente")
        }
        let vm = ScambiViewModel(server: s)
        XCTAssertNil(vm.limite)
        await vm.caricaLimite()
        XCTAssertEqual(vm.limite?.restano, 17)
        XCTAssertEqual(s.quante("GET /api/scambi/limite"), 1)
    }

    func testAdminSenzaLimiteENessunContatore() async {
        let s = ServerDiProva { _, _, _ in Data(#"{"restano": null, "tetto": null}"#.utf8) }
        let vm = ScambiViewModel(server: s)
        await vm.caricaLimite()
        XCTAssertNil(vm.limite?.testo)
    }

    func testUnServerSenzaLaRottaNonRompe() async {
        let vm = ScambiViewModel(server: ServerDiProva.chePrecipita())
        await vm.caricaLimite()
        XCTAssertNil(vm.limite)
    }

    func testLaRispostaDelleProposteAggiornaIlContatore() async {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scambi/proposte") { return Data(#"{"proposte": [], "ricerche": {"restano": 4, "tetto": 20}}"#.utf8) }
            throw ErroreApi.server("niente")
        }
        let vm = ScambiViewModel(server: s)
        await vm.caricaProposte()
        XCTAssertEqual(vm.limite?.restano, 4)
        XCTAssertEqual(s.quante("/api/scambi/limite"), 0, "il contatore e' gia' nella risposta: niente richiesta in piu'")
    }

    func testITreModi() {
        XCTAssertEqual(ModoScambi.allCases.map(\.rawValue), ["Trova per me", "Costruisci", "Valuta un'offerta"])
        XCTAssertEqual(ScambiViewModel(server: ServerDiProva.chePrecipita()).modo, .trova)
    }
}
