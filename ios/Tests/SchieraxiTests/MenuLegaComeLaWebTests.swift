import Foundation
import Testing
@testable import Schieraxi

// Issue #304 e #634. I menu Squadra e Altro dell'iPhone sono quelli della web: stesse voci, stesso ordine, stessi testi di
// `VOCI_LEGA` in `fanta/web/app.js` (nomi e righe sotto dal catalogo comune, #496). Dal 12/11/2026 la web ha quattro voci (#615) e
// l'iPhone la segue (#634): Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario, Scambi, Movimenti, Crediti, Nuova
// stagione e Novità non sono più voci di menu. Con #671 il Diario è la pagina Giornate della barra e l'iPhone la segue (#673 passo
// 2): in Altro restano le Regole. La web non si legge: le sue voci sono copiate ferme qui sotto.

/// Una voce di `VOCI_LEGA` della web com'è fra #671 e #675: `{ id, ambito, nome: t("lega.voce_…"), sub: t("lega.voce_…_sub") }`.
private struct VoceWeb: Sendable {
    let id: String
    let scheda: Sezione
    let nome: String
    let dettaglio: String
}

private let vociWeb: [VoceWeb] = [
    VoceWeb(id: "squadre", scheda: .squadra, nome: Catalogo.Lega.voceSquadre, dettaglio: Catalogo.Lega.voceSquadreSub),
    VoceWeb(id: "importa", scheda: .squadra, nome: Catalogo.Lega.voceImporta, dettaglio: Catalogo.Lega.voceImportaSub),
    VoceWeb(id: "regole", scheda: .altro, nome: Catalogo.Lega.voceRegole, dettaglio: Catalogo.Lega.voceRegoleSub),
]

/// Le voci tolte il 12/11/2026: nessuna deve tornare in un menu.
private let vociTolte = ["consigli", "osservati", "giocatori", "calendario", "scambi", "movimenti", "crediti", "stagione", "novita",
                         "diario"]

/// Le funzioni che il server spegneva per nascondere una voce di menu (`f` di `VOCI_LEGA` prima del 12/11/2026).
private let funzioniDelleVoci = ["seguiti", "elenco_giocatori", "diario", "movimenti", "crediti", "novita"]

@Suite("Menu Squadra e Altro come la web (#304, #634)")
struct MenuLegaComeLaWebTests {
    @Test("Stesse voci e stesso ordine di VOCI_LEGA", arguments: [Sezione.squadra, .altro])
    func stesseVociStessoOrdine(scheda: Sezione) {
        let attese = vociWeb.filter { $0.scheda == scheda }.map(\.id)
        #expect(VoceMenuLega.voci(scheda, funzioni: .tutteAccese).map(\.id) == attese)
        #expect(VoceMenuLega.tutte(scheda).map(\.id) == attese)
    }

    @Test("Nomi e righe sotto sono quelli del catalogo, nello stesso ordine", arguments: [Sezione.squadra, .altro])
    func testiComeLaWeb(scheda: Sezione) {
        let attese = vociWeb.filter { $0.scheda == scheda }.map { [$0.id, $0.nome, $0.dettaglio] }
        #expect(VoceMenuLega.tutte(scheda).map { [$0.id, $0.nome, $0.dettaglio] } == attese)
    }

    @Test("Ogni voce apre la pagina della sua scheda")
    func pagineDelleVoci() {
        #expect(VoceMenuLega.tutte(.squadra).map(\.pagina) == [.squadre, .importa])
        #expect(VoceMenuLega.tutte(.altro).map(\.pagina) == [.regole])
        for scheda in [Sezione.squadra, .altro] {
            #expect(VoceMenuLega.tutte(scheda).allSatisfy { $0.pagina.sezione == scheda })
        }
    }

    @Test("Nessuna delle voci tolte è in un menu", arguments: [Sezione.squadra, .altro])
    func nienteVociTolte(scheda: Sezione) {
        let ids = VoceMenuLega.tutte(scheda).map(\.id)
        #expect(ids.filter { vociTolte.contains($0) }.isEmpty)
    }

    @Test("Le voci si vedono anche con le funzioni del server spente: nessuna dipende da un interruttore",
          arguments: [Sezione.squadra, .altro])
    func nessunaFunzioneLeNasconde(scheda: Sezione) {
        let spente = StatoFunzioni(scelte: Dictionary(uniqueKeysWithValues: funzioniDelleVoci.map { ($0, false) }))
        #expect(VoceMenuLega.voci(scheda, funzioni: spente).map(\.id) == vociWeb.filter { $0.scheda == scheda }.map(\.id))
    }

    @Test("Senza «Squadre della lega» la prima voce di Squadra è «La mia squadra e rosa», come la web")
    func laMiaSquadra() throws {
        let senzaAltre = StatoFunzioni(scelte: [Funzione.squadreAltrui: false])
        let prima = try #require(VoceMenuLega.voci(.squadra, funzioni: senzaAltre).first)
        #expect(prima.id == "squadre")
        #expect(prima.pagina == .squadre)
        #expect(prima.nome == Catalogo.Lega.voceMiasquadra)
        #expect(prima.dettaglio == Catalogo.Lega.voceMiasquadraSub)
        #expect(VoceMenuLega.voci(.squadra, funzioni: senzaAltre).map(\.id) == ["squadre", "importa"])
    }
}
