import SwiftUI
import Testing
@testable import Schieraxi

/// Le taglie del testo provate: normale e le due delle foto («testo grande» e «testo massimo»).
private let taglieProva: [DynamicTypeSize] = [.large, .accessibility2, .accessibility5]

/// Il nome di una squadra non va a capo a metà parola (issue #432). Nella foto `iphone_chiaro_testomassimo_lega-squadre`
/// (corsa 42193213289) «Schiera FC» con la pillola «tua» accanto si leggeva «Schier» e «a FC»: la pillola prendeva il suo
/// posto e al nome restava una colonna più stretta della parola più lunga. Ora il nome va a capo solo tra le parole, con la
/// colonna intera; se non c'è posto accanto, la pillola passa sotto. Una parola sola che sta quasi nella riga si rimpicciolisce
/// un poco (al massimo fino a 0,8) invece di spezzarsi.
/// Si misura con `ImageRenderer` (come `EtichetteIntereTests`): con una larghezza proposta l'immagine ha l'altezza che la vista
/// si prende. La riga è larga quanto la parola più lunga più 4 punti: lì la parola sta intera, ma non c'è posto per la pillola
/// accanto. Se la parola si spezza, la vista è più alta di almeno una riga rispetto al nome da solo. La pillola della prova è
/// un rettangolo vuoto, così la sua altezza non conta. Nomi inventati.
@Suite("Nome della squadra: a capo solo tra le parole")
struct NomeSquadraACapoTests {

    /// Larghezza della pillola della prova (la vera, «tua», è larga circa questo).
    private static let larghezzaPillola: CGFloat = 24

    /// La misura che la vista si prende quando la riga è larga `larghezza` punti (nil: tutto lo spazio che vuole).
    @MainActor
    private static func misura<V: View>(_ vista: V, larghezza: CGFloat?, taglia: DynamicTypeSize) -> CGSize {
        let disegno = ImageRenderer(content: vista.dynamicTypeSize(taglia))
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: nil)
        disegno.scale = 1
        return disegno.uiImage?.size ?? .zero
    }

    /// Altezza di una riga sola del carattere del nome.
    @MainActor
    private static func riga(_ taglia: DynamicTypeSize) -> CGFloat {
        misura(Text("Riga").font(.headline), larghezza: nil, taglia: taglia).height
    }

    /// Larghezza di una parola su una riga sola, nel carattere del nome.
    @MainActor
    private static func larghezzaParola(_ parola: String, _ taglia: DynamicTypeSize) -> CGFloat {
        misura(Text(parola).font(.headline).fixedSize(), larghezza: nil, taglia: taglia).width
    }

    /// Un rettangolo vuoto al posto della pillola: occupa larghezza, quasi niente altezza.
    private static func pillola(altezza: CGFloat = 1) -> some View {
        Color.clear.frame(width: larghezzaPillola, height: altezza)
    }

    @MainActor
    @Test("Con la pillola accanto il nome non si spezza: va a capo solo tra le parole e la pillola passa sotto",
          arguments: ["Schiera", "Schiera FC", "Real Madrink", "Gli Amici del Bar Sport Centrale"], taglieProva)
    func nonSiSpezza(nome: String, taglia: DynamicTypeSize) {
        let piuLunga = nome.split(separator: " ").map { Self.larghezzaParola(String($0), taglia) }.max() ?? 0
        let larghezza = piuLunga + 4
        let riga = Self.riga(taglia)
        let solo = Self.misura(Text(nome).font(.headline).fixedSize(horizontal: false, vertical: true),
                               larghezza: larghezza, taglia: taglia).height
        let conPillola = Self.misura(NomeConPillola(nome: nome) { Self.pillola() }, larghezza: larghezza, taglia: taglia).height
        #expect(riga > 0)
        #expect(solo >= riga, "il nome da solo è almeno una riga (alto \(solo), una riga \(riga))")
        #expect(conPillola < solo + riga * 0.5,
                "«\(nome)» in \(larghezza) punti con la pillola: alto \(conPillola), il nome da solo \(solo), una riga \(riga): una parola si è spezzata")
    }

    @MainActor
    @Test("Una parola sola che supera di poco la riga si rimpicciolisce invece di spezzarsi", arguments: taglieProva)
    func parolaSolaSiRimpicciolisce(taglia: DynamicTypeSize) {
        let nome = "Schiera"
        let larghezza = Self.larghezzaParola(nome, taglia) * 0.9
        let riga = Self.riga(taglia)
        let altezza = Self.misura(NomeConPillola(nome: nome) { Self.pillola() }, larghezza: larghezza, taglia: taglia).height
        #expect(altezza < riga * 1.5,
                "«\(nome)» in \(larghezza) punti: alto \(altezza), una riga \(riga): la parola è su più righe")
    }

    @MainActor
    @Test("Se c'è posto la pillola resta accanto al nome, sulla stessa riga")
    func pillolaAccanto() {
        let taglia = DynamicTypeSize.large
        let riga = Self.riga(taglia)
        let altezza = Self.misura(NomeConPillola(nome: "Schiera FC") { Self.pillola(altezza: 10) }, larghezza: 300, taglia: taglia).height
        #expect(abs(altezza - riga) < 2, "c'è posto: nome e pillola sulla stessa riga (alto \(altezza), una riga \(riga))")
    }
}
