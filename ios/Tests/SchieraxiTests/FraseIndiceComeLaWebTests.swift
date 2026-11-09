import Foundation
import Testing
@testable import Schieraxi

/// La frase sull'indice in fondo alla Formazione (parte di #167). Dalla grafica B della web (#410) sul volto c'è il numero
/// dell'indice, e la web lo dice con `formazione.numero_sulla_maglia`. Anche sull'iPhone il numero sta sul volto (un cartellino
/// sull'avatar, con l'anello attorno, che è una differenza grafica ammessa): la frase deve essere la stessa, parola per parola, e dal
/// #495 arriva dal catalogo comune (`Catalogo.Formazione.numeroSullaMaglia`). La seconda frase della web («Tocca il fantavoto
/// atteso…») sull'iPhone ha il suo posto prima («Toccalo per sapere perché.»): qui conta la prima.
@MainActor
@Suite("Frase sull'indice sotto la Formazione come la web")
struct FraseIndiceComeLaWebTests {
    /// La prima frase del testo del catalogo, con il suo punto: «Negli elenchi il numero sul volto è l'indice: 100 = …».
    private func fraseDelCatalogo() throws -> String {
        let testo = Catalogo.Formazione.numeroSullaMaglia
        let fine = try #require(testo.range(of: ". "), "il catalogo non ha più due frasi in formazione.numero_sulla_maglia: aggiorna questo test")
        return String(testo[..<fine.upperBound]).trimmingCharacters(in: .whitespaces)
    }

    @Test("La legenda della Formazione dice l'indice con la frase della web, con e senza «Toccalo per sapere perché»", arguments: [true, false])
    func fraseUguale(conPerche: Bool) throws {
        let frase = try fraseDelCatalogo()
        #expect(frase.contains("numero sul volto"), "la frase del catalogo è cambiata: \(frase)")
        #expect(FormazioneView.legenda(conPerche: conPerche).contains(frase))
    }

    @Test("La legenda non parla più dell'anello: il numero sul volto è l'indice", arguments: [true, false])
    func senzaAnello(conPerche: Bool) {
        #expect(!FormazioneView.legenda(conPerche: conPerche).localizedCaseInsensitiveContains("anello"))
    }
}
