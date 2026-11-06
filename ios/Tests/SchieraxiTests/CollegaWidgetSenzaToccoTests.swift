import Foundation
import Testing
import UIKit
@testable import Schieraxi

// Issue #482. «Collega il widget» si apre anche da `schieraxi://widget/collega`, un indirizzo che può aprire qualsiasi app o pagina:
// aprire la schermata non fa niente da solo. Il token del widget, il collegamento automatico e la copia del codice negli appunti
// partono solo dal tocco su «Collega»; negli appunti il codice resta solo su questo telefono e per poco.
// Indirizzi e token finti (.invalid); ogni test ha i suoi finti, niente stato in comune.

/// Gli appunti finti: ricordano cosa ci si mette e fino a quando.
@MainActor
final class AppuntiFinti: AppuntiCodice {
    private(set) var copie: [(codice: String, scade: Date)] = []

    func copia(_ codice: String, scade: Date) {
        copie.append((codice, scade))
    }
}

/// I servizi del collegamento (token del widget, collegamento automatico, ricarica dei widget) finti, con il conto delle chiamate.
@MainActor
final class ServiziCollegamentoFinti {
    let token: String?
    let canale: Bool
    private(set) var richiesteToken = 0
    private(set) var collegamenti = 0
    private(set) var ricariche = 0

    init(token: String? = "fw_tokenDiProva123456", canale: Bool = false) {
        self.token = token
        self.canale = canale
    }

    var servizi: CollegaWidgetModello.Servizi {
        CollegaWidgetModello.Servizi(
            indirizzo: { "https://esempio.invalid" },
            token: { [self] _, _ in
                richiesteToken += 1
                return token
            },
            canale: { [self] in
                collegamenti += 1
                return canale
            },
            ricaricaWidget: { [self] in ricariche += 1 })
    }
}

@Suite("Collega il widget: niente negli appunti senza un tocco (#482)")
@MainActor
struct CollegaWidgetSenzaToccoTests {
    /// L'ora dei test: mai l'orologio vero.
    let adesso = Date(timeIntervalSince1970: 1_800_000_000)

    private func modello(_ servizi: ServiziCollegamentoFinti, _ appunti: AppuntiFinti,
                         demo: Bool = false, prova: Bool = false) -> CollegaWidgetModello {
        let ora = adesso
        return CollegaWidgetModello(prova: prova, demo: demo, appunti: appunti, servizi: servizi.servizi, adesso: { ora })
    }

    @Test("Aperta da un indirizzo, senza tocco: niente appunti, niente token, niente collegamento")
    func apertaSenzaTocco() {
        let servizi = ServiziCollegamentoFinti()
        let appunti = AppuntiFinti()
        let m = modello(servizi, appunti)
        #expect(m.stato == .pronto)
        #expect(appunti.copie.isEmpty)
        #expect(servizi.richiesteToken == 0)
        #expect(servizi.collegamenti == 0)
        #expect(servizi.ricariche == 0)
    }

    @Test("Il tocco su «Collega» senza collegamento automatico: il codice negli appunti, al massimo per 2 minuti")
    func toccoCopiaIlCodice() async throws {
        let servizi = ServiziCollegamentoFinti(canale: false)
        let appunti = AppuntiFinti()
        let m = modello(servizi, appunti)
        await m.collega(conAccount: true)
        #expect(m.stato == .copiato)
        #expect(m.riuscite == 1)
        #expect(appunti.copie.count == 1)
        let copia = try #require(appunti.copie.first)
        #expect(CodiceWidget.leggi(copia.codice) == CodiceWidget.Contenuto(i: "https://esempio.invalid", t: "fw_tokenDiProva123456"))
        #expect(copia.scade == adesso.addingTimeInterval(CollegamentoWidget.durataAppunti))
        #expect(CollegamentoWidget.durataAppunti <= 2 * 60, "negli appunti il codice resta poco")
    }

    @Test("Con il collegamento automatico niente appunti: i widget si ricaricano")
    func automaticoSenzaAppunti() async {
        let servizi = ServiziCollegamentoFinti(canale: true)
        let appunti = AppuntiFinti()
        let m = modello(servizi, appunti)
        await m.collega(conAccount: true)
        #expect(m.stato == .automatico)
        #expect(appunti.copie.isEmpty)
        #expect(servizi.ricariche == 1)
    }

    @Test("Con un account ma senza il token del widget: niente appunti")
    func senzaTokenNienteAppunti() async {
        let servizi = ServiziCollegamentoFinti(token: nil, canale: false)
        let appunti = AppuntiFinti()
        let m = modello(servizi, appunti)
        await m.collega(conAccount: true)
        #expect(m.stato == .senzaPermesso)
        #expect(appunti.copie.isEmpty)
        #expect(servizi.collegamenti == 0)
    }

    @Test("Con i dati di esempio il widget non si collega e gli appunti restano intatti")
    func provaNienteAppunti() async {
        let servizi = ServiziCollegamentoFinti()
        let appunti = AppuntiFinti()
        let m = modello(servizi, appunti, prova: true)
        #expect(m.stato == .prova)
        await m.collega(conAccount: true)
        #expect(m.stato == .prova)
        #expect(appunti.copie.isEmpty)
        #expect(servizi.richiesteToken == 0)
    }

    @Test("Nelle fotografie (demo) il tocco dice «Codice copiato» senza toccare gli appunti")
    func demoNienteAppunti() async {
        let servizi = ServiziCollegamentoFinti()
        let appunti = AppuntiFinti()
        let m = modello(servizi, appunti, demo: true)
        #expect(m.stato == .pronto)
        await m.collega(conAccount: true)
        #expect(m.stato == .copiato)
        #expect(appunti.copie.isEmpty)
        #expect(servizi.richiesteToken == 0)
    }

    @Test("Gli appunti veri: solo su questo telefono (niente Appunti universali) e con la scadenza")
    func opzioniDegliAppunti() {
        let opzioni = AppuntiDiSistema.opzioni(scade: adesso)
        #expect(opzioni[.localOnly] as? Bool == true)
        #expect(opzioni[.expirationDate] as? Date == adesso)
    }
}
