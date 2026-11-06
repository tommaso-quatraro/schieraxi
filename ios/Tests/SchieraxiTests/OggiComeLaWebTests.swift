import Foundation
import Testing
@testable import Schieraxi

/// Oggi come la web (#416, parte di #167). Con la grafica B (#415) la web parte dalla giornata con il conto alla rovescia, senza il
/// nome SchieraXI e lo slogan, e ha un ordine nuovo: la formazione con «Apri la formazione» subito sotto il conto, poi Partita
/// rinviata, Da fare e novità; poi I tuoi migliori, Da controllare, Indisponibili, Diffidati e Partite del turno.
/// L'ordine dell'iPhone sta in un posto solo (`SezioneOggi.ordine`, che la schermata percorre) e qui si confronta con l'ordine in cui
/// `mostraOggi` di `fanta/web/app.js` scrive le sezioni: una sezione spostata su un lato solo fa fallire il test.
@Suite("Oggi come la web: niente nome in cima, sezioni nell'ordine della web (#416)")
struct OggiComeLaWebTests {

    // MARK: ordine delle sezioni

    @Test("Prima della scadenza: conto, formazione, rinvio, Da fare, novità, migliori, Da controllare, indisponibili, diffidati, partite")
    func ordinePrima() {
        #expect(SezioneOggi.ordine(fase: .prima, conGiornata: true) == [
            .benvenuto, .conto, .formazione, .rinvio, .daFare, .novita,
            .suggerimento, .migliori, .daControllare, .indisponibili, .diffidati, .partite,
        ])
    }

    @Test("Giornata in corso: conto, punti finora, chi va a punteggio, cambi dalla panchina, rinvio, Da fare, novità, partite")
    func ordineInCorso() {
        #expect(SezioneOggi.ordine(fase: .inCorso, conGiornata: true) == [
            .benvenuto, .conto, .inCorso, .chiGioca, .cambiPanchina, .rinvio, .daFare, .novita, .partite,
        ])
    }

    @Test("Giornata finita: conto, riepilogo, formazione della prossima, rinvio, Da fare, novità, indisponibili, diffidati, partite")
    func ordineFinita() {
        #expect(SezioneOggi.ordine(fase: .finita, conGiornata: true) == [
            .benvenuto, .conto, .riepilogo, .formazione, .rinvio, .daFare, .novita, .indisponibili, .diffidati, .partite,
        ])
    }

    @Test("Senza giornata: al posto del conto la frase «Nessuna giornata», e niente formazione")
    func senzaGiornata() {
        for fase in [FaseGiornata.prima, .inCorso, .finita] {
            let sezioni = SezioneOggi.ordine(fase: fase, conGiornata: false)
            #expect(Array(sezioni.prefix(2)) == [.benvenuto, .senzaGiornata], "\(fase)")
            #expect(!sezioni.contains(.conto), "\(fase)")
            #expect(!sezioni.contains(.formazione), "\(fase)")
        }
    }

    @Test("Ogni fase ha le sezioni nell'ordine in cui la web le scrive in mostraOggi", arguments: [FaseGiornata.prima, .inCorso, .finita])
    func ordineComeLaWeb(fase: FaseGiornata) throws {
        let web = try OggiWeb()
        let sezioni = SezioneOggi.ordine(fase: fase, conGiornata: true)
        let posizioni = try sezioni.compactMap(OggiWeb.segno).map { try web.posizione($0) }
        #expect(!posizioni.isEmpty)
        #expect(posizioni == posizioni.sorted(), "ordine dell'iPhone \(sezioni) diverso da quello della web")
    }

    @Test("Giornata in corso: prima chi va a punteggio, poi i cambi dalla panchina, come la carta della web")
    func inCorsoComeLaWeb() throws {
        let web = try OggiWeb()
        let righe = try #require(web.cardInCorso.range(of: "a_punteggio"), "cardInCorso non ha più le righe di chi va a punteggio")
        let cambi = try #require(web.cardInCorso.range(of: "\"oggi.cambi_panchina\""), "cardInCorso non ha più i cambi dalla panchina")
        #expect(righe.lowerBound < cambi.lowerBound)
        let sezioni = SezioneOggi.ordine(fase: .inCorso, conGiornata: true)
        let chi = try #require(sezioni.firstIndex(of: .chiGioca))
        let panchina = try #require(sezioni.firstIndex(of: .cambiPanchina))
        #expect(chi < panchina)
    }

    // MARK: testa della schermata

    @Test("In cima a Oggi niente nome SchieraXI né slogan: si parte dalla giornata con il conto alla rovescia")
    func nienteNomeNeSlogan() throws {
        let sorgente = try OggiWeb.sorgenteIPhone("ios/Sources/Presentation/Oggi/OggiView.swift")
        #expect(!sorgente.contains("WordmarkSchieraXI"), "OggiView disegna ancora il nome SchieraXI")
        #expect(!sorgente.contains("SloganSchieraXI"), "OggiView mostra ancora lo slogan")
        #expect(!sorgente.contains("Schierali"))
        // la prima sezione con i dati è il conto alla rovescia (il benvenuto c'è solo per la lega senza rose)
        for fase in [FaseGiornata.prima, .inCorso, .finita] {
            let prima = SezioneOggi.ordine(fase: fase, conGiornata: true).first(where: { $0 != .benvenuto })
            #expect(prima == .conto, "\(fase)")
        }
    }

    // MARK: numeri

    /// La web faceva salire i punti attesi da 0 (`animaNumero`) e una foto o una scheda in secondo piano restava a metà
    /// («8,9» in Oggi, «65,5» in Formazione, #415). `NumeroCheSale` dell'iPhone fa lo stesso: parte da 0 a ogni comparsa.
    @Test("In Oggi i numeri si scrivono subito giusti: niente NumeroCheSale, che parte da 0", arguments: [
        "ios/Sources/Presentation/Oggi/OggiView.swift",
        "ios/Sources/Presentation/Oggi/FasiGiornataView.swift",
    ])
    func nienteNumeriCheSalgono(file: String) throws {
        let sorgente = try OggiWeb.sorgenteIPhone(file)
        #expect(!sorgente.contains("NumeroCheSale"))
    }

    // MARK: parole

    @Test("Titoli e frasi di Oggi con le parole della web (testi.js)", arguments: [
        ("oggi.tua_formazione", TestiOggi.titoloFormazione(tuaScelta: false)),
        ("oggi.tua_formazione_scelta", TestiOggi.titoloFormazione(tuaScelta: true)),
        ("oggi.punti_attesi", TestiOggi.puntiAttesi),
        ("oggi.apri_formazione", TestiOggi.apriFormazione),
        ("oggi.mancano_probabili_formazioni", TestiOggi.mancanoProbabili),
        ("oggi.tuoi_migliori_della", TestiOggi.migliori),
        ("oggi.da_controllare", TestiOggi.daControllare),
        ("oggi.giocatori_formazione_con", TestiOggi.daControllareSotto),
        ("oggi.diffidati", TestiOggi.diffidati),
        ("oggi.partite_del_turno", TestiOggi.partiteDelTurno),
    ])
    func paroleComeLaWeb(chiave: String, iPhone: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(iPhone == web)
    }

    @Test("«Indisponibili in rosa (3)» come la web")
    func indisponibili() throws {
        let web = try TestiWeb().italiano("oggi.indisponibili").replacingOccurrences(of: "{n}", with: "3")
        #expect(TestiOggi.indisponibili(3) == web)
    }

    /// La web: «<b>Novità della versione {versione}</b>» (dal 2/11/2026 senza stelline né «tocca per vedere», STILE-SENZA-AI.md).
    @Test("Il banner delle novità dice «Novità della versione 1.427», come la web")
    func bannerNovita() throws {
        let web = try TestiWeb().italiano("oggi.novita_banner")
            .replacingOccurrences(of: #"</?b>"#, with: "", options: .regularExpression)
            .replacingOccurrences(of: "{versione}", with: "1.427")
        #expect(TestiOggi.novita("1.427") == web)
        #expect(!TestiOggi.novita("1.427").contains("tocca"))
    }

    @Test("«Mancano le probabili» solo prima della scadenza e solo se mancano davvero, come la web", arguments: [
        CasoProbabili(fase: .prima, conProbabili: false, atteso: true),
        CasoProbabili(fase: .prima, conProbabili: true, atteso: false),
        CasoProbabili(fase: .prima, conProbabili: nil, atteso: false),
        CasoProbabili(fase: .inCorso, conProbabili: false, atteso: false),
        CasoProbabili(fase: .finita, conProbabili: false, atteso: false),
    ])
    func avvisoProbabili(caso: CasoProbabili) {
        #expect(SezioneOggi.avvisoProbabili(fase: caso.fase, conProbabili: caso.conProbabili) == caso.atteso)
    }

    /// Un caso dell'avviso «Mancano le probabili»: la fase, `con_probabili` del server (nil = server vecchio) e se si vede.
    struct CasoProbabili: Sendable, CustomTestStringConvertible {
        let fase: FaseGiornata
        let conProbabili: Bool?
        let atteso: Bool
        var testDescription: String { "\(fase.rawValue), con_probabili \(conProbabili.map { $0 ? "sì" : "no" } ?? "assente")" }
    }
}

/// Il codice di Oggi della web (`fanta/web/app.js`), letto dal repository come `TestiWeb` e `VociLegaWeb`.
private struct OggiWeb {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    let mostraOggi: String
    let cardInCorso: String

    init(file: String = #filePath) throws {
        let app = try Self.leggi("fanta/web/app.js", file: file)
        mostraOggi = try Self.funzione("mostraOggi(o, opz = {})", in: app)
        cardInCorso = try Self.funzione("cardInCorso(c, f)", in: app)
    }

    /// Dove la web scrive una sezione: il segno che la riconosce nel codice di `mostraOggi`. Nil per le sezioni solo dell'iPhone
    /// (il benvenuto della web è un'altra funzione, `mostraOggiSenzaRose`; la frase senza giornata e il suggerimento non ci sono).
    /// Le tre schede della giornata in corso dell'iPhone sono, sulla web, la sola `cardInCorso`.
    static func segno(_ sezione: SezioneOggi) -> String? {
        switch sezione {
        case .benvenuto, .senzaGiornata, .suggerimento: return nil
        case .conto: return "class=\"conto-oggi"
        case .riepilogo: return "cardRiepilogo("
        case .inCorso, .chiGioca, .cambiPanchina: return "cardInCorso("
        case .formazione: return "class=\"formazione-oggi\""
        case .rinvio: return "cardRinvio("
        case .daFare: return "cardDaFare("
        case .novita: return "banner-novita"
        case .migliori: return "\"oggi.tuoi_migliori_della\""
        case .daControllare: return "\"oggi.da_controllare\""
        case .indisponibili: return "\"oggi.indisponibili\""
        case .diffidati: return "\"oggi.diffidati\""
        case .partite: return "\"oggi.partite_del_turno\""
        }
    }

    /// La posizione (in caratteri) del primo segno nel codice di `mostraOggi`.
    func posizione(_ segno: String) throws -> Int {
        guard let r = mostraOggi.range(of: segno) else {
            throw Errore(description: "in mostraOggi di fanta/web/app.js non trovo «\(segno)»: aggiorna OggiWeb.segno")
        }
        return mostraOggi.distance(from: mostraOggi.startIndex, to: r.lowerBound)
    }

    /// Un file dell'app, per i controlli sul codice di Oggi (percorso dalla radice del repository).
    static func sorgenteIPhone(_ percorso: String, file: String = #filePath) throws -> String {
        try leggi(percorso, file: file)
    }

    private static func leggi(_ percorso: String, file: String) throws -> String {
        var radice = URL(fileURLWithPath: file)
        for _ in 0..<4 { radice.deleteLastPathComponent() }          // OggiComeLaWebTests.swift, SchieraxiTests, Tests, ios
        guard let testo = try? String(contentsOf: radice.appendingPathComponent(percorso), encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere \(percorso) dal repository")
        }
        return testo
    }

    /// Il corpo di una funzione di primo livello di app.js: da «function nome(…) {» alla riga «}» che la chiude.
    private static func funzione(_ firma: String, in app: String) throws -> String {
        guard let inizio = app.range(of: "\nfunction \(firma) {"),
              let fine = app.range(of: "\n}\n", range: inizio.upperBound..<app.endIndex) else {
            throw Errore(description: "in fanta/web/app.js non trovo «function \(firma) { … }»")
        }
        return String(app[inizio.upperBound..<fine.lowerBound])
    }
}
