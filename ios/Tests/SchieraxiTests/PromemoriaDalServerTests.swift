import Foundation
import Testing
@testable import Schieraxi

/// I promemoria del telefono (un'ora e un quarto d'ora prima della scadenza) li decide il server, con la regola dei suoi promemoria
/// (`serve_promemoria` di `/api/oggi`, `notifiche.serve_promemoria`): tacciono solo con «L'ho messa» e nessun titolare diventato
/// indisponibile. Così la spunta messa o tolta dalla web, o caduta perché dalla web sono cambiati gli 11, vale anche sull'iPhone alla
/// prima lettura in background, senza riaprire l'app (#710). La spunta toccata sul telefono vale subito, ma solo finché non arriva
/// una lettura di Oggi partita dopo il tocco. Senza il campo (server di prima) o con la lettura non riuscita il promemoria suona.
@Suite("Promemoria del telefono decisi dal server")
struct PromemoriaDalServerTests {
    private func memoria() throws -> UserDefaults {
        try #require(UserDefaults(suiteName: "prova-promemoria-\(UUID().uuidString)"))
    }

    /// La giornata 9 di Oggi, con il campo `serve_promemoria` (nil = il server non lo manda).
    private func oggi(serve: Bool?) throws -> Oggi {
        let campo = serve.map { ", \"serve_promemoria\": \($0)" } ?? ""
        return try Decodifica.decodifica(Data("{\"giornata\": 9\(campo)}".utf8))
    }

    private let tocco = Date(timeIntervalSince1970: 1_793_500_000)

    @Test("Il campo `serve_promemoria` di Oggi si legge; se manca o è strano non si sa", arguments: zip(
        [#"{"giornata": 9, "serve_promemoria": true}"#, #"{"giornata": 9, "serve_promemoria": false}"#,
         #"{"giornata": 9}"#, #"{"giornata": 9, "serve_promemoria": "forse"}"#],
        [Optional(true), Optional(false), nil, nil]))
    func campo(json: String, atteso: Bool?) throws {
        let oggi: Oggi = try Decodifica.decodifica(Data(json.utf8))
        #expect(oggi.servePromemoria?.valore == atteso)
    }

    @Test("Decide il server: tace solo se dice che il promemoria non serve; senza il campo suona")
    func decideIlServer() {
        #expect(Notifiche.tacePromemoria(serve: false, toccata: nil) == true)
        #expect(Notifiche.tacePromemoria(serve: true, toccata: nil) == false)
        #expect(Notifiche.tacePromemoria(serve: nil, toccata: nil) == false, "server di prima o lettura non riuscita: suona")
    }

    @Test("Una spunta appena toccata sul telefono vale subito, in un verso e nell'altro")
    func toccataValeSubito() {
        #expect(Notifiche.tacePromemoria(serve: true, toccata: true) == true)
        #expect(Notifiche.tacePromemoria(serve: false, toccata: false) == false)
        #expect(Notifiche.tacePromemoria(serve: nil, toccata: true) == true)
    }

    @Test("Spunta sull'iPhone, poi dalla web cambia un titolare: alla lettura in background il promemoria suona")
    func spuntaCadutaDallaWeb() throws {
        let m = try memoria()
        let serve = try oggi(serve: true)
        ArchivioMessa.ricorda(giornata: 9, messa: true, m, il: tocco)
        let subito = Aggiornamento.promemoriaTace(serve, lettura: .salvata, memoria: m)
        #expect(subito == true, "subito dopo il tocco tace")
        let dopo = Aggiornamento.promemoriaTace(serve, lettura: .fresca(chiestaIl: tocco.addingTimeInterval(3600)), memoria: m)
        #expect(dopo == false, "la lettura dopo il tocco dice che serve: suona")
        #expect(ArchivioMessa.toccata(giornata: 9, m) == nil, "il tocco è dimenticato: da qui vale il server")
    }

    @Test("Spunta messa dalla web: alla lettura in background l'iPhone tace")
    func spuntaDallaWeb() throws {
        let m = try memoria()
        let nonServe = try oggi(serve: false)
        let serve = try oggi(serve: true)
        #expect(Aggiornamento.promemoriaTace(nonServe, lettura: .fresca(chiestaIl: tocco), memoria: m) == true)
        #expect(Aggiornamento.promemoriaTace(serve, lettura: .fresca(chiestaIl: tocco), memoria: m) == false)
    }

    @Test("Una lettura partita prima del tocco non lo cancella: la spunta appena tolta fa suonare")
    func letturaPrimaDelTocco() throws {
        let m = try memoria()
        let nonServe = try oggi(serve: false)
        ArchivioMessa.ricorda(giornata: 9, messa: false, m, il: tocco)
        let tace = Aggiornamento.promemoriaTace(nonServe, lettura: .fresca(chiestaIl: tocco.addingTimeInterval(-5)), memoria: m)
        #expect(tace == false)
        #expect(ArchivioMessa.toccata(giornata: 9, m) == false)
    }

    @Test("Senza il campo (server di prima) il promemoria suona, anche con una spunta toccata prima della lettura")
    func serverDiPrima() throws {
        let m = try memoria()
        let senza = try oggi(serve: nil)
        ArchivioMessa.ricorda(giornata: 9, messa: true, m, il: tocco)
        #expect(Aggiornamento.promemoriaTace(senza, lettura: .salvata, memoria: m) == true, "prima della lettura vale il tocco")
        let dopo = Aggiornamento.promemoriaTace(senza, lettura: .fresca(chiestaIl: tocco.addingTimeInterval(60)), memoria: m)
        #expect(dopo == false)
    }

    @Test("Lettura non riuscita: il valore salvato del server non basta e il promemoria suona; una spunta appena toccata vale ancora")
    func letturaNonRiuscita() throws {
        let m = try memoria()
        let salvato = try oggi(serve: false)
        #expect(Aggiornamento.promemoriaTace(salvato, lettura: .salvata, memoria: m) == true, "senza rete vale l'ultima parola del server")
        #expect(Aggiornamento.promemoriaTace(salvato, lettura: .nonRiuscita, memoria: m) == false, "lettura non riuscita: suona")
        ArchivioMessa.ricorda(giornata: 9, messa: true, m, il: tocco)
        #expect(Aggiornamento.promemoriaTace(salvato, lettura: .nonRiuscita, memoria: m) == true, "la spunta appena toccata vale ancora")
    }
}
