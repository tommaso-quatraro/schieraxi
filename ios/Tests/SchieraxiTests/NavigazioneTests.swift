import Foundation
import SwiftUI
import Testing
@testable import Schieraxi

/// La barra a tre voci come la web (#673 passo 3, web #675): Formazione, Giornate, Impostazioni, più la ricerca. Squadra e Altro non
/// sono più schede: i loro nomi (indirizzi `schieraxi://`, «Da fare», l'ultima sezione salvata, gli avvisi che li aprivano) portano alle
/// Impostazioni, su La mia lega o sulla pagina giusta. L'ultima sezione si ricorda solo per Formazione e Giornate.
@MainActor
@Suite(.serialized)
struct NavigazioneTests {
    private func vai(_ testo: String) -> Destinazione? {
        URL(string: testo).flatMap { Collegamenti.interpreta($0) }
    }

    @Test("La barra ha tre voci, in quest'ordine, con i nomi del catalogo e Cmd+1…3")
    func barra() {
        #expect(Sezione.allCases == [.formazione, .giornate, .impostazioni])
        #expect(Sezione.allCases.map(\.titolo) == [Catalogo.Nav.formazione, Catalogo.Nav.giornate, Catalogo.Shell.impostazioni])
        #expect(Sezione.allCases.map(\.scorciatoia) == ["1", "2", "3"])
        #expect(Sezione.cerca.titolo == Catalogo.Shell.cerca, "la ricerca è una voce a parte, non fra le tre")
    }

    @Test("I nomi di Squadra, Altro e delle pagine tolte aprono le Impostazioni",
          arguments: ["squadra", "Squadra", "mercato", "altro", "lega", "scambi", "impostazioni"])
    func nomiVecchi(nome: String) {
        #expect(Sezione.da(nome: nome) == .impostazioni)
    }

    @Test("Oggi, Formazione, Diario e Giornate restano dove erano")
    func nomiCheRestano() {
        #expect(Sezione.da(nome: "oggi") == .formazione)
        #expect(Sezione.da(nome: "formazione") == .formazione)
        #expect(Sezione.da(nome: "diario") == .giornate)
        #expect(Sezione.da(nome: "giornate") == .giornate)
        #expect(Sezione.da(nome: "boh") == nil)
        #expect(Sezione.da(nome: nil) == nil)
    }

    @Test("Gli indirizzi di Squadra e Altro aprono le Impostazioni su La mia lega", arguments: [
        "schieraxi://squadra", "schieraxi://mercato", "schieraxi://altro", "schieraxi://lega", "schieraxi://scambi", "SCHIERAXI://Lega",
    ])
    func indirizziDellaLega(indirizzo: String) {
        #expect(vai(indirizzo) == .impostazioni(.lega))
    }

    @Test("Gli indirizzi delle pagine aprono la pagina giusta delle Impostazioni")
    func indirizziDellePagine() {
        #expect(vai("schieraxi://impostazioni") == .impostazioni(nil))
        #expect(vai("schieraxi://lega/rose") == .pagina(.importa))
        #expect(vai("schieraxi://lega/regole") == .pagina(.regole))
        #expect(vai("schieraxi://altro/regole") == .pagina(.regole))
        #expect(vai("schieraxi://impostazioni/installazione") == .pagina(.gestione))
        #expect(vai("schieraxi://impostazioni/avvisi") == .impostazioni(.avvisi))
    }

    @Test("Formazione, Giornate, giocatore e widget non cambiano")
    func indirizziCheRestano() {
        #expect(vai("schieraxi://oggi") == .sezione(.formazione))
        #expect(vai("schieraxi://formazione") == .sezione(.formazione))
        #expect(vai("schieraxi://giornate") == .sezione(.giornate))
        #expect(vai("schieraxi://lega/diario") == .sezione(.giornate))
        #expect(vai("schieraxi://altro/diario") == .sezione(.giornate))
        #expect(vai("schieraxi://giocatore/203") == .giocatore(203))
        #expect(vai("schieraxi://widget/collega") == .collegaWidget)
        #expect(vai("schieraxi://boh") == nil)
    }

    @Test("Una voce di «Da fare» che portava a Squadra o ad Altro apre La mia lega o la sua pagina")
    func daFare() {
        #expect(DestinazioneDaFare(sezione: "lega").destinazione == .impostazioni(.lega))
        #expect(DestinazioneDaFare(sezione: "squadra").destinazione == .impostazioni(.lega))
        #expect(DestinazioneDaFare(sezione: "formazione").destinazione == .sezione(.formazione))
        #expect(DestinazioneDaFare(scheda: "lega", sezione: "rose", link: "schieraxi://lega/rose").destinazione == .pagina(.importa))
    }

    @Test("All'avvio si torna solo su Formazione o Giornate: le schede di prima aprono la Formazione",
          arguments: [("squadra", Sezione.formazione), ("altro", .formazione), ("mercato", .formazione), ("lega", .formazione),
                      ("impostazioni", .formazione), ("oggi", .formazione), ("giornate", .giornate), ("diario", .giornate)])
    func avvio(salvata: String, attesa: Sezione) throws {
        let memoria = try #require(UserDefaults(suiteName: "prova-avvio-\(UUID().uuidString)"))
        memoria.set(salvata, forKey: "ultimaSezione")
        #expect(Navigazione.sezioneDiAvvio(memoria) == attesa)
    }

    @Test("Aprire le Impostazioni o la ricerca non cambia l'ultima sezione ricordata")
    func ultimaSezione() {
        let prima = UserDefaults.standard.string(forKey: "ultimaSezione")
        defer { UserDefaults.standard.set(prima, forKey: "ultimaSezione") }
        let nav = Navigazione()
        nav.sezione = .giornate
        #expect(UserDefaults.standard.string(forKey: "ultimaSezione") == "giornate")
        nav.sezione = .impostazioni
        nav.sezione = .cerca
        #expect(UserDefaults.standard.string(forKey: "ultimaSezione") == "giornate")
    }

    @Test("Le Impostazioni su La mia lega: si apre la voce e si ricorda dove portarla")
    func vaiAllaLega() {
        let prima = UserDefaults.standard.string(forKey: "ultimaSezione")
        defer { UserDefaults.standard.set(prima, forKey: "ultimaSezione") }
        let nav = Navigazione()
        nav.vai(a: .impostazioni(.lega))
        #expect(nav.sezione == .impostazioni)
        #expect(nav.parteImpostazioni == .lega)
        nav.vai(a: .pagina(.regole))
        #expect(nav.paginaDaAprire == .regole)
    }

    @Test("Ogni pagina della lega si apre nelle Impostazioni, con quelle che ci stanno sopra")
    func apriPagina() {
        let lega = LegaViewModel(server: FinteServer(risposte: [:]))
        #expect(lega.apri([.squadre, .rosa("X")]) == .impostazioni)
        #expect(lega.percorso == [.squadre, .rosa("X")])
        #expect(lega.apri([.importa]) == .impostazioni)
        #expect(lega.percorso == [.importa])
    }

    @Test("«Com'è andata» apre Giornate con la giornata da aprire")
    func comeAndata() {
        let prima = UserDefaults.standard.string(forKey: "ultimaSezione")
        defer { UserDefaults.standard.set(prima, forKey: "ultimaSezione") }
        let nav = Navigazione()
        nav.apriGiornate(11)
        #expect(nav.sezione == .giornate)
        #expect(nav.giornataDaAprire == 11)
    }
}
