import Foundation
import Testing
@testable import Schieraxi

/// Squadra e Altro prendono i testi dal catalogo comune con la web (#496, lavoro A4 dell'ondata 2): le chiavi elencate in
/// `ios/testi/` diventano i file generati `Support/Catalogo/Catalogo+*.swift`, e i file dell'area li usano invece di riscriverli.
/// Qui si legge il sorgente: nessun testo del catalogo è scritto di nuovo tra virgolette. Una frase copiata a mano tornerebbe a
/// cambiare su un lato solo. I file si leggono dalla cartella `ios/` del repository.
@Suite("Squadra e Altro: le parole vengono dal catalogo")
struct SquadraAltroDalCatalogoTests {
    /// I file generati dei prefissi di quest'area (da `ios/Sources/Support/Catalogo/`).
    static let generati = ["Aggiorna", "Ar", "Av", "Diario", "Lega", "Mercato", "Novita", "Regole", "Scambio", "Sd"]
        .map { "Catalogo+\($0).swift" }

    /// I file con le sole parole dell'area (da `ios/Sources/Presentation/`): nessun testo del catalogo, nemmeno corto.
    static let fileDeiTesti = [
        "Lega/TestiRegole.swift", "Lega/ParoleSquadre.swift", "Lega/VoceMenuLega.swift",
        "Lega/ParoleRegistro.swift", "Lega/ParoleRegistro+Taratura.swift", "Lega/ParoleNostri.swift", "Lega/ParoleConsiglio.swift",
        "Lega/ParoleNovita.swift",
    ]

    /// Le viste e i modelli dell'area che mostrano testi del catalogo: nessuna frase del catalogo (le parole corte come «Salva» o
    /// «Tutti» possono servire anche come valori, quindi qui non si guardano).
    static let viste = [
        "Lega/RegoleEditor.swift", "Lega/ImportaRoseView.swift", "Lega/DiarioView.swift", "Lega/FormazioneManualeDiarioView.swift",
        "Lega/EsitoRoseSalvate.swift", "Lega/Gestione.swift", "Lega/LegaPagine.swift", "Lega/LegaExtra.swift", "Lega/LegaView.swift",
        "Lega/LegaViewModels.swift", "Lega/LegaViewModels2.swift", "Lega/RigaRosa.swift", "Lega/QuantoCiAbbiamoPresoView.swift",
        "Mercato/RigaElencoGiocatore.swift", "Mercato/DatiRigaElenco.swift", "Mercato/RicercaGiocatoreView.swift",
    ]

    /// Una frase del catalogo con almeno tanti caratteri fissi non si trova per caso in un altro testo.
    static let lunghezzaMinima = 12

    /// Un file di `ios/` (percorso dalla cartella `ios/`), senza le righe di commento e i nomi delle anteprime (`#Preview("…")`).
    private static func codice(_ percorso: String, file: String = #filePath) throws -> String {
        var cartella = URL(fileURLWithPath: file)
        for _ in 0..<3 { cartella.deleteLastPathComponent() }          // questo file, SchieraxiTests, Tests
        let testo = try #require(try? String(contentsOf: cartella.appendingPathComponent(percorso), encoding: .utf8),
                                 "non riesco a leggere ios/\(percorso)")
        return testo.split(separator: "\n", omittingEmptySubsequences: false)
            .filter { riga in
                let inizio = riga.trimmingCharacters(in: .whitespaces)
                return !inizio.hasPrefix("//") && !inizio.hasPrefix("#Preview")
            }
            .joined(separator: "\n")
    }

    /// I testi tra virgolette di un sorgente Swift, così come sono scritti (con gli escape).
    static func letterali(_ codice: String) throws -> [String] {
        let forma = try NSRegularExpression(pattern: #""((?:[^"\\\n]|\\.)*)""#)
        let tutto = NSRange(codice.startIndex..., in: codice)
        return forma.matches(in: codice, range: tutto).compactMap { m in Range(m.range(at: 1), in: codice).map { String(codice[$0]) } }
    }

    /// Il testo con ogni segnaposto `\(…)` scritto «§»: «Versione \(v)» e «Versione \(numero)» hanno la stessa forma.
    static func forma(_ letterale: String) -> String {
        letterale.replacingOccurrences(of: #"\\\((?:[^()]|\([^()]*\))*\)"#, with: "§", options: .regularExpression)
    }

    /// I pezzi fissi di un testo, cioè quello che sta fra un segnaposto e l'altro.
    static func pezzi(_ letterale: String) -> [String] {
        forma(letterale).split(separator: "§").map(String.init)
    }

    /// Le forme dei testi dei file generati dell'area che hanno almeno una lettera (non «§ · §», che è solo un separatore).
    private static func formeDelCatalogo() throws -> Set<String> {
        Set(try generati.flatMap { try letterali(codice("Sources/Support/Catalogo/\($0)")) }.map(forma)
            .filter { $0.contains(where: \.isLetter) })
    }

    /// I testi di `percorso` che riscrivono il catalogo: uguali a un suo testo (per le viste solo se lungo), o con dentro un pezzo
    /// lungo di una sua frase con i segnaposto.
    private static func copie(in percorso: String, ancheCorte: Bool) throws -> [String] {
        let catalogo = try formeDelCatalogo()
        let pezziLunghi = catalogo.filter { $0.contains("§") }.flatMap(pezzi).filter { $0.count >= lunghezzaMinima }
        return try letterali(codice("Sources/Presentation/\(percorso)")).map(forma).filter { scritto in
            let fissi = scritto.replacingOccurrences(of: "§", with: "").count
            let uguale = catalogo.contains(scritto) && (ancheCorte || fissi >= lunghezzaMinima)
            return uguale || pezziLunghi.contains { scritto.contains($0) }
        }
    }

    @Test("I file generati dell'area ci sono e hanno testi")
    func generatiPresenti() throws {
        for nome in Self.generati {
            let testi = try Self.letterali(Self.codice("Sources/Support/Catalogo/\(nome)"))
            #expect(!testi.isEmpty, "\(nome) senza testi")
        }
    }

    @Test("Le parole di Squadra e Altro vengono dal catalogo: i file dei testi non ne riscrivono nessuna",
          arguments: SquadraAltroDalCatalogoTests.fileDeiTesti)
    func fileDeiTestiSenzaCopie(percorso: String) throws {
        let copie = try Self.copie(in: percorso, ancheCorte: true)
        #expect(copie.isEmpty, "testi del catalogo scritti in \(percorso): usa Catalogo")
    }

    @Test("Le viste di Squadra e Altro non riscrivono le frasi del catalogo", arguments: SquadraAltroDalCatalogoTests.viste)
    func visteSenzaCopie(percorso: String) throws {
        let copie = try Self.copie(in: percorso, ancheCorte: false)
        #expect(copie.isEmpty, "frasi del catalogo scritte in \(percorso): usa Catalogo")
    }

    @Test("Forma e pezzi di un testo: i segnaposto non contano, gli escape restano")
    func formaDiUnTesto() throws {
        #expect(Self.forma(#"Versione \(numero)"#) == Self.forma(#"Versione \(v)"#))
        #expect(Self.forma(#"crediti \(Formato.intero(c ?? 0))"#) == "crediti §")
        #expect(Self.pezzi(#"Media \(m) bonus \(b) punti"#) == ["Media ", " bonus ", " punti"])
        #expect(Self.pezzi("Cosa vuoi fare") == ["Cosa vuoi fare"])
        #expect(try Self.letterali(#"static let a = "Dici \"sì\"" + "b""#) == [#"Dici \"sì\""#, "b"])
    }
}
