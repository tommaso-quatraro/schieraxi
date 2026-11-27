import Foundation
import Testing
@testable import Schieraxi

/// Un limite raggiunto (429) la cui frase dice già quando riprovare non riceve un secondo tempo, come `attesaDa` della web
/// (`fanta/web/app.js`): niente aggiunta quando la frase del server contiene la parola «tra». Prima Scrivici diceva «… Si azzera
/// tra circa 7 ore. Riprova tra circa 7 ore.», e così i tetti giornalieri di importazioni e scambi (`err.limite_oggi`).
@Suite("Limiti (429): la frase che dice già quando riprovare non si ripete")
struct LimiteFraseConAttesaTests {
    @Test("La frase del server con «tra» resta com'è", arguments: [
        ("Hai raggiunto il limite di commenti di oggi (5). Si azzera tra circa 7 ore.", 25_200),
        ("Hai raggiunto il limite di importazioni di oggi (20). Si azzera tra circa 3 ore.", 10_800),
        ("Hai fatto troppe richieste in quest'ora. Riprova tra 40 minuti.", 2_400),
    ])
    func fraseConAttesa(messaggio: String, attesa: Int) {
        let errore = ErroreApi.troppiTentativi(messaggio, riprovaTra: attesa)
        #expect(errore.errorDescription == messaggio)
        #expect(errore.errorDescription?.components(separatedBy: " tra ").count == 2, "il tempo una volta sola")
    }

    @Test("Senza la parola «tra» il tempo si aggiunge come prima, anche con «entra» nella frase")
    func fraseSenzaAttesa() {
        let scambi = ErroreApi.troppiTentativi("Per oggi hai già fatto 20 ricerche di scambi. Riprova domani.", riprovaTra: 415 * 60)
        #expect(scambi.errorDescription == "Per oggi hai già fatto 20 ricerche di scambi. Riprova tra circa 7 ore.")
        let parole = ErroreApi.troppiTentativi("Chi entra troppe volte aspetta.", riprovaTra: 30)
        #expect(parole.errorDescription == "Chi entra troppe volte aspetta. Riprova tra 30 secondi.")
    }
}
