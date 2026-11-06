import Foundation
import Testing
@testable import Schieraxi

/// «Da fare» dei dati di prova (modalità demo e fotografie): deve dire quello che direbbe il server, con gli stessi testi
/// (`fanta/frasi.py`, chiavi `dafare.*`) e la giornata con i due numeri, lega e Serie A (#299).
/// Dati inventati: i nomi sono quelli della demo (`DatiDemo.swift`).
struct DemoDaFareTests {

    /// La risposta di Oggi della demo: la schermata normale (`oggi`) o una fase delle fotografie (`oggi-finita`).
    private func oggi(_ schermata: String) async throws -> Oggi {
        let server: FinteServer? = schermata == "oggi" ? FinteServer.demo : FinteServer.demoFase(schermata)
        let finto = try #require(server, "la demo «\(schermata)» non esiste")
        return try Decodifica.decodifica(try await finto.richiesta("GET", "/api/oggi", corpo: nil))
    }

    @Test("Il diario dice la giornata con i due numeri, lega e Serie A")
    func diarioConIlNumeroDellaLega() async throws {
        let o = try await oggi("oggi")
        let serieA = try #require(o.giornata)
        let lega = try #require(o.giornataLega)
        #expect(serieA != lega, "se i due numeri coincidono il test non distingue più la lega dalla Serie A")
        let voce = try #require(o.daFare?.first(where: { $0.tipo == "diario" }), "nella demo manca la voce del diario")
        // l'ultima giornata finita della lega è quella prima della giornata in corso, come in `_diario` di fanta/da_fare.py
        #expect(voce.testo == "Giornata \(lega - 1) · \(serieA - 1)ª di Serie A: è finita, dimmi se hai schierato la consigliata.")
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
            "diario": (try Self.fraseDiario(frasi), try frasi.frase("dafare.az_schierato")),
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

extension DemoDaFareTests {
    /// La voce del diario della demo (Serie A 10 = giornata 7 della lega). Dalla #299 il server mette in testa la giornata con i due
    /// numeri (parametro `giornata` di `dafare.diario`, `docs/API.md`). Finché `fanta/frasi.py` ha ancora la frase di prima (con
    /// `{n}`) vale il testo scritto in `docs/COERENZA-WEB-IPHONE.md`: la PR del server e questa si possono unire in qualunque ordine.
    fileprivate static func fraseDiario(_ frasi: FrasiDelServer) throws -> String {
        let nome = "Giornata 7 · 10ª di Serie A"
        guard try frasi.modello("dafare.diario").contains("{n}") else { return try frasi.frase("dafare.diario", ["giornata": nome]) }
        return "\(nome): è finita, dimmi se hai schierato la consigliata."
    }
}

/// Le frasi italiane del server: i modelli del `CATALOGO` di `fanta/frasi.py` delle famiglie in `prefissi` («dafare.»,
/// «probabili.»...), chiave → testo con segnaposto `{nome}`. Servono ai test che confrontano i testi della demo con quelli che
/// scriverebbe il server. Il file si legge dal repository (il test gira nel checkout di GitHub); se non c'è, il test fallisce e lo dice.
struct FrasiDelServer {
    let modelli: [String: String]

    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    init(prefissi: [String] = ["dafare."], file: String = #filePath) throws {
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
            guard prefissi.contains(where: { t.hasPrefix("\"" + $0) }), t.hasSuffix("\","), let separatore = t.range(of: "\": \"") else { continue }
            let fine = t.index(t.endIndex, offsetBy: -2)
            guard separatore.upperBound <= fine else { continue }
            trovati[String(t[t.index(after: t.startIndex)..<separatore.lowerBound])] = String(t[separatore.upperBound..<fine])
        }
        guard !trovati.isEmpty else {
            throw Errore(description: "in fanta/frasi.py non trovo nessuna frase \(prefissi.map { "«\($0)*»" }.joined(separator: " "))")
        }
        modelli = trovati
    }

    /// La frase del server con i segnaposto riempiti.
    /// Il modello com'è scritto nel catalogo, con i segnaposto.
    func modello(_ chiave: String) throws -> String {
        guard let testo = modelli[chiave] else { throw Errore(description: "manca la frase «\(chiave)» in fanta/frasi.py") }
        return testo
    }

    func frase(_ chiave: String, _ parametri: [String: String] = [:]) throws -> String {
        guard var testo = modelli[chiave] else { throw Errore(description: "manca la frase «\(chiave)» in fanta/frasi.py") }
        for (nome, valore) in parametri { testo = testo.replacingOccurrences(of: "{\(nome)}", with: valore) }
        guard !testo.contains("{") else { throw Errore(description: "«\(chiave)»: segnaposto senza valore in «\(testo)»") }
        return testo
    }
}
