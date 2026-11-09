import Foundation
import Testing
@testable import Schieraxi

// Regole, modificatore della difesa (#460): i campi di ogni fascia dicono a VoiceOver quale fascia sono, come la web (#454):
// «Fascia 2, media almeno», «Fascia 2, bonus», «Togli la fascia 2»; dopo «Togli» i numeri si rifanno. I quattro voti della prova
// hanno il loro nome: «Voto del portiere», «Voto del difensore 1/2/3». Il testo a vista resta quello di prima («Media almeno»,
// «bonus», «Togli la fascia»): cambia solo il nome letto da VoiceOver. Le frasi vengono dal catalogo comune (`Catalogo.Regole`,
// #496), con il numero al posto di `{n}`. Valori inventati, nessun dato vero.

@Suite("Regole: i nomi di VoiceOver delle fasce, come la web")
struct FasceVoiceOverTests {
    @Test("I tre controlli di una fascia hanno il nome della web, con il numero giusto", arguments: [1, 2, 3, 6, 10])
    func nomiComeLaWeb(n: Int) {
        let nomi = TestiRegole.nomiFascia(posto: n)
        #expect(nomi.media == Catalogo.Regole.fasciaMedia(n: String(n)))
        #expect(nomi.bonus == Catalogo.Regole.fasciaBonus(n: String(n)))
        #expect(nomi.togli == Catalogo.Regole.togliFascia(n: String(n)))
    }

    @Test("Gli esempi della issue #460: fascia 1")
    func esempiDellaIssue() {
        let nomi = TestiRegole.nomiFascia(posto: 1)
        #expect(nomi.media == "Fascia 1, media almeno")
        #expect(nomi.bonus == "Fascia 1, bonus")
        #expect(nomi.togli == "Togli la fascia 1")
    }

    @Test("Con sei fasce nessun nome si ripete")
    func nomiTuttiDiversi() {
        let nomi = (1...6).flatMap { n -> [String] in
            let f = TestiRegole.nomiFascia(posto: n)
            return [f.media, f.bonus, f.togli]
        }
        #expect(Set(nomi).count == nomi.count)
    }

    @Test("Voti della prova: il portiere e i tre difensori numerati da 1")
    func votiDellaProva() {
        #expect(TestiRegole.nomeVotoProva(indice: 0) == Catalogo.Regole.votoPortiere)
        for k in 1...3 {
            #expect(TestiRegole.nomeVotoProva(indice: k) == Catalogo.Regole.votoDifensore(n: String(k)))
        }
        #expect(TestiRegole.nomeVotoProva(indice: 0) == "Voto del portiere")
        #expect(TestiRegole.nomeVotoProva(indice: 1) == "Voto del difensore 1")
        #expect(TestiRegole.nomeVotoProva(indice: 3) == "Voto del difensore 3")
    }

    @Test("Il testo a vista non cambia: il nome per VoiceOver lo contiene")
    func ilNomeContieneIlTestoAVista() {
        let nomi = TestiRegole.nomiFascia(posto: 2)
        #expect(nomi.media.lowercased().contains("media almeno"))
        #expect(nomi.bonus.lowercased().contains("bonus"))
        #expect(nomi.togli.lowercased().contains("togli la fascia"))
        #expect(TestiRegole.nomeVotoProva(indice: 0).lowercased().contains("portiere"))
        #expect(TestiRegole.nomeVotoProva(indice: 2).lowercased().contains("difensore 2"))
    }
}

@MainActor
@Suite("Regole: il numero della fascia segue la riga, anche dopo «Togli»")
struct NumeroFasciaTests {
    private func modello() async -> RegoleEditorViewModel {
        let vm = RegoleEditorViewModel(server: ServerDiProva.conFixture(["/api/regole": "regole"]))
        await vm.carica()
        return vm
    }

    @Test("Le fasce caricate sono numerate da 1, nell'ordine in cui compaiono")
    func numeriDaUno() async throws {
        let vm = await modello()
        #expect(vm.fasce.count == 6)
        for (indice, fascia) in vm.fasce.enumerated() {
            #expect(vm.postoFascia(fascia.id) == indice + 1)
        }
    }

    @Test("Dopo «Togli» i numeri si rifanno: nessun buco, la fascia tolta non ha più posto")
    func numeriDopoTogli() async throws {
        let vm = await modello()
        let tolta = vm.fasce[1].id
        let seguente = vm.fasce[2].id
        vm.togliFascia(tolta)
        #expect(vm.fasce.count == 5)
        #expect(vm.postoFascia(tolta) == nil)
        #expect(vm.postoFascia(seguente) == 2, "la terza diventa la seconda")
        let posti = vm.fasce.compactMap { vm.postoFascia($0.id) }
        #expect(posti == [1, 2, 3, 4, 5])
    }

    @Test("Una fascia aggiunta prende il numero dopo l'ultima")
    func numeroDellaFasciaNuova() async throws {
        let vm = await modello()
        vm.aggiungiFascia()
        let nuova = try #require(vm.fasce.last)
        #expect(vm.postoFascia(nuova.id) == 7)
    }

    @Test("Le etichette della riga seguono il numero dopo «Togli»")
    func etichetteDopoTogli() async throws {
        let vm = await modello()
        vm.togliFascia(vm.fasce[0].id)
        let seconda = try #require(vm.fasce.first)   // era la seconda, ora è la prima
        let posto = try #require(vm.postoFascia(seconda.id))
        #expect(TestiRegole.nomiFascia(posto: posto).togli == "Togli la fascia 1")
    }
}
