import Foundation
import Testing
@testable import Schieraxi

// Regole uguali alla web (`vistaRegole` in `fanta/web/app.js`, testi `regole.*` del catalogo comune, #440 e #496): prova del
// modificatore («Prova», «Voti: portiere e 3 difensori», «Media 6,50 bonus +1 punto»), «Aggiungi fascia», «Scadenza della
// formazione» e «Prima giornata della lega» con la loro riga d'aiuto, la frase in fondo ai tempi della lega e le righe d'aiuto
// di «Posti fissi per ruolo» e «Cambio modulo nelle sostituzioni». I testi vengono da `Catalogo.Regole`: qui si prova che ogni
// nome usato dalla vista è il testo giusto e le frasi con un numero. Valori inventati, nessun dato vero.

/// Testo del catalogo e nome che usa la vista.
private let testiFissi: [(String, String)] = [
    (Catalogo.Regole.prova, TestiRegole.prova),
    (Catalogo.Regole.votiPortiereDifensori, TestiRegole.provaVoti),
    (Catalogo.Regole.postiFissi, TestiRegole.postiFissi),
    (Catalogo.Regole.postiFissiAiuto, TestiRegole.postiFissiAiuto),
    (Catalogo.Regole.cambioModulo, TestiRegole.cambioModulo),
    (Catalogo.Regole.cambioModuloAiuto, TestiRegole.cambioModuloAiuto),
    (Catalogo.Regole.scadenza, TestiRegole.scadenza),
    (Catalogo.Regole.scadenzaAiuto, TestiRegole.scadenzaAiuto),
    (Catalogo.Regole.primaGiornata, TestiRegole.primaGiornata),
    (Catalogo.Regole.primaGiornataAiuto, TestiRegole.primaGiornataAiuto),
    (Catalogo.Regole.conPrimaGiornata, TestiRegole.conPrimaGiornata),
]

/// Un esito della prova del modificatore: `m` e `b` sono i numeri come li scrive la web (segnaposto `{m}` e `{b}`).
struct CasoProvaRegole: Sendable, CustomTestStringConvertible {
    let media: Double
    let bonus: Double
    let m: String
    let b: String
    /// «punto» (chiave `.one`) solo con un bonus di 1; con 0, 0,5 o 1,5 si legge «punti».
    let singolare: Bool

    var testDescription: String { "media \(media), bonus \(bonus)" }
}

private let casiProva: [CasoProvaRegole] = [
    CasoProvaRegole(media: 6.5, bonus: 1, m: "6,50", b: "+1", singolare: true),
    CasoProvaRegole(media: 6.75, bonus: 3, m: "6,75", b: "+3", singolare: false),
    CasoProvaRegole(media: 6, bonus: 0, m: "6,00", b: "0", singolare: false),
    CasoProvaRegole(media: 7.25, bonus: 1.5, m: "7,25", b: "+1,5", singolare: false),
    CasoProvaRegole(media: 5.5, bonus: 0.5, m: "5,50", b: "+0,5", singolare: false),
]

@Suite("Regole: i testi della web")
struct RegoleComeLaWebTests {
    @Test("Ogni nome usato dalla vista è il testo giusto del catalogo", arguments: testiFissi)
    func comeIlCatalogo(catalogo: String, app: String) {
        #expect(app == catalogo)
    }

    @Test("«+ Aggiungi fascia»: le parole sono quelle della web, il «+» è l'icona del pulsante")
    func aggiungiFascia() {
        #expect(Catalogo.Regole.aggiungiFascia == "+ " + TestiRegole.aggiungiFascia)
        #expect(TestiRegole.aggiungiFascia == "Aggiungi fascia")
    }

    @Test("Prova: l'esito è la frase di `regole.media_bonus`, «punto» solo con 1", arguments: casiProva)
    func esitoProva(caso: CasoProvaRegole) {
        let atteso = Catalogo.Regole.mediaBonus(caso.singolare ? 1 : 2, b: caso.b, m: caso.m)
        #expect(TestiRegole.esitoProva(media: caso.media, bonus: caso.bonus) == atteso)
    }

    @Test("Prova: i due esempi della issue #440")
    func esempiDellaIssue() {
        #expect(TestiRegole.esitoProva(media: 6.5, bonus: 1) == "Media 6,50 bonus +1 punto")
        #expect(TestiRegole.esitoProva(media: 6.75, bonus: 3) == "Media 6,75 bonus +3 punti")
    }

    @Test("Prova: niente freccia e niente «Prova:» davanti alla riga dei voti")
    func senzaVecchiaForma() {
        #expect(!TestiRegole.esitoProva(media: 6.5, bonus: 1).contains("→"))
        #expect(!TestiRegole.prova.contains(":"))
    }
}
