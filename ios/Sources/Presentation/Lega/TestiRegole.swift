import Foundation

/// I testi della schermata Regole (modificatore difesa, panchina, tempi della lega), uguali alla web
/// (`vistaRegole` in `fanta/web/app.js`, testi `regole.*`). Logica pura: la provano i test.
enum TestiRegole {
    // Modificatore difesa
    /// Le parole di «+ Aggiungi fascia»: il «+» della web sull'iPhone è l'icona del pulsante.
    static let aggiungiFascia = "Aggiungi una fascia"
    static let prova = "Prova: voti di portiere e 3 difensori"
    static let provaVoti = ""

    /// L'esito della prova: «Media 6,50 bonus +1 punto», «Media 6,75 bonus +3 punti».
    static func esitoProva(media: Double, bonus: Double) -> String {
        "Media \(Formato.decimali(media, cifre: 2)) → bonus \(Formato.conSegno(bonus, cifre: 0)) punti"
    }

    // Panchina e sostituzioni
    static let postiFissi = "Posti fissi per ruolo"
    static let postiFissiAiuto = ""
    static let cambioModulo = "Cambio modulo nelle sostituzioni"
    static let cambioModuloAiuto = ""

    // Tempi della lega
    static let scadenza = "Scadenza (minuti prima)"
    static let scadenzaAiuto = ""
    static let primaGiornata = "Prima giornata della lega"
    static let primaGiornataAiuto = ""
    static let conPrimaGiornata = ""
}
