import Foundation
import Testing
@testable import Schieraxi

/// Stato dei dati: la riga della taratura di «gioca N%» con le probabili (#379, PR C del piano 2026-11-06-gioca-probabili-server),
/// con le parole della web (`rigaTaratura` di `fanta/web/app.js`, testi `sd.tar_*` e `sd.f_taratura` di `fanta/web/testi.js`).
/// La fixture `stato-dati-taratura.json` è la risposta vera del server (`taratura_probabili.riepilogo`): la versione 1 attiva dal
/// 15/1, con la prova sulle ultime 4 giornate e un cambio rimandato perché la prima partita è vicina. La controlla
/// `tests/test_stato_dati_taratura_web.py`, che prova la web sugli stessi numeri.
/// Brier con quattro decimali e «1 punto» al singolare: decisi dopo la revisione della parte web, che si allinea nello stesso ramo.
@Suite("Taratura di «gioca N%» in Stato dei dati")
struct TaraturaProbabiliTests {
    private static let titolo = "Taratura con le probabili"

    /// Il campo `calibrazione.taratura` scritto a mano (per i casi che la fixture non ha), letto come fa l'app.
    private func taratura(_ json: String) throws -> StatoDati.Taratura? {
        let risposta = "{\"stagione\":\"2026-27\",\"calibrazione\":{\"giornate\":3,\"gruppi\":[],\"taratura\":\(json)}}"
        let s: StatoDati = try Decodifica.decodifica(Data(risposta.utf8))
        return s.calibrazione?.taratura
    }

    private func frase(_ json: String) throws -> String? {
        ParoleRegistro.taratura(try taratura(json))
    }

    /// Un modello di testi.js con i segnaposto riempiti, come fa `t()` della web.
    private func riempi(_ modello: String, _ valori: [String: String]) -> String {
        valori.reduce(modello) { $0.replacingOccurrences(of: "{\($1.key)}", with: $1.value) }
    }

    /// La riga intera della web: «Taratura con le probabili: {s}» (`sd.tar_riga`).
    private func riga(_ web: TestiWeb, _ parti: String) throws -> String {
        riempi(try web.italiano("sd.tar_riga"), ["s": parti])
    }

    @Test("Si legge la risposta vera del server")
    func decodifica() throws {
        let s: StatoDati = try Fixture.decodifica("stato-dati-taratura")
        let t = try #require(s.calibrazione?.taratura)
        #expect(t.stato == "attiva")
        #expect(t.giornate == 10)
        #expect(t.minimo == 4)
        #expect(t.versione == "1")
        #expect(t.dal == "2027-01-15T10:00:00")
        #expect(t.motivo == "scadenza_vicina")
        let p = try #require(t.prova)
        #expect(p.giornate == 4)
        #expect(p.brier == 0.0912)
        #expect(p.brierPrima == 0.0968)
        #expect(p.brierMostrati == 0.0975)
        #expect(p.calibrazione == 0.0213)
    }

    @Test("La frase della risposta vera: attiva, la prova e il cambio rimandato")
    func fraseDellaFixture() throws {
        let s: StatoDati = try Fixture.decodifica("stato-dati-taratura")
        #expect(ParoleRegistro.taratura(s.calibrazione?.taratura)
                == "\(Self.titolo): attiva dal 15/1 (versione 1) · nelle ultime 4 giornate Brier 0,0912 invece di 0,0968, scarto 2,1 punti"
                + " · cambio rimandato: la prima partita è tra meno di 24 ore")
    }

    @Test("Senza il campo, con `null` o con un valore che non si legge: la pagina si apre lo stesso, senza la riga")
    func senzaCampo() throws {
        let vecchio: StatoDati = try Fixture.decodifica("stato-dati")
        #expect(vecchio.calibrazione?.gruppi?.isEmpty == false)
        #expect(vecchio.calibrazione?.taratura == nil)
        #expect(try taratura("null") == nil)
        #expect(ParoleRegistro.taratura(nil) == nil)
        #expect(try frase("\"attiva\"") == nil)
        #expect(try frase("{\"stato\":\"sconosciuto\",\"giornate\":1,\"minimo\":4}") == nil)
        #expect(try frase("{\"stato\":3,\"giornate\":\"x\"}") == nil)
    }

    /// Giornate buone per la taratura, quante ne servono per la prima prova e la frase dopo «Taratura con le probabili: ».
    struct CasoAttesa: Sendable, CustomTestStringConvertible {
        let giornate: Int
        let minimo: Int
        let frase: String
        var testDescription: String { "\(giornate) su \(minimo)" }
    }

    static let casiInAttesa: [CasoAttesa] = [
        CasoAttesa(giornate: 2, minimo: 4, frase: "in attesa · 2 giornate su 4"),
        CasoAttesa(giornate: 1, minimo: 4, frase: "in attesa · 1 giornata su 4"),
        CasoAttesa(giornate: 0, minimo: 4, frase: "in attesa · 0 giornate su 4"),
        // riaccesa da poco, o giornate con poche righe: le giornate bastano ma il verdetto non c'è ancora (niente «6 giornate su 4»)
        CasoAttesa(giornate: 6, minimo: 4, frase: "in attesa · 6 giornate"),
        CasoAttesa(giornate: 4, minimo: 4, frase: "in attesa · 4 giornate"),
        CasoAttesa(giornate: 1, minimo: 0, frase: "in attesa · 1 giornata"),
    ]

    @Test("In attesa: quante giornate su quante, o solo quante se bastano già", arguments: TaraturaProbabiliTests.casiInAttesa)
    func inAttesa(caso: CasoAttesa) throws {
        let json = "{\"stato\":\"in_attesa\",\"giornate\":\(caso.giornate),\"minimo\":\(caso.minimo),\"versione\":null,\"dal\":null,"
            + "\"prova\":null,\"motivo\":null}"
        #expect(try frase(json) == "\(Self.titolo): \(caso.frase)")
    }

    @Test("Attiva: data dalla stringa del server, versione, numeri della prova; «–» se mancano, mai «nan»")
    func attiva() throws {
        let base = "\"stato\":\"attiva\",\"giornate\":8,\"minimo\":4,\"versione\":3"
        let prova = "{\"giornate\":4,\"brier\":0.0912,\"brier_prima\":0.0968,\"brier_mostrati\":0.0975,\"calibrazione\":0.0213}"
        #expect(try frase("{\(base),\"dal\":\"2027-01-15T10:00:00\",\"prova\":\(prova),\"motivo\":null}")
                == "\(Self.titolo): attiva dal 15/1 (versione 3) · nelle ultime 4 giornate Brier 0,0912 invece di 0,0968, scarto 2,1 punti")
        // il giorno è quello scritto dal server, senza fuso orario: le 23:30 del 31/12 restano il 31/12
        #expect(try frase("{\(base),\"dal\":\"2026-12-31T23:30:00\",\"prova\":null,\"motivo\":null}")
                == "\(Self.titolo): attiva dal 31/12 (versione 3)")
        #expect(try frase("{\(base),\"dal\":null,\"prova\":null,\"motivo\":null}") == "\(Self.titolo): attiva (versione 3)")
        #expect(try frase("{\(base),\"dal\":\"x\",\"prova\":null}") == "\(Self.titolo): attiva (versione 3)")
        #expect(try frase("{\(base),\"dal\":\"2027-1-5\",\"prova\":null}") == "\(Self.titolo): attiva (versione 3)")
        let mancano = "{\"giornate\":1,\"brier\":null,\"brier_prima\":0.1,\"brier_mostrati\":null,\"calibrazione\":null}"
        #expect(try frase("{\(base),\"dal\":\"2027-03-02T06:00:00\",\"prova\":\(mancano)}")
                == "\(Self.titolo): attiva dal 2/3 (versione 3) · nell'ultima giornata Brier – invece di 0,1000, scarto – punti")
        // un motivo che non è il cambio rimandato non si aggiunge alla versione attiva
        #expect(try frase("{\(base),\"motivo\":\"non_migliora\"}") == "\(Self.titolo): attiva (versione 3)")
        // la versione come testo, o che manca
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":\"2\"}") == "\(Self.titolo): attiva (versione 2)")
        #expect(try frase("{\"stato\":\"attiva\"}") == "\(Self.titolo): attiva (versione –)")
    }

    @Test("Scarto di 1 punto al singolare, Brier sempre con quattro decimali")
    func unPunto() throws {
        let prova = "{\"giornate\":5,\"brier\":0.0955,\"brier_prima\":0.0961,\"calibrazione\":0.0104}"
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":2,\"prova\":\(prova)}")
                == "\(Self.titolo): attiva (versione 2) · nelle ultime 5 giornate Brier 0,0955 invece di 0,0961, scarto 1 punto")
        let quasi = "{\"giornate\":5,\"brier\":0.0955,\"brier_prima\":0.0961,\"calibrazione\":0.014}"
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":2,\"prova\":\(quasi)}")
                == "\(Self.titolo): attiva (versione 2) · nelle ultime 5 giornate Brier 0,0955 invece di 0,0961, scarto 1,4 punti")
    }

    /// Un codice di `motivo` del server e la sua frase (`sd.tar_m_*` della web), con 7 giornate.
    struct CasoMotivo: Sendable, CustomTestStringConvertible {
        let codice: String
        let frase: String
        var testDescription: String { codice }
    }

    static let motivi: [CasoMotivo] = [
        CasoMotivo(codice: "non_migliora", frase: "non sbaglia meno dei numeri di partenza"),
        CasoMotivo(codice: "poche_giornate", frase: "la prova passa, si accende con 8 giornate (ora 7)"),
        CasoMotivo(codice: "fuori_soglia", frase: "fuori dalle soglie di scarto o di Brier"),
        CasoMotivo(codice: "incoerente", frase: "i numeri tarati non sono validi"),
        CasoMotivo(codice: "peggiorata", frase: "tornata ai numeri di partenza: sbagliava di più nelle ultime giornate"),
        CasoMotivo(codice: "scadenza_vicina", frase: "cambio rimandato: la prima partita è tra meno di 24 ore"),
        CasoMotivo(codice: "spenta_a_mano", frase: "spenta a mano"),
    ]

    @Test("Non attiva: una frase per ogni motivo del server", arguments: TaraturaProbabiliTests.motivi)
    func nonAttiva(caso: CasoMotivo) throws {
        let json = "{\"stato\":\"non_attiva\",\"giornate\":7,\"minimo\":4,\"versione\":2,\"dal\":null,\"prova\":null,"
            + "\"motivo\":\"\(caso.codice)\"}"
        #expect(try frase(json) == "\(Self.titolo): non attiva · \(caso.frase)")
    }

    @Test("Motivo sconosciuto o assente: solo «non attiva», niente codici")
    func motivoSconosciuto() throws {
        #expect(try frase("{\"stato\":\"non_attiva\",\"giornate\":7,\"motivo\":\"nuovo_motivo\"}") == "\(Self.titolo): non attiva")
        #expect(try frase("{\"stato\":\"non_attiva\",\"giornate\":7,\"motivo\":null}") == "\(Self.titolo): non attiva")
        #expect(try frase("{\"stato\":\"non_attiva\"}") == "\(Self.titolo): non attiva")
    }

    @Test("Spenta a mano")
    func spenta() throws {
        let json = "{\"stato\":\"spenta\",\"giornate\":3,\"minimo\":4,\"versione\":null,\"dal\":null,\"prova\":null,\"motivo\":\"spenta_a_mano\"}"
        #expect(try frase(json) == "\(Self.titolo): spenta a mano")
    }

    // MARK: - stesse parole della web (testi.js)

    @Test("Plurali con i modelli della web", arguments: [1, 3])
    func pluraliComeLaWeb(n: Int) throws {
        let web = try TestiWeb()
        let forma = n == 1 ? "one" : "other"
        let suQuante = try riga(web, riempi(web.italiano("sd.tar_in_attesa_su.\(forma)"), ["n": "\(n)", "m": "4"]))
        #expect(try frase("{\"stato\":\"in_attesa\",\"giornate\":\(n),\"minimo\":4}") == suQuante)
        let soloQuante = try riga(web, riempi(web.italiano("sd.tar_in_attesa.\(forma)"), ["n": "\(n)"]))
        #expect(try frase("{\"stato\":\"in_attesa\",\"giornate\":\(n),\"minimo\":0}") == soloQuante)
        let prova = "{\"giornate\":\(n),\"brier\":0.0912,\"brier_prima\":0.0968,\"calibrazione\":0.0213}"
        let attiva = try riempi(web.italiano("sd.tar_attiva_dal"), ["d": "15/1", "v": "1"])
        let numeri = try riempi(web.italiano("sd.tar_prova.\(forma)"), ["n": "\(n)", "b": "0,0912", "p": "0,0968", "c": "2,1"])
        let conProva = try riga(web, attiva + " · " + numeri)
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":1,\"dal\":\"2027-01-15T10:00:00\",\"prova\":\(prova)}") == conProva)
    }

    @Test("Attiva, non attiva con ogni motivo, spenta e il nome negli aggiornamenti: i testi della web")
    func statiComeLaWeb() throws {
        let web = try TestiWeb()
        let nonAttiva = try web.italiano("sd.tar_non_attiva")
        let attiva = try riga(web, riempi(web.italiano("sd.tar_attiva"), ["v": "3"]))
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":3}") == attiva)
        let spenta = try riga(web, web.italiano("sd.tar_spenta"))
        #expect(try frase("{\"stato\":\"spenta\"}") == spenta)
        let senzaMotivo = try riga(web, nonAttiva)
        #expect(try frase("{\"stato\":\"non_attiva\"}") == senzaMotivo)
        for caso in Self.motivi {
            let motivo = try riempi(web.italiano("sd.tar_m_\(caso.codice)"), ["n": "7"])
            #expect(motivo == caso.frase, "\(caso.codice)")
            let conMotivo = try riga(web, nonAttiva + " · " + motivo)
            #expect(try frase("{\"stato\":\"non_attiva\",\"giornate\":7,\"motivo\":\"\(caso.codice)\"}") == conMotivo, "\(caso.codice)")
        }
        let rimandato = try riga(web, riempi(web.italiano("sd.tar_attiva"), ["v": "1"]) + " · " + web.italiano("sd.tar_m_scadenza_vicina"))
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":1,\"motivo\":\"scadenza_vicina\"}") == rimandato)
        #expect(try web.italiano("sd.f_taratura") == NomiDati.leggibile("taratura-probabili"))
    }

    // MARK: - demo (foto e anteprima)

    @Test("La demo ha la taratura attiva, con i numeri della prova tutti scritti e coerenti con il registro")
    func demo() async throws {
        let demo = FinteServer.demoFissata(adesso: Date(timeIntervalSinceReferenceDate: 815_000_000))
        let s: StatoDati = try Decodifica.decodifica(try await demo.richiesta("GET", "/api/stato-dati", corpo: nil))
        let t = try #require(s.calibrazione?.taratura)
        #expect(t.stato == "attiva")
        let testo = try #require(ParoleRegistro.taratura(t))
        #expect(testo.hasPrefix("\(Self.titolo): attiva dal "))
        #expect(testo.contains("· nelle ultime 4 giornate Brier "))
        #expect(!testo.contains("–"))
        // prima dell'accensione si mostravano i numeri misurati dal registro delle giornate: lo stesso punteggio di Brier
        #expect(t.prova?.brierMostrati == s.registro?.brier)
    }
}
