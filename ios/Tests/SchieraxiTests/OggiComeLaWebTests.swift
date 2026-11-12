import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// Oggi come la web (#416, parte di #167). Con la grafica B (#415) la web parte dalla giornata con il conto alla rovescia, senza il
/// nome SchieraXI e lo slogan, e ha un ordine nuovo: la formazione con «Apri la formazione» subito sotto il conto, poi Partita
/// rinviata, Da fare e novità; poi I tuoi migliori, Da controllare, Indisponibili, Diffidati e Partite del turno.
/// L'ordine dell'iPhone sta in un posto solo (`SezioneOggi.ordine`, che la schermata percorre) e qui si confronta, fase per fase,
/// con quello che `mostraOggi` della web scriveva il 12/11/2026. Dal rifacimento della web (spec `2026-11-12-revisione-generale-design`)
/// il codice della web non si legge più: l'app resta com'è finché il proprietario non decide.
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

    @Test("Giornata in corso: conto, una carta sola con punti, chi va a punteggio e cambi (#436), rinvio, Da fare, novità, partite")
    func ordineInCorso() {
        #expect(SezioneOggi.ordine(fase: .inCorso, conGiornata: true) == [
            .benvenuto, .conto, .inCorso, .rinvio, .daFare, .novita, .partite,
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

    // MARK: testa della schermata

    @Test("In cima a Oggi niente nome SchieraXI né slogan: si parte dalla giornata con il conto alla rovescia")
    func nienteNomeNeSlogan() throws {
        let sorgente = try CodiceOggiIPhone.leggi("Sources/Presentation/Oggi/OggiView.swift")
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
        "Sources/Presentation/Oggi/OggiView.swift",
        "Sources/Presentation/Oggi/FasiGiornataView.swift",
    ])
    func nienteNumeriCheSalgono(file: String) throws {
        let sorgente = try CodiceOggiIPhone.leggi(file)
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

    // MARK: partite del turno

    /// Decisione dell'utente (6/11/2026): Partite del turno si vede sempre, come sulla web (`mostraOggi` la scrive senza
    /// condizioni). «Risultati in diretta» spenta toglie solo i risultati in diretta (punteggio, minuto, eventi), non le partite.
    @Test("Partite del turno c'è sempre: in OggiView la sezione non dipende da «Risultati in diretta»")
    func partiteSempre() throws {
        let sorgente = try CodiceOggiIPhone.leggi("Sources/Presentation/Oggi/OggiView.swift")
        let caso = try #require(sorgente.range(of: "case .partite:"), "OggiView non ha più la sezione delle partite")
        // il corpo del caso: fino alla fine della funzione `sezione` (la graffa a 4 spazi)
        let resto = sorgente[caso.upperBound...]
        let fine = try #require(resto.range(of: "\n    }"), "non trovo la fine di OggiView.sezione")
        let corpo = resto[..<fine.lowerBound]
        #expect(!corpo.contains("Funzione.live"), "Partite del turno nascosta con «Risultati in diretta» spenta: \(corpo)")
        #expect(!corpo.contains("if "), "Partite del turno sotto una condizione: \(corpo)")
    }

    @MainActor
    @Test("«Risultati in diretta» spenta: le partite restano con giorno e ora, senza punteggio né minuto")
    func partiteSenzaDiretta() async throws {
        let corpoLive = #"{"fonte": "espn", "in_corso": 1, "partite": [{"casa": "inter", "trasferta": "roma", "stato": "primo_tempo", "minuto": "5'", "gol_casa": 1, "gol_trasferta": 0}]}"#
        let corpoOggi = #"{"giornata": 9, "partite": [{"casa": "inter", "trasferta": "roma", "data": "2026-10-31 15:00", "giocata": false}]}"#
        let server = ServerDiProva { _, percorso, _ in
            Data((percorso.hasPrefix("/api/live") ? corpoLive : corpoOggi).utf8)
        }
        let vm = OggiViewModel(server: server, conPromemoria: false)
        await vm.carica()
        await vm.live.ricarica()          // risultati rimasti in memoria da quando la funzione era accesa
        let partita = try #require(vm.oggi?.partite?.first)
        #expect(vm.dalVivo(partita)?.minuto == "5'", "con la funzione accesa il minuto c'è")

        vm.liveAcceso = false
        #expect(vm.risultatiLive == nil, "spenta: nessun risultato in diretta")
        #expect(vm.dalVivo(partita) == nil, "spenta: niente punteggio né minuto sulla riga")
        let giorni = vm.partitePerGiorno
        #expect(giorni.flatMap(\.partite).count == 1, "la partita resta")
        #expect(giorni.first?.titolo != "Data da definire", "con il suo giorno")
    }

    // MARK: parole

    /// Titoli e frasi di Oggi vengono dal catalogo comune con la web (`Catalogo.Oggi`, `Catalogo.Df`, #494): la prova è
    /// `OggiDalCatalogoTests`. Qui resta quello che il catalogo non dice: il banner senza «tocca per vedere» (STILE-SENZA-AI.md).
    @Test("Il banner delle novità dice «Novità della versione 1.427», senza «tocca per vedere»")
    func bannerNovita() {
        #expect(TestiOggi.novita("1.427") == "Novità della versione 1.427")
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

/// I file dell'app che alcune prove di Oggi leggono come testo (percorso dalla cartella `ios/`).
private enum CodiceOggiIPhone {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    static func leggi(_ percorso: String, file: String = #filePath) throws -> String {
        var ios = URL(fileURLWithPath: file)
        for _ in 0..<3 { ios.deleteLastPathComponent() }          // OggiComeLaWebTests.swift, SchieraxiTests, Tests
        guard let testo = try? String(contentsOf: ios.appendingPathComponent(percorso), encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere ios/\(percorso) dal repository")
        }
        return testo
    }
}
