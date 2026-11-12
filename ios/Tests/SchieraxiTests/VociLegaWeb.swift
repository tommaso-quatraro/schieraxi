import Foundation
import Testing

/// Le voci dei menu Squadra e Altro della web e i nomi delle funzioni del server. Le voci sono una copia ferma del blocco
/// `const VOCI_LEGA = [ … ];` di `fanta/web/app.js` presa il 12/11/2026, prima del rifacimento della web (spec
/// `2026-11-12-revisione-generale-design`): l'app resta com'è finché il proprietario non decide, quindi la prova non segue più
/// la web. Le funzioni si leggono da `FUNZIONI` di `fanta/funzioni.py` (il server, che l'app usa ancora).
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

    /// `VOCI_LEGA` della web com'era il 12/11/2026, nello stesso ordine.
    static let vociFerme: [Voce] = [
        Voce(id: "squadre", ambito: "squadra", funzione: nil,
             chiaveNome: "lega.voce_squadre", chiaveDettaglio: "lega.voce_squadre_sub"),
        Voce(id: "consigli", ambito: "squadra", funzione: nil,
             chiaveNome: "lega.voce_consigli", chiaveDettaglio: "lega.voce_consigli_sub"),
        Voce(id: "osservati", ambito: "squadra", funzione: "seguiti",
             chiaveNome: "lega.voce_osservati", chiaveDettaglio: "lega.voce_osservati_sub"),
        Voce(id: "giocatori", ambito: "squadra", funzione: "elenco_giocatori",
             chiaveNome: "lega.voce_giocatori", chiaveDettaglio: "lega.voce_giocatori_sub"),
        Voce(id: "calendario", ambito: "squadra", funzione: "elenco_giocatori",
             chiaveNome: "lega.voce_calendario", chiaveDettaglio: "lega.voce_calendario_sub"),
        Voce(id: "importa", ambito: "squadra", funzione: nil,
             chiaveNome: "lega.voce_importa", chiaveDettaglio: "lega.voce_importa_sub"),
        Voce(id: "scambi", ambito: "altro", funzione: nil,
             chiaveNome: "lega.voce_scambi", chiaveDettaglio: "lega.voce_scambi_sub"),
        Voce(id: "diario", ambito: "altro", funzione: "diario",
             chiaveNome: "lega.voce_diario", chiaveDettaglio: "lega.voce_diario_sub"),
        Voce(id: "regole", ambito: "altro", funzione: nil,
             chiaveNome: "lega.voce_regole", chiaveDettaglio: "lega.voce_regole_sub"),
        Voce(id: "movimenti", ambito: "altro", funzione: "movimenti",
             chiaveNome: "lega.voce_movimenti", chiaveDettaglio: "lega.voce_movimenti_sub"),
        Voce(id: "crediti", ambito: "altro", funzione: "crediti",
             chiaveNome: "lega.voce_crediti", chiaveDettaglio: "lega.voce_crediti_sub"),
        Voce(id: "stagione", ambito: "altro", funzione: nil,
             chiaveNome: "lega.voce_stagione", chiaveDettaglio: "lega.voce_stagione_sub"),
        Voce(id: "novita", ambito: "altro", funzione: "novita",
             chiaveNome: "lega.voce_novita", chiaveDettaglio: "lega.voce_novita_sub"),
    ]

    let voci: [Voce]
    /// Tutte le funzioni che il server conosce, nell'ordine di `fanta/funzioni.py`.
    let funzioniServer: [String]

    init(file: String = #filePath) throws {
        var radice = URL(fileURLWithPath: file)
        for _ in 0..<4 { radice.deleteLastPathComponent() }          // VociLegaWeb.swift, SchieraxiTests, Tests, ios
        voci = Self.vociFerme
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
