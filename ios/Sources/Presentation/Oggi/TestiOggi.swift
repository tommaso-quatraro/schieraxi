/// I titoli e le frasi fisse di Oggi, con le parole della web (chiavi `oggi.*` di `fanta/web/testi.js`, #416).
/// La prova è `OggiComeLaWebTests`, che li confronta con `testi.js`: una parola cambiata su un lato solo fa fallire il test.
enum TestiOggi {
    /// Sopra il modulo: `oggi.tua_formazione` o, se è la formazione salvata da te, `oggi.tua_formazione_scelta`.
    static func titoloFormazione(tuaScelta: Bool) -> String {
        tuaScelta ? "La tua formazione · la tua scelta" : "La tua formazione"
    }
    static let puntiAttesi = "punti attesi"
    /// Cosa legge VoiceOver sulle cifre della formazione: «Modulo 4-3-3, 65,5 punti attesi». Senza il titolo della carta
    /// («La tua formazione», «Prossima giornata»), che VoiceOver ha appena letto come intestazione.
    static func voceCifre(modulo: String?, punti: Double?) -> String {
        "Modulo \(modulo ?? "non disponibile"), \(Formato.punti(punti)) \(puntiAttesi)"
    }
    static let apriFormazione = "Apri la formazione"
    static let mancanoProbabili = "Mancano le probabili formazioni di questa giornata: i consigli usano le presenze recenti."
    static let migliori = "I tuoi migliori della giornata"
    static let daControllare = "Da controllare"
    /// La riga sotto il titolo di Da controllare (`oggi.giocatori_formazione_con`).
    static let daControllareSotto = "Giocatori in formazione con qualche dubbio: riguarda le probabili prima della partita."
    static let diffidati = "Diffidati"
    static let partiteDelTurno = "Partite del turno"
    static func indisponibili(_ n: Int) -> String { "Indisponibili in rosa (\(n))" }
    /// Il banner delle novità (`oggi.novita_banner`): senza stelline né «tocca per vedere» (`docs/STILE-SENZA-AI.md`).
    static func novita(_ versione: String) -> String { "Novità della versione \(versione)" }
}
