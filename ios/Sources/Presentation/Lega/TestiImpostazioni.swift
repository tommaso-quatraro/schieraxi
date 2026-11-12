import Foundation

/// I testi della pagina «Notifiche» (Impostazioni), dal catalogo comune con la web (`imp.avvisi*`, `avv.*`).
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
}
