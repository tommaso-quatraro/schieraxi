import Foundation
import Testing
@testable import Schieraxi

/// La pagina Giornate (#673, passo 2), come `mostraGiornate` della web (#617/#671): la formazione che conta, la frase sotto la riga
/// (il confronto con la consigliata solo con `consigliata.origine: "mostrata"`), gli 11 con l'atteso mostrato prima della scadenza e
/// il preso, «senza voto», la pagina vuota secondo `motivo_vuoto`, la correzione solo dove si può. Le fixture `diario-giornate.json`
/// (server di adesso, con i campi della #642) e `diario-giornate-vecchio.json` (server di prima, senza `origine`, `automatica` e
/// `giocatori`) sono dati inventati. I testi si confrontano con il catalogo comune (`Catalogo.Giornate`), non con la web.
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
        // con due stagioni nella pagina VoiceOver dice anche la stagione
        #expect(r.voce == "Giornata 8, 11ª di Serie A, 2026-27: 74,5 \(Catalogo.Formazione.puntiEAttesi(n: "71,7")). \(r.stato)")
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
        // la tua formazione con la consigliata rifatta: il confronto non c'è, e lo si dice
        let rifatta = try dettaglio(p, 7)
        #expect(rifatta.cambi == nil)
        #expect(rifatta.senzaConfronto == Catalogo.Giornate.senzaConfronto)
    }

    @Test("Il titolo dice di chi è la formazione; la consigliata rifatta ha la sua nota")
    func titoli() throws {
        let p = try pagina("diario-giornate")
        #expect(try dettaglio(p, 9).titolo == Catalogo.Giornate.formazioneAutomatica(modulo: "4-4-2"))
        #expect(try dettaglio(p, 9).nota == nil)
        let rifatta = try dettaglio(p, 8)
        #expect(rifatta.titolo == Catalogo.Giornate.formazioneRifatta(modulo: "4-3-3"))
        #expect(rifatta.nota == Catalogo.Giornate.rifattaNota)
    }

    @Test("«Non è quello che ho schierato» non c'è per le stagioni passate (`modificabile: false`)")
    func correggibile() throws {
        let p = try pagina("diario-giornate")
        #expect(try dettaglio(p, 11).correggibile)
        #expect(try !dettaglio(p, 38, stagione: "2025-26").correggibile)
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
}
