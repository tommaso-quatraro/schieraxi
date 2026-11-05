import Foundation

/// Come si legge una pedina del campo, a parole: «gioca 85%», «vs NAP» (in casa) / «@ NAP» (in trasferta), e la frase per VoiceOver.
/// Logica pura (provata in `LetturaPedinaTests`); il disegno è in `Support/CampoFormazione.swift`.
enum LetturaPedina {
    /// Sotto questa probabilità di giocare la pedina avvisa (icona e colore): la stessa soglia delle barre della web app.
    static let sogliaIncerto = 0.7

    static func incerto(_ pVoto: Double?) -> Bool {
        guard let pVoto else { return false }
        return pVoto < sogliaIncerto
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

    /// La frase completa per VoiceOver: «Rossi, difensore, fantavoto atteso 6,5, gioca all'85 per cento, avversario Napoli, in casa».
    static func voce(nome: String, ruolo: String, fvAtteso: Double?, pVoto: Double?, avversario: String?, inCasa: Bool?) -> String {
        var parti = [nome, ruolo, "fantavoto atteso \(Formato.punti(fvAtteso))"]
        if let pVoto {
            parti.append("gioca al \(Formato.percento(pVoto)) per cento" + (incerto(pVoto) ? ", non è sicuro di giocare" : ""))
        }
        if let avv = nomeSquadra(avversario) {
            parti.append("avversario \(avv)" + (inCasa == true ? ", in casa" : inCasa == false ? ", in trasferta" : ""))
        }
        return parti.joined(separator: ", ")
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
