import Foundation

// Le risposte del server finto della modalità demo (argomento di lancio `-DEMO`, vedi Demo.swift) e della «Prova con dati di
// esempio»: una lega da 8 squadre, la mia rosa da 25, giornata 11 con partite, avvisi, mercato, scambi, regole, stato dei dati.
// I fatti della lega (calciatori, partite, date, avvisi, Diario, scambio, svincolo, partite in diretta) stanno in `LegaDemo.swift`,
// gli stessi dei widget: qui si costruiscono le risposte dell'app. Le date sono relative ad «adesso»: la prima partita è sempre
// tra qualche ora, così il conto alla rovescia di Oggi si vede anche se lo scatto è fatto un altro giorno.

extension FinteServer {
    /// Server della modalità demo (costruito una volta sola all'avvio).
    static let demo: FinteServer = demoFissata(adesso: Date())

    /// La stessa demo costruita in un istante preciso: i test confrontano app e widget (`LegaDemo.widget`) nello stesso momento.
    static func demoFissata(adesso: Date) -> FinteServer {
        // ricerca, confronto ed elenco dei giocatori dipendono dalla domanda: li calcola `DatiDemo.calcolata`
        FinteServer(risposte: DatiDemo.risposte(adesso: adesso),
                    binari: { DemoImmagini.dati(per: $0) ?? DatiDemo.calcolata($0, adesso: adesso) })
    }

    /// Le fotografie delle fasi della giornata nella Formazione unica (#673: `-DEMO_SCHERMATA formazione-in-corso`,
    /// `formazione-finita`, …): la stessa demo, durante e dopo la giornata, con una partita rinviata o con una tua scelta diversa
    /// dalla consigliata. Ognuna ha il suo indirizzo finto, così la copia salvata non si mescola. I nomi di prima (`oggi-in-corso`,
    /// `oggi-finita`, …) restano come sinonimi: li usano i test che confrontano la demo con il widget. Nil per le altre schermate.
    /// `fissato`: l'istante della demo (solo i test); senza, adesso.
    static func demoFase(_ schermata: String?, adesso fissato: Date? = nil) -> FinteServer? {
        let adesso = fissato ?? Date()
        var server = fissato.map { demoFissata(adesso: $0) } ?? FinteServer.demo
        switch schermata ?? "" {
        case "oggi-in-corso", "formazione-in-corso", "formazione-chiusa":
            // la giornata in corso nel momento della demo (#417, #424): testa, campo chiuso, Rosa e schede raccontano la stessa
            // giornata, con le stesse partite agli stessi orari e la tua scelta salvata
            server.risposte.merge(DatiDemo.risposteInCorso(adesso: adesso)) { _, nuova in nuova }
            server.indirizzoFinto = schermata == "formazione-chiusa" ? "https://finto-formazione-chiusa.invalid"
                                                                     : "https://finto-giornata-in-corso.invalid"
        case "oggi-finita", "formazione-finita":
            server.risposte["/api/oggi"] = DatiDemo.oggiFinita(adesso: adesso)
            if schermata == "formazione-finita", let formazione = server.risposte["/api/formazione"] {
                // a giornata finita il server manda già la formazione della prossima: la testa la scrive sotto «Com'è andata»
                server.risposte["/api/formazione"] = DatiDemo.formazioneDellaProssima(formazione)
            }
            server.indirizzoFinto = "https://finto-giornata-finita.invalid"
        case "formazione-salvata", "formazione-modificata":
            // la tua scelta già salvata: gli 11 della consigliata («È la consigliata.»)
            server.risposte["/api/scelta"] = DatiDemo.sceltaSalvata(adesso: adesso)
            server.risposte["/api/oggi"] = DatiDemo.json(DatiDemo.oggiDati(adesso: adesso, tuaScelta: true))
            server.indirizzoFinto = schermata == "formazione-modificata" ? "https://finto-scelta-modificata.invalid"
                                                                         : "https://finto-scelta-salvata.invalid"
        case "formazione-cambiata":
            // la tua scelta salvata è un altro modulo: «L'hai cambiata tu: N titolari diversi dalla consigliata (… punti attesi).»
            // con «Torna alla consigliata»
            server.risposte["/api/scelta"] = DatiDemo.sceltaCambiata(adesso: adesso)
            server.risposte["/api/oggi"] = DatiDemo.json(DatiDemo.oggiDati(adesso: adesso, tuaScelta: true))
            server.indirizzoFinto = "https://finto-scelta-cambiata.invalid"
        case "oggi-rinvio", "formazione-rinvio":
            server.risposte["/api/oggi"] = DatiDemo.oggiRinvio(adesso: adesso)
            server.indirizzoFinto = "https://finto-partita-rinviata.invalid"
        case "oggi-finita-recupero":
            server.risposte["/api/oggi"] = DatiDemo.oggiFinita(adesso: adesso, recupero: true)
            server.indirizzoFinto = "https://finto-recupero-da-giocare.invalid"
        default:
            return nil
        }
        return server
    }

    /// La fase della giornata in cui vive la demo di una fotografia (`-DEMO_SCHERMATA`): in corso `formazione-in-corso` e
    /// `formazione-chiusa`, finita `formazione-finita` (e i sinonimi di prima), prima della scadenza le altre e la «Prova con dati di
    /// esempio». Serve all'ora dell'app (`Orologio`): a giornata in corso è il momento della demo.
    static func faseDemo(_ schermata: String?) -> LegaDemo.Fase {
        switch schermata ?? "" {
        case "oggi-in-corso", "formazione-in-corso", "formazione-chiusa": return .inCorso
        case "oggi-finita", "oggi-finita-recupero", "formazione-finita": return .finita
        default: return .prima
        }
    }
}

private typealias Calciatore = CalciatoreDemo
/// In questo file `DatiDemo` è la lega della demo vista dall'app: le risposte del server finto.
private typealias DatiDemo = LegaDemo

private extension LegaDemo {

    /// I crediti residui di ogni squadra, gli stessi in Squadre e nella sua rosa: AC Pigra ne ha 22 dopo aver preso Krslić
    /// (Movimenti), Real Madrink 30 come nel conguaglio dello scambio.
    static let creditiSquadre: [String: Int] = [nomeMia: creditiResidui, "Real Madrink": 30, "Atletico Divano": 7, "Dinamo Pizza": 25,
                                                "AC Pigra": 22, "Inter Nos": 63, "Borgo Rossi United": 18,
                                                "Gli Amici del Bar Sport Centrale": 41]

    /// La rosa di una squadra della lega (la mia o un'altra).
    static func giocatoriDi(_ squadra: String) -> [Calciatore] {
        squadra == nomeMia ? miaRosa : (roseAltre[squadra] ?? [])
    }

    // MARK: - Partite

    /// Un giocatore come lo manda il server per formazioni, classifiche e avvisi. `adesso`: l'istante della demo, da cui viene
    /// l'ora della sua partita (la stessa delle partite di Oggi). A giornata in corso (`fase`) la partita e lo stato sono quelli del
    /// momento della demo (`aGiornataIniziata`).
    static func giocatore(_ p: Calciatore, adesso: Date, fase: Fase = .prima, conAvversario: Bool = true,
                          conProprietario: Bool = false) -> [String: Any] {
        var d: [String: Any] = [
            "id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra,
            "p_voto": p.assente ? 0.0 : p.pVoto,
            "punti_attesi": p.puntiAttesi,
            "gol_attesi": golAttesi(p),
            "assist_attesi": assistAttesi(p),
        ]
        d["fv_atteso"] = p.fvAtteso
        d["voto_atteso"] = p.votoAtteso
        d["porta_inviolata"] = p.ruolo == "P" ? 0.34 : 0.0
        d["p_gol"] = min(0.6, golAttesi(p) * 0.85)
        d["p_assist"] = min(0.4, assistAttesi(p) * 0.9)
        d["p_giallo"] = 0.11
        d["p_rosso"] = 0.01
        d["quota_titolare"] = p.assente ? 0.0 : p.pVoto
        d["indice"] = p.assente ? 0 : min(100, max(1, Int(((p.punti - 4.6) / 3.4 * 100).rounded())))
        d["difficolta"] = difficolta(di: p.squadra)
        d["gol_squadra"] = 1.8
        d["gol_avversario"] = 1.2
        if let data = dataPartita(di: p.squadra, adesso: adesso, fase: fase) { d["data_partita"] = data }
        // titolarità: come nelle probabili formazioni (stato e percentuale come nel riassunto dei widget, `CalciatoreDemo`)
        d["stato"] = p.statoProbabili
        d["percentuale"] = p.percentualeProbabili
        if p.assente {
            d["titolarita"] = "fuori"; d["motivi"] = ["infortunato"]
        } else if p.dubbio {
            // in dubbio: la probabilità delle probabili è la stessa di «gioca N%» (una sola percentuale, coerente ovunque).
            // Come il server: il motivo della titolarità e l'etichetta pronta «In dubbio · gioca N%» (`fanta/etichette.py`).
            d["titolarita"] = "ballottaggio"; d["motivi"] = ["titolare in ballottaggio"]
            d["etichetta"] = ["codice": "in_dubbio", "testo": DubbioRiassunto.inDubbio(p.pVoto), "tono": "attenzione"]
        } else if p.pVoto < 0.75 {
            d["titolarita"] = "improbabile"; d["motivi"] = ["parte dalla panchina"]
        } else {
            d["titolarita"] = "titolare"; d["motivi"] = ["titolare"]
        }
        d["quotazione"] = quotazione(p)
        if conAvversario, let a = avversario(di: p.squadra) {
            d["avversario"] = a.nome
            d["in_casa"] = a.inCasa
        }
        if p.dubbio { d["dubbio"] = true }
        if p.diffidato { d["diffidato"] = true }
        if p.assente { d["assente"] = true }
        if conProprietario, let o = fantasquadra(di: p.id) { d["proprietario"] = o }
        if !p.assente { perche(p, in: &d) }
        if fase == .inCorso { aGiornataIniziata(p, in: &d) }
        return d
    }

    /// Dopo la scadenza, come `schede_a_giornata_iniziata` di fanta/fasi.py (#424): niente più titolarità delle probabili (resta
    /// «fuori» chi è indisponibile, finché i voti non dicono com'è andata) né i loro motivi; lo stato vero della sua giornata
    /// (`stato_partita`), il fantavoto preso solo con «fatto» (`fv_preso`) e l'etichetta che ne viene, come `fanta/etichette.py`.
    static func aGiornataIniziata(_ p: Calciatore, in d: inout [String: Any]) {
        let s = statoInCorso(p)
        let fuori = p.assente && s.stato != "fatto" && s.stato != "senza_voto"
        d["titolarita"] = fuori ? "fuori" as Any : NSNull() as Any
        let probabili = ["titolare", "parte dalla panchina", "non tra i convocati previsti"]   // _MOTIVI_PROBABILI del server
        d["motivi"] = ((d["motivi"] as? [String]) ?? []).filter { m in !probabili.contains { m.hasPrefix($0) } }
        d["stato_partita"] = s.stato
        d["fv_preso"] = s.fv.map { $0 as Any } ?? NSNull()
        d["etichetta"] = etichettaIniziata(stato: s.stato, fuori: fuori, statoProbabili: p.statoProbabili)
    }

    /// L'etichetta a giornata iniziata (`codice` e `CODICI` di fanta/etichette.py): lo stato della partita; chi è fuori e non ha
    /// ancora un esito resta «Infortunato» (o «Squalificato», «Fuori»).
    static func etichettaIniziata(stato: String, fuori: Bool, statoProbabili: String) -> [String: Any] {
        let codici: [String: (codice: String, testo: String, tono: String)] = [
            "fatto": ("voto", "Ha giocato", "positivo"), "senza_voto": ("senza_voto", "Senza voto", "attenzione"),
            "attesa_voti": ("voto_in_arrivo", "Voto in arrivo", "neutro"), "in_corso": ("in_corso", "Partita in corso", "positivo"),
            "da_giocare": ("da_giocare", "Da giocare", "neutro"),
        ]
        if fuori {
            switch statoProbabili {
            case "infortunato": return ["codice": "infortunato", "testo": "Infortunato", "tono": "negativo"]
            case "squalificato": return ["codice": "squalificato", "testo": "Squalificato", "tono": "negativo"]
            default: return ["codice": "fuori", "testo": "Fuori", "tono": "negativo"]
            }
        }
        let e = codici[stato] ?? ("da_giocare", "Da giocare", "neutro")
        return ["codice": e.codice, "testo": e.testo, "tono": e.tono]
    }

    /// «Perché questo numero» come lo manda il server (`perche_numero`, `fv_atteso_medio_ruolo`): stesse frasi del server,
    /// effetti in fantavoti rispetto al giocatore medio del ruolo, al massimo tre motivi.
    static func perche(_ p: Calciatore, in d: inout [String: Any]) {
        let fv = p.fvAtteso
        let medio = ["P": 6.0, "D": 6.1, "C": 6.4, "A": 7.0][p.ruolo] ?? 6.3
        let casa = avversario(di: p.squadra)?.inCasa ?? true
        let partita = Double(3 - difficolta(di: p.squadra)) * 0.15
        let resto = fv - medio - partita
        let arrotonda: (Double) -> Double = { ($0 * 100).rounded() / 100 }
        var numerici: [(String, String, Double)] = [
            ("partita", partita > 0 ? (casa ? "partita favorevole in casa" : "partita favorevole in trasferta")
                                    : (casa ? "partita difficile in casa" : "partita difficile in trasferta"), partita),
            ("voti", resto > 0 ? "voti sopra la media del ruolo" : "voti sotto la media del ruolo", resto * 0.4),
        ]
        if p.ruolo == "P" {
            numerici.append(("porta", resto > 0 ? "buone chance di porta inviolata (34%)" : "poche chance di porta inviolata (34%)", resto * 0.6))
        } else {
            let pGol = Int((min(0.6, golAttesi(p) * 0.85) * 100).rounded())
            numerici.append(("gol", resto > 0 ? "segna più della media del ruolo (\(pGol)% di segnare)" : "segna meno della media del ruolo", resto * 0.6))
        }
        var motivi: [[String: Any]] = []
        if p.dubbio {
            motivi.append(["chiave": "gioca", "testo": "gioca il \(Int((p.pVoto * 100).rounded()))%: dubbio", "effetto": NSNull()])
        } else if p.pVoto < 0.8 {
            let pct = Int((p.pVoto * 100).rounded())
            motivi.append(["chiave": "gioca", "testo": "gioca il \(pct)%: " + (p.pVoto < 0.5 ? "probabile panchina" : "dubbio"), "effetto": NSNull()])
        }
        let scelti = numerici.filter { abs($0.2) >= 0.08 }.sorted { abs($0.2) > abs($1.2) }.prefix(3 - motivi.count)
        motivi += scelti.map { t -> [String: Any] in ["chiave": t.0, "testo": t.1, "effetto": arrotonda(t.2)] }
        d["perche_numero"] = motivi
        d["fv_atteso_medio_ruolo"] = medio
    }

    static func golAttesi(_ p: Calciatore) -> Double { p.golAttesi }

    static func assistAttesi(_ p: Calciatore) -> Double { p.assistAttesi }

    /// Giocatore breve (scambi e mercato).
    static func breve(_ id: Int) -> [String: Any] {
        let p = calciatore(id)
        return ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra, "quotazione": quotazione(p)]
    }

    static func rigaRosa(_ p: Calciatore, adesso: Date, fase: Fase = .prima) -> [String: Any] {
        ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra, "squadra_slug": p.squadra,
         "costo": costo(p), "quotazione": quotazione(p), "previsione": giocatore(p, adesso: adesso, fase: fase)]
    }

    static func schedaGiocatore(_ p: Calciatore, adesso: Date, fase: Fase = .prima) -> [String: Any] {
        let presenze: Int = 7 + p.id % 4
        let media: Double = 5.7 + p.punti / 12.0
        let q: Int = quotazione(p)
        var gol: Int = p.id % 2
        if p.ruolo == "A" { gol = 3 + p.id % 4 }
        if p.ruolo == "C" { gol = 1 + p.id % 3 }
        let assist: Int = p.ruolo == "P" ? 0 : p.id % 4
        let espulsioni: Int = p.id % 11 == 0 ? 1 : 0

        var anagrafica: [String: Any] = ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra.uppercased(), "squadra_slug": p.squadra]
        anagrafica["quotazione"] = q
        anagrafica["quotazione_iniziale"] = q - 1
        anagrafica["fvm"] = q * 3 / 2

        var stagione: [String: Any] = ["presenze": presenze, "con_voto": presenze - 1, "giornate_giocate_serie_a": 10,
                                       "gol_subiti": p.ruolo == "P" ? 9 : 0, "rig_segnati": 0, "rig_parati": p.ruolo == "P" ? 1 : 0]
        stagione["media_voto"] = media
        stagione["fantamedia"] = media + p.punti / 25.0
        stagione["gol"] = gol
        stagione["assist"] = assist
        stagione["ammonizioni"] = p.id % 3
        stagione["espulsioni"] = espulsioni

        var d: [String: Any] = [:]
        d["calciatore"] = anagrafica
        d["stagione"] = stagione
        var previsione = giocatore(p, adesso: adesso, fase: fase)
        // come il server: la giornata di Serie A e, accanto, quella della lega (la scheda mostra «Giornata 8», come Oggi)
        previsione["giornata"] = giornata
        previsione["giornata_lega"] = giornataLega   // come il server: la scheda dice «Giornata 8 · 11ª di Serie A»
        d["previsione"] = previsione
        d["voti"] = voti(p)
        d["avanzate"] = ["minuti": 560 + p.id % 200, "xg": 3.4 + Double(p.id % 5) * 0.7, "xa": 1.2 + Double(p.id % 3) * 0.4, "tiri": 22 + p.id % 9,
                         "passaggi_chiave": 9 + p.id % 7, "rigori_calciati": p.id % 4 == 0 ? 2 : 0, "punizioni": p.id % 5 == 0 ? 3 : 0,
                         "per_90": ["xg": 0.52, "xa": 0.18, "tiri": 3.1],
                         "stagioni_precedenti": [["stagione": "2025-26", "minuti": 2400, "gol": 11, "xg": 10.2, "assist": 4, "xa": 3.6]]] as [String: Any]
        d["rendimento"] = ["sovra_rendimento": p.id % 2 == 0 ? 0.42 : -0.38, "gol_meno_xg": p.id % 2 == 0 ? 0.9 : -1.1, "assist_meno_xa": 0.2] as [String: Any]
        if let o = fantasquadra(di: p.id) { d["proprietario"] = o }
        return d
    }

    /// Voti e fantavoti delle ultime giornate: qualcuna senza voto (partita saltata), per vedere anche i «sv» nel grafico.
    static func voti(_ p: Calciatore) -> [[String: Any]] {
        var elenco: [[String: Any]] = []
        for (k, g) in [3, 4, 5, 6, 7, 8, 9, 10].enumerated() {
            if (p.id + k) % 7 == 0 { elenco.append(["giornata": g]); continue }
            let voto = 5.5 + Double((p.id * (k + 3)) % 15) / 10.0
            let bonus = p.ruolo == "A" && (p.id + k) % 3 == 0 ? 3.0 : (k % 4 == 0 ? 1.0 : 0.0)
            elenco.append(["giornata": g, "voto": voto, "fv": voto + bonus - (k % 5 == 0 ? 0.5 : 0), "gol": bonus >= 3 ? 1 : 0, "assist": 0])
        }
        return elenco
    }

    // MARK: - Formazione

    /// La Formazione (`GET /api/formazione`). A giornata in corso (`fase`) è chiusa (`iniziata`), nel momento della demo: ogni
    /// giocatore con la sua partita e il suo stato, come Oggi in corso (#424), e la tua scelta che vale.
    static func formazione(fase: Fase = .prima, adesso: Date) -> String {
        let iniziata = fase == .inCorso
        let base = moduli[0]
        let ids = base.titolari
        let bench = panchina(per: ids)
        let titolari = ids.map { giocatore(calciatore($0), adesso: adesso, fase: fase) }
        let panchinaJSON = bench.map { giocatore(calciatore($0), adesso: adesso, fase: fase) }
        // i punti della consigliata: la stessa fonte di Oggi, della valutazione e dei widget (#390)
        let attesi = attesiGiornata
        // gli stili come li manda ancora il server (LIVELLI_RISCHIO): Sicura, Equilibrata (la consigliata, l'unica che l'app mostra,
        // #634), Rischiosa
        let nomiStili = [-1: "Sicura", 0: "Equilibrata", 1: "Rischiosa"]
        var livelli: [[String: Any]] = []
        for r in [-1, 0, 1] {
            let nome = nomiStili[r] ?? ""
            let extra = Double(r) * 0.6
            var elenco: [[String: Any]] = []
            for m in moduli {
                let punti = (m.nome == base.nome ? attesi : punteggio(m.titolari)) + extra
                elenco.append(["modulo": m.nome, "punteggio_atteso": punti, "titolari": m.titolari, "panchina": panchina(per: m.titolari),
                               "dev": 4.2, "intervallo": fascia(punti)])
            }
            livelli.append(["rischio": r, "stile": r, "nome": nome,
                            "modulo": base.nome, "punteggio_atteso": attesi + extra, "moduli": elenco,
                            "intervallo": fascia(attesi + extra)])
        }
        var schede: [String: Any] = [:]
        for p in miaRosa { schede[String(p.id)] = giocatore(p, adesso: adesso, fase: fase) }
        // probabili uscite, come in Oggi, nel widget e nello Stato dei dati (prima diceva «non ancora uscite», #303)
        var f: [String: Any] = [
            "squadra": nomeMia, "giornata": giornata, "giornata_lega": giornataLega, "modulo": base.nome, "punteggio_atteso": attesi,
            "con_probabili": true, "titolari": titolari, "panchina": panchinaJSON, "livelli": livelli, "schede": schede, "stile_consigliato": 0,
            "dev": 4.2, "intervallo": fascia(attesi), "iniziata": iniziata,
        ]
        // a giornata chiusa il server dice se la tua scelta salvata si può schierare: sì (gli undici della consigliata)
        if iniziata { f["stato_scelta"] = tuaScelta(fase) ? "valida" : "nessuna" }
        return json(f)
    }

    /// La scelta salvata della giornata (gli undici del primo modulo), salvata un'ora prima di `adesso` (ora italiana, come il
    /// server). A giornata in corso `adesso` è la scadenza: la scelta è di prima che la formazione si chiudesse.
    static func sceltaSalvata(adesso: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return json(["titolari": moduli[0].titolari, "modulo": moduli[0].nome, "salvata": f.string(from: adesso.addingTimeInterval(-3600)),
                     "tipo": "manuale"])
    }

    /// La formazione della giornata dopo (foto `formazione-finita`), come la manda il server a giornata finita: la stessa consigliata
    /// con i numeri della prossima giornata, quelli di `prossima` di Oggi.
    static func formazioneDellaProssima(_ testo: String) -> String {
        guard var f = (try? JSONSerialization.jsonObject(with: Data(testo.utf8))) as? [String: Any] else { return testo }
        f["giornata"] = giornata + 1
        f["giornata_lega"] = giornataLega + 1
        return json(f)
    }

    /// La scelta salvata diversa dalla consigliata (foto `formazione-cambiata`): gli 11 del secondo modulo, salvati un'ora prima.
    static func sceltaCambiata(adesso: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        let modulo = moduli.count > 1 ? moduli[1] : moduli[0]
        return json(["titolari": modulo.titolari, "modulo": modulo.nome, "salvata": f.string(from: adesso.addingTimeInterval(-3600)),
                     "tipo": "manuale"])
    }

    /// La valutazione di una formazione (`POST /api/formazione/valuta`), come `valuta` di fanta/consigli.py. Il server finto non
    /// legge il corpo della domanda: risponde per gli undici della consigliata, che sono la scelta salvata della demo
    /// (`sceltaSalvata`) e quelli da cui parte «Modifica a mano». Quindi gli stessi punti attesi della consigliata e differenza zero,
    /// gli stessi di Oggi (#390).
    static func valutazione() -> String { json(valutazioneScelta) }

    static var valutazioneScelta: [String: Any] {
        // la valutazione e la consigliata sono gli stessi undici: un numero solo, `attesiGiornata`
        let attesi = attesiGiornata
        let f = fascia(attesi)
        return ["modulo": moduli[0].nome, "giornata": giornata, "giornata_lega": giornataLega, "punteggio_atteso": attesi,
                "dev": 4.2, "intervallo": f, "brutta_giornata": f["basso"] ?? NSNull(), "giornata_eccezionale": f["alto"] ?? NSNull(),
                "panchina": panchina(per: moduli[0].titolari), "consigliata_stesso_modulo": attesi, "differenza": 0.0, "consigliata": attesi]
    }

    // MARK: - Oggi

    static func oggi(adesso: Date) -> String { json(oggiDati(adesso: adesso)) }

    /// Oggi prima della scadenza. `tuaScelta`: c'è la tua formazione salvata (di norma no, come la Formazione: #418).
    static func oggiDati(adesso: Date, tuaScelta: Bool = LegaDemo.tuaScelta(.prima)) -> [String: Any] {
        let primaPartita = inizio(adesso: adesso)
        let ids = moduli[0].titolari
        // gli orari delle partite e gli avvisi: gli stessi del widget (`LegaDemo`)
        var partite: [[String: Any]] = []
        for (i, ora) in orari(adesso: adesso).enumerated() {
            partite.append(["data": formatta(ora, "yyyy-MM-dd HH:mm"),
                            "casa": incontri[i].casa, "trasferta": incontri[i].trasferta, "giocata": false])
        }
        let avvisi = avvisiOggi()
        // come `migliori` di fanta/gestione.py: i 3 titolari con più punti attesi
        let migliori = ids.map { calciatore($0) }.sorted { $0.puntiAttesi > $1.puntiAttesi }.prefix(3).map { giocatore($0, adesso: adesso) }
        var mieiTitolari: [String: [[String: Any]]] = [:]
        for id in ids {
            let c = calciatore(id)
            mieiTitolari[c.squadra, default: []].append(["id": c.id, "nome": c.nome, "ruolo": c.ruolo])
        }
        // come il server: con una scelta salvata modulo, punti e fascia della sua valutazione (`valutazioneScelta`), altrimenti
        // quelli della consigliata. Sono gli stessi undici: lo stesso numero della Formazione in tutti e due i casi (#390)
        let consigliata: [String: Any] = ["punteggio_atteso": attesiGiornata, "dev": 4.2, "intervallo": fascia(attesiGiornata)]
        let scelta = tuaScelta ? valutazioneScelta : consigliata
        let bloccoFormazione: [String: Any] = ["modulo": moduli[0].nome, "squadra": nomeMia, "tua_scelta": tuaScelta,
                                               "punteggio_atteso": scelta["punteggio_atteso"] ?? NSNull(), "dev": scelta["dev"] ?? NSNull(),
                                               "intervallo": scelta["intervallo"] ?? NSNull()]
        return [
            "miei_titolari": mieiTitolari, "fase": "prima",
            "giornata": giornata, "inizio": formatta(primaPartita, "yyyy-MM-dd HH:mm"),
            "scadenza": formatta(scadenza(adesso: adesso), "yyyy-MM-dd HH:mm"), "minuti_scadenza": minutiScadenza, "giornata_lega": giornataLega,
            "iniziata": false, "con_probabili": true,
            "probabili": probabili(adesso: adesso, scadenza: scadenza(adesso: adesso)),
            "formazione": bloccoFormazione,
            "avvisi": avvisi, "migliori": migliori, "partite": partite,
            "da_fare": [voceDubbio, voceSvincolato, voceRoseVecchie, voceDiario, voceBackup],
        ]
    }

    // MARK: - Probabili

    /// Quando sono state lette le probabili della giornata: otto ore fa, ai cinque minuti. La stessa ora in Oggi e nello Stato dei
    /// dati (#390); otto ore bastano per l'avviso delle probabili vecchie.
    static func probabiliLette(adesso: Date) -> Date {
        let cinqueMinuti = 5.0 * 60
        let prima = adesso.addingTimeInterval(-8 * 3600).timeIntervalSinceReferenceDate
        return Date(timeIntervalSinceReferenceDate: (prima / cinqueMinuti).rounded(.down) * cinqueMinuti)
    }

    /// Il campo `probabili` di Oggi come `freschezza_probabili` di fanta/gestione.py, con le frasi del server (`probabili.*` e
    /// `tempo.*` di fanta/frasi.py): l'ora della lettura, quanto tempo fa e, se sono lette da almeno 6 ore con la formazione che si
    /// chiude entro un giorno, l'avviso. Tutto da `adesso`, così «alle 17:05 · 8 ore fa» torna con l'ora del telefono.
    static func probabili(adesso: Date, scadenza: Date) -> [String: Any] {
        let lette = probabiliLette(adesso: adesso)
        let minuti = max(0, Int((adesso.timeIntervalSince(lette) / 60).rounded(.down)))
        let roma = oraItaliana
        let giorni = roma.dateComponents([.day], from: roma.startOfDay(for: lette), to: roma.startOfDay(for: adesso)).day ?? 0
        let ora = formatta(lette, "HH:mm")
        let testo = switch giorni {
        case ..<1: "Probabili aggiornate alle \(ora)"
        case 1: "Probabili aggiornate ieri alle \(ora)"
        default: "Probabili aggiornate il \(roma.component(.day, from: lette))/\(roma.component(.month, from: lette)) alle \(ora)"
        }
        // le ore alla scadenza a un decimale, come `_tempi` del server
        let oreMancanti = (scadenza.timeIntervalSince(adesso) / 360).rounded() / 10
        let vecchie = oreMancanti > 0 && oreMancanti <= 24 && minuti >= 6 * 60
        let eta = tempoFa(minuti)
        var d: [String: Any] = ["aggiornate_il": formatta(lette, "yyyy-MM-dd HH:mm"), "minuti_fa": minuti, "eta": eta, "testo": testo,
                                "vecchie": vecchie, "avviso": NSNull()]
        if vecchie {
            let n = max(1, Int(oreMancanti.rounded(.toNearestOrEven)))
            d["avviso"] = "Le ho lette \(eta) e la formazione si chiude tra \(n == 1 ? "1 ora" : "\(n) ore"): potrebbero essere cambiate, ricontrolla prima."
        }
        return d
    }

    /// «8 ore fa», «1 minuto fa», come `_eta_testo` di fanta/gestione.py.
    static func tempoFa(_ minuti: Int) -> String {
        if minuti < 1 { return "meno di un minuto fa" }
        if minuti < 60 { return minuti == 1 ? "1 minuto fa" : "\(minuti) minuti fa" }
        let ore = minuti / 60
        if ore < 48 { return ore == 1 ? "1 ora fa" : "\(ore) ore fa" }
        let giorni = ore / 24
        return giorni == 1 ? "1 giorno fa" : "\(giorni) giorni fa"
    }

    // MARK: - «Da fare» come lo scrive il server
    // Testi e pulsanti sono quelli di `fanta/frasi.py` (chiavi `dafare.*`), riempiti con i dati della demo;
    // `DemoDaFareTests` li confronta con il catalogo del server.

    /// I bonus delle regole della demo (`bonus` di `/api/regole`).
    static let bonus = (gol: 3.0, assist: 1.0, rigoreSegnato: 3.0, rigoreSbagliato: -3.0, golSubito: -1.0, imbattuto: 1.0)
    /// Quante sostituzioni ammette la lega della demo (`panchina.max_sostituzioni` delle regole).
    static let maxSostituzioni = 5

    /// Chi schierare tra due giocatori, come `da_schierare` di fanta/consigli.py: se la formazione del sistema (`titolari`; nil = non
    /// si sa) ne schiera uno solo è lui, anche con meno punti attesi da solo; altrimenti chi ha più punti attesi (#305).
    static func daSchierare(_ a: Calciatore, _ b: Calciatore, titolari: [Int]?) -> Calciatore {
        if let titolari {
            let dentro = [a, b].filter { titolari.contains($0.id) }
            if dentro.count == 1, let solo = dentro.first { return solo }
        }
        return a.puntiAttesi >= b.puntiAttesi ? a : b
    }

    /// Marténi, titolare in dubbio, come `_dubbi` di fanta/da_fare.py (#268): il cambio («Meglio Y», «Sostituisci») si propone solo
    /// se la consigliata lo fa (`daSchierare`); se la consigliata tiene il titolare, la voce dice chi entra dalla panchina se lui
    /// non gioca (la prima riserva del suo ruolo) e apre la formazione. Nella demo la consigliata tiene Marténi (#305). La
    /// percentuale è il suo «gioca».
    static var voceDubbio: [String: Any] {
        let x = calciatore(120)
        let titolari = moduli[0].titolari
        let p = Int((x.pVoto * 100).rounded(.toNearestOrEven))
        func persona(_ c: Calciatore) -> [String: Any] { ["id": c.id, "nome": c.nome] }
        let versoFormazione: [String: Any] = ["scheda": "formazione", "sezione": NSNull(), "link": "schieraxi://formazione"]
        var voce: [String: Any] = ["id": "dubbio:\(x.id)", "tipo": "dubbio", "priorita": 2, "giocatore": persona(x),
                                   "azione": "Apri la formazione", "destinazione": versoFormazione]
        // il candidato: il libero del suo ruolo con più punti attesi (la consigliata è la formazione stessa: non schiera nessun altro
        // al suo posto); il cambio solo se la regola del confronto sceglie lui
        let candidati = miaRosa.filter { !titolari.contains($0.id) && $0.ruolo == x.ruolo && !$0.assente }
        if let alt = candidati.max(by: { $0.puntiAttesi < $1.puntiAttesi }), daSchierare(x, alt, titolari: titolari).id == alt.id {
            voce["testo"] = "\(x.nome) è in dubbio (\(p)% di giocare). Meglio \(alt.nome)."
            voce["alternativa"] = ["id": alt.id, "nome": alt.nome, "ruolo": alt.ruolo, "punti_attesi": alt.puntiAttesi]
            voce["azione"] = "Sostituisci"
            voce["decisione"] = 1           // un cambio da fare: la prima decisione, come `segna_decisioni` del server (#673)
            voce["destinazione"] = ["scheda": "formazione", "sezione": NSNull(), "link": "schieraxi://giocatore/\(x.id)", "giocatore": x.id]
        } else if maxSostituzioni > 0,
                  let riserva = panchina(per: titolari).map({ calciatore($0) }).first(where: { $0.ruolo == x.ruolo && !$0.assente }) {
            voce["testo"] = "\(x.nome) è in dubbio (\(p)% di giocare) ma resta titolare: se non gioca entra \(riserva.nome) dalla panchina."
            voce["riserva"] = persona(riserva)
        } else {
            voce["testo"] = "\(x.nome) è in dubbio (\(p)% di giocare)."
        }
        return voce
    }

    /// Il consiglio del cambio con uno svincolato, che il server manda ancora (Retalli, libero, al posto di Vlasenić, 3,4 punti in
    /// più): dal 12/11/2026 (#634) l'app non lo mostra. Resta per provarlo.
    static var voceSvincolato: [String: Any] {
        let v = svincoloMigliore
        return ["id": "svincolato-\(v.entra)", "tipo": "svincolato",
                "testo": "\(calciatore(v.entra).nome) (libero) al posto di \(calciatore(v.esce).nome): circa \(Formato.punti(v.guadagno)) punti in più.",
                "priorita": 2, "azione": "Vedi", "destinazione": ["sezione": "mercato", "link": "schieraxi://mercato"]]
    }

    /// Rose ferme da 5 giorni dopo una giornata giocata: una decisione in cima alla Formazione (`decisione`, #673), dopo il cambio
    /// del titolare in dubbio se la demo lo propone.
    static var voceRoseVecchie: [String: Any] {
        ["id": "rose", "tipo": "rose", "testo": "Le rose non sono aggiornate da 5 giorni e nel frattempo si è giocata una giornata.",
         "priorita": 2, "azione": "Aggiorna le rose", "destinazione": ["sezione": "lega", "link": "schieraxi://lega"],
         "decisione": voceDubbio["alternativa"] == nil ? 1 : 2]
    }

    /// L'ultima giornata finita con i due numeri, come il server dalla #299 («Giornata 7 · 10ª di Serie A: è finita, …»), mentre
    /// `id`, `giornata` e `destinazione.giornata` sono i numeri della Serie A (la 10), come in `_diario` di `fanta/da_fare.py`.
    static var voceDiario: [String: Any] {
        let serieA = giornata - 1
        let lega = (giornata - 3) - 1
        let nome = TempiLega.etichetta(serieA: serieA, lega: lega)
        return ["id": "diario:\(serieA)", "tipo": "diario", "testo": "\(nome): è finita, dimmi se hai schierato la consigliata.",
                "priorita": 3, "azione": "Ho schierato la consigliata",
                "destinazione": ["scheda": "lega", "sezione": "diario", "link": "schieraxi://lega/diario", "giornata": serieA] as [String: Any],
                "giornata": serieA]
    }

    /// Una voce che il server non manda più: l'app la nasconde (la copia di sicurezza non si fa dall'app). Resta per provarlo.
    static var voceBackup: [String: Any] {
        ["id": "backup", "tipo": "backup", "testo": "Fai una copia di sicurezza dei tuoi dati", "priorita": 3,
         "azione": "Apri", "destinazione": ["sezione": "lega", "link": "schieraxi://lega"]]
    }

    // MARK: - Oggi durante e dopo la giornata (fotografie `oggi-in-corso` e `oggi-finita`)

    /// Fase `in_corso`, nel momento della demo (`LegaDemo.momento`, alle 18:48 ora italiana, #417): la formazione si è chiusa la
    /// sera prima, 10 minuti prima di Inter-Roma, finita con i voti; Milan-Juventus e Lazio-Fiorentina in corso, il resto da giocare.
    /// Un cambio già fatto (Bastrani senza voto, entra Dimarzi) e due probabili. Orari e numeri sono quelli del widget
    /// (`LegaDemo.bloccoInCorso`).
    static func oggiInCorso(adesso: Date) -> String {
        let adesso = momento(adesso: adesso, fase: .inCorso)
        var o = oggiDati(adesso: adesso, tuaScelta: tuaScelta(.inCorso))
        let stati = ["finita", "in_corso", "da_giocare", "in_corso", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "da_giocare"]
        // Inter-Roma è finita la sera prima: il calendario ha già il risultato (2-1, lo stesso della diretta), che si vede anche con
        // «Risultati in diretta» spenta, come sulla web; le altre senza (`gol_casa` e `gol_trasferta` null, come il server)
        o["partite"] = orari(adesso: adesso, fase: .inCorso).enumerated().map { i, ora -> [String: Any] in
            var p: [String: Any] = ["data": formatta(ora, "yyyy-MM-dd HH:mm"), "casa": incontri[i].casa, "trasferta": incontri[i].trasferta,
                                    "giocata": i == 0, "stato": stati[i], "gol_casa": NSNull(), "gol_trasferta": NSNull()]
            if i == 0 {
                p["gol_casa"] = 2
                p["gol_trasferta"] = 1
            }
            return p
        }
        o["fase"] = "in_corso"
        o["iniziata"] = true
        o["inizio"] = formatta(inizio(adesso: adesso, fase: .inCorso), "yyyy-MM-dd HH:mm")
        o["scadenza"] = formatta(scadenza(adesso: adesso, fase: .inCorso), "yyyy-MM-dd HH:mm")
        // le stesse probabili, ma la formazione è già chiusa: niente avviso (come il server)
        o["probabili"] = probabili(adesso: adesso, scadenza: scadenza(adesso: adesso, fase: .inCorso))
        o["da_fare"] = [[String: Any]]()
        o["in_corso"] = bloccoInCorso(adesso: adesso)
        return json(o)
    }

    /// Le risposte della giornata in corso, nel momento della demo, per le fotografie `oggi-in-corso` e `formazione-chiusa` (#424):
    /// Oggi e risultati in diretta, la Formazione chiusa con la tua scelta salvata un'ora prima della scadenza, le rose e le schede.
    /// Ogni giocatore ha la partita e lo stato della sua giornata come in Oggi (`LegaDemo.statoInCorso`).
    static func risposteInCorso(adesso: Date) -> [String: String] {
        let m = momento(adesso: adesso, fase: .inCorso)
        let mia = rosa(nomeMia, mia: true, adesso: m, fase: .inCorso)
        var r: [String: String] = [
            "/api/oggi": oggiInCorso(adesso: m),
            "/api/formazione": formazione(fase: .inCorso, adesso: m),
            "/api/scelta": sceltaSalvata(adesso: scadenza(adesso: m, fase: .inCorso)),
            "/api/rosa": mia,
        ]
        r["/api/rosa?squadra=" + IndirizzoServer.codifica(nomeMia)] = mia
        for nome in altreSquadre {
            r["/api/rosa?squadra=" + IndirizzoServer.codifica(nome)] = rosa(nome, mia: false, adesso: m, fase: .inCorso)
        }
        for p in tutti { r["/api/giocatore/\(p.id)"] = json(schedaGiocatore(p, adesso: m, fase: .inCorso)) }
        r["/api/giocatore/"] = json(schedaGiocatore(calciatore(203), adesso: m, fase: .inCorso))
        return r
    }

    // MARK: - Partite rinviate (fotografie `oggi-rinvio` e `oggi-finita-recupero`)

    /// La scelta «per questa giornata» della demo: la lega aspetta il recupero.
    static func sceltaRinvio(giornata g: Int, partite: [[String: Any]] = [], miei: [[String: Any]] = []) -> [String: Any] {
        ["stagione": "2026-27", "giornata": g, "giornata_lega": g - 3, "modo": "aspetta", "valore": NSNull(), "predefinito": "aspetta",
         "eccezione": false, "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6, "partite": partite, "miei": miei]
    }

    /// Oggi prima della scadenza con l'ultima partita del turno rinviata a un recupero fra un paio di settimane, alle 20:45
    /// (`dataRecupero`): il riquadro «Partita rinviata».
    static func oggiRinvio(adesso: Date) -> String {
        var o = oggiDati(adesso: adesso)
        var partite = (o["partite"] as? [[String: Any]]) ?? []
        guard let ultima = incontri.last, !partite.isEmpty else { return json(o) }
        let recupero = formatta(dataRecupero(adesso: adesso, fase: .prima), "yyyy-MM-dd HH:mm")
        partite[partite.count - 1]["data"] = recupero
        partite[partite.count - 1]["stato"] = "rinviata"
        o["partite"] = partite
        let miei = moduli[0].titolari.map { calciatore($0) }.filter { [ultima.casa, ultima.trasferta].contains($0.squadra) }
            .map { ["id": $0.id, "nome": $0.nome, "ruolo": $0.ruolo, "squadra": $0.squadra] as [String: Any] }
        o["rinvio"] = sceltaRinvio(giornata: giornata, partite: [["casa": ultima.casa, "trasferta": ultima.trasferta, "data": recupero]],
                                   miei: miei)
        return json(o)
    }

    /// Fase `finita`: la giornata 11 è finita, Oggi parla già della 12 (si chiude fra 4 giorni, probabili non ancora uscite).
    /// Riepilogo e prossima giornata sono quelli del widget (`LegaDemo.riepilogoFinita`, `prossimaDopoFinita`).
    static func oggiFinita(adesso: Date, recupero: Bool = false) -> String {
        var o = oggiDati(adesso: adesso, tuaScelta: tuaScelta(.finita))
        func data(_ d: Date) -> String { formatta(d, "yyyy-MM-dd HH:mm") }
        o["partite"] = orari(adesso: adesso, fase: .finita).enumerated().map { i, ora in
            ["data": data(ora), "casa": incontri[i].casa, "trasferta": incontri[i].trasferta, "giocata": false,
             "stato": "da_giocare"] as [String: Any]
        }
        o["fase"] = "finita"
        o["giornata"] = giornata + 1
        o["giornata_lega"] = giornataLega + 1
        o["inizio"] = data(inizio(adesso: adesso, fase: .finita))
        o["scadenza"] = data(scadenza(adesso: adesso, fase: .finita))
        o["con_probabili"] = false
        o["probabili"] = NSNull()
        o["da_fare"] = [voceSvincolato]
        o["riepilogo"] = riepilogoFinita()
        if recupero, let ultima = incontri.last {
            // la giornata è finita ma una partita aspetta il recupero: i punti possono ancora cambiare e si può decidere diversamente
            let partita: [String: Any] = ["casa": ultima.casa, "trasferta": ultima.trasferta,
                                          "data": data(dataRecupero(adesso: adesso, fase: .finita))]
            o["riepilogo"] = (o["riepilogo"] as? [String: Any] ?? [:]).merging(
                ["nel_diario": false, "consigliata": NSNull(), "recuperi": [partita], "rinvio": sceltaRinvio(giornata: giornata)]) { _, nuovo in nuovo }
        }
        o["prossima"] = prossimaDopoFinita(adesso: adesso)
        return json(o)
    }

    // MARK: - Elenco dei giocatori (per i risultati della ricerca)

    /// L'elenco dei giocatori della giornata (`/api/classifica`) come il server: chi ha almeno il 20% di giocare, dal più atteso,
    /// con il ruolo e «solo svincolati» chiesti e la squadra della lega di chi non è libero.
    static func classifica(liberi soloLiberi: Bool, ruolo: String?, limite: Int, adesso: Date) -> String {
        var elenco = tutti.filter { !$0.assente && $0.pVoto >= 0.2 }
        if let ruolo, !ruolo.isEmpty { elenco = elenco.filter { $0.ruolo == ruolo.uppercased() } }
        if soloLiberi { elenco = elenco.filter { fantasquadra(di: $0.id) == nil } }
        let ordinati = elenco.sorted { $0.puntiAttesi > $1.puntiAttesi }.prefix(max(1, min(limite, 800)))
        return json(["giornata": giornata, "giocatori": ordinati.map { giocatore($0, adesso: adesso, conProprietario: true) }])
    }

    // MARK: - Lega

    /// Le squadre della lega: quanti giocatori e quanti crediti, gli stessi delle loro rose.
    static func squadre() -> String {
        func immagini(_ nome: String) -> [String: Any] {
            ["stemma": DemoImmagini.conStemma.contains(nome), "maglia": DemoImmagini.conMaglia.contains(nome)]
        }
        let elenco: [[String: Any]] = ([nomeMia] + altreSquadre).map { nome in
            ["nome": nome, "mia": nome == nomeMia, "giocatori": giocatoriDi(nome).count, "crediti_residui": creditiSquadre[nome] ?? 0,
             "immagini": immagini(nome)] as [String: Any]
        }
        return json(elenco)
    }

    static func rosa(_ nome: String, mia: Bool, adesso: Date, fase: Fase = .prima) -> String {
        json(["nome": nome, "mia": mia, "crediti_residui": creditiSquadre[nome] ?? 0, "aggiornato": "2026-10-26T19:19:33",
              "giocatori": giocatoriDi(nome).map { rigaRosa($0, adesso: adesso, fase: fase) },
              "avvisi": mia ? ["Schiera FC: Rolf Gostein e Nereo Fagiani sono indisponibili"] : [String]()])
    }

    static func stato(adesso: Date) -> String {
        json(["stagione": "2026-27", "prossima_giornata": giornata, "mia_squadra": nomeMia, "rose_importate": true, "versione": "1.9",
              "ultimo_aggiornamento": ultimoAggiornamento(adesso: adesso)])
    }

    static func statoDati(adesso: Date) -> String {
        func quando(_ ore: Double) -> String { formatta(adesso.addingTimeInterval(-ore * 3600), "yyyy-MM-dd'T'HH:mm:ss") }
        // le probabili lette alla stessa ora che dice Oggi (#390); una fonte non ha risposto e si è usata la sua copia di prima
        let lette = probabiliLette(adesso: adesso)
        let lettura = formatta(lette, "yyyy-MM-dd'T'HH:mm:ss")
        let copia = formatta(lette.addingTimeInterval(-3 * 3600), "HH:mm")
        return json([
            "stagione": "2026-27", "calciatori": 612, "voti": 2431, "coppe_fino": "2026-12-10", "foto": 8,
            "probabili": [["giornata": giornata, "giocatori": 539, "rilevato": lettura]],
            "calibrazione": ["giornate": 3, "gruppi": [
                ["gruppo": "Titolare 90-100%", "n": 142, "osservato": 0.93, "previsto": 0.95, "indicativo": false],
                ["gruppo": "Titolare 70-89%", "n": 61, "osservato": 0.78, "previsto": 0.8, "indicativo": false],
                ["gruppo": "Panchina 20-49%", "n": 12, "osservato": 0.25, "previsto": 0.31, "indicativo": true],
            ], "taratura": taraturaProbabili(adesso: adesso)],
            "partite": ["totali": 380, "giocate": 100],
            "registro_nostri": registroNostri(),
            "aggiornamenti": [
                ["cosa": "listone e quotazioni", "quando": quando(30), "errori": [String]()],
                ["cosa": "probabili formazioni", "quando": lettura, "errori": ["Una fonte non ha risposto: usata la copia delle \(copia)"]],
                ["cosa": "voti e statistiche", "quando": quando(52), "errori": [String]()],
                ["cosa": "calendario e coppe europee", "quando": quando(100), "errori": [String]()],
            ],
            "registro": registroGiornate(),
            "consiglio": consiglioFormazione(adesso: adesso),
        ])
    }

    /// La taratura di «gioca N%» con le probabili (#379) come la manda il server: accesa da due giorni, dopo le 8 giornate del
    /// registro (4 per tarare, 4 per provare). Prima si mostravano i numeri misurati dal registro, con lo stesso Brier (0,128).
    /// Numeri inventati.
    private static func taraturaProbabili(adesso: Date) -> [String: Any] {
        ["stato": "attiva", "giornate": 8, "minimo": 4, "versione": 1, "motivo": NSNull(),
         "dal": formatta(adesso.addingTimeInterval(-2 * 86_400), "yyyy-MM-dd'T'HH:mm:ss"),
         "prova": ["giornate": 4, "brier": 0.1194, "brier_prima": 0.1307, "brier_mostrati": 0.128, "calibrazione": 0.021]]
    }

    /// Gli indicatori del consiglio di formazione (#366) come li manda il server: 8 giornate (dalla 3 alla 10) su 3 utenti; non regge
    /// solo «Cambi della consigliata» (2 cambi per meno di 1 punto atteso). Numeri inventati.
    private static func consiglioFormazione(adesso: Date) -> [String: Any] {
        let righe: [[String: Any]] = (3...10).reversed().map { g -> [String: Any] in
            let sotto: Int = g >= 9 ? 1 : 0
            let fuori: [String] = g == 10 ? ["C2"] : []
            return ["stagione": "2026-27", "giornata": g, "voci": 3, "meno_s2": 2.1, "meno_schierata": 0.6, "cambi": 1.3,
                    "cambi_sotto_soglia": sotto, "improbabili": 1, "con_compagno": 0, "storte": 1, "spiegate": 1,
                    "senza_motivo": 0.061, "fuori": fuori]
        }
        return [
            "finestra": 8, "giornate": 8, "voci": 24, "verdetto": true,
            "aggiornato": formatta(adesso.addingTimeInterval(-6 * 3600), "yyyy-MM-dd'T'HH:mm:ss"),
            "soglie": ["C1": 0.0, "C2": 0, "C3": 0, "C4_senza_motivo": 0.1],
            "meno_s2": 2.14, "meno_schierata": 0.63, "cambi": 1.33, "cambi_sotto_soglia": 2, "improbabili": 7, "con_compagno": 0,
            "reparti": 81, "storte": 9, "spiegate": 9, "senza_motivo": 0.061,
            "regge": ["C1": true, "C2": false, "C3": true, "C4": true], "fuori": ["C2"], "avvisati": [String](), "per_giornata": righe,
        ]
    }

    /// Il registro delle giornate (#344) come lo manda il server: 8 giornate di Serie A misurate (dalla 2 alla 10, la 6 persa),
    /// la fascia «8 volte su 10» sotto la soglia. Numeri inventati.
    private static func registroGiornate() -> [String: Any] {
        let righe: [[String: Any]] = (2...10).reversed().map { g -> [String: Any] in
            g == 6
                ? ["stagione": "2026-27", "giornata": g, "giocatori": 0,
                   "persa": "nessun tentativo negli ultimi 10 minuti prima della prima partita (servizio fermo o registro spento)"]
                : ["stagione": "2026-27", "giornata": g, "giocatori": 598, "persa": NSNull()]
        }
        return [
            "finestra": 8, "giornate": 8, "verdetto": true,
            "soglie": ["I1": -0.03, "I2_calibrazione": 0.05, "I2_brier": 0.15, "I3_minimo": 0.72, "I3_massimo": 0.88],
            "errore_modello": 2.38, "errore_fantamedia": 2.52, "i1": -0.056, "brier": 0.128, "calibrazione": 0.034, "copertura": 0.69,
            "regge": ["I1": true, "I2": true, "I3": false], "fuori": ["I3"], "per_giornata": righe,
        ]
    }

    /// I gol attesi nostri senza Understat (#401) come li manda il server: la 11 salvata e da misurare, la 7 persa, 8 giornate misurate
    /// della versione 3 (dalla 2 alla 10) e la 1 della versione 2, che non conta. Lo scarto per fasce resta sopra la soglia. Numeri inventati.
    private static func registroNostri() -> [String: Any] {
        let righe: [[String: Any]] = (1...11).reversed().map { g -> [String: Any] in
            var riga: [String: Any] = ["stagione": "2026-27", "giornata": g, "versione": g == 1 ? "2" : "3", "persa": NSNull(),
                                       "giocatori": 0, "misurato": NSNull(), "voti": 0]
            if g == 11 {
                riga["giocatori"] = 598
            } else if g == 7 {
                riga["persa"] = "nessun tentativo prima della prima partita (servizio fermo o riavviato)"
            } else {
                let errore: Double = 0.004 + Double(g % 3) / 1000
                let punti: Double = -0.05 * Double(g % 4)
                let golSuVeri: Double = 0.9 + Double(g % 5) / 100
                riga["misurato"] = "2026-10-" + (g < 10 ? "0\(g)" : "\(g)") + "T12:00:00"
                riga["voti"] = 287
                riga["rose"] = 20
                riga["errore_pct"] = errore
                riga["punti"] = punti
                riga["scarto_gol"] = 0.012
                riga["gol_su_veri"] = golSuVeri
            }
            return riga
        }
        return [
            "versione": "3", "finestra": 8, "giornate": 8, "verdetto": true, "voti": 2296, "rose": 160,
            "soglie": ["errore": 0.01, "punti": -0.3, "scarto_gol": 0.03],
            "errore_pct": 0.005, "punti": -0.08, "scarto_gol": 0.041, "gol_su_veri": 0.93,
            "scarto_gol_mostrati": 0.018, "gol_su_veri_mostrati": 0.99,
            "regge": ["errore": true, "punti": true, "gol": false], "regge_tutto": false, "per_giornata": righe,
        ]
    }

    static func regole() -> String {
        json([
            "nome_lega": "Lega degli amici", "fonte_voto": "redazione",
            // bonus e rimborso vengono dalle costanti della lega della demo (`bonus`, `rimborsoSvincolo`)
            "bonus": ["gol": ["P": bonus.gol, "D": bonus.gol, "C": bonus.gol, "A": bonus.gol], "rigore_segnato": bonus.rigoreSegnato,
                      "assist": bonus.assist, "rigore_parato": 3.0, "rigore_sbagliato": bonus.rigoreSbagliato, "autogol": -2.0,
                      "gol_subito_portiere": bonus.golSubito, "portiere_imbattuto": bonus.imbattuto,
                      "ammonizione": -0.5, "espulsione": -1.0, "mvp": 0.0],
            "rosa": postiRosa, "crediti_iniziali": 500, "rimborso_svincolo": rimborsoSvincolo,
            "scadenza_minuti": minutiScadenza, "prima_giornata_lega": 4, "aggiornamenti_vicino_scadenza": true,
            "partite_rinviate": "aspetta", "voto_ufficio_rinviate": 6, "rinvii_giornate": [String: Any](),
            "moduli": ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"],
            "panchina": ["numero": 11, "tipo": "per_ruolo", "max_sostituzioni": maxSostituzioni, "cambio_modulo": false,
                         "posti": ["P": 2, "D": 3, "C": 3, "A": 3]],
            "modificatore_difesa": ["attivo": true, "min_difensori": 4,
                                    "soglie": [[6, 1], [6.25, 1.5], [6.5, 2], [6.75, 2.5], [7, 3], [7.25, 3.5]]],
            "voto_senza_sostituto": NSNull(), "fattore_campo": 0.0, "soglia_primo_gol": 66.0, "ampiezza_fascia_gol": 6.0,
        ])
    }

    static func riconosci() -> String {
        json(["modifiche": [
            ["chiave": "bonus.assist", "etichetta": "Assist", "valore": 1.0, "riga": "Assist: +1 punto"],
            ["chiave": "bonus.ammonizione", "etichetta": "Ammonizione", "valore": -0.5, "riga": "Ammonizione: -0.5"],
            ["chiave": "panchina.numero", "etichetta": "Giocatori in panchina", "valore": 7, "riga": "Panchina: 7 giocatori"],
            ["chiave": "moduli", "etichetta": "Moduli ammessi", "valore": ["3-4-3", "4-3-3", "4-4-2"], "riga": "Moduli: 3-4-3, 4-3-3, 4-4-2"],
        ] as [[String: Any]], "non_riconosciute": ["Il bonus per il rigore parato vale 3 punti, tranne in coppa"]])
    }

    static func novita() -> String {
        json([
            ["versione": "1.9", "data": "2026-10-20", "titolo": "Formazione più chiara",
             "voci": ["Sotto il campo una riga spiega le scelte che sembrano strane.", "La scheda del giocatore mostra le prossime cinque partite.",
                      "Corretto il conto dei punti attesi con un titolare in dubbio."]],
            ["versione": "1.8", "data": "2026-10-05", "titolo": "Copia di sicurezza e icona",
             "voci": ["La copia di sicurezza notturna comprende anche le chiavi degli avvisi.", "Nuova icona dell'app."]],
            ["versione": "1.7", "data": "2026-09-21", "titolo": "Probabili formazioni",
             "voci": ["Le probabili formazioni arrivano da due fonti.", "Avviso quando un titolare diventa dubbio."]],
        ])
    }

    static func avvisi() -> String {
        json(["impostazioni": ["cambi": true, "promemoria_60": true, "promemoria_15": false, "riepilogo": true, "copertura": true, "app_nativa": true,
                              "silenzio": false, "silenzio_da": 23, "silenzio_a": 23, "avviso_prima": 60],
              "canale": true, "dispositivi": 2, "ore_tranquille_spente": true])
    }

    /// Diario delle giornate: le quattro giornate finite prima di quella di Oggi (la 4, 5, 6 e 7 della lega, Serie A 7-10),
    /// due con la tua formazione e due senza. Ogni voce porta `giornata_lega`, come le manda il server.
    static func diario() -> String {
        // la lega parte dalla giornata 4 di Serie A (`prima_giornata_lega` delle regole della demo), come in Oggi: Serie A 11 = giornata 8
        func lega(_ serieA: Int) -> Int { serieA - 3 }
        // Gli id seguono il nome (non la posizione), così due formazioni con un nome diverso risultano davvero diverse.
        let anagrafe = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Çalvaroğlu", "Leonel", "Thorvan", "Pulinski", "Lemão", "Kloosmeijer", "Dunfrey", "Orsetti", "Mkhedrian", "Zelawski"]
        let ruoliDi = ["Sorvani": "P", "Bastrani": "D", "Dimarzi": "D", "Dunfrey": "D", "Leonel": "A", "Thorvan": "A", "Lemão": "A", "Pulinski": "A", "Orsetti": "A"]
        func titolari(_ nomi: [String]) -> [[String: Any]] {
            nomi.map { ["id": 9000 + (anagrafe.firstIndex(of: $0) ?? 99), "nome": $0, "ruolo": ruoliDi[$0] ?? "C"] }
        }
        let base = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Çalvaroğlu", "Leonel", "Thorvan", "Pulinski", "Lemão", "Kloosmeijer", "Dunfrey"]
        let altra = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Çalvaroğlu", "Leonel", "Thorvan", "Pulinski", "Lemão", "Kloosmeijer", "Orsetti"]
        let altra2 = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Mkhedrian", "Leonel", "Thorvan", "Pulinski", "Lemão", "Zelawski", "Orsetti"]
        // Fantavoto atteso e preso di ogni giocatore (pagina Giornate, #673 passo 2): numeri inventati e fermi, vicini ai punti della
        // squadra divisi per 11; ogni giornata uno è senza voto.
        let scarti: [Double] = [1.5, -1, 0.5, -0.5, 2, -1.5, 0, 1, -2, 0.5, -0.5, 0.5, -1, 1]
        func scarto(_ i: Int, _ g: Int) -> Double { scarti[(i + g) % scarti.count] }
        func fvAtteso(_ i: Int, _ g: Int, _ atteso: Double) -> Double { ((atteso / 11 + scarto(i, g) * 0.4) * 10).rounded() / 10 }
        func fvPreso(_ i: Int, _ g: Int, _ fatti: Double) -> Any {
            (i + g) % 9 == 0 ? NSNull() as Any : ((fatti / 11 + scarto(i, g + 3)) * 2).rounded() / 2 as Any
        }
        // i titolari mostrati prima della scadenza portano il fantavoto atteso di allora, come `istantanea` del server
        func conAtteso(_ nomi: [String], _ g: Int, _ atteso: Double) -> [[String: Any]] {
            titolari(nomi).map { x -> [String: Any] in
                var d = x
                if let i = anagrafe.firstIndex(of: x["nome"] as? String ?? "") { d["fv_atteso"] = fvAtteso(i, g, atteso) }
                return d
            }
        }
        func numeriGiocatori(_ g: Int, _ c: EsitoGiornata) -> [[String: Any]] {
            anagrafe.indices.map { i in
                ["id": 9000 + i, "p_voto": 0.9, "fv_atteso": fvAtteso(i, g, c.atteso), "fv": fvPreso(i, g, c.fatti)] as [String: Any]
            }
        }
        func istantanea(_ g: Int, _ modulo: String, _ nomi: [String], atteso: Double, ora: String) -> [String: Any] {
            ["giornata": g, "modulo": modulo, "titolari": conAtteso(nomi, g, atteso),
             "panchina": conAtteso(["Mkhedrian", "Zelawski", "Orsetti"], g, atteso),
             "atteso": atteso, "stile": "Equilibrato", "calcolata": ora]
        }
        // «Quanto ci abbiamo preso»: punti attesi e fatti della consigliata (le stesse voci qui sotto), con la fascia.
        func avf(_ atteso: Double, _ fatti: Double) -> [String: Any] {
            let f = fascia(atteso)
            let basso = f["basso"] as? Double ?? atteso, alto = f["alto"] as? Double ?? atteso
            return ["riferimento": "consigliata", "atteso": atteso, "fatti": fatti, "scarto": ((fatti - atteso) * 10).rounded() / 10,
                    "nella_fascia": basso <= fatti && fatti <= alto, "intervallo": ["basso": basso, "alto": alto]]
        }
        let affidabilita: [String: Any] = [
            "giornate": 4, "scarto_medio": 3.4, "errore_medio": -0.4, "punti_medi_attesi": 67.4, "punti_medi_fatti": 67.0,
            "dentro_fascia": 4, "con_fascia": 4, "percentuale_dentro": 100, "fascia_dichiarata": 80, "pochi_dati": true,
            "giornate_minime": 8, "giudizio": "pochi_dati",
        ]
        // la riga su tutta la Serie A (registro delle giornate, #374): testo scritto dal server, numeri inventati
        let rigaSerieA: String = "Su tutta la Serie A, nelle ultime 5 giornate: il fantavoto atteso ha sbagliato il 9% in meno della fantamedia; quando diciamo «gioca 96%», ha giocato 9 volte su 10."
        // «Quanto ci abbiamo preso» (forma nuova): numeri onesti anche quando vanno male (qui «gioca» è troppo ottimista).
        let precisione: [String: Any] = [
            "giornate": 4, "pochi_dati": true, "giornate_minime": 8, "fonti": ["mostrati": 3, "ricostruiti": 1],
            "fantavoto": ["errore_medio": 1.4, "scostamento": -0.4, "entro_un_punto": 58, "voti": 41],
            "gioca": ["giocatori": 52, "principale": 1, "fonte": "mostrati", "giornate": 3, "gruppi": [
                ["da": 40, "a": 70, "giocatori": 9, "pochi": true, "detto": 55, "giocato": 44],
                ["da": 90, "a": 100, "giocatori": 43, "pochi": false, "detto": 96, "giocato": 83],
            ]],
            "confronto": ["giornate": 2, "meglio_consigliata": 2, "meglio_tua": 0, "pari": 0, "punti": 12.0,
                          "media_consigliata": 67.5, "media_tua": 61.5],
            "squadra": affidabilita,
            "per_giornata": [
                ["stagione": "2026-27", "giornata": 7, "giornata_lega": lega(7), "fonte": "ricostruiti", "errore_fantavoto": 1.6, "voti": 10,
                 "attesi": 65.0, "fatti": 60.5, "tua": NSNull(), "differenza": NSNull()],
                ["stagione": "2026-27", "giornata": 8, "giornata_lega": lega(8), "fonte": "mostrati", "errore_fantavoto": 1.2, "voti": 11,
                 "attesi": 67.0, "fatti": 64.0, "tua": 59.5, "differenza": 4.5],
                ["stagione": "2026-27", "giornata": 9, "giornata_lega": lega(9), "fonte": "mostrati", "errore_fantavoto": 1.5, "voti": 10,
                 "attesi": 68.5, "fatti": 71.0, "tua": 63.5, "differenza": 7.5],
                ["stagione": "2026-27", "giornata": 10, "giornata_lega": lega(10), "fonte": "mostrati", "errore_fantavoto": 1.3, "voti": 10,
                 "attesi": 69.0, "fatti": 72.5, "tua": NSNull(), "differenza": NSNull()],
            ],
            "serie_a": ["giornate": 5, "giornate_minime": 3, "mancano": 0, "testo": rigaSerieA],
        ]
        // le giornate finite sono quelle di «Attesi e fatti» dei widget (`LegaDemo.giornateFinite`); qui chi è sceso in campo e
        // quando è stata calcolata la consigliata (Serie A 10, 9, 8: l'istantanea; Serie A 7 no)
        let calcolata: [Int: String] = [10: "2026-10-31T10:05:00", 9: "2026-10-24T09:40:00", 8: "2026-10-17T11:20:00"]
        let tuoi: [Int: [String]] = [9: altra, 8: altra2]
        func esito(_ e: EsitoGiornata, _ nomi: [String]) -> [String: Any] {
            ["modulo": e.modulo, "atteso": e.atteso, "reale": e.fatti, "intervallo": fascia(e.atteso), "titolari": titolari(nomi)]
        }
        // Con l'istantanea la consigliata è quella mostrata prima della scadenza (`origine` «mostrata», #614), senza è rifatta
        // («ricostruita»); senza una tua formazione ma con l'istantanea c'è la copia salvata alla scadenza (`automatica`).
        let voci: [[String: Any]] = giornateFinite.map { g -> [String: Any] in
            let c = g.consigliata
            var consigliata = esito(c, base)
            consigliata["origine"] = calcolata[g.serieA] == nil ? "ricostruita" : "mostrata"
            var voce: [String: Any] = ["stagione": stagioneInCorso, "giornata": g.serieA, "giornata_lega": lega(g.serieA),
                                       "modificabile": true, "atteso_vs_fatto": avf(c.atteso, c.fatti), "consigliata": consigliata,
                                       "automatica": NSNull(), "giocatori": numeriGiocatori(g.serieA, c)]
            if let ora = calcolata[g.serieA] { voce["istantanea"] = istantanea(g.serieA, c.modulo, base, atteso: c.atteso, ora: ora) }
            if let s = g.schierata, let nomi = tuoi[g.serieA] {
                voce["schierata"] = esito(s, nomi)
            } else if calcolata[g.serieA] != nil {
                voce["automatica"] = esito(c, base)
            }
            // senza l'istantanea la consigliata di allora non era stata salvata: la frase la scrive il server
            // (`nota_consigliata` di fanta/diario.py, #674), qui il suo testo per la consigliata rifatta o per la tua formazione
            if calcolata[g.serieA] == nil {
                voce["consigliata_di_allora"] = "non_salvata"
                voce["nota_consigliata"] = voce["schierata"] == nil
                    ? "Questa è rifatta con i dati di allora: quella mostrata prima della scadenza non era stata salvata."
                    : "Qui il confronto con la consigliata non c'è: quella mostrata prima della scadenza non era stata salvata."
            }
            return voce
        }
        return json([
            "affidabilita": affidabilita,
            "precisione": precisione,
            "giornate": voci,
            // come `sintesi` di fanta/diario.py: le giornate 9 e 8 di Serie A, le due con la tua formazione
            "sintesi": ["giornate": 2, "punti_schierata": 61.5, "punti_consigliata": 67.5, "attesi_schierata": 66.0,
                        "meglio_tua": 0, "meglio_consigliata": 2],
            // come `scelte_tue` di fanta/diario.py, dalle stesse voci: le giornate 9 e 8 di Serie A, le sole con la tua formazione
            // (undici diversi da quelli consigliati); 2 giornate sono sotto le 8 che servono, quindi «pochi dati»
            "scelte_tue": ["giornate": 2, "meglio_tua": 0, "meglio_consigliata": 2, "pari": 0, "punti_differenza": -12.0,
                           "percentuale_tua": 0, "pochi_dati": true,
                           "per_giornata": [
                               ["stagione": "2026-27", "giornata": 9, "giornata_lega": lega(9), "hai_scelto": ["Orsetti"], "consigliava": ["Dunfrey"],
                                "punti_tua": 63.5, "punti_consigliata": 71.0, "differenza": -7.5, "esito": "consigliata"],
                               ["stagione": "2026-27", "giornata": 8, "giornata_lega": lega(8), "hai_scelto": ["Mkhedrian", "Zelawski", "Orsetti"],
                                "consigliava": ["Çalvaroğlu", "Kloosmeijer", "Dunfrey"],
                                "punti_tua": 59.5, "punti_consigliata": 64.0, "differenza": -4.5, "esito": "consigliata"],
                           ]],
        ])
    }

    /// Un backup piccolo ma valido, per provare «Scarica il backup» in demo.
    static func backup() -> String {
        json(["formato": "schieraxi-backup", "versione": 1, "creato": "2026-10-30T09:00:00",
              "file": ["dati/osservati.json": [9001, 9002]]])
    }

    // MARK: - Prova del modello, stagione

    static func affidabilita() -> String {
        var righe: [[String: Any]] = []
        for g in 1...8 {
            let base = 64.0 + Double((g * 7) % 9)
            righe.append(["stagione": "2026-27", "giornata": g, "errore_modello": 1.4 + Double(g % 3) * 0.2, "errore_fantamedia": 1.7 + Double(g % 4) * 0.15,
                          "punti_modello": base + 3, "punti_fantamedia": base, "punti_perfetta": base + 9, "n": 200])
        }
        return json(["calcolato": "2026-10-28T00:38:07", "ultima": "2026-27/8", "righe": righe,
                     "sintesi": ["giornate": 8, "errore_modello": 1.6, "errore_fantamedia": 1.82, "punti_modello": 71.7, "punti_fantamedia": 70.6, "punti_perfetta": 77.8]])
    }

    static func stagione() -> String {
        let nuova = Demo.schermata == "lega-stagione"
        return json(["corrente": nuova ? "2027-28" : "2026-27", "rose": "2026-27", "nuova": nuova])
    }

    static func importa() -> String {
        json(["squadre_importate": ["Real Madrink", "Dinamo Pizza"], "totale_squadre": 8, "avvisi": ["Dinamo Pizza: 24 giocatori invece di 25"],
              "mia_squadra": nomeMia, "riepilogo": "Scambio Real Madrink / Dinamo Pizza: Kaan Yurdız ⇄ Sandy McTarran",
              "differenze": [
                "prima_importazione": false, "nessuna_differenza": false,
                "scambi": [["squadre": ["Real Madrink", "Dinamo Pizza"], "da_a": [["id": 325, "nome": "Kaan Yurdız", "ruolo": "A", "squadra": "juventus", "costo": 33]],
                            "da_b": [["id": 321, "nome": "Sandy McTarran", "ruolo": "C", "squadra": "napoli", "costo": 25]]]],
                "svincolati_presi": [["squadra": "AC Pigra", "giocatori": [["id": 204, "nome": "Nenad Krslić", "ruolo": "A", "squadra": "lecce", "costo": 5]]]],
                "tagliati": [[String: Any]](), "crediti": [["squadra": "AC Pigra", "prima": 30, "dopo": 22]],
                "testo": "Scambio Real Madrink / Dinamo Pizza"] as [String: Any]])
    }

    // MARK: - Risposte che dipendono dalla domanda

    /// Le risposte che cambiano con la domanda (`?q=`, `?liberi=`): ricerca ed elenco dei giocatori, calcolati
    /// dalla lega come fa il server. Passano dal gancio `binari` del server finto, l'unico che riceve l'indirizzo intero: le risposte
    /// di testo si scelgono per prefisso e non vedono la domanda. Nil per gli altri indirizzi.
    static func calcolata(_ percorso: String, adesso: Date) -> Data? {
        guard let indirizzo = URLComponents(string: "https://demo.invalid" + percorso) else { return nil }
        var domanda: [String: String] = [:]
        for voce in indirizzo.queryItems ?? [] where domanda[voce.name] == nil {
            if let valore = voce.value { domanda[voce.name] = valore }
        }
        let limite = Int(domanda["limite"] ?? "")
        let testo: String
        switch indirizzo.path {
        case "/api/giocatori":
            testo = json(cerca(domanda["q"] ?? "", limite: limite ?? 15).map { breve($0.id) })
        case "/api/classifica":
            let soloLiberi = ["true", "1"].contains(domanda["liberi"]?.lowercased() ?? "")
            testo = classifica(liberi: soloLiberi, ruolo: domanda["ruolo"], limite: limite ?? 60, adesso: adesso)
        default:
            return nil
        }
        return Data(testo.utf8)
    }

    // MARK: - Tutte le risposte

    static func risposte(adesso: Date) -> [String: String] {
        var r: [String: String] = [
            // account (con il server di sempre non servono: «me» dice che non c'è nessun accesso)
            "/api/account/me": "{\"multiutente\": false, \"utente\": {\"id\": 0, \"nome_utente\": \"locale\", \"ruolo\": \"amministratore\", \"creato\": \"\"}}",
            "/api/account/accedi": "{\"multiutente\": true, \"utente\": {\"id\": 7, \"nome_utente\": \"mister.rossi\", \"ruolo\": \"utente\", \"creato\": \"2026-10-29\"}, \"token\": \"token-demo\"}",
            "/api/account/registra": "{\"multiutente\": true, \"utente\": {\"id\": 7, \"nome_utente\": \"mister.rossi\", \"ruolo\": \"utente\", \"creato\": \"2026-10-29\"}, \"token\": \"token-demo\", \"codice_recupero\": \"K7M2P-XQ4NH-W8RTV\"}",
            "/api/account/codice-recupero": "{\"codice_recupero\": \"H3N8D-R5WQA-C9XEJ\"}",
            "/api/account/recupero": "{\"ok\": true, \"codice_recupero\": \"H3N8D-R5WQA-C9XEJ\"}",
            // come il server dal #589: il codice di recupero cambia con la password (senza token: la sessione della demo resta quella)
            "/api/account/cambia-password": "{\"multiutente\": true, \"utente\": {\"id\": 7, \"nome_utente\": \"mister.rossi\", \"ruolo\": \"utente\", \"creato\": \"2026-10-29\"}, \"ok\": true, \"codice_recupero\": \"H3N8D-R5WQA-C9XEJ\"}",
            "/api/stato": stato(adesso: adesso),
            "/api/stato-dati": statoDati(adesso: adesso),
            "/api/squadre": squadre(),
            "/api/rosa": rosa(nomeMia, mia: true, adesso: adesso),
            "/api/calendario": json(calendario(adesso: adesso)),
            "/api/formazione/testo": "Giornata \(giornata) - 3-4-3 (\(Formato.punti(punteggio(moduli[0].titolari))) punti attesi)",
            "/api/formazione/valuta": valutazione(),
            "/api/scelta": "null",   // nessuna scelta salvata: si vede la consigliata
            "/api/formazione": formazione(adesso: adesso),
            "/api/primo-avvio": json(["primo_avvio": NSNull(), "passi": ["server", "accesso", "rose", "squadra", "stemma", "pwa", "widget", "avvisi"]]),
            "/api/oggi": oggi(adesso: adesso),
            "/api/regole": regole(),
            "/api/avvisi": avvisi(),
            "/api/diario": diario(),
            "/api/backup": backup(),
            "/api/novita": novita(),
            "/api/foto-disponibili": json(["ids": Array(DemoImmagini.idConFoto).sorted()]),
            "/api/affidabilita": affidabilita(),
            "/api/stagione": stagione(),
            "/api/regole/riconosci": riconosci(),
            "/api/rose/testo": importa(),
            "/api/rose/file": importa(),
            "/api/rose/anteprima": DemoAnteprimaRose.json,   // anche /api/rose/anteprima/file
            "/api/aggiorna": json(["avviato": true, "in_corso": false, "righe": [String](), "errori": [String]()]),
        ]
        r["/api/rosa?squadra=" + IndirizzoServer.codifica(nomeMia)] = rosa(nomeMia, mia: true, adesso: adesso)
        for nome in altreSquadre {
            r["/api/rosa?squadra=" + IndirizzoServer.codifica(nome)] = rosa(nome, mia: false, adesso: adesso)
        }
        // ogni scheda ha il suo indirizzo (id a tre cifre: nessun indirizzo è l'inizio di un altro)
        for p in tutti { r["/api/giocatore/\(p.id)"] = json(schedaGiocatore(p, adesso: adesso)) }
        r["/api/giocatore/"] = json(schedaGiocatore(calciatore(203), adesso: adesso))
        return r
    }
}
