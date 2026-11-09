import Foundation

/// Le parole di «Squadre e rose» e della rosa di una squadra, uguali alla web (issue #441): vengono dal catalogo comune (chiavi
/// `lega.*` e `scambio.*`, file generati `Catalogo+Lega.swift` e `Catalogo+Scambio.swift`). Si dice «maglia», mai «divisa». I testi
/// che la web non ha (le spiegazioni per caricare un'immagine dal telefono) restano qui e usano le stesse parole.
enum ParoleSquadre {
    // MARK: pagina Squadre e rose

    /// Il titolo della pagina: come la voce del menu (`lega.voce_squadre`), che senza le rose degli altri diventa `lega.voce_miasquadra`.
    static func titolo(squadreAltrui: Bool) -> String {
        squadreAltrui ? Catalogo.Lega.voceSquadre : Catalogo.Lega.voceMiasquadra
    }

    static let miaSquadra = Catalogo.Lega.miaSquadra
    static let stemmaEMaglia = Catalogo.Lega.stemmaMaglia
    static let vediLaRosa = Catalogo.Lega.vediRosa
    static let nonLaTua = Catalogo.Lega.nonTuaSquadra
    static let scegliLaTua = Catalogo.Lega.scegliQualeDelle
    /// Il nome del selettore per VoiceOver (`lega.tua_squadra`).
    static let tuaSquadra = Catalogo.Lega.tuaSquadra
    static let toccaUnaSquadra = Catalogo.Lega.toccaUnaSquadra
    static let importaPrima = Catalogo.Lega.importaPrimaRose
    static let chiudi = "Chiudi"

    /// «24 giocatori · 12 crediti»; senza crediti (il server non li ha) solo i giocatori.
    static func riepilogo(giocatori: Int?, crediti: Double?) -> String {
        let quanti = Formato.giocatori(giocatori ?? 0)
        guard let crediti else { return quanti }
        return "\(quanti) · \(Formato.crediti(Formato.intero(crediti)))"
    }

    // MARK: stemma e maglia

    /// «Stemma» o «Maglia» (`scambio.stemma`, `scambio.maglia`); `tipo` è «stemma» o «maglia» come per il server.
    static func nome(tipo: String) -> String { tipo == "stemma" ? Catalogo.Scambio.stemma : Catalogo.Scambio.maglia }

    /// «Stemma aggiornato» o «Maglia aggiornata» (`scambio.stemma_aggiornato`, `scambio.maglia_aggiornata`).
    static func aggiornata(tipo: String) -> String { tipo == "stemma" ? Catalogo.Scambio.stemmaAggiornato : Catalogo.Scambio.magliaAggiornata }

    /// «Usa come stemma» o «Usa come maglia» (`lega.usa_come_stemma`, `lega.usa_come_maglia`).
    static func usaCome(tipo: String) -> String { tipo == "stemma" ? Catalogo.Lega.usaComeStemma : Catalogo.Lega.usaComeMaglia }

    /// «Cambia stemma» o «Cambia maglia» (`scambio.cambia_tipo`).
    static func cambia(tipo: String) -> String { Catalogo.Scambio.cambiaTipo(tipo: nome(tipo: tipo).lowercased()) }

    /// «Carica stemma» o «Carica maglia» (`scambio.carica_tipo`).
    static func carica(tipo: String) -> String { Catalogo.Scambio.caricaTipo(tipo: nome(tipo: tipo).lowercased()) }

    /// «Stemma da un file» o «Maglia da un file».
    static func daUnFile(tipo: String) -> String { "\(nome(tipo: tipo)) da un file" }

    static let daUnFileMenu = "Da un file"
    static let daUnIndirizzoWeb = Catalogo.Lega.indirizzoWeb
    static let indirizzoDellImmagine = "Indirizzo dell'immagine"
    static let annulla = Catalogo.Mercato.annulla
    static let formazioneConsigliataPerLoro = Catalogo.Scambio.formazioneConsigliataPer

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

    static let cambiaIlNome = Catalogo.Scambio.cambiaNome
    static let nuovoNome = Catalogo.Scambio.nuovoNome
    static let aiutoNome = Catalogo.Scambio.nomeAiuto
    static let nomeNonValido = Catalogo.Scambio.nomeNonValido
    static let nomeSalvato = Catalogo.Scambio.nomeSalvato
    static let creditiResidui = Catalogo.Scambio.creditiResidui
    static let salva = Catalogo.Scambio.salva
    /// Cosa legge VoiceOver sui due «Salva» della rosa (sulla web si vede il campo accanto, qui basta il nome del pulsante).
    static let salvaNome = "Salva il nuovo nome"
    static let salvaCreditiResidui = "Salva i crediti residui"
    static let creditiSalvati = Catalogo.Scambio.creditiSalvati
    static let scriviCrediti = Catalogo.Scambio.scriviCreditiCome
    /// Il gruppo dei giocatori che il server non ha saputo collegare a un ruolo.
    static let senzaRuolo = Catalogo.Scambio.senzaRuolo

    /// «Rose aggiornate il 6 novembre 2026» (mese per intero, ora italiana); se la data manca o non si capisce, «–» come la web.
    static func roseAggiornate(_ aggiornato: String?) -> String {
        Catalogo.Scambio.roseAggiornate(data: dataEstesa(aggiornato))
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
