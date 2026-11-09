import Foundation

/// I testi della pagina «Notifiche» e di «Avanzate» (Impostazioni), dal catalogo comune con la web (`imp.avvisi*`, `avv.*`).
/// Le righe d'aiuto, come sulla web, non finiscono con il punto. Logica pura: li prova `NotificheComeLaWebTests`.
enum TestiImpostazioni {
    /// La voce nell'elenco delle Impostazioni e il titolo della pagina (`imp.avvisi`), con la riga sotto la voce (`imp.avvisi_sub`).
    static let notifiche = Catalogo.Imp.avvisi
    static let notificheSotto = Catalogo.Imp.avvisiSub

    static let cambi = Catalogo.Avv.cambi
    static let cambiAiuto = Catalogo.Avv.cambiAiuto
    static let promemoria60 = Catalogo.Avv.prom60
    static let promemoria60Aiuto = Catalogo.Avv.prom60Aiuto
    static let promemoria15 = Catalogo.Avv.prom15
    static let riepilogo = Catalogo.Avv.riepilogo
    static let riepilogoAiuto = Catalogo.Avv.riepilogoAiuto
    static let copertura = Catalogo.Avv.copertura
    static let coperturaAiuto = Catalogo.Avv.coperturaAiuto
    static let nativa = Catalogo.Avv.nativa
    static let oreTranquille = Catalogo.Avv.oreTranq
    static let oreTranquilleAiuto = Catalogo.Avv.oreTranqAiuto

    /// `av.mostra_tutte` e `av.mostra_tutte_spiega`: il prefisso `av` lo elenca Squadra e Altro (`ios/testi/av.txt`); finché
    /// queste due chiavi non ci sono, i testi restano qui e `NotificheComeLaWebTests` li confronta con `testi.js`.
    static let mostraTutte = "Mostra tutte le funzioni"
    static let mostraTutteSpiega = "Di norma SchieraXI mostra solo l'essenziale: formazione, squadra e scambi. Se lo accendi vedi anche il resto (risultati in diretta, confronto, seguiti, diario e altro). Vale solo per te."
}
