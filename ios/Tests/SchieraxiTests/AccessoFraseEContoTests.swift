import Foundation
import Testing
@testable import Schieraxi

/// Dopo «troppi tentativi» la schermata di accesso ha il pulsante che conta da solo («Riprova tra 35 s»). Foto del 20/11 (#787,
/// punto 4): la frase sopra diceva «Riprova tra 45 secondi» e restava ferma mentre il pulsante contava. Ora la frase non dice il
/// numero: lo dice solo il pulsante, che cambia.
@MainActor
@Suite("Accesso: con il pulsante che conta, la frase non dice il numero")
struct AccessoFraseEContoTests {
    @Test("«Troppi tentativi» con l'attesa: la frase del server senza il tempo, che conta il pulsante")
    func senzaNumero() {
        let errore = ErroreApi.troppiTentativi("Troppi tentativi sbagliati: aspetta prima di riprovare.", riprovaTra: 45)
        let frase = SchermataAccesso.fraseDopoInvio(errore)
        #expect(frase == "Troppi tentativi sbagliati.")
        #expect(!frase.contains("45"))
        #expect(!frase.localizedCaseInsensitiveContains("riprova tra"))
    }

    @Test("Senza un'attesa il pulsante non conta: la frase resta quella di sempre")
    func senzaConto() {
        let errore = ErroreApi.troppiTentativi("Troppi tentativi: riprova tra qualche secondo.", riprovaTra: nil)
        #expect(SchermataAccesso.fraseDopoInvio(errore) == SchermataAccesso.testoErrore(errore))
        #expect(SchermataAccesso.fraseDopoInvio(ErroreApi.accessoRichiesto("Nome utente o password sbagliati"))
                == "Nome utente o password sbagliati")
        #expect(SchermataAccesso.fraseDopoInvio(ErroreApi.rete("x")) == SchermataAccesso.testoErrore(ErroreApi.rete("x")))
    }

    @Test("Altrove, dove nessun pulsante conta, il tempo resta nella frase")
    func altroveColTempo() {
        #expect(SchermataAccesso.testoErrore(ErroreApi.troppiTentativi("Calma.", riprovaTra: 30)).contains("30 secondi"))
    }
}
