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

    /// Le fotografie delle fasi della giornata (`-DEMO_SCHERMATA oggi-in-corso` e `oggi-finita`): la stessa demo, con Oggi durante
    /// e dopo la giornata. Ognuna ha il suo indirizzo finto, così la copia salvata di Oggi non si mescola. Nil per le altre schermate.
    /// `fissato`: l'istante della demo (solo i test); senza, adesso.
    static func demoFase(_ schermata: String?, adesso fissato: Date? = nil) -> FinteServer? {
        let adesso = fissato ?? Date()
        var server = fissato.map { demoFissata(adesso: $0) } ?? FinteServer.demo
        switch schermata ?? "" {
        case "oggi-in-corso":
            server.risposte["/api/oggi"] = DatiDemo.oggiInCorso(adesso: adesso)
            server.risposte["/api/live"] = DatiDemo.live(adesso: adesso, giornataInCorso: true)
            server.indirizzoFinto = "https://finto-giornata-in-corso.invalid"
        case "oggi-finita":
            server.risposte["/api/oggi"] = DatiDemo.oggiFinita(adesso: adesso)
            server.risposte["/api/live"] = "{\"in_corso\": 0, \"partite\": []}"
            server.indirizzoFinto = "https://finto-giornata-finita.invalid"
        case "formazione-chiusa":
            // la giornata chiusa (dopo la scadenza): la formazione salvata in sola lettura
            server.risposte["/api/formazione"] = DatiDemo.formazione(iniziata: true, adesso: adesso)
            server.risposte["/api/scelta"] = DatiDemo.sceltaSalvata(adesso: adesso)
            server.indirizzoFinto = "https://finto-formazione-chiusa.invalid"
        case "formazione-salvata":
            // la Formazione con la tua scelta già salvata (riga «La tua formazione è salvata (oggi alle …)»)
            server.risposte["/api/scelta"] = DatiDemo.sceltaSalvata(adesso: adesso)
            server.indirizzoFinto = "https://finto-scelta-salvata.invalid"
        case "oggi-rinvio":
            server.risposte["/api/oggi"] = DatiDemo.oggiRinvio(adesso: adesso)
            server.indirizzoFinto = "https://finto-partita-rinviata.invalid"
        case "oggi-finita-recupero":
            server.risposte["/api/oggi"] = DatiDemo.oggiFinita(adesso: adesso, recupero: true)
            server.risposte["/api/live"] = "{\"in_corso\": 0, \"partite\": []}"
            server.indirizzoFinto = "https://finto-recupero-da-giocare.invalid"
        default:
            return nil
        }
        return server
    }
}

private typealias Calciatore = CalciatoreDemo
/// In questo file `DatiDemo` è la lega della demo vista dall'app: le risposte del server finto.
private typealias DatiDemo = LegaDemo

private extension LegaDemo {
    /// Le giornate degli scambi: le stesse del calendario.
    static var giornate: [Int] { giornateProssime }

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
    /// l'ora della sua partita (la stessa delle partite di Oggi).
    static func giocatore(_ p: Calciatore, adesso: Date, conAvversario: Bool = true, conProprietario: Bool = false) -> [String: Any] {
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
        if let data = dataPartita(di: p.squadra, adesso: adesso) { d["data_partita"] = data }
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
        return d
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

    static func rigaRosa(_ p: Calciatore, adesso: Date) -> [String: Any] {
        ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra, "squadra_slug": p.squadra,
         "costo": costo(p), "quotazione": quotazione(p), "previsione": giocatore(p, adesso: adesso)]
    }

    static func schedaGiocatore(_ p: Calciatore, adesso: Date) -> [String: Any] {
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
        var previsione = giocatore(p, adesso: adesso)
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

    static func formazione(iniziata: Bool = false, adesso: Date) -> String {
        let base = moduli[0]
        let ids = base.titolari
        let bench = panchina(per: ids)
        let titolari = ids.map { giocatore(calciatore($0), adesso: adesso) }
        let panchinaJSON = bench.map { giocatore(calciatore($0), adesso: adesso) }
        // gli stili come li manda il server (nomi e descrizioni di LIVELLI_RISCHIO): Sicura, Equilibrata (consigliata), Rischiosa
        var livelli: [[String: Any]] = []
        for r in [-1, 0, 1] {
            let nome = StileFormazione.nomi[r] ?? ""
            let extra = Double(r) * 0.6
            var elenco: [[String: Any]] = []
            for m in moduli {
                elenco.append(["modulo": m.nome, "punteggio_atteso": punteggio(m.titolari) + extra,
                               "titolari": m.titolari, "panchina": panchina(per: m.titolari),
                               "dev": 4.2, "intervallo": fascia(punteggio(m.titolari) + extra)])
            }
            livelli.append(["rischio": r, "stile": r, "nome": nome, "descrizione": StileFormazione.descrizione(r),
                            "modulo": base.nome, "punteggio_atteso": punteggio(ids) + extra, "moduli": elenco,
                            "intervallo": fascia(punteggio(ids) + extra)])
        }
        var schede: [String: Any] = [:]
        for p in miaRosa { schede[String(p.id)] = giocatore(p, adesso: adesso) }
        // probabili uscite, come in Oggi, nel widget e nello Stato dei dati (prima diceva «non ancora uscite», #303)
        return json([
            "squadra": nomeMia, "giornata": giornata, "giornata_lega": giornataLega, "modulo": base.nome, "punteggio_atteso": punteggio(ids),
            "con_probabili": true, "titolari": titolari, "panchina": panchinaJSON, "livelli": livelli, "schede": schede, "stile_consigliato": 0,
            "dev": 4.2, "intervallo": fascia(punteggio(ids)), "iniziata": iniziata,
        ])
    }

    /// La scelta salvata della giornata (gli undici del primo modulo), salvata un'ora fa (ora italiana, come il server).
    static func sceltaSalvata(adesso: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return json(["titolari": moduli[0].titolari, "modulo": moduli[0].nome, "salvata": f.string(from: adesso.addingTimeInterval(-3600)),
                     "tipo": "manuale"])
    }

    static func valutazione() -> String {
        let ids = moduli[0].titolari
        let punti = punteggio(ids)
        return json(["modulo": "3-4-3", "punteggio_atteso": punti - 1.2, "dev": 3.1, "intervallo": fascia(punti - 1.2), "panchina": panchina(per: ids),
                     "differenza": -1.2, "consigliata": punti])
    }

    // MARK: - Oggi

    static func oggi(adesso: Date) -> String { json(oggiDati(adesso: adesso)) }

    static func oggiDati(adesso: Date) -> [String: Any] {
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
        return [
            "miei_titolari": mieiTitolari, "fase": "prima",
            "giornata": giornata, "inizio": formatta(primaPartita, "yyyy-MM-dd HH:mm"),
            "scadenza": formatta(scadenza(adesso: adesso), "yyyy-MM-dd HH:mm"), "minuti_scadenza": minutiScadenza, "giornata_lega": giornataLega,
            "iniziata": false, "con_probabili": true,
            "probabili": ["aggiornate_il": "2026-11-08 09:05", "minuti_fa": 480, "eta": "8 ore fa", "testo": "Probabili aggiornate alle 09:05",
                          "vecchie": true, "avviso": "Le probabili hanno 8 ore: ricontrolla prima del fischio."],
            "formazione": ["modulo": "3-4-3", "punteggio_atteso": punteggio(ids), "squadra": nomeMia,
                           "dev": 4.2, "intervallo": fascia(punteggio(ids)), "tua_scelta": tuaScelta],
            "avvisi": avvisi, "migliori": migliori, "partite": partite,
            "da_fare": [voceDubbio, voceSvincolato, voceRoseVecchie, voceDiario, voceBackup],
        ]
    }

    // MARK: - «Da fare» come lo scrive il server
    // Testi e pulsanti sono quelli di `fanta/frasi.py` (chiavi `dafare.*`), riempiti con i dati della demo;
    // `DemoDaFareTests` li confronta con il catalogo del server.

    /// Marténi, titolare in dubbio, come `_dubbi` di fanta/da_fare.py (#268): il cambio («Meglio Y», «Sostituisci») si propone solo
    /// se la consigliata lo fa, con la regola di «consigliato» del confronto (`daSchierare`); se la consigliata tiene il titolare, la
    /// voce dice chi entra dalla panchina se lui non gioca (la prima riserva del suo ruolo) e apre la formazione. Nella demo la
    /// consigliata tiene Marténi: Oggi dice la stessa cosa di «Chi schierare?» (#305). La percentuale è il suo «gioca».
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

    /// Il primo cambio di `mercato()`: Retalli (libero) al posto di Vlasenić, 3,4 punti in più.
    static var voceSvincolato: [String: Any] {
        let v = svincoloMigliore
        return ["id": "svincolato-\(v.entra)", "tipo": "svincolato",
                "testo": "\(calciatore(v.entra).nome) (libero) al posto di \(calciatore(v.esce).nome): circa \(Formato.punti(v.guadagno)) punti in più.",
                "priorita": 2, "azione": "Vedi", "destinazione": ["sezione": "mercato", "link": "schieraxi://mercato"]]
    }

    /// Rose ferme da 5 giorni dopo una giornata giocata.
    static var voceRoseVecchie: [String: Any] {
        ["id": "rose", "tipo": "rose", "testo": "Le rose non sono aggiornate da 5 giorni e nel frattempo si è giocata una giornata.",
         "priorita": 2, "azione": "Aggiorna le rose", "destinazione": ["sezione": "lega", "link": "schieraxi://lega"]]
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

    /// Fase `in_corso`: scadenza passata da più di due ore; Inter-Roma finita con i voti, Milan-Juventus e Lazio-Fiorentina in
    /// corso, il resto da giocare. Un cambio già fatto (Bastrani senza voto, entra Dimarzi) e due probabili. Orari e numeri sono
    /// quelli del widget (`LegaDemo.bloccoInCorso`).
    static func oggiInCorso(adesso: Date) -> String {
        var o = oggiDati(adesso: adesso)
        let stati = ["finita", "in_corso", "da_giocare", "in_corso", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "da_giocare"]
        o["partite"] = orari(adesso: adesso, fase: .inCorso).enumerated().map { i, ora in
            ["data": formatta(ora, "yyyy-MM-dd HH:mm"), "casa": incontri[i].casa, "trasferta": incontri[i].trasferta, "giocata": i == 0,
             "stato": stati[i]] as [String: Any]
        }
        o["fase"] = "in_corso"
        o["iniziata"] = true
        o["inizio"] = formatta(inizio(adesso: adesso, fase: .inCorso), "yyyy-MM-dd HH:mm")
        o["scadenza"] = formatta(scadenza(adesso: adesso, fase: .inCorso), "yyyy-MM-dd HH:mm")
        o["da_fare"] = [[String: Any]]()
        o["in_corso"] = bloccoInCorso(adesso: adesso)
        return json(o)
    }

    // MARK: - Partite rinviate (fotografie `oggi-rinvio` e `oggi-finita-recupero`)

    /// La scelta «per questa giornata» della demo: la lega aspetta il recupero.
    static func sceltaRinvio(giornata g: Int, partite: [[String: Any]] = [], miei: [[String: Any]] = []) -> [String: Any] {
        ["stagione": "2026-27", "giornata": g, "giornata_lega": g - 3, "modo": "aspetta", "valore": NSNull(), "predefinito": "aspetta",
         "eccezione": false, "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6, "partite": partite, "miei": miei]
    }

    /// Oggi prima della scadenza con l'ultima partita del turno rinviata a fine mese: il riquadro «Partita rinviata».
    static func oggiRinvio(adesso: Date) -> String {
        var o = oggiDati(adesso: adesso)
        var partite = (o["partite"] as? [[String: Any]]) ?? []
        guard let ultima = incontri.last, !partite.isEmpty else { return json(o) }
        let recupero = formatta(adesso.addingTimeInterval(20 * 86_400), "yyyy-MM-dd HH:mm")
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
        var o = oggiDati(adesso: adesso)
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
            let partita: [String: Any] = ["casa": ultima.casa, "trasferta": ultima.trasferta, "data": data(adesso.addingTimeInterval(18 * 86_400))]
            o["riepilogo"] = (o["riepilogo"] as? [String: Any] ?? [:]).merging(
                ["nel_diario": false, "consigliata": NSNull(), "recuperi": [partita], "rinvio": sceltaRinvio(giornata: giornata)]) { _, nuovo in nuovo }
        }
        o["prossima"] = prossimaDopoFinita(adesso: adesso)
        return json(o)
    }

    // MARK: - Risultati in diretta

    /// Le partite del turno in diretta, le stesse del widget (`LegaDemo.liveDemo`): prima della scadenza tutte da giocare, con gli
    /// orari di Oggi; con `giornataInCorso` come nella fotografia `oggi-in-corso` (Inter-Roma finita, due partite in gioco).
    static func live(adesso: Date, giornataInCorso: Bool = false) -> String {
        json(liveDemo(adesso: adesso, fase: giornataInCorso ? .inCorso : .prima))
    }

    // MARK: - Mercato

    /// I Cambi consigliati con i conti del server (`mercato` di fanta/gestione.py): rimborso = quota delle regole del prezzo
    /// pagato, crediti dopo = crediti + rimborso − quotazione di chi entra, dal cambio che rende di più.
    static func mercato() -> String {
        // il primo è il miglior svincolo, lo stesso del widget e di «Da fare»
        let v = svincoloMigliore
        let cambi: [(esce: Int, entra: Int, guadagno: Double)] = [
            (v.esce, v.entra, v.guadagno), (119, 205, 1.9), (118, 210, 2.2), (109, 215, 2.6), (110, 209, 1.2), (103, 206, 0.8),
        ]
        let proposte: [[String: Any]] = cambi.sorted { $0.guadagno > $1.guadagno }.map { c -> [String: Any] in
            let resa = rimborso(calciatore(c.esce))
            let dopo = creditiResidui + resa - quotazione(calciatore(c.entra))
            return ["esce": breve(c.esce), "entra": breve(c.entra), "guadagno": c.guadagno, "breve": c.guadagno * 0.4,
                    "rimborso": resa, "crediti_dopo": dopo, "fattibile": dopo >= 0]
        }
        return json(["squadra": nomeMia, "svincolati": 118, "crediti_residui": creditiResidui, "proposte": proposte])
    }

    /// L'elenco dei giocatori della giornata (`/api/classifica`) come il server: chi ha almeno il 20% di giocare, dal più atteso,
    /// con il ruolo e «solo svincolati» chiesti e la squadra della lega di chi non è libero.
    static func classifica(liberi soloLiberi: Bool, ruolo: String?, limite: Int, adesso: Date) -> String {
        var elenco = tutti.filter { !$0.assente && $0.pVoto >= 0.2 }
        if let ruolo, !ruolo.isEmpty { elenco = elenco.filter { $0.ruolo == ruolo.uppercased() } }
        if soloLiberi { elenco = elenco.filter { fantasquadra(di: $0.id) == nil } }
        let ordinati = elenco.sorted { $0.puntiAttesi > $1.puntiAttesi }.prefix(max(1, min(limite, 800)))
        return json(["giornata": giornata, "giocatori": ordinati.map { giocatore($0, adesso: adesso, conProprietario: true) }])
    }

    static func osservati(adesso: Date) -> String {
        // gli stessi seguiti del widget, nello stesso ordine
        let elenco = idOsservati.map { giocatore(osservato($0), adesso: adesso, conProprietario: true) }
        return json(["giornata": giornata, "giocatori": elenco])
    }

    // MARK: - Scambi

    static func proposta(altra: String, dai: [Int], ricevi: [Int], mio: Double, loro: Double) -> [String: Any] {
        let n = Double(giornate.count)
        let mioPer = giornate.enumerated().map { (mio / n) + (Double($0.offset % 2) - 0.5) * 0.2 }
        let loroPer = giornate.enumerated().map { (loro / n) + (Double($0.offset % 3) - 1.0) * 0.1 }
        return ["mia": nomeMia, "altra": altra, "do": dai.map { breve($0) }, "ricevo": ricevi.map { breve($0) },
                "guadagno_mio": mio, "guadagno_loro": loro, "per_giornata_mio": mioPer, "per_giornata_loro": loroPer,
                "breve_mio": mio * 0.5, "breve_loro": loro * 0.5, "giornate": giornate]
    }

    /// Il miglior scambio, lo stesso del widget.
    static var propostaMigliore: [String: Any] {
        let s = scambioMigliore
        return proposta(altra: s.altra, dai: s.dai, ricevi: s.ricevi, mio: s.mio, loro: s.loro)
    }

    /// Le proposte di scambio: chi ricevo sta nella rosa dell'altra squadra (`altriPerSquadra`).
    static func scambi() -> String {
        let proposte: [[String: Any]] = [
            propostaMigliore,
            proposta(altra: "Gli Amici del Bar Sport Centrale", dai: [110, 119], ricevi: [323, 308], mio: 3.1, loro: 0.6),
            proposta(altra: "Dinamo Pizza", dai: [116], ricevi: [322], mio: 1.8, loro: 0.9),
            proposta(altra: "Atletico Divano", dai: [125], ricevi: [336], mio: 1.2, loro: 1.0),
            proposta(altra: "Borgo Rossi United", dai: [111], ricevi: [312], mio: 0.7, loro: 0.4),
        ]
        return json(["giornate": giornate, "proposte": proposte])
    }

    static func analisi() -> String {
        var p = propostaMigliore
        // l'analisi completa (scambi N contro M con conguaglio): rose valide, crediti, valore e giudizio
        p["completo"] = true
        p["valido"] = true
        p["problemi"] = [String]()
        p["rose"] = ["mio": ["squadra": nomeMia, "valida": true, "problemi": [String](), "modulo": "3-4-3"],
                     "loro": ["squadra": "Real Madrink", "valida": true, "problemi": [String](), "modulo": "4-3-3"]]
        p["valore_rosa"] = ["mio": ["prima": 64.5, "dopo": 66.9, "variazione": 2.4, "percentuale": 3.7],
                            "loro": ["prima": 61.0, "dopo": 62.1, "variazione": 1.1, "percentuale": 1.8]]
        p["panchina"] = ["mio": ["prima": 8.0, "dopo": 8.3, "variazione": 0.3], "loro": ["prima": 7.5, "dopo": 7.4, "variazione": -0.1]]
        p["conguaglio"] = ["crediti": 5, "valido": true, "residui": ["mio": 12, "loro": 30], "dopo": ["mio": 17, "loro": 25],
                           "chi_paga": "loro", "tasso_mio": 0.12, "tasso_loro": 0.1, "valore_mio": 0.6, "valore_loro": -0.5]
        p["netto_mio"] = 3.0
        p["netto_loro"] = 0.6
        p["giudizio"] = ["chi": "entrambi", "testo": "Conviene a tutti e due: proponilo.", "soglia": 0.5,
                         "spiegazione": ["Per te la formazione migliore passa da 64,5 a 66,9 punti attesi.",
                                         "Con 5 crediti ricevuti il netto per te è +3,0."]]
        return json(p)
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

    static func rosa(_ nome: String, mia: Bool, adesso: Date) -> String {
        json(["nome": nome, "mia": mia, "crediti_residui": creditiSquadre[nome] ?? 0, "aggiornato": "2026-10-26T19:19:33",
              "giocatori": giocatoriDi(nome).map { rigaRosa($0, adesso: adesso) },
              "avvisi": mia ? ["Schiera FC: Rolf Gostein e Nereo Fagiani sono indisponibili"] : [String]()])
    }

    static func stato(adesso: Date) -> String {
        json(["stagione": "2026-27", "prossima_giornata": giornata, "mia_squadra": nomeMia, "rose_importate": true, "versione": "1.9",
              "ultimo_aggiornamento": ultimoAggiornamento(adesso: adesso)])
    }

    static func statoDati(adesso: Date) -> String {
        func quando(_ ore: Double) -> String { formatta(adesso.addingTimeInterval(-ore * 3600), "yyyy-MM-dd'T'HH:mm:ss") }
        return json([
            "stagione": "2026-27", "calciatori": 612, "voti": 2431, "coppe_fino": "2026-12-10", "foto": 8,
            "probabili": [["giornata": giornata, "giocatori": 539, "rilevato": quando(2)]],
            "calibrazione": ["giornate": 3, "gruppi": [
                ["gruppo": "Titolare 90-100%", "n": 142, "osservato": 0.93, "previsto": 0.95, "indicativo": false],
                ["gruppo": "Titolare 70-89%", "n": 61, "osservato": 0.78, "previsto": 0.8, "indicativo": false],
                ["gruppo": "Panchina 20-49%", "n": 12, "osservato": 0.25, "previsto": 0.31, "indicativo": true],
            ]],
            "partite": ["totali": 380, "giocate": 100],
            "registro_nostri": registroNostri(),
            "aggiornamenti": [
                ["cosa": "listone e quotazioni", "quando": quando(30), "errori": [String]()],
                ["cosa": "probabili formazioni", "quando": quando(2), "errori": ["Una fonte non ha risposto: usata la copia delle 08:10"]],
                ["cosa": "voti e statistiche", "quando": quando(52), "errori": [String]()],
                ["cosa": "calendario e coppe europee", "quando": quando(100), "errori": [String]()],
            ],
            "registro": registroGiornate(),
            "consiglio": consiglioFormazione(adesso: adesso),
        ])
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
            // i bonus che servono al confronto e il rimborso dei Cambi consigliati vengono dalle stesse costanti (`bonus`, `rimborsoSvincolo`)
            "bonus": ["gol": ["P": bonus.gol, "D": bonus.gol, "C": bonus.gol, "A": bonus.gol], "rigore_segnato": bonus.rigoreSegnato,
                      "assist": bonus.assist, "rigore_parato": 3.0, "rigore_sbagliato": bonus.rigoreSbagliato, "autogol": -2.0,
                      "gol_subito_portiere": bonus.golSubito, "portiere_imbattuto": bonus.imbattuto,
                      "ammonizione": -0.5, "espulsione": -1.0, "mvp": 0.0],
            "rosa": postiRosa, "crediti_iniziali": 500, "rimborso_svincolo": rimborsoSvincolo,
            "scadenza_minuti": 30, "prima_giornata_lega": 4, "aggiornamenti_vicino_scadenza": true,
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
            ["versione": "1.9", "data": "2026-10-20", "titolo": "Scambi più veloci",
             "voci": ["Gli scambi 2 contro 2 si calcolano in metà tempo.", "Il calendario mostra la difficoltà per cinque giornate.",
                      "Corretto il conteggio dei crediti dopo uno svincolo."]],
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
        func istantanea(_ g: Int, _ modulo: String, _ nomi: [String], atteso: Double, ora: String) -> [String: Any] {
            ["giornata": g, "modulo": modulo, "titolari": titolari(nomi), "panchina": titolari(["Mkhedrian", "Zelawski", "Orsetti"]),
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
        let voci: [[String: Any]] = giornateFinite.map { g -> [String: Any] in
            let c = g.consigliata
            var voce: [String: Any] = ["stagione": stagioneInCorso, "giornata": g.serieA, "giornata_lega": lega(g.serieA),
                                       "atteso_vs_fatto": avf(c.atteso, c.fatti), "consigliata": esito(c, base)]
            if let ora = calcolata[g.serieA] { voce["istantanea"] = istantanea(g.serieA, c.modulo, base, atteso: c.atteso, ora: ora) }
            if let s = g.schierata, let nomi = tuoi[g.serieA] { voce["schierata"] = esito(s, nomi) }
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

    // MARK: - Confronto, prova del modello, movimenti, stagione

    /// «Chi schierare?» (`/api/confronto?a=…&b=…&modulo=…`): i due giocatori come in Formazione; scelta, cause, frase e posto
    /// nella formazione calcolati dagli stessi numeri come fa il server (`confrontoCalcolato`, in DemoConfronto.swift).
    static func confronto(_ a: Calciatore, _ b: Calciatore, modulo: String?, adesso: Date) -> String {
        var d = confrontoCalcolato(a, b, modulo: modulo)
        d["giornata"] = giornata
        d["giornata_lega"] = giornataLega
        d["giocatori"] = [giocatore(a, adesso: adesso), giocatore(b, adesso: adesso)]
        return json(d)
    }

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

    static func movimenti() -> String {
        func g(_ id: Int, _ nome: String, _ ruolo: String, _ squadra: String) -> [String: Any] { ["id": id, "nome": nome, "ruolo": ruolo, "squadra": squadra, "costo": 10] }
        return json([
            ["quando": "2026-10-26T19:19:33",
             "scambi": [["squadre": ["Real Madrink", "Dinamo Pizza"], "da_a": [g(325, "Kaan Yurdız", "A", "juventus")], "da_b": [g(321, "Sandy McTarran", "C", "napoli")]]],
             "svincolati_presi": [["squadra": "AC Pigra", "giocatori": [g(204, "Nenad Krslić", "A", "lecce")]]],
             "tagliati": [["squadra": "Inter Nos", "giocatori": [g(215, "Gilberto Mancarini", "D", "roma")]]],
             "crediti": [["squadra": "AC Pigra", "prima": 30, "dopo": 22]],
             "testo": "Scambio Real Madrink / Dinamo Pizza: Kaan Yurdız ⇄ Sandy McTarran"] as [String: Any],
            ["quando": "2026-10-19T08:02:10",
             "scambi": [[String: Any]](), "svincolati_presi": [["squadra": "Schiera FC", "giocatori": [g(113, "Hamit Çalvaroğlu", "C", "inter")]]],
             "tagliati": [[String: Any]](), "crediti": [[String: Any]](), "testo": "Schiera FC prende dagli svincolati: Hamit Çalvaroğlu"] as [String: Any],
        ] as [[String: Any]])
    }

    static func stagione() -> String {
        let nuova = Demo.schermata == "lega-stagione"
        return json(["corrente": nuova ? "2027-28" : "2026-27", "rose": "2026-27", "nuova": nuova])
    }

    static func offerta() -> String {
        json(["con": "Real Madrink", "do": ["Darko Vlasenić"], "ricevo": ["Rolando Lumbaku"], "ambigui": [String](),
              "analisi": propostaMigliore
                  .merging(["reparti": ["mio": ["P": 0.0, "D": 0.0, "C": 0.0, "A": 6.2], "loro": ["P": 0.0, "D": 0.0, "C": 1.1, "A": -2.0]],
                            "percentuale_mio": 1.4, "quotazione_do": 14, "quotazione_ricevo": 18]) { $1 }])
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

    /// Le risposte che cambiano con la domanda (`?q=`, `?a=&b=`, `?liberi=`): ricerca, confronto ed elenco dei giocatori, calcolati
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
        case "/api/confronto":
            guard let a = tutti.first(where: { $0.id == Int(domanda["a"] ?? "") }),
                  let b = tutti.first(where: { $0.id == Int(domanda["b"] ?? "") }) else { return nil }
            testo = confronto(a, b, modulo: domanda["modulo"], adesso: adesso)
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
            "/api/stato": stato(adesso: adesso),
            "/api/stato-dati": statoDati(adesso: adesso),
            "/api/squadre": squadre(),
            "/api/rosa": rosa(nomeMia, mia: true, adesso: adesso),
            "/api/scambi/proposte": scambi(),
            "/api/scambi/analizza": analisi(),
            "/api/mercato": mercato(),
            "/api/calendario": json(calendario(adesso: adesso)),
            "/api/osservati": osservati(adesso: adesso),
            "/api/formazione/testo": "Giornata \(giornata) - 3-4-3 (\(Formato.punti(punteggio(moduli[0].titolari))) punti attesi)",
            "/api/formazione/valuta": valutazione(),
            "/api/scelta": "null",   // nessuna scelta salvata: si vede la consigliata
            "/api/formazione": formazione(adesso: adesso),
            "/api/primo-avvio": json(["primo_avvio": NSNull(), "passi": ["server", "accesso", "rose", "squadra", "stemma", "pwa", "widget", "avvisi"]]),
            "/api/oggi": oggi(adesso: adesso),
            "/api/live": live(adesso: adesso),
            "/api/regole": regole(),
            "/api/avvisi": avvisi(),
            "/api/diario": diario(),
            "/api/backup": backup(),
            "/api/novita": novita(),
            "/api/foto-disponibili": json(["ids": Array(DemoImmagini.idConFoto).sorted()]),
            "/api/affidabilita": affidabilita(),
            "/api/movimenti": movimenti(),
            "/api/stagione": stagione(),
            "/api/scambi/da-testo": offerta(),
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
