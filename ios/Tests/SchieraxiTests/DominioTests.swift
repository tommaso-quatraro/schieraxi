import XCTest
@testable import Schieraxi

/// Le regole di contorno che non toccano la rete: forma, etichette, ballottaggi, testo della formazione, scambi, regole, collegamenti.
final class DominioTests: XCTestCase {
    private func voto(_ g: Int, _ fv: Double?) -> VotoGiornata {
        VotoGiornata(giornata: g, voto: fv.map { $0 - 1 }, fv: fv, gol: nil, assist: nil)
    }

    private func giocatore(_ id: Int, _ nome: String, ruolo: String = "D", titolarita: String? = "titolare", punti: Double = 5, pVoto: Double = 0.9,
                           extra: String = "") throws -> Giocatore {
        let titolo = titolarita.map { "\"titolarita\": \"\($0)\"," } ?? ""
        let json = "{\(titolo) \(extra) \"id\": \(id), \"nome\": \"\(nome)\", \"ruolo\": \"\(ruolo)\", \"punti_attesi\": \(punti), \"p_voto\": \(pVoto)}"
        return try Decodifica.decodifica(Data(json.utf8))
    }

    // MARK: forma

    func testFormaConPochiDatiNonGiudica() throws {
        let f = try XCTUnwrap(Forma.calcola([voto(1, 6), voto(2, 7), voto(3, nil)]))
        XCTAssertEqual(f.andamento, .pochiDati)
        XCTAssertEqual(f.ultime.count, 3)
        XCTAssertNil(Forma.calcola([]))
    }

    func testFormaInCrescitaInCaloEStabile() throws {
        let crescita = (1...6).map { voto($0, $0 <= 3 ? 5 : 8) }
        XCTAssertEqual(Forma.calcola(crescita)?.andamento, .crescita)
        XCTAssertEqual(Forma.calcola(crescita)?.andamento.freccia, "↗")
        let calo = (1...6).map { voto($0, $0 <= 3 ? 8 : 5) }
        XCTAssertEqual(Forma.calcola(calo)?.andamento, .calo)
        XCTAssertEqual(Forma.calcola(calo)?.andamento.freccia, "↘")
        let stabile = (1...6).map { voto($0, 6.5) }
        XCTAssertEqual(Forma.calcola(stabile)?.andamento, .stabile)
        // le ultime sono al massimo cinque, in ordine di giornata
        XCTAssertEqual(Forma.calcola(stabile)?.ultime.map(\.giornata), [2, 3, 4, 5, 6])
    }

    // Le etichette sono passate a Swift Testing: `EtichetteGiocatoreTests`.

    // MARK: testo, nome corto

    func testTestoDellaFormazione() throws {
        let p = try giocatore(1, "Noraldi", ruolo: "P")
        let d1 = try giocatore(2, "Foselli")
        let d2 = try giocatore(3, "Barucci")
        let c = try giocatore(4, "Delardi", ruolo: "C")
        let a = try giocatore(5, "Castotti", ruolo: "A")
        let panchina = [try giocatore(6, "Pelucci", ruolo: "P"), try giocatore(7, "Fosaldi", ruolo: "P")]
        let testo = TestoFormazione.crea(giornata: 9, modulo: "2-1-1", titolari: [a, c, d1, p, d2], panchina: panchina)
        XCTAssertEqual(testo, "9ª giornata di Serie A · 2-1-1\nP: Noraldi\nD: Foselli, Barucci\nC: Delardi\nA: Castotti\nPanchina: 1) Pelucci, 2) Fosaldi")
        XCTAssertFalse(TestoFormazione.crea(giornata: 1, modulo: "x", titolari: [], panchina: []).contains("Panchina"))
    }

    func testNomeCorto() throws {
        XCTAssertEqual(try giocatore(1, "Dalanti S.").nomeCorto, "Dalanti")
        XCTAssertEqual(try giocatore(1, "Monelli Feraldi").nomeCorto, "Monelli Feraldi")
        XCTAssertEqual(try giocatore(1, "Lanotti E.").nomeCorto, "Lanotti")
        XCTAssertEqual(try giocatore(1, "Pelayo").nomeCorto, "Pelayo")
    }

    // MARK: confronto

    // MARK: scambi

    // MARK: regole

    func testPercorsiNelJSONDelleRegole() throws {
        var v: JSONValue = try Fixture.decodifica("regole", snake: false)
        XCTAssertEqual(v.valore("bonus.assist")?.numero, 1)
        v.imposta("bonus.assist", .numero(1.5))
        XCTAssertEqual(v.valore("bonus.assist"), .decimale(1.5))
        v.imposta("crediti_iniziali", .numero(600))
        XCTAssertEqual(v.valore("crediti_iniziali"), .intero(600), "un numero intero resta intero")
        v.imposta("nuovo.livello.valore", .booleano(true))
        XCTAssertEqual(v.valore("nuovo.livello.valore")?.booleano, true)
        XCTAssertNil(v.valore("non.esiste"))
    }

    func testRiconoscimentoApplicatoSenzaSalvare() throws {
        let originale: JSONValue = try Fixture.decodifica("regole", snake: false)
        let riconosciute: [ModificaRegola] = [
            ModificaRegola(chiave: "bonus.assist", etichetta: "Assist", valore: .decimale(2), riga: nil),
            ModificaRegola(chiave: "moduli", etichetta: "Moduli", valore: .lista([.testo("3-4-3"), .testo("4-4-2")]), riga: nil),
            ModificaRegola(chiave: "panchina.numero", etichetta: "Panchina", valore: .intero(7), riga: nil),
        ]
        let nuove = RegoleLogica.applica(riconosciute, a: originale)
        XCTAssertEqual(nuove.valore("bonus.assist")?.numero, 2)
        XCTAssertEqual(nuove.valore("moduli")?.elenco?.count, 2)
        XCTAssertEqual(nuove.valore("panchina.numero")?.numero, 7)
        // il resto delle regole non cambia
        XCTAssertEqual(nuove.valore("bonus.gol.A"), originale.valore("bonus.gol.A"))
        XCTAssertEqual(originale.valore("bonus.assist")?.numero, 1, "l'originale non si tocca")
    }

    func testFasceDelModificatoreDifesa() throws {
        let v: JSONValue = try Fixture.decodifica("regole", snake: false)
        let fasce = RegoleLogica.fasce(v)
        XCTAssertEqual(fasce.count, 6)
        XCTAssertEqual(fasce.first?.media, 6)
        XCTAssertEqual(RegoleLogica.bonusDifesa(media: 5.9, fasce: fasce), 0)
        XCTAssertEqual(RegoleLogica.bonusDifesa(media: 6.0, fasce: fasce), 1)
        XCTAssertEqual(RegoleLogica.bonusDifesa(media: 6.6, fasce: fasce), 2)
        XCTAssertEqual(RegoleLogica.bonusDifesa(media: 9, fasce: fasce), 3.5)
        XCTAssertEqual(RegoleLogica.mediaDifesa([6.5, 6, 6.5, 7]), 6.5)
        var scritte = v
        RegoleLogica.scriviFasce([RegoleLogica.Fascia(media: 7, bonus: 4), RegoleLogica.Fascia(media: 6, bonus: 1)], in: &scritte)
        XCTAssertEqual(RegoleLogica.fasce(scritte).map(\.media), [6, 7], "si scrivono in ordine di media")
    }

    func testControlliPrimaDiSalvareLeRegole() throws {
        var v: JSONValue = try Fixture.decodifica("regole", snake: false)
        // posti fissi: il numero in panchina diventa la somma dei posti (2 + 3 + 3 + 3)
        v.imposta("panchina.numero", .intero(1))
        XCTAssertEqual(try RegoleLogica.preparaPerSalvataggio(v).valore("panchina.numero")?.numero, 11)
        // nessun modulo
        var senzaModuli = v
        senzaModuli.imposta("moduli", .lista([]))
        XCTAssertThrowsError(try RegoleLogica.preparaPerSalvataggio(senzaModuli)) { XCTAssertEqual($0.localizedDescription, "Scegli almeno un modulo.") }
        // due fasce con la stessa media
        var doppie = v
        doppie.imposta("modificatore_difesa.soglie", .lista([.lista([.intero(6), .intero(1)]), .lista([.intero(6), .intero(2)])]))
        XCTAssertThrowsError(try RegoleLogica.preparaPerSalvataggio(doppie)) { XCTAssertTrue($0.localizedDescription.contains("stessa media")) }
        // nome vuoto
        var senzaNome = v
        senzaNome.imposta("nome_lega", .testo("  "))
        XCTAssertEqual(try RegoleLogica.preparaPerSalvataggio(senzaNome).valore("nome_lega")?.testo, "La mia lega")
    }

    func testDescrizioneDeiValoriRiconosciuti() {
        XCTAssertEqual(RegoleLogica.descrivi(.booleano(true)), "sì")
        XCTAssertEqual(RegoleLogica.descrivi(.intero(7)), "7")
        XCTAssertEqual(RegoleLogica.descrivi(.decimale(0.5)), "0,5")
        XCTAssertEqual(RegoleLogica.descrivi(.lista([.testo("3-4-3"), .testo("4-4-2")])), "3-4-3, 4-4-2")
        XCTAssertEqual(RegoleLogica.descrivi(.lista([.lista([.decimale(6), .intero(1)]), .lista([.decimale(6.25), .decimale(1.5)])])), "6,00→+1 · 6,25→+2")
    }

    // MARK: collegamenti, icone, avvio, colori

    func testCollegamentiSchieraxi() {
        func vai(_ testo: String) -> Destinazione? { URL(string: testo).flatMap { Collegamenti.interpreta($0) } }
        XCTAssertEqual(vai("schieraxi://oggi"), .sezione(.formazione), "Oggi è nella Formazione (#673): widget e avvisi vecchi la aprono")
        XCTAssertEqual(vai("schieraxi://formazione"), .sezione(.formazione))
        // Squadra e Altro non sono più schede (#673 passo 3): si aprono le Impostazioni su La mia lega
        XCTAssertEqual(vai("schieraxi://mercato"), .impostazioni(.lega))
        XCTAssertEqual(vai("schieraxi://squadra"), .impostazioni(.lega))
        XCTAssertEqual(vai("schieraxi://altro"), .impostazioni(.lega))
        XCTAssertEqual(vai("schieraxi://scambi"), .impostazioni(.lega))
        XCTAssertEqual(vai("schieraxi://lega"), .impostazioni(.lega))
        XCTAssertEqual(vai("SCHIERAXI://Lega"), .impostazioni(.lega), "maiuscole e minuscole non contano")
        XCTAssertEqual(vai("schieraxi://giocatore/203"), .giocatore(203))
        XCTAssertEqual(vai("schieraxi://impostazioni"), .impostazioni(nil))
        XCTAssertNil(vai("schieraxi://giocatore/abc"))
        XCTAssertNil(vai("schieraxi://giocatore/0"))
        XCTAssertNil(vai("schieraxi://giocatore"))
        XCTAssertNil(vai("schieraxi://boh"))
        XCTAssertNil(vai("https://oggi"))
        // gli schemi dei nomi di prima non si aprono più (scritti a pezzi, vedi NomeVecchioTests)
        XCTAssertNil(vai("fanta" + "claude://formazione"))
        XCTAssertNil(vai("titolar" + "xi://formazione"))
    }

    @MainActor
    func testSezioneDiAvvio() throws {
        let memoria = try XCTUnwrap(UserDefaults(suiteName: "prova-avvio-\(UUID().uuidString)"))
        XCTAssertEqual(Navigazione.sezioneDiAvvio(memoria), .formazione, "senza scelte si parte dalla Formazione, come la web")
        memoria.set("oggi", forKey: "ultimaSezione")
        XCTAssertEqual(Navigazione.sezioneDiAvvio(memoria), .formazione, "chi era su Oggi si ritrova nella Formazione (#673)")
        memoria.set("giornate", forKey: "ultimaSezione")
        XCTAssertEqual(Navigazione.sezioneDiAvvio(memoria), .giornate, "predefinito: l'ultima sezione")
        memoria.set("scambi", forKey: "ultimaSezione")
        XCTAssertEqual(Navigazione.sezioneDiAvvio(memoria), .formazione, "si ricordano solo Formazione e Giornate (#673 passo 3)")
        memoria.set("diario", forKey: "sezioneAvvio")
        XCTAssertEqual(Navigazione.sezioneDiAvvio(memoria), .giornate, "una sezione scelta vince sull'ultima")
        memoria.set("boh", forKey: "sezioneAvvio")
        XCTAssertEqual(Navigazione.sezioneDiAvvio(memoria), .formazione)
    }

    func testColoriESigleDelleSquadre() {
        XCTAssertEqual(ColoriSquadra.sigla("inter"), "INT")
        XCTAssertEqual(ColoriSquadra.sigla("Juventus"), "JUV")
        XCTAssertEqual(ColoriSquadra.sigla("nuovaquadra"), "NUO", "una squadra sconosciuta usa le prime tre lettere")
        XCTAssertEqual(ColoriSquadra.sigla(nil), "")
        XCTAssertEqual(ColoriSquadra.esadecimali("inter").0, "0a58a8")
        XCTAssertEqual(ColoriSquadra.esadecimali("sconosciuta").0, "6b7280", "grigio")
        XCTAssertEqual(ColoriSquadra.tabella.count, ColoriSquadra.sigle.count)
    }
}

final class AvatarTests: XCTestCase {
    func testInizialiDelCognome() {
        XCTAssertEqual(AvatarGiocatore.iniziali("Leonel Marténi"), "MA")
        XCTAssertEqual(AvatarGiocatore.iniziali("Gianni Di Corvara"), "DI")
        XCTAssertEqual(AvatarGiocatore.iniziali("Pelayo"), "PE")
        XCTAssertEqual(AvatarGiocatore.iniziali("Hamit Çalvaroğlu"), "ÇA")
        XCTAssertEqual(AvatarGiocatore.iniziali("N'Dolani"), "ND")
        XCTAssertNil(AvatarGiocatore.iniziali(nil))
        XCTAssertNil(AvatarGiocatore.iniziali("   "))
        XCTAssertNil(AvatarGiocatore.iniziali("12 34"), "senza lettere niente iniziali")
    }
}

final class NomiDatiTests: XCTestCase {
    func testINomiGrezziDiventanoParole() {
        XCTAssertEqual(NomiDati.leggibile("dati-extra"), "Dati extra delle partite")
        XCTAssertEqual(NomiDati.leggibile("crediti-giocatore 2026-10"), "Crediti dei giocatori")
        XCTAssertEqual(NomiDati.leggibile("qualcosa-di_nuovo"), "Qualcosa di nuovo")
        XCTAssertEqual(NomiDati.leggibile(""), "")
        XCTAssertTrue(NomiDati.daNascondere("quote-odds"), "le fonti vecchie non si mostrano")
        XCTAssertFalse(NomiDati.daNascondere("voti"))
    }
}

/// «Da fare» in Oggi (campo `da_fare` di /api/oggi) e i giorni del certificato.
final class DaFareTests: XCTestCase {
    private func oggi(_ daFare: String) throws -> Oggi {
        try Decodifica.decodifica(Data(#"{"giornata": 11, "inizio": "2026-10-31 18:30", "da_fare": \#(daFare)}"#.utf8))
    }

    func testSiLeggeIlContratto() throws {
        let o = try oggi(#"""
        [{"id": "dubbio-5", "tipo": "dubbio", "testo": "Leonel e' in dubbio", "priorita": 1, "azione": "Sostituisci",
          "destinazione": {"scheda": "formazione", "sezione": "formazione", "link": "schieraxi://formazione"}, "giocatore": {"id": 5}},
         {"id": 7, "tipo": "rose", "testo": "Aggiorna le rose", "priorita": 2, "azione": "Aggiorna", "destinazione": {"sezione": "lega"}}]
        """#)
        let c = o.cosePerOrdine
        XCTAssertEqual(c.count, 2)
        XCTAssertEqual(c[0].id, "dubbio-5")
        XCTAssertEqual(c[1].id, "7", "un id numerico si legge come testo")
        XCTAssertEqual(c[0].destinazione?.destinazione, .sezione(.formazione))
        XCTAssertEqual(c[1].destinazione?.destinazione, .impostazioni(.lega), "senza link vale la sezione")
    }

    func testOrdineDiUrgenzaEVociVuote() throws {
        let o = try oggi(#"[{"id": "b", "testo": "B", "priorita": 3}, {"id": "a", "testo": "A", "priorita": 1}, {"id": "c", "testo": "C"}, {"id": "v", "testo": ""}, {"id": "a2", "testo": "A2", "priorita": 1}]"#)
        XCTAssertEqual(o.cosePerOrdine.map(\.id), ["a", "a2", "b", "c"], "per urgenza, a parità l'ordine del server; niente voci senza testo")
    }

    func testUnLinkStranoNonPortaDaNessunaParte() throws {
        let o = try oggi(#"[{"id": "x", "testo": "X", "destinazione": {"link": "https://esempio.invalid", "sezione": "boh"}}]"#)
        XCTAssertNil(o.cosePerOrdine.first?.destinazione?.destinazione)
    }

    func testSenzaIlCampoEUnServerVecchio() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 1}"#.utf8))
        XCTAssertTrue(o.cosePerOrdine.isEmpty)
    }

    func testIGiorniDelCertificato() {
        let adesso = Date(timeIntervalSince1970: 1_800_000_000)
        XCTAssertEqual(Certificato.giorniMancanti(scadenza: adesso.addingTimeInterval(2.5 * 86400), adesso: adesso), 2)
        XCTAssertEqual(Certificato.giorniMancanti(scadenza: adesso.addingTimeInterval(-3600), adesso: adesso), -1, "scaduto da poco: -1")
        XCTAssertEqual(Certificato.giorniMancanti(scadenza: adesso.addingTimeInterval(-3 * 86400), adesso: adesso), -3)
        XCTAssertNil(Certificato.giorniMancanti(scadenza: nil, adesso: adesso))
    }

    func testLIndirizzoDiOggiConIGiorni() {
        XCTAssertEqual(OggiRepository.percorso(giorniCertificato: nil), "/api/oggi")
        XCTAssertEqual(OggiRepository.percorso(giorniCertificato: 6), "/api/oggi?certificato_giorni=6")
        XCTAssertEqual(OggiRepository.percorso(giorniCertificato: -2), "/api/oggi?certificato_giorni=-2")
    }
}

/// Stemma e divisa da un indirizzo web.
@MainActor
final class ImmagineDaIndirizzoTests: XCTestCase {
    func testGliIndirizziAccettabili() {
        XCTAssertEqual(IndirizzoImmagine.pulito("  https://esempio.invalid/stemma.png \n"), "https://esempio.invalid/stemma.png")
        XCTAssertTrue(IndirizzoImmagine.valido("https://cdn.esempio.invalid/a/b.jpg?x=1"))
        XCTAssertFalse(IndirizzoImmagine.valido("http://esempio.invalid/a.png"), "solo https")
        XCTAssertFalse(IndirizzoImmagine.valido("ftp://esempio.invalid/a.png"))
        XCTAssertFalse(IndirizzoImmagine.valido("https://utente:pw@esempio.invalid/a.png"), "niente credenziali dentro l'indirizzo")
        XCTAssertFalse(IndirizzoImmagine.valido("https://localhost/a.png"), "un nome senza punto non e' pubblico")
        XCTAssertFalse(IndirizzoImmagine.valido(""))
        XCTAssertFalse(IndirizzoImmagine.valido("non un indirizzo"))
        XCTAssertFalse(IndirizzoImmagine.valido("https://esempio.invalid/" + String(repeating: "a", count: 2100)))
    }

    func testIlServerRiceveIlCorpoGiusto() async throws {
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "POST", percorso == "/api/squadre/immagine/da-url" { return Data(#"{"ok": true}"#.utf8) }
            if percorso.hasPrefix("/api/squadre/immagini") || percorso.hasPrefix("/api/foto-disponibili") { return Data("{}".utf8) }
            return Data("{}".utf8)
        }
        let immagini = Immagini(server: s)
        try await immagini.inviaDaIndirizzo("https://esempio.invalid/stemma.png", squadra: "Gli Amici", tipo: "stemma")
        let corpo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "/api/squadre/immagine/da-url").first), as: UTF8.self)
        XCTAssertTrue(corpo.contains("\"squadra\":\"Gli Amici\""), corpo)
        XCTAssertTrue(corpo.contains("\"tipo\":\"stemma\""), corpo)
        let letto = try XCTUnwrap(JSONSerialization.jsonObject(with: try XCTUnwrap(s.corpiInviati(a: "/api/squadre/immagine/da-url").first)) as? [String: String])
        XCTAssertEqual(letto["url"], "https://esempio.invalid/stemma.png")
    }

    func testUnIndirizzoSbagliatoNonArrivaAlServer() async {
        let s = ServerDiProva { _, _, _ in Data("{}".utf8) }
        let immagini = Immagini(server: s)
        do {
            try await immagini.inviaDaIndirizzo("http://esempio.invalid/a.png", squadra: "X", tipo: "maglia")
            XCTFail("doveva lanciare")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("https://"))
        }
        XCTAssertEqual(s.quante("da-url"), 0)
    }
}

/// «Apri con SchieraXI» per le immagini: stemma e divisa.
@MainActor
final class ImmagineRicevutaTests: XCTestCase {
    func testQualiFileSonoImmagini() {
        for nome in ["a.png", "b.JPG", "c.jpeg", "d.HEIC", "e.heif", "f.webp"] {
            XCTAssertTrue(Navigazione.eImmagine(URL(fileURLWithPath: "/tmp/" + nome)), nome)
        }
        for nome in ["rose.xlsx", "rose.csv", "testo.txt", "senza-estensione", "film.mov"] {
            XCTAssertFalse(Navigazione.eImmagine(URL(fileURLWithPath: "/tmp/" + nome)), nome)
        }
    }

    func testUnaImmagineNonVaTraLeRose() {
        let nav = Navigazione()
        nav.apriFile(URL(fileURLWithPath: "/tmp/stemma.png"))
        XCTAssertNotNil(nav.immagineRicevuta)
        XCTAssertNil(nav.fileDaImportare, "uno stemma non e' un file delle rose")
        let rose = Navigazione()
        rose.apriFile(URL(fileURLWithPath: "/tmp/rose.xlsx"))
        XCTAssertNil(rose.immagineRicevuta)
        XCTAssertNotNil(rose.fileDaImportare)
    }

    func testUnIndirizzoWebNonEUnFile() {
        let nav = Navigazione()
        nav.apriFile(URL(string: "https://esempio.invalid/stemma.png")!)
        XCTAssertNil(nav.immagineRicevuta)
        XCTAssertNil(nav.fileDaImportare)
    }
}
