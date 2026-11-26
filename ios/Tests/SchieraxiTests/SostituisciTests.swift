import Foundation
import Testing
@testable import Schieraxi

/// «Sostituisci» dalla scheda di un titolare, come `apriSostituzione` della web (collaudo del 26/11): l'elenco chiede a
/// `POST /api/formazione/sostituisci` chi può prendere il suo posto, con gli 11 in campo, e mostra i numeri del server nel suo
/// ordine: i punti attesi della FORMAZIONE in più o in meno con quel cambio, non la differenza fra i due giocatori (che diceva
/// «+2,7» per un cambio che alla formazione valeva −0,1). `giocatore_bloccato` è un'informazione al posto dell'elenco,
/// `formazione_chiusa` chiude l'elenco e rilegge; un elenco chiuso prima della risposta non si riapre. Gli errori e le attese
/// sono quelli di «Metti in campo» (`MettiInCampoTests`).
@MainActor
@Suite("«Sostituisci» con i numeri del server, come la web")
struct SostituisciTests {

    // MARK: la domanda e l'elenco

    @Test("La domanda manda chi esce, gli 11 in campo (dopo un cambio, i nuovi) e la giornata; l'elenco si apre subito con «Carico…»")
    func domandaConGli11InCampo() async throws {
        let cancello = Cancello()
        let (vm, srv) = try await caricata(rotta: { _ in
            await cancello.passa()
            return Data(Prova.risposta.utf8)
        })
        await vm.scegliModulo("5-3-2")
        #expect(vm.manuale == Prova.titolari532, "in campo c'è il 5-3-2, già salvato")
        let compito = Task { await vm.sostituisci(Prova.incerto) }
        let aperto = await diventa { vm.elencoSostituti?.stato.aspetta == true }
        await cancello.apri()
        await compito.value
        #expect(aperto, "l'elenco si apre prima della risposta, con «Carico…»")
        #expect(vm.elencoSostituti?.uscente.id == Prova.incerto)
        #expect(srv.quante("POST /api/formazione/sostituisci") == 1)
        let corpo = try #require(srv.corpiInviati(a: "/api/formazione/sostituisci").first)
        let letto = try JSONSerialization.jsonObject(with: corpo)
        let domanda = try #require(letto as? [String: Any])
        #expect(domanda["esce"] as? Int == Prova.incerto)
        #expect(domanda["titolari"] as? [Int] == Prova.titolari532, "gli 11 in campo, non quelli della consigliata")
        #expect(domanda["giornata"] as? Int == 9)
    }

    @Test("Le righe nell'ordine del server, senza titolari né chi non è nella Formazione, con la differenza della formazione")
    func righeNellOrdineDelServer() async throws {
        let (vm, _) = try await caricata()
        await vm.sostituisci(Prova.incerto)
        let righe = try #require(vm.elencoSostituti?.stato.righe)
        #expect(righe.map(\.entra.id) == [7457, 6994, 6980], "nell'ordine del server, non in quello dei punti attesi da soli")
        #expect(righe.map(\.differenza) == [0.3, -0.1, nil], "il numero del server; senza, niente numero")
        let zanaldi = try #require(righe.first { $0.entra.id == 6994 })
        let fraIDue = (zanaldi.entra.puntiAttesi ?? 0) - (vm.formazione?.schede?[String(Prova.incerto)]?.puntiAttesi ?? 0)
        #expect(fraIDue > 1.9, "fra i due giocatori +1,9: l'app scrive −0,1, il numero della formazione")
        #expect(righe.first?.entra.nome == "Zanetti Valelli", "la scheda di chi entra viene dalla Formazione")
        #expect(vm.messaggio == nil)
    }

    // MARK: il posto di chi entra (collaudo del 26/11)

    @Test("Ogni riga dice dov'è chi entra nella formazione in campo, come la web: «Panchina 5», «Panchina 3», «Non schierato»")
    func postoDiChiEntra() async throws {
        let (vm, _) = try await caricata(rotta: { _ in Data(Prova.rispostaConFuori.utf8) })
        await vm.sostituisci(Prova.incerto)
        let righe = try #require(vm.elencoSostituti?.stato.righe)
        #expect(righe.map(\.entra.id) == [7457, 6994, 5678])
        #expect(righe.map(\.posto) == [Catalogo.Mercato.panchinaN(n: "5"), Catalogo.Mercato.panchinaN(n: "3"), Catalogo.Mercato.postoFuori])
        #expect(Catalogo.Mercato.panchinaN(n: "3") == "Panchina 3")
        #expect(Catalogo.Mercato.postoFuori == "Non schierato")
    }

    @Test("Con un altro modulo in campo il posto è quello della sua panchina")
    func postoConUnAltroModulo() async throws {
        let (vm, _) = try await caricata(rotta: { _ in Data(Prova.rispostaConFuori.utf8) })
        await vm.scegliModulo("5-3-2")
        try #require(vm.manuale == Prova.titolari532)
        await vm.sostituisci(Prova.incerto)
        let righe = try #require(vm.elencoSostituti?.stato.righe)
        #expect(righe.map(\.entra.id) == [5678], "7457 e 6994 nel 5-3-2 sono titolari: non sono righe")
        #expect(righe.first?.posto == Catalogo.Mercato.panchinaN(n: "5"), "nel 5-3-2 Roselli è il quinto della panchina")
    }

    @Test("Il posto a parole: titolare, panchina con il numero, non schierato; chi non è nella formazione niente")
    func postoAParole() {
        #expect(PostoInFormazione.testo(1, titolari: [1, 2], panchina: [3, 4], inRosa: true) == Catalogo.Mercato.postoTitolare)
        #expect(PostoInFormazione.testo(4, titolari: [1, 2], panchina: [3, 4], inRosa: true) == Catalogo.Mercato.panchinaN(n: "2"))
        #expect(PostoInFormazione.testo(5, titolari: [1, 2], panchina: [3, 4], inRosa: true) == Catalogo.Mercato.postoFuori)
        #expect(PostoInFormazione.testo(5, titolari: [1, 2], panchina: [3, 4], inRosa: false) == nil)
        #expect(Catalogo.Mercato.postoTitolare == "Titolare")
    }

    @Test("Sotto il nome la partita e poi il posto, con il punto in mezzo come la web; senza posto solo la partita")
    func dettaglioDellaRiga() throws {
        let g: Giocatore = try Decodifica.decodifica(Data(#"{"id": 7, "nome": "Mario Prova", "ruolo": "D", "squadra": "lecce", "avversario": "frosinone", "in_casa": true}"#.utf8))
        let adesso = Date()
        let partita = RigaGiocatore.sottotitolo(g, adesso: adesso)
        try #require(!partita.isEmpty)
        #expect(RigaCambio.dettaglio(g, posto: "Panchina 3", adesso: adesso) == partita + " · Panchina 3")
        #expect(RigaCambio.dettaglio(g, posto: nil, adesso: adesso) == partita)
    }

    @Test("Nessun compagno può entrare: l'elenco è vuoto (la frase la scrive la vista)")
    func elencoVuoto() async throws {
        let (vm, _) = try await caricata(rotta: { _ in Data(#"{"giornata": 9, "esce": 6523, "entrate": []}"#.utf8) })
        await vm.sostituisci(Prova.incerto)
        let righe = try #require(vm.elencoSostituti?.stato.righe)
        #expect(righe.isEmpty)
        #expect(Catalogo.Formazione.nessunAltroGiocatore == "Nessun altro giocatore di questo ruolo in rosa.")
    }

    @Test("Il testo sotto il titolo spiega il numero della formazione e non mette un punto dopo il nome («Chalobah T..»)")
    func spiegazione() {
        let testo = Catalogo.Formazione.sostSpiega(nome: "Chalobah T.")
        #expect(testo.contains("punti attesi della formazione"))
        #expect(!testo.contains(".."))
    }

    // MARK: errori della rotta

    @Test("400 `giocatore_bloccato`: la frase del server al posto dell'elenco, come informazione e non come errore")
    func giocatoreBloccato() async throws {
        let frase = "Barucci gioca in una partita già cominciata: non si può più spostare."
        let (vm, _) = try await caricata(rotta: { _ in throw ErroreApi.codificato(codice: "giocatore_bloccato", messaggio: frase) })
        await vm.sostituisci(Prova.incerto)
        #expect(vm.elencoSostituti?.stato.frase == frase)
        #expect(vm.elencoSostituti?.stato.motivo == nil)
        #expect(vm.messaggio == nil, "non è un guasto: niente avviso sotto il campo")
    }

    @Test("409 `formazione_chiusa`: l'elenco si chiude, si dice perché e la Formazione si rilegge")
    func formazioneChiusa() async throws {
        let frase = "La formazione di questa giornata è chiusa: la scadenza è passata."
        let (vm, srv) = try await caricata(rotta: { _ in throw ErroreApi.codificato(codice: "formazione_chiusa", messaggio: frase) })
        let lettePrima = srv.quante("GET /api/scelta")
        await vm.sostituisci(Prova.incerto)
        #expect(vm.elencoSostituti == nil)
        #expect(vm.messaggio == frase)
        #expect(srv.quante("GET /api/scelta") > lettePrima, "formazione e scelta si rileggono")
    }

    @Test("Un altro errore della rotta: il motivo dentro l'elenco")
    func altroErrore() async throws {
        let (vm, _) = try await caricata(rotta: { _ in throw ErroreApi.rete("spento") })
        await vm.sostituisci(Prova.incerto)
        #expect(vm.elencoSostituti?.stato.motivo == ErroreApi.testoNonRaggiungibile)
        #expect(vm.elencoSostituti?.stato.frase == nil)
    }

    @Test("A giornata chiusa l'elenco non si apre e la domanda non parte")
    func nonSiApre() async throws {
        let (chiusa, srv) = try await caricata(chiusa: true)
        await chiusa.sostituisci(Prova.incerto)
        #expect(chiusa.elencoSostituti == nil)
        #expect(srv.quante("POST /api/formazione/sostituisci") == 0)
    }

    // MARK: la scelta

    @Test("Un tocco su una riga chiude l'elenco e fa il cambio, che si salva da solo")
    func sceltaSalva() async throws {
        let (vm, srv) = try await caricata()
        await vm.sostituisci(Prova.incerto)
        let fatto = await vm.scegliSostituto(6994)
        #expect(fatto)
        #expect(vm.elencoSostituti == nil)
        let attesi = Prova.titolari.map { $0 == Prova.incerto ? 6994 : $0 }
        #expect(vm.manuale == attesi)
        #expect(vm.salvata?.titolari == attesi, "il cambio è la tua scelta salvata")
        #expect(srv.quante("POST /api/formazione/valuta") == 1)
    }

    // MARK: risposte tardive

    @Test("L'elenco chiuso prima della risposta non si riapre")
    func chiusoPrimaDellaRisposta() async throws {
        let cancello = Cancello()
        let (vm, _) = try await caricata(rotta: { _ in
            await cancello.passa()
            return Data(Prova.risposta.utf8)
        })
        let compito = Task { await vm.sostituisci(Prova.incerto) }
        let aperto = await diventa { vm.elencoSostituti != nil }
        vm.elencoSostituti = nil                            // «Annulla», o il foglio trascinato giù, mentre il server risponde
        await cancello.apri()
        await compito.value
        #expect(aperto)
        #expect(vm.elencoSostituti == nil, "la risposta arrivata dopo non lo riapre")
    }

    // MARK: demo

    @Test("La demo risponde alla rotta per il suo titolare, con i numeri della lega della demo, dal cambio che rende di più")
    func demo() async throws {
        let server = FinteServer.demo
        let f: Formazione = try await server.get("/api/formazione")
        let titolari = f.titolari.map(\.id)
        let esce = FinteServer.esceSostituisci
        #expect(titolari.contains(esce), "il titolare della demo è fra gli 11")
        let r: RispostaSostituisci = try await server.posta("POST", "/api/formazione/sostituisci",
                                                           RichiestaSostituisci(esce: esce, titolari: titolari, giornata: f.giornata))
        #expect(r.esce == esce)
        let entrate = r.entrate ?? []
        #expect(!entrate.isEmpty)
        let ruolo = f.schede?[String(esce)]?.ruolo
        #expect(entrate.allSatisfy { e in !titolari.contains(e.entra ?? 0) && f.schede?[String(e.entra ?? 0)]?.ruolo == ruolo },
                "entrano solo compagni dello stesso ruolo che non sono titolari")
        let differenze = entrate.compactMap(\.differenza)
        #expect(differenze.count == entrate.count)
        #expect(differenze == differenze.sorted(by: >), "dal cambio che rende di più")
    }

    // MARK: aiuti

    /// La Formazione della fixture, senza scelta salvata. `chiusa`: dopo la scadenza (`iniziata`). `rotta`: cosa risponde
    /// `POST /api/formazione/sostituisci`, dal corpo della domanda.
    private func caricata(chiusa: Bool = false, rotta: @escaping @Sendable (Data?) async throws -> Data = { _ in
        Data(Prova.risposta.utf8)
    }) async throws -> (FormazioneViewModel, ServerDiProva) {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        if chiusa { formazione["iniziata"] = true }
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let srv = ServerDiProva { _, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/sostituisci") { return try await rotta(corpo) }
            if percorso.hasPrefix("/api/formazione/valuta") {
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return dati
        }
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        return (vm, srv)
    }

    /// Aspetta al massimo `secondi` che `condizione` sia vera (per ciò che parte in un `Task`); dice se lo è diventata.
    private func diventa(_ secondi: Double = 5, _ condizione: () -> Bool) async -> Bool {
        let limite = Date().addingTimeInterval(secondi)
        while !condizione(), Date() < limite {
            try? await Task.sleep(nanoseconds: 20_000_000)
        }
        return condizione()
    }
}

/// Giocatori della fixture `formazione` (stile equilibrato 4-3-3) e la risposta della rotta, fuori dal `MainActor`: la legge anche
/// il server finto.
private enum Prova {
    /// I titolari del 4-3-3 consigliato, nell'ordine della fixture.
    static let titolari = [7575, 4510, 7318, 5578, 6523, 2404, 6822, 5680, 7525, 7537, 7183]
    /// Gli 11 del 5-3-2, un altro modulo del menu (6523 resta titolare).
    static let titolari532 = [7575, 4510, 7318, 6994, 6523, 7457, 2404, 6822, 5680, 7525, 7537]
    /// Difensore titolare incerto (60%, 3,71 punti attesi da solo).
    static let incerto = 6523

    /// La risposta del server per 6523, volutamente non in ordine di punti attesi da soli (l'app tiene l'ordine del server).
    /// 999999 non è della formazione e 4510 è titolare: non diventano righe. L'ultima riga non ha la differenza.
    static let risposta = """
    {"giornata": 9, "esce": 6523, "punteggio_atteso": 64.1, "entrate": [
      {"entra": 7457, "punteggio_atteso": 64.4, "differenza": 0.3},
      {"entra": 999999, "punteggio_atteso": 65.0, "differenza": 0.9},
      {"entra": 4510, "punteggio_atteso": 64.3, "differenza": 0.2},
      {"entra": 6994, "punteggio_atteso": 64.0, "differenza": -0.1},
      {"entra": 6980, "punteggio_atteso": 64.0}
    ]}
    """

    /// La risposta per 6523 con due difensori in panchina (nel 4-3-3 quinto e terzo) e uno che non è fra i 18 (5678).
    static let rispostaConFuori = """
    {"giornata": 9, "esce": 6523, "punteggio_atteso": 64.1, "entrate": [
      {"entra": 7457, "punteggio_atteso": 64.4, "differenza": 0.3},
      {"entra": 6994, "punteggio_atteso": 64.0, "differenza": -0.1},
      {"entra": 5678, "punteggio_atteso": 63.0, "differenza": -1.1}
    ]}
    """
}

/// Per leggere lo stato dell'elenco nelle prove.
extension ElencoSostituti.Stato {
    /// Le righe, se il server ha risposto.
    var righe: [ElencoSostituti.Riga]? {
        if case .entrate(let righe) = self { return righe }
        return nil
    }
    /// La frase da dire come informazione.
    var frase: String? {
        if case .informazione(let frase) = self { return frase }
        return nil
    }
    /// Il motivo di un errore.
    var motivo: String? {
        if case .errore(let motivo) = self { return motivo }
        return nil
    }
    /// La domanda è partita e la risposta non è arrivata.
    var aspetta: Bool {
        if case .carico = self { return true }
        return false
    }
}
