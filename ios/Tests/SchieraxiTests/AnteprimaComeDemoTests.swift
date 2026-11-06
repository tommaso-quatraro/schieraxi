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
        let nellApp = try #require(formazione["punteggio_atteso"] as? Double, "Oggi in corso: manca «punteggio_atteso»")
        let r = try #require(try widget(.inCorso).comeRiassuntoOggi(scaricatoIl: Self.adesso))
        let nelWidget = try #require(r.punti, "il widget in corso non ha i punti attesi")
        #expect(Formato.punti(nelWidget) == Formato.punti(nellApp))
    }

    @Test("Giornata finita: i punti attesi del riepilogo nel widget sono quelli di Oggi a giornata finita")
    func attesiFinita() throws {
        let riepilogo = try #require(try app("/api/oggi", schermata: "oggi-finita")["riepilogo"] as? [String: Any])
        let attesiApp = try #require(riepilogo["punti_attesi"] as? Double, "Oggi finita: mancano i punti attesi")
        let fattiApp = try #require(riepilogo["punti_fatti"] as? Double, "Oggi finita: mancano i punti fatti")
        let nelWidget = try #require(try widget(.finita).faseGiornata.riepilogo, "il widget a giornata finita non ha il riepilogo")
        let attesi = try #require(nelWidget.puntiAttesi, "il riepilogo del widget non ha i punti attesi")
        let fatti = try #require(nelWidget.puntiFatti, "il riepilogo del widget non ha i punti fatti")
        #expect(Formato.punti(attesi) == Formato.punti(attesiApp))
        #expect(Formato.punti(fatti) == Formato.punti(fattiApp))
    }

    @Test("Giornata in corso: le partite del widget hanno il giorno e l'ora delle partite in diretta dell'app")
    func orariInCorso() throws {
        let partite = try #require(try app("/api/live", schermata: "oggi-in-corso")["partite"] as? [[String: Any]])
        let attese = try partite.map { p -> String in
            let data = try #require(p["data"] as? String, "una partita dell'app senza data")
            return "\(p["casa"] as? String ?? "")-\(p["trasferta"] as? String ?? ""): \(data)"
        }
        #expect(!attese.isEmpty, "l'app in corso non ha partite")
        let nelWidget = try #require(try widget(.inCorso).live?.partite, "il widget in corso non ha le partite live")
        #expect(!nelWidget.isEmpty)
        #expect(nelWidget.map { "\($0.id): \($0.data ?? "")" } == attese)
    }
}
