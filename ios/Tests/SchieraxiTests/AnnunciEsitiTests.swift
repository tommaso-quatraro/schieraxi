import Foundation
import Testing
@testable import Schieraxi

/// L'esito di un'azione che compare lontano dal pulsante toccato si fa leggere a VoiceOver (ricerca sull'accessibilità del 27/11):
/// dopo un cambio della Formazione la riga dello stato, come la riga `role="status"` della web (`rigaStato` di `mostraFormazione`);
/// l'errore della scelta sul rinvio e quello di «Questa è la mia». Prima cambiava solo lo schermo (con una vibrazione), e con
/// «Torna alla consigliata» spariva proprio il pulsante su cui stava VoiceOver. Dati inventati (fixture).
@MainActor
@Suite("VoiceOver legge l'esito di un'azione")
struct AnnunciEsitiTests {
    // MARK: Formazione

    @Test("Dopo un cambio di titolare VoiceOver legge la riga dello stato nuova, come la riga «status» della web")
    func cambio() async throws {
        let srv = try SalvataggioAutomaticoTests.server()
        let vm = FormazioneViewModel(server: srv, promemoria: {})
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        await vm.carica()
        let f = try #require(vm.formazione)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        #expect(await vm.sostituisciTitolare(esce, con: entra))
        #expect(annunci == [StatoScelta.cambiata(diversi: 1, punti: 20.0 - 71.1).voce])
        #expect(annunci == [vm.statoScelta.voce], "la stessa frase che VoiceOver legge sulla riga")
    }

    @Test("Un altro modulo, poi «Torna alla consigliata»: ogni volta VoiceOver legge la riga nuova, anche se il pulsante sparisce")
    func moduloETornaAllaConsigliata() async throws {
        let srv = try SalvataggioAutomaticoTests.server()
        let vm = FormazioneViewModel(server: srv, promemoria: {})
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        await vm.carica()
        let f = try #require(vm.formazione)
        let consigliato = try #require(vm.consigliato(f))
        let altro = try #require(vm.moduli(f).first { $0.modulo != consigliato.modulo })
        await vm.scegliModulo(altro.modulo)
        #expect(vm.statoScelta.conTorna, "in campo la tua: c'è «Torna alla consigliata»")
        #expect(annunci == [vm.statoScelta.voce])
        await vm.tornaAllaConsigliata()
        #expect(vm.statoScelta == .consigliata)
        #expect(annunci.count == 2)
        #expect(annunci.last == StatoScelta.consigliata.voce)
    }

    @Test("La spunta «L'ho messa» non si annuncia: la legge già l'interruttore e la riga dello stato non cambia")
    func spuntaSenzaAnnuncio() async throws {
        let srv = try SalvataggioAutomaticoTests.server()
        let vm = FormazioneViewModel(server: srv, promemoria: {})
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        await vm.carica()
        await vm.segnaMessa(true)
        #expect(vm.messa)
        #expect(annunci.isEmpty)
    }

    @Test("Un cambio che il server rifiuta non annuncia la riga dello stato: l'errore lo dice l'avviso sotto il campo")
    func rifiutoSenzaRigaNuova() async throws {
        let srv = try SalvataggioAutomaticoTests.server(conflitto: true)
        let vm = FormazioneViewModel(server: srv, promemoria: {})
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        await vm.carica()
        let f = try #require(vm.formazione)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(vm.messaggio != nil, "l'avviso c'è, e la Formazione lo fa già leggere")
        #expect(annunci.isEmpty)
    }

    // MARK: partite rinviate

    @Test("La scelta sul rinvio non si salva: VoiceOver legge il perché, anche la seconda volta con lo stesso errore")
    func rinvioNonSalvato() async throws {
        let vm = OggiViewModel(server: ServerDiProva.chePrecipita(), conPromemoria: false)
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        let scelta = SceltaRinvio(giornata: 10, modo: ModoRinvio.aspetta, predefinito: ModoRinvio.aspetta)
        await vm.cambiaRinvio(scelta, modo: ModoRinvio.senzaVoto)
        await vm.cambiaRinvio(scelta, modo: ModoRinvio.senzaVoto)
        let errore = try #require(vm.erroreRinvio)
        #expect(annunci == [errore, errore])
    }

    // MARK: la tua squadra

    @Test("«Questa è la mia» non riesce: VoiceOver legge il perché")
    func squadraNonScelta() async throws {
        let squadra = SquadraDaScegliere(server: ServerDiProva.chePrecipita())
        var annunci: [String] = []
        squadra.annuncia = { annunci.append($0) }
        let errore = try #require(await squadra.scegli("Borgo Alto"))
        #expect(annunci == [errore])
    }
}
