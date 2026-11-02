import XCTest
@testable import Schieraxi

/// Un contatore che si può usare dentro le closure dei server finti.
final class Contatore: @unchecked Sendable {
    private let blocco = NSLock()
    private var n = 0

    /// Aumenta di uno e restituisce il valore che c'era prima.
    func passo() -> Int {
        blocco.lock(); defer { blocco.unlock() }
        let prima = n
        n += 1
        return prima
    }

    var valore: Int {
        blocco.lock(); defer { blocco.unlock() }
        return n
    }
}

@MainActor
final class CaricatoreTests: XCTestCase {
    func testStatoEsponeDatoErroreEInCorso() {
        let idle = Stato<Int>.idle
        XCTAssertNil(idle.dato); XCTAssertNil(idle.errore); XCTAssertFalse(idle.inCorso)
        let caricamento = Stato<Int>.loading(3)
        XCTAssertEqual(caricamento.dato, 3); XCTAssertTrue(caricamento.inCorso)
        XCTAssertEqual(Stato<Int>.loaded(5).dato, 5)
        let fallito = Stato<Int>.failed("no", 7)
        XCTAssertEqual(fallito.dato, 7, "gli ultimi dati restano")
        XCTAssertEqual(fallito.errore, "no")
        XCTAssertFalse(fallito.inCorso)
    }

    func testRiuscitaDopoUnFallimento() async throws {
        let chiamate = Contatore()
        let server = ServerDiProva { _, _, _ in
            if chiamate.passo() == 0 { throw ErroreApi.rete("spento") }
            return try Fixture.dati("oggi")
        }
        let c = Caricatore<Oggi>("/api/oggi", ascolta: false, server: server)
        if case .idle = c.stato {} else { XCTFail("all'inizio è idle") }

        await c.ricarica()
        XCTAssertNil(c.dato)
        XCTAssertNotNil(c.errore, "il primo tentativo fallisce")
        XCTAssertEqual(c.errore, ErroreApi.rete("spento").errorDescription)

        await c.ricarica()
        XCTAssertEqual(c.dato?.giornata, 9, "il secondo riesce")
        XCTAssertNil(c.errore)
        XCTAssertNil(c.datiSalvati)
        if case .loaded = c.stato {} else { XCTFail("dopo la riuscita lo stato è loaded") }
    }

    func testSeIlServerCadeRestanoGliUltimiDatiConLaLoroData() async throws {
        let chiamate = Contatore()
        let server = ServerDiProva { _, _, _ in
            if chiamate.passo() == 0 { return try Fixture.dati("oggi") }
            throw ErroreApi.timeout
        }
        let c = Caricatore<Oggi>("/api/oggi", ascolta: false, server: server)
        await c.ricarica()
        XCTAssertEqual(c.dato?.giornata, 9)
        let primaDelFallimento = Date()
        await c.ricarica()
        XCTAssertEqual(c.dato?.giornata, 9, "i dati di prima si vedono ancora")
        XCTAssertNotNil(c.errore)
        let data = try XCTUnwrap(c.datiSalvati, "e si sa che sono dati vecchi")
        XCTAssertLessThanOrEqual(data, primaDelFallimento.addingTimeInterval(1))
        XCTAssertEqual(c.errore, ErroreApi.timeout.errorDescription)
    }

    func testLaCopiaSalvataSiVedeSubitoEQuandoIlServerNonRisponde() async throws {
        let indirizzo = "https://prova-cache-\(UUID().uuidString).invalid"
        let buono = ServerDiProva(indirizzo: indirizzo) { _, _, _ in try Fixture.dati("oggi") }
        let primo = Caricatore<Oggi>("/api/oggi", ascolta: false, server: buono)
        await primo.ricarica()
        XCTAssertEqual(primo.dato?.giornata, 9)
        // la cache si scrive in secondo piano: si aspetta che il file ci sia
        var presente = false
        for _ in 0..<100 where !presente {
            presente = await Cache.leggi("/api/oggi", indirizzo: indirizzo) != nil
            if !presente { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        XCTAssertTrue(presente, "la risposta riuscita è stata salvata su disco")

        // nuova «apertura» dell'app, server irraggiungibile: restano i dati salvati
        let spento = ServerDiProva(indirizzo: indirizzo) { _, _, _ in throw ErroreApi.rete("rete spenta") }
        let secondo = Caricatore<Oggi>("/api/oggi", ascolta: false, server: spento)
        await secondo.ricarica()
        XCTAssertEqual(secondo.dato?.giornata, 9, "i dati salvati si mostrano lo stesso")
        XCTAssertNotNil(secondo.errore)
        XCTAssertNotNil(secondo.datiSalvati)
    }

    func testCambiandoIndirizzoNonSiMostranoDatiDiUnAltraRichiesta() async throws {
        let server = ServerDiProva { _, percorso, _ in
            if percorso == "/api/a" { return try Fixture.dati("oggi") }
            throw ErroreApi.server("niente")
        }
        let c = Caricatore<Oggi>("/api/a", ascolta: false, server: server)
        await c.ricarica()
        XCTAssertEqual(c.dato?.giornata, 9)
        await c.ricarica("/api/b")
        XCTAssertNil(c.dato, "i dati di /api/a non devono comparire sotto /api/b")
        XCTAssertEqual(c.errore, "niente")
        XCTAssertEqual(c.percorso, "/api/b")
    }

    func testLeChiaviNonSiConvertonoSeServeRimandareIlJSON() async throws {
        let server = ServerDiProva.conFixture(["/api/regole": "regole"])
        let c = Caricatore<JSONValue>("/api/regole", snake: false, cache: false, ascolta: false, server: server)
        await c.ricarica()
        XCTAssertEqual(c.dato?.valore("crediti_iniziali")?.numero, 500, "la chiave resta crediti_iniziali, non creditiIniziali")
    }

    func testIlComandoAggiornaRicaricaIDati() async throws {
        let chiamate = Contatore()
        let server = ServerDiProva { _, _, _ in
            _ = chiamate.passo()
            return try Fixture.dati("oggi")
        }
        let c = Caricatore<Oggi>("/api/oggi", server: server)   // ascolta il comando Aggiorna
        await c.ricarica()
        XCTAssertEqual(chiamate.valore, 1)
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        await attendi("seconda richiesta", finche: { chiamate.valore >= 2 })
        withExtendedLifetime(c) {}
    }

    func testErroreDiDecodificaNonRompeNiente() async throws {
        let server = ServerDiProva { _, _, _ in Data("[1, 2]".utf8) }
        // «Oggi» ha tutti i campi opzionali: un oggetto vuoto è valido, l'errore vero è una forma sbagliata
        let c = Caricatore<Oggi>("/api/oggi", cache: false, ascolta: false, server: server)
        await c.ricarica()
        XCTAssertNil(c.dato)
        XCTAssertTrue(c.errore?.hasPrefix("Il server ha mandato una risposta") == true, c.errore ?? "nessun errore")
    }
}

final class CacheTests: XCTestCase {
    func testSalvaELeggeEPoiCambiaConIlServer() async throws {
        let a = "https://prova-a-\(UUID().uuidString).invalid"
        let b = "https://prova-b-\(UUID().uuidString).invalid"
        Cache.salva(Data("uno".utf8), "/api/x", indirizzo: a)
        var letto: (dati: Data, data: Date)?
        for _ in 0..<100 where letto == nil {
            letto = await Cache.leggi("/api/x", indirizzo: a)
            if letto == nil { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        XCTAssertEqual(letto.map { String(decoding: $0.dati, as: UTF8.self) }, "uno")
        let ieri = Date().addingTimeInterval(-60)
        XCTAssertGreaterThan(try XCTUnwrap(letto).data, ieri)
        let altroServer = await Cache.leggi("/api/x", indirizzo: b)
        XCTAssertNil(altroServer, "cambiando server la cache non si mescola")
        let altroPercorso = await Cache.leggi("/api/y", indirizzo: a)
        XCTAssertNil(altroPercorso)
    }

    /// Scrivere, togliere e leggere vanno nell'ordine delle chiamate: una scrittura in ritardo non rimette la copia appena tolta
    /// (era la causa di `testDopoUnRiavvioNonTornaLoStemmaVecchio` instabile) e la lettura subito dopo la scrittura la trova.
    func testScritturaRimozioneELetturaInOrdine() async throws {
        let indirizzo = "https://prova-ordine-\(UUID().uuidString).invalid"
        for giro in 0..<50 {
            Cache.salva(Data("vecchio-\(giro)".utf8), "/api/x", indirizzo: indirizzo, cartella: "img")
            let subito = await Cache.leggi("/api/x", indirizzo: indirizzo, cartella: "img")
            XCTAssertEqual(subito.map { String(decoding: $0.dati, as: UTF8.self) }, "vecchio-\(giro)", "giro \(giro): letta subito dopo la scrittura")
            Cache.salva(Data("di nuovo".utf8), "/api/x", indirizzo: indirizzo, cartella: "img")
            Cache.rimuovi("/api/x", indirizzo: indirizzo, cartella: "img")
            let dopo = await Cache.leggi("/api/x", indirizzo: indirizzo, cartella: "img")
            XCTAssertNil(dopo, "giro \(giro): la scrittura in coda non deve ricomparire dopo la rimozione")
        }
    }

    func testNomeFileStabileEDistinto() {
        XCTAssertEqual(Cache.nomeFile("/api/oggi", "https://a"), Cache.nomeFile("/api/oggi", "https://a"))
        XCTAssertNotEqual(Cache.nomeFile("/api/oggi", "https://a"), Cache.nomeFile("/api/oggi", "https://b"))
        XCTAssertNotEqual(Cache.nomeFile("/api/oggi", "https://a"), Cache.nomeFile("/api/stato", "https://a"))
        XCTAssertTrue(Cache.nomeFile("/api/oggi", "https://a").hasSuffix(".json"))
    }

    func testIGiorniDelCertificatoNonCambianoIlNomeDellaCopia() {
        let a = "https://a"
        XCTAssertEqual(Cache.nomeFile("/api/oggi?certificato_giorni=5", a), Cache.nomeFile("/api/oggi?certificato_giorni=4", a))
        XCTAssertEqual(Cache.nomeFile("/api/oggi?certificato_giorni=-2", a), Cache.nomeFile("/api/oggi", a))
        XCTAssertEqual(Cache.percorsoStabile("/api/x?a=1&certificato_giorni=3&b=2"), "/api/x?a=1&b=2")
        XCTAssertEqual(Cache.percorsoStabile("/api/oggi?certificato_giorni=3"), "/api/oggi")
        XCTAssertNotEqual(Cache.nomeFile("/api/giocatori?q=a", a), Cache.nomeFile("/api/giocatori?q=b", a), "gli altri parametri contano ancora")
    }

    func testLaCopiaDiOggiSalvataIeriSiRitrovaOggi() async throws {
        let indirizzo = "https://prova-oggi-\(UUID().uuidString).invalid"
        // ieri mancavano 5 giorni alla scadenza del certificato, oggi 4: senza rete l'app deve ritrovare la copia di ieri
        Cache.salva(Data("{}".utf8), OggiRepository.percorso(giorniCertificato: 5), indirizzo: indirizzo)
        var trovata = false
        for _ in 0..<100 where !trovata {
            trovata = await Cache.leggi(OggiRepository.percorso(giorniCertificato: 4), indirizzo: indirizzo) != nil
            if !trovata { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        XCTAssertTrue(trovata)
    }

    func testLeImmaginiStannoInUnaCartellaASe() async throws {
        let indirizzo = "https://prova-img-\(UUID().uuidString).invalid"
        Cache.salva(Data("png".utf8), "/api/foto/1", indirizzo: indirizzo, cartella: "img")
        var trovata = false
        for _ in 0..<100 where !trovata {
            trovata = await Cache.leggi("/api/foto/1", indirizzo: indirizzo, cartella: "img") != nil
            if !trovata { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        XCTAssertTrue(trovata)
        let nellaCartellaDelleRisposte = await Cache.leggi("/api/foto/1", indirizzo: indirizzo)
        XCTAssertNil(nellaCartellaDelleRisposte)
    }
}
