import Foundation

/// Le frasi dei Seguiti, uguali alla web (issue #441): `mercato.osservi_avviso`, `mercato.non_osservi` e
/// `mercato.nessun_giocatore_osservato` del catalogo comune (`Catalogo+Mercato.swift`). `SeguitiComeLaWebTests` le prova.
enum ParoleSeguiti {
    /// Dopo «Segui» sulla scheda del giocatore.
    static let loSegui = Catalogo.Mercato.osserviAvviso
    /// Dopo aver tolto il giocatore dai seguiti.
    static let nonLoSeguiPiu = Catalogo.Mercato.nonOsservi
    /// La pagina Seguiti senza nessun giocatore: solo questa frase.
    static let nessunGiocatore = Catalogo.Mercato.nessunGiocatoreOsservato
}
