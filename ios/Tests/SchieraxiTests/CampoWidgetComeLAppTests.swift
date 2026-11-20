import Foundation
import Testing
@testable import Schieraxi

/// Il campo dei widget Formazione (medio, grande, extra large) nello stesso verso del campo dell'app e della web: attaccanti in
/// alto, portiere in basso. Foto del 20/11 (#787, punto 3): nel widget il portiere stava in alto. Dati inventati.
@MainActor
@Suite("Widget: il campo nello stesso verso dell'app")
struct CampoWidgetComeLAppTests {
    private func g(_ id: Int, _ ruolo: String?) -> GiocatoreWidget {
        GiocatoreWidget(id: id, nome: "Giocatore \(id)", ruolo: ruolo)
    }

    @Test("Le file del widget sono quelle del campo dell'app, nello stesso ordine")
    func stesseFile() {
        #expect(DisposizioneWidget.fileCampo == CampoFormazione.file)
    }

    @Test("Attaccanti nella prima fila, portiere nell'ultima; un ruolo che non è una fila va in attacco, come nell'app")
    func verso() throws {
        let titolari = [g(1, "P"), g(2, "D"), g(3, "D"), g(4, "C"), g(5, "A"), g(6, "a"), g(7, nil)]
        let righe = DisposizioneWidget.righeCampo(titolari)
        #expect(righe.map { $0.map(\.id) } == [[5, 6, 7], [4], [2, 3], [1]])
        #expect(try #require(righe.last).map(\.ruolo) == ["P"], "il portiere in basso")
        #expect(righe.flatMap { $0 }.count == titolari.count, "nessun titolare manca dal campo")
    }
}
