import Foundation

/// I testi della pagina «Notifiche» e di «Avanzate» (Impostazioni), uguali alla web (`fanta/web/testi.js`: `imp.avvisi*`, `avv.*`, `av.mostra_tutte*`).
/// Logica pura: li prova `NotificheComeLaWebTests`, che li confronta con `testi.js`.
enum TestiImpostazioni {
    static let notifiche = "Avvisi e promemoria"
    static let notificheSotto = ""

    static let cambi = "Cambi di formazione e probabili"
    static let cambiAiuto = ""
    static let promemoria60 = "Promemoria un'ora prima"
    static let promemoria60Aiuto = ""
    static let promemoria15 = "Promemoria 15 minuti prima"
    static let riepilogo = "Riepilogo a giornata finita"
    static let riepilogoAiuto = ""
    static let copertura = "Reparto della rosa scoperto"
    static let coperturaAiuto = "Ti avvisa se in un reparto hai pochi giocatori disponibili (infortunati, squalificati, diffidati)."
    static let nativa = "Avvisi anche per l'app nativa"
    static let oreTranquille = "Ore tranquille"
    static let oreTranquilleAiuto = "Niente avvisi di notte: i promemoria che cadono in quelle ore non partono."

    static let mostraTutte = "Mostra tutte le funzioni"
    static let mostraTutteSpiega = "Di norma SchieraXI mostra solo l'essenziale: formazione, squadra e scambi. Se lo accendi vedi anche tutto il resto (risultati in diretta, confronto, seguiti, diario e altro). Vale solo per te."
}
