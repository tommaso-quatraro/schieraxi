import XCTest
@testable import Schieraxi

/// Decodifica delle risposte del server con dati inventati (in `Tests/Fixtures`).
final class ModelliTests: XCTestCase {
    func testOggi() throws {
        let o: Oggi = try Fixture.decodifica("oggi")
        XCTAssertEqual(o.giornata, 9)
        XCTAssertEqual(o.inizio, "2026-10-27 18:30")
        XCTAssertEqual(o.iniziata, true)
        XCTAssertEqual(o.conProbabili, true)
        XCTAssertEqual(o.formazione?.modulo, "4-3-3")
        XCTAssertEqual(o.formazione?.disponibile, true)
        XCTAssertEqual(o.avvisi?.count, 8)
        XCTAssertEqual(o.avvisi?.filter { $0.inFormazione == true }.count, 2)
        XCTAssertEqual(o.migliori?.count, 3)
        XCTAssertEqual(o.partite?.count, 10)
        XCTAssertEqual(o.partite?.first?.casa, "sassuolo")
    }

    func testOggiTuaSceltaOConsigliata() throws {
        func leggi(_ f: String) throws -> Oggi {
            let d = JSONDecoder()
            d.keyDecodingStrategy = .convertFromSnakeCase
            return try d.decode(Oggi.self, from: Data(#"{"giornata":9,"formazione":\#(f)}"#.utf8))
        }
        let tua = try leggi(#"{"modulo":"4-4-2","punteggio_atteso":71.7,"tua_scelta":true}"#).formazione
        XCTAssertEqual(tua?.modulo, "4-4-2")
        XCTAssertEqual(tua?.tuaScelta, true)
        XCTAssertEqual(tua?.titoloScheda, "La tua scelta")
        let consigliata = try leggi(#"{"modulo":"5-3-2","punteggio_atteso":70.1,"tua_scelta":false}"#).formazione
        XCTAssertEqual(consigliata?.tuaScelta, false)
        XCTAssertEqual(consigliata?.titoloScheda, "La formazione consigliata")
        // server vecchio (campo assente) o campo strano: vale «consigliata», e il resto si legge lo stesso
        let vecchio = try leggi(#"{"modulo":"5-3-2","punteggio_atteso":70.1}"#).formazione
        XCTAssertEqual(vecchio?.tuaScelta, false)
        let strano = try leggi(#"{"modulo":"5-3-2","punteggio_atteso":70.1,"tua_scelta":"si"}"#).formazione
        XCTAssertEqual(strano?.tuaScelta, false)
        XCTAssertEqual(strano?.modulo, "5-3-2")
    }

    func testProbabiliFresche() throws {
        func oggi(_ extra: String) throws -> Oggi {
            try Decodifica.decodifica(Data("{\"giornata\": 9\(extra)}".utf8))
        }
        let a = try oggi(", \"probabili\": {\"aggiornate_il\": \"2026-10-31 13:05\", \"minuti_fa\": 130, \"eta\": \"2 ore fa\", \"testo\": \"Probabili aggiornate alle 13:05\", \"vecchie\": true, \"avviso\": \"Hanno più di 6 ore\"}")
        XCTAssertEqual(a.probabili?.valore?.riga, "Probabili aggiornate alle 13:05 · 2 ore fa")
        XCTAssertEqual(a.probabili?.valore?.avvisoVisibile, "Hanno più di 6 ore")
        // non vecchie: l'avviso non si mostra anche se c'è
        let b = try oggi(", \"probabili\": {\"testo\": \"Probabili aggiornate ieri alle 20:00\", \"vecchie\": false, \"avviso\": \"x\"}")
        XCTAssertEqual(b.probabili?.valore?.riga, "Probabili aggiornate ieri alle 20:00")
        XCTAssertNil(b.probabili?.valore?.avvisoVisibile)
        // null, assente o del tipo sbagliato: niente riga e Oggi si legge lo stesso
        XCTAssertNil(try oggi(", \"probabili\": null").probabili?.valore)
        XCTAssertNil(try oggi("").probabili?.valore)
        let c = try oggi(", \"probabili\": \"strano\"")
        XCTAssertNil(c.probabili?.valore)
        XCTAssertEqual(c.giornata, 9)
    }

    func testFormazione() throws {
        let f: Formazione = try Fixture.decodifica("formazione")
        XCTAssertEqual(f.squadra, "Nuvola Ovest")
        XCTAssertEqual(f.giornata, 9)
        XCTAssertEqual(f.modulo, "4-3-3")
        XCTAssertEqual(f.titolari.count, 11)
        XCTAssertEqual(f.panchina.count, 11)
        XCTAssertEqual(f.livelli?.map(\.rischio), [-2, -1, 0, 1, 2])
        XCTAssertEqual(f.livelli?.first?.moduli.first?.titolari.count, 11)
        XCTAssertEqual(f.schede?.count, 25)
        XCTAssertEqual(f.fuori?.count, 3)
        XCTAssertEqual(f.senzaDati ?? [], [])
        XCTAssertEqual(f.dev, 4.0)
        // i campi della previsione ci sono tutti
        let vicario = try XCTUnwrap(f.titolari.first)
        XCTAssertEqual(vicario.nome, "Noraldi")
        XCTAssertEqual(vicario.ruolo, "P")
        XCTAssertEqual(vicario.titolarita, "titolare")
        XCTAssertEqual(vicario.indice, 100)
        XCTAssertNotNil(vicario.portaInviolata)
        XCTAssertEqual(vicario.motivi?.first, "titolare al 90%")
    }

    func testMercato() throws {
        let m: Mercato = try Fixture.decodifica("mercato")
        XCTAssertEqual(m.proposte.count, 10)
        XCTAssertEqual(m.svincolati, 353)
        XCTAssertNil(m.creditiResidui)
        XCTAssertEqual(m.rimborsoIpotizzato, 0.5)
        XCTAssertEqual(m.proposte.first?.esce.nome, "Norese G.")
        XCTAssertEqual(m.proposte.first?.giornate?.count, 5)
        XCTAssertNil(m.proposte.first?.creditiDopo)
    }

    func testClassifica() throws {
        let c: ElencoGiocatori = try Fixture.decodifica("classifica")
        XCTAssertEqual(c.giornata, 9)
        XCTAssertEqual(c.giocatori.count, 8)
        XCTAssertEqual(c.giocatori.first?.nome, "Malvi")
        XCTAssertEqual(c.giocatori.first?.quotazione, 35)
        XCTAssertNotNil(c.giocatori.first?.proprietario)
    }

    func testProposteDiScambio() throws {
        let p: ProposteScambi = try Fixture.decodifica("proposte")
        XCTAssertEqual(p.proposte.count, 5)
        XCTAssertEqual(p.giornate, [9, 10, 11, 12, 13])
        let prima = try XCTUnwrap(p.proposte.first)
        XCTAssertEqual(prima.altra, "Lambda Rossa")
        XCTAssertEqual(prima.`do`.first?.nome, "Barucci")
        XCTAssertEqual(prima.ricevo.first?.nome, "Mangoni")
        XCTAssertEqual(prima.guadagnoMio, 1.87, accuracy: 0.001)
        XCTAssertEqual(prima.perGiornataMio?.count, 5)
        // «reparti» è vuoto nelle proposte e non deve rompere la decodifica
        XCTAssertNil(prima.reparti?.mio)
        XCTAssertEqual(prima.quotazioneDo, 13)
    }

    func testRosa() throws {
        let r: Rosa = try Fixture.decodifica("rosa")
        XCTAssertEqual(r.nome, "Nuvola Ovest")
        XCTAssertEqual(r.mia, true)
        XCTAssertEqual(r.giocatori.count, 25)
        XCTAssertEqual(r.giocatori.first?.squadraSlug, "juventus")
        XCTAssertEqual(r.giocatori.first?.previsione?.titolarita, "titolare")
        XCTAssertEqual(r.avvisi?.count, 0)
        XCTAssertNil(r.creditiResidui)
    }

    func testRegoleComeJSONValue() throws {
        let v: JSONValue = try Fixture.decodifica("regole", snake: false)
        XCTAssertEqual(v.valore("nome_lega")?.testo, "La mia lega")
        XCTAssertEqual(v.valore("bonus.gol.D")?.numero, 3)
        XCTAssertEqual(v.valore("panchina.posti.D")?.numero, 3)
        XCTAssertEqual(v.valore("moduli")?.elenco?.count, 7)
        XCTAssertEqual(v.valore("modificatore_difesa.attivo")?.booleano, true)
        XCTAssertEqual(v.valore("voto_senza_sostituto"), JSONValue.nullo)
    }

    func testStatoDati() throws {
        let s: StatoDati = try Fixture.decodifica("stato-dati")
        XCTAssertEqual(s.stagione, "2026-27")
        XCTAssertEqual(s.partite?.giocate, 80)
        XCTAssertEqual(s.partite?.totali, 380)
        XCTAssertEqual(s.voti, 2542)
        XCTAssertEqual(s.foto, 4)
        XCTAssertEqual(s.probabili?.count, 1)
        XCTAssertEqual(s.calibrazione?.gruppi?.count, 7)
        // osservato e previsto sono null quando non ci sono dati
        XCTAssertNil(s.calibrazione?.gruppi?.first?.osservato)
        XCTAssertEqual(s.calibrazione?.gruppi?.first?.indicativo, true)
    }

    func testSquadre() throws {
        let s: [SquadraLega] = try Fixture.decodifica("squadre")
        XCTAssertEqual(s.count, 10)
        XCTAssertEqual(s.first?.nome, "Borgo Alto")
        XCTAssertEqual(s.first?.immagini, ImmaginiSquadra(stemma: false, maglia: false))
        XCTAssertNil(s.first?.creditiResidui)
    }

    func testSchedaGiocatore() throws {
        let s: SchedaGiocatore = try Fixture.decodifica("giocatore")
        XCTAssertEqual(s.calciatore.nome, "Malvi")
        XCTAssertEqual(s.calciatore.squadraSlug, "roma")
        XCTAssertEqual(s.stagione?.giornateGiocateSerieA, 8)
        XCTAssertEqual(s.voti?.count, 7)
        XCTAssertEqual(s.voti?.first?.giornata, 1)
        XCTAssertEqual(s.avanzate?.minuti, 492)
        XCTAssertEqual(s.avanzate?.per90?.xg, 1.22)
        XCTAssertEqual(s.avanzate?.stagioniPrecedenti?.count, 1)
        XCTAssertEqual(s.rendimento?.sovraRendimento, -0.29)
        XCTAssertEqual(s.previsione?.giornata, 9)
        XCTAssertEqual(s.proprietario, "FC Sotto 10,5")
    }

    func testConfronto() throws {
        let c: Confronto = try Fixture.decodifica("confronto")
        XCTAssertEqual(c.giornata, 9)
        XCTAssertEqual(c.giocatori.count, 2)
        XCTAssertEqual(c.consigliato, 4510)
        XCTAssertEqual(c.fattori.count, 6)
        XCTAssertEqual(c.fattori.first?.chiave, "giocare")
        XCTAssertEqual(c.fattori.first?.percentuale, true)
        XCTAssertEqual(c.formazione?.postoA, "titolare")
        XCTAssertEqual(c.formazione?.modulo, "4-3-3")
    }

    func testAffidabilita() throws {
        let a: Affidabilita = try Fixture.decodifica("affidabilita")
        XCTAssertEqual(a.righe?.count, 8)
        XCTAssertEqual(a.sintesi?.giornate, 8)
        XCTAssertEqual(a.sintesi?.puntiModello, 71.7)
        XCTAssertEqual(a.righe?.first?.giornata, 1)
    }

    func testRegoleRiconosciute() throws {
        let r: RiconoscimentoRegole = try Fixture.decodifica("riconosci")
        XCTAssertEqual(r.modifiche.count, 1)
        XCTAssertEqual(r.modifiche.first?.chiave, "bonus.rigore_parato")
        XCTAssertEqual(r.modifiche.first?.valore.numero, 3)
        XCTAssertEqual(r.nonRiconosciute ?? [], [])
    }

    func testOffertaDaTesto() throws {
        let o: OffertaRiconosciuta = try Fixture.decodifica("da-testo")
        XCTAssertEqual(o.con, "Lambda Rossa")
        XCTAssertEqual(o.`do`, ["Barucci"])
        XCTAssertEqual(o.ricevo, ["Mangoni"])
        XCTAssertEqual(o.ambigui ?? [], [])
        XCTAssertEqual(o.analisi?.reparti?.mio?["D"], 12.1)
        XCTAssertEqual(o.analisi?.percentualeMio, 0.2)
    }

    func testAsta() throws {
        let a: PianoAsta = try Fixture.decodifica("asta")
        XCTAssertEqual(a.crediti, 500)
        XCTAssertEqual(a.panchina, 60)
        XCTAssertEqual(a.ruoli.count, 4)
        XCTAssertEqual(a.ruoli.first?.giocatori.first?.nome, "Noraldi")
        XCTAssertEqual(a.ruoli.first?.giocatori.first?.prezzo, 65)
        let r: PianoRiparazione = try Fixture.decodifica("asta-riparazione")
        XCTAssertNil(r.tuoiCrediti)
        XCTAssertEqual(r.postiLiberi, 31)
        XCTAssertEqual(r.perTe?.count, 4)
        XCTAssertEqual(r.ruoli.map(\.ruolo), ["P", "D", "C", "A"])
        XCTAssertEqual(r.ruoli.first?.posti, 4)
    }

    func testAvvisiStagioneNovitaCalendario() throws {
        let a: StatoAvvisi = try Fixture.decodifica("avvisi", snake: false)
        XCTAssertTrue(a.impostazioni.cambi)
        XCTAssertEqual(a.impostazioni.app_nativa, false)
        XCTAssertEqual(a.dispositivi, 0)
        let s: StatoStagione = try Fixture.decodifica("stagione")
        XCTAssertEqual(s.nuova, false)
        XCTAssertEqual(s.corrente, "2026-27")
        let n: [VoceNovita] = try Fixture.decodifica("novita")
        XCTAssertEqual(n.map(\.versione), ["1.14", "1.13", "1.12"])
        let c: Calendario = try Fixture.decodifica("calendario")
        XCTAssertEqual(c.giornate, [9, 10, 11, 12, 13])
        XCTAssertEqual(c.squadre.count, 6)
        XCTAssertEqual(c.squadre.first?.partite.first?.avversario, "cagliari")
    }

    func testUnCampoMancanteNonRompeLaDecodifica() throws {
        // un giocatore con il solo necessario: tutto il resto è opzionale
        let json = #"{"id": 1, "nome": "Prova", "ruolo": "A"}"#
        let g: Giocatore = try Decodifica.decodifica(Data(json.utf8))
        XCTAssertEqual(g.nome, "Prova")
        XCTAssertNil(g.indice)
        XCTAssertTrue(g.etichette.isEmpty)
        // risposta senza «formazione» e senza «avvisi»
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 3}"#.utf8))
        XCTAssertNil(o.formazione)
        XCTAssertNil(o.avvisi)
    }

    func testOggiVuotoSiLeggeSenzaErrore() throws {
        // account nuovo: «Oggi» ha tutti i campi opzionali, un oggetto vuoto non è un errore
        let o: Oggi = try Decodifica.decodifica(Data("{}".utf8))
        XCTAssertNil(o.giornata)
    }

    func testErroreDiDecodificaDaUnMessaggioInItaliano() {
        XCTAssertThrowsError(try Decodifica.decodifica(Data("[1, 2]".utf8)) as Oggi) { errore in
            XCTAssertTrue(errore.localizedDescription.hasPrefix("Il server ha mandato una risposta"), errore.localizedDescription)
        }
    }

    func testImpostazioniAvvisiConAppNativaMancanteNonLaRimandano() throws {
        // un server vecchio non manda «app_nativa»: si legge come assente e non si rimanda (non si azzera niente)
        let vecchio = #"{"cambi": true, "promemoria_60": true, "promemoria_15": false, "riepilogo": true}"#
        let i = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: Data(vecchio.utf8))
        XCTAssertNil(i.app_nativa)
        let rimandato = String(decoding: try JSONEncoder().encode(i), as: UTF8.self)
        XCTAssertFalse(rimandato.contains("app_nativa"))
        var nuova = i
        nuova.app_nativa = true
        XCTAssertTrue(String(decoding: try JSONEncoder().encode(nuova), as: UTF8.self).contains("\"app_nativa\":true"))
    }
}
