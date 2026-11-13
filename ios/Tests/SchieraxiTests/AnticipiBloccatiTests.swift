import Foundation
import Testing
@testable import Schieraxi

/// Anticipi già cominciati (#373). Il server dice in `bloccati` (campo facoltativo di `GET /api/formazione`) chi gioca una partita
/// già cominciata: nella lega non si sposta più. Come la web (`sostituti` in `fanta/web/app.js`), un titolare fermo non si
/// sostituisce e uno fermo non entra dalla rosa; nella sua scheda, al posto di «Sostituisci», la frase della web
/// (`formazione.bloccati`). Un salvataggio che ne sposta uno il server lo rifiuta (400 `giocatore_bloccato`): si mostra la sua frase,
/// la stessa della web (`err.giocatore_bloccato`).
@MainActor
@Suite("Anticipi già cominciati come la web")
struct AnticipiBloccatiTests {
    /// Nella fixture, stile equilibrato 4-3-3: 4510 e 7318 difensori titolari, 6994 e 6980 difensori non titolari.
    static let titolareFermo = 4510
    static let fuoriFermo = 6994
    static let titolareLibero = 7318
    static let fuoriLibero = 6980

    @Test("Il campo `bloccati` si legge; senza il campo (server vecchio, nessun anticipo cominciato) nessuno è fermo")
    func campo() async throws {
        let base: Formazione = try Fixture.decodifica("formazione")
        #expect(base.bloccati == nil)
        let (vm, f) = try await caricata()
        #expect(f.bloccati == [Self.titolareFermo, Self.fuoriFermo])
        #expect(vm.fermi == [Self.titolareFermo, Self.fuoriFermo])
        let (senza, _) = try await caricata(conBloccati: false)
        #expect(senza.fermi.isEmpty)
    }

    @Test("Un titolare fermo non si sostituisce, uno fermo non entra, gli altri come sempre (e il cambio si salva subito)")
    func sostituzioni() async throws {
        let (vm, f) = try await caricata()
        let prima = vm.vista(f).titolari.map(\.id)
        #expect(prima.contains(Self.titolareFermo) && prima.contains(Self.titolareLibero))
        let fermo = try #require(f.schede?[String(Self.titolareFermo)])
        let libero = try #require(f.schede?[String(Self.titolareLibero)])
        #expect(vm.sostituti(di: fermo, f).isEmpty)
        let ids = vm.sostituti(di: libero, f).map(\.id)
        #expect(!ids.contains(Self.fuoriFermo))
        #expect(ids.contains(Self.fuoriLibero))
        let esceFermo = await vm.sostituisciTitolare(Self.titolareFermo, con: Self.fuoriLibero)
        let entraFermo = await vm.sostituisciTitolare(Self.titolareLibero, con: Self.fuoriFermo)
        #expect(!esceFermo && !entraFermo)
        #expect(vm.vista(f).titolari.map(\.id) == prima, "niente cambi su chi è fermo")
        let fatto = await vm.sostituisciTitolare(Self.titolareLibero, con: Self.fuoriLibero)
        #expect(fatto)
        let dopo = vm.vista(f).titolari.map(\.id)
        #expect(dopo.contains(Self.fuoriLibero) && dopo.contains(Self.titolareFermo) && !dopo.contains(Self.titolareLibero))
    }

    @Test("Senza `bloccati` la sostituzione è quella di sempre")
    func senzaCampoComeSempre() async throws {
        let (vm, f) = try await caricata(conBloccati: false)
        let fermo = try #require(f.schede?[String(Self.titolareFermo)])
        #expect(vm.sostituti(di: fermo, f).map(\.id).contains(Self.fuoriFermo))
    }

    @Test("Nella scheda di chi è fermo niente «Sostituisci» ma la frase della web; senza `bloccati` «Sostituisci»")
    func scheda() async throws {
        let (vm, _) = try await caricata()
        #expect(vm.fermo(Self.titolareFermo))
        #expect(!vm.sostituibile(Self.titolareFermo))
        #expect(vm.contestoScheda(Self.titolareFermo)?.fermo == true)
        #expect(Catalogo.Formazione.bloccati == "Chi gioca in una partita già cominciata non si può più spostare.")
        let (senza, _) = try await caricata(conBloccati: false)
        #expect(!senza.fermo(Self.titolareFermo))
        #expect(senza.sostituibile(Self.titolareFermo))
    }

    @Test("Salvataggio rifiutato dal server: la sua frase, la stessa della web")
    func salvataggioRifiutato() async throws {
        let frase = "Rossi gioca in una partita già cominciata: non si può più spostare."
        let web = try TestiWeb().italiano("err.giocatore_bloccato").replacingOccurrences(of: "{1}", with: "Rossi")
        #expect(frase == web)
        let (vm, f) = try await caricata(rifiutaCon: frase)
        let prima = vm.vista(f).titolari.map(\.id)
        await vm.sostituisciTitolare(Self.titolareLibero, con: Self.fuoriLibero)
        #expect(vm.messaggio == frase)
        #expect(vm.vista(f).titolari.map(\.id) == prima, "il cambio rifiutato non resta in campo")
    }

    // MARK: aiuti

    /// La Formazione della fixture con `bloccati` = il titolare e il fuori fermi (`conBloccati: false` = senza il campo); con
    /// `rifiutaCon` ogni salvataggio risponde 400 `giocatore_bloccato` con quella frase.
    private func caricata(conBloccati: Bool = true, rifiutaCon frase: String? = nil) async throws -> (FormazioneViewModel, Formazione) {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        if conBloccati { formazione["bloccati"] = [Self.titolareFermo, Self.fuoriFermo] }
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let srv = ServerDiProva { _, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if let frase, let corpo, String(decoding: corpo, as: UTF8.self).contains("\"salva\":true") {
                    throw ErroreApi.codificato(codice: "giocatore_bloccato", messaggio: frase)
                }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return dati
        }
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}
