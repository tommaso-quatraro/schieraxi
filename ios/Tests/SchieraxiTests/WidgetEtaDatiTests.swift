import Foundation
import Testing
@testable import Schieraxi

/// I widget dicono di quando sono i dati anche quando sono arrivati bene ma sono vecchi: iOS decide quando ricaricare un widget e
/// può rimandare di ore. Prima l'ora si vedeva solo con la copia salvata (server che non risponde), e a partite in corso i punti
/// di un'ora prima sembravano attuali. Soglie: 30 minuti con una partita della rosa (il widget chiede di ricaricare ogni 15
/// minuti, `RicaricaWidget`: oltre il doppio iOS ha rimandato), un'ora negli altri momenti (ogni 10-30 minuti). Fino al 27/11/2026
/// durante le partite il widget chiedeva ogni 2 minuti e la soglia era 15. La riga è quella della copia (`RigaCopia`,
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

    @Test("Con una partita della rosa i dati arrivati bene dicono la loro ora da 30 minuti in poi",
          arguments: [(0.0, false), (15.0, false), (29.9, false), (30.0, true), (40.0, true)])
    func partite(minuti: Double, conOra: Bool) {
        let ora = EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(minuti), copia: false, partite: true)
        #expect(ora == (conOra ? Self.scaricati : nil))
    }

    @Test("Senza partite da un'ora in poi", arguments: [(15.0, false), (30.0, false), (59.0, false), (60.0, true), (180.0, true)])
    func fuoriDallePartite(minuti: Double, conOra: Bool) {
        let ora = EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(minuti), copia: false, partite: false)
        #expect(ora == (conOra ? Self.scaricati : nil))
    }

    /// Se la ricarica chiesta con le partite cambiasse, la soglia deve seguirla: quando la ricarica è appena dovuta i dati non sono
    /// ancora «vecchi», quando è saltata un'intera volta sì.
    @Test("Con le partite l'ora non compare quando la ricarica è appena dovuta, compare quando ne è saltata una; fuori, dopo un'ora")
    func soglieComeLeRicariche() {
        let ricarica = RicaricaWidget.minutiPartite
        let dovuta = EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(ricarica), copia: false, partite: true)
        let saltata = EtaDatiWidget.ora(scaricatoIl: Self.scaricati, adesso: dopo(2 * ricarica), copia: false, partite: true)
        #expect(dovuta == nil)
        #expect(saltata == Self.scaricati)
        let piuLunga = RicaricaWidget.minuti(adesso: Self.scaricati, scadenza: nil, partite: false)
        #expect(EtaDatiWidget.soglia == 2 * piuLunga * 60)
    }

    @Test("La timeline ha una voce quando i dati diventano vecchi: senza, se iOS rimanda, resta la voce di prima senza l'ora")
    func istanti() {
        #expect(EtaDatiWidget.istanti(scaricatoIl: Self.scaricati, adesso: dopo(0)) == [dopo(30), dopo(60)])
        #expect(EtaDatiWidget.istanti(scaricatoIl: Self.scaricati, adesso: dopo(20)) == [dopo(30), dopo(60)])
        #expect(EtaDatiWidget.istanti(scaricatoIl: Self.scaricati, adesso: dopo(45)) == [dopo(60)])
        #expect(EtaDatiWidget.istanti(scaricatoIl: Self.scaricati, adesso: dopo(90)).isEmpty)
    }
}
