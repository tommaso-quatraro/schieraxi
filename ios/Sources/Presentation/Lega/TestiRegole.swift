import Foundation

/// I testi della schermata Regole (modificatore difesa, panchina, tempi della lega), uguali alla web
/// (`vistaRegole` in `fanta/web/app.js`, testi `regole.*` in `fanta/web/testi.js`). Logica pura: la provano i test.
enum TestiRegole {
    // MARK: modificatore difesa

    /// Le parole di «+ Aggiungi fascia» (`regole.aggiungi_fascia`): il «+» della web sull'iPhone è l'icona del pulsante.
    static let aggiungiFascia = "Aggiungi fascia"
    static let prova = "Prova"
    static let provaVoti = "Voti: portiere e 3 difensori"

    /// L'esito della prova, come la web (`regole.media_bonus`): «Media 6,50 bonus +1 punto», «Media 6,75 bonus +3 punti».
    /// «punto» solo con un bonus di 1; un bonus intero si scrive senza decimali, uno a metà con uno («+1,5 punti»).
    static func esitoProva(media: Double, bonus: Double) -> String {
        let intero = bonus == bonus.rounded()
        let numero = (bonus > 0 ? "+" : "") + Formato.decimali(bonus, cifre: intero ? 0 : 1)
        let punti = abs(bonus) == 1 ? "punto" : "punti"
        return "Media \(Formato.decimali(media, cifre: 2)) bonus \(numero) \(punti)"
    }

    // MARK: panchina e sostituzioni

    static let postiFissi = "Posti fissi per ruolo"
    static let postiFissiAiuto = "La panchina ha un numero preciso di posti per ogni ruolo"
    static let cambioModulo = "Cambio modulo nelle sostituzioni"
    static let cambioModuloAiuto = "Una riserva di un altro ruolo può entrare se il modulo resta valido"

    // MARK: tempi della lega

    static let scadenza = "Scadenza della formazione"
    static let scadenzaAiuto = "minuti prima della prima partita della giornata (0 = all'inizio)"
    static let primaGiornata = "Prima giornata della lega"
    static let primaGiornataAiuto = "la giornata di Serie A da cui parte la lega (1 se è partita con il campionato)"
    /// In fondo alla sezione: un esempio fisso («a 4»), che non cambia con il numero scelto.
    static let conPrimaGiornata = "Con la prima giornata a 4, la giornata 1 della lega è la 4ª di Serie A: calendario, Diario e promemoria contano da lì."
}
