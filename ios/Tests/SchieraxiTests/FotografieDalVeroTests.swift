import XCTest
@testable import Schieraxi

/// Le «fotografie dal vero» (`fotografie/*.json`: risposte vere del server con nomi inventati, vedi `ScenarioVero`) devono
/// leggersi con i modelli dell'app. Se il server cambia forma e una schermata non sa più leggere una risposta, lo si scopre qui,
/// in pochi secondi, e non guardando gli screenshot. Se la cartella non c'è (altro ambiente) il test si salta.
final class FotografieDalVeroTests: XCTestCase {
    private var cartella: URL {
        URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("fotografie", isDirectory: true)
    }

    private func scenari() throws -> [(nome: String, scenario: ScenarioVero)] {
        let file = (try? FileManager.default.contentsOfDirectory(at: cartella, includingPropertiesForKeys: nil)) ?? []
        let json = file.filter { $0.pathExtension == "json" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
        if json.isEmpty { throw XCTSkip("nessuna fotografia dal vero nella cartella fotografie/") }
        return try json.map { url in
            let nome = url.deletingPathExtension().lastPathComponent
            XCTAssertTrue(ScenarioVero.nomeValido(nome), "nome di scenario non valido: \(nome)")
            let s = try XCTUnwrap(ScenarioVero.leggi(try Data(contentsOf: url), nome: nome), "\(nome): file non valido")
            return (nome: nome, scenario: s)
        }
    }

    func testCiSonoITreMomentiDellaGiornata() throws {
        let nomi = try Set(scenari().map(\.nome))
        XCTAssertTrue(nomi.isSuperset(of: ["vero-prima", "vero-in-corso", "vero-finita"]), "scenari trovati: \(nomi.sorted())")
    }

    func testLeRisposteSiLeggonoConIModelliDellApp() throws {
        for (nome, s) in try scenari() {
            func prova<T: Decodable>(_ tipo: T.Type, _ percorso: String, snake: Bool = true, line: UInt = #line) {
                guard let testo = s.risposte[percorso] else {
                    XCTFail("\(nome): manca la risposta di \(percorso)", line: line)
                    return
                }
                do {
                    let _: T = try Decodifica.decodifica(Data(testo.utf8), snake: snake)
                } catch {
                    XCTFail("\(nome) \(percorso): \(error.localizedDescription)", line: line)
                }
            }
            prova(Oggi.self, "/api/oggi")
            prova(Formazione.self, "/api/formazione")
            prova(LiveWidget.self, "/api/live")
            prova(InfoServer.self, "/api/stato")
            prova(StatoDati.self, "/api/stato-dati")
            prova(StatoStagione.self, "/api/stagione")
            prova(Mercato.self, "/api/mercato")
            prova(ElencoGiocatori.self, "/api/classifica?limite=60&liberi=true")
            prova(ElencoGiocatori.self, "/api/osservati")
            prova(Calendario.self, "/api/calendario")
            prova(ProposteScambi.self, "/api/scambi/proposte")
            prova(DiarioRisposta.self, "/api/diario")
            prova(Rosa.self, "/api/rosa")
            prova([SquadraLega].self, "/api/squadre")
            prova([Differenze].self, "/api/movimenti?limite=30")
            prova(Affidabilita.self, "/api/affidabilita")
            prova(StatoAvvisi.self, "/api/avvisi", snake: false)
            prova(RispostaFunzioni.self, "/api/funzioni", snake: false)
            prova([GiocatoreBreve].self, "/api/giocatori")
            if s.risposte["/api/confronto"] != nil { prova(Confronto.self, "/api/confronto") }
            if s.risposte["/api/scambi/analizza"] != nil { prova(PropostaScambio.self, "/api/scambi/analizza") }
            if s.risposte["/api/scambi/da-testo"] != nil { prova(OffertaRiconosciuta.self, "/api/scambi/da-testo") }
            for chiave in s.risposte.keys.sorted() {
                if chiave.hasPrefix("/api/giocatore/") { prova(SchedaGiocatore.self, chiave) }
                if chiave.hasPrefix("/api/rosa?squadra=") { prova(Rosa.self, chiave) }
                if chiave.hasPrefix("/api/formazione?squadra=") { prova(Formazione.self, chiave) }
            }
        }
    }

    /// Le schermate che in demo aprono un giocatore, una squadra o un confronto trovano davvero la risposta.
    func testLeScelteDellaDemoHannoLaLoroRisposta() throws {
        for (nome, s) in try scenari() {
            if let g = s.giocatore { XCTAssertNotNil(s.risposte["/api/giocatore/\(g)"], "\(nome): manca la scheda del giocatore \(g)") }
            if let r = s.rosaAltra { XCTAssertNotNil(s.risposte["/api/rosa?squadra=" + IndirizzoServer.codifica(r)], "\(nome): manca la rosa da mostrare") }
            XCTAssertNotNil(s.confronto, "\(nome): manca la coppia del confronto")
        }
    }

    /// L'orologio delle fotografie: il momento dello scenario è l'ora dell'app (qui fuori dalla demo lo scarto è zero).
    func testFuoriDalleFotografieLOrologioEQuelloVero() {
        XCTAssertNil(ScenarioVero.attuale)
        XCTAssertEqual(Orologio.scarto, 0)
        XCTAssertLessThan(abs(Orologio.adesso().timeIntervalSinceNow), 2)
    }
}
