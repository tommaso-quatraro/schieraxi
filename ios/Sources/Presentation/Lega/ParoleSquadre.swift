import Foundation

/// Le parole di «Squadre e rose» e della rosa di una squadra, uguali alla web (issue #441): chiavi `lega.*` e `scambio.*` di
/// `fanta/web/testi.js`, `SquadreComeLaWebTests` le confronta. Si dice «maglia», mai «divisa». I testi che la web non ha
/// (le spiegazioni per caricare un'immagine dal telefono) usano le stesse parole.
enum ParoleSquadre {
    // MARK: pagina Squadre e rose

    /// Il titolo della pagina: come la voce del menu (`lega.voce_squadre`), che senza le rose degli altri diventa `lega.voce_miasquadra`.
    static func titoloPagina(squadreAltrui: Bool) -> String {
        squadreAltrui ? "Squadre e rose" : "La mia squadra e rosa"
    }

    static let miaSquadra = "La mia squadra"
    static let stemmaEMaglia = "Stemma e maglia"
    static let vediLaRosa = "Vedi la rosa"
    static let nonLaTua = "Non è la tua squadra?"
    static let scegliLaTua = "Scegli quale delle squadre è la tua."
    /// Il nome del selettore per VoiceOver (`lega.tua_squadra`).
    static let tuaSquadra = "La tua squadra"
    static let toccaUnaSquadra = "Tocca una squadra per vedere la rosa."
    static let importaPrima = "Importa prima le rose da «Aggiorna le rose»."
    static let chiudi = "Chiudi"

    /// «24 giocatori · 12 crediti»; senza crediti (il server non li ha) solo i giocatori.
    static func riepilogo(giocatori: Int?, crediti: Double?) -> String {
        let quanti = Formato.giocatori(giocatori ?? 0)
        guard let crediti else { return quanti }
        return "\(quanti) · \(Formato.crediti(Formato.intero(crediti)))"
    }

    // MARK: stemma e maglia

    /// «Stemma» o «Maglia» (`scambio.stemma`, `scambio.maglia`); `tipo` è «stemma» o «maglia» come per il server.
    static func nome(tipo: String) -> String { tipo == "stemma" ? "Stemma" : "Maglia" }

    /// «Stemma aggiornato» o «Maglia aggiornata».
    static func aggiornata(tipo: String) -> String { tipo == "stemma" ? "Stemma aggiornato" : "Maglia aggiornata" }

    /// «Usa come stemma» o «Usa come maglia».
    static func usaCome(tipo: String) -> String { "Usa come \(nome(tipo: tipo).lowercased())" }

    /// «Cambia stemma» o «Cambia maglia» (`scambio.cambia_tipo`).
    static func cambia(tipo: String) -> String { "Cambia \(nome(tipo: tipo).lowercased())" }

    /// «Carica stemma» o «Carica maglia» (`scambio.carica_tipo`).
    static func carica(tipo: String) -> String { "Carica \(nome(tipo: tipo).lowercased())" }

    /// «Stemma da un file» o «Maglia da un file».
    static func daUnFile(tipo: String) -> String { "\(nome(tipo: tipo)) da un file" }

    static let daUnFileMenu = "Da un file"
    static let daUnIndirizzoWeb = "Da un indirizzo web"
    static let indirizzoDellImmagine = "Indirizzo dell'immagine"
    static let annulla = "Annulla"
    static let formazioneConsigliataPerLoro = "Formazione consigliata per loro"

    /// Sotto il campo dell'indirizzo web.
    static let indirizzoImmagine = "Solo indirizzi https di un'immagine (stemma o maglia della tua squadra)."

    /// Come ottenere l'immagine da Leghe, quando si può incollare un indirizzo web.
    static let aiutoIndirizzo = "Dall'app o dal sito di Leghe tieni premuto sullo stemma o sulla maglia e scegli «Salva immagine» "
        + "(oppure copia l'indirizzo dell'immagine), poi incollalo qui. Se l'indirizzo non è pubblico, salva l'immagine "
        + "e caricala dalla libreria foto."

    /// Quando l'indirizzo web è spento per tutti.
    static let senzaIndirizzoWeb = "Per stemma e maglia scegli una foto dalla libreria o un file."

    static let immagineNonLeggibile = "Non riesco a leggere l'immagine."
    static let immagineDaFileNonLeggibile = "Non riesco a leggere l'immagine. Salvala su questo iPhone (Files > Sul mio iPhone) e riprova."

    // MARK: la rosa

    static let cambiaIlNome = "Cambia il nome"
    static let nuovoNome = "Nuovo nome della squadra"
    static let aiutoNome = "Su Leghe può restare il nome vecchio: quando reimporti le rose, SchieraXI aggiorna questa squadra."
    static let nomeNonValido = "Scrivi un nome da 1 a 60 caratteri."
    static let nomeSalvato = "Nome salvato"
    static let creditiResidui = "Crediti residui"
    static let salva = "Salva"
    static let creditiSalvati = "Crediti salvati"
    static let scriviCrediti = "Scrivi i crediti come numero intero, anche 0"
    /// Il gruppo dei giocatori che il server non ha saputo collegare a un ruolo.
    static let senzaRuolo = "Senza ruolo (da controllare)"

    /// «Rose aggiornate il 6 novembre 2026» (mese per intero, ora italiana); se la data manca o non si capisce, «–» come la web.
    static func roseAggiornate(_ aggiornato: String?) -> String {
        "Rose aggiornate il \(dataEstesa(aggiornato))"
    }

    private static let giornoLettura: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static let giornoScritto: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "d MMMM yyyy"
        return f
    }()

    /// «2026-11-06T10:12:00» o «2026-11-06 10:12» diventa «6 novembre 2026»; un testo che non si capisce, «–».
    private static func dataEstesa(_ testo: String?) -> String {
        guard let testo, testo.count >= 10, let data = giornoLettura.date(from: String(testo.prefix(10))) else { return "–" }
        return giornoScritto.string(from: data)
    }
}
