import SwiftUI
import Testing
@testable import Schieraxi

/// Le frasi della schermata di accesso che non sono errori hanno due aspetti, come `mostraMessaggioAccesso` della web: la conferma
/// (verde, con la spunta) e l'avviso «attenzione», per la sessione chiusa dal server. Prima «La sessione è finita: accedi di nuovo.»
/// si vedeva verde con la spunta, il segno di «fatto», anche con l'account bloccato (revisione della #965).
@Suite("Accesso: la sessione finita non si mostra come una conferma")
struct AvvisoAccessoAspettoTests {
    @Test("Attenzione: il colore «attenzione» e un'icona d'avviso; conferma: un altro colore e la spunta")
    func coloreEIcona() {
        #expect(AvvisoAccesso.Tipo.attenzione.colore == Color.attenzione)
        #expect(AvvisoAccesso.Tipo.conferma.colore != Color.attenzione)
        #expect(AvvisoAccesso.Tipo.conferma.icona == "checkmark.circle.fill")
        #expect(AvvisoAccesso.Tipo.attenzione.icona == "exclamationmark.circle.fill")
    }
}
