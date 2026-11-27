import Foundation

/// Dove sta un giocatore nella formazione in campo, a parole, come `postoInFormazione` della web: «Titolare», «Panchina 2»,
/// «Non schierato» (`mercato.posto_titolare`, `mercato.panchina_n`, `mercato.posto_fuori`). Parole proprie, mai quelle delle
/// probabili: «titolare» e «panchina» vogliono dire la tua formazione. Lo mostrano le righe di «Sostituisci» (collaudo del 26/11).
enum PostoInFormazione {
    /// `titolari` e `panchina`: gli 11 in campo e la panchina nell'ordine in cui entra. `inRosa`: il giocatore ha una scheda nella
    /// Formazione (allora, se non è fra i 18, è «Non schierato»); nil se non è nemmeno lì.
    static func testo(_ id: Int, titolari: [Int], panchina: [Int], inRosa: Bool) -> String? {
        if titolari.contains(id) { return Catalogo.Mercato.postoTitolare }
        if let k = panchina.firstIndex(of: id) { return Catalogo.Mercato.panchinaN(n: String(k + 1)) }
        return inRosa ? Catalogo.Mercato.postoFuori : nil
    }
}
