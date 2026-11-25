import Foundation
import Testing
@testable import Schieraxi

// L'anteprima del regolamento incollato come la web (#889, dopo la #884; `vistaRegole` in `fanta/web/app.js`): i valori di
// `non_applicabili` di `POST /api/regole/riconosci` stanno sotto «Non applicato», ognuno con «etichetta: valore», il perché del
// server (`motivo`) e la riga da cui viene, e «Applica ai campi» non li mette nei campi. L'ordine dei cambi si legge «Per ruolo» o
// «Libera» (prima «per_ruolo») e i posti per ruolo «2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti» (prima
// «A: 3, C: 3, D: 3, P: 2»). Regolamento inventato.

/// Una risposta di `POST /api/regole/riconosci` letta come la legge l'app (chiavi snake_case convertite).
private func risposta(_ json: String) throws -> RiconoscimentoRegole {
    try Decodifica.decodifica(Data(json.utf8))
}

/// Il perché che il server dà per la panchina di una lega con i posti fissi (frase `regole.panchina_posti_fissi`, 2 + 3 + 3 + 3).
private let perchePostiFissi = "La tua panchina ha posti fissi per ruolo, 11 in tutto: cambia a mano i posti di ogni ruolo nei valori delle regole."

/// Come la manda il server dal 25/11/2026 (#884) a una lega con i posti fissi in panchina.
private let conNonApplicabili = """
    {"modifiche": [
       {"chiave": "bonus.assist", "etichetta": "Assist", "valore": 1.5, "riga": "Assist: +1,5 punti"},
       {"chiave": "panchina.tipo", "etichetta": "Ordine dei cambi", "valore": "per_ruolo", "riga": "Sostituzioni per ruolo"}],
     "non_applicabili": [
       {"chiave": "panchina.numero", "etichetta": "Giocatori in panchina", "valore": 12, "riga": "In panchina vanno 12 giocatori",
        "motivo": "\(perchePostiFissi)", "motivo_frase": {"chiave": "regole.panchina_posti_fissi", "param": {"n": 11}}}],
     "non_riconosciute": [], "da_controllare": []}
    """

@Suite("Regole: «Non applicato» e i nomi in parole nell'anteprima del regolamento, come la web (#889)")
struct RegolamentoNonApplicatoTests {
    @Test("Sotto «Non applicato» il valore con il perché del server e la riga da cui viene")
    func nonApplicato() throws {
        let anteprima = AnteprimaRegolamento(try risposta(conNonApplicabili))
        #expect(anteprima.nonApplicati.map(\.testo) == ["Giocatori in panchina: 12"])
        #expect(anteprima.nonApplicati.first?.motivo == perchePostiFissi)
        #expect(anteprima.nonApplicati.first?.daRiga == "da: «In panchina vanno 12 giocatori»")
        #expect(Catalogo.Regole.nonApplicato == "Non applicato")
    }

    @Test("Sotto «Riconosciuto» solo i valori di `modifiche`, con l'ordine dei cambi in parole")
    func riconosciuti() throws {
        let anteprima = AnteprimaRegolamento(try risposta(conNonApplicabili))
        #expect(anteprima.riconosciuti.map(\.testo) == ["Assist: 1,5", "Ordine dei cambi: Per ruolo"])
        #expect(anteprima.riconosciuti.map(\.daRiga) == ["da: «Assist: +1,5 punti»", "da: «Sostituzioni per ruolo»"])
        #expect(anteprima.riconosciuti.allSatisfy { $0.motivo == nil })
        #expect(anteprima.siApplica)
        #expect(!anteprima.vuota)
    }

    @Test("I valori con le parole della pagina: «Per ruolo», «Libera», i posti per ruolo per esteso")
    func valoriInParole() {
        #expect(AnteprimaRegolamento.valore(chiave: "panchina.tipo", .testo("per_ruolo")) == "Per ruolo")
        #expect(AnteprimaRegolamento.valore(chiave: "panchina.tipo", .testo("libera")) == "Libera")
        let posti = JSONValue.oggetto(["P": .intero(2), "D": .intero(3), "C": .intero(3), "A": .intero(3)])
        #expect(AnteprimaRegolamento.valore(chiave: "panchina.posti", posti) == "2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti")
        let uno = JSONValue.oggetto(["A": .intero(1), "C": .intero(2), "D": .intero(1), "P": .intero(1)])
        #expect(AnteprimaRegolamento.valore(chiave: "panchina.posti", uno) == "1 portiere, 1 difensore, 2 centrocampisti, 1 attaccante")
        // il resto come prima
        #expect(AnteprimaRegolamento.valore(chiave: "bonus.ammonizione", .decimale(-0.5)) == RegoleLogica.descrivi(.decimale(-0.5)))
        #expect(AnteprimaRegolamento.valore(chiave: "panchina.cambio_modulo", .booleano(true)) == "sì")
    }

    @Test("I posti per ruolo fra i riconosciuti: la riga intera")
    func postiFraIRiconosciuti() throws {
        let json = """
            {"modifiche": [{"chiave": "panchina.posti", "etichetta": "Posti in panchina per ruolo",
              "valore": {"P": 2, "D": 3, "C": 3, "A": 3}, "riga": "Panchina: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti"}],
             "non_applicabili": []}
            """
        let anteprima = AnteprimaRegolamento(try risposta(json))
        #expect(anteprima.riconosciuti.map(\.testo) == ["Posti in panchina per ruolo: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti"])
        #expect(anteprima.nonApplicati.isEmpty)
    }

    @Test("Solo valori non applicabili: niente da applicare, ma l'anteprima non è vuota")
    func soloNonApplicabili() throws {
        let json = """
            {"modifiche": [], "non_applicabili": [{"chiave": "panchina.numero", "etichetta": "Giocatori in panchina", "valore": 12,
              "riga": "Panchina: 12 giocatori", "motivo": "\(perchePostiFissi)"}]}
            """
        let anteprima = AnteprimaRegolamento(try risposta(json))
        #expect(!anteprima.vuota, "si mostra «Non applicato», non «Non ho riconosciuto nessuna regola»")
        #expect(!anteprima.siApplica, "«Applica ai campi» non c'è")
        #expect(anteprima.riconosciuti.isEmpty)
    }

    @Test("Un server di prima, senza `non_applicabili`: come prima")
    func serverDiPrima() throws {
        let conValori = AnteprimaRegolamento(try risposta(#"{"modifiche": [{"chiave": "bonus.mvp", "etichetta": "Migliore in campo", "valore": 1}], "non_riconosciute": []}"#))
        #expect(conValori.riconosciuti.map(\.testo) == ["Migliore in campo: 1"])
        #expect(conValori.riconosciuti.first?.daRiga == nil)
        #expect(conValori.nonApplicati.isEmpty)
        #expect(conValori.siApplica)
        #expect(AnteprimaRegolamento(try risposta(#"{"modifiche": [], "non_riconosciute": []}"#)).vuota)
    }

    @Test("Un valore non applicabile senza etichetta né chiave non si mostra; senza perché, solo il valore")
    func voceIncompleta() throws {
        let json = """
            {"modifiche": [], "non_applicabili": [{"riga": "Riga senza regola"},
              {"chiave": "panchina.numero", "etichetta": "Giocatori in panchina", "valore": 9, "motivo": "  "}]}
            """
        let anteprima = AnteprimaRegolamento(try risposta(json))
        #expect(anteprima.nonApplicati.map(\.testo) == ["Giocatori in panchina: 9"])
        #expect(anteprima.nonApplicati.first?.motivo == nil)
        #expect(anteprima.nonApplicati.first?.daRiga == nil)
    }

    @MainActor
    @Test("«Applica ai campi» mette nei campi i soli valori riconosciuti: la panchina non applicabile resta com'era")
    func applicaSoloIRiconosciuti() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/regole/riconosci") { return Data(conNonApplicabili.utf8) }
            return try Fixture.dati("regole")
        }
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        vm.testoRegolamento = "Assist: +1,5 punti\nSostituzioni per ruolo\nIn panchina vanno 12 giocatori"
        await vm.riconosci()
        #expect(vm.riconoscimento?.nonApplicabili?.count == 1)
        vm.applicaRiconosciute()
        #expect(vm.valore.valore("bonus.assist")?.numero == 1.5)
        #expect(vm.valore.valore("panchina.tipo")?.testo == "per_ruolo")
        #expect(vm.valore.valore("panchina.numero")?.numero == 11, "il valore non applicabile non entra nei campi")
    }
}
