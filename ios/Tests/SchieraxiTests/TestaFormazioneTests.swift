import Foundation
import Testing
@testable import Schieraxi

/// La testa della Formazione per fase, come `testaGiornata` e `testoConto` della web (#616, #673): prima della scadenza la giornata e
/// «Si chiude … fra …»; in corso i punti fatti finora; finita com'è andata e sotto la giornata della formazione; arrivato a partite
/// cominciate la frase della prossima. Numeri e frasi del server, parole del catalogo comune. Dati inventati, ora fissa.
@Suite("Testa della Formazione per fase, come la web")
struct TestaFormazioneTests {
    /// sabato 31 ottobre 2026, 11:40 (ora italiana): 3 h 10 min prima della scadenza delle 14:50.
    static func adesso() throws -> Date { try #require(Quando.data("2026-10-31 11:40")) }

    static func oggi(_ json: String) throws -> Oggi { try Decodifica.decodifica(Data(json.utf8)) }

    /// La formazione della giornata 8 della lega (11ª di Serie A), con i campi in più di `altro`.
    static func formazione(_ altro: String = "", giornata: Int = 11, lega: Int = 8) throws -> Formazione {
        try Decodifica.decodifica(Data(#"""
        {"giornata": \#(giornata), "giornata_lega": \#(lega), "modulo": "4-3-3", "punteggio_atteso": 70.0, "titolari": [], "panchina": [] \#(altro)}
        """#.utf8))
    }

    // MARK: prima della scadenza

    @Test("Prima della scadenza: «Giornata 8 · 11ª di Serie A» e «Si chiude oggi 14:50» con «fra 3 h 10 min»")
    func prima() throws {
        let o = try Self.oggi(#"{"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 14:50", "fase": "prima"}"#)
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t.giornata == "Giornata 8 · 11ª di Serie A")
        #expect(t.chiude == "Si chiude oggi 14:50")
        #expect(t.chiude == Catalogo.Formazione.siChiude(quando: "oggi 14:50"))
        #expect(t.manca == "fra 3\u{00A0}h 10\u{00A0}min", "ogni numero attaccato alla sua unità, come la web")
        #expect(t.punti == nil && t.nota == nil && t.comeAndata == nil && t.prossima == nil && !t.inCorso)
    }

    @Test("Senza `fase` (server vecchio) come prima della scadenza; senza `scadenza` vale l'inizio della prima partita")
    func serverVecchio() throws {
        let o = try Self.oggi(#"{"giornata": 11, "giornata_lega": 8, "inizio": "2026-10-31 15:00"}"#)
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t.chiude == "Si chiude oggi 15:00")
        #expect(t.manca == "fra 3\u{00A0}h 20\u{00A0}min")
    }

    @Test("Scadenza passata: «Formazione chiusa» senza conto; senza date «Calendario non disponibile»")
    func scadutaOSenzaDate() throws {
        let scaduta = try Self.oggi(#"{"giornata": 11, "scadenza": "2026-10-31 09:00"}"#)
        let t = TestaFormazione.per(oggi: scaduta, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t.chiude == Catalogo.Formazione.chiusaBreve)
        #expect(t.manca == nil)
        let senza = try Self.oggi(#"{"giornata": 11}"#)
        let s = TestaFormazione.per(oggi: senza, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(s.chiude == Catalogo.Oggi.calendarioNo)
        #expect(s.manca == nil)
    }

    @Test("Formazione già chiusa (`iniziata`) senza i dati della fase: solo la giornata, come la web")
    func iniziataSenzaFase() throws {
        let o = try Self.oggi(#"{"giornata": 11, "scadenza": "2026-10-31 14:50"}"#)
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(#", "iniziata": true"#), adesso: try Self.adesso())
        #expect(t.giornata == "Giornata 8 · 11ª di Serie A")
        #expect(t.chiude == nil && t.manca == nil)
    }

    @Test("La formazione di un'altra squadra (senza la giornata di Oggi): solo la giornata")
    func altraSquadra() throws {
        let t = TestaFormazione.per(oggi: nil, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t == TestaFormazione(giornata: "Giornata 8 · 11ª di Serie A"))
    }

    // MARK: in corso

    @Test("In corso: «· in corso», «40,0 punti finora · circa 75 a fine giornata» e quanti devono ancora giocare")
    func inCorso() throws {
        let o = try Self.oggi(#"""
        {"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 09:00", "fase": "in_corso",
         "in_corso": {"punti_fatti": 40, "punti_previsti": 74.6, "ancora_da_giocare": 2, "giocatori": [], "sostituzioni": []}}
        """#)
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(#", "iniziata": true"#), adesso: try Self.adesso())
        #expect(t.giornata == "Giornata 8 · 11ª di Serie A")
        #expect(t.inCorso)
        #expect(t.punti == "40,0")
        #expect(t.testoPunti == "punti finora · circa 75 a fine giornata")
        #expect(t.sotto == Catalogo.Oggi.ancoraDaGiocare(2))
        #expect(t.chiude == nil, "a giornata in corso niente scadenza")
    }

    @Test("In corso, hanno giocato tutti: «Hanno giocato tutti: mancano solo i voti ufficiali.»; senza previsione solo «punti finora»")
    func inCorsoTuttiGiocato() throws {
        let o = try Self.oggi(#"""
        {"giornata": 11, "fase": "in_corso", "in_corso": {"punti_fatti": 61.5, "ancora_da_giocare": 0}}
        """#)
        let t = TestaFormazione.per(oggi: o, formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(t.sotto == Catalogo.Oggi.tuttiGiocato)
        #expect(t.punti == "61,5")
        #expect(t.testoPunti == Catalogo.Formazione.puntiFinora)
    }

    @Test("Arrivato a partite cominciate: la frase della prossima, con l'apostrofo davanti all'11ª, e quando si chiude la prossima")
    func arrivatoAGiornataIniziata() throws {
        let o = try Self.oggi(#"""
        {"giornata": 11, "giornata_lega": 8, "fase": "in_corso", "senza_formazione": true,
         "prossima": {"giornata": 12, "giornata_lega": 9, "scadenza": "2026-11-01 14:50"}}
        """#)
        let f = try Self.formazione(#", "giornata_saltata": 11, "giornata_saltata_lega": 8"#, giornata: 12, lega: 9)
        let t = TestaFormazione.per(oggi: o, formazione: f, adesso: try Self.adesso())
        #expect(t.nota == "Giornata 8 · 11ª di Serie A: è già iniziata. Questa è la formazione per la Giornata 9 · 12ª di Serie A.")
        #expect(t.giornata == nil && t.punti == nil)
        #expect(t.chiude == "Si chiude domani 14:50")
        // senza i due numeri della giornata saltata (server vecchio): la frase di sempre
        let senza = TestaFormazione.per(oggi: o, formazione: try Self.formazione(giornata: 12, lega: 9), adesso: try Self.adesso())
        #expect(senza.nota == Catalogo.Oggi.giaIniziataTesto)
        // l'apostrofo davanti agli ordinali che si leggono con una vocale, come la web
        let undicesima = try Self.formazione(#", "giornata_saltata": 10"#, giornata: 11, lega: 0)
        let elisa = TestaFormazione.per(oggi: o, formazione: undicesima, adesso: try Self.adesso())
        #expect(elisa.nota == "10ª giornata di Serie A: è già iniziata. Questa è la formazione per l'11ª giornata di Serie A.")
    }

    // MARK: finita

    static let jsonFinita = #"""
    {"giornata": 12, "giornata_lega": 9, "fase": "finita",
     "riepilogo": {"giornata": 11, "giornata_lega": 8, "formazione_di": "tua", "nel_diario": true, "punti_fatti": 83, "punti_attesi": 71.7,
                   "consigliata": {"punti_fatti": 72, "punti_attesi": 66.1}, "recuperi": []},
     "prossima": {"giornata": 12, "giornata_lega": 9, "scadenza": "2026-11-06 14:50", "con_probabili": false}}
    """#

    @Test("Finita: «…: finita», «83,0 punti (attesi 71,7)», «Com'è andata», il confronto con la consigliata e sotto la prossima")
    func finita() throws {
        let t = TestaFormazione.per(oggi: try Self.oggi(Self.jsonFinita), formazione: try Self.formazione(giornata: 12, lega: 9),
                                    adesso: try Self.adesso())
        #expect(t.giornata == "Giornata 8 · 11ª di Serie A: finita")
        #expect(t.punti == "83,0")
        #expect(t.testoPunti == "punti (attesi 71,7)")
        #expect(t.sotto == Catalogo.Oggi.conConsigliata(attesi: "66,1", fatti: "72,0"))
        #expect(t.comeAndata == 11)
        #expect(t.prossima == "Giornata 9 · 12ª di Serie A")
        #expect(t.recuperi == nil)
        #expect(t.chiude == "Si chiude ven 6 14:50", "la scadenza della prossima")
        #expect(t.manca == "fra 6\u{00A0}giorni 3\u{00A0}h")
    }

    @Test("Finita con la consigliata (o con gli stessi punti): niente confronto; senza punti attesi solo «punti»")
    func finitaSenzaConfronto() throws {
        let consigliata = Self.jsonFinita.replacingOccurrences(of: #""formazione_di": "tua""#, with: #""formazione_di": "consigliata""#)
        let t = TestaFormazione.per(oggi: try Self.oggi(consigliata), formazione: try Self.formazione(giornata: 12, lega: 9),
                                    adesso: try Self.adesso())
        #expect(t.sotto == nil)
        let uguali = Self.jsonFinita.replacingOccurrences(of: #""punti_fatti": 72"#, with: #""punti_fatti": 83"#)
        #expect(TestaFormazione.per(oggi: try Self.oggi(uguali), formazione: try Self.formazione(), adesso: try Self.adesso()).sotto == nil)
        let senzaAttesi = Self.jsonFinita.replacingOccurrences(of: #""punti_attesi": 71.7,"#, with: "")
        let s = TestaFormazione.per(oggi: try Self.oggi(senzaAttesi), formazione: try Self.formazione(), adesso: try Self.adesso())
        #expect(s.testoPunti == Catalogo.Formazione.punti)
    }

    @Test("Il nome di una giornata con un numero solo: quello che c'è, come `nomeGiornata` della web")
    func nomeGiornata() {
        #expect(TestaFormazione.nome(serieA: 11, lega: 8) == "Giornata 8 · 11ª di Serie A")
        #expect(TestaFormazione.nome(serieA: 11, lega: nil) == "11ª giornata di Serie A")
        #expect(TestaFormazione.nome(serieA: nil, lega: 8) == "Giornata 8")
        #expect(TestaFormazione.nome(serieA: nil, lega: nil).isEmpty)
    }
}
