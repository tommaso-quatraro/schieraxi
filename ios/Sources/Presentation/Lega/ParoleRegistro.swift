import Foundation

/// Le parole del registro delle giornate in Stato dei dati (#344), uguali alla web: `cartaRegistro` di `fanta/web/app.js` e i testi
/// `sd.reg_*` del catalogo comune (file generato `Catalogo+Sd.swift`; `RegistroGiornateTests` prova le frasi composte). Soglie e verdetto («regge») arrivano dal server:
/// qui si scrivono e basta, non si ricalcolano.
enum ParoleRegistro {
    /// Le tre misure del registro, nell'ordine della web (sul server I1, I2, I3).
    enum Misura: CaseIterable {
        /// Errore del fantavoto atteso contro quello della fantamedia (I1).
        case fantavoto
        /// «Gioca N%» contro chi ha giocato davvero (I2).
        case gioca
        /// Punti veri dentro la fascia «8 volte su 10» (I3).
        case fascia
    }

    /// Accanto al nome della misura: regge, non regge, quante giornate servono ancora per dirlo, o nessun dato.
    enum Esito: Equatable {
        case regge
        case nonRegge
        case servono(Int)
        case senzaDati

        var testo: String {
            switch self {
            case .regge: return Catalogo.Sd.regRegge
            case .nonRegge: return Catalogo.Sd.regNonRegge
            case .servono(let n): return Catalogo.Sd.regServono(n)
            case .senzaDati: return Catalogo.Sd.nessunDato
            }
        }
    }

    static let titolo = Catalogo.Sd.regTitolo
    static let spiega = Catalogo.Sd.regSpiega
    static let nessuna = Catalogo.Sd.regNessuna
    static let titoloPerse = Catalogo.Sd.regPerse
    static let spiegaPerse = Catalogo.Sd.regPerseSpiega

    static func media(giornate n: Int) -> String { Catalogo.Sd.regMedia(n) }

    /// La riga sotto il titolo: su quante giornate è la media, o che non ce n'è ancora nessuna misurata.
    static func sottotitolo(_ r: StatoDati.Registro) -> String {
        let n = r.giornate ?? 0
        return n > 0 ? media(giornate: n) : nessuna
    }

    static func nome(_ misura: Misura) -> String {
        switch misura {
        case .fantavoto: return Catalogo.Sd.regI1
        case .gioca: return Catalogo.Sd.regI2
        case .fascia: return Catalogo.Sd.regI3
        }
    }

    static func esito(_ misura: Misura, di r: StatoDati.Registro) -> Esito {
        let regge: Bool?
        switch misura {
        case .fantavoto: regge = r.regge?.i1
        case .gioca: regge = r.regge?.i2
        case .fascia: regge = r.regge?.i3
        }
        return esito(verdetto: r.verdetto, regge: regge, giornate: r.giornate, finestra: r.finestra)
    }

    /// Senza verdetto (meno giornate della finestra) conta solo quante ne mancano; con il verdetto vale `regge` del server.
    static func esito(verdetto: Bool?, regge: Bool?, giornate: Int?, finestra: Int?) -> Esito {
        guard verdetto == true else {
            let tutte = finestra.flatMap { $0 > 0 ? $0 : nil } ?? 8
            return .servono(max(1, tutte - (giornate ?? 0)))
        }
        switch regge {
        case true?: return .regge
        case false?: return .nonRegge
        case nil: return .senzaDati
        }
    }

    /// Sotto il nome: la media e la soglia (più i due errori per il fantavoto, l'errore medio delle percentuali per «gioca N%»).
    static func dettaglio(_ misura: Misura, di r: StatoDati.Registro) -> String {
        let s = r.soglie
        switch misura {
        case .fantavoto:
            return Catalogo.Sd.regI1Riga(f: Formato.decimali(r.erroreFantamedia, cifre: 2), m: Formato.decimali(r.erroreModello, cifre: 2),
                                         s: percento(s?.i1, segno: true), v: percento(r.i1, segno: true))
        case .gioca:
            return Catalogo.Sd.regI2Riga(c: punti(r.calibrazione, per: 100), e: errore(r.erroreMedio),
                                         sc: cifra(s?.i2Calibrazione, per: 100), se: errore(s?.i2ErroreMedio))
        case .fascia:
            return Catalogo.Sd.regI3Riga(max: percento(s?.i3Massimo), min: percento(s?.i3Minimo), v: percento(r.copertura))
        }
    }

    /// Le giornate non salvate in tempo, dalla più recente (come le manda il server).
    static func perse(_ r: StatoDati.Registro) -> [StatoDati.Registro.Giornata] {
        (r.perGiornata ?? []).filter { !($0.persa ?? "").isEmpty }
    }

    /// «9ª giornata di Serie A · 2026-27» (`sd.reg_giornata` della web): il numero è quello della Serie A, non della lega.
    static func giornata(_ g: StatoDati.Registro.Giornata) -> String {
        Catalogo.Sd.regGiornata(g: g.giornata.map(TempiLega.serieA) ?? "", s: g.stagione ?? "")
    }

    /// Un numero (moltiplicato per `per`) con una cifra decimale e senza «,0», come `regCifra` della web: «10», «3,4», «−3».
    static func cifra(_ x: Double?, per: Double = 1, segno: Bool = false) -> String {
        guard let x, x.isFinite else { return "–" }
        let testo = segno ? Formato.conSegno(x * per, cifre: 1) : Formato.decimali(x * per, cifre: 1)
        return testo.hasSuffix(",0") ? String(testo.dropLast(2)) : testo
    }

    /// Un numero di punti scritto come `cifra`, con «punto» al singolare: «1 punto», «2,1 punti», «– punti».
    static func punti(_ x: Double?, per: Double = 1) -> String {
        let testo = cifra(x, per: per)
        return testo == "1" ? "1 punto" : testo + " punti"
    }

    /// L'errore medio delle percentuali di «gioca N%» in punti, già calcolato dal server (#821), con due cifre come `regErrore`
    /// della web: 31,62 → «31,62», 30,2 → «30,20»; «–» se manca (l'app non lo ricava dal Brier).
    static func errore(_ x: Double?) -> String {
        Formato.decimali(x, cifre: 2)
    }

    /// Una quota come percentuale, come `regPerc` della web: 0,057 → «5,7%», −0,03 con il segno → «−3%».
    static func percento(_ x: Double?, segno: Bool = false) -> String {
        let testo = cifra(x, per: 100, segno: segno)
        return testo == "–" ? testo : testo + "%"
    }
}
