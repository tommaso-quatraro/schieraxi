import Foundation
import Testing
@testable import Schieraxi

/// La frase sull'indice in fondo alla Formazione (parte di #167). Dalla grafica B della web (#410) sul volto c'è il numero
/// dell'indice, e la web lo dice con `formazione.numero_sulla_maglia`. Anche sull'iPhone il numero sta sul volto (un cartellino
/// sull'avatar, con l'anello attorno, che è una differenza grafica ammessa): la frase deve essere la stessa, parola per parola,
/// così una frase cambiata su un lato solo fa fallire il test. La seconda frase della web («Tocca il fantavoto atteso…») sull'iPhone
/// ha il suo posto prima («Toccalo per sapere perché.»): qui conta la prima.
@MainActor
@Suite("Frase sull'indice sotto la Formazione come la web")
struct FraseIndiceComeLaWebTests {
    /// La prima frase del testo della web, con il suo punto: «Negli elenchi il numero sul volto è l'indice: 100 = …».
    private func fraseDellaWeb() throws -> String {
        let testo = try TestiWeb().italiano("formazione.numero_sulla_maglia")
        let fine = try #require(testo.range(of: ". "), "la web non ha più due frasi in formazione.numero_sulla_maglia: aggiorna questo test")
        return String(testo[..<fine.upperBound]).trimmingCharacters(in: .whitespaces)
    }

    @Test("La legenda della Formazione dice l'indice con la frase della web, con e senza «Toccalo per sapere perché»", arguments: [true, false])
    func fraseUguale(conPerche: Bool) throws {
        let web = try fraseDellaWeb()
        #expect(web.contains("numero sul volto"), "la frase della web è cambiata: \(web)")
        #expect(FormazioneView.legenda(conPerche: conPerche).contains(web))
    }

    @Test("La legenda non parla più dell'anello: il numero sul volto è l'indice", arguments: [true, false])
    func senzaAnello(conPerche: Bool) {
        #expect(!FormazioneView.legenda(conPerche: conPerche).localizedCaseInsensitiveContains("anello"))
    }
}
