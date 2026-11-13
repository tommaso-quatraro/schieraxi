import Foundation
import Testing
@testable import Schieraxi

/// La ricerca di un giocatore come la web (#673 passo 3, decisione 3 della #677): ruolo, nome, club e quotazione da `/api/giocatori`,
/// senza fantavoto atteso né «gioca N%» (niente più scarico dell'elenco largo della giornata). Testi dal catalogo.
@Suite("Ricerca come la web")
struct RicercaComeLaWebTests {
    @Test("Una riga: nome, ruolo, club e «quotazione N»")
    func riga() {
        let r = DatiRigaRicerca(GiocatoreBreve(id: 7, nome: "Leonel Marténi", ruolo: "A", squadra: "INT", quotazione: 31))
        #expect(r.nome == "Leonel Marténi")
        #expect(r.ruolo == "A")
        #expect(r.club == "INT")
        #expect(r.quotazione == Catalogo.Avv.quot(n: "31"))
        #expect(r.voce == "Leonel Marténi, \(nomeRuolo("A")), INT, \(Catalogo.Avv.quot(n: "31"))")
    }

    @Test("Il club è la sigla, come nel listone della web")
    func sigla() {
        #expect(DatiRigaRicerca(GiocatoreBreve(id: 9, nome: "Fosola", ruolo: "C", squadra: "inter", quotazione: 4)).club == "INT")
    }

    @Test("Senza quotazione né club: «–» e niente club")
    func senzaDati() {
        let r = DatiRigaRicerca(GiocatoreBreve(id: 8, nome: "Sorvani", ruolo: "P", squadra: nil, quotazione: nil))
        #expect(r.club.isEmpty)
        #expect(r.quotazione == Catalogo.Avv.quot(n: "–"))
    }

    @Test("Al massimo 12 risultati, come la web, e i testi d'attesa del catalogo")
    func limiteETesti() {
        #expect(RicercaViewModel.limite == 12)
        #expect(RicercaViewModel.percorso("Leo") == "/api/giocatori?limite=12&q=Leo")
        #expect(RicercaViewModel.testoVuoto == Catalogo.Avv.scriviAlmenoDue)
        #expect(RicercaViewModel.testoNessuno == Catalogo.Avv.nessunGiocatoreTrovato)
    }
}
