import Foundation
import Testing
@testable import Schieraxi

/// Issue #299: ogni giornata con i due numeri, come su Leghe e come la web. Dove c'è spazio «Giornata 8 · 11ª di Serie A»;
/// dove si parla solo di Serie A (stagioni passate, `giornata_lega` null, server vecchio) «11ª giornata di Serie A».
/// Una sola regola (`TempiLega`) per tutte le schermate e i widget. Dati inventati: la lega parte dalla 4ª di Serie A.
@Suite("Giornata della lega e di Serie A (#299)")
struct DueNumeriGiornataTests {

    struct Caso: Sendable, CustomTestStringConvertible {
        let serieA: Int
        let lega: Int?
        let atteso: String
        var testDescription: String { atteso }
    }

    @Test("La forma intera dice i due numeri; senza il numero della lega solo quello di Serie A", arguments: [
        Caso(serieA: 11, lega: 8, atteso: "Giornata 8 · 11ª di Serie A"),
        Caso(serieA: 10, lega: 7, atteso: "Giornata 7 · 10ª di Serie A"),
        // lega partita con il campionato: i due numeri coincidono e si scrivono tutti e due, come sempre
        Caso(serieA: 3, lega: 3, atteso: "Giornata 3 · 3ª di Serie A"),
        // stagione passata, prima che la lega parta o server vecchio: solo Serie A, mai un numero della lega inventato
        Caso(serieA: 11, lega: nil, atteso: "11ª giornata di Serie A"),
        Caso(serieA: 11, lega: 0, atteso: "11ª giornata di Serie A"),
        Caso(serieA: 11, lega: -2, atteso: "11ª giornata di Serie A"),
    ])
    func formaIntera(_ caso: Caso) {
        #expect(TempiLega.etichetta(serieA: caso.serieA, lega: caso.lega) == caso.atteso)
    }

    @Test("Dove si parla solo del calendario di Serie A: «11ª giornata di Serie A»")
    func soloSerieA() {
        #expect(TempiLega.serieA(11) == "11ª giornata di Serie A")
        #expect(TempiLega.serieA(1) == "1ª giornata di Serie A")
    }

    @Test("Oggi: la testata dice i due numeri")
    func oggi() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11, "giornata_lega": 8}"#.utf8))
        #expect(o.etichettaGiornata == "Giornata 8 · 11ª di Serie A")
        let vecchio: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11}"#.utf8))
        #expect(vecchio.etichettaGiornata == "11ª giornata di Serie A", "server senza `giornata_lega`")
    }

    @Test("Formazione: intestazione e testo da condividere con i due numeri")
    func formazione() throws {
        let f: Formazione = try Fixture.decodifica("formazione")
        #expect(f.etichettaGiornata == "\(f.giornata)ª giornata di Serie A", "la fixture non ha `giornata_lega`")
        let testo = TestoFormazione.crea(giornata: 11, giornataLega: 8, modulo: "4-3-3", titolari: [], panchina: [])
        #expect(testo.components(separatedBy: "\n").first == "Giornata 8 · 11ª di Serie A · 4-3-3")
    }

    @Test("Diario e «Le tue scelte»: stagione in corso con i due numeri, stagione passata solo Serie A")
    func diario() throws {
        let v: VoceDiario = try Decodifica.decodifica(Data(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27"}"#.utf8))
        #expect(v.titolo == "Giornata 8 · 11ª di Serie A")
        #expect(v.giornata == 11, "al server si manda sempre il numero di Serie A")
        let passata: VoceDiario = try Decodifica.decodifica(Data(#"{"giornata": 38, "giornata_lega": null, "stagione": "2025-26"}"#.utf8))
        #expect(passata.titolo == "38ª giornata di Serie A")
        let s: SceltaGiornata = try Decodifica.decodifica(Data(#"{"stagione": "2026-27", "giornata": 9, "giornata_lega": 6}"#.utf8))
        #expect(s.titolo == "Giornata 6 · 9ª di Serie A")
    }

    @Test("Fasi della giornata in Oggi: la giornata con i due numeri")
    func giornataFinita() {
        #expect(TestiFase.giornata(serieA: 11, lega: 8) == "Giornata 8 · 11ª di Serie A")
        #expect(TestiFase.giornata(serieA: 11, lega: nil) == "11ª giornata di Serie A")
        #expect(TestiFase.giornata(serieA: nil, lega: 8) == nil, "senza Serie A non si inventa niente")
    }

    @Test("Widget: la forma intera dove c'è spazio, «G8» negli spazi strettissimi")
    func widget() throws {
        let w = try #require(RiassuntoWidget.leggi(Data(#"{"giornata": 11, "giornata_lega": 8}"#.utf8)))
        #expect(w.etichettaGiornata == "Giornata 8 · 11ª di Serie A")
        #expect(w.siglaGiornata == "G8")
        #expect(w.comeRiassuntoOggi()?.etichettaGiornata == "Giornata 8 · 11ª di Serie A")
    }

    @Test("Widget «Attesi e fatti»: le voci del diario con i due numeri, quelle di un'altra stagione solo Serie A")
    func widgetDiario() throws {
        let w = try #require(RiassuntoWidget.leggi(Data(#"""
        {"giornata": 6, "giornata_lega": 3, "diario": [
          {"giornata": 5, "giornata_lega": 2, "stagione": "2026-27", "attesi": 66, "fatti": 63.5},
          {"giornata": 38, "giornata_lega": null, "stagione": "2025-26", "attesi": 70, "fatti": 72}]}
        """#.utf8)))
        let g = w.giornateGiocate
        #expect(g.map(\.titolo) == ["Giornata 2 · 5ª di Serie A", "38ª giornata di Serie A · 2025-26"])
        #expect(g.map(\.sigla) == ["G2", "G38"])
    }

    // MARK: forme corte e VoiceOver

    @Test("Spazio poco: «Giornata 8» con «11ª di Serie A» sotto, poi «G8»; VoiceOver sempre i due numeri")
    func formeCorte() {
        let n = NomeGiornata(serieA: 11, lega: 8)
        #expect(n.corto == "Giornata 8")
        #expect(n.sotto == "11ª di Serie A")
        #expect(n.sigla == "G8")
        #expect(n.voce == "Giornata 8, 11ª di Serie A", "VoiceOver: la virgola al posto di «·»")
        #expect(n.forme == ["Giornata 8 · 11ª di Serie A", "Giornata 8", "G8"])
        #expect(n.formeCorte == ["Giornata 8", "G8"], "nel widget piccolo solo «Giornata 8»")
        #expect(n.intero.unicodeScalars.contains("\u{00AA}"), "«ª» è l'ordinale femminile, non una «a»")
        let s = NomeGiornata(serieA: 11, lega: nil)
        #expect(s.corto == "11ª di Serie A")
        #expect(s.sotto == nil, "senza numero della lega non c'è la seconda riga")
        #expect(s.sigla == "G11")
        #expect(s.voce == "11ª giornata di Serie A")
        #expect(s.forme == ["11ª giornata di Serie A", "11ª di Serie A", "G11"])
    }

    @Test("La didascalia della Formazione: «Giornata 8 · 11ª di Serie A · modulo consigliato»; con la tua scelta solo la giornata")
    func didascaliaFormazione() {
        let g = TempiLega.etichetta(serieA: 11, lega: 8)
        #expect(TempiLega.didascalia(giornata: g, scelta: true, comeConsigliato: false) == "Giornata 8 · 11ª di Serie A")
        #expect(TempiLega.didascalia(giornata: g, scelta: false, comeConsigliato: true) == "Giornata 8 · 11ª di Serie A · modulo consigliato")
        #expect(TempiLega.didascalia(giornata: g, scelta: false, comeConsigliato: false) == "Giornata 8 · 11ª di Serie A · modulo scelto")
    }

    // MARK: schermate

    @MainActor
    @Test("Oggi dopo la scadenza: «La formazione si è chiusa …», senza ripetere la giornata scritta sopra")
    func oggiChiusa() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 14:50"}"#.utf8))
        let quando = Quando.leggibile("2026-10-31 14:50")
        #expect(OggiView.siEChiusa(o) == "La formazione si è chiusa \(quando)")
        if let web = try TestiWeb().italianoDopo299("oggi.chiusa_dettaglio", quando) { #expect(OggiView.siEChiusa(o) == web) }
    }

    @Test("Oggi a giornata finita: «Giornata 8 · 11ª di Serie A: finita», come la web")
    func oggiFinita() throws {
        let attesa = "Giornata 8 · 11ª di Serie A: finita"
        #expect(TestiFase.giornataFinita(serieA: 11, lega: 8) == attesa)
        #expect(TestiFase.giornataFinita(serieA: 11, lega: 8, voce: true) == "Giornata 8, 11ª di Serie A: finita")
        #expect(TestiFase.giornataFinita(serieA: nil, lega: 8) == nil)
        if let web = try TestiWeb().italianoDopo299("oggi.giornata_finita", "Giornata 8 · 11ª di Serie A") { #expect(web == attesa) }
    }

    private func giocatore(_ extra: String) throws -> Giocatore {
        try Decodifica.decodifica(Data(#"{"id": 7, "nome": "Retalli", "ruolo": "A", \#(extra)}"#.utf8))
    }

    @MainActor
    @Test("Scheda, prossima partita: «Giornata 8 · 11ª di Serie A · in casa contro Como»")
    func scheda() throws {
        let g = try giocatore(#""giornata": 11, "giornata_lega": 8, "avversario": "como", "in_casa": true"#)
        #expect(GiocatoreCorpo.descrizionePartita(g) == "Giornata 8 · 11ª di Serie A · in casa contro Como")
        #expect(GiocatoreCorpo.descrizionePartita(g, voce: true) == "Giornata 8, 11ª di Serie A, in casa contro Como")
        let vecchio = try giocatore(#""giornata": 11, "avversario": "milan", "in_casa": false"#)
        #expect(GiocatoreCorpo.descrizionePartita(vecchio) == "11ª giornata di Serie A · in trasferta contro Milan",
                "server senza `giornata_lega`: solo Serie A")
    }

    @Test("Confronto, titolo (#302): i due numeri dal server; senza `giornata_lega` solo Serie A")
    func confronto() throws {
        let c: Confronto = try Decodifica.decodifica(Data(#"{"giornata": 11, "giornata_lega": 8, "giocatori": [], "fattori": []}"#.utf8))
        #expect(c.titolo == "Giornata 8 · 11ª di Serie A")
        let vecchio: Confronto = try Fixture.decodifica("confronto")
        #expect(vecchio.titolo == "9ª giornata di Serie A", "la fixture viene da un server senza `giornata_lega`")
        let senza: Confronto = try Decodifica.decodifica(Data(#"{"giornata": null, "giocatori": [], "fattori": []}"#.utf8))
        #expect(senza.titolo == nil)
    }

    @MainActor
    @Test("Confronto, sotto il nome (#302): «INT vs ROM» in casa, «INT @ ROM» in trasferta, come la web (`partitaRiga`)")
    func confrontoPartita() throws {
        #expect(ColonnaDuello.partita(try giocatore(#""squadra": "inter", "avversario": "roma", "in_casa": true"#)) == "INT vs ROM")
        #expect(ColonnaDuello.partita(try giocatore(#""squadra": "inter", "avversario": "roma", "in_casa": false"#)) == "INT @ ROM")
        #expect(ColonnaDuello.partita(try giocatore(#""squadra": "inter""#)) == "INT", "senza avversario solo la sigla")
    }

    @Test("Diario, «Quanto ci abbiamo preso»: VoiceOver legge i due numeri della giornata")
    func diarioVoce() throws {
        let v: VoceDiario = try Decodifica.decodifica(Data(#"""
        {"stagione": "2026-27", "giornata": 11, "giornata_lega": 8, "atteso_vs_fatto": {"atteso": 70.0, "fatti": 72.5}}
        """#.utf8))
        let p = try #require(PuntoAttesoFatto.elenco([v]).first)
        #expect(p.giornata == 8, "nel grafico il numero della lega")
        #expect(p.voce == "Giornata 8, 11ª di Serie A: attesi 70,0 punti, fatti 72,5")
        let barra = TestoPrecisione.Barra(id: 0, etichetta: "8", errore: 1.4, nome: NomeGiornata(serieA: 11, lega: 8))
        #expect(barra.voce == "Giornata 8, 11ª di Serie A: errore medio 1,4 punti")
    }

    @Test("Avvisi del telefono: la giornata in testa, seguita dai due punti, come gli avvisi del server")
    func promemoria() {
        let n = NomeGiornata(serieA: 11, lega: 8)
        #expect(Notifiche.corpoPromemoria(giornata: n, modulo: "3-4-3")
                == "Giornata 8 · 11ª di Serie A: modulo consigliato 3-4-3. Mister, dai un'occhiata alla formazione.")
        #expect(Notifiche.corpoPromemoria(giornata: n, modulo: nil) == "Giornata 8 · 11ª di Serie A: mister, dai un'occhiata alla formazione.")
    }

    @MainActor
    @Test("Calendario e grafico dei voti, dove si parla solo di Serie A: «11ª giornata di Serie A» per VoiceOver")
    func soloSerieAPerVoiceOver() {
        let voti = [VotoGiornata(giornata: 11, voto: 6.5, fv: 7, gol: nil, assist: nil),
                    VotoGiornata(giornata: 12, voto: nil, fv: nil, gol: nil, assist: nil)]
        #expect(GraficoVoti.descrizione(voti) == ["11ª giornata di Serie A: voto 6,5, fantavoto 7,0", "12ª giornata di Serie A: senza voto"])
    }

    @Test("Widget, server o riassunto vecchi: senza `giornata_lega` solo Serie A, senza giornata niente")
    func widgetVecchio() throws {
        let senza = RiassuntoWidget.leggi(Data(#"{"giornata": 11, "giornata_lega": null}"#.utf8))
        #expect(senza?.etichettaGiornata == "11ª giornata di Serie A")
        #expect(RiassuntoWidget.leggi(Data(#"{}"#.utf8))?.etichettaGiornata == nil)
        let salvato = try JSONDecoder().decode(RiassuntoOggi.self, from: Data(#"{"giornata": 9, "daControllare": 0, "scaricatoIl": 0}"#.utf8))
        #expect(salvato.etichettaGiornata == "9ª giornata di Serie A", "un riassunto salvato da una versione vecchia si legge")
        #expect(salvato.voceGiornata == "9ª giornata di Serie A")
    }
}
