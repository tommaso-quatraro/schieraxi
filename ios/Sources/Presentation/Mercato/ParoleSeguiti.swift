import Foundation

/// Le frasi dei Seguiti, uguali alla web (issue #441): `mercato.osservi_avviso`, `mercato.non_osservi` e
/// `mercato.nessun_giocatore_osservato` di `fanta/web/testi.js`. `SeguitiComeLaWebTests` le confronta.
enum ParoleSeguiti {
    /// Dopo «Segui» sulla scheda del giocatore.
    static let loSegui = "Lo segui: ti avviso se cambia qualcosa"
    /// Dopo aver tolto il giocatore dai seguiti.
    static let nonLoSeguiPiu = "Non lo segui più"
    /// La pagina Seguiti senza nessun giocatore: solo questa frase.
    static let nessunGiocatore = "Nessun giocatore seguito."
}
