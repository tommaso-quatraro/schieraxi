import Foundation

/// La pagina Giornate (#673, passo 2; la web con #617/#671, `mostraGiornate` di `fanta/web/app.js`): una riga per giornata finita,
/// dalla più recente, con i punti fatti e attesi della formazione che conta e, al tocco, gli 11 con il fantavoto atteso e quello
/// preso. Il confronto «tu contro la consigliata» c'è solo dove la consigliata è quella mostrata prima della scadenza
/// (`consigliata.origine == "mostrata"`, #614): un server di prima non manda `origine` e la sua consigliata è rifatta a giornata
/// finita, e lì il confronto non si mostra. Numeri, nomi e frasi vengono da `GET /api/diario`: qui si sceglie cosa mostrare, non si
/// calcola. Logica pura, provata in `GiornateTests`.
enum FormazioneCheConta: Equatable, Sendable {
    /// La tua formazione (`schierata`).
    case tua
    /// La consigliata salvata da sola alla scadenza, se non avevi scelto (`automatica`).
    case automatica
    /// La consigliata (`consigliata`), con i suoi punti.
    case consigliata
}

extension VoceDiario {
    /// La formazione che conta per la giornata, come `formazioneDi` della web: la tua, poi la copia automatica, poi la consigliata.
    var cheConta: (tipo: FormazioneCheConta, formazione: FormazioneDiario?) {
        if let schierata { return (.tua, schierata) }
        if let automatica { return (.automatica, automatica) }
        return (.consigliata, consigliata)
    }

    /// La consigliata è quella mostrata prima della scadenza (`conMostrata` della web).
    var conMostrata: Bool { consigliata?.origine == "mostrata" }
}

/// Una riga dell'elenco: nome della giornata, la frase di chi sono i punti, i punti fatti grandi e «punti (attesi 71,7)».
struct RigaGiornata: Identifiable, Equatable, Sendable {
    /// Stagione e giornata (`VoceDiario.id`).
    let id: String
    /// «Giornata 8 · 11ª di Serie A».
    let nome: String
    /// La stagione, solo se nella pagina ce n'è più di una.
    let stagione: String?
    let stato: String
    /// I punti fatti («74,5», «–» se mancano).
    let punti: String
    /// «punti (attesi 71,7)», o «punti» senza gli attesi.
    let attesi: String
    /// La riga intera per VoiceOver: «Giornata 8, 11ª di Serie A: 74,5 punti (attesi 71,7). La tua formazione.»
    let voce: String
}

/// Un titolare della giornata aperta: nome, ruolo, fantavoto atteso e preso.
struct TitolareGiornata: Identifiable, Equatable, Sendable {
    let id: Int
    let nome: String
    let ruolo: String
    /// Il fantavoto atteso mostrato prima della scadenza (`istantanea`), se no quello rifatto (`giocatori[].fv_atteso`); «–» se manca.
    let atteso: String
    /// Il fantavoto preso, «senza voto» se non l'ha preso, «–» se il server non lo dice.
    let preso: String
    let senzaVoto: Bool

    /// «Rossi, Attaccante: atteso 6,8, preso 7,5.»
    var voce: String {
        "\(nome), \(nomeRuolo(ruolo)): \(Catalogo.Giornate.colAtteso.lowercased()) \(atteso), \(Catalogo.Giornate.colPreso.lowercased()) \(preso)."
    }
}

/// La giornata aperta: gli 11 della formazione che conta, cosa hai cambiato rispetto alla consigliata e la correzione.
struct DettaglioGiornata: Equatable, Sendable {
    /// «La tua formazione (3-4-3)», «La consigliata alla scadenza (…)», «La consigliata (…)», «La consigliata rifatta… (…)».
    let titolo: String
    /// Sotto il titolo, per la consigliata rifatta a giornata finita.
    let nota: String?
    let titolari: [TitolareGiornata]
    /// «Al posto di X hai messo Y.» (solo con la consigliata mostrata).
    let cambi: String?
    /// La tua formazione senza la consigliata di allora: il confronto non c'è, e lo si dice.
    let senzaConfronto: String?
    /// «Non è quello che ho schierato»: non per le stagioni passate (`modificabile: false`).
    let correggibile: Bool
}

/// Tutto quello che la pagina mostra, letto da una risposta di `GET /api/diario`.
struct PaginaGiornate {
    /// In cima: «Finora il fantavoto atteso sbaglia in media di 1,4 punti a giocatore.» (nil senza il numero).
    let precisione: String?
    /// Il titolo della parte che si apre: «Dettagli», o «Quanto ci abbiamo preso» se manca la riga sopra. Nil senza dettagli.
    let titoloDettagli: String?
    /// I numeri di «Quanto ci abbiamo preso»; la voce «la consigliata contro la tua» solo se una giornata ha la consigliata mostrata.
    let dettagli: TestoPrecisione?
    let righe: [RigaGiornata]
    /// La frase della pagina senza giornate, secondo `motivo_vuoto`; nil se le giornate ci sono.
    let vuoto: String?

    private let voci: [VoceDiario]
    private let scelte: [SceltaGiornata]
    private let stagioni: Bool

    init(_ d: DiarioRisposta) {
        let voci = d.giornate ?? []
        let scelte = d.scelteTue?.perGiornata ?? []
        let stagioni = Set(voci.map { $0.stagione ?? "" }).count > 1
        self.voci = voci
        self.scelte = scelte
        self.stagioni = stagioni
        let errore = d.precisione?.fantavoto?.erroreMedio.flatMap { $0.isFinite ? $0 : nil }
        precisione = errore.map { Catalogo.Giornate.precisione(e: Formato.punti($0)) }
        let testo = TestoPrecisione(d.precisione, conConfronto: voci.contains { $0.conMostrata })
        dettagli = testo
        titoloDettagli = testo == nil ? nil : (errore != nil ? Catalogo.Giornate.dettagli : Catalogo.Diario.afTitolo)
        if voci.isEmpty {
            switch d.motivoVuoto {
            case "squadra": vuoto = Catalogo.Giornate.vuotoSquadra(voce: Catalogo.Lega.miaSquadra)
            case "giornate": vuoto = Catalogo.Giornate.vuotoGiornate
            case "calcolo": vuoto = Catalogo.Giornate.vuotoCalcolo
            default: vuoto = Catalogo.Giornate.vuoto
            }
        } else {
            vuoto = nil
        }
        righe = voci.map { Self.riga($0, scelte: scelte, stagioni: stagioni) }
    }

    /// La voce del diario di una riga.
    func voce(_ id: String) -> VoceDiario? { voci.first { $0.id == id } }

    /// La riga da aprire per una giornata di Serie A («Com'è andata», un indirizzo): la più recente, cioè la stagione in corso.
    func id(giornata: Int) -> String? { voci.first { $0.giornata == giornata }?.id }

    /// Gli 11 della giornata `id`; nil se non c'è.
    func dettaglio(_ id: String) -> DettaglioGiornata? {
        voce(id).map { Self.dettaglio($0, scelte: scelte) }
    }

    // MARK: regole uguali alla web

    /// La voce di `scelte_tue.per_giornata` della giornata (`sceltaDi`): 11 diversi dai consigliati, con i nomi e la differenza.
    private static func scelta(_ v: VoceDiario, in scelte: [SceltaGiornata]) -> SceltaGiornata? {
        scelte.first { $0.stagione == v.stagione && $0.giornata == v.giornata }
    }

    /// Sotto la riga (`statoGiornata`): hai schierato la consigliata, o quanti cambi tuoi e quanto sono valsi (solo con la
    /// consigliata mostrata); altrimenti di chi sono i punti.
    static func stato(_ v: VoceDiario, scelte: [SceltaGiornata]) -> String {
        let tipo = v.cheConta.tipo
        if tipo == .tua && v.conMostrata {
            guard let s = scelta(v, in: scelte) else { return Catalogo.Giornate.haiConsigliata }
            let n = s.haiScelto?.count ?? 0
            if n > 0, let diff = s.differenza, diff.isFinite {
                return diff == 0 ? Catalogo.Giornate.cambiPari(n) : Catalogo.Giornate.cambi(n, d: Formato.conSegno(diff))
            }
        }
        switch tipo {
        case .tua: return Catalogo.Giornate.tua
        case .automatica: return Catalogo.Giornate.automatica
        case .consigliata: return Catalogo.Giornate.nonSalvata
        }
    }

    private static func riga(_ v: VoceDiario, scelte: [SceltaGiornata], stagioni: Bool) -> RigaGiornata {
        let f = v.cheConta.formazione
        let punti = Formato.punti(f?.reale)
        let attesi = f?.atteso.map { Catalogo.Formazione.puntiEAttesi(n: Formato.punti($0)) } ?? Catalogo.Formazione.punti
        let frase = Self.stato(v, scelte: scelte)
        let stagione = stagioni ? v.stagione : nil
        let nomeVoce = (v.nomeGiornata?.voce ?? v.titolo) + (stagione.map { ", \($0)" } ?? "")
        return RigaGiornata(id: v.id, nome: v.titolo, stagione: stagione, stato: frase, punti: punti, attesi: attesi,
                            voce: "\(nomeVoce): \(punti) \(attesi). \(frase)")
    }

    static func dettaglio(_ v: VoceDiario, scelte: [SceltaGiornata]) -> DettaglioGiornata {
        let conta = v.cheConta
        let tipo = conta.tipo, f = conta.formazione
        let mostrata = v.conMostrata, origine = v.consigliata?.origine
        let modulo = f?.modulo ?? ""
        let titolo: String
        switch tipo {
        case .tua: titolo = Catalogo.Giornate.formazioneTua(modulo: modulo)
        case .automatica: titolo = Catalogo.Giornate.formazioneAutomatica(modulo: modulo)
        case .consigliata:
            titolo = mostrata ? Catalogo.Giornate.formazioneConsigliata(modulo: modulo) : Catalogo.Giornate.formazioneRifatta(modulo: modulo)
        }
        // l'atteso mostrato prima della scadenza (titolari e panchina dell'istantanea), se no quello rifatto con i dati di prima
        var mostrati: [Int: Double] = [:]
        for x in (v.istantanea?.titolari ?? []) + (v.istantanea?.panchina ?? []) {
            if let id = x.id, let a = x.fvAtteso, mostrati[id] == nil { mostrati[id] = a }
        }
        var numeri: [Int: NumeriGiocatoreDiario] = [:]
        for n in v.giocatori ?? [] {
            if let id = n.id, numeri[id] == nil { numeri[id] = n }
        }
        let titolari = (f?.titolari ?? []).enumerated().map { i, x -> TitolareGiornata in
            let n = x.id.flatMap { numeri[$0] }
            let atteso = x.id.flatMap { mostrati[$0] } ?? n?.fvAtteso
            let senza = n != nil && n?.fv == nil
            return TitolareGiornata(id: x.id ?? -(i + 1), nome: x.nome ?? "–", ruolo: x.ruolo ?? "",
                                    atteso: Formato.punti(atteso), preso: senza ? Catalogo.Giornate.senzaVoto : Formato.punti(n?.fv),
                                    senzaVoto: senza)
        }
        var cambi: String?
        var senzaConfronto: String?
        if tipo == .tua && mostrata, let s = scelta(v, in: scelte), let dentro = s.haiScelto, !dentro.isEmpty {
            cambi = Catalogo.Giornate.alPosto(dentro: dentro.joined(separator: ", "), fuori: (s.consigliava ?? []).joined(separator: ", "))
        } else if tipo == .tua && origine == "ricostruita" {
            senzaConfronto = Catalogo.Giornate.senzaConfronto
        }
        let nota = tipo == .consigliata && origine == "ricostruita" ? Catalogo.Giornate.rifattaNota : nil
        return DettaglioGiornata(titolo: titolo, nota: nota, titolari: titolari, cambi: cambi, senzaConfronto: senzaConfronto,
                                 correggibile: v.siPuoCambiare)
    }
}
