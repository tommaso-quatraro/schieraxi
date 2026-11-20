import Foundation
import Testing
@testable import Schieraxi

/// Le Impostazioni in una pagina sola, come `paginaImpostazioni` della web (#673 passo 3, web #675): in La mia lega «Aggiorna le
/// rose», «La mia squadra» (con le rose), «Regole e scadenza», «Le altre squadre» (con più squadre e la funzione `squadre_altrui`);
/// poi «Il tuo account» con gli account, «Informazioni» e «Gestione» solo per chi gestisce il server. Nomi e righe sotto dal catalogo.
@MainActor
@Suite("Impostazioni come la web")
struct ImpostazioniComeLaWebTests {
    private func squadre(_ n: Int, mia: Int? = nil) -> [SquadraLega] {
        (0..<n).map { i in SquadraLega(nome: "Squadra \(i + 1)", mia: i == mia, giocatori: nil, creditiResidui: nil, immagini: nil) }
    }

    @Test("Senza rose: «Aggiorna le rose» e «Regole e scadenza»")
    func senzaRose() {
        let voci = VociImpostazioni.lega(squadre: [], squadreAltrui: true)
        #expect(voci.map(\.id) == ["rose", "regole"])
    }

    @Test("Con più squadre e la funzione accesa: le quattro voci, nell'ordine della web")
    func conPiuSquadre() {
        let voci = VociImpostazioni.lega(squadre: squadre(8, mia: 2), squadreAltrui: true)
        #expect(voci.map(\.id) == ["rose", "squadra", "regole", "squadre"])
        #expect(voci.map(\.pagina) == [.importa, .rosa("Squadra 3"), .regole, .squadre])
    }

    @Test("Nomi e righe sotto vengono dal catalogo")
    func testi() {
        let voci = VociImpostazioni.lega(squadre: squadre(8, mia: 2), squadreAltrui: true)
        #expect(voci.map(\.nome) == [Catalogo.Lega.voceImporta, Catalogo.Lega.miaSquadra, Catalogo.Imp.regole, Catalogo.Imp.altreSquadre])
        // otto squadre, una è la mia: le altre sono sette (#788, come la web)
        #expect(voci.map(\.sotto) == [Catalogo.Lega.voceImportaSub, "Squadra 3", Catalogo.Imp.regoleSub, Catalogo.Lega.nSquadre(7)])
    }

    /// Foto del 20/11 (#787, punto 5) e #788: «Le altre squadre · 8 squadre» quando le altre erano 7. Come la web (#779): numero
    /// ed elenco senza la mia; finché la mia non è scelta, tutte (lì si sceglie la propria).
    @Test("«Le altre squadre»: con quattro squadre e la mia scelta conta e mostra le altre tre")
    func altreSenzaLaMia() throws {
        let quattro = squadre(4, mia: 1)
        let voce = try #require(VociImpostazioni.lega(squadre: quattro, squadreAltrui: true).first { $0.id == "squadre" })
        #expect(voce.sotto == Catalogo.Lega.nSquadre(3))
        let altre = VociImpostazioni.altreSquadre(quattro)
        #expect(altre.map(\.nome) == ["Squadra 1", "Squadra 3", "Squadra 4"])
        #expect(!altre.contains { $0.mia == true })
    }

    @Test("«Le altre squadre» senza la mia scelta: tutte, nel numero e nell'elenco")
    func altreSenzaSceltaTutte() throws {
        let quattro = squadre(4)
        let voce = try #require(VociImpostazioni.lega(squadre: quattro, squadreAltrui: true).first { $0.id == "squadre" })
        #expect(voce.sotto == Catalogo.Lega.nSquadre(4))
        #expect(VociImpostazioni.altreSquadre(quattro).count == 4)
        // due squadre, una è la mia: «1 squadra», al singolare
        let due = try #require(VociImpostazioni.lega(squadre: squadre(2, mia: 0), squadreAltrui: true).first { $0.id == "squadre" })
        #expect(due.sotto == Catalogo.Lega.nSquadre(1))
    }

    @Test("La mia squadra non ancora scelta: lo dice, e la voce apre l'elenco per sceglierla")
    func senzaMiaSquadra() throws {
        let voci = VociImpostazioni.lega(squadre: squadre(4), squadreAltrui: true)
        let mia = try #require(voci.first { $0.id == "squadra" })
        #expect(mia.sotto == Catalogo.Imp.miaSquadraNessuna)
        #expect(mia.pagina == .squadre)
    }

    @Test("Le altre squadre solo con più di una squadra e con la funzione accesa")
    func altreSquadre() {
        #expect(!VociImpostazioni.lega(squadre: squadre(8, mia: 0), squadreAltrui: false).contains { $0.id == "squadre" })
        #expect(!VociImpostazioni.lega(squadre: squadre(1, mia: 0), squadreAltrui: true).contains { $0.id == "squadre" })
        #expect(VociImpostazioni.lega(squadre: squadre(2, mia: 0), squadreAltrui: true).contains { $0.id == "squadre" })
    }

    @Test("«Il tuo account» solo con un account, con sotto il nome")
    func account() {
        #expect(VociImpostazioni.account(nome: nil) == nil)
        let voce = VociImpostazioni.account(nome: "Mister Rossi")
        #expect(voce?.nome == Catalogo.Imp.account)
        #expect(voce?.sotto == "Mister Rossi")
        #expect(voce?.pagina == .account)
    }

    @Test("Gestione è invisibile a un utente normale; Informazioni c'è per tutti")
    func gestione() throws {
        #expect(VociImpostazioni.informazioni(gestisce: false).map(\.id) == ["informazioni"])
        #expect(VociImpostazioni.informazioni(gestisce: true).map(\.id) == ["informazioni", "gestione"])
        let voci = VociImpostazioni.informazioni(gestisce: true)
        #expect(voci.map(\.nome) == [Catalogo.Imp.informazioni, Catalogo.Imp.gestione])
        // la Gestione dell'iPhone non ha inviti né utenti (quelli sono della web): la riga sotto dice solo ciò che c'è
        #expect(voci.map(\.sotto) == [Catalogo.Imp.informazioniSub, "\(Catalogo.Shell.aggiorna) · \(Catalogo.Av.stato)"])
        let sottoGestione = try #require(voci.last?.sotto)
        #expect(!sottoGestione.contains("Inviti"))
        #expect(voci.map(\.pagina) == [.informazioni, .gestione])
    }

    @Test("Le ore tranquille dicono la fascia scelta, con le ore del server")
    func oreTranquille() {
        let ore = OreTranquille(attive: true, da: 22, a: 8)
        #expect(AvvisiDispositivoViewModel.aiutoOreTranquille(ore) == Catalogo.Imp.oreTranquilleAiuto(a: "8", da: "22"))
    }
}
