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

    /// La foto scorre alla prima giornata, sotto i Dettagli: subito sopra devono esserci la voce dei punti della squadra e il
    /// confronto, senza il grafico, l'andamento, la riga su tutta la Serie A e le note, che lo spingerebbero fuori dallo schermo.
    @Test("Sotto il confronto, nei Dettagli della foto, resta solo la voce dei punti della squadra")
    func sottoIlConfrontoSoloLaSquadra() async throws {
        let p = try await pagina()
        let t = try #require(p.dettagli)
        let confronto = try #require(t.confronto, "la voce del confronto deve esserci")
        #expect(t.voci.suffix(2).map(\.etichetta) == [confronto.etichetta, t.squadra.etichetta])
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
}
