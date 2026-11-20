import Foundation
import Testing
@testable import Schieraxi

/// «Metti in campo» dalla scheda (#778), come `apriMettiInCampo` della web (#643, PR #783): nella scheda di chi non è fra gli 11
/// il pulsante c'è esattamente quando c'è «Sostituisci» per i titolari (una sola condizione, `siSposta` della web); il tocco chiede
/// a `POST /api/formazione/metti-in-campo` chi può lasciargli il posto, con gli 11 in campo, e l'elenco mostra i numeri del server
/// nel suo ordine. `giocatore_bloccato` è un'informazione al posto dell'elenco, `formazione_chiusa` chiude l'elenco e rilegge, il
/// 412 al salvataggio rilegge e lo dice; un elenco chiuso prima della risposta non si riapre.
@MainActor
@Suite("«Metti in campo» dalla scheda, come la web")
struct MettiInCampoTests {

    // MARK: quando c'è

    @Test("«Metti in campo» per chi non è fra gli 11 esattamente quando c'è «Sostituisci» per i titolari: la stessa condizione",
          arguments: CasoCondizione.allCases)
    func stessaCondizione(_ caso: CasoCondizione) async throws {
        let (vm, _) = try await caricata(chiusa: caso == .chiusa, sceltaLetta: caso != .comandiSpenti)
        if caso == .altraSquadra {
            vm.vediSquadra("Gli Amici")
            await vm.carica()                               // la formazione dell'altra squadra (nella prova, gli stessi dati)
        }
        let aperta = caso == .aperta
        #expect(vm.sostituibile(Prova.titolare) == aperta)
        #expect(vm.entrabile(Prova.panchinaro) == aperta)
        #expect(vm.entrabile(Prova.indisponibile) == aperta, "infortunati e squalificati entrano, come fra i sostituti")
        #expect(vm.contestoScheda(Prova.panchinaro)?.entrabile == aperta)
        #expect(vm.contestoScheda(Prova.panchinaro)?.sostituibile == false)
        #expect(!vm.entrabile(Prova.titolare), "un titolare ha «Sostituisci», non «Metti in campo»")
        #expect(vm.contestoScheda(Prova.titolare)?.entrabile == false)
        #expect(!vm.entrabile(Prova.estraneo), "chi non è nella Formazione")
    }

    @Test("Chi gioca un anticipo già cominciato non ha «Metti in campo»: nella scheda la frase, anche se è in panchina (come la web)")
    func fermoInPanchina() async throws {
        let (vm, srv) = try await caricata(bloccati: [Prova.panchinaroFermo])
        #expect(!vm.entrabile(Prova.panchinaroFermo))
        #expect(vm.fermo(Prova.panchinaroFermo))
        let c = try #require(vm.contestoScheda(Prova.panchinaroFermo))
        #expect(c.fermo && !c.entrabile && !c.sostituibile)
        #expect(vm.entrabile(Prova.panchinaro), "gli altri sì")
        await vm.mettiInCampo(Prova.panchinaroFermo)
        #expect(vm.elencoEntra == nil, "per chi è fermo l'elenco non si apre")
        #expect(srv.quante("POST /api/formazione/metti-in-campo") == 0)
    }

    // MARK: la domanda e l'elenco

    @Test("La domanda manda chi entra, gli 11 in campo (dopo un cambio, i nuovi) e la giornata; l'elenco si apre subito con «Carico…»")
    func domandaConGli11InCampo() async throws {
        let cancello = Cancello()
        let (vm, srv) = try await caricata(rotta: { _ in
            await cancello.passa()
            return Data(Prova.risposta.utf8)
        })
        await vm.scegliModulo("5-3-2")
        #expect(vm.manuale == Prova.titolari532, "in campo c'è il 5-3-2, già salvato")
        let compito = Task { await vm.mettiInCampo(Prova.panchinaro) }
        let aperto = await diventa { vm.elencoEntra?.stato.aspetta == true }
        await cancello.apri()
        await compito.value
        #expect(aperto, "l'elenco si apre prima della risposta, con «Carico…»")
        #expect(vm.elencoEntra?.entra.id == Prova.panchinaro)
        #expect(srv.quante("POST /api/formazione/metti-in-campo") == 1)
        let corpo = try #require(srv.corpiInviati(a: "/api/formazione/metti-in-campo").first)
        let letto = try JSONSerialization.jsonObject(with: corpo)
        let domanda = try #require(letto as? [String: Any])
        #expect(domanda["entra"] as? Int == Prova.panchinaro)
        #expect(domanda["titolari"] as? [Int] == Prova.titolari532, "gli 11 in campo, non quelli della consigliata")
        #expect(domanda["giornata"] as? Int == 9)
    }

    @Test("Le righe nell'ordine del server, solo i titolari in campo, con i suoi numeri: differenza, modulo e se cambia")
    func righeNellOrdineDelServer() async throws {
        let (vm, _) = try await caricata()
        await vm.mettiInCampo(Prova.panchinaro)
        let righe = try #require(vm.elencoEntra?.stato.righe)
        #expect(righe.map(\.esce.id) == [7183, 2404, 5680], "nell'ordine del server, senza chi non è fra gli 11 in campo")
        #expect(righe.map(\.differenza) == [-1.6, 0.4, nil], "il numero del server; senza, niente numero")
        #expect(righe.map(\.cambiaModulo) == [true, false, false])
        #expect(righe.first?.modulo == "4-4-2")
        #expect(righe.first?.esce.nome == "Lanotti E.", "la scheda del titolare viene dalla Formazione")
        #expect(vm.messaggio == nil)
    }

    @Test("Nessun titolare può lasciargli il posto: l'elenco è vuoto (la frase la scrive la vista)")
    func elencoVuoto() async throws {
        let (vm, _) = try await caricata(rotta: { _ in Data(#"{"giornata": 9, "entra": 5307, "uscite": []}"#.utf8) })
        await vm.mettiInCampo(Prova.panchinaro)
        let righe = try #require(vm.elencoEntra?.stato.righe)
        #expect(righe.isEmpty)
        #expect(Catalogo.Formazione.nessunoLasciaPosto == "Nessun titolare può lasciargli il posto.")
    }

    // MARK: errori della rotta

    @Test("400 `giocatore_bloccato`: la frase del server al posto dell'elenco, come informazione e non come errore")
    func giocatoreBloccato() async throws {
        let frase = "Barese Torozzi gioca in una partita già cominciata: non si può più spostare."
        let (vm, _) = try await caricata(rotta: { _ in throw ErroreApi.codificato(codice: "giocatore_bloccato", messaggio: frase) })
        await vm.mettiInCampo(Prova.panchinaro)
        #expect(vm.elencoEntra?.stato.frase == frase)
        #expect(vm.elencoEntra?.stato.motivo == nil)
        #expect(vm.messaggio == nil, "non è un guasto: niente avviso sotto il campo")
    }

    @Test("409 `formazione_chiusa`: l'elenco si chiude, si dice perché e la Formazione si rilegge")
    func formazioneChiusa() async throws {
        let frase = "La formazione di questa giornata è chiusa: la scadenza è passata."
        let (vm, srv) = try await caricata(rotta: { _ in throw ErroreApi.codificato(codice: "formazione_chiusa", messaggio: frase) })
        let lettePrima = srv.quante("GET /api/scelta")
        await vm.mettiInCampo(Prova.panchinaro)
        #expect(vm.elencoEntra == nil)
        #expect(vm.messaggio == frase)
        #expect(srv.quante("GET /api/scelta") > lettePrima, "formazione e scelta si rileggono")
    }

    @Test("Un altro errore della rotta: il motivo dentro l'elenco")
    func altroErrore() async throws {
        let (vm, _) = try await caricata(rotta: { _ in throw ErroreApi.rete("spento") })
        await vm.mettiInCampo(Prova.panchinaro)
        #expect(vm.elencoEntra?.stato.motivo == ErroreApi.testoNonRaggiungibile)
        #expect(vm.elencoEntra?.stato.frase == nil)
    }

    // MARK: la scelta

    @Test("Un tocco su una riga chiude l'elenco e fa il cambio, che si salva da solo, come «Sostituisci»")
    func sceltaSalva() async throws {
        let (vm, srv) = try await caricata()
        await vm.mettiInCampo(Prova.panchinaro)
        let fatto = await vm.scegliChiEsce(2404)
        #expect(fatto)
        #expect(vm.elencoEntra == nil)
        let attesi = Prova.titolari.map { $0 == 2404 ? Prova.panchinaro : $0 }
        #expect(vm.manuale == attesi)
        #expect(vm.salvata?.titolari == attesi, "il cambio è la tua scelta salvata")
        #expect(srv.quante("POST /api/formazione/valuta") == 1)
    }

    @Test("412 al salvataggio: si rilegge e lo si dice, come ogni salvataggio")
    func conflittoAlSalvataggio() async throws {
        let (vm, srv) = try await caricata(salvataggio: .conflitto)
        await vm.mettiInCampo(Prova.panchinaro)
        let lettePrima = srv.quante("GET /api/scelta")
        await vm.scegliChiEsce(2404)
        #expect(vm.elencoEntra == nil)
        #expect(vm.messaggio == ErroreApi.conflitto.localizedDescription)
        #expect(srv.quante("GET /api/scelta") > lettePrima, "formazione e scelta si rileggono")
        #expect(vm.manuale == nil, "in campo resta quella del server")
    }

    // MARK: risposte tardive

    @Test("L'elenco chiuso prima della risposta non si riapre")
    func chiusoPrimaDellaRisposta() async throws {
        let cancello = Cancello()
        let (vm, _) = try await caricata(rotta: { _ in
            await cancello.passa()
            return Data(Prova.risposta.utf8)
        })
        let compito = Task { await vm.mettiInCampo(Prova.panchinaro) }
        let aperto = await diventa { vm.elencoEntra != nil }
        vm.elencoEntra = nil                                // «Annulla», o il foglio trascinato giù, mentre il server risponde
        await cancello.apri()
        await compito.value
        #expect(aperto)
        #expect(vm.elencoEntra == nil, "la risposta arrivata dopo non lo riapre")
    }

    @Test("Chiuso e aperto per un altro: la risposta del primo non prende il posto del secondo")
    func rispostaDiUnElencoVecchio() async throws {
        let cancello = Cancello()
        let (vm, _) = try await caricata(rotta: { corpo in
            let domanda = corpo.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]
            guard domanda?["entra"] as? Int == Prova.panchinaro else { return Data(Prova.rispostaAltro.utf8) }
            await cancello.passa()
            return Data(Prova.risposta.utf8)
        })
        let primo = Task { await vm.mettiInCampo(Prova.panchinaro) }
        let aperto = await diventa { vm.elencoEntra?.entra.id == Prova.panchinaro }
        vm.elencoEntra = nil
        await vm.mettiInCampo(Prova.altroPanchinaro)
        await cancello.apri()
        await primo.value
        #expect(aperto)
        #expect(vm.elencoEntra?.entra.id == Prova.altroPanchinaro)
        #expect(vm.elencoEntra?.stato.righe?.map(\.esce.id) == [7537])
    }

    // MARK: dalla scheda

    @Test("«Metti in campo» nella scheda: l'elenco si apre quando il foglio della scheda è sparito, una volta sola")
    func elencoInAttesa() async throws {
        let (vm, srv) = try await caricata()
        vm.apriMettiInCampoInAttesa()
        vm.chiediMettiInCampo(Prova.panchinaro)
        #expect(vm.elencoEntra == nil, "finché la scheda è aperta l'elenco non parte")
        vm.apriMettiInCampoInAttesa()
        #expect(await diventa { vm.elencoEntra?.stato.righe != nil })
        #expect(vm.elencoEntra?.entra.id == Prova.panchinaro)
        vm.elencoEntra = nil
        vm.apriMettiInCampoInAttesa()
        vm.chiediMettiInCampo(Prova.titolare)              // un titolare non si mette in campo
        vm.apriMettiInCampoInAttesa()
        try await Task.sleep(nanoseconds: 200_000_000)
        #expect(vm.elencoEntra == nil)
        #expect(srv.quante("POST /api/formazione/metti-in-campo") == 1)
    }

    // MARK: demo

    @Test("La demo risponde alla rotta per il suo panchinaro, con i numeri della lega della demo, dal cambio che rende di più")
    func demo() async throws {
        let server = FinteServer.demo
        let f: Formazione = try await server.get("/api/formazione")
        let titolari = f.titolari.map(\.id)
        let entra = FinteServer.entraMettiInCampo
        #expect(!titolari.contains(entra) && f.panchina.contains { $0.id == entra }, "il panchinaro della demo è in panchina")
        let r: RispostaMettiInCampo = try await server.posta("POST", "/api/formazione/metti-in-campo",
                                                            RichiestaMettiInCampo(entra: entra, titolari: titolari, giornata: f.giornata))
        #expect(r.entra == entra)
        let uscite = r.uscite ?? []
        #expect(!uscite.isEmpty)
        #expect(uscite.allSatisfy { titolari.contains($0.esce ?? 0) }, "escono solo titolari")
        let differenze = uscite.compactMap(\.differenza)
        #expect(differenze.count == uscite.count)
        #expect(differenze == differenze.sorted(by: >), "dal cambio che rende di più")
        #expect(uscite.first?.cambiaModulo == true, "in cima un cambio di modulo, che la foto mostra")
    }

    // MARK: aiuti

    /// La Formazione della fixture, senza scelta salvata. `chiusa`: dopo la scadenza (`iniziata`). `bloccati`: chi gioca un
    /// anticipo già cominciato. `sceltaLetta` falso: `/api/scelta` non risponde e i comandi restano spenti. `rotta`: cosa risponde
    /// `POST /api/formazione/metti-in-campo`, dal corpo della domanda. `salvataggio`: l'errore di ogni salvataggio (`salva: true`).
    private func caricata(chiusa: Bool = false, bloccati: [Int] = [], sceltaLetta: Bool = true,
                          rotta: @escaping @Sendable (Data?) async throws -> Data = { _ in Data(Prova.risposta.utf8) },
                          salvataggio: ErroreApi? = nil) async throws -> (FormazioneViewModel, ServerDiProva) {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        if !bloccati.isEmpty { formazione["bloccati"] = bloccati }
        if chiusa { formazione["iniziata"] = true }
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let srv = ServerDiProva { _, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/metti-in-campo") { return try await rotta(corpo) }
            if percorso.hasPrefix("/api/formazione/valuta") {
                if let salvataggio, let corpo, String(decoding: corpo, as: UTF8.self).contains("\"salva\":true") { throw salvataggio }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") {
                if !sceltaLetta { throw ErroreApi.rete("spento") }
                return Data("null".utf8)
            }
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

/// I casi della condizione unica di «Sostituisci» e «Metti in campo».
enum CasoCondizione: String, CaseIterable, Sendable {
    /// La tua formazione, aperta, con la scelta letta: i due pulsanti ci sono.
    case aperta
    /// Dopo la scadenza.
    case chiusa
    /// La formazione di un'altra squadra della lega.
    case altraSquadra
    /// La scelta salvata non si è letta: i comandi che scrivono sono spenti.
    case comandiSpenti
}

/// Giocatori della fixture `formazione` (stile equilibrato 4-3-3) e risposte della rotta, fuori dal `MainActor`: le leggono anche
/// i server finti.
private enum Prova {
    /// I titolari del 4-3-3 consigliato, nell'ordine della fixture.
    static let titolari = [7575, 4510, 7318, 5578, 6523, 2404, 6822, 5680, 7525, 7537, 7183]
    /// Gli 11 del 5-3-2, un altro modulo del menu (senza 5307).
    static let titolari532 = [7575, 4510, 7318, 6994, 6523, 7457, 2404, 6822, 5680, 7525, 7537]
    static let titolare = 7525
    /// Centrocampista in panchina.
    static let panchinaro = 5307
    /// Attaccante in panchina.
    static let altroPanchinaro = 1926
    /// Difensore della rosa fuori dai 18, che non gioca (fra «Infortunati e squalificati»).
    static let indisponibile = 5678
    /// Difensore in panchina, fermo quando la prova lo mette fra i `bloccati`.
    static let panchinaroFermo = 6994
    /// Non sta nella Formazione.
    static let estraneo = 999_999

    /// La risposta del server per 5307, volutamente non in ordine di `differenza` (l'app tiene l'ordine del server). 999999 non è
    /// della formazione e 1926 non è fra gli 11: non diventano righe. L'ultima riga non ha la differenza.
    static let risposta = """
    {"giornata": 9, "entra": 5307, "punteggio_atteso": 64.1, "uscite": [
      {"esce": 7183, "modulo": "4-4-2", "cambia_modulo": true, "punteggio_atteso": 62.5, "differenza": -1.6},
      {"esce": 999999, "modulo": "4-3-3", "cambia_modulo": false, "punteggio_atteso": 65.0, "differenza": 0.9},
      {"esce": 2404, "modulo": "4-3-3", "cambia_modulo": false, "punteggio_atteso": 64.5, "differenza": 0.4},
      {"esce": 1926, "modulo": "4-3-3", "cambia_modulo": false, "punteggio_atteso": 64.3, "differenza": 0.2},
      {"esce": 5680, "modulo": "4-3-3", "cambia_modulo": false, "punteggio_atteso": 64.1}
    ]}
    """

    /// La risposta per 1926, un altro elenco.
    static let rispostaAltro = """
    {"giornata": 9, "entra": 1926, "punteggio_atteso": 64.1, "uscite": [
      {"esce": 7537, "modulo": "4-3-3", "cambia_modulo": false, "punteggio_atteso": 63.2, "differenza": -0.9}
    ]}
    """
}

/// Per leggere lo stato dell'elenco nelle prove.
extension ElencoMettiInCampo.Stato {
    /// Le righe, se il server ha risposto.
    var righe: [ElencoMettiInCampo.Riga]? {
        if case .uscite(let righe) = self { return righe }
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
