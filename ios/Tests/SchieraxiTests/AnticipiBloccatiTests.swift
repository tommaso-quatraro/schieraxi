import Foundation
import Testing
@testable import Schieraxi

/// Anticipi già cominciati (#373). Il server dice in `bloccati` (campo facoltativo di `GET /api/formazione`) chi gioca una partita
/// già cominciata: nella lega non si sposta più. Come la web (`sostituti` in `fanta/web/app.js`), nella modifica a mano un
/// titolare fermo non si sostituisce e uno fermo non entra dalla rosa; sotto i titolari una riga lo dice con la frase della web
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

    @Test("Modifica a mano: un titolare fermo non si sostituisce, uno fermo non entra, gli altri come sempre")
    func sostituzioni() async throws {
        let (vm, f) = try await caricata()
        vm.iniziaModificaManuale(f)
        let prima = try #require(vm.manuale)
        #expect(prima.contains(Self.titolareFermo) && prima.contains(Self.titolareLibero))
        let fermo = try #require(f.schede?[String(Self.titolareFermo)])
        let libero = try #require(f.schede?[String(Self.titolareLibero)])
        #expect(vm.sostituti(di: fermo, f).isEmpty)
        let ids = vm.sostituti(di: libero, f).map(\.id)
        #expect(!ids.contains(Self.fuoriFermo))
        #expect(ids.contains(Self.fuoriLibero))
        vm.sostituisci(Self.titolareFermo, con: Self.fuoriLibero)
        #expect(vm.manuale == prima)
        vm.sostituisci(Self.titolareLibero, con: Self.fuoriFermo)
        #expect(vm.manuale == prima)
        vm.sostituisci(Self.titolareLibero, con: Self.fuoriLibero)
        #expect(vm.manuale?.contains(Self.fuoriLibero) == true)
        #expect(vm.manuale?.contains(Self.titolareFermo) == true)
    }

    @Test("Senza `bloccati` la sostituzione è quella di sempre")
    func senzaCampoComeSempre() async throws {
        let (vm, f) = try await caricata(conBloccati: false)
        vm.iniziaModificaManuale(f)
        let fermo = try #require(f.schede?[String(Self.titolareFermo)])
        #expect(vm.sostituti(di: fermo, f).map(\.id).contains(Self.fuoriFermo))
    }

    @Test("La riga sotto i titolari: la frase della web, solo in modifica a mano e solo se qualcuno è fermo")
    func riga() async throws {
        let web = try TestiWeb().italiano("formazione.bloccati")
        let (vm, f) = try await caricata()
        #expect(vm.notaFermi == nil)
        vm.iniziaModificaManuale(f)
        #expect(vm.notaFermi == web)
        let (senza, fs) = try await caricata(conBloccati: false)
        senza.iniziaModificaManuale(fs)
        #expect(senza.notaFermi == nil)
    }

    @Test("Salvataggio rifiutato dal server: la sua frase, la stessa della web")
    func salvataggioRifiutato() async throws {
        let frase = "Rossi gioca in una partita già cominciata: non si può più spostare."
        let web = try TestiWeb().italiano("err.giocatore_bloccato").replacingOccurrences(of: "{1}", with: "Rossi")
        #expect(frase == web)
        let (vm, f) = try await caricata(rifiutaCon: frase)
        await vm.salvaQuesta(f)
        #expect(vm.messaggio == frase)
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
