import Foundation
import Testing
@testable import Schieraxi

/// Il menu del modulo dopo un cambio fatto a mano, come `voci` di `mostraFormazione` della web (#978): se gli 11 in campo non sono
/// quelli di una formazione calcolata dal server (un cambio a mano, anche nello stesso modulo), in cima c'è la tua formazione con
/// i suoi punti, quelli del server («4-3-3 · 20,0 punti · la tua», `formazione.opzione_tua`), con la spunta; scegliendo il
/// consigliato si torna alla consigliata. Prima la spunta stava sulla voce del server con lo stesso modulo e altri punti
/// («4-3-3 · 71,1 punti · consigliato») e la tua non c'era. Dati inventati (fixture; il server di prova valuta ogni cambio
/// «4-3-3», 20,0 punti).
@MainActor
@Suite("Formazione: il menu del modulo con la tua formazione, come la web")
struct MenuModuloTuaTests {
    @Test("Con la consigliata in campo: le voci del server, la spunta sul consigliato, niente «la tua»")
    func conLaConsigliata() async throws {
        let (vm, f, _) = try await caricata()
        let consigliato = try #require(vm.consigliato(f))
        let voci = vm.vociModulo(f)
        #expect(voci.map(\.modulo) == vm.moduli(f).map { Optional($0.modulo) })
        #expect(voci.map(\.etichetta) == vm.moduli(f).map { vm.etichettaModulo($0, f) })
        #expect(voci.filter(\.scelta).map(\.modulo) == [consigliato.modulo])
    }

    @Test("Dopo una sostituzione nello stesso modulo: in cima «4-3-3 · 20,0 punti · la tua» con la spunta, le altre senza")
    func dopoUnaSostituzione() async throws {
        let (vm, f, _) = try await caricata()
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let fatto = await vm.sostituisciTitolare(esce, con: entra)
        #expect(fatto)
        let v = vm.vista(f)
        #expect(v.modulo == vm.consigliato(f)?.modulo, "il cambio resta nel modulo della consigliata: è il caso del difetto")
        let voci = vm.vociModulo(f)
        let tua = try #require(voci.first)
        #expect(tua.modulo == nil, "la tua non è una formazione del server: sceglierla non cambia niente")
        #expect(tua.etichetta == Catalogo.Formazione.opzioneTua(modulo: v.modulo, punti: "20,0"))
        #expect(tua.etichetta == "4-3-3 · 20,0 punti · la tua")
        #expect(tua.scelta)
        #expect(voci.dropFirst().allSatisfy { !$0.scelta }, "la spunta non sta più sulla voce del server con lo stesso modulo")
        #expect(voci.count == vm.moduli(f).count + 1)
    }

    @Test("Dalla tua, il consigliato riporta alla consigliata (`DELETE /api/scelta`) e la voce «la tua» sparisce")
    func tornaAllaConsigliata() async throws {
        let (vm, f, srv) = try await caricata()
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        let consigliato = try #require(vm.consigliato(f))
        let voce = try #require(vm.vociModulo(f).first { $0.modulo == consigliato.modulo })
        let modulo = try #require(voce.modulo)
        await vm.scegliModulo(modulo)
        #expect(srv.quante("DELETE /api/scelta?giornata=9") == 1)
        let voci = vm.vociModulo(f)
        #expect(voci.count == vm.moduli(f).count && voci.allSatisfy { $0.modulo != nil })
        #expect(voci.filter(\.scelta).map(\.modulo) == [consigliato.modulo])
    }

    @Test("Un'altra formazione del server scelta dal menu: niente «la tua», la spunta sulla sua voce")
    func altroModuloDelServer() async throws {
        let (vm, f, _) = try await caricata()
        let altro = try #require(vm.moduli(f).first { $0.modulo != vm.consigliato(f)?.modulo })
        await vm.scegliModulo(altro.modulo)
        let voci = vm.vociModulo(f)
        #expect(voci.count == vm.moduli(f).count)
        #expect(voci.filter(\.scelta).map(\.modulo) == [altro.modulo])
    }

    @Test("La formazione di un'altra squadra: solo le voci del server, la spunta sul modulo guardato")
    func altraSquadra() async throws {
        let srv = try SalvataggioAutomaticoTests.server()
        let vm = FormazioneViewModel(server: srv)
        vm.vediSquadra("Gli Amici")
        await vm.carica()
        let f = try #require(vm.formazione)
        let altro = try #require(vm.moduli(f).first { $0.modulo != vm.consigliato(f)?.modulo })
        await vm.scegliModulo(altro.modulo)
        let voci = vm.vociModulo(f)
        #expect(voci.count == vm.moduli(f).count && voci.allSatisfy { $0.modulo != nil })
        #expect(voci.filter(\.scelta).map(\.modulo) == [altro.modulo])
    }

    // MARK: aiuti

    private func caricata() async throws -> (FormazioneViewModel, Formazione, ServerDiProva) {
        let srv = try SalvataggioAutomaticoTests.server()
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        return (vm, try #require(vm.formazione), srv)
    }
}
