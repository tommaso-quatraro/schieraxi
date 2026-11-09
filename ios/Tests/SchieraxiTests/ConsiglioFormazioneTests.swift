import Foundation
import Testing
@testable import Schieraxi

/// Stato dei dati: gli indicatori del consiglio di formazione (#366) con le parole della web (`cartaConsiglio` di `fanta/web/app.js`,
/// testi `sd.cons_*` del catalogo comune). La fixture `stato-dati-consiglio.json` è la risposta vera del server con 8 giornate e
/// due utenti, due indicatori fuori soglia (la controlla `tests/test_stato_dati_consiglio_web.py`, che prova la web sugli stessi numeri).
@Suite("Consiglio di formazione in Stato dei dati")
struct ConsiglioFormazioneTests {
    private func consiglio() throws -> StatoDati.Consiglio {
        let s: StatoDati = try Fixture.decodifica("stato-dati-consiglio")
        return try #require(s.consiglio)
    }

    /// Un campo `consiglio` scritto a mano, decodificato come fa l'app.
    private func consiglio(_ json: String) throws -> StatoDati.Consiglio {
        let s: StatoDati = try Decodifica.decodifica(Data(#"{"stagione": "2026-27", "consiglio": \#(json)}"#.utf8))
        return try #require(s.consiglio)
    }

    @Test("Si legge la risposta vera del server")
    func decodifica() throws {
        let c = try consiglio()
        #expect(c.finestra == 8)
        #expect(c.giornate == 8)
        #expect(c.voci == 16)
        #expect(c.verdetto == true)
        #expect(c.menoS2 == 1.0)
        #expect(c.menoSchierata == -0.25)
        #expect(c.cambi == 1.5)
        #expect(c.cambiSottoSoglia == 1)
        #expect(c.improbabili == 8)
        #expect(c.conCompagno == 0)
        #expect(c.storte == 16)
        #expect(c.spiegate == 16)
        #expect(c.senzaMotivo == 0.045)
        let soglie = try #require(c.soglie)
        #expect(soglie.c1 == 0)
        #expect(soglie.c2 == 0)
        #expect(soglie.c3 == 0)
        #expect(soglie.c4SenzaMotivo == 0.1)
        let regge = try #require(c.regge)
        #expect(regge.c1 == false)
        #expect(regge.c2 == false)
        #expect(regge.c3 == true)
        #expect(regge.c4 == true)
    }

    @Test("Un server senza il campo: la pagina si legge lo stesso", arguments: ["stato-dati", "stato-dati-registro"])
    func senzaConsiglio(fixture: String) throws {
        let s: StatoDati = try Fixture.decodifica(fixture)
        #expect(s.consiglio == nil)
        #expect(s.stagione == "2026-27")
    }

    @Test("Media e soglia di ogni indicatore, scritte come la web")
    func dettagli() throws {
        let c = try consiglio()
        #expect(ParoleConsiglio.dettaglio(.valore, di: c)
                == "+1,00 punti a giornata (deve stare a 0 o più) · −0,25 rispetto alla formazione schierata, quando è diversa")
        #expect(ParoleConsiglio.dettaglio(.stabilita, di: c)
                == "1,5 a formazione, in media · per meno di 1 punto atteso, senza un titolare diventato fuori o improbabile: 1 (devono essere 0)")
        #expect(ParoleConsiglio.dettaglio(.chiGioca, di: c)
                == "sotto il 20% o fuori: 8 · con un compagno di ruolo al 50% o più tra gli esclusi: 0 (devono essere 0)")
        #expect(ParoleConsiglio.dettaglio(.perche, di: c)
                == "spiegate 16 su 16 (devono essere tutte) · titolari senza un motivo loro in «Perché questo numero»: 4,5% (al massimo 10%)")
    }

    @Test("Regge o non regge come dice il server")
    func esitiDelServer() throws {
        let c = try consiglio()
        #expect(ParoleConsiglio.esito(.valore, di: c) == .nonRegge)
        #expect(ParoleConsiglio.esito(.stabilita, di: c) == .nonRegge)
        #expect(ParoleConsiglio.esito(.chiGioca, di: c) == .regge)
        #expect(ParoleConsiglio.esito(.perche, di: c) == .regge)
        #expect(ParoleConsiglio.sottotitolo(c) == "Media delle ultime 8 giornate, su 16 formazioni.")
    }

    @Test("Con il verdetto il client non ricalcola: scrive quello che dice il server")
    func verdettoDelServer() throws {
        let c = try consiglio(#"{"finestra": 8, "giornate": 8, "voci": 8, "meno_s2": -3.0, "cambi_sotto_soglia": 5, "verdetto": true, "regge": {"C1": true, "C2": null, "C3": false}}"#)
        #expect(ParoleConsiglio.esito(.valore, di: c) == .regge)
        #expect(ParoleConsiglio.esito(.stabilita, di: c) == .senzaDati)
        #expect(ParoleConsiglio.esito(.chiGioca, di: c) == .nonRegge)
        #expect(ParoleConsiglio.esito(.perche, di: c) == .senzaDati)
    }

    @Test("Prima di 8 giornate: quante ne servono ancora, per ogni indicatore")
    func servonoAncora() throws {
        let c = try consiglio(#"{"finestra": 8, "soglie": {"C1": 0.0, "C2": 0, "C3": 0, "C4_senza_motivo": 0.1}, "giornate": 3, "voci": 3, "meno_s2": 1.0, "verdetto": false, "regge": {"C1": null, "C2": null, "C3": null, "C4": null}}"#)
        for indicatore in ParoleConsiglio.Indicatore.allCases {
            #expect(ParoleConsiglio.esito(indicatore, di: c) == .servono(5), "\(indicatore)")
        }
        #expect(ParoleConsiglio.sottotitolo(c) == "Media delle ultime 3 giornate, su 3 formazioni.")
        #expect(ParoleConsiglio.dettaglio(.valore, di: c) == "+1,00 punti a giornata (deve stare a 0 o più)")
    }

    @Test("Senza giornate misurate: la frase di attesa")
    func senzaGiornate() throws {
        let c = try consiglio(#"{"finestra": 8, "giornate": 0, "voci": 0, "verdetto": false, "per_giornata": []}"#)
        #expect(ParoleConsiglio.sottotitolo(c) == ParoleConsiglio.nessuna)
    }

    @Test("Numeri che mancano: «–», mai un numero inventato")
    func numeriMancanti() throws {
        let c = try consiglio(#"{"finestra": 8, "giornate": 8, "voci": 8, "meno_s2": null, "meno_schierata": null, "cambi": null, "verdetto": true, "soglie": {"C1": 0.0, "C2": 0, "C3": 0, "C4_senza_motivo": 0.1}}"#)
        #expect(ParoleConsiglio.dettaglio(.valore, di: c) == "– punti a giornata (deve stare a 0 o più)")
        #expect(ParoleConsiglio.dettaglio(.chiGioca, di: c)
                == "sotto il 20% o fuori: – · con un compagno di ruolo al 50% o più tra gli esclusi: – (devono essere 0)")
        #expect(ParoleConsiglio.punti(nil) == "–")
        #expect(ParoleConsiglio.punti(0.004) == "0,00")
        #expect(ParoleConsiglio.intero(nil) == "–")
        #expect(ParoleConsiglio.intero(1234) == "1234")
    }

    // MARK: - stesse parole della web (catalogo)

    @Test("Titolo, spiegazione, nomi degli indicatori come la web")
    func frasiComeLaWeb() {
        #expect(Catalogo.Sd.consTitolo == ParoleConsiglio.titolo)
        #expect(Catalogo.Sd.consSpiega == ParoleConsiglio.spiega)
        #expect(Catalogo.Sd.consNessuna == ParoleConsiglio.nessuna)
        #expect(Catalogo.Sd.consC1 == ParoleConsiglio.nome(.valore))
        #expect(Catalogo.Sd.consC2 == ParoleConsiglio.nome(.stabilita))
        #expect(Catalogo.Sd.consC3 == ParoleConsiglio.nome(.chiGioca))
        #expect(Catalogo.Sd.consC4 == ParoleConsiglio.nome(.perche))
    }

    @Test("Plurali con i modelli della web", arguments: [1, 3])
    func pluraliComeLaWeb(n: Int) {
        let formazioni = Catalogo.Sd.consFormazioni(n)
        #expect(formazioni == ParoleConsiglio.formazioni(n))
        #expect(formazioni == (n == 1 ? "1 formazione" : "\(n) formazioni"))
        #expect(Catalogo.Sd.consMedia(n, f: formazioni) == ParoleConsiglio.media(giornate: n, formazioni: n))
    }

    @Test("Righe con i numeri: i modelli della web riempiti")
    func righeComeLaWeb() throws {
        let c = try consiglio()
        let c1 = Catalogo.Sd.consC1Riga(s: "0", v: "+1,00") + " · " + Catalogo.Sd.consC1Schierata(w: "−0,25")
        #expect(c1 == ParoleConsiglio.dettaglio(.valore, di: c))
        #expect(Catalogo.Sd.consC2Riga(c: "1,5", n: "1", s: "0") == ParoleConsiglio.dettaglio(.stabilita, di: c))
        #expect(Catalogo.Sd.consC3Riga(i: "8", n: "0", s: "0") == ParoleConsiglio.dettaglio(.chiGioca, di: c))
        #expect(Catalogo.Sd.consC4Riga(s: "10%", sp: "16", st: "16", v: "4,5%") == ParoleConsiglio.dettaglio(.perche, di: c))
    }

    @Test("Niente sigle degli indicatori nelle parole per chi legge")
    func nienteSigle() throws {
        let c = try consiglio()
        var testi = [ParoleConsiglio.titolo, ParoleConsiglio.spiega, ParoleConsiglio.nessuna, ParoleConsiglio.sottotitolo(c)]
        for indicatore in ParoleConsiglio.Indicatore.allCases {
            testi += [ParoleConsiglio.nome(indicatore), ParoleConsiglio.dettaglio(indicatore, di: c)]
        }
        for testo in testi {
            #expect(testo.range(of: #"\bC[1-4]\b"#, options: .regularExpression) == nil, "\(testo)")
        }
    }

    // MARK: - demo (foto e anteprima)

    @Test("La demo ha gli indicatori: verdetto, uno che non regge e tutti i numeri")
    func demo() async throws {
        let demo = FinteServer.demoFissata(adesso: Date(timeIntervalSinceReferenceDate: 815_000_000))
        let s: StatoDati = try Decodifica.decodifica(try await demo.richiesta("GET", "/api/stato-dati", corpo: nil))
        let c = try #require(s.consiglio)
        #expect(c.verdetto == true)
        let esiti = ParoleConsiglio.Indicatore.allCases.map { ParoleConsiglio.esito($0, di: c) }
        #expect(esiti.contains(.regge))
        #expect(esiti.contains(.nonRegge))
        for indicatore in ParoleConsiglio.Indicatore.allCases {
            #expect(!ParoleConsiglio.dettaglio(indicatore, di: c).contains("–"), "\(indicatore)")
        }
    }
}
