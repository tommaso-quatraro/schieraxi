import Foundation

// Il fantavoto atteso: il numero firma di SchieraXI. Qui le frasi (pure, provate dai test) di «Perché questo numero»
// e di «Quanto ci abbiamo preso» del Diario. Parole come nella web app; niente parole da scommessa.

/// Le parole del fantavoto atteso, uguali in ogni schermata.
enum FantavotoAtteso {
    static let nome = "Fantavoto atteso"

    /// «+1,1» o «−0,4» (con il vero segno meno), in fantavoti o punti. Sotto 0,05 due cifre, per non scrivere «+0,0».
    static func conSegno(_ valore: Double) -> String {
        let cifre = abs(valore) < 0.05 && valore != 0 ? 2 : 1
        return (valore < 0 ? "−" : "+") + Formato.decimali(abs(valore), cifre: cifre)
    }

    /// La stessa cosa a parole, per VoiceOver: «più 1,1», «meno 0,4».
    static func conSegnoVoce(_ valore: Double) -> String {
        let cifre = abs(valore) < 0.05 && valore != 0 ? 2 : 1
        return (valore < 0 ? "meno " : "più ") + Formato.decimali(abs(valore), cifre: cifre)
    }
}

/// «Perché questo numero»: al massimo tre motivi del fantavoto atteso, come li manda il server (`perche_numero`),
/// e il riferimento (il giocatore medio del ruolo). nil = server vecchio o niente da dire: il riquadro non si mostra.
struct PercheNumero: Equatable {
    enum Verso: Equatable {
        /// Alza il numero rispetto al giocatore medio del ruolo.
        case su
        /// Lo abbassa.
        case giu
        /// «gioca N%»: non cambia il fantavoto «se gioca», ma va detto (cambia i punti attesi).
        case avviso
        /// Un motivo senza numero che non è «gioca» (server più nuovo o dato strano).
        case neutro
    }

    struct Riga: Equatable, Identifiable {
        let id: Int
        let chiave: String
        /// La frase del server con la prima lettera maiuscola.
        let testo: String
        /// «+1,1», «−0,4»; nil senza numero.
        let effetto: String?
        let verso: Verso
        /// Frase completa per VoiceOver.
        let voce: String
    }

    /// `perche.titolo` del catalogo comune con la web.
    static let titolo = Catalogo.Perche.titolo
    static let massimoMotivi = 3

    let righe: [Riga]
    /// Il riferimento: «Un giocatore medio del suo ruolo ha 6,2…».
    let nota: String

    init?(motivi: [MotivoNumero]?, mediaRuolo: Double?) {
        guard let motivi else { return nil }
        let media = mediaRuolo.flatMap { $0.isFinite ? $0 : nil }
        var righe: [Riga] = []
        for m in motivi {
            guard righe.count < Self.massimoMotivi else { break }
            let testo = (m.testo ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !testo.isEmpty else { continue }
            let chiave = m.chiave ?? "altro"
            let frase = testo.prefix(1).uppercased() + testo.dropFirst()
            let effetto = m.effetto.flatMap { $0.isFinite ? $0 : nil }
            let verso: Verso
            let voce: String
            if let e = effetto {
                verso = e < 0 ? .giu : .su
                voce = "\(FantavotoAtteso.conSegnoVoce(e)): \(testo)"
            } else {
                verso = chiave == "gioca" ? .avviso : .neutro
                voce = chiave == "gioca" ? "Attenzione: \(testo)" : frase
            }
            righe.append(Riga(id: righe.count, chiave: chiave, testo: frase, effetto: effetto.map(FantavotoAtteso.conSegno), verso: verso, voce: voce))
        }
        if righe.isEmpty && media == nil { return nil }
        self.righe = righe
        // le frasi della web (`perche.nessuno`, `perche.rispetto`); senza la media del ruolo una frase solo dell'iPhone
        if righe.isEmpty, let media {
            nota = Catalogo.Perche.nessuno(n: Formato.punti(media))
        } else if let media {
            nota = Catalogo.Perche.rispetto(n: Formato.punti(media))
        } else {
            nota = "I numeri sono le differenze rispetto a un giocatore medio del suo ruolo."
        }
    }

    init?(_ g: Giocatore) {
        // Un assente non ha un fantavoto atteso da spiegare.
        guard g.assente != true else { return nil }
        self.init(motivi: g.motiviNumero, mediaRuolo: g.mediaRuolo)
    }
}
