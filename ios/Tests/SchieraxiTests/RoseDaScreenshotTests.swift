import XCTest
@testable import Schieraxi

/// Rose dagli screenshot di Leghe: ricostruzione di righe e squadre da parole OCR SIMULATE.
/// Squadre, proprietari e calciatori INVENTATI; le posizioni imitano la schermata «Dettaglio squadra» (misure in larghezze).
final class RoseDaScreenshotTests: XCTestCase {
    struct Finto {
        let ruolo: String, nome: String, club: String, q: Int, fvm: Int, costo: Int
        init(_ ruolo: String, _ nome: String, _ club: String, _ q: Int, _ fvm: Int, _ costo: Int) {
            self.ruolo = ruolo; self.nome = nome; self.club = club; self.q = q; self.fvm = fvm; self.costo = costo
        }
    }

    static let proporzione = 2.176          // 1184 x 2576, come uno screenshot di iPhone
    static let cima = 0.654                 // fine dell'intestazione della tabella: sopra, le righe sono nascoste
    static let passo = 0.194                // da una scheda all'altra

    /// Parole di una scritta, una per parola, con larghezze proporzionate ai caratteri.
    static func parole(_ testo: String, x: Double, y: Double, h: Double) -> [ParolaLetta] {
        var risultato: [ParolaLetta] = []
        var cx = x
        for p in testo.split(separator: " ") {
            let w = Double(p.count) * 0.62 * h
            risultato.append(ParolaLetta(testo: String(p), x: cx, y: y, larghezza: w, altezza: h))
            cx += w + 0.3 * h
        }
        return risultato
    }

    /// Uno screenshot finto: intestazione fissa, poi le schede a partire da `inizio` (spostato per simulare lo scorrimento).
    static func pagina(squadra: String = "Atletico Pigiama", proprietario: String = "Gianni", crediti: Int? = 7,
                       giocatori: [Finto], inizio: Double = 0.72, colori: Bool = true, lettere: Bool = false,
                       figurine: Bool = true) -> PaginaScreenshot {
        var p: [ParolaLetta] = []
        p += parole("10:54", x: 0.123, y: 0.062, h: 0.034)
        p += parole("Lega Inventata", x: 0.134, y: 0.165, h: 0.029)
        p += parole("DETTAGLIO SQUADRA", x: 0.133, y: 0.208, h: 0.024)
        p += parole(squadra, x: 0.336, y: 0.335, h: 0.033)
        p += parole(proprietario, x: 0.335, y: 0.392, h: 0.022)
        if let crediti { p += parole(String(crediti), x: 0.93, y: 0.335, h: 0.03) }
        p += parole("CREDITI", x: 0.846, y: 0.392, h: 0.023)
        p += parole("Rosa", x: 0.211, y: 0.534, h: 0.03)
        p += parole("Calendario e risultati", x: 0.569, y: 0.533, h: 0.031)
        p += parole("Calciatore", x: 0.041, y: 0.63, h: 0.02)
        p += parole("Q. att.", x: 0.593, y: 0.632, h: 0.022)
        p += parole("FVMp", x: 0.733, y: 0.632, h: 0.022)
        p += parole("V. Acq.", x: 0.861, y: 0.632, h: 0.022)
        var striscia = [String?](repeating: nil, count: 1000)
        func visibile(_ y: Double, _ h: Double) -> Bool { y >= cima && y + h <= proporzione }
        for (k, g) in giocatori.enumerated() {
            let y = inizio + Double(k) * passo
            if visibile(y, 0.028) { p += parole(g.nome, x: 0.231, y: y, h: 0.028) }
            if visibile(y + 0.051, 0.02) { p += parole(g.club, x: 0.231, y: y + 0.051, h: 0.02) }
            for (n, centro) in zip([g.q, g.fvm, g.costo], [0.629, 0.766, 0.902]) where visibile(y + 0.027, 0.021) {
                let w = Double(String(n).count) * 0.015
                p.append(ParolaLetta(testo: String(n), x: centro - w / 2, y: y + 0.027, larghezza: w, altezza: 0.021))
            }
            if figurine, visibile(y - 0.02, 0.06) {      // scritte della figurina: grandi e storte, a sinistra
                p.append(ParolaLetta(testo: "agi", x: 0.092, y: y - 0.02, larghezza: 0.06, altezza: 0.065))
                p.append(ParolaLetta(testo: "17", x: 0.09, y: y + 0.02, larghezza: 0.02, altezza: 0.012))
            }
            let pallino = y + 0.014 - 0.033
            if lettere, visibile(pallino - 0.01, 0.02) {
                p.append(ParolaLetta(testo: g.ruolo, x: 0.04, y: pallino - 0.01, larghezza: 0.015, altezza: 0.02))
            }
            if colori, pallino - 0.015 >= cima, pallino + 0.015 < proporzione {
                let da = Int((pallino - 0.015) / proporzione * 1000), a = Int((pallino + 0.015) / proporzione * 1000)
                for i in max(0, da)...min(999, a) { striscia[i] = g.ruolo }
            }
        }
        return PaginaScreenshot(parole: p, proporzione: proporzione, strisciaRuoli: striscia)
    }

    static let cognomi = ["Abeti", "Brunetto", "Corsini", "Dalmasso", "Esteri", "Fabbroni", "Galletti", "Iorio", "Lentini",
                          "Mauriello", "Nardoni", "Olmetto", "Pacetti", "Quartieri", "Rizzuto", "Sartorio", "Tosatti",
                          "Ugolotti", "Vallardi", "Zannoni", "Arpini", "Bellucco", "Cirillo", "Donnini", "Ferrandi"]

    static let difficili: [Finto] = [
        Finto("P", "Porticelli", "Genoa", 9, 7, 1),
        Finto("D", "N'Gorra", "Roma", 12, 20, 12),
        Finto("D", "Lucimì", "Fiorentina", 8, 10, 3),
        Finto("D", "Bianchi Al.", "Venezia", 5, 4, 1),
        Finto("D", "Edervan D.S.", "Atalanta", 14, 22, 18),
        Finto("C", "Soulèt", "Roma", 16, 30, 25),
        Finto("C", "Kavè M.", "Udinese", 7, 6, 2),
        Finto("C", "Nicolosi Cavaglia", "Parma", 6, 5, 1),
        Finto("C", "Zambi Angossa", "Napoli", 9, 13, 2),
        Finto("A", "Espinaldo F.P.", "Inter", 20, 45, 86),
        Finto("A", "Kolo Muaro", "Juventus", 19, 40, 152),
        Finto("A", "Milanovic-Savor V.", "Torino", 11, 12, 9),
    ]

    // MARK: una pagina

    func testUnaPaginaNomeSquadraCreditiERighe() throws {
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(Self.pagina(giocatori: Array(Self.difficili.prefix(5)))))
        XCTAssertEqual(r.squadra, "Atletico Pigiama", "il proprietario sotto non c'entra")
        XCTAssertEqual(r.crediti, 7)
        XCTAssertEqual(r.righe.map(\.nome), ["Porticelli", "N'Gorra", "Lucimì", "Bianchi Al.", "Edervan D.S."])
        XCTAssertEqual(r.righe.map(\.ruolo), ["P", "D", "D", "D", "D"], "ruolo dal colore del pallino")
        XCTAssertEqual(r.righe.map(\.club), ["Genoa", "Roma", "Fiorentina", "Venezia", "Atalanta"])
        XCTAssertEqual(r.righe.map(\.costo), [1, 12, 3, 1, 18], "il prezzo è la colonna «V. Acq.»")
        XCTAssertEqual(r.righe.first?.quotazione, 9)
        XCTAssertEqual(r.righe.first?.fvm, 7)
        XCTAssertFalse(r.righe.contains { $0.nome.contains("agi") }, "le scritte della figurina si ignorano")
    }

    func testNomiDifficiliRestanoComeScritti() throws {
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(Self.pagina(giocatori: Array(Self.difficili.suffix(7)), inizio: 0.69)))
        XCTAssertEqual(r.righe.map(\.nome), ["Soulèt", "Kavè M.", "Nicolosi Cavaglia", "Zambi Angossa", "Espinaldo F.P.",
                                            "Kolo Muaro", "Milanovic-Savor V."])
        XCTAssertEqual(r.righe.map(\.costo), [25, 2, 1, 2, 86, 152, 9])
    }

    func testNomeSquadraConVirgolaENumeriEProprietarioMinuscolo() throws {
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(Self.pagina(squadra: "FC RISERVE 17,5", proprietario: "jack",
                                                                giocatori: Array(Self.difficili.prefix(2)))))
        XCTAssertEqual(r.squadra, "FC RISERVE 17,5")
        let s = try XCTUnwrap(RoseDaScreenshot.leggi(Self.pagina(squadra: "Real Pigiama", proprietario: "Lupo",
                                                                giocatori: Array(Self.difficili.prefix(2)))))
        XCTAssertEqual(s.squadra, "Real Pigiama", "un proprietario che è una parola comune non diventa la squadra")
        XCTAssertFalse(s.righe.contains { $0.nome == "Lupo" })
    }

    func testRuoloDallaLetteraSeIlColoreManca() throws {
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(Self.pagina(giocatori: Array(Self.difficili.prefix(3)), colori: false, lettere: true)))
        XCTAssertEqual(r.righe.map(\.ruolo), ["P", "D", "D"])
    }

    func testNonELaRosaDiLeghe() {
        let p = PaginaScreenshot(parole: Self.parole("Una foto qualsiasi", x: 0.1, y: 0.5, h: 0.03), proporzione: 2)
        XCTAssertNil(RoseDaScreenshot.leggi(p))
    }

    func testNumeriLettiInUnPezzoSolo() throws {
        var p = Self.pagina(giocatori: [Self.difficili[0]], figurine: false)
        p.parole.removeAll { RoseDaScreenshot.eNumero($0.testo) && $0.x > 0.5 && $0.y > 0.7 }
        p.parole.append(ParolaLetta(testo: "9 7 1", x: 0.6215, y: 0.747, larghezza: 0.2885, altezza: 0.021))
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(p))
        XCTAssertEqual(r.righe.first?.quotazione, 9)
        XCTAssertEqual(r.righe.first?.costo, 1)
    }

    func testRigaTagliataInCimaSiScarta() throws {
        // la prima scheda ha il nome nascosto sotto l'intestazione: si vede solo la squadra di Serie A
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(Self.pagina(giocatori: Array(Self.difficili.prefix(3)), inizio: 0.62)))
        XCTAssertEqual(r.righe.map(\.nome), ["N'Gorra", "Lucimì"])
        XCTAssertEqual(r.illeggibili, 0, "la riga tagliata in cima non è un errore: si legge nello screenshot prima")
    }

    func testRigaTagliataInFondoEParziale() throws {
        // l'ultima scheda si vede solo fino al nome: niente squadra di Serie A né numeri
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(Self.pagina(giocatori: Array(Self.difficili.prefix(9)), inizio: 0.58)))
        let ultima = try XCTUnwrap(r.righe.last)
        XCTAssertEqual(ultima.nome, "Zambi Angossa")
        XCTAssertTrue(ultima.parziale)
        XCTAssertNil(ultima.club)
        XCTAssertNil(ultima.costo)
    }

    func testNomeNonLettoInMezzoSiConta() throws {
        var p = Self.pagina(giocatori: Array(Self.difficili.prefix(4)))
        p.parole.removeAll { $0.testo == "Lucimì" }
        let r = try XCTUnwrap(RoseDaScreenshot.leggi(p))
        XCTAssertEqual(r.illeggibili, 1)
        XCTAssertFalse(r.righe.contains { $0.nome == "Fiorentina" }, "la squadra di Serie A non diventa un giocatore")
    }

    // MARK: più screenshot

    /// Una rosa intera in 4 screenshot sovrapposti, come scorrendo.
    func testScreenshotSovrappostiSenzaDoppioni() throws {
        let rosa = (0..<25).map { i -> Finto in
            let ruolo = i < 3 ? "P" : i < 11 ? "D" : i < 19 ? "C" : "A"
            return Finto(ruolo, Self.cognomi[i], ["Como", "Lecce", "Pisa"][i % 3], i + 1, i + 2, i * 3 + 1)
        }
        let pagine = [0.72, -0.6, -1.95, -3.3].compactMap { RoseDaScreenshot.leggi(Self.pagina(giocatori: rosa, inizio: $0)) }
        let squadre = RoseDaScreenshot.unisci(pagine)
        XCTAssertEqual(squadre.count, 1)
        let s = try XCTUnwrap(squadre.first)
        XCTAssertEqual(s.foto, 4)
        XCTAssertEqual(s.righe.map(\.nome), rosa.map(\.nome), "tutti, una volta sola, in ordine")
        XCTAssertEqual(s.righe.map(\.ruolo), rosa.map { Optional($0.ruolo) })
        XCTAssertEqual(s.righe.map(\.costo), rosa.map { Optional($0.costo) }, "le righe tagliate prendono i numeri dallo screenshot dopo")
        XCTAssertTrue(s.righe.allSatisfy { !$0.parziale })
    }

    func testPiuSquadreInUnCaricamentoENomeLettoConUnaLetteraDiversa() {
        let a = Self.pagina(squadra: "Real Pigiama", giocatori: Array(Self.difficili.prefix(4)))
        let b = Self.pagina(squadra: "Sporting Ciabatta", giocatori: Array(Self.difficili.suffix(3)))
        let a2 = Self.pagina(squadra: "Real Pigiarna", giocatori: Array(Self.difficili.prefix(6)), inizio: 0.72 - 2 * Self.passo)
        let squadre = RoseDaScreenshot.unisci([a, b, a2].compactMap(RoseDaScreenshot.leggi), esistenti: ["sporting ciabatta"])
        XCTAssertEqual(squadre.map(\.nome), ["Real Pigiama", "sporting ciabatta"], "il nome salvato vince su quello letto")
        XCTAssertEqual(squadre.first?.righe.count, 6)
    }

    func testOmonimiConNumeriDiversiRestanoDue() {
        let due = [Finto("A", "Morenez Jo.", "Inter", 10, 12, 30), Finto("A", "Morenez Ju.", "Inter", 4, 3, 1)]
        let squadre = RoseDaScreenshot.unisci([Self.pagina(giocatori: due)].compactMap(RoseDaScreenshot.leggi))
        XCTAssertEqual(squadre.first?.righe.map(\.nome), ["Morenez Jo.", "Morenez Ju."])
    }

    func testRuoliMancantiDallOrdineDiLeghe() {
        var righe = [RigaScreenshot(nome: "Uno", ruolo: nil), RigaScreenshot(nome: "Due", ruolo: "P"),
                     RigaScreenshot(nome: "Tre", ruolo: "D"), RigaScreenshot(nome: "Quattro", ruolo: nil),
                     RigaScreenshot(nome: "Cinque", ruolo: "D"), RigaScreenshot(nome: "Sei", ruolo: "C"),
                     RigaScreenshot(nome: "Sette", ruolo: nil), RigaScreenshot(nome: "Otto", ruolo: "A"),
                     RigaScreenshot(nome: "Nove", ruolo: nil)]
        RoseDaScreenshot.riempiRuoli(&righe)
        XCTAssertEqual(righe.map(\.ruolo), ["P", "P", "D", "D", "D", "C", nil, "A", "A"], "tra C e A non si indovina")
    }

    func testColoriDeiPallini() {
        XCTAssertEqual(RoseDaScreenshot.ruolo(rosso: 0.95, verde: 0.66, blu: 0.19), "P")
        XCTAssertEqual(RoseDaScreenshot.ruolo(rosso: 0.49, verde: 0.70, blu: 0.26), "D")
        XCTAssertEqual(RoseDaScreenshot.ruolo(rosso: 0.16, verde: 0.38, blu: 1.0), "C")
        XCTAssertEqual(RoseDaScreenshot.ruolo(rosso: 0.90, verde: 0.22, blu: 0.21), "A")
        XCTAssertNil(RoseDaScreenshot.ruolo(rosso: 0.96, verde: 0.96, blu: 0.98), "bianco della scheda")
        XCTAssertNil(RoseDaScreenshot.ruolo(rosso: 0.1, verde: 0.1, blu: 0.12), "fondo scuro")
    }

    func testSquadraDiSerieALettaMale() {
        XCTAssertEqual(RoseDaScreenshot.squadraSerieA("Caqliari"), "Cagliari")
        XCTAssertEqual(RoseDaScreenshot.squadraSerieA("Juventus"), "Juventus")
        XCTAssertNil(RoseDaScreenshot.squadraSerieA("Pigiama"))
    }

    // MARK: testo per il server e avvisi

    func testTestoNelFormatoDelleSchermate() {
        let s = SquadraScreenshot(nome: "FC RISERVE 17,5", crediti: 3, righe: [
            RigaScreenshot(nome: "N'Gorra", club: "Roma", ruolo: "D", costo: 12),
            RigaScreenshot(nome: "Kolo Muaro", club: nil, ruolo: "A", costo: nil),
            RigaScreenshot(nome: "Senza Ruolo", club: "Pisa", ruolo: nil, costo: 4),
        ])
        let vuota = SquadraScreenshot(nome: "Solo Dubbi", crediti: nil, righe: [RigaScreenshot(nome: "Uno", ruolo: nil)])
        XCTAssertEqual(RoseDaScreenshot.testo([s, vuota]),
                       "ruolo;nome;club;prezzo\nFC RISERVE 17,5\nD;N'Gorra;Roma;12\nA;Kolo Muaro;;\ncrediti;3\n",
                       "senza ruolo il server scarterebbe la riga: resta fuori (e lo dicono gli avvisi)")
        let conPuntoEVirgola = SquadraScreenshot(nome: "Real;Pigiama", crediti: nil, righe: [RigaScreenshot(nome: "Rossi;Al.", ruolo: "C")])
        XCTAssertEqual(RoseDaScreenshot.testo([conPuntoEVirgola]), "ruolo;nome;club;prezzo\nReal,Pigiama\nC;Rossi,Al.;;\n",
                       "il punto e virgola non entra nelle celle")
    }

    func testAvvisiERiassuntoConIPlurali() {
        let s = SquadraScreenshot(nome: "Real Pigiama", crediti: nil, righe: [
            RigaScreenshot(nome: "Uno", ruolo: "D", costo: nil), RigaScreenshot(nome: "Due", ruolo: "C", costo: 4),
            RigaScreenshot(nome: "Tre", ruolo: nil, costo: 2),
        ], illeggibili: 2, foto: 3)
        XCTAssertEqual(RoseDaScreenshot.riassunto([s]), "Ho letto 1 squadra e 2 giocatori da 3 foto.")
        XCTAssertEqual(RoseDaScreenshot.avvisi([s], scartate: 1), [
            "1 foto non sembra la rosa di una squadra di Leghe: l'ho saltata.",
            "«Real Pigiama»: in 2 righe non leggo il nome. Controlla nell'anteprima chi manca.",
            "«Real Pigiama»: non leggo il ruolo di Tre: l'ho lasciato fuori. Rifai lo screenshot di quella parte.",
            "«Real Pigiama»: non leggo il prezzo di 1 giocatore.",
        ])
    }

    // MARK: ViewModel

    @MainActor
    func testDalleFotoAllAnteprimaConIlTestoRicostruito() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/rose/anteprima") { return Data(AnteprimaRoseTests.risposta.utf8) }
            if percorso.hasPrefix("/api/squadre") { return Data(#"[{"nome": "Real Fantasia"}]"#.utf8) }
            throw ErroreApi.server("non previsto")
        }
        let vm = ImportaExcelViewModel(server: s)
        await vm.usaPagine([Self.pagina(squadra: "Real Fantasla", giocatori: Array(Self.difficili.prefix(3))), nil])
        XCTAssertNil(vm.errore)
        XCTAssertNotNil(vm.anteprima)
        let corpo = try XCTUnwrap(JSONSerialization.jsonObject(with: try XCTUnwrap(s.corpiInviati(a: "/api/rose/anteprima").last)) as? [String: Any])
        let testo = try XCTUnwrap(corpo["testo"] as? String)
        XCTAssertTrue(testo.hasPrefix("ruolo;nome;club;prezzo\nReal Fantasia\n"), "intestazione, poi il nome della squadra salvata")
        XCTAssertTrue(testo.contains("\nD;N'Gorra;Roma;12\n"))
        XCTAssertTrue(testo.hasSuffix("\ncrediti;7"), "a capo finale tolto prima di inviare")
        XCTAssertEqual(vm.avvisiFoto.first, "Ho letto 1 squadra e 3 giocatori da 1 foto.")
        XCTAssertTrue(vm.avvisiFoto.contains("1 foto non sembra la rosa di una squadra di Leghe: l'ho saltata."))
    }

    @MainActor
    func testFotoSenzaRoseDiconoCosaServe() async {
        let s = ServerDiProva { _, _, _ in throw ErroreApi.server("non previsto") }
        let vm = ImportaExcelViewModel(server: s)
        await vm.usaPagine([PaginaScreenshot(parole: Self.parole("Spiaggia", x: 0.3, y: 0.4, h: 0.03), proporzione: 2)])
        XCTAssertEqual(vm.errore, ImportaExcelViewModel.nienteNelleFoto)
        XCTAssertEqual(s.quante("/api/rose/anteprima"), 0, "niente al server")
    }
}
