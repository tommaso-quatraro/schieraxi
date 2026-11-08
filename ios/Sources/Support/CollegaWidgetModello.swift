import Foundation
import Observation
import WidgetKit

/// Cosa fa «Collega il widget». La schermata si apre anche da `schieraxi://widget/collega`, un indirizzo che può aprire qualsiasi app
/// o pagina: per questo aprirla non fa niente da sola. Il token del widget, il collegamento automatico (App Group o Keychain
/// condiviso) e, solo se quello non va, la copia del codice negli appunti partono dal tocco dell'utente su «Collega» (#482).
@MainActor
@Observable
final class CollegaWidgetModello {
    enum Stato: Equatable {
        /// Appena aperta: aspetta il tocco su «Collega».
        case pronto
        case inCorso, automatico, copiato, senzaPermesso
        /// Con i dati di esempio il widget non si collega.
        case prova
    }

    /// Le operazioni vere; i test ne passano di finte.
    struct Servizi {
        /// L'indirizzo del server di adesso.
        var indirizzo: @MainActor () -> String
        /// Il token del widget per quell'indirizzo; con un account (secondo valore) lo chiede al server se manca.
        var token: @MainActor (_ indirizzo: String, _ conAccount: Bool) async -> String?
        /// Passa indirizzo e token al widget (App Group e Keychain condiviso): true se almeno uno dei due funziona.
        var canale: @MainActor () -> Bool
        var ricaricaWidget: @MainActor () -> Void

        static var veri: Servizi {
            Servizi(indirizzo: { IndirizzoServer.attuale },
                    token: { indirizzo, conAccount in
                        if conAccount, TokenWidget.leggi(server: indirizzo) == nil {
                            await TokenWidget.assicura(server: ServerCorrente.condiviso)
                        }
                        return TokenWidget.leggi(server: indirizzo)
                    },
                    canale: { Accesso.sincronizzaConIlWidget() },
                    ricaricaWidget: { WidgetCenter.shared.reloadAllTimelines() })
        }
    }

    private(set) var stato: Stato
    /// Cambia a ogni collegamento o copia riusciti: fa partire il feedback aptico.
    private(set) var riuscite = 0

    // costanti: l'osservazione non le segue
    private let demo: Bool
    private let appunti: any AppuntiCodice
    private let servizi: Servizi
    private let adesso: () -> Date

    /// `demo`: le fotografie del simulatore (nessun token, appunti intatti). `prova`: i dati di esempio.
    init(prova: Bool = ProvaEsempio.attiva, demo: Bool = Demo.daLancio, appunti: (any AppuntiCodice)? = nil,
         servizi: Servizi? = nil, adesso: @escaping () -> Date = { .now }) {
        stato = prova && !demo ? .prova : .pronto
        self.demo = demo
        self.appunti = appunti ?? AppuntiDiSistema()
        self.servizi = servizi ?? Servizi.veri
        self.adesso = adesso
    }

    /// Il tocco su «Collega» (e su «Copia di nuovo» o «Riprova»). Con un account si assicura il token del widget, poi prova il
    /// collegamento automatico; solo se non va mette il codice negli appunti di QUESTO telefono per `CollegamentoWidget.durataAppunti`.
    /// Se il lavoro viene annullato («Annulla» o foglio chiuso) mentre si aspetta il token, non collega e non copia niente.
    func collega(conAccount: Bool) async {
        guard stato != .inCorso, stato != .prova else { return }
        if demo {
            stato = .copiato
            riuscite += 1
            return
        }
        stato = .inCorso
        let indirizzo = servizi.indirizzo()
        let token = await servizi.token(indirizzo, conAccount)
        // annullato mentre il server rispondeva: niente collegamento e niente appunti
        if Task.isCancelled {
            stato = .pronto
            return
        }
        // con gli account serve il token: un codice senza farebbe dire al widget di nuovo «Tocca per collegare»
        if conAccount, token == nil {
            stato = .senzaPermesso
            return
        }
        // collegamento automatico: niente da copiare, il widget si ricarica e trova tutto
        if CollegamentoWidget.automatico(canale: servizi.canale(), conAccount: conAccount, haToken: token != nil) {
            servizi.ricaricaWidget()
            stato = .automatico
            riuscite += 1
            return
        }
        appunti.copia(CodiceWidget.crea(indirizzo: indirizzo, token: token), scade: adesso().addingTimeInterval(CollegamentoWidget.durataAppunti))
        stato = .copiato
        riuscite += 1
    }
}
