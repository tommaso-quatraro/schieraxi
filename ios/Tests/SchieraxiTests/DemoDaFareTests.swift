import Foundation
import Testing
@testable import Schieraxi

/// «Da fare» dei dati di prova (modalità demo e fotografie): deve dire quello che direbbe il server, con gli stessi testi
/// (`fanta/frasi.py`, chiavi `dafare.*`) e il numero di giornata della lega (non quello della Serie A).
/// Dati inventati: i nomi sono quelli della demo (`DatiDemo.swift`).
struct DemoDaFareTests {

    /// La risposta di Oggi della demo: la schermata normale (`oggi`) o una fase delle fotografie (`oggi-finita`).
    private func oggi(_ schermata: String) async throws -> Oggi {
        let server: FinteServer? = schermata == "oggi" ? FinteServer.demo : FinteServer.demoFase(schermata)
        let finto = try #require(server, "la demo «\(schermata)» non esiste")
        return try Decodifica.decodifica(try await finto.richiesta("GET", "/api/oggi", corpo: nil))
    }

    @Test("Il diario numera la giornata della lega, non quella della Serie A")
    func diarioConIlNumeroDellaLega() async throws {
        let o = try await oggi("oggi")
        let serieA = try #require(o.giornata)
        let lega = try #require(o.giornataLega)
        #expect(serieA != lega, "se i due numeri coincidono il test non distingue più la lega dalla Serie A")
        let voce = try #require(o.daFare?.first(where: { $0.tipo == "diario" }), "nella demo manca la voce del diario")
        // l'ultima giornata finita della lega è quella prima della giornata in corso, come in `_diario` di fanta/da_fare.py
        #expect(voce.testo == "La giornata \(lega - 1) è finita: dimmi se hai schierato la consigliata.")
        #expect(!voce.testo.contains("giornata \(serieA - 1) "), "il numero è quello della Serie A")
        #expect(voce.azione == "Ho schierato la consigliata")
        #expect(voce.destinazione?.link == "schieraxi://lega/diario")
    }

    @Test("I testi di «Da fare» della demo sono quelli del server")
    func testiDellaDemoCometIlServer() async throws {
        try await controlla("oggi", tipi: ["dubbio", "svincolato", "rose", "diario"])
    }

    @Test("Anche «Oggi» a giornata finita usa i testi del server")
    func testiDellaDemoFinitaCometIlServer() async throws {
        try await controlla("oggi-finita", tipi: ["svincolato"])
    }

    /// Confronta ogni voce della schermata con la frase che il server scriverebbe con gli stessi dati. `tipi`: le voci che ci devono essere.
    private func controlla(_ schermata: String, tipi: Set<String>) async throws {
        let frasi = try FrasiDelServer()
        let o = try await oggi(schermata)
        let voci = try #require(o.daFare, "\(schermata): manca «da_fare»")

        // i dati della demo (stessi numeri del mercato: Vlasenić esce, Retalli entra, 3,4 punti; Marténi ha il 62% di giocare e la
        // consigliata lo tiene titolare, quindi niente «Meglio»: se non gioca entra Lemão, il primo attaccante della panchina, #305)
        let guadagno = try frasi.frase("dafare.guadagno_stagione", ["punti": "3,4"])
        let attese: [String: (testo: String, azione: String)] = [
            "dubbio": (try frasi.frase("dafare.dubbio_incerto_tiene", ["nome": "Leonel Marténi", "p": "62", "riserva": "Renato Lemão"]),
                       try frasi.frase("dafare.az_formazione")),
            "svincolato": (try frasi.frase("dafare.svincolato", ["entra": "Mauro Retalli", "esce": "Darko Vlasenić", "guadagno": guadagno]),
                           try frasi.frase("dafare.az_vedi")),
            "rose": (try frasi.frase("dafare.rose_vecchie", ["giorni": "5"]),
                     try frasi.frase("dafare.az_aggiorna_rose")),
            "diario": (try frasi.frase("dafare.diario", ["n": "7"]),
                       try frasi.frase("dafare.az_schierato")),
        ]

        var controllati: Set<String> = []
        for voce in voci {
            guard let tipo = voce.tipo else { continue }
            guard let attesa = attese[tipo] else {
                // la copia di sicurezza l'app la nasconde e il server non la manda più: ogni altra voce deve avere un confronto
                #expect(tipo == "backup", "\(schermata): la voce «\(tipo)» non ha un confronto con le frasi del server")
                continue
            }
            #expect(voce.testo == attesa.testo, "\(schermata), «\(tipo)»: il testo non è quello del server")
            #expect(voce.azione == attesa.azione, "\(schermata), «\(tipo)»: il pulsante non è quello del server")
            controllati.insert(tipo)
        }
        #expect(controllati == tipi, "\(schermata): voci confrontate \(controllati.sorted()), attese \(tipi.sorted())")
    }
}

/// Le frasi italiane del server: i modelli `dafare.*` del `CATALOGO` di `fanta/frasi.py` (chiave → testo con segnaposto `{nome}`).
/// Il file si legge dal repository (il test gira nel checkout di GitHub); se non c'è, il test fallisce e lo dice.
private struct FrasiDelServer {
    let modelli: [String: String]

    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    init(file: String = #filePath) throws {
        var url = URL(fileURLWithPath: file)
        for _ in 0..<4 { url.deleteLastPathComponent() }          // SchieraxiTests, Tests, ios, radice del repository
        url.appendPathComponent("fanta/frasi.py")
        guard let sorgente = try? String(contentsOf: url, encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere fanta/frasi.py dal repository")
        }
        var trovati: [String: String] = [:]
        for riga in sorgente.split(whereSeparator: \.isNewline) {
            // una riga del catalogo:    "dafare.diario": "La giornata {n} è finita: ...",
            let t = riga.trimmingCharacters(in: .whitespaces)
            guard t.hasPrefix("\"dafare."), t.hasSuffix("\","), let separatore = t.range(of: "\": \"") else { continue }
            let fine = t.index(t.endIndex, offsetBy: -2)
            guard separatore.upperBound <= fine else { continue }
            trovati[String(t[t.index(after: t.startIndex)..<separatore.lowerBound])] = String(t[separatore.upperBound..<fine])
        }
        guard !trovati.isEmpty else { throw Errore(description: "in fanta/frasi.py non trovo nessuna frase «dafare.*»") }
        modelli = trovati
    }

    /// La frase del server con i segnaposto riempiti.
    func frase(_ chiave: String, _ parametri: [String: String] = [:]) throws -> String {
        guard var testo = modelli[chiave] else { throw Errore(description: "manca la frase «\(chiave)» in fanta/frasi.py") }
        for (nome, valore) in parametri { testo = testo.replacingOccurrences(of: "{\(nome)}", with: valore) }
        guard !testo.contains("{") else { throw Errore(description: "«\(chiave)»: segnaposto senza valore in «\(testo)»") }
        return testo
    }
}
