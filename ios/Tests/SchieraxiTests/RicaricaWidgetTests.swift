import Foundation
import Testing
@testable import Schieraxi

/// Ogni quanto i widget chiedono a iOS di ricaricarsi (`RicaricaWidget`, che il `Fornitore` usa). Dal 27/11/2026 durante le partite
/// ogni 15 minuti, non più ogni 2: nessun widget mostra la diretta (#634) e iOS concede poche ricariche al giorno, che finivano prima
/// dei punti. Le partite sono quelle dei giocatori della rosa (`data_partita`), perché il server non manda più la diretta in
/// `/api/widget`: da 10 minuti prima del calcio d'inizio a 4 ore e 15 minuti dopo, perché il server legge risultati e voti 2 ore e
/// 30 dopo l'inizio e, se mancano ancora, di nuovo a 4 ore (`pianificatore.GIRI_RISULTATI`), e lì arrivano i punti fatti; i 15
/// minuti in più sono una ricarica (la finestra di prima finiva dopo 130 minuti, prima dei voti). Che la finestra copra l'ultimo
/// giro lo controlla anche `tests/test_widget_ricariche.py`, contro il pianificatore. Orari inventati, in ora italiana.
@Suite("Widget: ogni quanto si ricarica")
struct RicaricaWidgetTests {
    private static let adesso = Date(timeIntervalSince1970: 1_795_000_000)

    private func data(_ testo: String) throws -> Date { try #require(Quando.data(testo), "data non letta: \(testo)") }

    /// Un riassunto con la rosa: un giocatore per ogni orario della sua partita (nil: partita senza data).
    private func riassunto(_ orari: [String?]) throws -> RiassuntoWidget {
        let rosa = orari.enumerated().map { i, orario -> String in
            let partita = orario.map { ", \"data_partita\": \"\($0)\"" } ?? ""
            return "{\"id\": \(i + 1), \"nome\": \"Giocatore \(i + 1)\", \"ruolo\": \"C\"\(partita)}"
        }
        let corpo = "{\"giornata\": 11, \"rosa\": [\(rosa.joined(separator: ", "))]}"
        return try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
    }

    // MARK: la finestra delle partite

    /// 17:30 e 19:00 sono i due giri dei voti della partita delle 15:00.
    @Test("Una partita della rosa tiene i widget attenti da 10 minuti prima del calcio d'inizio a 4 ore e 15 dopo, due giri di voti",
          arguments: [("2026-11-01 14:49", false), ("2026-11-01 14:50", true), ("2026-11-01 15:00", true),
                      ("2026-11-01 17:30", true), ("2026-11-01 19:00", true), ("2026-11-01 19:14", true),
                      ("2026-11-01 19:15", false)])
    func finestra(adesso: String, attenta: Bool) throws {
        let w = try riassunto(["2026-11-01 15:00", nil])
        let istante = try data(adesso)
        #expect(w.conPartite(adesso: istante) == attenta)
    }

    @Test("Ogni partita ha la sua finestra: fra una partita del pranzo e una della sera si torna alle ricariche di sempre")
    func piuPartite() throws {
        let w = try riassunto(["2026-11-01 12:30", "2026-11-01 20:45"])
        let alle1630 = try data("2026-11-01 16:30"), alle17 = try data("2026-11-01 17:00"), alle2040 = try data("2026-11-01 20:40")
        #expect(w.conPartite(adesso: alle1630), "il secondo giro dei voti della partita delle 12:30 è alle 16:30")
        #expect(w.conPartite(adesso: alle17) == false)
        #expect(w.conPartite(adesso: alle2040))
    }

    @Test("Senza orari nella rosa (rosa vuota, partita senza data, server di prima) niente partite")
    func senzaOrari() throws {
        let alle15 = try data("2026-11-01 15:00")
        let senzaData = try riassunto([nil]), vuota = try riassunto([])
        let vecchio = try #require(RiassuntoWidget.leggi(Data(#"{"giornata": 11}"#.utf8)))
        #expect(senzaData.conPartite(adesso: alle15) == false)
        #expect(vuota.conPartite(adesso: alle15) == false)
        #expect(vecchio.conPartite(adesso: alle15) == false)
    }

    @Test("La prossima ricarica arriva quando si apre la finestra della prossima partita, 10 minuti prima del calcio d'inizio")
    func prossimaFinestra() throws {
        let w = try riassunto(["2026-11-01 20:45", "2026-11-01 15:00", nil])
        let alle12 = try data("2026-11-01 12:00"), alle21 = try data("2026-11-01 21:00")
        let alle1450 = try data("2026-11-01 14:50"), alle2035 = try data("2026-11-01 20:35")
        #expect(w.prossimaFinestra(dopo: alle12) == alle1450)
        #expect(w.prossimaFinestra(dopo: alle1450) == alle2035, "una finestra già aperta non conta")
        #expect(w.prossimaFinestra(dopo: alle21) == nil)
    }

    // MARK: l'intervallo

    /// `ore`: quanto manca alla scadenza della formazione (negativo: è passata).
    @Test("Senza partite: più spesso man mano che la scadenza si avvicina, ogni quarto d'ora nelle 3 ore dopo, poi ogni mezz'ora",
          arguments: [(48.0, 30.0), (23.0, 20.0), (2.0, 10.0), (-1.0, 15.0), (-4.0, 30.0)])
    func senzaPartite(ore: Double, minuti: Double) {
        let scadenza = Self.adesso.addingTimeInterval(ore * 3600)
        #expect(RicaricaWidget.minuti(adesso: Self.adesso, scadenza: scadenza, partite: false) == minuti)
    }

    @Test("Con una partita della rosa ogni 15 minuti, non più ogni 2; a meno di 3 ore dalla scadenza restano 10",
          arguments: [(48.0, 15.0), (23.0, 15.0), (2.0, 10.0), (-1.0, 15.0), (-4.0, 15.0)])
    func conPartite(ore: Double, minuti: Double) {
        let scadenza = Self.adesso.addingTimeInterval(ore * 3600)
        #expect(RicaricaWidget.minuti(adesso: Self.adesso, scadenza: scadenza, partite: true) == minuti)
    }

    @Test("Senza scadenza nota ogni mezz'ora, con una partita della rosa ogni 15 minuti")
    func senzaScadenza() {
        #expect(RicaricaWidget.minuti(adesso: Self.adesso, scadenza: nil, partite: false) == 30)
        #expect(RicaricaWidget.minuti(adesso: Self.adesso, scadenza: nil, partite: true) == RicaricaWidget.minutiPartite)
        #expect(RicaricaWidget.minutiPartite == 15)
    }
}
