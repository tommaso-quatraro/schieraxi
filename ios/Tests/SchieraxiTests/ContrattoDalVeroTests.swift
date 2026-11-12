import Foundation
import Testing
@testable import Schieraxi

/// Contratto fra iPhone e server, dal vero (#507, lavoro F2 del piano `docs/superpowers/plans/2026-11-08-ondata-2.md`): le risposte
/// vere del server registrate in `ios/fotografie/vero-*.json` (nomi inventati, `prove/fotografie_dal_vero.py`) si leggono con lo
/// stesso tipo e lo stesso decodificatore che usa l'app. Se il server cambia un campo che l'app legge, lo dice questo test, con
/// indirizzo e percorso del campo, e non l'utente con «una risposta che l'app non capisce». Il controllo dei soli nomi dei campi,
/// senza Mac, è `tests/contratto_ios.py` (F1).
@Suite("Contratto dal vero: le risposte vere si leggono con i modelli dell'app")
struct ContrattoDalVeroTests {
    /// Le tre fotografie: prima della scadenza, giornata in corso, giornata finita.
    static let scenari = ["vero-prima", "vero-in-corso", "vero-finita"]

    // MARK: come legge l'app

    /// Come l'app legge una risposta: il tipo (per i messaggi) e la stessa chiamata che fa l'app.
    struct Lettura: Sendable {
        let tipo: String
        /// nil se la risposta si legge; altrimenti cosa non va, con il percorso del campo.
        let problema: @Sendable (Data) -> String?

        /// `Decodifica.decodifica(_:snake:)`: la usano `get`, `posta` e `Caricatore` (snake: false dove lo usa l'app).
        static func modello<T: Decodable>(_ tipo: T.Type, snake: Bool = true) -> Lettura {
            Lettura(tipo: "\(T.self)" + (snake ? "" : " (snake: false)")) { dati in
                do {
                    let _: T = try Decodifica.decodifica(dati, snake: snake)
                    return nil
                } catch {
                    return ContrattoDalVeroTests.spiegazione(T.self, dati, snake: snake) ?? "\(error)"
                }
            }
        }

        /// `RiassuntoWidget.leggi`: la usano l'app e il widget per `/api/widget` (`ScaricoWidget`).
        static let widget = Lettura(tipo: "RiassuntoWidget (RiassuntoWidget.leggi)") { dati in
            guard RiassuntoWidget.leggi(dati) == nil else { return nil }
            return ContrattoDalVeroTests.spiegazione(RiassuntoWidget.self, dati, snake: true)
                ?? "RiassuntoWidget.leggi la scarta anche se il JSON si legge (\(dati.count) byte)"
        }
    }

    /// Rotta (indirizzo senza parametri, `{id}` al posto dei numeri) → come la legge l'app; dove la legge in più modi, tutti.
    /// Manca solo `StatoLega` della configurazione guidata (`/api/stato`): è privato e legge ogni campo con `try?`, non può fallire.
    static let letture: [String: [Lettura]] = [
        "/api/account/me": [.modello(RispostaAccount.self)],
        "/api/affidabilita": [.modello(Affidabilita.self)],
        "/api/avvisi": [.modello(StatoAvvisi.self, snake: false)],
        "/api/calendario": [.modello(Calendario.self)],
        "/api/classifica": [.modello(ElencoGiocatori.self)],
        "/api/diario": [.modello(DiarioRisposta.self)],
        "/api/formazione": [.modello(Formazione.self)],
        "/api/formazione/valuta": [.modello(ValutazioneManuale.self)],
        "/api/funzioni": [.modello(RispostaFunzioni.self, snake: false)],
        "/api/giocatore/{id}": [.modello(SchedaGiocatore.self)],
        "/api/giocatori": [.modello([GiocatoreBreve].self)],
        "/api/oggi": [.modello(Oggi.self)],   // anche il ripiego del widget senza `/api/widget` (stesse chiavi)
        "/api/primo-avvio": [.modello(PrimoAvvioRisposta.self)],
        "/api/regole": [.modello(JSONValue.self, snake: false)],
        "/api/rosa": [.modello(Rosa.self)],
        "/api/scelta": [.modello(SceltaSalvata?.self)],   // «null» se non c'è una scelta salvata
        "/api/squadre": [.modello([SquadraLega].self)],
        "/api/stagione": [.modello(StatoStagione.self)],
        "/api/stato": [.modello(InfoServer.self), .modello(StatoSorgente.self)],
        "/api/stato-dati": [.modello(StatoDati.self)],
        "/api/widget": [.widget],
    ]

    /// Rotte registrate che l'app non decodifica, con il motivo.
    static let nonLette: [String: String] = [
        "/api/asta": "l'asta c'è solo sulla web",
        "/api/confronto": ContrattoDalVeroTests.tolta,
        "/api/diario/schierata": "l'app la manda (POST) e non legge la risposta",
        "/api/formazione/testo": "testo semplice per la web: l'app non la chiede",
        "/api/live": ContrattoDalVeroTests.tolta,
        "/api/mercato": ContrattoDalVeroTests.tolta,
        "/api/movimenti": ContrattoDalVeroTests.tolta,
        "/api/osservati": ContrattoDalVeroTests.tolta,
        "/api/scambi/analizza": ContrattoDalVeroTests.tolta,
        "/api/scambi/da-testo": ContrattoDalVeroTests.tolta,
        "/api/scambi/limite": ContrattoDalVeroTests.tolta,
        "/api/scambi/proposte": ContrattoDalVeroTests.tolta,
    ]

    /// Il motivo delle rotte delle schermate tolte il 12/11/2026 (#634): le fotografie le hanno ancora, l'app non le chiede più.
    static let tolta = "la schermata non c'è più dal 12/11/2026 (#634): l'app non la chiede"

    // MARK: test

    @Test("Ogni risposta vera si legge come la legge l'app", arguments: ContrattoDalVeroTests.scenari)
    func risposteVere(scenario: String) throws {
        let risposte = try Self.risposte(scenario)
        try #require(!risposte.isEmpty, "\(scenario): nessuna risposta nella fotografia")
        for (indirizzo, testo) in risposte.sorted(by: { $0.key < $1.key }) {
            // le rotte fuori dalla tabella le segnala `ogniRottaHaLaSuaLettura`
            for lettura in Self.letture[Self.rotta(indirizzo)] ?? [] {
                let problema = lettura.problema(Data(testo.utf8))
                #expect(problema == nil, "\(scenario) \(indirizzo) letto come \(lettura.tipo): \(problema ?? "")")
            }
        }
    }

    @Test("Ogni rotta registrata sta nella tabella o tra quelle che l'app non legge")
    func ogniRottaHaLaSuaLettura() throws {
        var registrate: Set<String> = []
        for scenario in Self.scenari {
            for indirizzo in try Self.risposte(scenario).keys.sorted() {
                let rotta = Self.rotta(indirizzo)
                registrate.insert(rotta)
                #expect(Self.letture[rotta] != nil || Self.nonLette[rotta] != nil,
                        "\(scenario) \(indirizzo): la rotta \(rotta) non è in tabella. Se l'app la legge, aggiungi a `letture` il tipo e il decodificatore che usa; se no, scrivila in `nonLette` con il motivo.")
            }
        }
        let doppie = Set(Self.letture.keys).intersection(Self.nonLette.keys)
        #expect(doppie.isEmpty, "rotte sia in `letture` sia in `nonLette`: \(doppie.sorted())")
        let senzaRisposta = Set(Self.letture.keys).union(Self.nonLette.keys).subtracting(registrate)
        #expect(senzaRisposta.isEmpty,
                "rotte senza una risposta vera nelle fotografie: \(senzaRisposta.sorted()). Rifai le fotografie con prove/fotografie_dal_vero.py, oppure togli la riga.")
    }

    /// Il controllo sa fallire: un campo che manca o che cambia tipo dà un problema con il suo percorso (risposte inventate).
    static let rosaRotta: [(String, String)] = [
        (#"{"giocatori": []}"#, "manca il campo «nome»"),
        (#"{"nome": "Squadra Prova", "giocatori": "nessuno"}"#, "campo «giocatori»"),
        (#"{"nome": "Squadra Prova", "giocatori": [{"id": 1, "nome": 7}]}"#, "campo «giocatori[0].nome»"),
    ]

    @Test("Un campo rotto si vede, con il suo percorso", arguments: ContrattoDalVeroTests.rosaRotta)
    func campoRotto(json: String, atteso: String) throws {
        let problema = try #require(Lettura.modello(Rosa.self).problema(Data(json.utf8)))
        #expect(problema.contains(atteso), "problema: \(problema)")
    }

    @Test("Nel messaggio i campi hanno il nome del server")
    func nomiDelServer() {
        #expect(Self.nomeDelServer("creditiResidui") == "crediti_residui")
        #expect(Self.nomeDelServer("fvAtteso") == "fv_atteso")
        #expect(Self.nomeDelServer("nome") == "nome")
    }

    @Test("Anche la lettura del widget sa fallire")
    func widgetRotto() throws {
        let problema = try #require(Lettura.widget.problema(Data("[1]".utf8)))
        #expect(problema.contains("(radice)"), "problema: \(problema)")
    }

    // MARK: strumenti

    struct Fotografia: Decodable {
        let risposte: [String: String]
    }

    /// Le risposte registrate di `ios/fotografie/<scenario>.json`, indirizzo → testo della risposta.
    static func risposte(_ scenario: String) throws -> [String: String] {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()   // SchieraxiTests
            .deletingLastPathComponent()   // Tests
            .deletingLastPathComponent()   // ios
            .appendingPathComponent("fotografie", isDirectory: true)
            .appendingPathComponent(scenario + ".json")
        return try JSONDecoder().decode(Fotografia.self, from: Data(contentsOf: url)).risposte
    }

    /// «/api/giocatore/4312» → «/api/giocatore/{id}», «/api/rosa?squadra=…» → «/api/rosa».
    static func rotta(_ indirizzo: String) -> String {
        indirizzo.prefix { $0 != "?" }
            .split(separator: "/", omittingEmptySubsequences: false)
            .map { parte in !parte.isEmpty && parte.allSatisfy { ("0"..."9").contains($0) } ? "{id}" : String(parte) }
            .joined(separator: "/")
    }

    /// Lo stesso decodificatore di `Decodifica` (chiavi da snake_case se `snake`), per dire quale campo non va: `Decodifica`
    /// tiene solo 160 caratteri dell'errore.
    static func spiegazione<T: Decodable>(_ tipo: T.Type, _ dati: Data, snake: Bool) -> String? {
        let d = JSONDecoder()
        if snake { d.keyDecodingStrategy = .convertFromSnakeCase }
        do {
            _ = try d.decode(T.self, from: dati)
            return nil
        } catch let errore as DecodingError {
            switch errore {
            case .keyNotFound(let chiave, let c):
                return "manca il campo «\(percorso(c.codingPath + [chiave], snake: snake))»"
            case .typeMismatch(let atteso, let c):
                return "campo «\(percorso(c.codingPath, snake: snake))»: l'app vuole \(atteso). \(c.debugDescription)"
            case .valueNotFound(let atteso, let c):
                return "campo «\(percorso(c.codingPath, snake: snake))»: è null, l'app vuole \(atteso)"
            case .dataCorrupted(let c):
                return "campo «\(percorso(c.codingPath, snake: snake))»: \(c.debugDescription)"
            @unknown default:
                return "\(errore)"
            }
        } catch {
            return "\(error)"
        }
    }

    /// Il percorso di un campo: «giocatori[0].nome»; «(radice)» per la risposta intera. Con `snake` i nomi tornano quelli del
    /// server («creditiResidui» → «crediti_residui»), così si ritrovano nel JSON.
    static func percorso(_ chiavi: [any CodingKey], snake: Bool = false) -> String {
        let testo = chiavi.reduce(into: "") { testo, chiave in
            if let indice = chiave.intValue {
                testo += "[\(indice)]"
            } else {
                let nome = snake ? nomeDelServer(chiave.stringValue) : chiave.stringValue
                testo += (testo.isEmpty ? "" : ".") + nome
            }
        }
        return testo.isEmpty ? "(radice)" : testo
    }

    /// Da camelCase a snake_case, al contrario di `.convertFromSnakeCase`.
    static func nomeDelServer(_ nome: String) -> String {
        nome.reduce(into: "") { testo, lettera in
            if lettera.isUppercase {
                testo += "_" + lettera.lowercased()
            } else {
                testo.append(lettera)
            }
        }
    }
}
