import Foundation
import Testing
@testable import Schieraxi

/// Oggi a giornata in corso e finita con le frasi della web (#436, parte di #167): `cardInCorso`, `valoreLive` e `cardRiepilogo`
/// di `fanta/web/app.js`, testi `oggi.*` del catalogo comune (`fanta/testi/oggi.json`, in Swift `Catalogo.Oggi`, #494). Le frasi
/// di `TestiFase` si confrontano con `Catalogo`, i numeri con la stessa risposta del server: una parola cambiata su un lato solo
/// fa fallire il test.
@Suite("Oggi in corso e finita con le frasi della web (#436)")
struct OggiFasiComeLaWebTests {
    // MARK: il difetto dei voti

    /// `ancora_da_giocare` conta chi va a punteggio e deve ancora giocare o sta giocando (`docs/API.md`, «fasi della giornata»):
    /// chi ha già giocato e aspetta il voto non c'è. L'iPhone scriveva «Mancano i voti di 2 giocatori», che è falso.
    @Test("«2 giocatori devono ancora giocare», non «Mancano i voti»: il numero è di chi deve ancora giocare", arguments: [1, 2, 6])
    func ancoraDaGiocare(n: Int) throws {
        let web = Catalogo.Oggi.ancoraDaGiocare(n)
        let frase = try #require(TestiFase.ancora(n))
        #expect(frase == web)
        #expect(!frase.contains("voti"), "il numero non è quello dei voti che mancano: \(frase)")
    }

    /// La stessa risposta del server che legge la web: uno ha il voto, uno ha finito e aspetta il voto, uno sta giocando e uno deve
    /// ancora cominciare. `ancora_da_giocare` = 2 (gli ultimi due): i voti che mancano sarebbero 3.
    @Test("Con la risposta del server: 2 devono ancora giocare (uno in campo, uno da giocare), uno aspetta solo il voto")
    func ancoraDaGiocareDalServer() throws {
        let json = #"""
        {"giornata": 11, "giornata_lega": 8, "fase": "in_corso", "iniziata": true,
         "in_corso": {"giornata": 11, "giornata_lega": 8, "formazione_di": "tua", "punti_fatti": 12.5, "punti_previsti": 70.1,
           "ancora_da_giocare": 2,
           "giocatori": [
             {"id": 1, "nome": "Ivo Sorvani", "ruolo": "P", "titolare": true, "a_punteggio": true, "stato": "fatto", "fantavoto": 6},
             {"id": 2, "nome": "Glauco Brevisi", "ruolo": "D", "titolare": true, "a_punteggio": true, "stato": "attesa_voti"},
             {"id": 3, "nome": "Aurelio Buonvicini", "ruolo": "D", "titolare": true, "a_punteggio": true, "stato": "in_corso"},
             {"id": 4, "nome": "Marvin Thorvan", "ruolo": "A", "titolare": true, "a_punteggio": true, "stato": "da_giocare",
              "data": "2026-11-08 18:00"}]}}
        """#
        let oggi: Oggi = try Decodifica.decodifica(Data(json.utf8))
        let b = try #require(oggi.giornataInCorso)
        let daGiocare = b.giocatori.filter { $0.aPunteggio && ["da_giocare", "in_corso"].contains($0.stato ?? "") }.count
        let senzaVoto = b.giocatori.filter { $0.aPunteggio && $0.stato != "fatto" }.count
        #expect(b.ancoraDaGiocare == daGiocare, "il conto del server è quello di chi deve ancora giocare")
        #expect(senzaVoto == 3, "i voti che mancano sono di più: non è lo stesso numero")
        let web = Catalogo.Oggi.ancoraDaGiocare(2)
        #expect(TestiFase.ancora(b.ancoraDaGiocare) == web)
        #expect(web == "2 giocatori devono ancora giocare")
    }

    @Test("Hanno giocato tutti: «Hanno giocato tutti: mancano solo i voti ufficiali.»; senza il numero niente riga")
    func tuttiGiocato() {
        #expect(TestiFase.ancora(0) == Catalogo.Oggi.tuttiGiocato)
        let nessuna: String? = nil
        #expect(TestiFase.ancora(nil) == nessuna, "server senza il numero: la riga non si inventa")
    }

    // MARK: chi va a punteggio

    @Test("Chi deve ancora giocare ha la data della sua partita («sab 8 18:00»), come la web, non «Da giocare»")
    func dataDiChiDeveGiocare() {
        let g = GiocatoreInCorso(id: 1, nome: "Ivo Sorvani", stato: "da_giocare", data: "2026-11-08 18:00")
        #expect(TestiFase.valore(g) == Quando.leggibile("2026-11-08 18:00", adesso: Orologio.adesso()))
        let senzaData = GiocatoreInCorso(id: 1, nome: "Ivo Sorvani", stato: "da_giocare")
        #expect(TestiFase.valore(senzaData) == Catalogo.Oggi.stDaGiocare, "senza la data, come la web: «Da giocare»")
    }

    @Test("Lo stato della partita con le parole della web", arguments: [
        ("senza_voto", Catalogo.Oggi.stSenzaVoto), ("attesa_voti", Catalogo.Oggi.stAttesaVoti),
        ("in_corso", Catalogo.Oggi.stInCorso), ("rinviata", Catalogo.Oggi.stRinviata),
    ])
    func statoComeLaWeb(stato: String, testo: String) {
        #expect(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo Sorvani", stato: stato)) == testo)
    }

    // MARK: cambi dalla panchina

    @Test("Cambi dalla panchina: «Bastrani → Dimarzi», «Buonvicini → nessun sostituto», «già fatto» o «probabile»")
    func cambi() {
        let fatto = Catalogo.Oggi.cambioFatto
        let probabile = Catalogo.Oggi.cambioProbabile
        let nessuno = Catalogo.Oggi.nessunSostituto
        let certo = CambioPanchina(esce: PersonaCambio(id: 1, nome: "Bastrani"), entra: PersonaCambio(id: 2, nome: "Dimarzi"),
                                   certa: true, motivo: "senza_voto")
        #expect(TestiFase.cambio(certo) == "Bastrani → Dimarzi")
        #expect(TestiFase.etichettaCambio(certo) == fatto)
        let senza = CambioPanchina(esce: PersonaCambio(id: 3, nome: "Buonvicini"), entra: nil, certa: false, motivo: "fuori")
        #expect(TestiFase.cambio(senza) == "Buonvicini → \(nessuno)")
        #expect(TestiFase.etichettaCambio(senza) == probabile)
    }

    // MARK: giornata finita

    @Test("Giornata finita: «Con la consigliata: 72,0 punti (66,1 attesi).» e «Il confronto con la consigliata arriva nel Diario.»")
    func riepilogo() {
        let conConsigliata = Catalogo.Oggi.conConsigliata(attesi: "66,1", fatti: "72,0")
        let r = RiepilogoGiornata(giornata: 10, giornataLega: 7, formazioneDi: "tua", nelDiario: true, puntiFatti: 70.5, puntiAttesi: 66.1,
                                  consigliata: PuntiConsigliata(puntiFatti: 72, puntiAttesi: 66.1))
        #expect(TestiFase.confronto(r) == conConsigliata)
        let nessuna: String? = nil
        let consigliata = RiepilogoGiornata(formazioneDi: "consigliata", nelDiario: true, puntiFatti: 72,
                                            consigliata: PuntiConsigliata(puntiFatti: 72, puntiAttesi: 66.1))
        #expect(TestiFase.confronto(consigliata) == nessuna, "con la consigliata schierata la web non scrive il confronto")
        let nota = Catalogo.Oggi.confrontoInArrivo
        #expect(TestiFase.notaDiario(RiepilogoGiornata(nelDiario: false, puntiFatti: 50)) == nota)
        #expect(TestiFase.notaDiario(r) == nessuna)
    }

    @Test("Prossima giornata nella carta della giornata finita: «Giornata 9 · 12ª di Serie A: la formazione si chiude …» e da quando prepararla")
    func prossima() throws {
        let adesso = try #require(Quando.data("2026-11-09 10:00"))
        let chiude = Catalogo.Oggi.prossimaChiude(g: "Giornata 9 · 12ª di Serie A",
                                                  quando: Quando.leggibile("2026-11-14 14:30", adesso: adesso))
        let da = Catalogo.Oggi.prossimaDa(quando: Quando.leggibile("2026-11-11 14:30", adesso: adesso))
        let pronta = Catalogo.Oggi.prossimaPronta

        let presto = ProssimaGiornata(giornata: 12, giornataLega: 9, scadenza: "2026-11-14 14:30", preparaDa: "2026-11-11 14:30")
        #expect(TestiFase.prossima(presto, adesso: adesso) == "\(chiude) \(da)")
        #expect(TestiFase.prossima(presto, adesso: adesso) == "Giornata 9 · 12ª di Serie A: la formazione si chiude sab 14 14:30. Conviene prepararla da mer 11 14:30, quando escono le probabili formazioni.")
        let conProbabili = ProssimaGiornata(giornata: 12, giornataLega: 9, scadenza: "2026-11-14 14:30", preparaDa: "2026-11-11 14:30",
                                            conProbabili: true)
        #expect(TestiFase.prossima(conProbabili, adesso: adesso) == "\(chiude) \(pronta)")
        let giaOra = ProssimaGiornata(giornata: 12, giornataLega: 9, scadenza: "2026-11-14 14:30", preparaDa: "2026-11-09 10:00")
        #expect(TestiFase.prossima(giaOra, adesso: adesso) == "\(chiude) \(pronta)")
        let nessuna: String? = nil
        #expect(TestiFase.prossima(ProssimaGiornata(giornata: 12, giornataLega: 9, preparaDa: "2026-11-11 14:30"), adesso: adesso) == nessuna,
                "senza scadenza la web non scrive la riga")
    }

    @Test("Prossima giornata senza il numero (server strano): la stessa frase senza «Giornata N:» davanti, con la maiuscola")
    func prossimaSenzaNumero() throws {
        let adesso = try #require(Quando.data("2026-11-09 10:00"))
        let p = ProssimaGiornata(scadenza: "2026-11-14 14:30", conProbabili: true)
        #expect(TestiFase.prossima(p, adesso: adesso) == "La formazione si chiude sab 14 14:30. \(Catalogo.Oggi.prossimaPronta)")
    }

    // MARK: parole fisse

    /// `TestiFase` (in `Domain/FasiGiornata.swift`) prende i testi dal catalogo (#556; prova del sorgente in `RestiDalCatalogoTests`):
    /// qui si confrontano i valori. Da fare e le partite del turno usano direttamente `Catalogo.Df` e `Catalogo.Live` (prova in
    /// `OggiDalCatalogoTests`).
    @Test("Titoli e frasi fisse della giornata in corso, già iniziata e finita: quelle del catalogo", arguments: [
        (TestiFase.puntiFinora, Catalogo.Oggi.puntiFinora),
        (TestiFase.aFineGiornata, Catalogo.Oggi.aFineGiornata),
        (TestiFase.dallaPanchina, Catalogo.Oggi.dallaPanchina),
        (TestiFase.cambiPanchina, Catalogo.Oggi.cambiPanchina),
        (TestiFase.tuttiGiocato, Catalogo.Oggi.tuttiGiocato),
        (TestiFase.nessunSostituto, Catalogo.Oggi.nessunSostituto),
        (TestiFase.giaIniziata, Catalogo.Oggi.giaIniziata),
        (TestiFase.giaIniziataTesto, Catalogo.Oggi.giaIniziataTesto),
        (TestiFase.preparaProssima, Catalogo.Oggi.preparaProssima),
        (TestiFase.formazioneDi(RiepilogoGiornata(formazioneDi: "tua")), Catalogo.Oggi.laTuaFormazione),
        (TestiFase.formazioneDi(RiepilogoGiornata(formazioneDi: "consigliata")), Catalogo.Oggi.laConsigliata),
        (TestiFase.puntiFatti, Catalogo.Oggi.puntiFatti),
        (TestiFase.puntiAttesi, Catalogo.Oggi.puntiAttesi),
        (TestiFase.apriDiario, Catalogo.Oggi.apriDiario),
    ])
    func paroleComeLaWeb(iPhone: String, catalogo: String) {
        #expect(iPhone == catalogo)
    }

    @Test("«attesi prima: 65,5» e «≈ 77,7» come la web")
    func cifreInCorso() {
        #expect(TestiFase.attesiPrima(65.5) == Catalogo.Oggi.attesiPrima(n: "65,5"))
        #expect(TestiFase.previsti(77.7) == "≈ 77,7")
    }

    // MARK: entrato a giornata iniziata

    static let prossimaJSON = #""prossima": {"giornata": 12, "giornata_lega": 9, "scadenza": "2026-11-14 14:30", "prepara_da": "2026-11-11 14:30", "con_probabili": false}"#

    @Test("`senza_formazione` con la fase in corso: la carta «Questa giornata è già iniziata» con la prossima giornata")
    func senzaFormazione() throws {
        let json = #"{"giornata": 11, "giornata_lega": 8, "fase": "in_corso", "iniziata": true, "senza_formazione": true, "in_corso": null, "# + Self.prossimaJSON + "}"
        let oggi: Oggi = try Decodifica.decodifica(Data(json.utf8))
        #expect(oggi.senzaFormazioneInCorso)
        #expect(oggi.giornataInCorso == nil)
        let p = try #require(oggi.prossimaGiornata, "la prossima giornata serve alla riga «… la formazione si chiude …»")
        #expect(p.giornataLega == 9)
        let adesso = try #require(Quando.data("2026-11-09 10:00"))
        #expect(TestiFase.prossima(p, adesso: adesso)?.hasPrefix("Giornata 9 · 12ª di Serie A: la formazione si chiude") == true)
    }

    @Test("Server vecchio, valore strano o fase sbagliata: niente carta «già iniziata» e Oggi si legge lo stesso", arguments: [
        #"{"giornata": 11, "fase": "in_corso", "in_corso": null, "# + OggiFasiComeLaWebTests.prossimaJSON + "}",
        #"{"giornata": 11, "fase": "in_corso", "senza_formazione": "sì", "in_corso": null, "# + OggiFasiComeLaWebTests.prossimaJSON + "}",
        #"{"giornata": 11, "fase": "in_corso", "senza_formazione": false, "in_corso": null}"#,
        #"{"giornata": 11, "fase": "prima", "senza_formazione": true, "# + OggiFasiComeLaWebTests.prossimaJSON + "}",
    ])
    func senzaFormazioneTollerante(json: String) throws {
        let oggi: Oggi = try Decodifica.decodifica(Data(json.utf8))
        #expect(oggi.giornata == 11)
        #expect(!oggi.senzaFormazioneInCorso)
        #expect(oggi.prossimaGiornata == nil, "la prossima conta solo a giornata finita o per chi è entrato a giornata iniziata")
    }

    // MARK: partite del turno

}
