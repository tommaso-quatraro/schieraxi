import Foundation
import Testing
@testable import Schieraxi

/// Issue #391: le foto dei widget (app `AnteprimaWidget`, che mostra `LegaDemo.widget`) e quelle dell'app in demo devono dire gli
/// stessi numeri e gli stessi orari nella stessa fase della giornata: una sola fonte. `DemoWidgetComeAppTests` lo prova già per
/// i punti prima della scadenza e per i punti fatti; qui i punti attesi a giornata in corso («attesi prima») e a giornata finita,
/// e gli orari delle partite del widget «Partite live», che si fotografa a giornata in corso. Stesso istante fisso di quei test.
@Suite("Demo: anteprima dei widget e app con gli stessi punti attesi e gli stessi orari (#391)")
struct AnteprimaComeDemoTests {
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)

    /// Una risposta della demo dell'app nella fase di `schermata` (`oggi-in-corso`, `oggi-finita`).
    private func app(_ percorso: String, schermata: String) throws -> [String: Any] {
        let server = try #require(FinteServer.demoFase(schermata, adesso: Self.adesso), "nessuna demo per \(schermata)")
        let testo = try #require(server.risposte[percorso], "la demo dell'app non ha \(percorso)")
        return try #require(try JSONSerialization.jsonObject(with: Data(testo.utf8)) as? [String: Any])
    }

    /// Il riassunto che l'anteprima dei widget mostra in quella fase.
    private func widget(_ fase: LegaDemo.Fase) throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: Self.adesso, fase: fase)), "il riassunto dei widget non si legge")
    }

    @Test("Giornata in corso: «attesi prima» del widget è il numero di Oggi in corso dell'app")
    func attesiPrimaInCorso() throws {
        let formazione = try #require(try app("/api/oggi", schermata: "oggi-in-corso")["formazione"] as? [String: Any])
        let r = try #require(try widget(.inCorso).comeRiassuntoOggi(scaricatoIl: Self.adesso))
        #expect(Formato.punti(r.punti) == Formato.punti(formazione["punteggio_atteso"] as? Double))
    }

    @Test("Giornata finita: i punti attesi del riepilogo nel widget sono quelli di Oggi a giornata finita")
    func attesiFinita() throws {
        let riepilogo = try #require(try app("/api/oggi", schermata: "oggi-finita")["riepilogo"] as? [String: Any])
        let w = try widget(.finita)
        #expect(Formato.punti(w.faseGiornata.riepilogo?.puntiAttesi) == Formato.punti(riepilogo["punti_attesi"] as? Double))
        #expect(Formato.punti(w.faseGiornata.riepilogo?.puntiFatti) == Formato.punti(riepilogo["punti_fatti"] as? Double))
    }

    @Test("Giornata in corso: le partite del widget hanno il giorno e l'ora delle partite in diretta dell'app")
    func orariInCorso() throws {
        let partite = try #require(try app("/api/live", schermata: "oggi-in-corso")["partite"] as? [[String: Any]])
        let attese = partite.map { "\($0["casa"] as? String ?? "")-\($0["trasferta"] as? String ?? ""): \($0["data"] as? String ?? "")" }
        let w = try widget(.inCorso)
        #expect((w.live?.partite ?? []).map { "\($0.id): \($0.data ?? "")" } == attese)
    }
}
