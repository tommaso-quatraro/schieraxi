import Foundation

/// Come si legge una pedina del campo, a parole, come la web (#616): il fantavoto atteso, «gioca N%» solo sotto l'80%, lo stato a
/// parole, e la frase per VoiceOver (`contenuto`). Logica pura (provata in `PedinaComeLaWebTests`); il disegno è in
/// `Support/CampoFormazione.swift`.
enum LetturaPedina {
    /// Quanto è probabile che giochi, con la soglia unica di `SogliaGioca` (#673): la stessa della scheda, delle righe e della
    /// web (sotto l'80% arancio, sotto il 50% rosso, sul numero che si legge). nil senza probabilità.
    static func livello(_ pVoto: Double?) -> SogliaGioca.Livello? {
        guard let pVoto else { return nil }
        return SogliaGioca.livello(pVoto)
    }

    /// Sotto l'80% la pedina avvisa (icona e colore), come la scheda; senza probabilità no.
    static func incerto(_ pVoto: Double?) -> Bool {
        guard let pVoto else { return false }
        return SogliaGioca.daMostrare(pVoto)
    }

    /// «gioca 85%» (nil se il server non manda la probabilità).
    static func gioca(_ pVoto: Double?) -> String? {
        guard let pVoto else { return nil }
        return "gioca \(Formato.percento(pVoto))%"
    }

    /// «vs» in casa, «@» in trasferta, niente se non si sa.
    static func prefisso(inCasa: Bool?) -> String? {
        switch inCasa {
        case true?: return "vs"
        case false?: return "@"
        case nil: return nil
        }
    }

    /// Il nome della squadra per VoiceOver e legenda: «napoli» → «Napoli»; una sigla resta com'è.
    static func nomeSquadra(_ squadra: String?) -> String? {
        guard let s = squadra?.trimmingCharacters(in: .whitespaces), !s.isEmpty else { return nil }
        guard ColoriSquadra.sigle[s.lowercased()] != nil else { return s }
        return s.prefix(1).uppercased() + s.dropFirst().lowercased()
    }

    /// Un pezzo di testo sotto il cognome della pedina e come si mostra.
    struct Pezzo: Equatable, Sendable {
        enum Tono: Equatable, Sendable {
            /// «gioca N%» fra 50 e 79: pillola arancio.
            case medio
            /// «gioca N%» sotto 50, o uno stato che dice che non gioca («Infortunato»): pillola rossa.
            case basso
            /// Una parola senza pillola: «In dubbio», lo stato della partita, quando gioca.
            case parola
        }
        let testo: String
        let tono: Tono
    }

    /// Cosa mostra la pedina, come `pedina` di app.js (#616): nel disco il fantavoto atteso (a partita finita quello preso), sotto il
    /// cognome «gioca N%» solo sotto l'80%, lo stato a parole («In dubbio», «Infortunato», «Squalificato», «Fuori», «Rinviata»), a
    /// partita cominciata il suo stato finché non c'è il voto, a formazione chiusa quando gioca chi deve ancora giocare. Niente
    /// avversario: sta nella scheda, a un tocco. `adesso`: per «oggi», «domani» della data.
    struct Contenuto: Equatable {
        /// Il numero nel disco.
        let valore: Double?
        /// Il numero è l'atteso mentre la partita è cominciata senza voto, è rinviata o, a formazione chiusa, deve ancora giocare: il
        /// disco è vuoto (solo il bordo), come la classe `attesa` della pedina della web; pieno con il voto preso e prima della scadenza.
        let attesa: Bool
        let pezzi: [Pezzo]
        /// La frase per VoiceOver, come `vocePedina` della web: «Rossi, fantavoto atteso 6,8, gioca al 45 per cento, In dubbio».
        let voce: String
    }

    static func contenuto(_ g: Giocatore, adesso: Date = Date()) -> Contenuto {
        let partita = Self.esito(g)
        let stato: ParolaStato? = partita == nil ? ParolaStato(g) : nil
        let preso: Double? = partita?.fv
        let attesa: String? = preso == nil ? partita?.testo : nil              // cominciata, senza voto (o rinviata): lo stato
        let daGiocare = partita == nil && g.statoPartita == "da_giocare"       // formazione chiusa, la sua partita non è cominciata
        let gioca = partita == nil && !daGiocare && !(stato?.nonGiocaDiSicuro ?? false) && SogliaGioca.daMostrare(g.pVoto)
        let quando: String? = daGiocare ? Quando.data(g.dataPartita).map { Quando.relativa($0, adesso: adesso) } : nil
        var pezzi: [Pezzo] = []
        if gioca {
            pezzi.append(Pezzo(testo: "gioca \(Formato.percento(SogliaGioca.letta(g.pVoto)))%",
                               tono: SogliaGioca.livello(g.pVoto) == .basso ? .basso : .medio))
        }
        if let stato { pezzi.append(Pezzo(testo: stato.testo, tono: stato.nonGiocaDiSicuro ? .basso : .parola)) }
        if let attesa { pezzi.append(Pezzo(testo: attesa, tono: .parola)) }
        if let quando { pezzi.append(Pezzo(testo: quando, tono: .parola)) }
        // la frase per VoiceOver: le stesse cose che si vedono
        var frase: [String] = [g.nome, preso != nil ? (partita?.testo ?? "") : Catalogo.Formazione.voceFv(fv: Formato.punti(g.fvAtteso))]
        if let attesa { frase.append(attesa) }
        if gioca { frase.append(voceGioca(Formato.percento(g.pVoto))) }
        if let stato { frase.append(stato.testo) }
        if let quando { frase.append(quando) }
        return Contenuto(valore: preso ?? g.fvAtteso, attesa: (partita != nil && preso == nil) || daGiocare, pezzi: pezzi,
                         voce: frase.filter { !$0.isEmpty }.joined(separator: ", "))
    }

    /// La partita al posto di «gioca N%» (`esitoPedina` della web): a partita cominciata il fantavoto preso (`fv`) o lo stato; prima,
    /// la partita rinviata. nil se la partita non è cominciata e non è rinviata.
    static func esito(_ g: Giocatore) -> (fv: Double?, testo: String?)? {
        if let partita = g.esitoPartita { return (partita.fv, partita.testo) }
        guard let rinviata = g.esitoPedina else { return nil }
        return (nil, rinviata)
    }

    /// «gioca al 62 per cento», «gioca all'85 per cento» (`formazione.voce_gioca`, `formazione.voce_gioca_v`).
    static func voceGioca(_ percento: Int) -> String {
        let vocale = percento == 1 || percento == 8 || percento == 11 || (80...89).contains(percento)
        return vocale ? Catalogo.Formazione.voceGiocaV(p: String(percento)) : Catalogo.Formazione.voceGioca(p: String(percento))
    }

    /// Il trattino morbido (U+00AD): non si vede, dice al testo dove può andare a capo dentro una parola e lì disegna «-».
    static let trattinoMorbido = "\u{00AD}"

    /// Il nome con i trattini morbidi nei punti in cui l'italiano va a capo («Castelvecchi» → «Ca·stel·vec·chi», dove «·» è il
    /// trattino morbido): sul campo stretto il cognome va a capo con il trattino, come la web (`hyphens: auto`), invece di
    /// spezzarsi a una lettera qualsiasi. `Text` di SwiftUI non sillaba da solo (ignora `hyphenationFactor`) ma va a capo dove
    /// trova il trattino morbido. Se il telefono non sa sillabare l'italiano il nome resta com'è (e va a capo tra le lettere).
    /// Solo per il disegno: VoiceOver legge il nome del server (`voce`).
    static func sillabato(_ testo: String) -> String {
        let lingua = NSLocale(localeIdentifier: "it_IT") as CFLocale
        guard !testo.isEmpty, CFStringIsHyphenationAvailableForLocale(lingua) else { return testo }
        // una parola alla volta: gli spazi restano dove sono
        return testo.components(separatedBy: " ").map { sillabaParola($0, lingua: lingua) }.joined(separator: " ")
    }

    /// I trattini morbidi in una parola sola. Mai una lettera sola prima del primo trattino o dopo l'ultimo («a-» o «-o»).
    private static func sillabaParola(_ parola: String, lingua: CFLocale) -> String {
        let stringa = parola as CFString
        let lunghezza = CFStringGetLength(stringa)
        guard lunghezza >= 4 else { return parola }
        let tutto = CFRange(location: 0, length: lunghezza)
        // i punti dal fondo all'inizio: inserendo i trattini in quest'ordine le posizioni ancora da usare non si spostano
        var punti: [CFIndex] = []
        var prima = lunghezza
        while prima > 0 {
            let punto = CFStringGetHyphenationLocationBeforeIndex(stringa, prima, tutto, 0, lingua, nil)
            guard punto != kCFNotFound, punto > 0, punto < prima else { break }
            if punto >= 2, lunghezza - punto >= 2 { punti.append(punto) }
            prima = punto
        }
        let risultato = NSMutableString(string: parola)
        for punto in punti { risultato.insert(trattinoMorbido, at: punto) }
        return risultato as String
    }

    /// Il nome con una parola per riga («Hamit Çalvaroğlu» → «Hamit» sopra «Çalvaroğlu»): sul campo si prova prima di spezzare
    /// le parole, così una parola che ci sta intera non va a capo con il trattino. nil con una parola sola.
    static func parolePerRiga(_ nome: String) -> String? {
        let parole = nome.split(separator: " ")
        guard parole.count > 1 else { return nil }
        return parole.joined(separator: "\n")
    }

    /// Il testo del distintivo va scuro o chiaro secondo il colore di fondo (il contrasto più alto, come WCAG).
    static func testoScuro(suEsadecimale hex: String) -> Bool {
        var n: UInt64 = 0
        guard Scanner(string: hex).scanHexInt64(&n) else { return false }
        func lineare(_ c: UInt64) -> Double {
            let v = Double(c) / 255
            return v <= 0.03928 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4)
        }
        let l = 0.2126 * lineare((n >> 16) & 0xff) + 0.7152 * lineare((n >> 8) & 0xff) + 0.0722 * lineare(n & 0xff)
        // contrasto con il nero (l + 0,05) / 0,05 contro quello con il bianco 1,05 / (l + 0,05)
        return (l + 0.05) / 0.05 > 1.05 / (l + 0.05)
    }
}
