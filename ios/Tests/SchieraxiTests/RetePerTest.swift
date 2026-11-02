import XCTest
import UIKit
@testable import Schieraxi

/// Un finto «internet»: intercetta le richieste di una `URLSession` di prova e risponde con quello che decide il test.
final class ProtocolloFinto: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) static var gestore: ((URLRequest) throws -> (HTTPURLResponse, Data))?
    nonisolated(unsafe) static var ultimaRichiesta: URLRequest?
    nonisolated(unsafe) static var ultimoCorpo: Data?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.ultimaRichiesta = request
        if let flusso = request.httpBodyStream {
            flusso.open()
            var dati = Data()
            var buffer = [UInt8](repeating: 0, count: 4096)
            while flusso.hasBytesAvailable {
                let n = flusso.read(&buffer, maxLength: buffer.count)
                if n <= 0 { break }
                dati.append(buffer, count: n)
            }
            flusso.close()
            Self.ultimoCorpo = dati
        } else {
            Self.ultimoCorpo = request.httpBody
        }
        do {
            guard let gestore = Self.gestore else { throw URLError(.badServerResponse) }
            let (risposta, dati) = try gestore(request)
            client?.urlProtocol(self, didReceive: risposta, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: dati)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}

final class ServerHTTPTests: XCTestCase {
    private var server: ServerHTTP!
    private var indirizzoPrima: String?

    override func setUp() {
        super.setUp()
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        server = ServerHTTP(sessione: URLSession(configuration: configurazione))
        indirizzoPrima = UserDefaults.standard.string(forKey: "indirizzo")
        UserDefaults.standard.set("https://prova.invalid:8443/", forKey: "indirizzo")   // con la barra finale: va tolta
        ProtocolloFinto.gestore = nil
        ProtocolloFinto.ultimaRichiesta = nil
        ProtocolloFinto.ultimoCorpo = nil
    }

    override func tearDown() {
        if let indirizzoPrima { UserDefaults.standard.set(indirizzoPrima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
        ProtocolloFinto.gestore = nil
        super.tearDown()
    }

    private func risposta(_ richiesta: URLRequest, _ codice: Int) -> HTTPURLResponse {
        HTTPURLResponse(url: richiesta.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: nil) ?? HTTPURLResponse()
    }

    func testRichiestaConIntestazioneEIndirizzoGiusto() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{\"ok\":true}".utf8)) }
        let dati = try await server.grezzo("/api/oggi")
        XCTAssertEqual(String(decoding: dati, as: UTF8.self), "{\"ok\":true}")
        let r = try XCTUnwrap(ProtocolloFinto.ultimaRichiesta)
        XCTAssertEqual(r.url?.absoluteString, "https://prova.invalid:8443/api/oggi", "la barra finale dell'indirizzo si toglie")
        XCTAssertEqual(r.value(forHTTPHeaderField: "X-Fanta"), "1", "senza questa intestazione il server rifiuta le modifiche")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Accept-Language"), "it", "i testi del server sempre in italiano, qualunque sia la lingua del telefono")
        XCTAssertEqual(r.httpMethod, "GET")
    }

    func testCorpoJSONEMetodo() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.corpoJSON("PUT", "/api/mia-squadra", NomeSquadra(nome: "Gli Amici"))
        let r = try XCTUnwrap(ProtocolloFinto.ultimaRichiesta)
        XCTAssertEqual(r.httpMethod, "PUT")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Content-Type"), "application/json")
        XCTAssertEqual(String(decoding: try XCTUnwrap(ProtocolloFinto.ultimoCorpo), as: UTF8.self), "{\"nome\":\"Gli Amici\"}")
    }

    func testIlMessaggioDelServerArrivaCosiCom() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 409), Data("{\"detail\": \"Nessuna rosa importata\"}".utf8)) }
        do {
            _ = try await server.grezzo("/api/formazione")
            XCTFail("doveva lanciare un errore")
        } catch {
            XCTAssertEqual(error.localizedDescription, "Nessuna rosa importata")
        }
    }

    func testErroreDiValidazioneConElencoDiMessaggi() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 422), Data("{\"detail\": [{\"msg\": \"campo mancante\"}]}".utf8)) }
        do {
            _ = try await server.grezzo("/api/x")
            XCTFail("doveva lanciare un errore")
        } catch {
            XCTAssertEqual(error.localizedDescription, "campo mancante")
        }
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 500), Data("<html>boom</html>".utf8)) }
        do {
            _ = try await server.grezzo("/api/x")
            XCTFail("doveva lanciare un errore")
        } catch {
            XCTAssertEqual(error.localizedDescription, "SchieraXI ha un problema in questo momento. Riprova tra poco.", "una pagina HTML non è un messaggio del server")
        }
    }

    func testTimeoutERete() async throws {
        ProtocolloFinto.gestore = { _ in throw URLError(.timedOut) }
        do { _ = try await server.grezzo("/api/x"); XCTFail("doveva lanciare") } catch {
            XCTAssertEqual(error.localizedDescription, ErroreApi.timeout.errorDescription)
        }
        ProtocolloFinto.gestore = { _ in throw URLError(.notConnectedToInternet) }
        do { _ = try await server.grezzo("/api/x"); XCTFail("doveva lanciare") } catch {
            XCTAssertEqual(error.localizedDescription, ErroreApi.rete("").errorDescription, "il messaggio suggerisce di controllare la connessione")
        }
    }

    func testCaricamentoDiUnFileMultipart() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.carica("/api/rose/file?sostituisci_tutto=false", nome: "ro\"se\n.xlsx", dati: Data([1, 2, 3]))
        let r = try XCTUnwrap(ProtocolloFinto.ultimaRichiesta)
        XCTAssertEqual(r.httpMethod, "POST")
        XCTAssertTrue(r.value(forHTTPHeaderField: "Content-Type")?.hasPrefix("multipart/form-data; boundary=") == true)
        XCTAssertEqual(r.value(forHTTPHeaderField: "X-Fanta"), "1")
        let corpo = String(decoding: try XCTUnwrap(ProtocolloFinto.ultimoCorpo), as: UTF8.self)
        XCTAssertTrue(corpo.contains("name=\"file\"; filename=\"rose.xlsx\""), "virgolette e a capo tolti dal nome: \(corpo.prefix(200))")
    }

    func testIndirizziAmmessi() {
        XCTAssertTrue(IndirizzoServer.valido("https://server.example.invalid:8443"))
        XCTAssertTrue(IndirizzoServer.valido("  https://a.b  "))
        XCTAssertFalse(IndirizzoServer.valido("http://server.example.invalid:8000"), "solo https")
        XCTAssertFalse(IndirizzoServer.valido("server"))
        XCTAssertFalse(IndirizzoServer.valido("https://"))
        XCTAssertFalse(IndirizzoServer.valido(""))
    }

    func testCodificaDegliIndirizzi() {
        XCTAssertEqual(IndirizzoServer.codifica("Gli Amici"), "Gli%20Amici")
        XCTAssertEqual(IndirizzoServer.codifica("A&B+C=D?E#F"), "A%26B%2BC%3DD%3FE%23F", "i simboli che cambierebbero l'indirizzo si codificano")
        XCTAssertEqual(IndirizzoServer.codifica("Dušan"), "Du%C5%A1an")
    }

    func testIndirizzoAttualeUsaQuelloScrittoSeValidoAltrimentiQuelloDellaCompilazione() {
        UserDefaults.standard.set("http://non-valido", forKey: "indirizzo")
        XCTAssertEqual(IndirizzoServer.attuale, Config.indirizzoPredefinito)
        UserDefaults.standard.set("https://valido.invalid///", forKey: "indirizzo")
        XCTAssertEqual(IndirizzoServer.attuale, "https://valido.invalid")
    }
}

@MainActor
final class ImmaginiTests: XCTestCase {
    private func png(_ lato: CGFloat = 20) -> Data {
        UIGraphicsImageRenderer(size: CGSize(width: lato, height: lato)).pngData { c in
            UIColor.red.setFill()
            c.fill(CGRect(x: 0, y: 0, width: lato, height: lato))
        }
    }

    private func server(indirizzo: String = "https://prova-img-\(UUID().uuidString).invalid", conFoto: Bool = true) -> ServerDiProva {
        let immagine = png()
        return ServerDiProva(indirizzo: indirizzo) { metodo, percorso, _ in
            if percorso.hasPrefix("/api/foto-disponibili") { return Data("{\"ids\": [101]}".utf8) }
            if percorso.hasPrefix("/api/squadre/immagine") && metodo == "GET" {
                if percorso.contains("tipo=stemma") { return immagine }
                throw ErroreApi.server("Nessuna immagine")
            }
            if percorso.hasPrefix("/api/squadre") && metodo == "GET" {
                return Data("[{\"nome\": \"Gli Amici\", \"mia\": true, \"immagini\": {\"stemma\": true, \"maglia\": false}}]".utf8)
            }
            if percorso == "/api/foto/101" { return immagine }
            if metodo == "UPLOAD" { return Data("{}".utf8) }
            throw ErroreApi.server("Nessuna foto")
        }
    }

    func testChiHaLaFotoEChiHaLoStemma() async {
        let immagini = Immagini(server: server())
        XCTAssertFalse(immagini.haFoto(101))
        await immagini.caricaElenchi()
        XCTAssertTrue(immagini.haFoto(101))
        XCTAssertFalse(immagini.haFoto(102))
        XCTAssertTrue(immagini.haImmagine("Gli Amici", tipo: "stemma"))
        XCTAssertFalse(immagini.haImmagine("Gli Amici", tipo: "maglia"))
        XCTAssertFalse(immagini.haImmagine("Altri", tipo: "stemma"))
    }

    func testLaFotoSiScaricaUnaVoltaSola() async {
        let s = server()
        let immagini = Immagini(server: s)
        await immagini.caricaElenchi()
        XCTAssertNil(immagini.memoriaFoto(101))
        await immagini.caricaFoto(101)
        XCTAssertNotNil(immagini.memoriaFoto(101), "dopo il caricamento la foto è in memoria, pronta per essere disegnata senza attese")
        await immagini.caricaFoto(101)
        XCTAssertEqual(s.quante("GET /api/foto/101"), 1)
        // chi non ha la foto non si chiede nemmeno (niente errori 404 nel registro del server)
        await immagini.caricaFoto(102)
        XCTAssertEqual(s.quante("/api/foto/102"), 0)
    }

    func testLoStemmaSiCaricaELaMagliaMancanteNo() async {
        let s = server()
        let immagini = Immagini(server: s)
        await immagini.caricaElenchi()
        await immagini.caricaSquadra("Gli Amici", tipo: "stemma")
        XCTAssertNotNil(immagini.memoriaSquadra("Gli Amici", tipo: "stemma"))
        await immagini.caricaSquadra("Gli Amici", tipo: "maglia")
        XCTAssertNil(immagini.memoriaSquadra("Gli Amici", tipo: "maglia"))
        XCTAssertEqual(s.quante("tipo=maglia"), 0, "la maglia non c'è e non si chiede")
    }

    func testSeIlServerCadeLeFotoGiaScaricateSiVedonoDalDisco() async throws {
        let indirizzo = "https://prova-disco-\(UUID().uuidString).invalid"
        let primo = Immagini(server: server(indirizzo: indirizzo))
        await primo.caricaElenchi()
        await primo.caricaFoto(101)
        // il disco si scrive in secondo piano
        var presente = false
        for _ in 0..<100 where !presente {
            let foto = await Cache.leggi(Immagini.percorsoFoto(101), indirizzo: indirizzo, cartella: "img")
            let elenco = await Cache.leggi("/api/foto-disponibili", indirizzo: indirizzo)
            presente = foto != nil && elenco != nil
            if !presente { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        XCTAssertTrue(presente)
        // un'altra «apertura» con il server spento: elenchi e foto vengono dalle copie salvate
        let spento = Immagini(server: ServerDiProva(indirizzo: indirizzo) { _, _, _ in throw ErroreApi.rete("spento") })
        await spento.caricaElenchi()
        XCTAssertTrue(spento.haFoto(101), "l'elenco di chi ha la foto è salvato")
        await spento.caricaFoto(101)
        XCTAssertNotNil(spento.memoriaFoto(101))
    }

    func testInvioDiUnaImmagineDellaSquadra() async throws {
        let s = server()
        let immagini = Immagini(server: s)
        await immagini.caricaElenchi()
        try await immagini.invia(png(), squadra: "Gli Amici", tipo: "maglia")
        XCTAssertEqual(s.quante("UPLOAD /api/squadre/immagine?squadra=Gli%20Amici&tipo=maglia"), 1)
        XCTAssertFalse(s.corpiInviati(a: "UPLOAD").isEmpty)
    }

    func testDopoUnRiavvioNonTornaLoStemmaVecchio() async throws {
        let indirizzo = "https://prova-stemma-\(UUID().uuidString).invalid"
        let elenco = Data("[{\"nome\": \"Gli Amici\", \"mia\": true, \"immagini\": {\"stemma\": true, \"maglia\": false}}]".utf8)
        func serverCon(_ immagine: Data) -> ServerDiProva {
            ServerDiProva(indirizzo: indirizzo) { metodo, percorso, _ in
                if percorso.hasPrefix("/api/foto-disponibili") { return Data("{\"ids\": []}".utf8) }
                if percorso.hasPrefix("/api/squadre/immagine") { return metodo == "GET" ? immagine : Data("{}".utf8) }
                if percorso.hasPrefix("/api/squadre") { return elenco }
                throw ErroreApi.server("niente")
            }
        }
        let vecchio = png(20), nuovo = png(40)
        let primo = Immagini(server: serverCon(vecchio))
        await primo.caricaElenchi()
        await primo.caricaSquadra("Gli Amici", tipo: "stemma")
        XCTAssertNotNil(primo.memoriaSquadra("Gli Amici", tipo: "stemma"))
        // la copia su disco si scrive in secondo piano: si aspetta che ci sia
        var presente = false
        for _ in 0..<100 where !presente {
            presente = await Cache.leggi(Immagini.percorsoSquadra("Gli Amici", tipo: "stemma"), indirizzo: indirizzo, cartella: "img") != nil
            if !presente { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        XCTAssertTrue(presente, "lo stemma scaricato resta su disco")
        // l'utente carica uno stemma nuovo
        try await primo.invia(nuovo, squadra: "Gli Amici", tipo: "stemma")
        // alla prossima apertura (la numerazione delle edizioni riparte da zero) si deve vedere quello nuovo, non la copia vecchia
        let secondo = Immagini(server: serverCon(nuovo))
        await secondo.caricaElenchi()
        await secondo.caricaSquadra("Gli Amici", tipo: "stemma")
        let visto = try XCTUnwrap(secondo.memoriaSquadra("Gli Amici", tipo: "stemma"))
        let larghezzaNuovo = try XCTUnwrap(UIImage(data: nuovo)).size.width
        let larghezzaVecchio = try XCTUnwrap(UIImage(data: vecchio)).size.width
        XCTAssertNotEqual(larghezzaNuovo, larghezzaVecchio)
        XCTAssertEqual(visto.size.width, larghezzaNuovo, "lo stemma vecchio rimasto su disco non deve tornare")
    }

    func testImmagineRidottaPerIlServer() throws {
        let opaco = UIGraphicsImageRendererFormat.default()
        opaco.opaque = true   // come una foto della libreria: nessun canale della trasparenza
        opaco.scale = 1
        let grande = UIGraphicsImageRenderer(size: CGSize(width: 2000, height: 1000), format: opaco).image { c in
            UIColor.blue.setFill()
            c.fill(CGRect(x: 0, y: 0, width: 2000, height: 1000))
        }
        // opaca: JPEG, lato massimo 800
        let dati = try XCTUnwrap(grande.datiPerServer())
        XCTAssertEqual(Array(dati.prefix(3)), [0xFF, 0xD8, 0xFF], "una foto senza trasparenza diventa JPEG")
        let ridotta = try XCTUnwrap(UIImage(data: dati))
        XCTAssertLessThanOrEqual(max(ridotta.size.width * ridotta.scale, ridotta.size.height * ridotta.scale), 800.5)
        XCTAssertLessThan(dati.count, 4 * 1024 * 1024, "il server accetta al massimo 4 MB")
        // con trasparenza (uno stemma): PNG
        let formato = UIGraphicsImageRendererFormat.default()
        formato.opaque = false
        formato.scale = 1
        let stemma = UIGraphicsImageRenderer(size: CGSize(width: 100, height: 100), format: formato).image { c in
            UIColor.green.setFill()
            c.cgContext.fillEllipse(in: CGRect(x: 10, y: 10, width: 80, height: 80))
        }
        let png = try XCTUnwrap(stemma.datiPerServer())
        XCTAssertEqual(Array(png.prefix(4)), [0x89, 0x50, 0x4E, 0x47], "uno stemma con la trasparenza resta PNG")
    }
}

final class CertificatoTests: XCTestCase {
    private func profilo(_ scadenza: String) -> Data {
        let xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"><plist version=\"1.0\"><dict><key>Name</key><string>prova</string><key>ExpirationDate</key><date>\(scadenza)</date></dict></plist>"
        // il profilo vero è un messaggio firmato: prima e dopo il plist ci sono byte binari
        return Data([0x30, 0x82, 0x01, 0xFF]) + Data(xml.utf8) + Data([0x00, 0x01, 0x02])
    }

    func testLaScadenzaSiLeggeDalProfilo() throws {
        let data = try XCTUnwrap(Certificato.scadenza(nelProfilo: profilo("2026-11-04T10:00:00Z")))
        XCTAssertEqual(data, ISO8601DateFormatter().date(from: "2026-11-04T10:00:00Z"))
    }

    func testProfiloIllegibileDaNil() {
        XCTAssertNil(Certificato.scadenza(nelProfilo: Data([1, 2, 3])))
        XCTAssertNil(Certificato.scadenza(nelProfilo: Data("<?xml senza fine".utf8)))
        XCTAssertNil(Certificato.scadenza(nelProfilo: Data("<?xml version=\"1.0\"?><plist><array/></plist>".utf8)))
    }

    func testTestoEGravitaDellaScadenza() {
        let adesso = Date(timeIntervalSince1970: 1_800_000_000)
        func info(_ secondi: TimeInterval) -> Certificato.Info { Certificato.info(scadenza: adesso.addingTimeInterval(secondi), adesso: adesso) }
        XCTAssertEqual(Certificato.info(scadenza: nil, adesso: adesso), Certificato.Info(testo: "scadenza non leggibile", livello: .ignoto))
        XCTAssertEqual(info(-10), Certificato.Info(testo: "Scaduto", livello: .scaduto))
        XCTAssertEqual(info(30 * 60), Certificato.Info(testo: "Scade tra meno di un'ora", livello: .attenzione))
        XCTAssertEqual(info(3600 + 60), Certificato.Info(testo: "Scade tra 1 ora", livello: .attenzione))
        XCTAssertEqual(info(30 * 3600), Certificato.Info(testo: "Scade tra 30 ore", livello: .attenzione))
        XCTAssertEqual(info(2 * 86_400 + 10), Certificato.Info(testo: "Scade tra 2 giorni", livello: .ok), "da due giorni in su non è più arancio")
        XCTAssertEqual(info(6.5 * 86_400), Certificato.Info(testo: "Scade tra 6 giorni", livello: .ok))
    }
}
