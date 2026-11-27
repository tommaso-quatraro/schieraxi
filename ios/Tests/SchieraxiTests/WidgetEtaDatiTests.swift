import Foundation
import Testing
@testable import Schieraxi

/// I widget dicono di quando sono i dati anche quando sono arrivati bene ma sono vecchi: iOS decide quando ricaricare un widget e
/// può rimandare di ore. Prima l'ora si vedeva solo con la copia salvata (server che non risponde), e a partite in corso i punti
/// di un'ora prima sembravano attuali. Soglie: 15 minuti con una partita in gioco o che sta per iniziare (il widget chiede di
/// ricaricare ogni 2 minuti), un'ora negli altri momenti (ogni 10-30 minuti). La riga è quella della copia (`RigaCopia`,
/// `ParoleWidget.datiSalvati`): va a capo, mai «…». Ore inventate.
@Suite("Widget: l'età dei dati quando iOS rimanda gli aggiornamenti")
struct WidgetEtaDatiTests {
    private static let scaricati = Date(timeIntervalSince1970: 1_795_000_000)

    private func dopo(_ minuti: Double) -> Date { Self.scaricati.addingTimeInterval(minuti * 60) }

    @Test("La copia salvata dice sempre di quando è, anche appena letta")
    func copia() {
        #expect(EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(1), copia: true, partite: false) == Self.scaricati)
        #expect(EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(1), copia: true, partite: true) == Self.scaricati)
    }

    @Test("Con una partita in gioco i dati arrivati bene dicono la loro ora da 15 minuti in poi",
          arguments: [(0.0, false), (10.0, false), (14.9, false), (15.0, true), (40.0, true)])
    func partite(minuti: Double, conOra: Bool) {
        let ora = EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(minuti), copia: false, partite: true)
        #expect(ora == (conOra ? Self.scaricati : nil))
    }

    @Test("Senza partite in gioco da un'ora in poi", arguments: [(15.0, false), (30.0, false), (59.0, false), (60.0, true), (180.0, true)])
    func fuoriDallePartite(minuti: Double, conOra: Bool) {
        let ora = EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(minuti), copia: false, partite: false)
        #expect(ora == (conOra ? Self.scaricati : nil))
    }

    @Test("La timeline ha una voce quando i dati diventano vecchi: senza, se iOS rimanda, resta la voce di prima senza l'ora")
    func istanti() {
        #expect(EtaDatiWidget.istanti(scaricatoIl: Self.scaricati, adesso: dopo(0)) == [dopo(15), dopo(60)])
        #expect(EtaDatiWidget.istanti(scaricatoIl: Self.scaricati, adesso: dopo(20)) == [dopo(60)])
        #expect(EtaDatiWidget.istanti(scaricatoIl: Self.scaricati, adesso: dopo(90)).isEmpty)
    }
}
