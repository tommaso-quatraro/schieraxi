import Foundation

/// A che punto è «la tua scelta» della giornata: si confrontano gli undici mostrati con quelli salvati sul server
/// (`GET /api/scelta`). Logica pura, provata in `StatoSceltaTests`; la Formazione la mostra in una riga fissa.
enum StatoScelta: Equatable {
    /// Non si sa (lettura non riuscita, o si guarda un'altra squadra): non si dice niente, per non dire cose false.
    case sconosciuto
    /// Nessuna scelta salvata: si vede la consigliata (o uno stile).
    case consigliata
    /// Una modifica a mano mai salvata.
    case bozza
    /// La formazione mostrata è quella salvata (con l'ora del salvataggio, se il server la manda).
    case salvata(Date?)
    /// C'è una scelta salvata, ma quella mostrata è diversa: ci sono modifiche non salvate.
    case modificata(Date?)

    /// - Parameters:
    ///   - letta: la scelta della giornata è stata letta dal server (anche «nessuna»).
    ///   - salvati: i titolari salvati (nil = nessuna scelta salvata).
    ///   - manuale: i titolari della modifica a mano (nil = si vede la consigliata).
    /// L'ordine dei titolari non conta.
    static func calcola(letta: Bool, salvati: [Int]?, salvataIl: Date?, manuale: [Int]?) -> StatoScelta {
        guard letta else { return .sconosciuto }
        guard let salvati else { return manuale == nil ? .consigliata : .bozza }
        guard let manuale, Set(manuale) == Set(salvati) else { return .modificata(salvataIl) }
        return .salvata(salvataIl)
    }

    /// La frase della riga di stato (frase completa: la legge anche VoiceOver).
    func titolo(adesso: Date = Date()) -> String {
        switch self {
        case .sconosciuto: return ""
        case .consigliata: return "Stai vedendo la consigliata: non hai salvato una tua formazione."
        case .bozza: return "Modifica a mano non ancora salvata."
        case .salvata(let d):
            return "La tua formazione è salvata" + (d.map { " (\(Self.momento($0, adesso: adesso)))" } ?? "") + "."
        case .modificata(let d):
            return "Modifiche non salvate: " + (d.map { "la formazione salvata è di \(Self.momento($0, adesso: adesso))." }
                                                 ?? "la formazione salvata è un'altra.")
        }
    }

    /// Simbolo SF della riga (oltre al colore: lo stato non si legge dal solo colore).
    var simbolo: String {
        switch self {
        case .sconosciuto: return ""
        case .consigliata: return "info.circle"
        case .bozza, .modificata: return "pencil.circle.fill"
        case .salvata: return "checkmark.circle.fill"
        }
    }

    enum Tono: Equatable { case neutro, bene, attenzione }

    var tono: Tono {
        switch self {
        case .salvata: return .bene
        case .bozza, .modificata: return .attenzione
        case .consigliata, .sconosciuto: return .neutro
        }
    }

    /// C'è qualcosa da salvare (pulsante «Salva» in evidenza).
    var daSalvare: Bool {
        switch self {
        case .bozza, .modificata, .sconosciuto: return true
        case .consigliata, .salvata: return false
        }
    }

    // MARK: quando

    private static let italia = TimeZone(identifier: "Europe/Rome") ?? .current

    private static let ora: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.timeZone = italia
        f.dateFormat = "HH:mm"
        return f
    }()

    private static let giorno: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.timeZone = italia
        f.dateFormat = "EEE d MMM"
        return f
    }()

    /// «oggi alle 21:40», «ieri alle 09:05», «sab 31 ott alle 21:40» (ora italiana).
    static func momento(_ data: Date, adesso: Date = Date()) -> String {
        var calendario = Calendar(identifier: .gregorian)
        calendario.timeZone = italia
        let alle = "alle " + ora.string(from: data)
        if calendario.isDate(data, inSameDayAs: adesso) { return "oggi " + alle }
        if let ieri = calendario.date(byAdding: .day, value: -1, to: adesso), calendario.isDate(data, inSameDayAs: ieri) {
            return "ieri " + alle
        }
        return giorno.string(from: data) + " " + alle
    }
}

/// Il modulo («3-4-3») contato dai ruoli dei titolari: in modifica a mano si sa subito, senza aspettare il server.
enum ModuloTitolari {
    static func modulo(ruoli: [String]) -> String {
        let conta = { (r: String) in ruoli.filter { $0.uppercased() == r }.count }
        return "\(conta("D"))-\(conta("C"))-\(conta("A"))"
    }
}

/// Una scelta salvata vale ancora? 11 titolari diversi, tutti della rosa. Senza rosa (scheda mancante o vuota) non si
/// giudica: la scelta NON si cancella.
enum ValiditaScelta {
    enum Esito: Equatable { case valida, nonValida, nonSiSa }

    static func controlla(titolari: [Int], rosa: [String: Giocatore]?) -> Esito {
        guard let rosa, !rosa.isEmpty else { return .nonSiSa }
        let diversi = Set(titolari)
        guard diversi.count == 11, titolari.count == 11, diversi.allSatisfy({ rosa[String($0)] != nil }) else { return .nonValida }
        return .valida
    }

    /// Il codice d'errore del server per una formazione che non si può valutare (non 11 della rosa, modulo non ammesso).
    static let codiceNonValida = "formazione_non_valida"
}
