import Foundation

/// I testi della pagina «Notifiche» e di «Avanzate» (Impostazioni), uguali alla web (`fanta/web/testi.js`: `imp.avvisi*`, `avv.*`, `av.mostra_tutte*`).
/// Le righe d'aiuto, come sulla web, non finiscono con il punto. Logica pura: li prova `NotificheComeLaWebTests`, che li confronta con `testi.js`.
enum TestiImpostazioni {
    /// La voce nell'elenco delle Impostazioni e il titolo della pagina (`imp.avvisi`), con la riga sotto la voce (`imp.avvisi_sub`).
    static let notifiche = "Notifiche"
    static let notificheSotto = "Cosa ricevere sul telefono e quando"

    static let cambi = "Cambi di formazione e probabili"
    static let cambiAiuto = "Infortunati, squalificati, titolari in panchina, forti cali"
    static let promemoria60 = "Promemoria un'ora prima"
    static let promemoria60Aiuto = "Con la formazione consigliata e i giocatori da controllare"
    static let promemoria15 = "Promemoria 15 minuti prima"
    static let riepilogo = "Riepilogo a giornata finita"
    static let riepilogoAiuto = "Punti fatti, attesi e massimo possibile con la tua rosa"
    static let copertura = "Reparto della rosa scoperto"
    static let coperturaAiuto = "Ti avvisa se in un reparto hai pochi giocatori disponibili (infortunati, squalificati, diffidati)"
    static let nativa = "Avvisi anche per l'app nativa"
    static let oreTranquille = "Ore tranquille"
    static let oreTranquilleAiuto = "Niente avvisi nella fascia scelta: cambi e riepilogo arrivano appena finisce. Un promemoria che cade lì non viene mandato"

    static let mostraTutte = "Mostra tutte le funzioni"
    static let mostraTutteSpiega = "Di norma SchieraXI mostra solo l'essenziale: formazione, squadra e scambi. Se lo accendi vedi anche il resto (risultati in diretta, confronto, seguiti, diario e altro). Vale solo per te."
}
