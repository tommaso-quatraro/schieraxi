import Foundation
import SwiftUI
import Testing
import UIKit
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

    /// L'ordine da solo non basta: una sezione tolta su un lato solo lascerebbe giusto l'ordine delle altre. Qui l'insieme delle
    /// sezioni di ogni fase si confronta con quello che la web mostra, letto dalle condizioni di `mostraOggi`.
    @Test("Ogni segno delle sezioni della web c'è davvero in mostraOggi")
    func segniNellaWeb() throws {
        let web = try OggiWeb()
        let segni = SezioneOggi.allCases.compactMap(OggiWeb.segno)
        #expect(!segni.isEmpty)
        let mancanti = segni.filter { web.mostraOggi.range(of: $0) == nil }
        #expect(mancanti.isEmpty, "in mostraOggi di fanta/web/app.js mancano \(mancanti): aggiorna OggiWeb.segno")
    }

    @Test("Ogni fase ha le stesse sezioni della web, né una in più né una in meno", arguments: [FaseGiornata.prima, .inCorso, .finita])
    func stesseSezioniDellaWeb(fase: FaseGiornata) throws {
        let web = try OggiWeb()
        let attese = try web.sezioni(fase: fase)
        let iPhone = Set(SezioneOggi.ordine(fase: fase, conGiornata: true).compactMap(OggiWeb.comeSullaWeb))
        #expect(iPhone == attese, "in più sull'iPhone: \(iPhone.subtracting(attese)); mancano sull'iPhone: \(attese.subtracting(iPhone))")
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

    // MARK: carta della formazione

    /// La web scrive «Mancano le probabili…» nella formazione anche quando i punti attesi non ci sono (`num(null)` = «–»):
    /// sull'iPhone l'avviso stava dentro il controllo «formazione disponibile» e con `punteggio_atteso: null` spariva.
    /// Si disegna la carta (`ImageRenderer`, larga come un iPhone stretto) con e senza probabili: con l'avviso è più alta.
    @MainActor
    @Test("«Mancano le probabili» c'è anche con la formazione non disponibile (punti attesi assenti), come la web")
    func avvisoProbabiliSenzaFormazione() throws {
        func altezza(conProbabili: Bool) throws -> CGFloat {
            let json = #"{"giornata": 11, "fase": "prima", "con_probabili": \#(conProbabili), "formazione": {"modulo": "4-3-3", "punteggio_atteso": null}}"#
            let oggi: Oggi = try Decodifica.decodifica(Data(json.utf8))
            #expect(oggi.formazione?.disponibile == false, "il caso da provare è la formazione senza punti attesi")
            let disegno = ImageRenderer(content: CartaFormazioneOggi(oggi: oggi).frame(width: 320))
            disegno.scale = 1
            return disegno.uiImage?.size.height ?? 0
        }
        let conLeProbabili = try altezza(conProbabili: true)
        let senzaProbabili = try altezza(conProbabili: false)
        #expect(conLeProbabili > 0)
        #expect(senzaProbabili > conLeProbabili, "con con_probabili false l'avviso deve comparire anche senza punti attesi")
    }

    @Test("VoiceOver sulle cifre dice modulo e punti attesi, senza ripetere il titolo appena letto")
    func voceCifreSenzaTitolo() {
        let voce = TestiOggi.voceCifre(modulo: "4-3-3", punti: 65.5)
        #expect(voce == "Modulo 4-3-3, 65,5 punti attesi")
        for titolo in [TestiOggi.titoloFormazione(tuaScelta: false), TestiOggi.titoloFormazione(tuaScelta: true), "Prossima giornata"] {
            #expect(!voce.contains(titolo), "«\(titolo)» è già il titolo della carta")
        }
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

    /// La sezione come la conta la web: nil per quelle solo dell'iPhone; le tre della giornata in corso sono una sola.
    static func comeSullaWeb(_ sezione: SezioneOggi) -> SezioneOggi? {
        guard let s = segno(sezione) else { return nil }
        return s == segno(.inCorso) ? .inCorso : sezione
    }

    /// Le sezioni che la web mostra in una fase (con una giornata in calendario e i dati della giornata in corso).
    /// Le quattro liste di consigli e avvisi le svuota il codice di `mostraOggi` (`const migliori = inCorso || finita ? [] : …`):
    /// le loro fasi si leggono da lì. Le altre condizioni stanno nel markup: riepilogo solo a giornata finita (`finita ? cardRiepilogo`),
    /// giornata in corso solo nella sua fase (`inCorso ? … cardInCorso`), formazione tranne a giornata in corso con i suoi dati
    /// (`inCorso && (o.in_corso || o.senza_formazione) ? ""`); conto, rinvio, Da fare, novità e partite sempre.
    func sezioni(fase: FaseGiornata) throws -> Set<SezioneOggi> {
        var sezioni: Set<SezioneOggi> = [.conto, .rinvio, .daFare, .novita, .partite]
        switch fase {
        case .prima: sezioni.insert(.formazione)
        case .inCorso: sezioni.insert(.inCorso)
        case .finita: sezioni.formUnion([SezioneOggi.riepilogo, .formazione])
        }
        let liste: [(String, SezioneOggi)] = [("inFormazione", .daControllare), ("migliori", .migliori),
                                              ("indisponibili", .indisponibili), ("altri", .diffidati)]
        for (variabile, sezione) in liste {
            let vuote = try fasiVuote(variabile)
            if !vuote.contains(fase) { sezioni.insert(sezione) }
        }
        return sezioni
    }

    /// Le fasi in cui `mostraOggi` svuota una lista: `const migliori = inCorso || finita ? [] : o.migliori;` → in corso e finita.
    func fasiVuote(_ variabile: String) throws -> Set<FaseGiornata> {
        guard let inizio = mostraOggi.range(of: "const \(variabile) = ") else {
            throw Errore(description: "in mostraOggi non trovo «const \(variabile) = …»: aggiorna OggiWeb.sezioni")
        }
        let riga = String(mostraOggi[inizio.upperBound...].prefix { $0 != "\n" })
        guard let fine = riga.range(of: " ? [] :") else {
            throw Errore(description: "la riga di «\(variabile)» non ha più la forma «condizione ? [] : …»: \(riga)")
        }
        var fasi: Set<FaseGiornata> = []
        for parola in riga[..<fine.lowerBound].components(separatedBy: "||") {
            switch parola.trimmingCharacters(in: .whitespaces) {
            case "inCorso": fasi.insert(.inCorso)
            case "finita": fasi.insert(.finita)
            default: throw Errore(description: "condizione di «\(variabile)» che il test non sa leggere: \(riga)")
            }
        }
        return fasi
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
