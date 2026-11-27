import Foundation
import Testing
@testable import Schieraxi

/// La pagina Giornate (#673, passo 2), come `mostraGiornate` della web (#617/#671): la formazione che conta, la frase sotto la riga
/// (il confronto con la consigliata solo con `consigliata.origine: "mostrata"`), gli 11 con l'atteso mostrato prima della scadenza e
/// il preso, «senza voto», la pagina vuota secondo `motivo_vuoto`, la correzione solo dove si può, la frase del server sulla
/// consigliata di allora (`nota_consigliata`, #674), la differenza fra punti fatti e attesi e chi ha fatto meglio o peggio del previsto
/// (`fatti_e_attesi`, #672 e #705). Le fixture `diario-giornate.json` (server di adesso, con i campi della #642, della #674 e della
/// #672, le frasi come le scrivono `diario.nota_consigliata` e `diario.fatti_e_attesi`) e `diario-giornate-vecchio.json` (server di
/// prima, senza `origine`, `automatica`, `giocatori` e `fatti_e_attesi`) sono dati inventati. I testi fissi si confrontano con il
/// catalogo comune (`Catalogo.Giornate`), le frasi del server con quelle della fixture.
@MainActor
struct GiornateTests {
    private func pagina(_ fixture: String) throws -> PaginaGiornate {
        PaginaGiornate(try Fixture.decodifica(fixture) as DiarioRisposta)
    }

    private func riga(_ p: PaginaGiornate, _ giornata: Int, stagione: String = "2026-27") throws -> RigaGiornata {
        try #require(p.righe.first { $0.id == "\(stagione)-\(giornata)" }, "manca la giornata \(giornata) \(stagione)")
    }

    private func dettaglio(_ p: PaginaGiornate, _ giornata: Int, stagione: String = "2026-27") throws -> DettaglioGiornata {
        try #require(p.dettaglio("\(stagione)-\(giornata)"), "manca il dettaglio della giornata \(giornata)")
    }

    // MARK: la formazione che conta

    @Test("La formazione che conta: la tua, poi la copia alla scadenza, poi la consigliata")
    func formazioneCheConta() throws {
        let d: DiarioRisposta = try Fixture.decodifica("diario-giornate")
        let voci = try #require(d.giornate)
        let tipi = voci.map { $0.cheConta.tipo }
        #expect(tipi == [.tua, .tua, .automatica, .consigliata, .tua, .tua, .consigliata])
        #expect(voci.map { $0.cheConta.formazione?.reale } == [74.5, 68.0, 71.0, 78.5, 64.0, 70.0, 61.5])
    }

    @Test("Le righe vanno dalla più recente, con i punti fatti e «punti (attesi …)» della formazione che conta")
    func righe() throws {
        let p = try pagina("diario-giornate")
        #expect(p.righe.count == 7)
        let r = try riga(p, 11)
        #expect(r.nome == "Giornata 8 · 11ª di Serie A")
        #expect(r.punti == "74,5")
        #expect(r.attesi == Catalogo.Formazione.puntiEAttesi(n: "71,7"))
        // senza punti attesi resta «punti», come la web
        #expect(try riga(p, 7).attesi == Catalogo.Formazione.punti)
        // con due stagioni nella pagina VoiceOver dice anche la stagione, e di quanto i punti sono sopra o sotto gli attesi
        #expect(r.voce == "Giornata 8, 11ª di Serie A, 2026-27: 74,5 \(Catalogo.Formazione.puntiEAttesi(n: "71,7")), "
                + "\(Catalogo.Giornate.sulPrevisto(d: "+2,8")). \(r.stato)")
        // senza `fatti_e_attesi` la frase resta quella di prima
        #expect(try riga(p, 7).voce.hasSuffix(": 64,0 \(Catalogo.Formazione.punti). \(Catalogo.Giornate.tua)"))
    }

    @Test("Con due stagioni nella pagina la riga dice la stagione; con una sola no")
    func stagione() throws {
        let p = try pagina("diario-giornate")
        #expect(try riga(p, 38, stagione: "2025-26").stagione == "2025-26")
        #expect(try riga(p, 38, stagione: "2025-26").nome == "38ª giornata di Serie A")
        #expect(try riga(p, 11).stagione == "2026-27")
        let una = try pagina("diario-giornate-vecchio")
        #expect(una.righe.allSatisfy { $0.stagione == nil })
    }

    // MARK: la frase sotto la riga

    @Test("Con la consigliata mostrata: hai schierato la consigliata, o quanti cambi e quanto sono valsi")
    func fraseConLaConsigliataMostrata() throws {
        let p = try pagina("diario-giornate")
        #expect(try riga(p, 11).stato == Catalogo.Giornate.cambi(2, d: "\u{2212}1,5"))
        #expect(try riga(p, 11).stato == "2 cambi tuoi: −1,5 punti rispetto alla consigliata.")
        #expect(try riga(p, 10).stato == Catalogo.Giornate.haiConsigliata)
        #expect(try riga(p, 6).stato == Catalogo.Giornate.cambiPari(1))
    }

    @Test("Senza la consigliata mostrata: solo di chi sono i punti")
    func fraseSenzaConfronto() throws {
        let p = try pagina("diario-giornate")
        #expect(try riga(p, 9).stato == Catalogo.Giornate.automatica)
        #expect(try riga(p, 8).stato == Catalogo.Giornate.nonSalvata)
        #expect(try riga(p, 7).stato == Catalogo.Giornate.tua)
        #expect(try riga(p, 38, stagione: "2025-26").stato == Catalogo.Giornate.nonSalvata)
    }

    @Test("Un server di prima, senza `origine`: niente confronto anche con «Le tue scelte» piene")
    func serverDiPrimaSenzaOrigine() throws {
        let p = try pagina("diario-giornate-vecchio")
        #expect(try riga(p, 11).stato == Catalogo.Giornate.tua)
        #expect(try riga(p, 10).stato == Catalogo.Giornate.nonSalvata)
        let d = try dettaglio(p, 11)
        #expect(d.titolo == Catalogo.Giornate.formazioneTua(modulo: "4-4-2"))
        #expect(d.cambi == nil)
        #expect(d.senzaConfronto == nil, "senza `origine` non si sa se la consigliata era quella mostrata")
        let consigliata = try dettaglio(p, 10)
        #expect(consigliata.titolo == Catalogo.Giornate.formazioneRifatta(modulo: "4-3-3"))
        #expect(consigliata.nota == nil)
        // senza `giocatori` atteso e preso non si sanno: «–», mai «senza voto»
        #expect(d.titolari.map(\.atteso) == ["–", "–"])
        #expect(d.titolari.map(\.preso) == ["–", "–"])
        #expect(d.titolari.allSatisfy { !$0.senzaVoto })
        #expect(d.correggibile, "senza `modificabile` la correzione c'è, come prima")
    }

    // MARK: gli 11

    @Test("Gli 11: l'atteso mostrato prima della scadenza (titolari e panchina), se no quello rifatto; il preso o «senza voto»")
    func titolari() throws {
        let d = try dettaglio(try pagina("diario-giornate"), 11)
        #expect(d.titolo == Catalogo.Giornate.formazioneTua(modulo: "4-4-2"))
        #expect(d.titolari.map(\.nome) == ["Portiere Uno", "Difensore Quattro", "Attaccante Cinque"])
        #expect(d.titolari.map(\.ruolo) == ["P", "D", "A"])
        #expect(d.titolari.map(\.atteso) == ["6,1", "5,8", "6,9"], "6,1 e 5,8 dall'istantanea (anche dalla panchina), 6,9 rifatto")
        #expect(d.titolari.map(\.preso) == ["5,5", "6,5", Catalogo.Giornate.senzaVoto])
        #expect(d.titolari.map(\.senzaVoto) == [false, false, true])
        #expect(d.titolari[2].voce == "Attaccante Cinque, attaccante: atteso 6,9, preso senza voto.")
    }

    @Test("Un titolare senza numeri dal server: «–» per atteso e preso")
    func titolareSenzaNumeri() throws {
        let d = try dettaglio(try pagina("diario-giornate"), 8)
        let t = try #require(d.titolari.last)
        #expect(t.nome == "Senza Numeri")
        #expect(t.atteso == "–")
        #expect(t.preso == "–")
        #expect(!t.senzaVoto)
    }

    @Test("Cosa hai cambiato: i nomi del server, solo con la consigliata mostrata")
    func cambi() throws {
        let p = try pagina("diario-giornate")
        #expect(try dettaglio(p, 11).cambi == Catalogo.Giornate.alPosto(dentro: "Difensore Quattro, Attaccante Cinque",
                                                                         fuori: "Difensore Due, Attaccante Tre"))
        #expect(try dettaglio(p, 10).cambi == nil, "stessi undici della consigliata")
        // la tua formazione con la consigliata rifatta: il confronto non c'è, e lo dice la frase del server, sotto la tabella
        let rifatta = try dettaglio(p, 7)
        #expect(rifatta.cambi == nil)
        #expect(rifatta.senzaConfronto
                == "Qui il confronto con la consigliata non c'è: quella mostrata prima della scadenza non era stata salvata.")
        #expect(rifatta.nota == nil)
        #expect(try dettaglio(p, 11).senzaConfronto == nil, "con la consigliata mostrata il confronto c'è")
    }

    @Test("Il titolo dice di chi è la formazione; sotto la consigliata rifatta la frase del server")
    func titoli() throws {
        let p = try pagina("diario-giornate")
        #expect(try dettaglio(p, 9).titolo == Catalogo.Giornate.formazioneAutomatica(modulo: "4-4-2"))
        #expect(try dettaglio(p, 9).nota == nil)
        let rifatta = try dettaglio(p, 8)
        #expect(rifatta.titolo == Catalogo.Giornate.formazioneRifatta(modulo: "4-3-3"))
        #expect(rifatta.nota == "Questa è rifatta con i dati di allora: quella mostrata prima della scadenza non era stata salvata.")
        #expect(rifatta.senzaConfronto == nil)
    }

    @Test("Un server senza `nota_consigliata` (o con la frase vuota): nessuna frase sulla consigliata di allora, anche con `origine`")
    func senzaLaFraseDelServer() throws {
        let json = #"""
            {"giornate": [
              {"stagione": "2026-27", "giornata": 7, "consigliata": {"modulo": "4-3-3", "origine": "ricostruita", "titolari": []},
               "schierata": {"modulo": "3-5-2", "titolari": []}},
              {"stagione": "2026-27", "giornata": 6, "consigliata": {"modulo": "4-3-3", "origine": "ricostruita", "titolari": []},
               "nota_consigliata": "  "}
            ]}
            """#
        let p = PaginaGiornate(try Decodifica.decodifica(Data(json.utf8)))
        let tua = try dettaglio(p, 7)
        #expect(tua.titolo == Catalogo.Giornate.formazioneTua(modulo: "3-5-2"))
        #expect(tua.senzaConfronto == nil && tua.nota == nil, "l'app non scrive frasi sue sulla consigliata di allora")
        let rifatta = try dettaglio(p, 6)
        #expect(rifatta.titolo == Catalogo.Giornate.formazioneRifatta(modulo: "4-3-3"))
        #expect(rifatta.nota == nil, "una frase vuota vale come nessuna frase")
    }

    // MARK: fatti contro attesi (#672, #705)

    @Test("La riga dice di quanto i punti fatti sono sopra o sotto gli attesi: la differenza del server, con il segno")
    func sulPrevisto() throws {
        let p = try pagina("diario-giornate")
        #expect(try riga(p, 11).sulPrevisto == Catalogo.Giornate.sulPrevisto(d: "+2,8"))
        #expect(try riga(p, 11).sulPrevisto == "+2,8 sul previsto")
        #expect(try riga(p, 10).sulPrevisto == "\u{2212}2,0 sul previsto")
        #expect(try riga(p, 9).sulPrevisto == "+1,5 sul previsto", "anche con la copia alla scadenza")
        #expect(try riga(p, 6).sulPrevisto == "\u{2212}0,1 sul previsto")
        #expect(try riga(p, 38, stagione: "2025-26").sulPrevisto == "\u{2212}6,5 sul previsto")
        // la tua formazione senza punti attesi: il server manda `fatti_e_attesi: null` e la riga non lo dice
        #expect(try riga(p, 7).sulPrevisto == nil)
    }

    @Test("A zero «come previsto»; senza una differenza del server niente, anche con i punti fatti e attesi")
    func comePrevistoESenzaDifferenza() throws {
        let json = #"""
            {"giornate": [
              {"stagione": "2026-27", "giornata": 9, "schierata": {"modulo": "4-4-2", "atteso": 70.0, "reale": 70.0, "titolari": []},
               "fatti_e_attesi": {"formazione": "schierata", "atteso": 70.0, "fatti": 70.0, "differenza": 0.0, "meglio": [], "peggio": [],
                                  "testo": null, "frase": null}},
              {"stagione": "2026-27", "giornata": 8, "schierata": {"modulo": "4-4-2", "atteso": 70.0, "reale": 75.0, "titolari": []},
               "fatti_e_attesi": {"differenza": "+5,0", "testo": "  "}},
              {"stagione": "2026-27", "giornata": 7, "schierata": {"modulo": "4-4-2", "atteso": 70.0, "reale": 75.0, "titolari": []},
               "fatti_e_attesi": "boh"},
              {"stagione": "2026-27", "giornata": 6, "schierata": {"modulo": "4-4-2", "atteso": 70.0, "reale": 75.0, "titolari": []}}
            ]}
            """#
        let p = PaginaGiornate(try Decodifica.decodifica(Data(json.utf8)))
        #expect(try riga(p, 9).sulPrevisto == Catalogo.Giornate.comePrevisto)
        #expect(try riga(p, 9).sulPrevisto == "come previsto")
        for g in [8, 7, 6] {
            #expect(try riga(p, g).sulPrevisto == nil, "giornata \(g): l'app non fa la differenza da sé")
            #expect(try dettaglio(p, g).scarti == nil, "giornata \(g): nessuna frase sua")
            #expect(try riga(p, g).punti == "75,0", "giornata \(g): un `fatti_e_attesi` strano non rompe la riga")
        }
    }

    @Test("Nella giornata aperta la frase del server su chi ha fatto meglio o peggio del previsto, così com'è")
    func meglioEPeggio() throws {
        let p = try pagina("diario-giornate")
        #expect(try dettaglio(p, 6).scarti == "Meglio del previsto: Portiere Uno (+1,5). Peggio: Difensore Quattro (\u{2212}1,7).")
        #expect(try dettaglio(p, 9).scarti == "Meglio del previsto: Portiere Uno (+2,1).", "anche con la copia alla scadenza")
        let rifatta = try dettaglio(p, 38, stagione: "2025-26")
        #expect(rifatta.scarti == "Peggio del previsto: Portiere Uno (\u{2212}2,5).")
        #expect(rifatta.nota != nil, "con la consigliata rifatta ci sono tutte e due le frasi del server")
        // nessuno a un punto dal suo atteso: il server manda `testo: null`, e la frase non c'è
        #expect(try dettaglio(p, 11).scarti == nil)
        #expect(try dettaglio(p, 7).scarti == nil, "`fatti_e_attesi: null`")
    }

    @Test("Un server di prima, senza `fatti_e_attesi`: niente differenza nella riga né frase nella giornata aperta")
    func serverDiPrimaSenzaFattiEAttesi() throws {
        let p = try pagina("diario-giornate-vecchio")
        #expect(!p.righe.isEmpty)
        #expect(p.righe.allSatisfy { $0.sulPrevisto == nil })
        #expect(p.righe.allSatisfy { p.dettaglio($0.id)?.scarti == nil })
        #expect(try riga(p, 11).voce.hasSuffix("74,5 \(Catalogo.Formazione.puntiEAttesi(n: "71,7")). \(Catalogo.Giornate.tua)"))
    }

    @Test("«Non è quello che ho schierato» non c'è per le stagioni passate (`modificabile: false`)")
    func correggibile() throws {
        let p = try pagina("diario-giornate")
        #expect(try dettaglio(p, 11).correggibile)
        #expect(try !dettaglio(p, 38, stagione: "2025-26").correggibile)
    }

    /// Come `correggiGiornata` della web: il foglio spunta e conta solo chi è nella rosa letta adesso. Prima l'iPhone spuntava gli 11
    /// della riga anche con un titolare ceduto: il conto diceva «11 di 11», le spunte visibili erano 10, «Salva» dava l'errore del
    /// server e il giocatore nascosto non si poteva togliere. Giocatori e numeri inventati.
    @Test("«Non è quello che ho schierato» parte dai titolari ancora in rosa: un titolare ceduto non è spuntato né contato (#807)")
    func titolariInRosa() throws {
        let ruoli = ["P", "D", "D", "D", "D", "C", "C", "C", "A", "A", "A"]
        let titolari: [[String: Any]] = ruoli.enumerated().map { (i, ruolo) -> [String: Any] in
            ["id": i + 1, "nome": "Giocatore \(i + 1)", "ruolo": ruolo]
        }
        let corpo: [String: Any] = ["stagione": "2026-27", "giornata": 11, "schierata": ["modulo": "4-3-3", "titolari": titolari]]
        let voce: VoceDiario = try Decodifica.decodifica(JSONSerialization.data(withJSONObject: corpo))
        func giocatore(_ id: Int, _ ruolo: String?) -> GiocatoreRosa {
            GiocatoreRosa(id: id, nome: "Giocatore \(id)", ruolo: ruolo, squadra: nil, squadraSlug: nil, costo: nil, quotazione: nil,
                          previsione: nil)
        }
        // tutti ancora in rosa, più due in panchina: gli 11 della riga
        let rosa = ruoli.enumerated().map { (i, ruolo) in giocatore(i + 1, ruolo) } + [giocatore(12, "P"), giocatore(13, "D")]
        #expect(voce.titolariInRosa(rosa) == Set(1...11))
        // il 9 è stato ceduto dopo la giornata: non è nella rosa letta, quindi non è spuntato e il conto dice 10 di 11
        let senzaIl9 = rosa.filter { $0.id != 9 }
        #expect(voce.titolariInRosa(senzaIl9) == Set(1...11).subtracting([9]))
        #expect(voce.titolariInRosa(senzaIl9).count == 10)
        // il foglio elenca solo portieri, difensori, centrocampisti e attaccanti: chi non ha uno di questi ruoli non si vede, e non si spunta
        let senzaRuolo = rosa.map { $0.id == 6 ? giocatore(6, nil) : $0 }
        #expect(voce.titolariInRosa(senzaRuolo) == Set(1...11).subtracting([6]))
        // rosa non ancora letta: niente spunte
        #expect(voce.titolariInRosa([]).isEmpty)
    }

    // MARK: in cima e pagina vuota

    @Test("In cima la riga sulla precisione e «Dettagli»; la voce del confronto solo con una consigliata mostrata")
    func testa() throws {
        let p = try pagina("diario-giornate")
        #expect(p.precisione == Catalogo.Giornate.precisione(e: "1,4"))
        #expect(p.precisione == "Finora il fantavoto atteso sbaglia in media di 1,4 punti a giocatore.")
        #expect(p.titoloDettagli == Catalogo.Giornate.dettagli)
        let t = try #require(p.dettagli)
        #expect(t.confronto?.numero == Catalogo.Diario.qpKSuN(k: "1", n: "2"))
        #expect(t.nota == "1 giornata non entra nel confronto: la consigliata di allora non era stata salvata.")
        let vecchia = try #require(try pagina("diario-giornate-vecchio").dettagli)
        #expect(vecchia.confronto == nil, "senza consigliate mostrate il confronto non si mostra, come la web")
        #expect(vecchia.voci.count == 3)
    }

    @Test("Senza l'errore medio niente riga in cima: i dettagli si chiamano «Quanto ci abbiamo preso»")
    func testaSenzaErrore() throws {
        let d: DiarioRisposta = try Decodifica.decodifica(Data(#"{"giornate": [], "precisione": {"giornate": 2, "fantavoto": null}}"#.utf8))
        let p = PaginaGiornate(d)
        #expect(p.precisione == nil)
        #expect(p.titoloDettagli == Catalogo.Diario.afTitolo)
        let senza = PaginaGiornate(try Decodifica.decodifica(Data(#"{"giornate": []}"#.utf8)))
        #expect(senza.precisione == nil && senza.titoloDettagli == nil && senza.dettagli == nil)
    }

    @Test("La pagina vuota dice il motivo del server", arguments: [
        ("squadra", Catalogo.Giornate.vuotoSquadra(voce: Catalogo.Lega.miaSquadra)),
        ("giornate", Catalogo.Giornate.vuotoGiornate),
        ("calcolo", Catalogo.Giornate.vuotoCalcolo),
        ("boh", Catalogo.Giornate.vuoto),
    ])
    func vuota(motivo: String, frase: String) throws {
        let d: DiarioRisposta = try Decodifica.decodifica(Data(#"{"giornate": [], "motivo_vuoto": "\#(motivo)"}"#.utf8))
        let p = PaginaGiornate(d)
        #expect(p.righe.isEmpty)
        #expect(p.vuoto == frase)
    }

    @Test("Un server senza `motivo_vuoto`: la frase generica; con le giornate nessuna frase")
    func vuotaSenzaMotivo() throws {
        #expect(PaginaGiornate(try Decodifica.decodifica(Data(#"{"giornate": []}"#.utf8))).vuoto == Catalogo.Giornate.vuoto)
        #expect(try pagina("diario-giornate").vuoto == nil)
    }

    @Test("Una giornata che aspetta il recupero (`in_attesa`, revisione di #947): la frase del server, anche al posto della pagina vuota")
    func inAttesaDelRecupero() throws {
        let frase = "Giornata 9 · 12ª di Serie A: in attesa del recupero, i punti arrivano dopo."
        let json = #"{"giornate": [], "motivo_vuoto": "calcolo", "in_attesa": [{"stagione": "2026-27", "giornata": 12, "giornata_lega": 9, "testo": "\#(frase)", "frase": {"chiave": "diario.in_attesa_recupero"}}, {"giornata": 3, "testo": " "}]}"#
        let p = PaginaGiornate(try Decodifica.decodifica(Data(json.utf8)))
        #expect(p.inAttesa == [frase])
        #expect(p.vuoto == nil)
        #expect(PaginaGiornate(try Decodifica.decodifica(Data(#"{"giornate": []}"#.utf8))).inAttesa.isEmpty)
        #expect(try pagina("diario-giornate").inAttesa.isEmpty)
    }

    // MARK: la giornata da aprire

    @Test("«Com'è andata» apre la giornata della stagione in corso, la più recente con quel numero")
    func giornataDaAprire() throws {
        let p = try pagina("diario-giornate")
        #expect(p.id(giornata: 11) == "2026-27-11")
        #expect(p.id(giornata: 38) == "2025-26-38")
        #expect(p.id(giornata: 20) == nil)
    }

    @Test("La pagina apre la giornata chiesta appena arriva, e la tiene finché la copia del telefono non la contiene")
    func viewModelApreLaGiornataChiesta() async throws {
        let json = try Fixture.testo("diario-giornate")
        let vm = GiornateViewModel(server: ServerDiProva { _, _, _ in Data(json.utf8) })
        vm.apri(giornata: 9)
        #expect(vm.aperte.isEmpty, "le giornate non ci sono ancora")
        await vm.carica()
        #expect(vm.aperte == ["2026-27-9"])
        #expect(vm.scelta == "2026-27-9")
    }

    /// Il diario prima e dopo la fine della giornata 11 di Serie A (8 della lega).
    private static let senzaLaUndicesima = #"{"giornate": [{"stagione": "2026-27", "giornata": 10, "giornata_lega": 7}]}"#
    private static let conLaUndicesima = #"""
        {"giornate": [{"stagione": "2026-27", "giornata": 11, "giornata_lega": 8}, {"stagione": "2026-27", "giornata": 10, "giornata_lega": 7}]}
        """#

    /// Un server che alla prima lettura del diario manda `prima` e poi sempre `dopo`. Contano solo le letture del diario:
    /// `/api/stato`, che la pagina legge insieme alle giornate (#913) e a volte arriva prima, ha una risposta sua.
    private static func server(prima: String, dopo: String) -> ServerDiProva {
        let letture = Scatola<Int>()
        return ServerDiProva { _, percorso, _ in
            guard percorso.hasPrefix("/api/diario") else { return Data("{}".utf8) }
            let n = (letture.valore ?? 0) + 1
            letture.valore = n
            return Data((n == 1 ? prima : dopo).utf8)
        }
    }

    @Test("«Com'è andata» con la pagina già letta prima: la giornata nuova si apre quando arriva la risposta fresca che la contiene")
    func giornataChiestaConLaPaginaGiaLetta() async throws {
        let vm = GiornateViewModel(server: Self.server(prima: Self.senzaLaUndicesima, dopo: Self.conLaUndicesima))
        await vm.carica()
        #expect(vm.aperte.isEmpty)
        // la pagina era già aperta: i suoi dati sono freschi ma di prima della giornata 11, che non c'è ancora
        vm.apri(giornata: 11)
        #expect(vm.aperte.isEmpty, "la 11ª non c'è ancora: la richiesta resta finché non arriva una risposta fresca")
        await vm.carica()
        #expect(vm.aperte == ["2026-27-11"])
        #expect(vm.scelta == "2026-27-11")
    }

    @Test("Se la giornata chiesta c'è già si apre subito; una risposta fresca senza la giornata chiude la richiesta")
    func giornataChiestaSubitoOPersa() async throws {
        let vm = GiornateViewModel(server: Self.server(prima: Self.conLaUndicesima, dopo: Self.senzaLaUndicesima))
        await vm.carica()
        vm.apri(giornata: 11)
        #expect(vm.aperte == ["2026-27-11"], "c'è già: si apre senza aspettare")
        vm.apri(giornata: 20)
        await vm.carica()
        #expect(vm.aperte == ["2026-27-11"], "la 20ª non c'è nemmeno nella risposta fresca: niente cambia")
    }
}
