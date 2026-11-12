import Foundation
import Testing
@testable import Schieraxi

/// Partite del turno di Oggi senza i risultati in diretta (funzione spenta o non raggiungibile), come `mostraOggi` della web
/// del 12/11/2026 (la web nuova non ha più le partite del turno; il suo codice non si legge più): una partita giocata ha
/// l'orario e il risultato del calendario (`punteggioUfficiale` di `fanta/web/live.js`, campi `gol_casa` e `gol_trasferta` di
/// `GET /api/oggi`); «Finita» solo se è finita per l'orario e il calendario non ha ancora il risultato. Prima
/// l'iPhone scriveva «Finita» senza il risultato. Con la diretta vince il punteggio in diretta. Dati inventati.
@MainActor
@Suite("Partite del turno: il risultato del calendario anche senza la diretta, come la web")
struct PartiteRisultatoUfficialeTests {
    private func partita(_ json: String) throws -> Partita { try Decodifica.decodifica(Data(json.utf8)) }

    private var giocata: Partita {
        Partita(data: "2026-11-05 20:45", casa: "inter", trasferta: "roma", giocata: true, stato: "finita", golCasa: 2, golTrasferta: 1)
    }

    /// I gol mostrati come testo («2–1»), nil se la colonna del punteggio resta vuota.
    private func gol(_ g: (casa: Int, trasferta: Int)?) -> String? { g.map { "\($0.casa)–\($0.trasferta)" } }

    @Test("Una partita giocata ha il risultato del calendario; una non giocata, un server vecchio o un valore strano no")
    func risultatoUfficiale() throws {
        let p = try partita(#"{"data": "2026-11-05 20:45", "casa": "inter", "trasferta": "roma", "giocata": true, "gol_casa": 2, "gol_trasferta": 1}"#)
        #expect(gol(p.punteggioUfficiale) == "2–1")
        let nonGiocata = try partita(#"{"data": "2026-11-06 18:00", "casa": "milan", "trasferta": "juventus", "giocata": false, "gol_casa": 1, "gol_trasferta": 0}"#)
        #expect(gol(nonGiocata.punteggioUfficiale) == nil, "il risultato del calendario vale solo per una partita giocata")
        let vecchio = try partita(#"{"data": "2026-11-05 20:45", "casa": "inter", "trasferta": "roma", "giocata": true}"#)
        #expect(gol(vecchio.punteggioUfficiale) == nil)
        let strano = try partita(#"{"data": "2026-11-05 20:45", "casa": "inter", "trasferta": "roma", "giocata": true, "gol_casa": "due", "gol_trasferta": 1}"#)
        #expect(gol(strano.punteggioUfficiale) == nil, "un valore strano non rompe la partita")
    }

    @Test("Senza la diretta la riga scrive l'ora e il risultato del calendario; «Finita» solo senza risultato, come la web")
    func senzaDiretta() {
        #expect(gol(RigaPartitaView.golMostrati(live: nil, partita: giocata)) == "2–1")
        #expect(RigaPartitaView.statoSenzaDiretta(giocata) == .ora)
        // finita per l'orario, ma il calendario non ha ancora il risultato
        let senzaRisultato = Partita(data: "2026-11-06 12:30", casa: "genoa", trasferta: "como", giocata: false, stato: "finita")
        #expect(RigaPartitaView.statoSenzaDiretta(senzaRisultato) == .finita)
        #expect(gol(RigaPartitaView.golMostrati(live: nil, partita: senzaRisultato)) == nil)
        let inCorso = Partita(data: "2026-11-06 18:00", casa: "milan", trasferta: "juventus", giocata: false, stato: "in_corso")
        #expect(RigaPartitaView.statoSenzaDiretta(inCorso) == .inCorso)
        let rinviata = Partita(data: nil, casa: "pisa", trasferta: "cremonese", giocata: false, stato: "rinviata")
        #expect(RigaPartitaView.statoSenzaDiretta(rinviata) == .rinviata)
        let daGiocare = Partita(data: "2026-11-06 20:45", casa: "napoli", trasferta: "atalanta", giocata: false, stato: "da_giocare")
        #expect(RigaPartitaView.statoSenzaDiretta(daGiocare) == .ora)
        #expect(gol(RigaPartitaView.golMostrati(live: nil, partita: daGiocare)) == nil)
    }

    @Test("Con la diretta vince il suo punteggio; una diretta senza punteggio non cancella quello del calendario")
    func conDiretta() {
        let live = PartitaLive(casa: "inter", trasferta: "roma", data: "2026-11-05 20:45", stato: "finita", golCasa: 3, golTrasferta: 1)
        #expect(gol(RigaPartitaView.golMostrati(live: live, partita: giocata)) == "3–1")
        let senzaGol = PartitaLive(casa: "inter", trasferta: "roma", data: "2026-11-05 20:45", stato: "da_giocare")
        #expect(gol(RigaPartitaView.golMostrati(live: senzaGol, partita: giocata)) == "2–1")
    }

    @Test("VoiceOver legge il risultato del calendario")
    func voce() {
        let frase = RigaPartitaView.voce(partita: giocata, live: nil, ora: "20:45", titolari: [])
        #expect(frase.hasPrefix("Inter 2, Roma 1, finita"), "«\(frase)»")
    }

    @Test("Nella demo a giornata in corso la partita finita ha in Oggi lo stesso risultato della diretta")
    func demoInCorso() async throws {
        let s = try #require(FinteServer.demoFase("oggi-in-corso", adesso: Date(timeIntervalSinceReferenceDate: 815_000_000)))
        let oggi: Oggi = try Decodifica.decodifica(try await s.richiesta("GET", "/api/oggi", corpo: nil))
        let live: LiveWidget = try Decodifica.decodifica(try await s.richiesta("GET", "/api/live", corpo: nil))
        let giocate = (oggi.partite ?? []).filter { $0.giocata == true }
        try #require(!giocate.isEmpty, "nessuna partita giocata a giornata in corso")
        for p in giocate {
            let l = try #require(DirettaLogica.dalVivo(live, per: p), "\(p.casa)-\(p.trasferta) non è nella diretta")
            #expect(gol(p.punteggioUfficiale) == l.punteggio, "\(p.casa)-\(p.trasferta): calendario \(gol(p.punteggioUfficiale) ?? "–"), diretta \(l.punteggio)")
        }
    }
}
