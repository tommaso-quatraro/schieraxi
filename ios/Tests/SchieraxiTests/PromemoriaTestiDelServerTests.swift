import Foundation
import Testing
@testable import Schieraxi

/// I promemoria della scadenza sul telefono con i testi del server (#906, parte B): titolo e testo di `testi_promemoria` di Oggi
/// così come sono, niente frasi composte nell'app (niente più «modulo consigliato», anche quando il modulo l'ha scelto l'utente);
/// lista vuota, nessun promemoria; server di prima, o testo di un'ora prima letto troppo presto, il promemoria minimo del catalogo
/// con l'ora della scadenza (`oggi.prossima_chiude`). Un solo avviso per telefono: se il server manda già i suoi avvisi (notifiche
/// della web, ntfy per l'app nativa) l'app non programma i suoi. I promemoria del certificato rispettano le ore tranquille.
@Suite("Promemoria con i testi del server")
struct PromemoriaTestiDelServerTests {
    private let nome = NomeGiornata(serieA: 11, lega: 8)
    private let ore23a7 = OreTranquille(attive: true, da: 23, a: 7)
    private let testiServer = [
        TestoPromemoria(minuti: 60, titolo: "SchieraXI · hai messo la formazione?",
                        testo: "Hai messo la formazione nell'app della lega? Se sì, spunta «L'ho messa». Giornata 8 · 11ª di Serie A: si chiude tra circa un'ora, alle 14:50."),
        TestoPromemoria(minuti: 15, titolo: "SchieraXI · hai messo la formazione?",
                        testo: "Hai messo la formazione nell'app della lega? Se sì, spunta «L'ho messa». Giornata 8 · 11ª di Serie A: si chiude alle 14:50."),
    ]
    /// La frase minima del catalogo (`oggi.prossima_chiude`) per la scadenza di sabato 28/11 alle 14:50, vista il giorno stesso.
    private let minima = "Giornata 8 · 11ª di Serie A: la formazione si chiude oggi 14:50."
    private let rinnova = "l'app smette di aprirsi. Rinnovala dall'app con cui l'hai installata."

    private func data(_ testo: String) throws -> Date { try #require(Quando.data(testo)) }

    private func oggi(_ json: String) throws -> Oggi { try Decodifica.decodifica(Data(json.utf8)) }

    private func memoria() throws -> UserDefaults {
        try #require(UserDefaults(suiteName: "prova-testi-promemoria-\(UUID().uuidString)"))
    }

    private func promemoria(testi: [TestoPromemoria]?, lettaIl: Date?, dalServer: Bool = false,
                            adesso: Date) throws -> [Notifiche.Promemoria] {
        Notifiche.promemoriaDaProgrammare(giornata: nome, inizio: try data("2026-11-28 14:50"), testi: testi, lettaIl: lettaIl,
                                          ore: ore23a7, attivi: [60, 15], tace: false, dalServer: dalServer, adesso: adesso)
    }

    // MARK: il campo di Oggi

    @Test("Il campo `testi_promemoria` si legge; una voce strana si salta; un campo strano o senza voci leggibili vale «non mandato»")
    func campo() throws {
        let pieno = try oggi(#"""
        {"giornata": 11, "testi_promemoria": [{"minuti": 60, "titolo": "T60", "testo": "Testo 60"}, {"minuti": "quindici"},
         {"minuti": 15, "titolo": "T15", "testo": "Testo 15"}]}
        """#)
        #expect(pieno.promemoriaDelServer == [TestoPromemoria(minuti: 60, titolo: "T60", testo: "Testo 60"),
                                              TestoPromemoria(minuti: 15, titolo: "T15", testo: "Testo 15")])
        #expect(try oggi(#"{"giornata": 11, "testi_promemoria": []}"#).promemoriaDelServer == [])
        #expect(try oggi(#"{"giornata": 11}"#).promemoriaDelServer == nil, "server di prima")
        #expect(try oggi(#"{"giornata": 11, "testi_promemoria": "no"}"#).promemoriaDelServer == nil)
        #expect(try oggi(#"{"giornata": 11, "testi_promemoria": [{"minuti": 60}]}"#).promemoriaDelServer == nil,
                "voci illeggibili: mai una lista vuota per errore, che vorrebbe dire «non serve»")
    }

    // MARK: i testi

    @Test("I due promemoria hanno titolo e testo del server, così come sono, senza frasi dell'app")
    func testiDelServer() throws {
        let letta = try data("2026-11-28 13:20")
        let elenco = try promemoria(testi: testiServer, lettaIl: letta, adesso: letta)
        let attesi = [try data("2026-11-28 13:50"), try data("2026-11-28 14:35")]
        #expect(elenco.map(\.id) == ["fanta-60", "fanta-15"])
        #expect(elenco.map(\.quando) == attesi)
        #expect(elenco.map(\.titolo) == testiServer.map(\.titolo))
        #expect(elenco.map(\.testo) == testiServer.map(\.testo))
        #expect(!elenco.contains { $0.testo.contains("modulo consigliato") })
    }

    @Test("Il testo di un'ora prima letto più di due ore prima che suoni (può avere numeri vecchi): la frase minima con l'ora")
    func unOraLettaPresto() throws {
        let letta = try data("2026-11-28 10:00")   // il promemoria di un'ora prima suona alle 13:50, quasi 4 ore dopo
        let elenco = try promemoria(testi: testiServer, lettaIl: letta, adesso: letta)
        #expect(elenco.map(\.titolo) == ["", testiServer[1].titolo])
        #expect(elenco.map(\.testo) == [minima, testiServer[1].testo], "quello di un quarto d'ora prima non ha numeri: resta del server")
        let senzaOra = try promemoria(testi: testiServer, lettaIl: nil, adesso: letta)
        #expect(senzaOra.map(\.testo) == [minima, testiServer[1].testo], "lettura di cui non si sa l'ora: come una vecchia")
    }

    @Test("Server di prima, senza i testi: il promemoria minimo del catalogo con l'ora della scadenza, senza titolo")
    func serverDiPrima() throws {
        let letta = try data("2026-11-28 13:20")
        let elenco = try promemoria(testi: nil, lettaIl: letta, adesso: letta)
        #expect(elenco.map(\.id) == ["fanta-60", "fanta-15"])
        #expect(elenco.map(\.titolo) == ["", ""])
        #expect(elenco.map(\.testo) == [minima, minima])
    }

    @Test("Il server manda già i suoi avvisi a questo telefono: l'app non programma i suoi (un solo avviso per telefono)")
    func unSoloAvviso() throws {
        let letta = try data("2026-11-28 13:20")
        #expect(try promemoria(testi: testiServer, lettaIl: letta, dalServer: true, adesso: letta).isEmpty)
        #expect(try promemoria(testi: nil, lettaIl: letta, dalServer: true, adesso: letta).isEmpty)
        #expect(try promemoria(testi: testiServer, lettaIl: letta, dalServer: false, adesso: letta).count == 2)
    }

    @Test("Lista dei testi vuota: nessun promemoria, anche senza `serve_promemoria`; lettura non riuscita o spunta appena tolta: suona")
    func listaVuota() throws {
        let m = try memoria()
        let vuota = try oggi(#"{"giornata": 11, "testi_promemoria": []}"#)
        let tocco = try data("2026-11-28 12:00")
        #expect(Aggiornamento.promemoriaTace(vuota, lettura: .fresca(chiestaIl: tocco), memoria: m) == true)
        #expect(Aggiornamento.promemoriaTace(vuota, lettura: .salvata, memoria: m) == true)
        #expect(Aggiornamento.promemoriaTace(vuota, lettura: .nonRiuscita, memoria: m) == false, "mai tacere per un dato incerto")
        ArchivioMessa.ricorda(giornata: 11, messa: false, m, il: tocco)
        #expect(Aggiornamento.promemoriaTace(vuota, lettura: .salvata, memoria: m) == false, "la spunta appena tolta vale subito")
        let conTesti = try oggi(#"{"giornata": 11, "testi_promemoria": [{"minuti": 15, "titolo": "T", "testo": "Testo"}]}"#)
        #expect(Aggiornamento.promemoriaTace(conTesti, lettura: .fresca(chiestaIl: tocco.addingTimeInterval(60)), memoria: m) == false)
    }

    // MARK: un solo avviso per telefono

    @Test("Il server manda già gli avvisi a questo telefono con le notifiche della web accese, o con ntfy per l'app nativa",
          arguments: zip([
            #"{"impostazioni": {"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "app_nativa": false}, "canale": true, "dispositivi": 1}"#,
            #"{"impostazioni": {"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "app_nativa": true}, "canale": true, "dispositivi": 0}"#,
            #"{"impostazioni": {"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "app_nativa": true}, "canale": false, "dispositivi": 0}"#,
            #"{"impostazioni": {"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true, "app_nativa": false}, "canale": true, "dispositivi": 0}"#,
            #"{"impostazioni": {"cambi": true, "promemoria_60": true, "promemoria_15": true, "riepilogo": true}}"#,
          ], [true, true, false, false, false]))
    func dalServer(json: String, atteso: Bool) throws {
        let stato: StatoAvvisi = try Decodifica.decodifica(Data(json.utf8), snake: false)
        #expect(stato.mandaGiaIlServer == atteso)
    }

    // MARK: certificato e ore tranquille

    @Test("Promemoria del certificato fuori dalle ore tranquille: 24 e 6 ore prima, come sempre")
    func certificatoFuoriDalSilenzio() throws {
        let scadenza = try data("2026-11-28 18:00")
        let elenco = Notifiche.promemoriaCertificato(scadenza: scadenza, ore: ore23a7, adesso: try data("2026-11-25 12:00"))
        let attesi = [try data("2026-11-27 18:00"), try data("2026-11-28 12:00")]
        #expect(elenco.map(\.id) == ["fanta-cert-24", "fanta-cert-6"])
        #expect(elenco.map(\.quando) == attesi)
        #expect(elenco.map(\.testo) == ["Tra circa 24 ore \(rinnova)", "Tra circa 6 ore \(rinnova)"])
    }

    @Test("Nelle ore tranquille il promemoria del certificato suona un minuto prima che comincino, con le ore vere nel testo")
    func certificatoNelSilenzio() throws {
        // scadenza alle 5: 24 ore prima sono le 5 del giorno prima, 6 ore prima le 23, tutte e due nelle ore tranquille 23-7
        let scadenza = try data("2026-11-28 05:00")
        let elenco = Notifiche.promemoriaCertificato(scadenza: scadenza, ore: ore23a7, adesso: try data("2026-11-25 12:00"))
        let attesi = [try data("2026-11-26 22:59"), try data("2026-11-27 22:59")]
        #expect(elenco.map(\.id) == ["fanta-cert-24", "fanta-cert-6"])
        #expect(elenco.map(\.quando) == attesi)
        #expect(elenco.map(\.testo) == ["Tra circa 30 ore \(rinnova)", "Tra circa 6 ore \(rinnova)"])
        #expect(!elenco.contains { ore23a7.inSilenzio($0.quando) })
    }

    @Test("Ore tranquille già cominciate: il promemoria del certificato suona quando finiscono, se manca ancora almeno un'ora")
    func certificatoSilenzioGiaCominciato() throws {
        let adesso = try data("2026-11-27 23:30")
        // scadenza alle 10: 6 ore prima sono le 4, nelle ore tranquille già cominciate → alle 7, «circa 3 ore»
        let elenco = Notifiche.promemoriaCertificato(scadenza: try data("2026-11-28 10:00"), ore: ore23a7, adesso: adesso)
        let alleSette = try data("2026-11-28 07:00")
        #expect(elenco.map(\.id) == ["fanta-cert-6"])
        #expect(elenco.map(\.quando) == [alleSette])
        #expect(elenco.map(\.testo) == ["Tra circa 3 ore \(rinnova)"])
        // scadenza alle 7:30: alla fine delle ore tranquille manca meno di un'ora, e prima si suonerebbe di notte → nessuno
        #expect(Notifiche.promemoriaCertificato(scadenza: try data("2026-11-28 07:30"), ore: ore23a7, adesso: adesso).isEmpty)
    }
}
