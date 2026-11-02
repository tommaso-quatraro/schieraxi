import XCTest
@testable import Schieraxi

/// Parità con la web: ore tranquille, ETag/If-Match con il 412, diario e backup.
final class OreTranquilleTests: XCTestCase {
    private func ora(_ testo: String) -> Date { ISO8601DateFormatter().date(from: testo) ?? Date(timeIntervalSince1970: 0) }

    func testSilenzioDiNotteACavalloDellaMezzanotte() {
        let o = OreTranquille(attive: true, da: 23, a: 7)
        XCTAssertTrue(o.inSilenzio(ora("2026-11-10T23:30:00+01:00")))
        XCTAssertTrue(o.inSilenzio(ora("2026-11-11T00:00:00+01:00")))
        XCTAssertTrue(o.inSilenzio(ora("2026-11-11T06:59:00+01:00")))
        XCTAssertFalse(o.inSilenzio(ora("2026-11-11T07:00:00+01:00")))
        XCTAssertFalse(o.inSilenzio(ora("2026-11-11T22:59:00+01:00")))
    }

    func testSilenzioDiGiornoESpento() {
        let giorno = OreTranquille(attive: true, da: 13, a: 15)
        XCTAssertTrue(giorno.inSilenzio(ora("2026-11-10T14:00:00+01:00")))
        XCTAssertFalse(giorno.inSilenzio(ora("2026-11-10T15:00:00+01:00")))
        XCTAssertFalse(OreTranquille(attive: false, da: 23, a: 7).inSilenzio(ora("2026-11-10T23:30:00+01:00")))
        XCTAssertFalse(OreTranquille(attive: true, da: 8, a: 8).inSilenzio(ora("2026-11-10T08:30:00+01:00")), "stessa ora: nessun silenzio, come sul server")
    }

    func testOreFuoriScalaRientranoNelGiro() {
        let o = OreTranquille(attive: true, da: 25, a: -1)
        XCTAssertEqual(o.da, 1)
        XCTAssertEqual(o.a, 23)
    }

    func testLaFineDelSilenzio() {
        let o = OreTranquille(attive: true, da: 23, a: 7)
        let fine = o.fine(da: ora("2026-11-10T23:30:00+01:00"))
        XCTAssertEqual(fine, ora("2026-11-11T07:00:00+01:00"))
        XCTAssertEqual(o.fine(da: ora("2026-11-11T03:00:00+01:00")), ora("2026-11-11T07:00:00+01:00"))
        XCTAssertNil(o.fine(da: ora("2026-11-11T12:00:00+01:00")), "fuori dal silenzio non c'è una fine")
    }

    func testIPromemoriaNelleOreTranquilleSiSaltano() {
        let o = OreTranquille(attive: true, da: 23, a: 7)
        let adesso = ora("2026-11-10T10:00:00+01:00")
        // partita alle 08:00 del giorno dopo: l'avviso di un'ora prima (07:00) è fuori dal silenzio, quello di 15 minuti prima (07:45) pure
        let mattina = Notifiche.promemoriaConsentiti(inizio: ora("2026-11-11T08:00:00+01:00"), ore: o, adesso: adesso)
        XCTAssertEqual(mattina.map(\.id), ["fanta-60", "fanta-15"])
        // partita alle 07:30: 06:30 cade nel silenzio (saltato), 07:15 no
        let presto = Notifiche.promemoriaConsentiti(inizio: ora("2026-11-11T07:30:00+01:00"), ore: o, adesso: adesso)
        XCTAssertEqual(presto.map(\.id), ["fanta-15"])
        // senza ore tranquille restano tutti
        let tutti = Notifiche.promemoriaConsentiti(inizio: ora("2026-11-11T07:30:00+01:00"), ore: .predefinite, adesso: adesso)
        XCTAssertEqual(tutti.count, 2)
        // i promemoria nel passato non ci sono
        XCTAssertTrue(Notifiche.promemoriaConsentiti(inizio: ora("2026-11-10T09:00:00+01:00"), ore: .predefinite, adesso: adesso).isEmpty)
    }

    func testArchivioRicordaLeOreTranquille() {
        let nome = "prova-ore-\(UUID().uuidString)"
        guard let memoria = UserDefaults(suiteName: nome) else { return XCTFail("UserDefaults di prova non disponibile") }
        defer { memoria.removePersistentDomain(forName: nome) }
        XCTAssertEqual(ArchivioOreTranquille.leggi(memoria), .predefinite)
        ArchivioOreTranquille.salva(OreTranquille(attive: true, da: 22, a: 6), memoria)
        XCTAssertEqual(ArchivioOreTranquille.leggi(memoria), OreTranquille(attive: true, da: 22, a: 6))
    }

    func testLeImpostazioniDelServerPortanoLeOreTranquille() throws {
        let nuovo = Data("""
        {"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "app_nativa": false,
         "silenzio": true, "silenzio_da": 22, "silenzio_a": 6}
        """.utf8)
        let i = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: nuovo)
        XCTAssertEqual(i.oreTranquille, OreTranquille(attive: true, da: 22, a: 6))
        let vecchio = Data(#"{"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true}"#.utf8)
        let v = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: vecchio)
        XCTAssertEqual(v.oreTranquille, .predefinite)
        // un server vecchio non manda i campi: l'app non li rimanda (non si azzera niente)
        let corpo = String(decoding: try JSONEncoder().encode(v), as: UTF8.self)
        XCTAssertFalse(corpo.contains("silenzio"), corpo)
    }

    func testAvvisoRepartoScopertoSiLeggeESiRimandaSoloSeCeraNelServer() throws {
        let nuovo = Data(#"{"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "copertura": false}"#.utf8)
        var i = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: nuovo)
        XCTAssertEqual(i.copertura, false)
        i.copertura = true
        XCTAssertTrue(String(decoding: try JSONEncoder().encode(i), as: UTF8.self).contains(#""copertura":true"#))
        let vecchio = Data(#"{"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true}"#.utf8)
        let v = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: vecchio)
        XCTAssertNil(v.copertura)
        XCTAssertFalse(String(decoding: try JSONEncoder().encode(v), as: UTF8.self).contains("copertura"))
    }

    func testOreTranquilleSpenteDalServerEDecodificaTollerante() throws {
        let imp = #""impostazioni": {"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true}"#
        func stato(_ extra: String) throws -> StatoAvvisi {
            try JSONDecoder().decode(StatoAvvisi.self, from: Data("{\(imp)\(extra)}".utf8))
        }
        XCTAssertTrue(try stato(#", "ore_tranquille_spente": true"#).oreTranquilleSpente)
        XCTAssertFalse(try stato("").oreTranquilleSpente)                                  // campo mancante: niente
        XCTAssertFalse(try stato(#", "ore_tranquille_spente": null"#).oreTranquilleSpente)
        XCTAssertFalse(try stato(#", "ore_tranquille_spente": "si""#).oreTranquilleSpente) // tipo strano: niente
    }
}

final class VersioniEConflittiTests: XCTestCase {
    private var server: ServerHTTP!
    private var indirizzoPrima: String?
    private var indirizzo = ""

    override func setUp() {
        super.setUp()
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        server = ServerHTTP(sessione: URLSession(configuration: configurazione), archivioToken: MemoriaToken(), attesaCalcolo: 0.01, massimoTentativiCalcolo: 2)
        indirizzoPrima = UserDefaults.standard.string(forKey: "indirizzo")
        indirizzo = "https://prova-etag-\(UUID().uuidString.lowercased()).invalid"
        UserDefaults.standard.set(indirizzo, forKey: "indirizzo")
        ProtocolloFinto.gestore = nil
        ProtocolloFinto.ultimaRichiesta = nil
        VersioniRisorse.condivise.azzera()
    }

    override func tearDown() {
        if let indirizzoPrima { UserDefaults.standard.set(indirizzoPrima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
        ProtocolloFinto.gestore = nil
        VersioniRisorse.condivise.azzera()
        super.tearDown()
    }

    private func risposta(_ r: URLRequest, _ codice: Int, _ intestazioni: [String: String] = [:]) -> HTTPURLResponse {
        HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: intestazioni) ?? HTTPURLResponse()
    }

    func testQualeRisorsaHaUnETag() {
        XCTAssertEqual(VersioniRisorse.risorsa(per: "/api/regole"), "regole")
        XCTAssertEqual(VersioniRisorse.risorsa(per: "/api/avvisi"), "avvisi")
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/avvisi/prova"))
        XCTAssertEqual(VersioniRisorse.risorsa(per: "/api/osservati/12"), "osservati")
        for p in ["/api/squadre", "/api/crediti", "/api/mia-squadra", "/api/rose/testo", "/api/squadre?x=1"] {
            XCTAssertEqual(VersioniRisorse.risorsa(per: p), "rose", p)
        }
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/oggi"))
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/regolette"), "solo il percorso intero, non un prefisso di parola")
    }

    func testLEtagLettoVieneRimandatoInIfMatch() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in
            r.httpMethod == "GET" ? (risposta(r, 200, ["ETag": "\"abc123\""]), Data("{}".utf8)) : (risposta(r, 200, ["ETag": "\"nuovo\""]), Data("{}".utf8))
        }
        _ = try await server.grezzo("/api/regole")
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "in lettura niente If-Match")
        _ = try await server.corpoJSON("PUT", "/api/regole", ["a": 1])
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "\"abc123\"")
        // la risposta alla scrittura porta l'ETag nuovo, usato dalla scrittura dopo
        _ = try await server.corpoJSON("PUT", "/api/regole", ["a": 2])
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "\"nuovo\"")
    }

    func testSenzaUnaLetturaPrimaSiScriveComeSempre() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.corpoJSON("PUT", "/api/crediti", ["crediti": [String: Int]()])
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"))
    }

    func testLeRisorseSonoSeparate() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in
            r.url?.path == "/api/regole" ? (risposta(r, 200, ["ETag": "\"r1\""]), Data("{}".utf8)) : (risposta(r, 200), Data("{}".utf8))
        }
        _ = try await server.grezzo("/api/regole")
        _ = try await server.corpoJSON("PUT", "/api/avvisi", ["cambi": true])
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "l'ETag delle regole non vale per gli avvisi")
    }

    func test412DiventaUnConflittoConIlMessaggioGiusto() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in
            r.httpMethod == "GET" ? (risposta(r, 200, ["ETag": "\"v1\""]), Data("{}".utf8))
                                   : (risposta(r, 412, ["ETag": "\"v2\""]), Data(#"{"detail": "Questi dati sono stati cambiati da un altro dispositivo."}"#.utf8))
        }
        _ = try await server.grezzo("/api/avvisi")
        do {
            _ = try await server.corpoJSON("PUT", "/api/avvisi", ["cambi": false])
            XCTFail("doveva lanciare")
        } catch let e as ErroreApi {
            XCTAssertTrue(e.eConflitto)
            XCTAssertTrue((e.errorDescription ?? "").contains("altro dispositivo"))
            XCTAssertTrue((e.errorDescription ?? "").contains("ricaricato"))
        }
        // dopo il 412 si usa l'ETag nuovo dato dal server: la scrittura dopo la rilettura non litiga più
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.corpoJSON("PUT", "/api/avvisi", ["cambi": false])
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "\"v2\"")
    }

    func testLaSceltaHaUnETagPerGiornata() {
        XCTAssertEqual(VersioniRisorse.risorsa(per: "/api/scelta?giornata=9"), "scelta:9")
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/scelta"), "senza giornata non si sa quale scelta")
        let salva = Data(#"{"titolari": [1, 2], "salva": true, "giornata": 9}"#.utf8)
        XCTAssertEqual(VersioniRisorse.risorsa(per: "/api/formazione/valuta", corpo: salva), "scelta:9")
        let prova = Data(#"{"titolari": [1, 2], "salva": false, "giornata": 9}"#.utf8)
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/formazione/valuta", corpo: prova), "una valutazione e basta non scrive niente")
        let altra = Data(#"{"titolari": [1], "salva": true, "giornata": 9, "squadra": "Gli Amici"}"#.utf8)
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/formazione/valuta", corpo: altra), "per un'altra squadra il server non salva")
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/formazione/valuta", corpo: Data("non json".utf8)))
        XCTAssertNil(VersioniRisorse.risorsa(per: "/api/formazione"))
    }

    func testSalvareLaSceltaMandaLETagLettoE412EUnConflitto() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in
            if r.httpMethod == "GET" { return (risposta(r, 200, ["ETag": "\"s1\""]), Data("null".utf8)) }
            return (risposta(r, 412, ["ETag": "\"s2\""]), Data(#"{"detail": "Questi dati sono stati cambiati da un altro dispositivo."}"#.utf8))
        }
        _ = try await server.grezzo("/api/scelta?giornata=9")
        // una valutazione senza salvare non manda If-Match
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.corpoJSON("POST", "/api/formazione/valuta", RichiestaValutazione(titolari: [1], salva: false, giornata: 9))
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"))
        // salvando sì, con l'ETag della giornata giusta
        ProtocolloFinto.gestore = { [unowned self] r in
            (risposta(r, 412, ["ETag": "\"s2\""]), Data(#"{"detail": "Questi dati sono stati cambiati da un altro dispositivo."}"#.utf8))
        }
        do {
            _ = try await server.corpoJSON("POST", "/api/formazione/valuta", RichiestaValutazione(titolari: [1], salva: true, giornata: 9))
            XCTFail("doveva lanciare")
        } catch let e as ErroreApi {
            XCTAssertTrue(e.eConflitto)
        }
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "\"s1\"")
        // la cancellazione della stessa giornata usa l'ETag nuovo dato dal 412; un'altra giornata nessuno
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.richiesta("DELETE", "/api/scelta?giornata=9", corpo: nil)
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "\"s2\"")
        _ = try await server.richiesta("DELETE", "/api/scelta?giornata=10", corpo: nil)
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"))
    }

    func testUnETagStranoNonSiRicorda() {
        VersioniRisorse.condivise.imposta("a\nb", server: indirizzo, risorsa: "regole")
        VersioniRisorse.condivise.imposta(String(repeating: "x", count: 500), server: indirizzo, risorsa: "regole")
        VersioniRisorse.condivise.imposta("", server: indirizzo, risorsa: "regole")
        XCTAssertNil(VersioniRisorse.condivise.leggi(server: indirizzo, risorsa: "regole"))
    }

    func testUnETagNonPassaDaUnServerAllAltro() {
        VersioniRisorse.condivise.imposta("\"x\"", server: "https://uno.invalid", risorsa: "rose")
        XCTAssertNil(VersioniRisorse.condivise.leggi(server: "https://due.invalid", risorsa: "rose"))
        VersioniRisorse.condivise.azzera()
        XCTAssertNil(VersioniRisorse.condivise.leggi(server: "https://uno.invalid", risorsa: "rose"))
    }
}

final class DiarioEBackupTests: XCTestCase {
    private static let backupProva = #"{"formato": "schieraxi-backup", "versione": 1, "creato": "2026-10-30T09:00:00", "file": {"dati/osservati.json": [1, 2]}}"#

    func testIlDiarioSiLeggeAnchePoveroDiCampi() throws {
        let dati = Data("""
        {"giornate": [
          {"stagione": "2026-27", "giornata": 9,
           "consigliata": {"modulo": "3-4-3", "atteso": 68.5, "reale": 71.0, "titolari": [{"id": 1, "nome": "Sorvani"}, {"id": 2, "nome": "Lemao"}]},
           "schierata": {"modulo": "3-5-2", "atteso": 66.0, "reale": 63.5, "titolari": [{"id": 1, "nome": "Sorvani"}, {"id": 3, "nome": "Orsetti"}]}},
          {"giornata": 8}
        ], "sintesi": {"giornate": 1, "punti_schierata": 63.5, "punti_consigliata": 71.0, "meglio_tua": 0, "meglio_consigliata": 1}}
        """.utf8)
        let d: DiarioRisposta = try Decodifica.decodifica(dati)
        XCTAssertEqual(d.giornate?.count, 2)
        XCTAssertEqual(d.sintesi?.puntiSchierata, 63.5)
        XCTAssertEqual(d.giornate?.first?.confronto?.fraseCambi, "Hai cambiato 1: Orsetti al posto di Lemao.")
        XCTAssertNil(d.giornate?.last?.confronto, "senza formazioni non c'è un confronto")
    }

    func testStessiSchieraxiDelModello() throws {
        let dati = Data(#"{"giornate": [{"giornata": 1, "consigliata": {"titolari": [{"id": 1, "nome": "A"}]}, "schierata": {"titolari": [{"id": 1, "nome": "A"}]}}]}"#.utf8)
        let d: DiarioRisposta = try Decodifica.decodifica(dati)
        XCTAssertEqual(d.giornate?.first?.confronto?.fraseCambi, "Hai schierato gli stessi 11 consigliati.")
    }

    func testIlDiarioVuotoNonRompeNiente() throws {
        let d: DiarioRisposta = try Decodifica.decodifica(Data(#"{"giornate": [], "sintesi": {"giornate": 0}}"#.utf8))
        XCTAssertEqual(d.giornate?.count, 0)
    }

    private func errore(_ dati: Data) -> FileBackup.Errore? {
        if case .failure(let e) = FileBackup.controlla(dati) { return e }
        return nil
    }

    func testControlloDelFileDiBackup() {
        let buono = Data(#"{"formato": "schieraxi-backup", "versione": 1, "creato": "2026-10-30T09:00:00", "file": {"dati/osservati.json": [1]}}"#.utf8)
        XCTAssertNil(errore(buono))
        XCTAssertEqual(errore(Data()), .vuoto)
        XCTAssertEqual(errore(Data("non json".utf8)), .nonEUnBackup)
        XCTAssertEqual(errore(Data("[1,2]".utf8)), .nonEUnBackup)
        XCTAssertEqual(errore(Data(#"{"formato": "altro", "versione": 1, "file": {"a": 1}}"#.utf8)), .nonEUnBackup)
        XCTAssertEqual(errore(Data(#"{"formato": "schieraxi-backup", "versione": 1, "file": {}}"#.utf8)), .nonEUnBackup, "vuoto")
        XCTAssertEqual(errore(Data(#"{"formato": "schieraxi-backup", "versione": 9, "file": {"a": 1}}"#.utf8)), .piuNuovo)
        XCTAssertEqual(errore(Data(repeating: 0x20, count: FileBackup.massimoByte + 1)), .troppoGrande)
    }

    func testNomeDelFileDiBackup() {
        XCTAssertEqual(FileBackup.nomeFile(Data(#"{"creato": "2026-10-30T09:00:00"}"#.utf8)), "schieraxi-backup-2026-10-30.json")
        XCTAssertEqual(FileBackup.nomeFile(Data(#"{"creato": "../../etc/x"}"#.utf8)), "schieraxi-backup.json", "niente percorsi nel nome")
        XCTAssertEqual(FileBackup.nomeFile(Data("{}".utf8)), "schieraxi-backup.json")
    }
}

/// Il nome «SchieraXI» con XI maiuscolo e il marchio sempre vivo, anche con «Ridurre movimento».
final class NomeEMovimentoTests: XCTestCase {
    func testLOndaDiOpacitaRestaNelSuoIntervallo() {
        for passo in 0..<120 {
            let t = Double(passo) * 0.05
            let v = Marchio.opacitaOnda(t, ritardo: 0.2)
            XCTAssertTrue((0.45...1.0).contains(v), "t=\(t) v=\(v)")
            let c = Marchio.opacitaOnda(t, ritardo: 0, minimo: 0.7)
            XCTAssertTrue((0.7...1.0).contains(c), "t=\(t) c=\(c)")
        }
    }

    func testLOndaSiMuoveDavveroNelTempo() {
        let valori = (0..<26).map { Marchio.opacitaOnda(Double($0) * 0.1, ritardo: 0) }
        XCTAssertGreaterThan((valori.max() ?? 0) - (valori.min() ?? 0), 0.4, "il marchio deve respirare, non restare fermo")
    }

    func testIlNomeNonSiScriveMaiInMinuscoloNelleVisteDelMarchio() throws {
        // Il file sorgente sta accanto ai test sul Mac di GitHub; se non si trova (altro ambiente) il test non dice niente.
        let radice = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let cartella = radice.appendingPathComponent("Sources", isDirectory: true)
        guard let elenco = FileManager.default.enumerator(at: cartella, includingPropertiesForKeys: nil) else { return }
        var trovati: [String] = []
        for caso in elenco {
            guard let url = caso as? URL, url.pathExtension == "swift", let testo = try? String(contentsOf: url, encoding: .utf8) else { continue }
            if testo.contains("Text(\"schieraxi\")") || testo.contains("Text(\"Schieraxi\")") { trovati.append(url.lastPathComponent) }
        }
        XCTAssertTrue(trovati.isEmpty, "«SchieraXI» va sempre con XI maiuscolo: \(trovati)")
    }
}

/// Diario: «Ho schierato la consigliata» per una giornata finita.
@MainActor
final class DiarioSchierataTests: XCTestCase {
    func testSalvaLaConsigliataERicaricaIlDiario() async throws {
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "POST", percorso == "/api/diario/schierata" { return Data(#"{"giornata": 9}"#.utf8) }
            if percorso == "/api/diario" { return Data(#"{"giornate": [{"giornata": 9, "stagione": "2026-27"}], "sintesi": {"giornate": 0}}"#.utf8) }
            throw ErroreApi.server("niente")
        }
        let vm = DiarioViewModel(server: s)
        await vm.haSchieratoLaConsigliata(giornata: 9)
        XCTAssertEqual(s.quante("POST /api/diario/schierata"), 1)
        let corpo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "/api/diario/schierata").first), as: UTF8.self)
        XCTAssertTrue(corpo.contains("\"consigliata\"") && corpo.contains("9"), corpo)
        XCTAssertFalse(corpo.contains("titolari"), "senza titolari per «consigliata»")
        XCTAssertTrue(vm.messaggioRiuscito)
        XCTAssertNil(vm.inSalvataggio)
        XCTAssertEqual(s.quante("GET /api/diario"), 1, "dopo il salvataggio il diario si rilegge")
    }

    func testUnErroreDelServerSiMostraSenzaRompere() async {
        let s = ServerDiProva { _, _, _ in throw ErroreApi.server("Si può dire cosa hai schierato solo per le giornate già finite") }
        let vm = DiarioViewModel(server: s)
        await vm.haSchieratoLaConsigliata(giornata: 99)
        XCTAssertFalse(vm.messaggioRiuscito)
        XCTAssertTrue((vm.messaggio ?? "").contains("giornate già finite"))
        XCTAssertNil(vm.inSalvataggio)
    }
}

/// Diario: la formazione schierata a mano.
@MainActor
final class DiarioManualeTests: XCTestCase {
    func testManualeManda11TitolariEUnTipoGiusto() async throws {
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "POST" { return Data(#"{"giornata": 9}"#.utf8) }
            return Data(#"{"giornate": [], "sintesi": {"giornate": 0}}"#.utf8)
        }
        let vm = DiarioViewModel(server: s)
        let ids = Array(1...11)
        let ok = await vm.haSchieratoAMano(giornata: 9, titolari: ids)
        XCTAssertTrue(ok)
        let corpo = try XCTUnwrap(s.corpiInviati(a: "/api/diario/schierata").first)
        let letto = try XCTUnwrap(JSONSerialization.jsonObject(with: corpo) as? [String: Any])
        XCTAssertEqual(letto["tipo"] as? String, "manuale")
        XCTAssertEqual(letto["giornata"] as? Int, 9)
        XCTAssertEqual(letto["titolari"] as? [Int], ids)
        XCTAssertTrue(vm.messaggioRiuscito)
    }

    func testUnRifiutoDelServerNonChiudeESiVede() async {
        let s = ServerDiProva { _, _, _ in throw ErroreApi.server("Tra i titolari ci sono giocatori che non sono nella tua rosa") }
        let vm = DiarioViewModel(server: s)
        let ok = await vm.haSchieratoAMano(giornata: 9, titolari: Array(1...11))
        XCTAssertFalse(ok)
        XCTAssertFalse(vm.messaggioRiuscito)
        XCTAssertTrue((vm.messaggio ?? "").contains("non sono nella tua rosa"))
    }
}
