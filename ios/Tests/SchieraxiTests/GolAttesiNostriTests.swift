import Foundation
import Testing
@testable import Schieraxi

/// Stato dei dati: i gol attesi «nostri» senza Understat (I4 dal vivo, #401) con le parole della web (`cartaNostri` di
/// `fanta/web/app.js`, testi `sd.nos_*` di `fanta/web/testi.js`). La fixture `stato-dati-nostri.json` è la risposta vera del server
/// (`registro_nostri.riepilogo`): 8 giornate misurate della versione 3 (dalla 2 alla 9), la 1 di un'altra versione, la 10 persa e la
/// 11 salvata e non ancora misurata. La controlla `tests/test_stato_dati_nostri_web.py`, che prova la web sugli stessi numeri.
@Suite("Gol attesi nostri in Stato dei dati")
struct GolAttesiNostriTests {
    private func nostri() throws -> StatoDati.RegistroNostri {
        let s: StatoDati = try Fixture.decodifica("stato-dati-nostri")
        return try #require(s.registroNostri)
    }

    /// Un campo `registro_nostri` scritto a mano (solo per i casi che la fixture non ha), letto come fa l'app.
    private func nostri(_ json: String) throws -> StatoDati.RegistroNostri {
        let s: StatoDati = try Decodifica.decodifica(Data("{\"stagione\":\"2026-27\",\"registro_nostri\":\(json)}".utf8))
        return try #require(s.registroNostri)
    }

    private func giornata(_ json: String) throws -> StatoDati.RegistroNostri.Giornata {
        try #require(try nostri("{\"per_giornata\":[\(json)]}").perGiornata?.first)
    }

    /// Un modello di testi.js con i segnaposto riempiti, come fa `t()` della web.
    private func riempi(_ modello: String, _ valori: [String: String]) -> String {
        valori.reduce(modello) { $0.replacingOccurrences(of: "{\($1.key)}", with: $1.value) }
    }

    @Test("Si legge la risposta vera del server")
    func decodifica() throws {
        let n = try nostri()
        #expect(n.versione == "3")
        #expect(n.finestra == 8)
        #expect(n.giornate == 8)
        #expect(n.verdetto == true)
        #expect(n.reggeTutto == false)
        #expect(n.errorePct == 0.006)
        #expect(n.punti == -0.1)
        #expect(n.scartoGol == 0.05)
        #expect(n.golSuVeri == 0.944)
        #expect(n.golSuVeriMostrati == 0.979)
        let soglie = try #require(n.soglie)
        #expect(soglie.errore == 0.01)
        #expect(soglie.punti == -0.3)
        #expect(soglie.scartoGol == 0.03)
        let regge = try #require(n.regge)
        #expect(regge.errore == true)
        #expect(regge.punti == true)
        #expect(regge.gol == false)
        let giornate = try #require(n.perGiornata)
        #expect(giornate.map { $0.giornata ?? -1 } == Array((1...11).reversed()))
        #expect(giornate[0].giocatori == 3)
        #expect(giornate[0].misurato == nil)
        #expect(giornate[1].persa?.hasPrefix("nessun tentativo") == true)
        #expect(giornate[2].errorePct == 0.006)
        #expect(giornate[2].golSuVeri == 0.944)
        #expect(giornate.last?.versione == "2")
    }

    @Test("Un server senza il campo, o che non riesce a leggerlo: la pagina si legge lo stesso")
    func senzaCampo() throws {
        let vecchio: StatoDati = try Fixture.decodifica("stato-dati")
        #expect(vecchio.registroNostri == nil)
        let nullo: StatoDati = try Decodifica.decodifica(Data("{\"stagione\":\"2026-27\",\"registro_nostri\":null}".utf8))
        #expect(nullo.registroNostri == nil)
        #expect(nullo.stagione == "2026-27")
    }

    @Test("Il verdetto delle tre misure insieme e di ognuna, come dice il server")
    func esitiDelServer() throws {
        let n = try nostri()
        #expect(ParoleNostri.esitoInsieme(n) == .nonRegge)
        #expect(ParoleNostri.testoInsieme(ParoleNostri.esitoInsieme(n)) == "non reggono")
        #expect(ParoleNostri.esito(.errore, di: n) == .regge)
        #expect(ParoleNostri.esito(.punti, di: n) == .regge)
        #expect(ParoleNostri.esito(.gol, di: n) == .nonRegge)
        #expect(ParoleNostri.sottotitolo(n) == "Media delle ultime 8 giornate misurate, versione 3 del calcolo.")
    }

    @Test("Media e soglia di ogni misura, scritte come la web")
    func dettagli() throws {
        let n = try nostri()
        #expect(ParoleNostri.dettaglio(.errore, di: n) == "+0,6% (deve stare a +1% o meno)")
        #expect(ParoleNostri.dettaglio(.punti, di: n) == "−0,10 punti a rosa e giornata (deve stare a −0,3 o più)")
        #expect(ParoleNostri.dettaglio(.gol, di: n)
                == "scarto più grande 0,050 gol a giocatore (al massimo 0,030) · gol attesi su veri 0,94, con i numeri mostrati 0,98")
    }

    /// Giornate misurate e quante ne mancano alle 8 che servono per il verdetto.
    static let attese: [(Int, Int)] = [(0, 8), (1, 7), (3, 5), (7, 1)]

    @Test("Prima di 8 giornate: quante ne servono ancora, qualunque cosa dica `regge_tutto`", arguments: GolAttesiNostriTests.attese)
    func servonoAncora(giornate: Int, mancano: Int) throws {
        for tutto in ["true", "false", "null"] {
            let n = try nostri("{\"finestra\":8,\"giornate\":\(giornate),\"verdetto\":false,\"regge_tutto\":\(tutto)}")
            #expect(ParoleNostri.esitoInsieme(n) == .servono(mancano))
            #expect(ParoleNostri.esito(.errore, di: n) == .servono(mancano))
        }
    }

    @Test("Con il verdetto il client non ricalcola: scrive quello che dice il server")
    func verdettoDelServer() throws {
        let n = try nostri("{\"finestra\":8,\"giornate\":8,\"verdetto\":true,\"regge_tutto\":true,"
                           + "\"regge\":{\"errore\":false,\"punti\":null,\"gol\":true}}")
        #expect(ParoleNostri.esitoInsieme(n) == .regge)
        #expect(ParoleNostri.testoInsieme(.regge) == "reggono")
        #expect(ParoleNostri.esito(.errore, di: n) == .nonRegge)
        #expect(ParoleNostri.esito(.punti, di: n) == .senzaDati)
        #expect(ParoleNostri.esito(.gol, di: n) == .regge)
        #expect(ParoleNostri.testoInsieme(.servono(3)) == "servono ancora 3 giornate")
    }

    @Test("Le giornate una per una: da misurare, persa con il motivo, misurata, di un'altra versione")
    func giornate() throws {
        let n = try nostri()
        let g = try #require(n.perGiornata)
        #expect(ParoleNostri.giornata(g[0]) == "Serie A 2026-27, giornata 11")
        #expect(ParoleNostri.stato(g[0], versione: n.versione) == "salvati i numeri di 3 giocatori, da misurare a giornata finita")
        #expect(!ParoleNostri.persa(g[0]))
        #expect(ParoleNostri.stato(g[1], versione: n.versione) == g[1].persa)
        #expect(ParoleNostri.persa(g[1]))
        #expect(ParoleNostri.stato(g[2], versione: n.versione) == "errore +0,6% · punti −0,10 · gol attesi su veri 0,94")
        let vecchia = try #require(g.last)
        #expect(ParoleNostri.giornata(vecchia) == "Serie A 2026-27, giornata 1")
        #expect(ParoleNostri.stato(vecchia, versione: n.versione)
                == "errore +0,6% · punti −0,10 · gol attesi su veri 0,94 · versione 2, non conta")
        let vuota = try giornata("{\"stagione\":\"2026-27\",\"giornata\":4,\"versione\":\"3\",\"misurato\":\"2026-10-04T12:00:00\",\"voti\":0}")
        #expect(ParoleNostri.stato(vuota, versione: "3") == "misurata, ma senza giocatori da confrontare")
        let una = try giornata("{\"stagione\":\"2026-27\",\"giornata\":12,\"versione\":\"3\",\"giocatori\":1}")
        #expect(ParoleNostri.stato(una, versione: "3") == "salvati i numeri di 1 giocatore, da misurare a giornata finita")
    }

    @Test("Senza giornate misurate: la spiegazione con la versione")
    func nessuna() throws {
        let n = try nostri("{\"versione\":\"3\",\"finestra\":8,\"giornate\":0,\"verdetto\":false,\"per_giornata\":[]}")
        #expect(ParoleNostri.sottotitolo(n) == "Ancora nessuna giornata misurata con la versione 3 del calcolo: i numeri arrivano il "
                + "giorno dopo la fine della prima giornata salvata.")
    }

    @Test("Numeri che mancano: «–», mai «nan»")
    func numeriMancanti() throws {
        let n = try nostri("{\"versione\":\"3\",\"giornate\":2}")
        for misura in ParoleNostri.Misura.allCases {
            let testo = ParoleNostri.dettaglio(misura, di: n)
            #expect(testo.contains("–"), "\(misura)")
            #expect(!testo.lowercased().contains("nan"), "\(misura)")
        }
    }

    // MARK: - stesse parole della web (testi.js)

    @Test("Titolo, spiegazione, nomi delle misure e verdetti come la web")
    func frasiComeLaWeb() throws {
        let web = try TestiWeb()
        #expect(try web.italiano("sd.nos_titolo") == ParoleNostri.titolo)
        #expect(try web.italiano("sd.nos_spiega") == ParoleNostri.spiega)
        #expect(try web.italiano("sd.nos_insieme") == ParoleNostri.insieme)
        #expect(try web.italiano("sd.nos_reggono") == ParoleNostri.testoInsieme(.regge))
        #expect(try web.italiano("sd.nos_non_reggono") == ParoleNostri.testoInsieme(.nonRegge))
        #expect(try web.italiano("sd.nos_errore") == ParoleNostri.nome(.errore))
        #expect(try web.italiano("sd.nos_punti") == ParoleNostri.nome(.punti))
        #expect(try web.italiano("sd.nos_gol") == ParoleNostri.nome(.gol))
        #expect(try web.italiano("sd.nos_per_giornata") == ParoleNostri.perGiornata)
        #expect(try web.italiano("sd.nos_g_vuota") == ParoleNostri.vuota)
        // le misure usano le parole del registro delle giornate
        #expect(try web.italiano("sd.reg_regge") == ParoleRegistro.Esito.regge.testo)
        #expect(try web.italiano("sd.reg_non_regge") == ParoleRegistro.Esito.nonRegge.testo)
    }

    @Test("Plurali con i modelli della web", arguments: [1, 3])
    func pluraliComeLaWeb(n: Int) throws {
        let web = try TestiWeb()
        let forma = n == 1 ? "one" : "other"
        #expect(try riempi(web.italiano("sd.nos_media.\(forma)"), ["n": "\(n)", "v": "3"]) == ParoleNostri.media(giornate: n, versione: "3"))
        #expect(try riempi(web.italiano("sd.nos_g_da_misurare.\(forma)"), ["n": "\(n)"]) == ParoleNostri.daMisurare(giocatori: n))
        #expect(try riempi(web.italiano("sd.reg_servono.\(forma)"), ["n": "\(n)"]) == ParoleNostri.testoInsieme(.servono(n)))
    }

    @Test("Righe con i numeri: i modelli della web riempiti")
    func righeComeLaWeb() throws {
        let web = try TestiWeb()
        let n = try nostri()
        #expect(try riempi(web.italiano("sd.nos_errore_riga"), ["v": "+0,6%", "s": "+1%"]) == ParoleNostri.dettaglio(.errore, di: n))
        #expect(try riempi(web.italiano("sd.nos_punti_riga"), ["v": "−0,10", "s": "−0,3"]) == ParoleNostri.dettaglio(.punti, di: n))
        #expect(try riempi(web.italiano("sd.nos_gol_riga"), ["v": "0,050", "s": "0,030", "g": "0,94", "m": "0,98"])
                == ParoleNostri.dettaglio(.gol, di: n))
        #expect(try riempi(web.italiano("sd.nos_nessuna"), ["v": "3"]) == ParoleNostri.nessuna(versione: "3"))
        let g = try #require(n.perGiornata)
        #expect(try riempi(web.italiano("sd.reg_giornata"), ["s": "2026-27", "g": "11"]) == ParoleNostri.giornata(g[0]))
        let misurata = try riempi(web.italiano("sd.nos_g_misurata"), ["e": "+0,6%", "p": "−0,10", "g": "0,94"])
        #expect(misurata == ParoleNostri.stato(g[2], versione: n.versione))
        let vecchia = try #require(g.last)
        #expect(try misurata + " · " + riempi(web.italiano("sd.nos_g_versione"), ["v": "2"])
                == ParoleNostri.stato(vecchia, versione: n.versione))
    }

    // MARK: - demo (foto e anteprima)

    @Test("La demo ha i gol attesi nostri: verdetto, una misura che non regge, una giornata persa e una da misurare")
    func demo() async throws {
        let demo = FinteServer.demoFissata(adesso: Date(timeIntervalSinceReferenceDate: 815_000_000))
        let s: StatoDati = try Decodifica.decodifica(try await demo.richiesta("GET", "/api/stato-dati", corpo: nil))
        let n = try #require(s.registroNostri)
        #expect(n.verdetto == true)
        let esiti = ParoleNostri.Misura.allCases.map { ParoleNostri.esito($0, di: n) }
        #expect(esiti.contains(.regge))
        #expect(esiti.contains(.nonRegge))
        #expect(ParoleNostri.esitoInsieme(n) == .nonRegge)
        for misura in ParoleNostri.Misura.allCases {
            #expect(!ParoleNostri.dettaglio(misura, di: n).contains("–"), "\(misura)")
        }
        let giornate = n.perGiornata ?? []
        #expect(giornate.contains { ParoleNostri.persa($0) })
        #expect(giornate.contains { $0.misurato == nil && !ParoleNostri.persa($0) })
        #expect(giornate.allSatisfy { !ParoleNostri.stato($0, versione: n.versione).contains("–") })
    }
}
