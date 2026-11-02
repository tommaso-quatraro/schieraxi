import XCTest
@testable import Schieraxi

/// «Quanto ci abbiamo preso» (campo `precisione` di `/api/diario`) e «Avviso se il consiglio cambia» (`avviso_prima` degli avvisi).
/// Dati inventati; le frasi devono essere quelle della web (`diario.qp_*` e `avv.prima*` di `fanta/web/testi.js`).
final class PrecisioneTests: XCTestCase {

    private func diario(_ json: String) throws -> DiarioRisposta {
        try Decodifica.decodifica(Data(json.utf8))
    }

    private let completo = #"""
    {"giornate": [], "precisione": {
      "giornate": 6, "pochi_dati": true, "giornate_minime": 8, "fonti": {"mostrati": 4, "ricostruiti": 2},
      "fantavoto": {"errore_medio": 1.26, "scostamento": -0.5, "entro_un_punto": 61, "voti": 64},
      "gioca": {"giocatori": 70, "principale": 1, "fonte": "mostrati", "giornate": 4, "gruppi": [
        {"da": 40, "a": 70, "giocatori": 12, "pochi": true, "detto": 56, "giocato": 50},
        {"da": 90, "a": 100, "giocatori": 58, "pochi": false, "detto": 98, "giocato": 81}]},
      "confronto": {"giornate": 6, "meglio_consigliata": 4, "meglio_tua": 1, "pari": 1, "punti": 9.5, "media_consigliata": 70.1, "media_tua": 68.5},
      "squadra": {"giornate": 6, "punti_medi_attesi": 72.0, "punti_medi_fatti": 73.4, "scarto_medio": 4.1, "errore_medio": 1.4,
                  "dentro_fascia": 5, "con_fascia": 6, "percentuale_dentro": 83, "fascia_dichiarata": 80},
      "per_giornata": [
        {"stagione": "2026-27", "giornata": 5, "giornata_lega": 3, "fonte": "ricostruiti", "errore_fantavoto": 1.4, "voti": 10,
         "attesi": 70, "fatti": 66.5, "tua": null, "differenza": null},
        {"stagione": "2026-27", "giornata": 6, "giornata_lega": 4, "fonte": "mostrati", "errore_fantavoto": 1.1, "voti": 11,
         "attesi": 71, "fatti": 75, "tua": 70, "differenza": 5},
        {"stagione": "2026-27", "giornata": 7, "giornata_lega": 5, "fonte": "mostrati", "errore_fantavoto": null, "voti": 0,
         "attesi": 69.5, "fatti": 68, "tua": 70.5, "differenza": -2.5}]}}
    """#

    func testDecodificaCompleta() throws {
        let p = try XCTUnwrap(try diario(completo).precisione)
        XCTAssertEqual(p.giornate, 6)
        XCTAssertEqual(p.pochiDati, true)
        XCTAssertEqual(p.fonti?.ricostruiti, 2)
        XCTAssertEqual(p.fantavoto?.voti, 64)
        XCTAssertEqual(p.gioca?.fasciaPrincipale?.detto, 98)
        XCTAssertEqual(p.confronto?.punti, 9.5)
        XCTAssertEqual(p.squadra?.dentroFascia, 5)
        XCTAssertEqual(p.perGiornata.count, 3)
        XCTAssertEqual(p.perGiornata.first?.numero, 3, "si mostra il numero della lega")
        XCTAssertNil(p.perGiornata.first?.tua)
    }

    func testFrasiUgualiAllaWeb() throws {
        let t = try XCTUnwrap(TestoPrecisione(try diario(completo).precisione))
        XCTAssertEqual(t.calcolatoSu, "Calcolato su 6 giornate, dalla giornata 3 alla 5.")
        XCTAssertEqual(t.pochi, "Ancora pochi dati: servono almeno 8 giornate perché questi numeri siano affidabili. Per ora possono cambiare molto.")
        XCTAssertEqual(t.fantavoto.numero, "1,3")
        XCTAssertEqual(t.fantavoto.frase, "In media il fantavoto atteso dei tuoi giocatori sbaglia di 1,3 punti; 6 voti su 10 sono entro un punto. Su 64 voti. In media hanno fatto 0,5 in meno del previsto.")
        XCTAssertEqual(t.gioca.numero, "8 su 10")
        XCTAssertEqual(t.gioca.frase, "Quando diciamo «gioca 98%», ha giocato 8 volte su 10.")
        XCTAssertEqual(t.gioca.giudizio, "Qui siamo stati troppo ottimisti.")
        XCTAssertTrue(t.gioca.attenzione)
        XCTAssertEqual(t.gioca.fasce, ["Gioca 40-69%: dicevamo 56%, hanno giocato nel 50% dei casi (12 casi, pochi per dirlo)",
                                       "Gioca 90-100%: dicevamo 98%, hanno giocato nel 81% dei casi (58 casi)"])
        XCTAssertEqual(t.confronto.numero, "4 su 6")
        XCTAssertEqual(t.confronto.frase, "Giornate in cui la consigliata ha fatto meglio della tua: 4 su 6. Meglio la tua: 1. Pari: 1. Seguendo sempre la consigliata avresti fatto 9,5 punti in più.")
        XCTAssertEqual(t.squadra.numero, "4,1")
        XCTAssertEqual(t.squadra.frase, "Punti della consigliata: 72,0 previsti e 73,4 fatti, in media. Giornate dentro la fascia prevista: 5 su 6 (puntiamo a 8 su 10).")
        XCTAssertEqual(t.notaRicostruiti, "In 2 giornate su 6 i numeri dei giocatori sono ricostruiti con i dati che c'erano prima: quelli mostrati allora non erano stati salvati.")
        // il grafico salta le giornate senza errore; l'andamento parte dalla più recente
        XCTAssertEqual(t.barre.map(\.etichetta), ["3", "4"])
        XCTAssertEqual(t.righe.first, "Giornata 5 · squadra: 69,5 previsti, 68,0 fatti · tua: 70,5 (−2,5)")
        XCTAssertEqual(t.righe.last, "Giornata 3 · fantavoto: errore 1,4 · squadra: 70,0 previsti, 66,5 fatti")
        XCTAssertEqual(t.gioca.voce, "Hanno giocato davvero, quando diciamo che giocano: 8 su 10. Quando diciamo «gioca 98%», ha giocato 8 volte su 10. Qui siamo stati troppo ottimisti.")
    }

    func testGiocaRicostruitiUsaLaFraseSenzaProbabili() throws {
        let t = try XCTUnwrap(TestoPrecisione(PrecisioneDiario(
            giornate: 9, pochiDati: false,
            gioca: .init(gruppi: [.init(da: 90, a: 100, giocatori: 30, pochi: false, detto: 98, giocato: 99)], principale: 0, fonte: "ricostruiti"))))
        XCTAssertNil(t.pochi)
        XCTAssertEqual(t.gioca.frase, "Con i dati disponibili prima di ogni giornata (senza le probabili formazioni), chi davamo al 98% ha giocato 10 volte su 10.")
        XCTAssertNil(t.gioca.giudizio, "entro 10 punti: nessun giudizio")
        XCTAssertFalse(t.gioca.attenzione)
    }

    func testNumeriBruttiEPluraliAllUno() throws {
        let t = try XCTUnwrap(TestoPrecisione(PrecisioneDiario(
            giornate: 1, fantavoto: .init(erroreMedio: 3.0, scostamento: 2.1, entroUnPunto: 20, voti: 1),
            gioca: .init(gruppi: [.init(da: 70, a: 90, giocatori: 1, pochi: true, detto: 75, giocato: 100)], principale: 0, fonte: "mostrati"),
            confronto: .init(giornate: 1, meglioConsigliata: 0, meglioTua: 1, pari: 0, punti: -1),
            perGiornata: [.init(giornata: 2, erroreFantavoto: 3.0, attesi: 70, fatti: 58)])))
        XCTAssertEqual(t.calcolatoSu, "Calcolato su 1 giornata (la 2).")
        XCTAssertEqual(t.fantavoto.frase, "In media il fantavoto atteso dei tuoi giocatori sbaglia di 3,0 punti; 2 voti su 10 sono entro un punto. Su 1 voto. In media hanno fatto 2,1 in più del previsto.")
        XCTAssertEqual(t.gioca.giudizio, "Qui siamo stati troppo prudenti.")
        XCTAssertEqual(t.gioca.fasce, ["Gioca 70-89%: dicevamo 75%, hanno giocato nel 100% dei casi (1 caso, pochi per dirlo)"])
        XCTAssertEqual(t.confronto.frase, "Giornate in cui la consigliata ha fatto meglio della tua: 0 su 1. Meglio la tua: 1. Pari: 0. Con le tue scelte hai fatto 1,0 punto in più della consigliata.")
        XCTAssertTrue(t.barre.count < 2, "con una sola giornata niente grafico")
    }

    func testCampiMancantiONulli() throws {
        let t = try XCTUnwrap(TestoPrecisione(try diario(#"""
        {"precisione": {"giornate": 3, "pochi_dati": true, "fantavoto": null, "gioca": null, "confronto": {"giornate": 0}, "squadra": null,
                        "per_giornata": []}}
        """#).precisione))
        XCTAssertEqual(t.calcolatoSu, "Calcolato su 3 giornate.")
        XCTAssertEqual(t.fantavoto.numero, "–")
        XCTAssertEqual(t.fantavoto.frase, "Ancora niente da confrontare.")
        XCTAssertEqual(t.gioca.numero, "–")
        XCTAssertEqual(t.confronto.frase, "Non sappiamo ancora cosa hai schierato: dillo qui sotto in ogni giornata, con «Ho schierato…».")
        XCTAssertEqual(t.squadra.numero, "–")
        XCTAssertEqual(t.fantavoto.voce, "Punti di errore medio del fantavoto atteso: non ancora disponibile. Ancora niente da confrontare.")
        XCTAssertTrue(t.barre.isEmpty)
        XCTAssertTrue(t.righe.isEmpty)
        XCTAssertNil(t.notaRicostruiti)
    }

    func testServerVecchioOFormatoStranoNonMostranoNiente() throws {
        // server vecchio: niente campo
        let vecchio = try diario(#"{"giornate": [], "affidabilita": {"giornate": 4}}"#)
        XCTAssertNil(vecchio.precisione)
        XCTAssertNil(TestoPrecisione(vecchio.precisione))
        XCTAssertNotNil(vecchio.affidabilita, "resta la scheda di prima")
        // nessuna giornata: niente sezione
        XCTAssertNil(TestoPrecisione(try diario(#"{"precisione": {"giornate": 0}}"#).precisione))
        // tipi strani: il Diario si legge lo stesso, la sezione no
        let strano = try diario(#"{"giornate": [], "precisione": "boh"}"#)
        XCTAssertNil(TestoPrecisione(strano.precisione))
        let misto = try XCTUnwrap(try diario(#"""
        {"precisione": {"giornate": "sei", "fantavoto": [1], "gioca": {"gruppi": [{"da": "x"}, 5], "principale": 7},
                        "per_giornata": [{"giornata": 2, "errore_fantavoto": "?"}, "rotta"]}}
        """#).precisione)
        XCTAssertNil(misto.giornate)
        XCTAssertNil(misto.gioca?.fasciaPrincipale, "indice fuori dall'elenco")
        XCTAssertEqual(misto.perGiornata.count, 1, "la voce illeggibile si salta")
        XCTAssertNil(misto.perGiornata.first?.erroreFantavoto)
    }

    // MARK: Avviso se il consiglio cambia

    func testAvvisoPrimaSiLeggeESiRimandaSoloSeCeraNelServer() throws {
        let nuovo = Data(#"{"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "avviso_prima": 90}"#.utf8)
        var i = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: nuovo)
        XCTAssertEqual(i.avviso_prima, 90)
        i.avviso_prima = 0
        XCTAssertTrue(String(decoding: try JSONEncoder().encode(i), as: UTF8.self).contains(#""avviso_prima":0"#))
        // server vecchio: niente campo, niente scelta e niente invio
        let vecchio = Data(#"{"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true}"#.utf8)
        let v = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: vecchio)
        XCTAssertNil(v.avviso_prima)
        XCTAssertFalse(String(decoding: try JSONEncoder().encode(v), as: UTF8.self).contains("avviso_prima"))
        // tipo strano: vale «non mandato», il resto si legge
        let strano = Data(#"{"cambi": false, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "avviso_prima": "un'ora", "silenzio": "sì"}"#.utf8)
        let s = try JSONDecoder().decode(ImpostazioniAvvisi.self, from: strano)
        XCTAssertNil(s.avviso_prima)
        XCTAssertNil(s.silenzio)
        XCTAssertFalse(s.cambi)
    }

    func testAvvisoPrimaTestiEScelte() {
        XCTAssertEqual(AvvisoPrima.valori.map(AvvisoPrima.testo), ["Spento", "30 minuti prima", "1 ora prima", "1 ora e mezza prima"])
        XCTAssertEqual(AvvisoPrima.scelte(attuale: 60), [0, 30, 60, 90])
        XCTAssertEqual(AvvisoPrima.scelte(attuale: 45), [0, 30, 45, 60, 90], "un valore nuovo del server resta scelto")
        XCTAssertEqual(AvvisoPrima.testo(45), "45 minuti prima")
        XCTAssertEqual(AvvisoPrima.predefinito, 60)
    }

    func testDemoHaEntrambeLeFunzioni() throws {
        let risposte = FinteServer.demo.risposte
        let d = try diario(try XCTUnwrap(risposte["/api/diario"]))
        XCTAssertNotNil(TestoPrecisione(d.precisione))
        let s = try JSONDecoder().decode(StatoAvvisi.self, from: Data(try XCTUnwrap(risposte["/api/avvisi"]).utf8))
        XCTAssertEqual(s.impostazioni.avviso_prima, 60)
    }
}
