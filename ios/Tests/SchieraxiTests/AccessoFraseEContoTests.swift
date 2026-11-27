import Foundation
import Testing
@testable import Schieraxi

/// Dopo «troppi tentativi» la schermata di accesso ha il pulsante che conta da solo («Riprova tra 35 secondi», come la web dal #940;
/// prima «Riprova tra 35 s» e i secondi anche oltre il minuto). Foto del 20/11 (#787,
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
        #expect(SchermataAccesso.fraseDopoInvio(ErroreApi.accessoRichiesto("Nome utente o password sbagliati."))
                == "Nome utente o password sbagliati.")
        #expect(SchermataAccesso.fraseDopoInvio(ErroreApi.rete("x")) == SchermataAccesso.testoErrore(ErroreApi.rete("x")))
    }

    /// Revisione della #806: con due messaggi veri del server (`err.troppi_tentativi`, `err.molto_occupato`) la frase diventava
    /// «Troppi tentativi:.» e «Il server è molto occupato:.». Il segno prima dell'invito a riprovare se ne va con l'invito.
    @Test("Dalla frase del server si toglie anche il segno prima dell'invito: mai «:.»", arguments: [
        ("Troppi tentativi: riprova più tardi.", "Troppi tentativi."),
        ("Il server è molto occupato: riprova fra qualche secondo.", "Il server è molto occupato."),
        // un server di prima del 27/11, con i messaggi senza il punto finale
        ("Troppi tentativi: riprova più tardi", "Troppi tentativi."),
        ("Il server è molto occupato: riprova fra qualche secondo", "Il server è molto occupato."),
    ])
    func senzaDuePuntiFinali(messaggio: String, attesa: String) {
        let errore = ErroreApi.troppiTentativi(messaggio, riprovaTra: 30)
        #expect(SchermataAccesso.fraseDopoInvio(errore) == attesa)
        #expect(errore.errorDescription == "\(attesa) Riprova tra 30 secondi.", "anche dove il tempo resta nella frase")
    }

    /// Il pulsante conta al massimo un'ora: oltre (per esempio il tetto delle iscrizioni del giorno) la frase tiene il tempo,
    /// con le parole della web («Riprova tra circa 20 ore.», #940; prima «Riprova tra 20 h»).
    @Test("Attesa oltre l'ora: la frase tiene il tempo, come la web; fino all'ora no")
    func attesaLunga() {
        let lunga = ErroreApi.troppiTentativi("Per oggi le iscrizioni sono chiuse: riprova domani.", riprovaTra: 72_000)
        #expect(SchermataAccesso.fraseDopoInvio(lunga) == "Per oggi le iscrizioni sono chiuse. Riprova tra circa 20 ore.")
        #expect(SchermataAccesso.fraseDopoInvio(ErroreApi.troppiTentativi("Calma.", riprovaTra: 3600)) == "Calma.",
                "un'ora esatta la conta ancora il pulsante")
    }

    @Test("Il pulsante che conta usa le parole della web: secondi (anche al singolare), poi minuti, poi ore (#940)", arguments: [
        (35, "Riprova tra 35 secondi"), (1, "Riprova tra 1 secondo"), (89, "Riprova tra 89 secondi"), (90, "Riprova tra 2 minuti"),
        (300, "Riprova tra 5 minuti"), (3599, "Riprova tra 60 minuti"), (3600, "Riprova tra circa 1 ora"),
    ])
    func testoDelPulsante(secondi: Int, testo: String) {
        #expect(AttesaRiprova.testoPulsante(secondi) == testo)
    }

    @Test("Altrove, dove nessun pulsante conta, il tempo resta nella frase")
    func altroveColTempo() {
        #expect(SchermataAccesso.testoErrore(ErroreApi.troppiTentativi("Calma.", riprovaTra: 30)).contains("30 secondi"))
    }
}
