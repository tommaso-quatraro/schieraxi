import Foundation
import Testing
@testable import Schieraxi

/// Diario, «Ho schierato la consigliata» e «Ho schierato un'altra formazione»: cosa si manda al server, dove compare l'esito
/// (nella sezione della sua giornata, stagione compresa), cosa legge VoiceOver, dove va l'errore del foglio.
@MainActor
struct DiarioEsitoTests {
    private func voce(_ json: String) throws -> VoceDiario {
        try Decodifica.decodifica(Data(json.utf8))
    }

    /// Il corpo di `POST /api/diario/schierata` come l'ha ricevuto il server finto.
    private struct CorpoInviato: Decodable {
        let giornata: Int?
        let tipo: String?
        let titolari: [Int]?
    }

    /// Un server che accetta ogni «Ho schierato…» e rimanda un diario vuoto.
    private func serverCheAccetta() -> ServerDiProva {
        ServerDiProva { metodo, _, _ in
            metodo == "POST" ? Data("{}".utf8) : Data(#"{"giornate": [], "sintesi": {"giornate": 0}}"#.utf8)
        }
    }

    // MARK: testi e posto dell'esito

    @Test("«Ho schierato la consigliata»: il testo della web, nella sezione della sua giornata")
    func laConsigliataUsaIlTestoDellaWeb() async throws {
        let v = try voce(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27"}"#)
        let vm = DiarioViewModel(server: serverCheAccetta())
        await vm.haSchieratoLaConsigliata(v)
        #expect(vm.messaggioRiuscito)
        #expect(vm.messaggio(per: v) == "Salvato: ho segnato che hai schierato la consigliata")
        #expect(DiarioViewModel.salvataConsigliata == "Salvato: ho segnato che hai schierato la consigliata")
    }

    @Test("«Ho schierato un'altra formazione»: il testo della web")
    func aManoUsaIlTestoDellaWeb() async throws {
        let v = try voce(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27"}"#)
        let vm = DiarioViewModel(server: serverCheAccetta())
        let errore = await vm.haSchieratoAMano(v, titolari: Array(1...11))
        #expect(errore == nil)
        #expect(vm.messaggio(per: v) == "Salvato: ho segnato i tuoi undici della giornata")
        #expect(DiarioViewModel.salvataAMano == "Salvato: ho segnato i tuoi undici della giornata")
    }

    @Test("Con due stagioni nel Diario l'esito va solo nella sezione della stagione giusta")
    func lEsitoDistingueLaStagione() async throws {
        let questa = try voce(#"{"giornata": 5, "stagione": "2026-27"}"#)
        let primaStagione = try voce(#"{"giornata": 5, "stagione": "2025-26"}"#)
        let vm = DiarioViewModel(server: serverCheAccetta())
        await vm.haSchieratoLaConsigliata(questa)
        #expect(vm.messaggio(per: questa) == DiarioViewModel.salvataConsigliata)
        #expect(vm.messaggio(per: primaStagione) == nil, "stessa giornata, stagione diversa: lì l'esito non c'entra")
    }

    @Test("Durante il secondo salvataggio sotto la nuova giornata non resta l'esito del primo", .timeLimit(.minutes(1)))
    func duranteIlSecondoSalvataggioNonRestaLEsitoDelPrimo() async throws {
        let cancello = Cancello()
        let s = ServerDiProva { metodo, _, corpo in
            guard metodo == "POST" else { return Data(#"{"giornate": []}"#.utf8) }
            // solo la seconda richiesta (giornata 6) resta ferma finché il test non apre
            if let corpo, String(decoding: corpo, as: UTF8.self).contains(#""giornata":6"#) { await cancello.passa() }
            return Data("{}".utf8)
        }
        let ottava = try voce(#"{"giornata": 8, "stagione": "2026-27"}"#)
        let sesta = try voce(#"{"giornata": 6, "stagione": "2026-27"}"#)
        let vm = DiarioViewModel(server: s)
        await vm.haSchieratoLaConsigliata(ottava)
        #expect(vm.messaggio(per: ottava) == DiarioViewModel.salvataConsigliata)

        let seconda = Task { await vm.haSchieratoLaConsigliata(sesta) }
        await cancello.richiestaArrivata()
        #expect(vm.inSalvataggio == sesta.id)
        #expect(vm.messaggio(per: sesta) == nil, "sotto la giornata 6 non deve comparire «Salvato…» della 8")
        #expect(vm.messaggio(per: ottava) == nil)

        await cancello.apri()
        await seconda.value
        #expect(vm.inSalvataggio == nil)
        #expect(vm.messaggio(per: sesta) == DiarioViewModel.salvataConsigliata)
    }

    // MARK: VoiceOver

    @Test("Due salvataggi di fila sulla stessa giornata: VoiceOver legge l'esito tutte e due le volte")
    func dueSalvataggiDueAnnunci() async throws {
        let v = try voce(#"{"giornata": 9, "stagione": "2026-27"}"#)
        let vm = DiarioViewModel(server: serverCheAccetta())
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        _ = await vm.haSchieratoAMano(v, titolari: Array(1...11))
        _ = await vm.haSchieratoAMano(v, titolari: Array(1...11))
        #expect(annunci == [DiarioViewModel.salvataAMano, DiarioViewModel.salvataAMano])
    }

    // MARK: errori

    @Test("Se il salvataggio a mano non riesce l'errore torna al foglio, non alla lista che sta sotto")
    func lErroreAManoVaNelFoglio() async throws {
        let v = try voce(#"{"giornata": 9, "stagione": "2026-27"}"#)
        let rifiuto = "Tra i titolari ci sono giocatori che non sono nella tua rosa"
        let vm = DiarioViewModel(server: ServerDiProva.chePrecipita(.server(rifiuto)))
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        let errore = await vm.haSchieratoAMano(v, titolari: Array(1...11))
        #expect(errore == rifiuto)
        #expect(vm.messaggio(per: v) == nil, "nella lista, coperta dal foglio, non si vedrebbe")
        #expect(annunci == [rifiuto], "VoiceOver lo legge comunque")
        #expect(vm.inSalvataggio == nil)
    }

    @Test("Un errore di «Ho schierato la consigliata» si vede nella sezione della sua giornata")
    func lErroreDellaConsigliataStaConLaSuaGiornata() async throws {
        let v = try voce(#"{"giornata": 99, "stagione": "2026-27"}"#)
        let rifiuto = "Si può dire cosa hai schierato solo per le giornate già finite"
        let vm = DiarioViewModel(server: ServerDiProva.chePrecipita(.server(rifiuto)))
        await vm.haSchieratoLaConsigliata(v)
        #expect(!vm.messaggioRiuscito)
        #expect(vm.messaggio(per: v) == rifiuto)
        #expect(vm.inSalvataggio == nil)
    }

    // MARK: cosa arriva al server (prima in ParitaWebTests, XCTest)

    @Test("«Ho schierato la consigliata» manda la giornata di Serie A senza titolari e poi rilegge il Diario")
    func laConsigliataMandaLaGiornataERicarica() async throws {
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "POST", percorso == "/api/diario/schierata" { return Data(#"{"giornata": 9}"#.utf8) }
            if percorso == "/api/diario" { return Data(#"{"giornate": [{"giornata": 9, "stagione": "2026-27"}], "sintesi": {"giornate": 0}}"#.utf8) }
            throw ErroreApi.server("niente")
        }
        let v = try voce(#"{"giornata": 9, "giornata_lega": 6, "stagione": "2026-27"}"#)
        let vm = DiarioViewModel(server: s)
        await vm.haSchieratoLaConsigliata(v)
        #expect(s.quante("POST /api/diario/schierata") == 1)
        let corpo = try #require(s.corpiInviati(a: "/api/diario/schierata").first)
        let letto = try JSONDecoder().decode(CorpoInviato.self, from: corpo)
        #expect(letto.tipo == "consigliata")
        #expect(letto.giornata == 9, "al server il numero di Serie A, non quello della lega")
        #expect(letto.titolari == nil, "senza titolari per «consigliata»")
        #expect(vm.messaggioRiuscito)
        #expect(vm.inSalvataggio == nil)
        #expect(s.quante("GET /api/diario") >= 1, "dopo il salvataggio il diario si rilegge")
    }

    @Test("A mano si mandano gli 11 titolari con il tipo «manuale»")
    func aManoMandaITitolariScelti() async throws {
        let s = serverCheAccetta()
        let v = try voce(#"{"giornata": 9, "stagione": "2026-27"}"#)
        let vm = DiarioViewModel(server: s)
        let ids = Array(1...11)
        let errore = await vm.haSchieratoAMano(v, titolari: ids)
        #expect(errore == nil)
        let corpo = try #require(s.corpiInviati(a: "/api/diario/schierata").first)
        let letto = try JSONDecoder().decode(CorpoInviato.self, from: corpo)
        #expect(letto.tipo == "manuale")
        #expect(letto.giornata == 9)
        #expect(letto.titolari == ids)
        #expect(vm.messaggioRiuscito)
    }
}
