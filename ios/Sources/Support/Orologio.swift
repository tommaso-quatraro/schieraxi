import Foundation

/// L'ora con cui l'app confronta le date del server (conto alla rovescia, scadenza, fasi della giornata, diretta).
/// Di norma è l'ora vera. Nelle «fotografie dal vero» (`ScenarioVero`) è l'ora in cui il server è stato fotografato, che poi
/// scorre normalmente: così scadenze e fasi sono quelle di quel momento, qualunque giorno si scattino le foto.
enum Orologio {
    /// Secondi da aggiungere all'ora vera: 0 fuori dalle fotografie dal vero. Si calcola una volta, all'avvio.
    static let scarto: TimeInterval = ScenarioVero.attuale.map { $0.adesso.timeIntervalSinceNow } ?? 0

    /// Adesso, per l'app.
    static func adesso() -> Date { Date().addingTimeInterval(scarto) }

    /// Un istante dell'orologio di sistema (per esempio quello di `TimelineView`) portato sull'ora dell'app.
    static func daSistema(_ data: Date) -> Date { data.addingTimeInterval(scarto) }

    /// Il contrario: un istante dell'ora dell'app sull'orologio di sistema, per i testi che contano da soli
    /// (`Text(timerInterval:)`, `Text(_:style: .relative)`).
    static func perSistema(_ data: Date) -> Date { data.addingTimeInterval(-scarto) }
}
