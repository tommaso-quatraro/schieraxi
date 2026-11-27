import Foundation
import Testing
@testable import Schieraxi

/// La Formazione aperta resta vera, come `mostraFormazione` della web (#978): si rilegge da sola quando serve, una lettura per
/// evento e mai a ciclo. Oltre alla rilettura 5 secondi dopo la scadenza (`FormazioneView`) e a quella al ritorno dopo la scadenza
/// (`ScadenzaAlRitornoTests`): tornando dal secondo piano con i dati di più di 5 minuti fa (`DATI_VECCHI_MS` della web), e dopo un
/// rifiuto `giocatore_bloccato` di un salvataggio o di «Torna alla consigliata» (come dopo `formazione_chiusa`). Prima l'iPhone
/// rileggeva solo alla scadenza con l'app aperta. Ore inventate, a metà giornata; dati inventati (fixture).
/// La frase del server per chi gioca una partita già cominciata (`err.giocatore_bloccato`, nome inventato). Fuori dalla suite:
/// la legge anche il server di prova, che non è sull'attore principale.
private let fraseBloccato = "Mario Prova gioca in una partita già cominciata: non si può più spostare."

@MainActor
@Suite("Formazione: si rilegge da sola quando serve, come la web")
struct FormazioneSiRileggeTests {
    private static let adesso = Date(timeIntervalSince1970: 1_795_000_000)

    /// `secondi` dopo adesso (prima, se negativo).
    private func t(_ secondi: TimeInterval) -> Date { Self.adesso.addingTimeInterval(secondi) }

    // MARK: ritorno in primo piano

    @Test("Di ritorno dal secondo piano con i dati di più di 5 minuti fa: si rilegge, una volta")
    func datiVecchiAlRitorno() {
        // letti 6 minuti fa, fuori da 2
        #expect(DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: t(-120), inBackgroundDal: t(-119), lettaIl: t(-360),
                                            adesso: Self.adesso))
        // letti appena prima di uscire, fuori da 5 minuti e mezzo: meno dei 10 dopo cui ricarica già tutto la porta
        #expect(DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: t(-330), inBackgroundDal: t(-330), lettaIl: t(-331),
                                            adesso: Self.adesso))
        // la scadenza è ancora lontana: decide l'età dei dati
        #expect(DatiVecchi.rileggiAlRitorno(scadenza: t(3600), fuoriDal: t(-120), inBackgroundDal: t(-119), lettaIl: t(-360),
                                            adesso: Self.adesso))
    }

    @Test("Altrimenti no: dati di 5 minuti o meno, solo il Centro di controllo, la porta che ricarica già tutto, nessuna lettura")
    func altriCasi() {
        #expect(!DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: t(-60), inBackgroundDal: t(-59), lettaIl: t(-299),
                                             adesso: Self.adesso))
        #expect(!DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: t(-60), inBackgroundDal: t(-59), lettaIl: t(-300),
                                             adesso: Self.adesso), "più di 5 minuti, come la web")
        // solo inattiva (Centro di controllo, Centro Notifiche), senza secondo piano: la web rilegge quando la pagina torna visibile
        #expect(!DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: t(-30), inBackgroundDal: nil, lettaIl: t(-900),
                                             adesso: Self.adesso))
        // fuori da 10 minuti o più: la porta manda già «Aggiorna» a tutte le schermate, e basta quella lettura
        let soglia = DatiVecchi.sogliaRitorno
        #expect(!DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: t(-soglia), inBackgroundDal: t(-soglia), lettaIl: t(-3600),
                                             adesso: Self.adesso))
        // mai letta (la schermata la legge quando compare), o l'app non era uscita
        #expect(!DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: t(-60), inBackgroundDal: t(-59), lettaIl: nil,
                                             adesso: Self.adesso))
        #expect(!DatiVecchi.rileggiAlRitorno(scadenza: nil, fuoriDal: nil, inBackgroundDal: nil, lettaIl: t(-900),
                                             adesso: Self.adesso))
    }

    @Test("La scadenza passata mentre l'app era fuori fa rileggere anche con i dati appena letti (la regola della #972)")
    func scadenzaConDatiFreschi() {
        #expect(DatiVecchi.rileggiAlRitorno(scadenza: t(-30), fuoriDal: t(-60), inBackgroundDal: nil, lettaIl: t(-61),
                                            adesso: Self.adesso))
        #expect(DatiVecchi.rileggiAlRitorno(scadenza: t(-30), fuoriDal: t(-60), inBackgroundDal: t(-59), lettaIl: t(-61),
                                            adesso: Self.adesso))
    }

    @Test("Ogni lettura della Formazione segna quando è partita: è l'età dei dati che conta al ritorno")
    func segnaLaLettura() async throws {
        let vm = FormazioneViewModel(server: try SalvataggioAutomaticoTests.server())
        #expect(vm.lettaIl == nil && vm.ultimaLettura == nil)
        let prima = Date()
        await vm.carica()
        let letta = try #require(vm.lettaIl)
        #expect(letta >= prima && letta <= Date())
        #expect(vm.ultimaLettura == letta)
    }

    @Test("Un salvataggio riuscito rinfresca l'età dei dati, come `sc.letta` della web; la lettura per la scadenza resta quella di prima")
    func salvataggioRinfresca() async throws {
        let vm = FormazioneViewModel(server: try SalvataggioAutomaticoTests.server())
        await vm.carica()
        let lettura = try #require(vm.ultimaLettura)
        let f = try #require(vm.formazione)
        let prima = Date()
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let partito = await vm.sostituisciTitolare(esce, con: entra)
        #expect(partito)
        let dopoIlSalvataggio = try #require(vm.lettaIl)
        #expect(dopoIlSalvataggio >= prima, "il server ha appena risposto su questa formazione: i dati sono freschi")
        #expect(vm.ultimaLettura == lettura, "un salvataggio non è una rilettura")
        // anche «Torna alla consigliata», quando il server toglie la scelta
        let primaDiTornare = Date()
        await vm.tornaAllaConsigliata()
        let dopoIlRitorno = try #require(vm.lettaIl)
        #expect(dopoIlRitorno >= primaDiTornare)
        #expect(vm.salvata == nil && vm.ultimaLettura == lettura)
    }

    // MARK: la rilettura della scadenza dopo l'attesa

    @Test("Finita l'attesa, il lavoro della scadenza rilegge solo se dalla scadenza non è partita un'altra lettura")
    func scadenzaDopoLAttesa() {
        let scadenza = t(-5)
        #expect(DatiVecchi.rileggiDopoLAttesa(scadenza: scadenza, ultimaLettura: nil))
        #expect(DatiVecchi.rileggiDopoLAttesa(scadenza: scadenza, ultimaLettura: t(-600)), "letta prima della scadenza: si rilegge")
        #expect(DatiVecchi.rileggiDopoLAttesa(scadenza: scadenza, ultimaLettura: scadenza))
        // tornati nell'app 2 secondi dopo la scadenza con i dati vecchi: è già partita quella lettura, e basta
        #expect(!DatiVecchi.rileggiDopoLAttesa(scadenza: scadenza, ultimaLettura: t(-3)))
    }

    // MARK: rifiuto per una partita cominciata

    @Test("Un salvataggio rifiutato perché una partita è cominciata (`giocatore_bloccato`): la frase del server e si rilegge")
    func bloccatoAlSalvataggio() async throws {
        let srv = Self.server(rifiutaIl: "POST")
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        let f = try #require(vm.formazione)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let partito = await vm.sostituisciTitolare(esce, con: entra)
        #expect(partito)
        #expect(vm.messaggio == fraseBloccato)
        #expect(srv.quante("GET /api/formazione") == 2, "la schermata non sapeva della partita cominciata: si rilegge")
        #expect(vm.manuale == nil, "il cambio rifiutato non resta in campo")
        #expect(!vm.occupato && !vm.leggendo)
    }

    @Test("«Torna alla consigliata» rifiutato perché una partita è cominciata: la frase del server, la tua resta e si rilegge")
    func bloccatoTornandoAllaConsigliata() async throws {
        let srv = Self.server(rifiutaIl: "DELETE", salvata: try FormazioneChiusaTests.altroModulo())
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        #expect(vm.salvata != nil)
        await vm.tornaAllaConsigliata()
        #expect(srv.quante("DELETE /api/scelta") == 1)
        #expect(vm.messaggio == fraseBloccato)
        #expect(srv.quante("GET /api/formazione") == 2, "la schermata non sapeva della partita cominciata: si rilegge")
        #expect(vm.salvata != nil, "la scelta non è stata tolta")
        #expect(!vm.occupato && !vm.leggendo)
    }

    // MARK: aiuti

    /// La formazione della fixture e la scelta `salvata` (nil = nessuna); le scritture con `rifiutaIl` («POST»: i salvataggi,
    /// «DELETE»: «Torna alla consigliata») rispondono 400 `giocatore_bloccato`, come il server vero quando una partita è cominciata.
    static func server(rifiutaIl metodoRifiutato: String, salvata: [Int]? = nil) -> ServerDiProva {
        let scelta = salvata.map { SalvataggioAutomaticoTests.json($0) } ?? "null"
        return ServerDiProva { metodo, percorso, corpo in
            let scrive = metodo == "DELETE" || SalvataggioAutomaticoTests.salva(corpo)
            if scrive, metodo == metodoRifiutato {
                throw ErroreApi.codificato(codice: FormazioneViewModel.codiceBloccato, messaggio: fraseBloccato)
            }
            if percorso.hasPrefix("/api/formazione/valuta") {
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data(scelta.utf8) }
            return try Fixture.dati("formazione")
        }
    }
}
