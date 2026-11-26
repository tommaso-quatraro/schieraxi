import Foundation
import Testing
@testable import Schieraxi

/// La foto `giornate-confronto` (#842): Giornate › Dettagli con la voce «la consigliata contro la tua» a video e un diario della demo
/// in cui la consigliata ha fatto 1,0 punti in più (la demo di sempre ne ha 12,0, legati alle giornate, a «Le tue scelte» e ai widget,
/// e lì restano). Così una foto mostra «1,0 punti», il plurale scelto sul numero come è scritto.
struct DemoFotoConfrontoTests {

    private func pagina() async throws -> PaginaGiornate {
        let server = try #require(FinteServer.demoFase("giornate-confronto"), "la demo «giornate-confronto» non esiste")
        let d: DiarioRisposta = try Decodifica.decodifica(try await server.richiesta("GET", "/api/diario", corpo: nil))
        return PaginaGiornate(d)
    }

    @Test("Nella demo della foto la consigliata ha fatto 1,0 punti in più, e la pagina lo scrive al plurale")
    func confrontoAUnPunto() async throws {
        let p = try await pagina()
        let frase = try #require(p.dettagli?.confronto?.frase, "la voce del confronto deve esserci")
        #expect(frase.hasSuffix("Seguendo sempre la consigliata avresti fatto 1,0 punti in più."), "\(frase)")
    }

    @Test("La demo della foto ha la sua copia salvata: il diario con 1,0 non finisce nelle altre foto")
    func copiaSalvataSua() throws {
        let server = try #require(FinteServer.demoFase("giornate-confronto"))
        #expect(server.indirizzoFinto != FinteServer.demo.indirizzoFinto)
    }

    /// La foto porta in fondo allo schermo il bordo basso dei Dettagli (la voce del confronto sta dentro quella riga e la lista non la
    /// trova): sotto il confronto non devono esserci il grafico, l'andamento, la riga su tutta la Serie A e le note, e la voce della
    /// squadra dev'essere corta («–», senza numeri), che anche con il testo grande la fine del confronto resti a video (#842, foto
    /// della corsa 44826938210).
    @Test("Sotto il confronto, nei Dettagli della foto, resta solo la voce corta dei punti della squadra")
    func sottoIlConfrontoSoloLaSquadra() async throws {
        let p = try await pagina()
        let t = try #require(p.dettagli)
        let confronto = try #require(t.confronto, "la voce del confronto deve esserci")
        #expect(t.voci.suffix(2).map(\.etichetta) == [confronto.etichetta, t.squadra.etichetta])
        #expect(t.squadra.numero == "–" && t.squadra.frase == Catalogo.Diario.qpFvVuoto, "\(t.squadra)")
        #expect(t.barre.count < 2, "niente grafico")
        #expect(t.righe.isEmpty, "niente andamento")
        #expect(t.serieA == nil && t.notaRicostruiti == nil && t.nota == nil)
        #expect(!p.righe.isEmpty, "la foto scorre alla prima giornata: deve esserci")
    }

    @MainActor
    @Test("La foto apre «Dettagli», come `giornate-dettagli`")
    func apreIDettagli() {
        let vm = GiornateViewModel(server: FinteServer.demo)
        vm.preparaFoto("giornate-confronto")
        #expect(vm.dettagliAperti)
    }

    /// La riga sotto il titolo (`GET /api/stato`, #863) arriva dopo le giornate e compare in cima alla lista: comparendo la riporta in
    /// cima. La foto scorreva appena c'erano i Dettagli e, quando la riga arrivava dopo, lo scorrimento andava perso e la voce restava
    /// sotto lo schermo (test `FotoUITests`, 3 corse su 6 il 25/11; nel registro della corsa 45668942279 la lista scorre a 284, poi
    /// arriva la riga e torna a −116, la cima). Adesso la foto aspetta la cima completa: Dettagli e riga.
    @MainActor
    @Test("La foto aspetta la cima della pagina completa: i Dettagli e anche la riga sotto il titolo")
    func cimaCompletaConDettagliERiga() async throws {
        let server = try #require(FinteServer.demoFase("giornate-confronto"))
        let vm = GiornateViewModel(server: server)
        #expect(!vm.cimaCompleta, "senza dati")
        await vm.caricatore.ricarica()
        #expect(vm.pagina?.dettagli != nil, "le giornate con i Dettagli ci sono")
        #expect(!vm.cimaCompleta, "manca la riga sotto il titolo: comparendo riporterebbe la lista in cima")
        await vm.info.ricarica()
        #expect(vm.rigaStato != nil)
        #expect(vm.cimaCompleta)
    }

    /// Se `/api/stato` non risponde la riga c'è lo stesso («Server non raggiungibile»): la foto non aspetta per sempre.
    @MainActor
    @Test("Senza risposta da `/api/stato` la cima è completa lo stesso, con «Server non raggiungibile»")
    func cimaCompletaSenzaStato() async throws {
        var server = try #require(FinteServer.demoFase("giornate-confronto"))
        server.errori = ["/api/stato": "server spento"]
        server.indirizzoFinto = "https://finto-confronto-senza-stato.invalid"   // una copia salvata sua
        let vm = GiornateViewModel(server: server)
        await vm.carica()
        #expect(vm.rigaStato?.testo == Catalogo.Testata.offline)
        #expect(vm.cimaCompleta)
    }
}
