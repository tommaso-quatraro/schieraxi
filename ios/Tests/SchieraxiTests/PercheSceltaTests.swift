import Foundation
import Testing
@testable import Schieraxi

/// Il perché della scelta in una riga (#356): sotto il campo, per i titolari che sembrano una scelta storta (o incerti con la
/// riserva sicura), la riga che scrive il server (`perche_scelta` del modulo mostrato), come la web: «Nome · riga».
/// Solo per la proposta del server: niente righe in modifica a mano né a giornata chiusa.
@MainActor
@Suite("Perché della scelta sotto il campo")
struct PercheSceltaTests {
    static let riga = "Preferito a Gallo: con lui la formazione fa più punti attesi (64,1 contro 64,0)."

    @Test("La riga del server per il titolare, con il suo nome, solo nel modulo mostrato")
    func righeDelModuloMostrato() async throws {
        let (vm, f, id) = try await caricata()
        let nome = try #require(f.schede?[String(id)]?.nome)
        let righe = vm.righeScelta(f)
        #expect(righe.map(\.nome) == [nome])
        #expect(righe.map(\.testo) == [Self.riga])
        #expect(righe.map(\.id) == [id])
        vm.scegliModulo("5-3-2")                // un altro modulo dello stile: le sue righe (qui nessuna)
        #expect(vm.righeScelta(f).isEmpty)
    }

    @Test("In modifica a mano niente righe, come la web")
    func nienteInModificaAMano() async throws {
        let (vm, f, _) = try await caricata()
        vm.iniziaModificaManuale(f)
        #expect(vm.manuale != nil)
        #expect(vm.righeScelta(f).isEmpty)
    }

    @Test("A giornata chiusa niente righe, come la web")
    func nienteAGiornataChiusa() async throws {
        let (vm, f, _) = try await caricata(chiusa: true)
        #expect(vm.chiusa)
        #expect(vm.righeScelta(f).isEmpty)
    }

    @Test("Un server senza il campo: nessuna riga")
    func serverVecchio() async throws {
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        let f = try #require(vm.formazione)
        #expect(vm.righeScelta(f).isEmpty)
    }

    @Test("Una riga incompleta o di un giocatore che non c'è si salta: la Formazione si carica lo stesso")
    func rigaIncompleta() async throws {
        let (vm, f, _) = try await caricata(extra: [["titolare": 999_999, "testo": "x"], ["altro": 3], ["titolare": 1, "testo": ""]])
        #expect(vm.righeScelta(f).map(\.testo) == [Self.riga])
    }

    @Test("La riga si legge come sulla web: il nome, un punto in mezzo e la frase del server (fanta/frasi.py)")
    func comeLaWeb() throws {
        let web = try TestiWeb().italiano("frase.scelta.piu_punti")
        #expect(web.hasPrefix("Preferito a {altro}: con lui la formazione fa più punti attesi"))
        let r = RigaScelta(id: 7, nome: "Rossi", testo: Self.riga)
        #expect(r.voce == "Rossi · " + Self.riga)
    }

    // MARK: aiuti

    /// La formazione d'esempio con una riga del perché della scelta per un difensore titolare del modulo consigliato
    /// (stile consigliato), più le righe `extra`, e se serve con la giornata chiusa.
    private func caricata(chiusa: Bool = false, extra: [[String: Any]] = []) async throws -> (FormazioneViewModel, Formazione, Int) {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        let base: Formazione = try Fixture.decodifica("formazione")
        let id = try #require(base.titolari.first { $0.ruolo == "D" }?.id)
        let righe: [[String: Any]] = [["titolare": id, "altro": 1, "testo": Self.riga,
                                        "frase": ["chiave": "scelta.piu_punti", "param": ["altro": "Gallo", "attuale": "64.1", "invertita": "64.0"]]]]
            + extra
        var livelli = try #require(formazione["livelli"] as? [[String: Any]])
        for i in livelli.indices {
            var moduli = try #require(livelli[i]["moduli"] as? [[String: Any]])
            for j in moduli.indices {
                let consigliato = moduli[j]["modulo"] as? String == livelli[i]["modulo"] as? String
                moduli[j]["perche_scelta"] = consigliato ? righe : []
            }
            livelli[i]["moduli"] = moduli
        }
        formazione["livelli"] = livelli
        if chiusa { formazione["iniziata"] = true }
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/formazione/valuta") {
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return dati
        }
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        return (vm, try #require(vm.formazione), id)
    }
}
