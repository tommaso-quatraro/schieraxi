import Foundation
import Testing
@testable import Schieraxi

/// Impostazioni › La mia lega come la web (ricerca del 27/11 sulle sue pagine): «Rimuovi» per stemma e maglia, «La mia squadra»
/// spenta senza rete, le righe dei gruppi e la correzione in Stato dei dati, le parole della prova del modello, − e + che vanno al
/// passo vicino (#911), il nome della lega senza spazi ai lati e le frasi del salvataggio dal catalogo. Dati inventati.
@MainActor
@Suite("La mia lega come la web")
struct LaMiaLegaComeLaWebTests {

    // MARK: stemma e maglia, «Rimuovi»

    /// Il server della rosa: dopo «Rimuovi» gli elenchi dicono che quell'immagine non c'è più.
    private static func serverImmagini() -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if metodo == "GET", percorso == "/api/squadre" {
                return Data(#"[{"nome": "Nuvola Ovest", "mia": true, "immagini": {"stemma": false, "maglia": false}}]"#.utf8)
            }
            if metodo == "GET", percorso == "/api/foto-disponibili" { return Data(#"{"ids": []}"#.utf8) }
            if metodo == "GET", percorso.hasPrefix("/api/rosa") { return try Fixture.dati("rosa") }
            return Data(#"{"squadra": "Nuvola Ovest", "immagini": {"stemma": false, "maglia": false}}"#.utf8)
        }
    }

    @Test("«Rimuovi»: DELETE /api/squadre/immagine con squadra e tipo, poi la frase della web e gli elenchi riletti",
          arguments: [("stemma", Catalogo.Lega.stemmaRimosso), ("maglia", Catalogo.Lega.magliaRimossa)])
    func rimuovi(tipo: String, frase: String) async {
        let server = Self.serverImmagini()
        let immagini = Immagini(server: server)
        let vm = RosaViewModel(nome: "Nuvola Ovest", server: server, immagini: immagini, centro: NotificationCenter())
        await vm.rimuoviImmagine(tipo: tipo)
        #expect(server.richieste.contains("DELETE " + Immagini.percorsoSquadra("Nuvola Ovest", tipo: tipo)))
        #expect(vm.messaggio == frase)
        #expect(server.quante("GET /api/squadre") == 1, "gli elenchi si rileggono: il pulsante «Rimuovi» sparisce")
        #expect(!immagini.haImmagine("Nuvola Ovest", tipo: tipo))
        #expect(!vm.inCorso)
    }

    @Test("«Rimuovi» che non riesce: la frase del server, come l'avviso della web")
    func rimuoviNonRiesce() async {
        let server = ServerDiProva { metodo, _, _ in
            if metodo == "DELETE" { throw ErroreApi.server("Squadra non trovata.") }
            return Data("{}".utf8)
        }
        let vm = RosaViewModel(nome: "Nuvola Ovest", server: server, immagini: Immagini(server: server), centro: NotificationCenter())
        await vm.rimuoviImmagine(tipo: "maglia")
        #expect(server.quante("DELETE /api/squadre/immagine") == 1)
        #expect(vm.messaggio == "Squadra non trovata.")
    }

    // MARK: «La mia squadra» senza rete

    @Test("Senza rete e senza copia: «La mia squadra» resta, spenta, con «Si apre quando il server torna raggiungibile»")
    func miaSquadraSenzaRete() async throws {
        let vm = LegaViewModel(server: ServerDiProva.chePrecipita(.senzaRete))
        await vm.carica()
        #expect(vm.squadreNonArrivate)
        let voci = VociImpostazioni.lega(squadre: vm.squadre.dato ?? [], squadreAltrui: true, squadreNonArrivate: vm.squadreNonArrivate)
        #expect(voci.map(\.id) == ["rose", "squadra", "regole"], "«Le altre squadre» resta nascosta, come la web")
        let mia = try #require(voci.first { $0.id == "squadra" })
        #expect(mia.nome == Catalogo.Lega.miaSquadra)
        #expect(mia.sotto == Catalogo.Imp.miaSquadraSenzaRete)
        #expect(mia.pagina == nil, "spenta: non apre niente, come `rigaImpSpenta` della web")
    }

    @Test("Server spento (la rete c'è): anche così la riga resta spenta")
    func miaSquadraServerSpento() async {
        let vm = LegaViewModel(server: ServerDiProva.chePrecipita(.rete("spento")))
        await vm.carica()
        #expect(vm.squadreNonArrivate)
    }

    @Test("Un rifiuto del server con il suo motivo non è «senza rete»: niente riga, come la web sotto i 500")
    func rifiutoDelServer() async {
        let vm = LegaViewModel(server: ServerDiProva.chePrecipita(.troppiTentativi("Troppe richieste.", riprovaTra: nil)))
        await vm.carica()
        #expect(!vm.squadreNonArrivate)
        #expect(!VociImpostazioni.lega(squadre: [], squadreAltrui: true, squadreNonArrivate: vm.squadreNonArrivate)
            .contains { $0.id == "squadra" })
    }

    @Test("Squadre arrivate e nessuna (lega senza rose): nessuna riga «La mia squadra»")
    func senzaRose() async {
        let server = ServerDiProva { _, percorso, _ in
            if percorso == "/api/squadre" { return Data("[]".utf8) }
            throw ErroreApi.server("niente")
        }
        let vm = LegaViewModel(server: server)
        await vm.carica()
        #expect(!vm.squadreNonArrivate)
        #expect(!VociImpostazioni.lega(squadre: vm.squadre.dato ?? [], squadreAltrui: true, squadreNonArrivate: vm.squadreNonArrivate)
            .contains { $0.id == "squadra" })
    }

    // MARK: Stato dei dati, «Quanto ci azzecca il modello»

    private static let calibrazione = #"""
    {"calibrazione": {"giornate": 5, "gruppi": [
      {"gruppo": "Titolare 90-100%", "n": 312, "osservato": 0.94, "previsto": 0.912, "indicativo": false},
      {"gruppo": "Titolare sotto 50%", "n": 1, "osservato": 1.0, "previsto": 0.4, "indicativo": true},
      {"gruppo": "Panchina sotto 20%", "n": 0, "osservato": null, "previsto": null, "indicativo": true}],
      "fattori": {"Titolare 90-100%": 1.03}}}
    """#

    @Test("La riga di ogni gruppo come la web: «hanno giocato» anche con uno solo, e la correzione che il server usa")
    func righeDeiGruppi() throws {
        let s: StatoDati = try Decodifica.decodifica(Data(Self.calibrazione.utf8))
        let c = try #require(s.calibrazione)
        let gruppi = try #require(c.gruppi)
        #expect(c.fattori?["Titolare 90-100%"] == 1.03, "il nome del gruppo resta la chiave, anche con le chiavi convertite")
        let righe = gruppi.map { ParoleRegistro.gruppo($0, fattore: c.fattori?[$0.gruppo]) }
        #expect(righe[0] == "312 giocatori · hanno giocato 94% · previsto 91% · correzione ×1,03")
        #expect(righe[0] == "\(Catalogo.Sd.nGiocatori(312)) · \(Catalogo.Sd.hannoGiocato(o: "94%", p: "91%")) · "
                + Catalogo.Sd.correzione(f: "1,03"))
        #expect(righe[1] == "\(Catalogo.Sd.nGiocatori(1)) · \(Catalogo.Sd.hannoGiocato(o: "100%", p: "40%"))\(Catalogo.Sd.pochiDati)")
        #expect(righe[2] == Catalogo.Sd.nessunDato)
    }

    @Test("La correzione si scrive con i decimali che ha, al massimo tre, come `fNum` della web", arguments: [
        (1.0, "1"), (0.85, "0,85"), (1.125, "1,125"), (1.15, "1,15"),
    ])
    func decimaliDellaCorrezione(fattore: Double, scritto: String) throws {
        let g: StatoDati.GruppoCalibrazione = try Decodifica.decodifica(
            Data(#"{"gruppo": "Panchina 50-100%", "n": 40, "osservato": 0.5, "previsto": 0.5, "indicativo": false}"#.utf8))
        #expect(ParoleRegistro.gruppo(g, fattore: fattore).hasSuffix(" · " + Catalogo.Sd.correzione(f: scritto)))
    }

    // MARK: Stato dei dati, «Quanto è affidabile il modello»

    private static func affidabilita(_ righe: String, sintesi: String = "{}") throws -> Affidabilita {
        try Decodifica.decodifica(Data(#"{"righe": \#(righe), "sintesi": \#(sintesi)}"#.utf8))
    }

    @Test("Legenda e VoiceOver dicono «modello», «da fantamedia» e «massimo possibile», come la web")
    func paroleDelGrafico() throws {
        #expect(ParoleAffidabilita.modello == "modello")
        #expect(ParoleAffidabilita.fantamedia == "da fantamedia")
        #expect(ParoleAffidabilita.massimo == Catalogo.Avv.maxPossibile)
        #expect(ParoleAffidabilita.nomeGrafico == Catalogo.Avv.puntiDelleFormazioni)
        let a = try Self.affidabilita(#"[{"giornata": 5, "punti_modello": 70.1, "punti_fantamedia": 66.4, "punti_perfetta": 88.0}]"#)
        let riga = try #require(a.righe?.first)
        #expect(ParoleAffidabilita.riga(riga) == "5ª giornata di Serie A: modello 70,1, da fantamedia 66,4, massimo possibile 88,0")
    }

    @Test("Sotto la legenda le giornate del grafico, dalla prima all'ultima, con l'apostrofo davanti all'8ª e all'11ª")
    func giornateDelGrafico() throws {
        let a = try Self.affidabilita(#"""
        [{"giornata": 12, "punti_modello": 72.4}, {"giornata": 5, "punti_modello": 70.1}, {"giornata": 9, "punti_modello": 71.0}]
        """#)
        #expect(ParoleAffidabilita.giornate(a.righe ?? []) == "dalla 5ª alla 12ª giornata di Serie A")
        let b = try Self.affidabilita(#"[{"giornata": 8, "punti_modello": 70.1}, {"giornata": 11, "punti_modello": 71.0}]"#)
        #expect(ParoleAffidabilita.giornate(b.righe ?? []) == "dall'8ª all'11ª giornata di Serie A")
        #expect(ParoleAffidabilita.giornate([]) == nil)
    }

    @Test("Il verde sui punti del modello quando valgono almeno quelli da fantamedia (classe `positivo` della web)")
    func verdeSuiPunti() throws {
        let meglio = try #require(try Self.affidabilita("[]", sintesi: #"{"punti_modello": 71.3, "punti_fantamedia": 68.3}"#).sintesi)
        let pari = try #require(try Self.affidabilita("[]", sintesi: #"{"punti_modello": 70.0, "punti_fantamedia": 70.0}"#).sintesi)
        let peggio = try #require(try Self.affidabilita("[]", sintesi: #"{"punti_modello": 66.0, "punti_fantamedia": 68.3}"#).sintesi)
        let senza = try #require(try Self.affidabilita("[]", sintesi: #"{"punti_modello": 66.0}"#).sintesi)
        #expect(ParoleAffidabilita.modelloBatteFantamedia(meglio))
        #expect(ParoleAffidabilita.modelloBatteFantamedia(pari))
        #expect(!ParoleAffidabilita.modelloBatteFantamedia(peggio))
        #expect(!ParoleAffidabilita.modelloBatteFantamedia(senza))
    }

    // MARK: Regole, − e +

    @Test("− e + come la web (#911): da un valore fuori dai passi si va al passo vicino, senza saltarne uno", arguments: [
        (1.25, 0.5, true, 1.5), (1.25, 0.5, false, 1.0), (-0.25, 0.5, true, 0.0), (-0.25, 0.5, false, -0.5),
        (1.0, 0.5, true, 1.5), (1.0, 0.5, false, 0.5), (6.1, 0.25, true, 6.25), (6.1, 0.25, false, 6.0), (3.0, 1.0, true, 4.0),
    ])
    func passi(valore: Double, passo: Double, su: Bool, atteso: Double) {
        #expect(RegoleLogica.passoSuccessivo(valore, passo: passo, su: su, minimo: -20, massimo: 20) == atteso)
    }

    @Test("− e + non escono dai limiti")
    func passiNeiLimiti() {
        #expect(RegoleLogica.passoSuccessivo(19.75, passo: 0.5, su: true, minimo: 0, massimo: 20) == 20)
        #expect(RegoleLogica.passoSuccessivo(0.25, passo: 0.5, su: false, minimo: 0, massimo: 20) == 0)
        #expect(RegoleLogica.passoSuccessivo(20, passo: 0.5, su: true, minimo: 0, massimo: 20) == 20)
    }

    // MARK: Regole, salvataggio

    @Test("Il nome della lega si salva senza spazi ai lati, come la web; vuoto, «La mia lega» del catalogo")
    func nomeDellaLega() throws {
        var v: JSONValue = try Fixture.decodifica("regole", snake: false)
        v.imposta("nome_lega", .testo("  Lega degli Amici \n"))
        #expect(try RegoleLogica.preparaPerSalvataggio(v).valore("nome_lega")?.testo == "Lega degli Amici")
        v.imposta("nome_lega", .testo(" \n "))
        #expect(try RegoleLogica.preparaPerSalvataggio(v).valore("nome_lega")?.testo == Catalogo.Regole.miaLega)
    }

    @Test("Senza moduli, o con due fasce con la stessa media, le frasi della web")
    func frasiDelSalvataggio() throws {
        let v: JSONValue = try Fixture.decodifica("regole", snake: false)
        var senzaModuli = v
        senzaModuli.imposta("moduli", .lista([]))
        var doppie = v
        doppie.imposta("modificatore_difesa.soglie", .lista([.lista([.intero(6), .intero(1)]), .lista([.intero(6), .intero(2)])]))
        for (regole, frase) in [(senzaModuli, Catalogo.Regole.scegliAlmenoModulo), (doppie, Catalogo.Regole.dueFasceHanno)] {
            do {
                _ = try RegoleLogica.preparaPerSalvataggio(regole)
                Issue.record("doveva fermarsi con «\(frase)»")
            } catch {
                #expect(error.localizedDescription == frase)
            }
        }
    }
}
