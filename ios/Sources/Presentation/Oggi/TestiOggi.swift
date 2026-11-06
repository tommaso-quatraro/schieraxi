/// I testi di Oggi.
enum TestiOggi {
    static func titoloFormazione(tuaScelta: Bool) -> String { tuaScelta ? "La tua scelta" : "La formazione consigliata" }
    static let puntiAttesi = "punti attesi"
    static let apriFormazione = "Apri la formazione"
    static let mancanoProbabili = "Mancano le probabili formazioni di questa giornata: i consigli usano le presenze recenti."
    static let migliori = "I tuoi migliori della giornata"
    static let daControllare = "Da controllare"
    static let daControllareSotto = "Mister, c'è qualche dubbio in formazione. Riguarda le probabili prima del fischio."
    static let diffidati = "Diffidati"
    static let partiteDelTurno = "Partite del turno"
    static func indisponibili(_ n: Int) -> String { "Indisponibili in rosa (\(n))" }
    static func novita(_ versione: String) -> String { "Novità nell'app (versione \(versione)): tocca per vedere" }
}
