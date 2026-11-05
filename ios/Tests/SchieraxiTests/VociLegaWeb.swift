import Foundation
import Testing

/// Le voci dei menu Squadra e Altro della web, lette dal repository: il blocco `const VOCI_LEGA = [ … ];` di `fanta/web/app.js`
/// (id, scheda, funzione che accende la voce, chiavi di `testi.js` per il nome e la riga sotto) e i nomi delle funzioni del
/// server (`FUNZIONI` di `fanta/funzioni.py`). Così una voce spostata, aggiunta o tolta su un lato solo fa fallire i test.
struct VociLegaWeb {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    /// Una riga di `VOCI_LEGA`: `{ id: "calendario", ambito: "squadra", f: "elenco_giocatori", nome: t("lega.voce_calendario"), sub: t("…"), … }`.
    struct Voce: Equatable, Sendable, CustomTestStringConvertible {
        let id: String
        let ambito: String
        /// La funzione (`f`) che accende la voce; nil = la voce c'è sempre.
        let funzione: String?
        let chiaveNome: String
        let chiaveDettaglio: String

        var testDescription: String { "\(ambito)/\(id)" }
    }

    let voci: [Voce]
    /// Tutte le funzioni che il server conosce, nell'ordine di `fanta/funzioni.py`.
    let funzioniServer: [String]

    init(file: String = #filePath) throws {
        var radice = URL(fileURLWithPath: file)
        for _ in 0..<4 { radice.deleteLastPathComponent() }          // VociLegaWeb.swift, SchieraxiTests, Tests, ios
        voci = try Self.vociLega(Self.leggi(radice, "fanta/web/app.js"))
        funzioniServer = try Self.funzioni(Self.leggi(radice, "fanta/funzioni.py"))
    }

    /// Le voci di una scheda («squadra» o «altro»), nell'ordine della web.
    func voci(_ ambito: String) -> [Voce] { voci.filter { $0.ambito == ambito } }

    private static func leggi(_ radice: URL, _ percorso: String) throws -> String {
        guard let testo = try? String(contentsOf: radice.appendingPathComponent(percorso), encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere \(percorso) dal repository")
        }
        return testo
    }

    private static func vociLega(_ app: String) throws -> [Voce] {
        guard let inizio = app.range(of: "const VOCI_LEGA = ["),
              let fine = app.range(of: "\n];", range: inizio.upperBound..<app.endIndex) else {
            throw Errore(description: "in fanta/web/app.js non trovo il blocco «const VOCI_LEGA = [ … ];»")
        }
        let righe = app[inizio.upperBound..<fine.lowerBound]
            .split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { $0.hasPrefix("{ id:") }
        let forma = try NSRegularExpression(pattern:
            #"^\{ id: "([a-z_]+)", ambito: "([a-z]+)", (?:f: "([a-z_]+)", )?nome: t\("([a-z_.]+)"\), sub: t\("([a-z_.]+)"\)"#)
        let voci = try righe.map { riga -> Voce in
            let tutta = NSRange(riga.startIndex..., in: riga)
            guard let m = forma.firstMatch(in: riga, range: tutta) else {
                throw Errore(description: "riga di VOCI_LEGA in una forma che il test non sa leggere: \(riga)")
            }
            func pezzo(_ i: Int) -> String? { Range(m.range(at: i), in: riga).map { String(riga[$0]) } }
            guard let id = pezzo(1), let ambito = pezzo(2), let nome = pezzo(4), let sotto = pezzo(5) else {
                throw Errore(description: "riga di VOCI_LEGA senza id, ambito, nome o sub: \(riga)")
            }
            return Voce(id: id, ambito: ambito, funzione: pezzo(3), chiaveNome: nome, chiaveDettaglio: sotto)
        }
        guard !voci.isEmpty else { throw Errore(description: "VOCI_LEGA di fanta/web/app.js è vuoto") }
        return voci
    }

    /// Le chiavi di `FUNZIONI` in `fanta/funzioni.py`: le righe `    "elenco_giocatori": ("Elenco dei giocatori", …),`.
    private static func funzioni(_ sorgente: String) throws -> [String] {
        let forma = try NSRegularExpression(pattern: #"^    "([a-z_]+)": \(""#, options: .anchorsMatchLines)
        let tutta = NSRange(sorgente.startIndex..., in: sorgente)
        let chiavi = forma.matches(in: sorgente, range: tutta).compactMap { m in
            Range(m.range(at: 1), in: sorgente).map { String(sorgente[$0]) }
        }
        guard !chiavi.isEmpty else { throw Errore(description: "in fanta/funzioni.py non trovo le funzioni di FUNZIONI") }
        return chiavi
    }
}
