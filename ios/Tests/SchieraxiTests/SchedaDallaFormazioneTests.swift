import Foundation
import Testing
@testable import Schieraxi

/// La scheda aperta dalla Formazione, come `stato.formaz` di app.js (#616): si apre subito con la previsione già letta, dice
/// «Perché è titolare» solo sulla consigliata a formazione aperta, e per un titolare della tua formazione ha «Sostituisci» (o, se
/// gioca un anticipo già cominciato, la frase di `formazione.bloccati`). La sostituzione parte dagli undici sullo schermo.
@MainActor
@Suite("La scheda aperta dalla Formazione, come la web")
struct SchedaDallaFormazioneTests {
    /// Nella fixture, stile equilibrato 4-3-3: titolari 7575, 4510, 7318, 5578, 6523, 2404, 6822, 5680, 7525, 7537, 7183.
    static let attaccante = 7525
    static let altroAttaccante = 7537
    /// Titolare che gioca un anticipo già cominciato (`bloccati`).
    static let fermo = 7183
    /// Attaccante della rosa non titolare.
    static let riservaAttaccante = 1926
    /// Difensore titolare incerto (60%) e la sua riserva sicura (`incerti`).
    static let incerto = 6523
    static let riservaSicura = 6994
    /// In panchina, non titolare.
    static let panchinaro = 5307
    static let frase = "Preferito a Tavozzi: con lui la formazione fa più punti attesi (64,1 contro 63,9)."

    @Test("Si apre con la previsione già letta, il perché del titolare e «Sostituisci»")
    func contesto() async throws {
        let (vm, _) = try await caricata()
        let c = try #require(vm.contestoScheda(Self.attaccante))
        #expect(c.previsione.id == Self.attaccante)
        #expect(c.perche == Self.frase)
        #expect(c.sostituibile && !c.fermo)
    }

    @Test("Chi gioca un anticipo già cominciato non ha «Sostituisci» ma la frase; chi non è titolare nessuno dei due")
    func fermiEPanchina() async throws {
        let (vm, _) = try await caricata()
        let fermo = try #require(vm.contestoScheda(Self.fermo))
        #expect(fermo.fermo && !fermo.sostituibile)
        let panchina = try #require(vm.contestoScheda(Self.panchinaro))
        #expect(!panchina.fermo && !panchina.sostituibile)
        #expect(panchina.perche == nil)
        #expect(vm.contestoScheda(999_999) == nil, "un giocatore che la Formazione non ha: la scheda aspetta il server")
    }

    @Test("Senza la riga del server, il perché dell'incerto con la riserva sicura (campo `incerti`)")
    func percheDellIncerto() async throws {
        let (vm, f) = try await caricata()
        let riserva = try #require(f.schede?[String(Self.riservaSicura)])
        #expect(vm.percheTitolare(Self.incerto) == Catalogo.Formazione.incerto(p: "60%", riserva: riserva.nome))
    }

    @Test("Il perché del titolare solo sulla consigliata: non con un altro modulo né dopo un cambio (salvati da soli)")
    func soloSullaConsigliata() async throws {
        let (vm, _) = try await caricata()
        #expect(vm.percheTitolare(Self.attaccante) == Self.frase, "in campo la consigliata: vale")
        await vm.sostituisciTitolare(Self.altroAttaccante, con: Self.riservaAttaccante)
        #expect(vm.manuale != nil, "il cambio è in campo")
        #expect(vm.percheTitolare(Self.attaccante) == nil)
        let (altro, fa) = try await caricata()
        let altroModulo = altro.livello(fa)?.moduli.first(where: { $0.modulo != "4-3-3" })?.modulo
        let modulo = try #require(altroModulo)
        await altro.scegliModulo(modulo)
        #expect(altro.manuale != nil, "l'altro modulo è in campo")
        #expect(altro.percheTitolare(Self.attaccante) == nil)
    }

    @Test("A giornata chiusa niente perché e niente «Sostituisci»")
    func chiusa() async throws {
        let (vm, _) = try await caricata(chiusa: true)
        let c = try #require(vm.contestoScheda(Self.attaccante))
        #expect(c.perche == nil && !c.sostituibile && !c.fermo)
    }

    @Test("La formazione di un'altra squadra: il perché sì, «Sostituisci» no")
    func altraSquadra() async throws {
        let (vm, _) = try await caricata()
        vm.vediSquadra("Gli Amici")
        await vm.carica()                                   // la formazione dell'altra squadra (nella prova, gli stessi dati)
        let c = try #require(vm.contestoScheda(Self.attaccante))
        #expect(c.perche == Self.frase, "il perché del titolare vale anche per la consigliata di un'altra squadra")
        #expect(!c.sostituibile && !c.fermo)
        #expect(!vm.sostituibile(Self.attaccante))
        #expect(!vm.fermo(Self.fermo))
    }

    @Test("I sostituti: stesso ruolo, mai uno dei titolari in campo né chi è fermo")
    func sostituti() async throws {
        let (vm, f) = try await caricata()
        let uscente = try #require(f.schede?[String(Self.attaccante)])
        let ids = vm.sostituti(di: uscente, f).map(\.id)
        #expect(ids.contains(Self.riservaAttaccante))
        #expect(!ids.contains(Self.altroAttaccante) && !ids.contains(Self.fermo) && !ids.contains(Self.attaccante))
    }

    @Test("Sostituire dalla scheda parte dagli undici in campo, cambia solo quel titolare e si salva subito")
    func sostituisciTitolare() async throws {
        let (vm, f) = try await caricata()
        let prima = vm.vista(f).titolari.map(\.id)
        let attesa = prima.map { $0 == Self.attaccante ? Self.riservaAttaccante : $0 }
        let fatto = await vm.sostituisciTitolare(Self.attaccante, con: Self.riservaAttaccante)
        #expect(fatto)
        let dopo = try #require(vm.manuale)
        #expect(dopo == attesa)
        #expect(vm.vista(f).titolari.map(\.id) == attesa)
        #expect(vm.salvata?.titolari == attesa, "il cambio è la tua scelta salvata")
    }

    @Test("Un titolare fermo non si sostituisce, uno fermo non entra, un titolare non entra due volte, a giornata chiusa niente")
    func sostituzioniRifiutate() async throws {
        let (vm, _) = try await caricata()
        let esceFermo = await vm.sostituisciTitolare(Self.fermo, con: Self.riservaAttaccante)
        let entraTitolare = await vm.sostituisciTitolare(Self.attaccante, con: Self.altroAttaccante)
        #expect(!esceFermo && !entraTitolare)
        #expect(vm.manuale == nil && vm.salvata == nil)
        let (chiusa, _) = try await caricata(chiusa: true)
        let aGiornataChiusa = await chiusa.sostituisciTitolare(Self.attaccante, con: Self.riservaAttaccante)
        #expect(!aGiornataChiusa)
        #expect(chiusa.manuale == nil)
    }

    @Test("«Sostituisci» chiude la scheda e poi apre la scelta del sostituto, una volta sola")
    func sostituzioneInAttesa() async throws {
        let (vm, _) = try await caricata()
        vm.apriSostituzioneInAttesa()
        #expect(vm.daSostituire == nil, "senza una richiesta non si apre niente")
        vm.chiediSostituzione(Self.attaccante)
        #expect(vm.daSostituire == nil, "finché la scheda è aperta il foglio non parte")
        vm.apriSostituzioneInAttesa()
        #expect(vm.daSostituire?.id == Self.attaccante)
        vm.daSostituire = nil
        vm.apriSostituzioneInAttesa()
        #expect(vm.daSostituire == nil)
        vm.chiediSostituzione(Self.fermo)
        vm.apriSostituzioneInAttesa()
        #expect(vm.daSostituire == nil, "un titolare fermo non si sostituisce")
    }

    // MARK: aiuti

    /// La Formazione della fixture con, nel 4-3-3 dello stile equilibrato, una riga di `perche_scelta` per l'attaccante, un
    /// incerto con la riserva sicura e `bloccati`; `chiusa`: dopo la scadenza (`iniziata`). Nessuna scelta salvata.
    private func caricata(chiusa: Bool = false) async throws -> (FormazioneViewModel, Formazione) {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        var livelli = try #require(formazione["livelli"] as? [[String: Any]])
        let indiceEquilibrato = livelli.firstIndex(where: { ($0["rischio"] as? Int) == 0 })
        let equilibrato = try #require(indiceEquilibrato)
        var moduli = try #require(livelli[equilibrato]["moduli"] as? [[String: Any]])
        let indiceConsigliato = moduli.firstIndex(where: { ($0["modulo"] as? String) == "4-3-3" })
        let consigliato = try #require(indiceConsigliato)
        moduli[consigliato]["perche_scelta"] = [["titolare": Self.attaccante, "altro": Self.riservaAttaccante, "testo": Self.frase]]
        moduli[consigliato]["incerti"] = [["titolare": Self.incerto, "riserva": Self.riservaSicura]]
        livelli[equilibrato]["moduli"] = moduli
        formazione["livelli"] = livelli
        formazione["bloccati"] = [Self.fermo]
        if chiusa { formazione["iniziata"] = true }
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/formazione/valuta") {
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
