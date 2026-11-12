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
}
