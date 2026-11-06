import Foundation

/// L'ora con cui l'app confronta le date del server e conta «oggi» e «ieri» (conto alla rovescia, scadenza, fasi della giornata,
/// diretta, giorno delle partite). Di norma è l'ora vera. Nelle «fotografie dal vero» (`ScenarioVero`) è l'ora in cui il server è
/// stato fotografato, e nelle foto della demo a giornata in corso il momento in cui vive la demo (#424); da lì scorre normalmente:
/// così scadenze e fasi sono quelle di quel momento, qualunque giorno e a qualunque ora si scattino le foto.
enum Orologio {
    /// Secondi da aggiungere all'ora vera: 0 fuori dalle fotografie. Si calcola una volta, all'avvio.
    static let scarto: TimeInterval = scartoAllAvvio(scenario: ScenarioVero.attuale?.adesso, demo: Demo.daLancio,
                                                     schermata: Demo.argomento("DEMO_SCHERMATA"), adesso: Date())

    /// Lo scarto di un avvio, con il telefono a `adesso`. Fotografie dal vero (`scenario`): l'ora della fotografia. Demo da
    /// argomento di lancio (`demo`, `-DEMO`) con la `schermata` di una giornata in corso (`oggi-in-corso`, `formazione-chiusa`): il
    /// momento della demo (`LegaDemo.momento`, alle 18:48), così Oggi scrive «La formazione si è chiusa ieri 20:35» e le righe
    /// «oggi 18:00» come il widget anche con le foto scattate di notte. Altrimenti, anche nella «Prova con dati di esempio», 0.
    static func scartoAllAvvio(scenario: Date?, demo: Bool, schermata: String?, adesso: Date) -> TimeInterval {
        if let scenario { return scenario.timeIntervalSince(adesso) }
        guard demo else { return 0 }
        return LegaDemo.momento(adesso: adesso, fase: FinteServer.faseDemo(schermata)).timeIntervalSince(adesso)
    }

    /// Adesso, per l'app.
    static func adesso() -> Date { Date().addingTimeInterval(scarto) }

    /// Un istante dell'orologio di sistema (per esempio quello di `TimelineView`) portato sull'ora dell'app.
    static func daSistema(_ data: Date) -> Date { data.addingTimeInterval(scarto) }

    /// Il contrario: un istante dell'ora dell'app sull'orologio di sistema, per i testi che contano da soli
    /// (`Text(timerInterval:)`, `Text(_:style: .relative)`).
    static func perSistema(_ data: Date) -> Date { data.addingTimeInterval(-scarto) }
}
