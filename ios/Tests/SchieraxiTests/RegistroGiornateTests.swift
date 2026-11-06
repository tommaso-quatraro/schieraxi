import Foundation
import Testing
@testable import Schieraxi

/// Stato dei dati: il registro delle giornate (#344) con le parole della web (`cartaRegistro` di `fanta/web/app.js`, testi `sd.reg_*`
/// di `fanta/web/testi.js`). La fixture `stato-dati-registro.json` è la risposta vera del server con 8 giornate misurate e la 9 persa
/// (la controlla `tests/test_stato_dati_registro_web.py`, che prova la web sugli stessi numeri).
@Suite("Registro delle giornate in Stato dei dati")
struct RegistroGiornateTests {
    private func registro() throws -> StatoDati.Registro {
        let s: StatoDati = try Fixture.decodifica("stato-dati-registro")
        return try #require(s.registro)
    }

    /// Un modello di testi.js con i segnaposto riempiti, come fa `t()` della web.
    private func riempi(_ modello: String, _ valori: [String: String]) -> String {
        valori.reduce(modello) { $0.replacingOccurrences(of: "{\($1.key)}", with: $1.value) }
    }

    @Test("Si legge la risposta vera del server")
    func decodifica() throws {
        let r = try registro()
        #expect(r.finestra == 8)
        #expect(r.giornate == 8)
        #expect(r.verdetto == true)
        #expect(r.i1 == -0.057)
        #expect(r.erroreModello == 1.0)
        #expect(r.erroreFantamedia == 1.061)
        #expect(r.brier == 0.1)
        #expect(r.calibrazione == 0.1)
        #expect(r.copertura == 0.8)
        let soglie = try #require(r.soglie)
        #expect(soglie.i1 == -0.03)
        #expect(soglie.i2Calibrazione == 0.05)
        #expect(soglie.i2Brier == 0.15)
        #expect(soglie.i3Minimo == 0.72)
        #expect(soglie.i3Massimo == 0.88)
        let regge = try #require(r.regge)
        #expect(regge.i1 == true)
        #expect(regge.i2 == false)
        #expect(regge.i3 == true)
        let giornate = try #require(r.perGiornata)
        #expect(giornate.count == 9)
        #expect(giornate.first?.giornata == 9)
        #expect(giornate.first?.stagione == "2026-27")
        #expect(giornate.first?.persa?.hasPrefix("nessun tentativo") == true)
        #expect(giornate.dropFirst().allSatisfy { $0.persa == nil })
    }

    @Test("Un server senza registro: la pagina si legge lo stesso")
    func senzaRegistro() throws {
        let s: StatoDati = try Fixture.decodifica("stato-dati")
        #expect(s.registro == nil)
        #expect(s.stagione == "2026-27")
    }

    @Test("Media e soglia di ogni misura, scritte come la web")
    func dettagli() throws {
        let r = try registro()
        #expect(ParoleRegistro.dettaglio(.fantavoto, di: r) == "−5,7% (deve stare a −3% o meno) · errore 1,00 contro 1,06")
        #expect(ParoleRegistro.dettaglio(.gioca, di: r) == "scarto 10 punti (al massimo 5) · punteggio di Brier 0,100 (al massimo 0,150)")
        #expect(ParoleRegistro.dettaglio(.fascia, di: r) == "80% (deve stare tra 72% e 88%)")
    }

    @Test("Regge o non regge come dice il server")
    func esitiDelServer() throws {
        let r = try registro()
        #expect(ParoleRegistro.esito(.fantavoto, di: r) == .regge)
        #expect(ParoleRegistro.esito(.gioca, di: r) == .nonRegge)
        #expect(ParoleRegistro.esito(.fascia, di: r) == .regge)
        #expect(ParoleRegistro.sottotitolo(r) == "Media delle ultime 8 giornate misurate.")
    }

    /// Giornate misurate e quante ne mancano alle 8 che servono per il verdetto.
    static let attese: [(Int, Int)] = [(0, 8), (1, 7), (3, 5), (7, 1)]

    @Test("Prima di 8 giornate: quante ne servono ancora, qualunque cosa dica `regge`", arguments: RegistroGiornateTests.attese)
    func servonoAncora(giornate: Int, mancano: Int) {
        for regge in [true, false, nil] as [Bool?] {
            #expect(ParoleRegistro.esito(verdetto: false, regge: regge, giornate: giornate, finestra: 8) == .servono(mancano))
        }
    }

    @Test("Con il verdetto il client non ricalcola: scrive quello che dice il server")
    func verdettoDelServer() {
        #expect(ParoleRegistro.esito(verdetto: true, regge: true, giornate: 8, finestra: 8) == .regge)
        #expect(ParoleRegistro.esito(verdetto: true, regge: false, giornate: 8, finestra: 8) == .nonRegge)
        #expect(ParoleRegistro.esito(verdetto: true, regge: nil, giornate: 8, finestra: 8) == .senzaDati)
        #expect(ParoleRegistro.esito(verdetto: nil, regge: true, giornate: nil, finestra: nil) == .servono(8))
    }

    @Test("Numeri: una cifra decimale senza «,0», il meno tipografico, «–» se manca")
    func cifre() {
        #expect(ParoleRegistro.percento(-0.03, segno: true) == "−3%")
        #expect(ParoleRegistro.percento(-0.057, segno: true) == "−5,7%")
        #expect(ParoleRegistro.percento(0.012, segno: true) == "+1,2%")
        #expect(ParoleRegistro.percento(0.88) == "88%")
        #expect(ParoleRegistro.percento(0.795) == "79,5%")
        #expect(ParoleRegistro.percento(nil) == "–")
        #expect(ParoleRegistro.cifra(0.1, per: 100) == "10")
        #expect(ParoleRegistro.cifra(0.034, per: 100) == "3,4")
        #expect(ParoleRegistro.cifra(nil, per: 100) == "–")
    }

    @Test("Le giornate perse con il motivo del server")
    func perse() throws {
        let r = try registro()
        let perse = ParoleRegistro.perse(r)
        #expect(perse.count == 1)
        let g = try #require(perse.first)
        #expect(ParoleRegistro.giornata(g) == "9ª giornata di Serie A · 2026-27")
    }

    // MARK: - stesse parole della web (testi.js)

    @Test("Titoli, spiegazioni, nomi delle misure e verdetti come la web")
    func frasiComeLaWeb() throws {
        let web = try TestiWeb()
        #expect(try web.italiano("sd.reg_titolo") == ParoleRegistro.titolo)
        #expect(try web.italiano("sd.reg_spiega") == ParoleRegistro.spiega)
        #expect(try web.italiano("sd.reg_nessuna") == ParoleRegistro.nessuna)
        #expect(try web.italiano("sd.reg_perse") == ParoleRegistro.titoloPerse)
        #expect(try web.italiano("sd.reg_perse_spiega") == ParoleRegistro.spiegaPerse)
        #expect(try web.italiano("sd.reg_i1") == ParoleRegistro.nome(.fantavoto))
        #expect(try web.italiano("sd.reg_i2") == ParoleRegistro.nome(.gioca))
        #expect(try web.italiano("sd.reg_i3") == ParoleRegistro.nome(.fascia))
        #expect(try web.italiano("sd.reg_regge") == ParoleRegistro.Esito.regge.testo)
        #expect(try web.italiano("sd.reg_non_regge") == ParoleRegistro.Esito.nonRegge.testo)
        #expect(try web.italiano("sd.nessun_dato") == ParoleRegistro.Esito.senzaDati.testo)
    }

    @Test("Plurali con i modelli della web", arguments: [1, 3])
    func pluraliComeLaWeb(n: Int) throws {
        let web = try TestiWeb()
        let forma = n == 1 ? "one" : "other"
        #expect(try riempi(web.italiano("sd.reg_servono.\(forma)"), ["n": "\(n)"]) == ParoleRegistro.Esito.servono(n).testo)
        #expect(try riempi(web.italiano("sd.reg_media.\(forma)"), ["n": "\(n)"]) == ParoleRegistro.media(giornate: n))
    }

    @Test("Righe con i numeri: i modelli della web riempiti")
    func righeComeLaWeb() throws {
        let web = try TestiWeb()
        let r = try registro()
        #expect(try riempi(web.italiano("sd.reg_i1_riga"), ["v": "−5,7%", "s": "−3%", "m": "1,00", "f": "1,06"])
                == ParoleRegistro.dettaglio(.fantavoto, di: r))
        #expect(try riempi(web.italiano("sd.reg_i2_riga"), ["c": "10", "sc": "5", "b": "0,100", "sb": "0,150"])
                == ParoleRegistro.dettaglio(.gioca, di: r))
        #expect(try riempi(web.italiano("sd.reg_i3_riga"), ["v": "80%", "min": "72%", "max": "88%"])
                == ParoleRegistro.dettaglio(.fascia, di: r))
        let persa = try #require(ParoleRegistro.perse(r).first)
        // la giornata di Serie A come nel resto dell'app (docs/COERENZA-WEB-IPHONE.md, «Giornata: le forme»), poi la stagione
        #expect(ParoleRegistro.giornata(persa) == "9ª giornata di Serie A · 2026-27")
        #expect(try riempi(web.italiano("sd.reg_giornata"), ["s": "2026-27", "g": TempiLega.serieA(9)]) == ParoleRegistro.giornata(persa))
    }

    // MARK: - demo (foto e anteprima)

    @Test("La demo ha un registro completo: verdetto, una misura che non regge e una giornata persa")
    func demo() async throws {
        let demo = FinteServer.demoFissata(adesso: Date(timeIntervalSinceReferenceDate: 815_000_000))
        let s: StatoDati = try Decodifica.decodifica(try await demo.richiesta("GET", "/api/stato-dati", corpo: nil))
        let r = try #require(s.registro)
        #expect(r.verdetto == true)
        let esiti = ParoleRegistro.Misura.allCases.map { ParoleRegistro.esito($0, di: r) }
        #expect(esiti.contains(.regge))
        #expect(esiti.contains(.nonRegge))
        #expect(ParoleRegistro.perse(r).count == 1)
        for misura in ParoleRegistro.Misura.allCases {
            #expect(!ParoleRegistro.dettaglio(misura, di: r).contains("–"), "\(misura)")
        }
    }
}
