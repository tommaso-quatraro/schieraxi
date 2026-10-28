import SwiftUI

/// Modalità demo: se l'app parte con l'argomento di lancio `-DEMO` usa `FinteServer.demo` (dati finti, nessuna rete),
/// non chiede permessi, non programma notifiche e non registra lavori in background.
/// Serve a fotografare l'app nel simulatore di un Mac di GitHub (workflow `screenshot.yml`): nel comportamento normale non cambia niente.
///
/// Argomenti di lancio opzionali (solo con `-DEMO`):
/// - `-DEMO_SCHERMATA <nome>`: apre subito una schermata (vedi `applica`), perché dal simulatore non si può toccare lo schermo.
/// - `-DEMO_FONDO 1`: le schermate lunghe partono scorse in fondo (iOS 17 o più).
/// - `-DEMO_ORIENTAMENTO orizzontale`: chiede l'orientamento orizzontale.
enum Demo {
    static let attivo: Bool = ProcessInfo.processInfo.arguments.contains("-DEMO")

    /// Il valore che segue `-NOME` negli argomenti di lancio.
    static func argomento(_ nome: String) -> String? {
        let tutti = ProcessInfo.processInfo.arguments
        guard let i = tutti.firstIndex(of: "-" + nome), i + 1 < tutti.count else { return nil }
        return tutti[i + 1]
    }

    static var schermata: String? { attivo ? argomento("DEMO_SCHERMATA") : nil }

    /// Il server di partenza dell'app: quello finto in demo, quello vero altrimenti.
    static func serverPredefinito() -> any ServerClient {
        if attivo { return FinteServer.demo }
        return ServerHTTP()
    }
}

extension View {
    /// Solo in demo con `-DEMO_FONDO`: la schermata parte scorsa in fondo, per vedere anche la parte sotto la piega.
    @ViewBuilder
    func demoInFondo() -> some View {
        if Demo.attivo, Demo.argomento("DEMO_FONDO") != nil, #available(iOS 17, *) {
            self.defaultScrollAnchor(.bottom)
        } else {
            self
        }
    }
}

@MainActor
extension Demo {
    private static var applicata = false

    /// Porta l'app sulla schermata chiesta con `-DEMO_SCHERMATA`. Chiamata una volta sola all'avvio.
    static func applica(nav: Navigazione, modello: AppModel) {
        guard attivo, !applicata else { return }
        applicata = true

        if argomento("DEMO_ORIENTAMENTO") == "orizzontale" {
            let scena = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first
            scena?.requestGeometryUpdate(.iOS(interfaceOrientations: .landscape))
        }

        guard let nome = argomento("DEMO_SCHERMATA") else { return }
        switch nome {
        case "oggi":
            nav.sezione = .oggi

        case "formazione":
            nav.sezione = .formazione
        case "formazione-manuale":
            nav.sezione = .formazione
            Task {
                await modello.formazione.carica()
                try? await Task.sleep(nanoseconds: 400_000_000)
                if let f = modello.formazione.formazione { modello.formazione.iniziaModificaManuale(f) }
            }

        case "mercato", "mercato-consigliati":
            nav.sezione = .mercato
            modello.mercato.sezione = .consigliati
        case "mercato-classifica":
            nav.sezione = .mercato
            modello.mercato.sezione = .classifica
        case "mercato-calendario":
            nav.sezione = .mercato
            modello.mercato.sezione = .calendario
        case "mercato-osservati":
            nav.sezione = .mercato
            modello.mercato.sezione = .osservati
        case "mercato-cerca":
            nav.sezione = .mercato
            modello.mercato.sezione = .cerca
            modello.mercato.testoRicerca = "ma"
        case "giocatore":
            nav.vai(a: .giocatore(203))

        case "scambi":
            nav.sezione = .scambi
        case "scambi-dettaglio":
            nav.sezione = .scambi
            Task {
                await modello.scambi.caricaProposte()
                try? await Task.sleep(nanoseconds: 800_000_000)
                modello.scambi.selezionata = modello.scambi.proposte.dato?.proposte.first(where: { $0.`do`.count > 1 })
                    ?? modello.scambi.proposte.dato?.proposte.first
            }
        case "scambi-analizza":
            nav.sezione = .scambi
            modello.scambi.percorso = [.analizza]

        case "lega":
            nav.sezione = .lega
        case "lega-squadre":
            apriLega(nav, modello, [.squadre])
        case "lega-rosa":
            apriLega(nav, modello, [.squadre, .rosa("Gli Amici del Bar Sport Centrale")])
        case "lega-regole":
            apriLega(nav, modello, [.regole])
        case "lega-asta":
            apriLega(nav, modello, [.asta])
        case "lega-stato":
            apriLega(nav, modello, [.stato])
        case "lega-crediti":
            apriLega(nav, modello, [.crediti])
        case "lega-avvisi":
            apriLega(nav, modello, [.avvisi])
        case "lega-novita":
            apriLega(nav, modello, [.novita])
        case "lega-importa":
            apriLega(nav, modello, [.importa])
        default:
            break
        }
    }

    private static func apriLega(_ nav: Navigazione, _ modello: AppModel, _ pagine: [PaginaLega]) {
        nav.sezione = .lega
        modello.lega.percorso = pagine
    }
}
