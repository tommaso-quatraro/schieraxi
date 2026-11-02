import XCTest
@testable import Schieraxi

/// Scheda del giocatore ed elenco: numeri e colori che si spiegano da soli.
@MainActor
final class SchedaChiaraTests: XCTestCase {
    private func giocatore(_ extra: String) throws -> Giocatore {
        let json = "{\(extra) \"id\": 7, \"nome\": \"Retalli\", \"ruolo\": \"A\", \"punti_attesi\": 7.2, \"p_voto\": 0.9}"
        return try Decodifica.decodifica(Data(json.utf8))
    }

    func testRisultatoAttesoComeSulWeb() throws {
        let g = try giocatore(#""squadra": "genoa", "avversario": "como", "gol_squadra": 2.08, "gol_avversario": 1,"#)
        XCTAssertEqual(GiocatoreCorpo.risultatoAtteso(g), "Risultato atteso 2,1–1,0", "una cifra decimale e il trattino lungo, come il web")
        XCTAssertEqual(GiocatoreCorpo.voceRisultatoAtteso(g, squadra: "GENOA"), "Risultato atteso: Genoa 2,1, Como 1,0")
        let senzaNomi = try giocatore(#""gol_squadra": 1.8, "gol_avversario": 1.2,"#)
        XCTAssertEqual(GiocatoreCorpo.risultatoAtteso(senzaNomi), "Risultato atteso 1,8–1,2")
        XCTAssertEqual(GiocatoreCorpo.voceRisultatoAtteso(senzaNomi, squadra: nil), "Risultato atteso: 1,8 a 1,2")
        XCTAssertNil(GiocatoreCorpo.risultatoAtteso(try giocatore(#""gol_squadra": 1.8,"#)), "con un numero solo non si mostra")
        XCTAssertNil(GiocatoreCorpo.risultatoAtteso(try giocatore("")))
    }

    func testLaRigaDellElencoComeLaWeb() throws {
        let g = try giocatore(#""squadra": "genoa", "quotazione": 19, "proprietario": null, "fv_atteso": 6.94, "indice": 80,"#)
        let d = DatiRigaElenco(g)
        XCTAssertEqual(d.dettaglio, "GEN · quotazione 19 · svincolato", "sigla, mai il nome intero in maiuscolo")
        XCTAssertEqual(d.numero, "6,9")
        XCTAssertEqual(d.sotto, "gioca 90%")
        let mio = try giocatore(#""squadra": "genoa", "quotazione": 19, "proprietario": "Squadra Uno","#)
        XCTAssertEqual(DatiRigaElenco(mio).dettaglio, "GEN · quotazione 19 · Squadra Uno")
        let breve = GiocatoreBreve(id: 9, nome: "Fosola", ruolo: "C", squadra: "inter", quotazione: 4)
        XCTAssertEqual(DatiRigaElenco(breve, nonGioca: true).dettaglio, "INT · quotazione 4", "il proprietario non si conosce: non si scrive")
        XCTAssertEqual(DatiRigaElenco(breve, nonGioca: true).numero, "–")
        XCTAssertEqual(DatiRigaElenco(breve, nonGioca: true).sotto, "non gioca")
        XCTAssertNil(DatiRigaElenco(breve, nonGioca: false).sotto, "senza l'elenco della giornata non si dice «non gioca»")
    }

    func testCelleDelCalendarioVsEChiocciola() {
        XCTAssertEqual(ProssimePartite.cella(PartitaCalendario(giornata: 8, avversario: "milan", inCasa: true, difficolta: 3, data: nil)), "vs MIL")
        XCTAssertEqual(ProssimePartite.cella(PartitaCalendario(giornata: 9, avversario: "milan", inCasa: false, difficolta: 3, data: nil)), "@ MIL")
    }

    func testLaSchedaUsaLaGiornataDellaLega() throws {
        XCTAssertEqual(GiocatoreCorpo.giornataMostrata(try giocatore(#""giornata": 11, "giornata_lega": 8,"#)), 8)
        XCTAssertEqual(GiocatoreCorpo.giornataMostrata(try giocatore(#""giornata": 11,"#)), 11, "server vecchio: il numero di prima")
    }

    private func voto(_ giornata: Int, _ fv: Double?, _ voto: Double? = nil) -> VotoGiornata {
        VotoGiornata(giornata: giornata, voto: voto ?? fv.map { $0 - 0.5 }, fv: fv, gol: nil, assist: nil)
    }

    func testIlGraficoDeiVotiSiInterrompeSenzaVoto() {
        let voti = [voto(1, 6.5), voto(2, 7), voto(3, nil, nil), voto(4, 6), voto(6, 8), voto(7, nil, nil)]
        let fv = GraficoVoti.puntiDi(voti).filter { $0.serie == "Fantavoto" }
        XCTAssertEqual(fv.map(\.giornata), [1, 2, 4, 6], "nessun punto inventato nelle giornate senza voto")
        XCTAssertEqual(fv.map(\.tratto), [0, 0, 1, 2], "la sv (G3) e la giornata che manca (G5) spezzano la linea")
        XCTAssertEqual(GraficoVoti.giornateSenzaVoto(voti), [3, 7], "anche l'ultima giornata senza voto resta nel grafico")
        XCTAssertEqual(GraficoVoti.puntiDi(voti).filter { $0.serie == "Voto" }.count, 4)
    }

    func testIlGraficoSenzaGiornateSenzaVotoEUnaLineaSola() {
        let voti = [voto(3, 6), voto(1, 7), voto(2, 5.5)]
        let fv = GraficoVoti.puntiDi(voti).filter { $0.serie == "Fantavoto" }
        XCTAssertEqual(fv.map(\.giornata), [1, 2, 3], "in ordine di giornata")
        XCTAssertEqual(Set(fv.map(\.linea)).count, 1)
        XCTAssertTrue(GraficoVoti.giornateSenzaVoto(voti).isEmpty)
    }

    func testLaTitolaritaEAParoleSenzaNumero() throws {
        let g = try giocatore(#""titolarita": "titolare", "stato": "titolare", "percentuale": 90,"#)
        XCTAssertEqual(g.etichette.first?.testo, "Probabile titolare", "una sola percentuale all'utente: «gioca N%»")
        let b = try giocatore(#""titolarita": "ballottaggio", "stato": "titolare", "percentuale": 55,"#)
        XCTAssertEqual(b.etichette.first?.testo, "In ballottaggio")
        let p = try giocatore(#""titolarita": "panchina","#)
        XCTAssertEqual(p.etichette.first?.testo, "Probabile panchina")
        XCTAssertFalse(g.etichette.contains { $0.testo.contains("%") })
    }

    func testAGiornataIniziataSiVedeLoStatoDellaPartita() throws {
        let fatto = try giocatore(#""titolarita": null, "stato_partita": "fatto","#)
        XCTAssertEqual(fatto.etichette.first?.testo, "Ha giocato")
        let senza = try giocatore(#""stato_partita": "senza_voto","#)
        XCTAssertEqual(senza.etichette.first?.testo, "Senza voto")
        XCTAssertEqual(senza.etichette.first?.gravita, .attenzione, "arancio come la web (STATO_PARTITA in app.js)")
        XCTAssertEqual(try giocatore(#""stato_partita": "attesa_voti","#).etichette.first?.testo, "Voto in arrivo")
        XCTAssertEqual(try giocatore(#""stato_partita": "in_corso","#).etichette.first?.testo, "Partita in corso")
        XCTAssertEqual(try giocatore(#""stato_partita": "rinviata","#).etichette.first?.testo, "Rinviata")
        let fuori = try giocatore(#""titolarita": "fuori", "stato_partita": "da_giocare","#)
        XCTAssertEqual(fuori.etichette.first?.testo, "Fuori", "infortunati e squalificati restano «Fuori»")
        XCTAssertTrue(try giocatore(#""stato_partita": "strano","#).etichette.isEmpty, "uno stato sconosciuto non si mostra")
    }

    func testLaLegendaDellElencoSpiegaAnelloEPercentuale() {
        XCTAssertTrue(ClassificaView.legendaBreve.contains("fantavoto atteso"))
        XCTAssertLessThanOrEqual(ClassificaView.legendaBreve.count, 50, "sopra l'elenco una riga sola")
        XCTAssertTrue(ClassificaView.legenda.contains("indice"))
        XCTAssertTrue(ClassificaView.legenda.contains("gioca"))
    }

    func testLaSchedaCaricaTuttoInsieme() async throws {
        let s = ServerDiProva.conFixture(["/api/giocatore/": "giocatore", "/api/calendario": "calendario",
                                          "/api/osservati": "osservati", "/api/formazione": "formazione"])
        let vm = SchedaGiocatoreViewModel(id: 1, server: s)
        await vm.carica()
        XCTAssertNotNil(vm.caricatore.dato)
        XCTAssertNotNil(vm.calendario.dato)
        XCTAssertNotNil(vm.formazione.dato)
        XCTAssertNotNil(vm.osservato)
    }
}
