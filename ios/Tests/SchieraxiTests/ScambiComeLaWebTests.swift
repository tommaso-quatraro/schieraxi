import Foundation
import Testing
@testable import Schieraxi

/// La schermata Scambi dice le stesse parole della web (issue #438, sotto la #167): titoli, pulsanti, frasi di spiegazione e
/// giudizio vengono dal catalogo comune (chiavi `scambi.*` e `scambio.*`, #496). Prima l'iPhone scriveva «Analizza»,
/// «Rose dopo lo scambio», «Con chi», «Ho ricevuto un'offerta»… Qui si provano le frasi composte (numeri, nomi, plurali) e che
/// ogni nome usato dalle viste sia il testo giusto del catalogo. La bozza del messaggio (`ScambiLogica`) si confronta ancora con
/// `testi.js`. Dati inventati.
@Suite("Scambi: le stesse parole della web")
struct ScambiComeLaWebTests {
    /// Il testo del catalogo e il nome che usano le viste: ogni nome è collegato al testo giusto.
    static let voci: [(String, String)] = [
        // i tre modi e «Trova per me»
        (Catalogo.Scambio.cosaVuoiFare, TestiScambi.cosaVuoiFare),
        (Catalogo.Scambio.trovaPer, TestiScambi.trovaPerMe),
        (Catalogo.Scambio.valutaOfferta, TestiScambi.valutaOfferta),
        (Catalogo.Scambio.scambiCuiGuadagnate, TestiScambi.scambiCuiGuadagnate),
        (Catalogo.Scambio.conQualeSquadra, TestiScambi.conQualeSquadra),
        (Catalogo.Scambio.tutteSquadre, TestiScambi.tutteLeSquadre),
        (Catalogo.Scambio.quantiGiocatoriPer, TestiScambi.quantiGiocatoriPerParte),
        (Catalogo.Scambio.unoControUno, TestiScambi.unoControUno),
        (Catalogo.Scambio.finoA2, TestiScambi.finoA2),
        (Catalogo.Scambio.finoA3, TestiScambi.finoA3),
        (Catalogo.Scambio.finoA4, TestiScambi.finoA4),
        (Catalogo.Scambio.perGliScambi, TestiScambi.perGliScambi),
        (Catalogo.Scambio.cercaScambi, TestiScambi.cercaScambi),
        (Catalogo.Scambio.cercoGliScambi, TestiScambi.cercoGliScambi),
        (Catalogo.Scambio.nessunoScambioChe, TestiScambi.nessunoScambio),
        (Catalogo.Scambio.servonoAltre, TestiScambi.servonoAltreRose),
        // proposte
        (Catalogo.Scambio.copiaBozzaDel, TestiScambi.copiaBozza),
        (Catalogo.Mercato.bozzaCopiata, TestiScambi.bozzaCopiata),
        (Catalogo.Scambio.chiAccettaPiu, TestiScambi.chiAccettaPiu),
        (Catalogo.Scambio.squadreCheGuadagnano, TestiScambi.squadreCheGuadagnano),
        (Catalogo.Scambio.gliUltimiScambi, TestiScambi.ultimiScambi),
        // «Valuta un'offerta»
        (Catalogo.Scambio.incollaMessaggioChe, TestiScambi.incollaMessaggio),
        (Catalogo.Scambio.messaggioDellOfferta, TestiScambi.messaggioOfferta),
        (Catalogo.Scambio.valutaOfferta2, TestiScambi.valutaOffertaPulsante),
        (Catalogo.Scambio.incollaPrimaMessaggio, TestiScambi.incollaPrima),
        (Catalogo.Scambio.leggoMessaggio, TestiScambi.leggoMessaggio),
        (Catalogo.Scambio.rigaCon, TestiScambi.rigaCon),
        (Catalogo.Scambio.nonTrovatoGiocatori, TestiScambi.nonTrovatoGiocatori),
        (Catalogo.Scambio.scegliManoCostruisci, TestiScambi.scegliAMano),
        (Catalogo.Scambio.vediGiudizioCompleto, TestiScambi.vediGiudizioCompleto),
        // «Costruisci uno scambio»
        (Catalogo.Scambi.analizzaTitolo, TestiScambi.costruisciTitolo),
        (Catalogo.Scambi.analizzaSpiega, TestiScambi.costruisciSpiega),
        (Catalogo.Scambi.con, TestiScambi.scambioCon),
        (Catalogo.Scambi.dai, TestiScambi.dai),
        (Catalogo.Scambi.ricevi, TestiScambi.ricevi),
        (Catalogo.Scambi.conguaglio, TestiScambi.conguaglio),
        (Catalogo.Scambi.conguaglioAiuto, TestiScambi.conguaglioAiuto),
        (Catalogo.Scambi.ricevoCrediti, TestiScambi.ricevoCrediti),
        (Catalogo.Scambi.pagoCrediti, TestiScambi.pagoCrediti),
        (Catalogo.Scambi.creditiQuanti, TestiScambi.creditiQuanti),
        (Catalogo.Scambi.conguaglioNumero, TestiScambi.conguaglioNumero),
        (Catalogo.Scambi.analizza, TestiScambi.valutaScambio),
        (Catalogo.Scambi.calcolo, TestiScambi.calcolo),
        // il giudizio
        (Catalogo.Scambi.chiNonValido, TestiScambi.cosiNonSiPuoFare),
        (Catalogo.Scambi.roseDopo, TestiScambi.roseDopo),
        (Catalogo.Scambi.panchina, TestiScambi.panchina),
        (Catalogo.Scambi.inStagione, TestiScambi.inStagione),
        (Catalogo.Scambi.tu, TestiScambi.tu),
        (Catalogo.Scambi.creditiTitolo, TestiScambi.crediti),
        (Catalogo.Scambio.impattoSullaTua, TestiScambi.impatto),
        (Catalogo.Scambio.contaAncheResto, TestiScambi.contaAncheResto),
    ]

    /// Il testo italiano di `testi.js` con ogni segnaposto `{nome}` sostituito: solo per la bozza del messaggio, che scrive
    /// `ScambiLogica` con chiavi che l'iPhone non prende ancora dal catalogo.
    private func web(_ chiave: String, _ valori: [String: String] = [:]) throws -> String {
        var testo = try TestiWeb().italiano(chiave)
        for (nome, valore) in valori { testo = testo.replacingOccurrences(of: "{\(nome)}", with: valore) }
        return testo
    }

    @Test("Ogni nome usato dalle viste è il testo giusto del catalogo", arguments: ScambiComeLaWebTests.voci)
    func ugualeAlCatalogo(catalogo: String, app: String) {
        #expect(app == catalogo)
    }

    @Test("Il titolo e la descrizione dello stato vuoto, messi insieme, sono la frase della web")
    func servonoAltreRoseInDue() {
        #expect(!TestiScambi.servonoAltreRoseTitolo.isEmpty)
        #expect(!TestiScambi.servonoAltreRoseCorpo.isEmpty)
        #expect(TestiScambi.servonoAltreRoseTitolo.hasSuffix("."))
        #expect(TestiScambi.servonoAltreRoseTitolo + " " + TestiScambi.servonoAltreRoseCorpo == Catalogo.Scambio.servonoAltre)
        let sola = TestiScambi.inDue("Una frase sola")
        #expect(sola.titolo == "Una frase sola")
        #expect(sola.corpo.isEmpty)
    }

    // MARK: frasi con un numero o un nome

    @Test("«2 su 4» per parte, «Al massimo 4 giocatori per parte», «2 contro 1»")
    func numeriPerParte() throws {
        #expect(TestiScambi.scelti(2, massimo: 4) == Catalogo.Scambi.scelti(max: "4", n: "2"))
        #expect(TestiScambi.scelti(2, massimo: 4) == "2 su 4")
        #expect(TestiScambi.alMassimo(4) == Catalogo.Scambi.massimo(max: "4"))
        #expect(TestiScambi.alMassimo(4) == "Al massimo 4 giocatori per parte")
        #expect(TestiScambi.formato(2, 1) == Catalogo.Scambi.formato(m: "1", n: "2"))
        #expect(TestiScambi.formato(2, 1) == "2 contro 1")
    }

    @Test("«con Squadra» e, se non è 1 contro 1, anche il formato come la web")
    func conSquadra() throws {
        let con = Catalogo.Scambio.con
        let formato = Catalogo.Scambi.formato(m: "1", n: "2")
        #expect(TestiScambi.conSquadra("Gli Amici", dai: 1, ricevi: 1) == "\(con) Gli Amici")
        #expect(TestiScambi.conSquadra("Gli Amici", dai: 2, ricevi: 1) == "\(con) Gli Amici · \(formato)")
        #expect(TestiScambi.conSquadra("Gli Amici", dai: 2, ricevi: 1) == "con Gli Amici · 2 contro 1")
        let unoTre = Catalogo.Scambi.formato(m: "3", n: "1")
        #expect(TestiScambi.conSquadra("Gli Amici", dai: 1, ricevi: 3) == "\(con) Gli Amici · \(unoTre)")
    }

    @Test("Formazione migliore: «prossima giornata» con una sola, «prossime N giornate» con più")
    func formazioneMigliore() throws {
        #expect(TestiScambi.formazioneMigliore(giornate: 1) == Catalogo.Scambi.formazioneMiglioreUna)
        #expect(TestiScambi.formazioneMigliore(giornate: 3) == Catalogo.Scambi.formazioneMigliore(n: "3"))
        #expect(TestiScambi.formazioneMigliore(giornate: 2) == Catalogo.Scambi.formazioneMigliore(n: "2"))
        #expect(TestiScambi.formazioneMigliore(giornate: 3) == "Formazione migliore (prossime 3 giornate)")
    }

    @Test("Senza il numero delle giornate (server vecchio) resta la parte comune, mai «prossime 0 giornate»")
    func formazioneMiglioreSenzaNumero() throws {
        let una = Catalogo.Scambi.formazioneMiglioreUna
        #expect(una.hasPrefix(TestiScambi.formazioneMigliore(giornate: 0)))
        #expect(TestiScambi.formazioneMigliore(giornate: 0) == "Formazione migliore")
        #expect(!TestiScambi.formazioneMigliore(giornate: 0).contains("0"))
    }

    @Test("In totale: «prossima giornata» con una sola, «prossime N giornate» con più")
    func inTotale() throws {
        #expect(TestiScambi.inTotale(giornate: 1) == Catalogo.Scambio.inTotale(1))
        #expect(TestiScambi.inTotale(giornate: 1) == "In totale (prossima giornata)")
        #expect(TestiScambi.inTotale(giornate: 4) == Catalogo.Scambio.inTotale(4))
        #expect(TestiScambi.inTotale(giornate: 4) == "In totale (prossime 4 giornate)")
    }

    @Test("Chi accetta più volentieri: «1 scambio», «3 scambi», «migliora i portieri di +2,1%», «Archivio (5)»")
    func propenseEArchivio() throws {
        #expect(TestiScambi.nScambi(1) == "1 scambio")
        #expect(TestiScambi.nScambi(3) == "3 scambi")
        #expect(TestiScambi.migliora(reparto: "portieri", p: "+2,1") == Catalogo.Scambio.migliora(p: "+2,1", reparto: "portieri"))
        #expect(TestiScambi.migliora(reparto: "portieri", p: "+2,1") == "migliora i portieri di +2,1%")
        #expect(TestiScambi.archivio(5) == Catalogo.Scambio.archivio(n: "5"))
        #expect(TestiScambi.archivio(5) == "Archivio (5)")
    }

    @Test("Più giocatori con lo stesso cognome: i nomi separati da «; » come la web")
    func ambigui() throws {
        let attesa = Catalogo.Scambio.ambigui(nomi: "Rossi A.; Rossi B.")
        #expect(TestiScambi.ambigui(["Rossi A.", "Rossi B."]) == attesa)
    }

    // MARK: i modi della schermata

    @Test("I tre modi hanno i nomi dei pulsanti della web, nello stesso ordine")
    func modi() {
        let attesi = [Catalogo.Scambio.trovaPer, Catalogo.Scambio.costruisci, Catalogo.Scambio.valutaOfferta]
        #expect(ModoScambi.allCases.map(\.rawValue) == attesi)
    }

    // MARK: la bozza del messaggio

    private func scambio(mio: Double, loro: Double) throws -> PropostaScambio {
        let corpo = """
        {"altra": "Loro", "guadagno_mio": \(mio), "guadagno_loro": \(loro),
         "do": [{"id": 1, "nome": "Aldo", "ruolo": "C", "squadra": "inter", "quotazione": 10},
                {"id": 2, "nome": "Bruno", "ruolo": "D", "squadra": "milan", "quotazione": 8}],
         "ricevo": [{"id": 3, "nome": "Carlo", "ruolo": "A", "squadra": "roma", "quotazione": 12}]}
        """
        return try Decodifica.decodifica(Data(corpo.utf8))
    }

    @Test("La bozza del messaggio ha le parole della web: «più o meno uguale» se i conti sono vicini")
    func bozzaUguale() throws {
        let e = try web("scambio.bozza_e")
        let quanto = try web("scambio.bozza_uguale")
        let attesa = try web("scambio.bozza", ["do": "Aldo\(e)Bruno", "ricevo": "Carlo", "quanto": quanto])
        let proposta = try scambio(mio: 1.0, loro: 0.5)
        #expect(ScambiLogica.bozza(proposta) == attesa)
    }

    @Test("La bozza del messaggio ha le parole della web: i punti attesi di tutti e due se i conti sono lontani")
    func bozzaConIPunti() throws {
        let e = try web("scambio.bozza_e")
        let quanto = try web("scambio.bozza_punti", ["loro": Formato.conSegno(0.1), "mio": Formato.conSegno(2.4)])
        let attesa = try web("scambio.bozza", ["do": "Aldo\(e)Bruno", "ricevo": "Carlo", "quanto": quanto])
        let proposta = try scambio(mio: 2.4, loro: 0.1)
        #expect(ScambiLogica.bozza(proposta) == attesa)
    }

    // MARK: il conguaglio: «Ricevo» e «Pago»

    @MainActor
    private func analisi() -> AnalizzaScambioViewModel {
        let v = AnalizzaScambioViewModel(server: ServerDiProva { _, _, _ in Data("{}".utf8) })
        v.altra = "Loro"
        v.doIds = [1]
        v.ricevoIds = [2]
        return v
    }

    @Test("«Ricevo» manda i crediti positivi, «Pago» negativi: come i due pulsanti della web")
    @MainActor
    func versoDelConguaglio() {
        let v = analisi()
        v.conguaglio = "12"
        #expect(v.verso == .ricevo, "all'inizio «Ricevo», come sulla web")
        #expect(v.creditiConguaglio == 12)
        #expect(v.indirizzoAnalisi.hasSuffix("&completo=true&conguaglio=12"))
        v.verso = .pago
        #expect(v.creditiConguaglio == -12)
        #expect(v.indirizzoAnalisi.hasSuffix("&completo=true&conguaglio=-12"))
        #expect(v.conguaglioValido)
    }

    @Test("Senza crediti, o con zero, nessun conguaglio: né con «Ricevo» né con «Pago»")
    @MainActor
    func nessunConguaglio() {
        let v = analisi()
        for verso in VersoConguaglio.allCases {
            v.verso = verso
            for vuoto in ["", "0", "  "] {
                v.conguaglio = vuoto
                #expect(v.creditiConguaglio == 0, "\(vuoto) con \(verso)")
                #expect(!v.indirizzoAnalisi.contains("conguaglio"))
            }
        }
    }

    @Test("Un numero troppo grande non si manda, qualunque sia il verso")
    @MainActor
    func troppiCrediti() {
        let v = analisi()
        for verso in VersoConguaglio.allCases {
            v.verso = verso
            for cattivo in ["100001", "1000000", "99999999999999999999", "abc", "1,5"] {
                v.conguaglio = cattivo
                #expect(!v.conguaglioValido, "\(cattivo) con \(verso)")
                #expect(!v.puoAnalizzare)
            }
        }
        v.conguaglio = "100000"
        #expect(v.puoAnalizzare)
    }

    @Test("I due pulsanti del conguaglio si chiamano «Ricevo» e «Pago»")
    func nomiDelVerso() {
        let nomi = [Catalogo.Scambi.ricevoCrediti, Catalogo.Scambi.pagoCrediti]
        #expect(VersoConguaglio.allCases.map(\.nome) == nomi)
    }

    // MARK: i messaggi del ViewModel

    @Test("«Più di 4 giocatori per parte»: la frase della web")
    @MainActor
    func troppiGiocatori() throws {
        let v = analisi()
        v.doIds = [1, 2, 3, 4, 5]
        #expect(v.troppi == Catalogo.Scambi.massimo(max: "4"))
    }

    @Test("Offerta senza testo: «Incolla prima il messaggio» come la web, e non si chiede niente al server")
    @MainActor
    func offertaSenzaTesto() async throws {
        let vm = ScambiViewModel(server: ServerDiProva.chePrecipita())
        await vm.valutaOfferta()
        #expect(vm.erroreOfferta == Catalogo.Scambio.incollaPrimaMessaggio)
    }
}
