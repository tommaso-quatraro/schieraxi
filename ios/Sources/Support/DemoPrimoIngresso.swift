import Foundation

/// Solo per le fotografie del simulatore: due momenti del primo ingresso di un amico nuovo (#880) che con i dati della demo non si
/// vedrebbero, perché la lega di prova ha già le rose e la guida ha passi da fare.
/// - `guida-pronta`: la configurazione guidata su «Tutto pronto», con la frase dei punteggi più comuni e «Vai alla Formazione»
///   (il server finto ricorda tutti i passi fatti);
/// - `lega-importa-prima`: Importa le rose al primo caricamento (il server finto dice che le rose non ci sono ancora);
/// - `formazione-senza-squadra` e `giornate-senza-server` (collaudo del 26/11): la Formazione con le rose ma senza la tua squadra, e
///   Giornate col server spento con le copie salvate.
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
        case "formazione-senza-squadra":
            // rose salvate, la tua squadra no (collaudo del 26/11): lo stato lo dice, Oggi e Formazione rispondono 400 come il server
            finto.risposte["/api/stato"] = #"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "rose_importate": true, "mia_squadra": null}"#
            finto.errori["/api/oggi"] = Catalogo.Err.indicaSquadra
            finto.errori["/api/formazione"] = Catalogo.Err.indicaSquadra
            finto.indirizzoFinto = "https://finto-senza-squadra.invalid"
        case "giornate-senza-server":
            // il server spento dopo una ricarica (collaudo del 26/11): giornate e stato dalle copie salvate in una lettura di prima;
            // la riga sotto il titolo dice «Server non raggiungibile» e poi giornata, squadra e ora della copia. La coda della cache
            // scrive le copie prima di ogni lettura della pagina.
            finto.indirizzoFinto = "https://finto-giornate-senza-server.invalid"
            for percorso in ["/api/stato", "/api/diario"] {
                if let testo = finto.risposte[percorso] { Cache.salva(Data(testo.utf8), percorso, indirizzo: finto.indirizzoFinto) }
                finto.fallimenti[percorso] = .senzaRete
            }
        default:
            return nil
        }
        return finto
    }
}
