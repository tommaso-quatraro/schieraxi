import Foundation

extension LegaDemo {
    /// Solo per la fotografia `lega-regole-anteprima` (#889): il regolamento inventato che la demo incolla nelle Regole prima di
    /// «Riconosci le regole». Le sue righe sono quelle della risposta finta di `/api/regole/riconosci` (`riconosci()` in
    /// DatiDemo.swift): valori riconosciuti, la panchina non applicata e le righe da controllare a mano.
    static let regolamentoIncollato = """
        Assist: +1 punto
        Ammonizione: -0.5
        Sostituzioni per ruolo
        Panchina: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti
        In panchina vanno 12 giocatori
        Moduli: 3-4-3, 4-3-3, 4-4-2
        Il bonus per il rigore parato vale 3 punti, tranne in coppa
        Non è vietato il cambio modulo
        """
}
