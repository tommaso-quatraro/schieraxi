import Foundation
import Testing
@testable import Schieraxi

// Regole uguali alla web (`vistaRegole` in `fanta/web/app.js`, testi `regole.*` in `fanta/web/testi.js`), #440: prova del
// modificatore («Prova», «Voti: portiere e 3 difensori», «Media 6,50 bonus +1 punto»), «Aggiungi fascia», «Scadenza della
// formazione» e «Prima giornata della lega» con la loro riga d'aiuto, la frase in fondo ai tempi della lega e le righe d'aiuto
// di «Posti fissi per ruolo» e «Cambio modulo nelle sostituzioni». Ogni testo si confronta con `testi.js` (`TestiWeb`): una
// frase cambiata su un lato solo fa fallire il test. Valori inventati, nessun dato vero.

/// Chiave di `testi.js` e testo che l'app mostra.
private let testiFissi: [(String, String)] = [
    ("regole.prova", TestiRegole.prova),
    ("regole.voti_portiere_difensori", TestiRegole.provaVoti),
    ("regole.posti_fissi", TestiRegole.postiFissi),
    ("regole.posti_fissi_aiuto", TestiRegole.postiFissiAiuto),
    ("regole.cambio_modulo", TestiRegole.cambioModulo),
    ("regole.cambio_modulo_aiuto", TestiRegole.cambioModuloAiuto),
    ("regole.scadenza", TestiRegole.scadenza),
    ("regole.scadenza_aiuto", TestiRegole.scadenzaAiuto),
    ("regole.prima_giornata", TestiRegole.primaGiornata),
    ("regole.prima_giornata_aiuto", TestiRegole.primaGiornataAiuto),
    ("regole.con_prima_giornata", TestiRegole.conPrimaGiornata),
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
    @Test("Il testo dell'app è quello di `testi.js`", arguments: testiFissi)
    func comeLaWeb(chiave: String, app: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(app == web, "chiave \(chiave)")
    }

    @Test("«+ Aggiungi fascia»: le parole sono quelle della web, il «+» è l'icona del pulsante")
    func aggiungiFascia() throws {
        let web = try TestiWeb().italiano("regole.aggiungi_fascia")
        #expect(web == "+ " + TestiRegole.aggiungiFascia)
    }

    @Test("Prova: l'esito è la frase di `regole.media_bonus`, «punto» solo con 1", arguments: casiProva)
    func esitoProva(caso: CasoProvaRegole) throws {
        let modello = try TestiWeb().italiano(caso.singolare ? "regole.media_bonus.one" : "regole.media_bonus.other")
        let atteso = modello
            .replacingOccurrences(of: "{m}", with: caso.m)
            .replacingOccurrences(of: "{b}", with: caso.b)
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
