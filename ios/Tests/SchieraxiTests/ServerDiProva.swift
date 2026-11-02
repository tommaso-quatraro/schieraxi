import Foundation
import XCTest
@testable import Schieraxi

/// Un server finto «programmabile» per i test: ogni richiesta passa dal `gestore`, che decide cosa rispondere (o quale errore lanciare).
/// Ogni istanza ha un indirizzo suo: la cache su disco dell'app (che è per indirizzo) non si mescola tra un test e l'altro.
final class ServerDiProva: ServerClient, @unchecked Sendable {
    typealias Gestore = @Sendable (_ metodo: String, _ percorso: String, _ corpo: Data?) async throws -> Data

    let indirizzo: String
    private let gestore: Gestore
    private let blocco = NSLock()
    private var registro: [String] = []
    private var corpi: [String: [Data]] = [:]

    init(indirizzo: String = "https://prova-\(UUID().uuidString).invalid", gestore: @escaping Gestore) {
        self.indirizzo = indirizzo
        self.gestore = gestore
    }

    /// Le richieste ricevute, nell'ordine, come «GET /api/oggi».
    var richieste: [String] {
        blocco.lock(); defer { blocco.unlock() }
        return registro
    }

    func quante(_ prefisso: String) -> Int { richieste.filter { $0.contains(prefisso) }.count }

    /// I corpi inviati a un indirizzo (per controllare cosa ha mandato l'app).
    func corpiInviati(a percorso: String) -> [Data] {
        blocco.lock(); defer { blocco.unlock() }
        return corpi.filter { $0.key.contains(percorso) }.flatMap { $0.value }
    }

    /// Annota una richiesta (in una funzione non asincrona: il blocco non si tiene mai attraverso un `await`).
    private func annota(_ chiave: String, _ corpo: Data?) {
        blocco.lock()
        defer { blocco.unlock() }
        registro.append(chiave)
        if let corpo { corpi[chiave, default: []].append(corpo) }
    }

    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data {
        annota("\(metodo) \(percorso)", corpo)
        return try await gestore(metodo, percorso, corpo)
    }

    func carica(_ percorso: String, nome: String, dati: Data, tipo: String) async throws -> Data {
        try await carica(percorso, nome: nome, dati: dati, tipo: tipo, campi: [])
    }

    func carica(_ percorso: String, nome: String, dati: Data, tipo: String, campi: [CampoModulo]) async throws -> Data {
        annota("UPLOAD \(percorso)", dati)
        annotaFile(nome: nome, tipo: tipo, campi: campi)
        return try await gestore("UPLOAD", percorso, dati)
    }

    /// Nome e tipo dei file caricati, nell'ordine.
    var fileCaricati: [(nome: String, tipo: String)] {
        blocco.lock(); defer { blocco.unlock() }
        return files
    }

    private var files: [(nome: String, tipo: String)] = []
    private var moduli: [[CampoModulo]] = []

    /// I campi di testo mandati con ogni file (vuoto = solo il file), nell'ordine.
    var campiCaricati: [[CampoModulo]] {
        blocco.lock(); defer { blocco.unlock() }
        return moduli
    }

    private func annotaFile(nome: String, tipo: String, campi: [CampoModulo]) {
        blocco.lock(); defer { blocco.unlock() }
        files.append((nome, tipo))
        moduli.append(campi)
    }

    // MARK: costruzione rapida

    /// Risponde con le fixture: la chiave è il prefisso dell'indirizzo, il valore il nome del file in `Tests/Fixtures`.
    /// Vince il prefisso più lungo; per gli indirizzi senza fixture: un errore del server (come un 404). Le richieste che
    /// modificano qualcosa (POST, PUT, DELETE) senza fixture vanno a buon fine con `{}`.
    static func conFixture(_ mappa: [String: String]) -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            let chiavi = mappa.keys.filter { percorso.hasPrefix($0) }.sorted { $0.count > $1.count }
            if let chiave = chiavi.first, let nome = mappa[chiave] { return try Fixture.dati(nome) }
            if metodo != "GET" { return Data("{}".utf8) }
            throw ErroreApi.server("nessuna fixture per \(percorso)")
        }
    }

    /// Risponde sempre con lo stesso errore.
    static func chePrecipita(_ errore: ErroreApi = .rete("spento")) -> ServerDiProva {
        ServerDiProva { _, _, _ in throw errore }
    }
}

/// Una scatola con un valore dentro, che si può riempire dalle closure dei server finti (che girano su altri thread).
final class Scatola<T>: @unchecked Sendable {
    private let blocco = NSLock()
    private var contenuto: T?

    var valore: T? {
        get { blocco.lock(); defer { blocco.unlock() }; return contenuto }
        set { blocco.lock(); defer { blocco.unlock() }; contenuto = newValue }
    }
}

/// Aspetta (al massimo `secondi`) che una condizione diventi vera: per le azioni che partono in un `Task` (come la modifica a mano).
@MainActor
func attendi(_ descrizione: String = "condizione", secondi: Double = 5, finche condizione: @MainActor () -> Bool,
             file: StaticString = #filePath, line: UInt = #line) async {
    let limite = Date().addingTimeInterval(secondi)
    while !condizione() && Date() < limite {
        try? await Task.sleep(nanoseconds: 20_000_000)
    }
    XCTAssertTrue(condizione(), "Troppo tempo ad aspettare: \(descrizione)", file: file, line: line)
}
