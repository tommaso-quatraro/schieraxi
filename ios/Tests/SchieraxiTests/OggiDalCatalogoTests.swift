import Foundation
import Testing
@testable import Schieraxi

/// Le parole di Oggi vengono dal catalogo comune con la web (#494, parte di #167): `fanta/testi/` è la fonte, i file Swift di
/// `Support/Catalogo/` li genera `python script/testi.py --scrivi` per le chiavi elencate in `ios/testi/`. Le viste di Oggi e i
/// pulsanti comuni di `Support` usano `Catalogo.…`: una frase riscritta a mano in Swift non seguirebbe più la web, e qui fallisce.
@Suite("Oggi: le parole vengono dal catalogo (#494)")
struct OggiDalCatalogoTests {

    // MARK: niente testi a mano

    /// I testi del catalogo che Oggi e le parti comuni mostrano: nessuno deve stare scritto a mano, fra virgolette, nei loro file.
    static let testiFissi: [String] = [
        Catalogo.Oggi.benvenutoSchieraxi, Catalogo.Oggi.perCominciareImporta, Catalogo.Oggi.chiusa,
        Catalogo.Oggi.preparo, Catalogo.Oggi.tuaFormazione, Catalogo.Oggi.tuaFormazioneScelta, Catalogo.Oggi.puntiAttesi,
        Catalogo.Oggi.apriFormazione, Catalogo.Oggi.mancanoProbabiliFormazioni, Catalogo.Oggi.tuoiMiglioriDella,
        Catalogo.Oggi.daControllare, Catalogo.Oggi.giocatoriFormazioneCon, Catalogo.Oggi.diffidati, Catalogo.Oggi.partiteDelTurno,
        Catalogo.Oggi.dataDaDefinire, Catalogo.Oggi.partitaInCorso,
        Catalogo.Df.daFare, Catalogo.Df.urgente, Catalogo.Df.tuttoPostoMister, Catalogo.Df.nonNienteSbrigare, Catalogo.Df.apri,
        Catalogo.Live.aggiornamento, Catalogo.Live.intervallo, Catalogo.Live.finita, Catalogo.Live.rinviata, Catalogo.Live.sospesa,
        Catalogo.Comune.importaRose, Catalogo.Comune.riprova, Catalogo.Shell.impostazioni, Catalogo.Shell.chiudi, Catalogo.Nav.oggi,
    ]

    /// Le frasi con un valore dentro (segnaposto o numero): il valore si scrive «§» (o 7 per i plurali) e restano le parti fisse.
    static let frasiConValori: [String] = [
        Catalogo.Oggi.chiusaDettaglio(quando: "§"), Catalogo.Oggi.siChiude(min: "§", quando: "§"),
        Catalogo.Oggi.primaPartita(quando: "§"), Catalogo.Oggi.novitaBanner(versione: "§"), Catalogo.Oggi.indisponibili(n: "§"),
        Catalogo.Oggi.nTitolari(1), Catalogo.Oggi.nTitolari(7), Catalogo.Df.altre(1), Catalogo.Df.altre(7),
    ]

    /// Le parti fisse di una frase (almeno 6 caratteri senza spazi ai lati: le più corte potrebbero stare in tutt'altro codice).
    static func partiFisse(_ frase: String) -> [String] {
        frase.replacingOccurrences(of: #"<[^>]+>"#, with: "§", options: .regularExpression)
            .components(separatedBy: CharacterSet(charactersIn: "§17"))
            .filter { $0.trimmingCharacters(in: .whitespaces).count >= 6 }
    }

    /// I file controllati: tutti quelli di `Presentation/Oggi` e i pulsanti comuni di `Support` passati al catalogo.
    static func fileControllati(file: String = #filePath) throws -> [String] {
        let oggi = try FileManager.default.contentsOfDirectory(atPath: SorgenteDiOggi.radice(file: file).appendingPathComponent(
            "Sources/Presentation/Oggi").path)
            .filter { $0.hasSuffix(".swift") }
            .sorted()
            .map { "Sources/Presentation/Oggi/\($0)" }
        return oggi + ["Sources/Support/Design/Stati.swift", "Sources/Support/PercheNumeroView.swift"]
    }

    @Test("Nei file di Oggi e nei pulsanti comuni nessun testo del catalogo è scritto a mano")
    func nienteTestiAMano() throws {
        let file = try Self.fileControllati()
        #expect(file.contains("Sources/Presentation/Oggi/TestiOggi.swift"), "la cartella di Oggi non si legge: \(file)")
        for percorso in file {
            let codice = try SorgenteDiOggi.codice(percorso)
            for testo in Self.testiFissi {
                #expect(!codice.contains("\"\(testo)\""), "\(percorso) scrive a mano «\(testo)»: usa Catalogo.…")
            }
            for parte in Self.frasiConValori.flatMap(Self.partiFisse) {
                #expect(!codice.contains(parte), "\(percorso) scrive a mano «\(parte)»: usa Catalogo.…")
            }
        }
    }

    /// Il controllo sopra deve trovare davvero un testo scritto a mano: qui con un codice finto.
    @Test("Il controllo trova un testo del catalogo scritto a mano, anche dentro una frase con un valore")
    func ilControlloFunziona() {
        let codice = SorgenteDiOggi.soloCodice(#"""
        /// «Chiusa» nel commento non conta
        Text("Chiusa")
        return "La formazione si è chiusa \(quando)"
        #Preview("Oggi") { OggiView() }
        """#)
        #expect(codice.contains("\"\(Catalogo.Oggi.chiusa)\""))
        #expect(Self.partiFisse(Catalogo.Oggi.chiusaDettaglio(quando: "§")).contains { codice.contains($0) })
        #expect(!codice.contains("«Chiusa»"), "i commenti non contano")
        #expect(!codice.contains("\"\(Catalogo.Nav.oggi)\""), "le anteprime non contano")
    }

    // MARK: le viste usano il catalogo

    /// Le viste usano davvero le costanti del catalogo (anche dove prima l'iPhone diceva un'altra cosa e ora vince la web:
    /// la frase del benvenuto). Senza data il conto dice «Data da definire», come vuole il vocabolario.
    @Test("Le viste di Oggi e i pulsanti comuni prendono le parole dal catalogo", arguments: [
        ("Sources/Presentation/Oggi/OggiView.swift", [
            "Catalogo.Oggi.benvenutoSchieraxi", "Catalogo.Oggi.perCominciareImporta", "Catalogo.Comune.importaRose",
            "Catalogo.Oggi.dataDaDefinire", "Text(Catalogo.Oggi.chiusa)", "Catalogo.Oggi.siChiude(", "Catalogo.Oggi.primaPartita(",
            "Catalogo.Oggi.chiusaDettaglio(", "Catalogo.Oggi.preparo", "Catalogo.Nav.oggi", "Catalogo.Df.daFare",
            "Catalogo.Df.urgente", "Catalogo.Df.altre(", "Catalogo.Df.tuttoPostoMister", "Catalogo.Df.nonNienteSbrigare",
            "Catalogo.Df.apri", "Catalogo.Oggi.daControllare", "Catalogo.Oggi.giocatoriFormazioneCon", "Catalogo.Oggi.indisponibili(",
            "Catalogo.Oggi.diffidati", "Catalogo.Oggi.tuoiMiglioriDella",
        ]),
        ("Sources/Presentation/Oggi/CartaFormazioneOggi.swift", [
            "Catalogo.Oggi.apriFormazione", "Catalogo.Oggi.mancanoProbabiliFormazioni", "Catalogo.Oggi.puntiAttesi",
        ]),
        ("Sources/Presentation/Oggi/PartiteDelTurnoView.swift", [
            "Catalogo.Oggi.partiteDelTurno", "Catalogo.Live.intervallo", "Catalogo.Live.sospesa", "Catalogo.Live.finita",
            "Catalogo.Live.rinviata", "Catalogo.Oggi.partitaInCorso", "Catalogo.Oggi.nTitolari(", "Catalogo.Live.aggiornamento",
        ]),
        ("Sources/Presentation/Oggi/OggiViewModel.swift", ["Catalogo.Oggi.dataDaDefinire"]),
        ("Sources/Presentation/Oggi/TestiOggi.swift", [
            "Catalogo.Oggi.tuaFormazione", "Catalogo.Oggi.tuaFormazioneScelta", "Catalogo.Oggi.novitaBanner(",
        ]),
        ("Sources/Support/Design/Stati.swift", ["Catalogo.Comune.riprova", "Catalogo.Shell.impostazioni"]),
        ("Sources/Support/PercheNumeroView.swift", ["Catalogo.Shell.chiudi"]),
    ])
    func vistaUsaIlCatalogo(percorso: String, costanti: [String]) throws {
        let codice = try SorgenteDiOggi.codice(percorso)
        for costante in costanti {
            #expect(codice.contains(costante), "\(percorso) non usa \(costante)")
        }
    }

    // MARK: frasi con un valore

    @Test("Il titolo della formazione: «La tua formazione», con la tua scelta «La tua formazione · la tua scelta»")
    func titoloFormazione() {
        #expect(TestiOggi.titoloFormazione(tuaScelta: false) == Catalogo.Oggi.tuaFormazione)
        #expect(TestiOggi.titoloFormazione(tuaScelta: true) == Catalogo.Oggi.tuaFormazioneScelta)
    }

    /// La web scrive il banner in grassetto con `<b>`; l'iPhone mette il grassetto con SwiftUI e toglie i segni.
    @Test("Il banner delle novità: la frase del catalogo senza i segni del grassetto della web")
    func bannerSenzaSegni() {
        #expect(TestiOggi.novita("1.427") == "Novità della versione 1.427")
        #expect(Catalogo.Oggi.novitaBanner(versione: "1.427").contains("Novità della versione 1.427"))
        #expect(!TestiOggi.novita("1.427").contains("<"))
    }

    @MainActor
    @Test("Sotto il conto alla rovescia le frasi del catalogo, con quando e i minuti della lega")
    func quandoSiChiude() throws {
        let adesso = try #require(Quando.data("2026-10-29 10:00"))
        let conScadenza: Oggi = try Decodifica.decodifica(Data(
            #"{"giornata": 11, "inizio": "2026-10-31 15:00", "scadenza": "2026-10-31 14:50", "minuti_scadenza": 10}"#.utf8))
        #expect(OggiView.quandoSiChiude(conScadenza, adesso: adesso)
                == Catalogo.Oggi.siChiude(min: "10", quando: Quando.leggibile("2026-10-31 14:50", adesso: adesso)))
        let senzaScadenza: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11, "inizio": "2026-10-31 15:00"}"#.utf8))
        #expect(OggiView.quandoSiChiude(senzaScadenza, adesso: adesso)
                == Catalogo.Oggi.primaPartita(quando: Quando.leggibile("2026-10-31 15:00", adesso: adesso)))
        #expect(OggiView.siEChiusa(conScadenza, adesso: adesso)
                == Catalogo.Oggi.chiusaDettaglio(quando: Quando.leggibile("2026-10-31 14:50", adesso: adesso)))
    }
}

/// Il codice Swift di un file dell'app (percorso dalla cartella `ios/`, come fa `DemoFormazioneInCorsoTests`), senza commenti né
/// anteprime.
private enum SorgenteDiOggi {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    /// La cartella `ios/`.
    static func radice(file: String = #filePath) -> URL {
        var url = URL(fileURLWithPath: file)
        for _ in 0..<3 { url.deleteLastPathComponent() }          // OggiDalCatalogoTests.swift, SchieraxiTests, Tests
        return url
    }

    static func codice(_ percorso: String, file: String = #filePath) throws -> String {
        guard let testo = try? String(contentsOf: radice(file: file).appendingPathComponent(percorso), encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere ios/\(percorso)")
        }
        return soloCodice(testo)
    }

    /// Senza le righe di commento (`//`, `///`), i commenti in fondo alla riga e le anteprime (`#Preview("…")`).
    static func soloCodice(_ testo: String) -> String {
        testo.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.hasPrefix("//") && !$0.hasPrefix("#Preview") }
            .map { riga in riga.range(of: " //").map { String(riga[..<$0.lowerBound]) } ?? riga }
            .joined(separator: "\n")
    }
}
