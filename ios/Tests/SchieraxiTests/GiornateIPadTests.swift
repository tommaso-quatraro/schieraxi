import Foundation
import Testing
@testable import Schieraxi

/// Giornate sull'iPad (#896): l'elenco a sinistra e a destra la giornata scelta oppure i numeri di «Dettagli», che prima si
/// aprivano dentro la colonna stretta dell'elenco lasciando vuota la metà destra. Sul telefono non cambia niente: «Dettagli» si
/// apre sotto la sua riga. Dati inventati (`diario-giornate.json`).
@MainActor
@Suite("Giornate sull'iPad: a destra la giornata scelta o i Dettagli")
struct GiornateIPadTests {
    private func pagina() throws -> PaginaGiornate {
        PaginaGiornate(try Fixture.decodifica("diario-giornate") as DiarioRisposta)
    }

    @Test("Senza una scelta a destra c'è la giornata più recente")
    func piuRecente() throws {
        let p = try pagina()
        let prima = try #require(p.righe.first?.id)
        #expect(p.aDestra(scelta: nil) == .giornata(prima))
        #expect(p.aDestra(scelta: nil).id == prima)
    }

    @Test("La giornata toccata va a destra; una che non c'è più lascia il posto alla più recente")
    func giornataScelta() throws {
        let p = try pagina()
        let ultima = try #require(p.righe.last?.id)
        #expect(p.aDestra(scelta: ultima) == .giornata(ultima))
        let prima = try #require(p.righe.first?.id)
        #expect(p.aDestra(scelta: "2019-20-1") == .giornata(prima))
    }

    @Test("«Dettagli» toccato: a destra i numeri, e nell'elenco è la sua riga a risultare scelta")
    func dettagli() throws {
        let p = try pagina()
        #expect(p.dettagli != nil)
        #expect(p.aDestra(scelta: PaginaGiornate.idDettagli) == .dettagli)
        #expect(p.aDestra(scelta: PaginaGiornate.idDettagli).id == PaginaGiornate.idDettagli)
    }

    @Test("L'identità di «Dettagli» non può essere quella di una giornata")
    func idDettagliDiverso() throws {
        let p = try pagina()
        #expect(!p.righe.contains { $0.id == PaginaGiornate.idDettagli })
    }

    @Test("Senza i numeri di «Dettagli» a destra resta la giornata più recente; senza giornate niente")
    func senzaDettagli() throws {
        let senza = PaginaGiornate(try Decodifica.decodifica(Data(#"{"giornate": []}"#.utf8)))
        #expect(senza.aDestra(scelta: PaginaGiornate.idDettagli) == .niente)
        #expect(senza.aDestra(scelta: nil) == .niente)
        #expect(senza.aDestra(scelta: nil).id == nil)
        let soloDettagli = PaginaGiornate(try Decodifica.decodifica(
            Data(#"{"giornate": [], "precisione": {"giornate": 2, "fantavoto": null}}"#.utf8)))
        #expect(soloDettagli.aDestra(scelta: nil) == .dettagli, "senza giornate ma con i Dettagli: a destra i Dettagli")
    }

    @Test("La foto `giornate-dettagli` apre i Dettagli anche a destra; «Com'è andata» porta poi a destra la sua giornata")
    func fotoEPoiComeAndata() async throws {
        let json = try Fixture.testo("diario-giornate")
        let vm = GiornateViewModel(server: ServerDiProva { _, _, _ in Data(json.utf8) })
        vm.preparaFoto("giornate-dettagli")
        #expect(vm.dettagliAperti, "sul telefono «Dettagli» aperto sotto la sua riga, come prima")
        #expect(vm.scelta == PaginaGiornate.idDettagli)
        await vm.carica()
        #expect(vm.pagina?.aDestra(scelta: vm.scelta) == .dettagli)
        vm.apri(giornata: 9)
        #expect(vm.scelta == "2026-27-9")
        #expect(vm.pagina?.aDestra(scelta: vm.scelta) == .giornata("2026-27-9"))
    }

    // MARK: la riga scelta (#919)

    /// Contrasto WCAG fra due colori pieni (0xRRGGBB).
    private func contrasto(_ a: UInt32, _ b: UInt32) -> Double {
        func luminanza(_ n: UInt32) -> Double {
            func lineare(_ v: UInt32) -> Double {
                let x = Double(v) / 255
                return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4)
            }
            return 0.2126 * lineare((n >> 16) & 0xff) + 0.7152 * lineare((n >> 8) & 0xff) + 0.0722 * lineare(n & 0xff)
        }
        let (x, y) = (luminanza(a), luminanza(b))
        return (max(x, y) + 0.05) / (min(x, y) + 0.05)
    }

    @Test("La riga scelta a sinistra ha un grigio suo: nomi, punti e testi grigi restano sopra 4,5:1 in chiaro e in scuro")
    func rigaSceltaLeggibile() {
        // prima la selezione di iOS riempiva la riga del colore principale e i testi grigi sparivano (foto della corsa 45760638734)
        #expect(contrasto(Tema.secondarioChiaro, Tema.rigaSceltaChiaro) >= 4.5, "testo grigio, chiaro")
        #expect(contrasto(Tema.secondarioScuro, Tema.rigaSceltaScuro) >= 4.5, "testo grigio, scuro")
        #expect(contrasto(0x000000, Tema.rigaSceltaChiaro) >= 4.5, "nome e punti, chiaro")
        #expect(contrasto(0xFFFFFF, Tema.rigaSceltaScuro) >= 4.5, "nome e punti, scuro")
    }

    @Test("La riga scelta si distingue dalle altre righe della scheda")
    func rigaSceltaSiVede() {
        // le schede: bianco in chiaro, #1C1C1E in scuro (`Color.sfondoScheda`)
        #expect(contrasto(0xFFFFFF, Tema.rigaSceltaChiaro) >= 1.4)
        #expect(contrasto(0x1C1C1E, Tema.rigaSceltaScuro) >= 1.4)
    }
}
