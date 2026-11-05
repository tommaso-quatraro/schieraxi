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

    /// Provvisorio (issue #274): il cognome con i trattini morbidi. Da scrivere dopo il test rosso.
    static func sillabato(_ testo: String) -> String { testo }

    /// Provvisorio (issue #274): il nome con una parola per riga. Da scrivere dopo il test rosso.
    static func parolePerRiga(_ nome: String) -> String? { nil }

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
