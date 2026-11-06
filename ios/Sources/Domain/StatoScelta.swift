import Foundation

/// A che punto è «la tua scelta» della giornata: si confrontano gli undici mostrati con quelli salvati sul server
/// (`GET /api/scelta`). Stati e frasi sono quelli della web (`statoScelta` e `rigaStatoScelta` di `fanta/web/app.js`, frasi
/// `formazione.stato_*` di `testi.js`). Logica pura, provata in `RigaStatoComeWebTests`; la Formazione la mostra in una riga fissa.
enum StatoScelta: Equatable {
    /// Non si sa (lettura non riuscita, o si guarda un'altra squadra): non si dice niente, per non dire cose false.
    case sconosciuto
    /// Nessuna scelta salvata: si vede la consigliata.
    case consigliata
    /// Nessuna scelta salvata e si vede un altro stile o un altro modulo: non è la consigliata (web: «altra»).
    case altra
    /// Una modifica a mano mai salvata (web: «mano»).
    case bozza
    /// La formazione mostrata è quella salvata (con l'ora del salvataggio, se il server la manda).
    case salvata(Date?)
    /// C'è una scelta salvata, ma quella mostrata è diversa: ci sono modifiche non salvate.
    case modificata(Date?)
    /// La scelta salvata non vale più (rosa o regole cambiate): non si cancella da sola, si rifà o si torna alla consigliata
    /// (web: «non_valida»).
    case nonValida
    /// Giornata chiusa (scadenza passata, `iniziata` del server): niente più da salvare né da cambiare. `tua`: c'è una scelta
    /// salvata, ed è quella che vale. Come lo stato «chiusa» della web, vale anche prima di aver letto la scelta.
    case chiusa(tua: Bool)
    /// Giornata chiusa e la scelta salvata non si può schierare (`stato_scelta: "non_valida"` del server, o non valida
    /// rileggendola): vale la consigliata, che è anche quella mostrata (web: `formazione.stato_chiusa_non_valida`).
    case chiusaNonValida

    /// - Parameters:
    ///   - letta: la scelta della giornata è stata letta dal server (anche «nessuna»).
    ///   - salvati: i titolari salvati (nil = nessuna scelta salvata).
    ///   - manuale: i titolari della modifica a mano (nil = si vede la consigliata, o uno stile o un modulo).
    ///   - chiusa: la giornata è chiusa (viene prima di tutto il resto, come sulla web).
    ///   - nonValida: la scelta salvata non vale più (lo dice il server con `formazione_non_valida` o, a giornata chiusa, con
    ///     `stato_scelta`; o non è nella rosa).
    ///   - altra: senza modifica a mano si vede un altro stile o un altro modulo.
    /// L'ordine dei titolari non conta.
    static func calcola(letta: Bool, salvati: [Int]?, salvataIl: Date?, manuale: [Int]?, mostrati: [Int]? = nil, chiusa: Bool = false,
                        nonValida: Bool = false, altra: Bool = false) -> StatoScelta {
        if chiusa { return nonValida ? .chiusaNonValida : .chiusa(tua: letta && salvati != nil) }
        guard letta else { return .sconosciuto }
        guard let salvati else { return manuale != nil ? .bozza : altra ? .altra : .consigliata }
        // dopo «Modifica a mano» si può salvare la nuova («modificata»); gli undici che non valgono più non sono «salvata»
        if nonValida, manuale.map({ Set($0) == Set(salvati) }) ?? true { return .nonValida }
        guard let manuale, Set(manuale) == Set(salvati) else { return .modificata(salvataIl) }
        return .salvata(salvataIl)
    }

    /// La frase della riga di stato, uguale alla web.
    func titolo(adesso: Date = Date()) -> String {
        switch self {
        case .sconosciuto: return ""
        case .consigliata: return "Stai vedendo la consigliata: non hai salvato una tua formazione."
        case .altra: return "Stai vedendo un modulo o uno stile diverso dalla consigliata: non l'hai salvato."
        case .bozza: return "Modifica a mano non ancora salvata"
        case .salvata(let d):
            return "La tua formazione è salvata" + (d.map { " (\(Self.momento($0, adesso: adesso)))" } ?? "")
        case .modificata(let d):
            return "Modifiche non salvate" + (d.map { " · salvata \(Self.momento($0, adesso: adesso, breve: true))" } ?? "")
        case .nonValida: return "La formazione salvata non è più valida: rifalla o torna alla consigliata."
        case .chiusa(let tua):
            return "Giornata iniziata: la formazione è chiusa" + (tua ? " · vale quella che hai salvato" : "")
        case .chiusaNonValida:
            return "Giornata iniziata: la formazione è chiusa · vale la consigliata, la tua non è più valida"
        }
    }

    /// La stessa frase per VoiceOver: il «·» diventa una virgola (com'è, si sente il nome del simbolo).
    func voce(adesso: Date = Date()) -> String {
        titolo(adesso: adesso).replacingOccurrences(of: " · ", with: ", ")
    }

    /// Simbolo SF della riga (oltre al colore: lo stato non si legge dal solo colore). Come i segni della web: ○ ✓ ● ! ■.
    var simbolo: String {
        switch self {
        case .sconosciuto: return ""
        case .consigliata, .altra: return "info.circle"
        case .bozza, .modificata: return "pencil.circle.fill"
        case .salvata: return "checkmark.circle.fill"
        case .nonValida: return "exclamationmark.triangle.fill"
        case .chiusa, .chiusaNonValida: return "lock.fill"
        }
    }

    enum Tono: Equatable { case neutro, bene, attenzione, malus }

    /// Il colore del segno, come la web: verde salvata, arancio modifiche, rosso non valida, grigio il resto.
    var tono: Tono {
        switch self {
        case .salvata: return .bene
        case .bozza, .modificata: return .attenzione
        case .nonValida: return .malus
        case .consigliata, .altra, .sconosciuto, .chiusa, .chiusaNonValida: return .neutro
        }
    }

    /// C'è qualcosa da salvare (pulsante «Salva» in evidenza).
    var daSalvare: Bool {
        switch self {
        case .bozza, .modificata, .sconosciuto: return true
        case .consigliata, .altra, .salvata, .nonValida, .chiusa, .chiusaNonValida: return false
        }
    }

    /// «Salva questa» nella riga, come la web: si vede una formazione che non hai salvato (la consigliata, un altro stile o modulo).
    var conSalvaQuesta: Bool { self == .consigliata || self == .altra }

    /// «Torna alla consigliata» nella riga, come la web, dove non c'è già sotto con la modifica a mano: un altro stile o modulo,
    /// o una scelta salvata che non vale più.
    var conTornaNellaRiga: Bool { self == .altra || self == .nonValida }

    enum Pulsante: Hashable { case salvaQuesta, salva, annulla, torna }

    var pulsanti: [Pulsante] { (conSalvaQuesta ? [.salvaQuesta] : []) + (conTornaNellaRiga ? [.torna] : []) }

    var conModificaAMano: Bool { true }

    // MARK: quando

    private static let italia = TimeZone(identifier: "Europe/Rome") ?? .current

    private static let ora: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.timeZone = italia
        f.dateFormat = "HH:mm"
        return f
    }()

    /// Come `tempo.giorno_0…6` della web, dalla domenica (`Calendar.weekday` parte da 1 = domenica).
    private static let sigleGiorni = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"]

    /// Quando è stata salvata, come `quandoSalvata` della web (ora italiana): «oggi alle 21:40», «ieri alle 09:05»,
    /// «sab 31 alle 21:40». `breve` (per «Modifiche non salvate · salvata …»): oggi solo «alle 21:40».
    static func momento(_ data: Date, adesso: Date = Date(), breve: Bool = false) -> String {
        var calendario = Calendar(identifier: .gregorian)
        calendario.timeZone = italia
        let alle = "alle " + ora.string(from: data)
        let inizio = calendario.startOfDay(for: adesso)
        let giorni = calendario.dateComponents([.day], from: inizio, to: calendario.startOfDay(for: data)).day ?? 0
        switch giorni {
        case 0: return breve ? alle : "oggi " + alle
        case -1: return "ieri " + alle
        default:
            let sigla = sigleGiorni[min(max(calendario.component(.weekday, from: data) - 1, 0), 6)]
            return "\(sigla) \(calendario.component(.day, from: data)) " + alle
        }
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
