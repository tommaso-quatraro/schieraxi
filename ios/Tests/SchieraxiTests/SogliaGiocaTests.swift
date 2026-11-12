import Foundation
import Testing
@testable import Schieraxi

/// «gioca N%» conta solo sotto l'80% (arancio fra 50 e 79, rosso sotto 50) e si decide sul numero che si legge, come
/// `SOGLIA_GIOCA`, `SOGLIA_BASSA` e `giocaLetto` di app.js (#616): 79,6% si scrive «80%» e non è «sotto l'80%».
/// Un tipo solo in `Domain/`, per la scheda del giocatore e poi per pedina e sostituti.
@Suite("Soglia di «gioca N%» come la web")
struct SogliaGiocaTests {
    @Test("Le soglie della web: 0,8 e 0,5")
    func soglie() {
        #expect(SogliaGioca.alta == 0.8)
        #expect(SogliaGioca.bassa == 0.5)
    }

    @Test("Il livello si decide sul numero arrotondato al centesimo",
          arguments: zip([0.92, 0.8, 0.796, 0.794, 0.62, 0.5, 0.497, 0.493, 0.2, 0.0],
                         [SogliaGioca.Livello.sicuro, .sicuro, .sicuro, .medio, .medio, .medio, .medio, .basso, .basso, .basso]))
    func livello(p: Double, atteso: SogliaGioca.Livello) {
        #expect(SogliaGioca.livello(p) == atteso, "\(p)")
    }

    @Test("«gioca N%» si mostra solo sotto l'80%, letto come lo legge l'utente")
    func daMostrare() {
        #expect(!SogliaGioca.daMostrare(0.85))
        #expect(!SogliaGioca.daMostrare(0.796), "si legge «80%»: non è sotto l'80%")
        #expect(SogliaGioca.daMostrare(0.79))
        #expect(SogliaGioca.daMostrare(0.3))
    }

    @Test("Senza probabilità vale 0, come `p_voto ?? 0` della web")
    func senzaProbabilita() {
        #expect(SogliaGioca.letta(nil) == 0)
        #expect(SogliaGioca.livello(nil) == .basso)
        #expect(SogliaGioca.letta(.nan) == 0)
    }

    @Test("Il numero letto è arrotondato al centesimo")
    func letta() {
        #expect(SogliaGioca.letta(0.796) == 0.8)
        #expect(SogliaGioca.letta(0.621) == 0.62)
    }

    // MARK: pedina e righe (sostituti compresi) con la stessa soglia della scheda

    @Test("Un titolare al 75%: avviso sul campo e arancio nella scheda; al 45% rosso; a 79,6% nessun avviso")
    func pedina() {
        #expect(LetturaPedina.incerto(0.75))
        #expect(LetturaPedina.livello(0.75) == .medio)
        #expect(LetturaPedina.livello(0.45) == .basso)
        #expect(!LetturaPedina.incerto(0.796), "si legge «80%»")
        #expect(LetturaPedina.livello(0.92) == .sicuro)
        #expect(LetturaPedina.livello(nil) == nil, "senza probabilità niente avviso")
        #expect(!LetturaPedina.incerto(nil))
    }

    /// Un giocatore inventato con questa probabilità di giocare (e altri campi, `extra` comincia con «, »).
    private func giocatore(_ p: Double, _ extra: String = "") throws -> Giocatore {
        try Decodifica.decodifica(Data(#"{"id": 9, "nome": "Paolo Esempio", "ruolo": "C", "fv_atteso": 6.4, "p_voto": \#(p)\#(extra)}"#.utf8))
    }

    @Test("Scheda, pedina e righe dicono la stessa cosa per la stessa probabilità",
          arguments: [0.95, 0.8, 0.796, 0.79, 0.75, 0.62, 0.5, 0.497, 0.45, 0.1])
    func stessaSogliaOvunque(p: Double) throws {
        let g = try giocatore(p)
        let attesa = SogliaGioca.livello(p)
        guard case .cifre(_, .gioca(_, let scheda, _)?) = LetturaScheda.cifre(g) else {
            Issue.record("la scheda non mostra «gioca N%» per \(p)")
            return
        }
        #expect(scheda == attesa)
        #expect(LetturaPedina.livello(p) == attesa)
        #expect(LetturaPedina.incerto(p) == (attesa != .sicuro))
        #expect(RigaGiocatore.livelloGioca(g) == (attesa == .sicuro ? nil : attesa), "riga (anche fra i sostituti) per \(p)")
    }

    @Test("Nelle righe niente colore a partita iniziata, per un assente e per chi non gioca di sicuro (lo dice la parola)")
    func righeSenzaColore() throws {
        let inCorso = try giocatore(0.4, #", "stato_partita": "in_corso""#)
        let assente = try giocatore(0.0, #", "assente": true"#)
        let infortunato = try giocatore(0.0, #", "stato": "infortunato""#)
        let dubbio = try giocatore(0.4, #", "dubbio": true"#)
        #expect(RigaGiocatore.livelloGioca(inCorso) == nil)
        #expect(RigaGiocatore.livelloGioca(assente) == nil)
        #expect(RigaGiocatore.livelloGioca(infortunato) == nil)
        #expect(RigaGiocatore.livelloGioca(dubbio) == .basso, "in dubbio non è sicuro di non giocare: il numero resta rosso")
    }
}
