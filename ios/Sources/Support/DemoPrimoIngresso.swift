import Foundation

/// Solo per le fotografie del simulatore: due momenti del primo ingresso di un amico nuovo (#880) che con i dati della demo non si
/// vedrebbero, perché la lega di prova ha già le rose e la guida ha passi da fare.
/// - `guida-pronta`: la configurazione guidata su «Tutto pronto», con la frase dei punteggi più comuni e «Vai alla Formazione»
///   (il server finto ricorda tutti i passi fatti);
/// - `lega-importa-prima`: Importa le rose al primo caricamento (il server finto dice che le rose non ci sono ancora).
extension FinteServer {
    static func demoPrimoIngresso(_ schermata: String?) -> FinteServer? {
        var finto = FinteServer.demo
        switch schermata {
        case "guida-pronta":
            finto.risposte["/api/primo-avvio"] = #"""
            {"primo_avvio": {"fatti": ["rose", "squadra", "stemma", "widget", "avvisi"], "saltati": [], "chiuso": false},
             "passi": ["server", "accesso", "rose", "squadra", "stemma", "pwa", "widget", "avvisi"]}
            """#
            finto.indirizzoFinto = "https://finto-guida-pronta.invalid"
        case "lega-importa-prima":
            finto.risposte["/api/stato"] = #"{"rose_importate": false, "mia_squadra": null}"#
            finto.errori["/api/squadre"] = "Nessuna rosa importata"
            finto.indirizzoFinto = "https://finto-prime-rose.invalid"   // niente copie salvate della lega di prova
        default:
            return nil
        }
        return finto
    }
}
