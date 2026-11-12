import Foundation

/// A che punto è «la tua scelta» della giornata: si confrontano gli undici mostrati con quelli salvati sul server
/// (`GET /api/scelta`). Stati e frasi sono quelli della web (`statoScelta` e `rigaStatoScelta` di `fanta/web/app.js`, frasi
/// `formazione.stato_*` di `testi.js`). Logica pura, provata in `RigaStatoComeWebTests`; la Formazione la mostra in una riga fissa.
enum StatoScelta: Equatable {
    /// Non si sa (lettura non riuscita, o si guarda un'altra squadra): non si dice niente, per non dire cose false.
    case sconosciuto
    /// Nessuna scelta salvata: si vede la consigliata.
    case consigliata
    /// Nessuna scelta salvata e si vede un altro modulo: non è la consigliata (web: «altra»).
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
    ///   - manuale: i titolari della modifica a mano (nil = si vede la consigliata o un altro modulo).
    ///   - mostrati: senza modifica a mano, i titolari del modulo sullo schermo (nil = non si sa). Con una scelta
    ///     salvata dicono se è «salvata» o se ci sono modifiche, come la web che confronta gli undici mostrati.
    ///   - chiusa: la giornata è chiusa (viene prima di tutto il resto, come sulla web).
    ///   - nonValida: la scelta salvata non vale più (lo dice il server con `formazione_non_valida` o, a giornata chiusa, con
    ///     `stato_scelta`; o non è nella rosa).
    ///   - altra: senza modifica a mano si vede un altro modulo.
    /// L'ordine dei titolari non conta.
    static func calcola(letta: Bool, salvati: [Int]?, salvataIl: Date?, manuale: [Int]?, mostrati: [Int]? = nil, chiusa: Bool = false,
                        nonValida: Bool = false, altra: Bool = false) -> StatoScelta {
        if chiusa { return nonValida ? .chiusaNonValida : .chiusa(tua: letta && salvati != nil) }
        guard letta else { return .sconosciuto }
        guard let salvati else { return manuale != nil ? .bozza : altra ? .altra : .consigliata }
        // dopo «Modifica a mano» si può salvare la nuova («modificata»); gli undici che non valgono più non sono «salvata»
        if nonValida, manuale.map({ Set($0) == Set(salvati) }) ?? true { return .nonValida }
        guard let visti = manuale ?? mostrati, Set(visti) == Set(salvati) else { return .modificata(salvataIl) }
        return .salvata(salvataIl)
    }

    /// La frase della riga di stato, uguale alla web (`formazione.stato_*` del catalogo comune).
    func titolo(adesso: Date = Date()) -> String {
        switch self {
        case .sconosciuto: return ""
        case .consigliata: return Catalogo.Formazione.statoConsigliata
        case .altra: return Catalogo.Formazione.statoAltroModulo
        case .bozza: return Catalogo.Formazione.statoMano
        case .salvata(let d):
            return d.map { Catalogo.Formazione.statoSalvataQuando(quando: Self.momento($0, adesso: adesso)) }
                ?? Catalogo.Formazione.statoSalvata
        case .modificata(let d):
            return d.map { Catalogo.Formazione.statoModificataQuando(quando: Self.momento($0, adesso: adesso, breve: true)) }
                ?? Catalogo.Formazione.statoModificata
        case .nonValida: return Catalogo.Formazione.statoNonValida
        case .chiusa(let tua): return tua ? Catalogo.Formazione.statoChiusaTua : Catalogo.Formazione.statoChiusa
        case .chiusaNonValida: return Catalogo.Formazione.statoChiusaNonValida
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

    /// Un pulsante della riga di stato: «Salva questa», «Salva le modifiche» o «Salva come mia scelta», «Annulla modifiche»,
    /// «Torna alla consigliata».
    enum Pulsante: Hashable {
        case salvaQuesta, salva, annulla, torna

        /// Spento mentre un salvataggio è in corso, come i pulsanti della web che guardano `sc.occupato`: quelli che salvano e
        /// «Annulla modifiche». «Torna alla consigliata» resta attivo, come sulla web (#477).
        var spentoSalvando: Bool { self != .torna }
    }

    /// I pulsanti della riga, nell'ordine di `rigaStatoScelta` della web (#463): dipendono dallo stato, non dalla modifica a mano,
    /// così con una scelta salvata e un altro modulo sullo schermo ci sono «Salva le modifiche» e «Annulla modifiche».
    /// «Modifica a mano» sull'iPhone sta sopra i moduli: vedi `conModificaAMano`.
    var pulsanti: [Pulsante] {
        switch self {
        case .consigliata: return [.salvaQuesta]
        case .altra: return [.salvaQuesta, .torna]
        case .salvata: return [.torna]
        case .modificata: return [.salva, .annulla, .torna]
        case .bozza: return [.salva, .torna]
        case .nonValida: return [.torna]
        case .sconosciuto, .chiusa, .chiusaNonValida: return []
        }
    }

    /// «Modifica a mano» dove la web la offre: nella riga con la consigliata, un altro modulo e la scelta che non vale più,
    /// e quando la riga non c'è (un'altra squadra, scelta non ancora letta). Con una scelta salvata no: la si cambia dal modulo
    /// o, in modifica a mano, dai titolari.
    var conModificaAMano: Bool {
        switch self {
        case .sconosciuto, .consigliata, .altra, .nonValida: return true
        case .salvata, .modificata, .bozza, .chiusa, .chiusaNonValida: return false
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

    /// `tempo.giorno_0…6` del catalogo comune, dalla domenica (`Calendar.weekday` parte da 1 = domenica).
    private static let sigleGiorni = [Catalogo.Tempo.giorno0, Catalogo.Tempo.giorno1, Catalogo.Tempo.giorno2, Catalogo.Tempo.giorno3,
                                      Catalogo.Tempo.giorno4, Catalogo.Tempo.giorno5, Catalogo.Tempo.giorno6]

    /// Quando è stata salvata, come `quandoSalvata` della web (ora italiana, `formazione.alle` e `formazione.giorno_alle`):
    /// «oggi alle 21:40», «ieri alle 09:05», «sab 31 alle 21:40». `breve` (per «Modifiche non salvate · salvata …»): oggi solo
    /// «alle 21:40».
    static func momento(_ data: Date, adesso: Date = Date(), breve: Bool = false) -> String {
        var calendario = Calendar(identifier: .gregorian)
        calendario.timeZone = italia
        let orario = ora.string(from: data)
        let inizio = calendario.startOfDay(for: adesso)
        let giorni = calendario.dateComponents([.day], from: inizio, to: calendario.startOfDay(for: data)).day ?? 0
        switch giorni {
        case 0:
            return breve ? Catalogo.Formazione.alle(ora: orario) : Catalogo.Formazione.giornoAlle(giorno: Catalogo.Tempo.oggi, ora: orario)
        case -1: return Catalogo.Formazione.giornoAlle(giorno: Catalogo.Tempo.ieri, ora: orario)
        default:
            let sigla = sigleGiorni[min(max(calendario.component(.weekday, from: data) - 1, 0), 6)]
            return Catalogo.Formazione.giornoAlle(giorno: "\(sigla) \(calendario.component(.day, from: data))", ora: orario)
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
