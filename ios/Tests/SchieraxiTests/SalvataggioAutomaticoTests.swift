import Foundation
import Testing
@testable import Schieraxi

/// Il salvataggio automatico della Formazione unica, come `salvaTitolari` e `tornaConsigliata` di `mostraFormazione` della web
/// (#616, #673): ogni cambio degli 11 (un altro modulo, «Sostituisci», una decisione, la spunta «L'ho messa») è
/// `POST /api/formazione/valuta` con `salva: true` e la giornata (che dà l'If-Match `scelta:<giornata>`), «Torna alla consigliata» è
/// `DELETE /api/scelta`. Una scrittura alla volta; una risposta arrivata dopo una rilettura non vale e si rilegge dal server; 412
/// rilegge e lo dice; con la copia del telefono i comandi che scrivono restano spenti. Dati inventati (fixture).
@MainActor
@Suite("Formazione: salvataggio automatico come la web")
struct SalvataggioAutomaticoTests {
    // MARK: cosa si manda

    @Test("Un cambio di titolare si salva subito: `salva: true` e la giornata, quindi la richiesta porta l'If-Match della scelta")
    func cambioSalvato() async throws {
        let srv = try Self.server()
        let (vm, f) = try await caricata(srv)
        let (esce, entra) = try Self.cambio(f, vm)
        let fatto = await vm.sostituisciTitolare(esce, con: entra)
        #expect(fatto)
        let corpo = try #require(srv.corpiInviati(a: "POST /api/formazione/valuta").last)
        let testo = String(decoding: corpo, as: UTF8.self)
        #expect(testo.contains("\"salva\":true") && testo.contains("\"giornata\":9"), "\(testo)")
        #expect(!testo.contains("messa"), "senza la spunta il server lascia «L'ho messa» com'era")
        #expect(VersioniRisorse.risorsa(per: "/api/formazione/valuta", corpo: corpo) == "scelta:9")
        #expect(vm.vista(f).titolari.map(\.id).contains(entra))
        #expect(vm.statoScelta == .cambiata(diversi: 1, punti: 20.0 - 71.1))
        #expect(!vm.occupato)
    }

    @Test("Un altro modulo dal menu si salva; il consigliato toglie la scelta (`DELETE /api/scelta`), come la web")
    func moduloSalvatoEConsigliato() async throws {
        let srv = try Self.server()
        let (vm, f) = try await caricata(srv)
        let consigliato = try #require(vm.consigliato(f))
        let altro = try #require(vm.moduli(f).first { $0.modulo != consigliato.modulo })
        await vm.scegliModulo(altro.modulo)
        #expect(Self.salvataggi(srv) == 1)
        #expect(vm.salvata?.titolari == altro.titolari)
        #expect(vm.vista(f).modulo == altro.modulo)
        await vm.scegliModulo(consigliato.modulo)
        #expect(srv.quante("DELETE /api/scelta?giornata=9") == 1)
        #expect(vm.salvata == nil && vm.manuale == nil)
        #expect(vm.statoScelta == .consigliata)
        // con la consigliata già in campo e niente di salvato, «Torna alla consigliata» non chiede niente al server
        await vm.tornaAllaConsigliata()
        #expect(srv.quante("DELETE") == 1)
    }

    @Test("La spunta «L'ho messa» manda `messa` vero o falso; un cambio degli 11 dopo la toglie, come il server")
    func spunta() async throws {
        let srv = try Self.server()
        let (vm, f) = try await caricata(srv)
        await vm.segnaMessa(true)
        #expect(Self.ultimoCorpo(srv).contains("\"messa\":true"))
        #expect(vm.messa)
        #expect(vm.statoScelta == .consigliata, "messa la consigliata: resta «È la consigliata.»")
        #expect(vm.salvata?.eraConsigliata == true)
        await vm.segnaMessa(false)
        #expect(Self.ultimoCorpo(srv).contains("\"messa\":false"))
        #expect(!vm.messa)
        await vm.segnaMessa(true)
        let (esce, entra) = try Self.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(!Self.ultimoCorpo(srv).contains("messa"))
        #expect(!vm.messa, "altri 11: la spunta non vale più")
        #expect(Self.salvataggi(srv) == 4)
    }

    // MARK: una scrittura alla volta

    @Test("Mentre una scrittura è in volo i comandi sono spenti e un secondo cambio non parte")
    func unaAllaVolta() async throws {
        let cancello = Cancello()
        let srv = try Self.server(cancello: cancello)
        let (vm, f) = try await caricata(srv)
        let altro = try #require(vm.moduli(f).first { $0.modulo != vm.consigliato(f)?.modulo })
        let primo = Task { await vm.scegliModulo(altro.modulo) }
        await cancello.richiestaArrivata()
        #expect(vm.occupato && vm.comandiSpenti)
        #expect(vm.statoScelta == .consigliata, "finché il server non risponde in campo resta quella di prima")
        let (esce, entra) = try Self.cambio(f, vm)
        let secondo = await vm.sostituisciTitolare(esce, con: entra)
        #expect(!secondo)
        await cancello.apri()
        await primo.value
        #expect(!vm.occupato && !vm.comandiSpenti)
        #expect(Self.salvataggi(srv) == 1)
        #expect(vm.vista(f).modulo == altro.modulo)
    }

    @Test("Una risposta arrivata dopo una rilettura non vale: si rilegge dal server, mai una scelta salvata che non si vede")
    func rispostaVecchia() async throws {
        let cancello = Cancello()
        let salvata = Scatola<String>()
        let srv = try Self.server(cancello: cancello, salvata: salvata)
        let (vm, f) = try await caricata(srv)
        let altro = try #require(vm.moduli(f).first { $0.modulo != vm.consigliato(f)?.modulo })
        let salvataggio = Task { await vm.scegliModulo(altro.modulo) }
        await cancello.richiestaArrivata()
        await vm.carica()                       // la schermata si rilegge mentre il salvataggio è in volo
        #expect(vm.manuale == nil, "il server non ha ancora scritto niente")
        await cancello.apri()
        await salvataggio.value
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(altro.titolari), "riletta dal server: c'è la scelta salvata")
        #expect(srv.quante("GET /api/formazione") == 3, "apertura, rilettura e la rilettura dopo la risposta vecchia")
        #expect(!vm.occupato)
    }

    // MARK: errori

    @Test("412 (cambiata da un altro dispositivo): si dice che si ricarica, si rilegge e poi si chiede di controllare")
    func cambiataAltrove() async throws {
        let salvata = Scatola<String>()
        let altroDispositivo = try Self.altroModulo()
        let srv = try Self.server(salvata: salvata, conflitto: true) {
            // l'altro dispositivo ha salvato la sua scelta: dopo il 412 la lettura la trova
            salvata.valore = Self.json(altroDispositivo)
        }
        let (vm, f) = try await caricata(srv)
        let (esce, entra) = try Self.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(vm.messaggio == ErroreApi.conflitto.localizedDescription)
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(altroDispositivo), "in campo la scelta dell'altro dispositivo")
        #expect(srv.quante("GET /api/formazione") == 2)
        #expect(!vm.comandiSpenti)
    }

    @Test("412 e rilettura della scelta non riuscita: resta «sto ricaricando», la riga dice che non si è letta, comandi spenti")
    func cambiataAltroveSenzaRete() async throws {
        let giu = Scatola<Bool>()
        let srv = try Self.server(conflitto: true, giu: giu) { giu.valore = true }
        let (vm, f) = try await caricata(srv)
        let (esce, entra) = try Self.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(vm.messaggio == Catalogo.Comune.cambiatoRicarico)
        #expect(vm.statoScelta == .nonLetta)
        #expect(vm.comandiSpenti)
    }

    @Test("I dati nuovi non arrivano: resta la copia, che non si può cambiare (`formazione.copia_ferma`); tornata la rete sì")
    func copiaDelTelefono() async throws {
        let giu = Scatola<Bool>()
        let srv = try Self.server(giu: giu)
        let (vm, f) = try await caricata(srv)
        giu.valore = true
        let letta = await vm.carica()
        #expect(!letta)
        #expect(vm.formazione != nil, "resta quello che c'era")
        #expect(vm.copiaFerma && vm.comandiSpenti)
        let (esce, entra) = try Self.cambio(f, vm)
        let fatto = await vm.sostituisciTitolare(esce, con: entra)
        await vm.segnaMessa(true)
        #expect(!fatto && Self.salvataggi(srv) == 0)
        #expect(!vm.sostituibile(esce))
        giu.valore = false
        let riletta = await vm.carica()
        #expect(riletta)
        #expect(!vm.copiaFerma && !vm.comandiSpenti)
    }

    // MARK: aiuti

    /// Gli 11 del secondo modulo dello stile equilibrato della fixture.
    static func altroModulo() throws -> [Int] {
        let f: Formazione = try Fixture.decodifica("formazione")
        let livello = try #require(f.livelli?.first { $0.rischio == 0 })
        return try #require(livello.moduli.first { $0.modulo != livello.modulo }).titolari
    }

    /// Il cambio di un difensore titolare con uno della rosa che non gioca.
    static func cambio(_ f: Formazione, _ vm: FormazioneViewModel) throws -> (esce: Int, entra: Int) {
        let titolari = vm.vista(f).titolari
        let uscente = try #require(titolari.first { $0.ruolo == "D" })
        let dentro = Set(titolari.map(\.id))
        let entrante = try #require(f.schede?.values.filter { $0.ruolo == "D" && !dentro.contains($0.id) }.map(\.id).min())
        return (uscente.id, entrante)
    }

    /// La risposta di `GET /api/scelta` per questi titolari.
    nonisolated static func json(_ titolari: [Int]) -> String {
        "{\"titolari\": [\(titolari.map(String.init).joined(separator: ","))], \"salvata\": \"2026-11-02T21:40:00\"}"
    }

    /// La richiesta salva la scelta (`salva: true` nel corpo di `POST /api/formazione/valuta`).
    nonisolated static func salva(_ corpo: Data?) -> Bool {
        corpo.map { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") } == true
    }

    static func salvataggi(_ srv: ServerDiProva) -> Int {
        srv.corpiInviati(a: "POST /api/formazione/valuta").filter { Self.salva($0) }.count
    }

    static func ultimoCorpo(_ srv: ServerDiProva) -> String {
        srv.corpiInviati(a: "POST /api/formazione/valuta").last.map { String(decoding: $0, as: UTF8.self) } ?? ""
    }

    /// Un server con la formazione della fixture e la scelta in `salvata` (nil = nessuna), che un salvataggio riuscito aggiorna come
    /// il server vero. `cancello`: il salvataggio aspetta il test; `conflitto`: salvataggi e cancellazioni rispondono 412 dopo aver
    /// chiamato `dopoIlConflitto`; `giu`: finché vale vero non risponde la lettura della scelta (e, senza conflitto, niente).
    static func server(cancello: Cancello? = nil, salvata: Scatola<String> = Scatola(), conflitto: Bool = false,
                       giu: Scatola<Bool> = Scatola(), dopoIlConflitto: @escaping @Sendable () -> Void = {}) throws -> ServerDiProva {
        let dati = try Fixture.dati("formazione")
        return ServerDiProva { metodo, percorso, corpo in
            let scrive = metodo == "DELETE" || Self.salva(corpo)
            if conflitto, scrive {
                dopoIlConflitto()
                throw ErroreApi.conflitto
            }
            if giu.valore == true, percorso.hasPrefix("/api/scelta") || !conflitto { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/formazione/valuta") {
                if let cancello, Self.salva(corpo) { await cancello.passa() }
                if Self.salva(corpo), let corpo, let o = try? JSONSerialization.jsonObject(with: corpo) as? [String: Any],
                   let titolari = o["titolari"] as? [Int] {
                    salvata.valore = Self.json(titolari)
                }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") {
                if metodo == "DELETE" {
                    salvata.valore = nil
                    return Data("{\"ok\": true}".utf8)
                }
                return Data((salvata.valore ?? "null").utf8)
            }
            return dati
        }
    }

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}
