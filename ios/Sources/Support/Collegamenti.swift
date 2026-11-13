import Foundation

/// Dove porta un indirizzo `schieraxi://...`.
enum Destinazione: Equatable {
    case sezione(Sezione)
    case giocatore(Int)
    /// Una pagina delle Impostazioni (Aggiorna le rose, Regole e scadenza, Gestione…), da «Da fare» e dagli indirizzi.
    case pagina(PaginaImpostazioni)
    /// Le Impostazioni, portate a una loro parte (La mia lega, Avvisi, Aspetto) o in cima (`nil`): `schieraxi://impostazioni` e gli
    /// indirizzi di Squadra e Altro, che non sono più schede (#673 passo 3).
    case impostazioni(ParteImpostazioni?)
    /// «Collega il widget» (`schieraxi://widget/collega`, il tocco sul widget non collegato): apre solo la schermata, che aspetta il
    /// tocco su «Collega» prima di collegare o di copiare il codice (l'indirizzo lo può aprire anche un'altra app, #482).
    case collegaWidget

    /// Porta alle Impostazioni (in cima, a una parte o a una pagina).
    var portaAlleImpostazioni: Bool {
        switch self {
        case .sezione(let s): return s == .impostazioni
        case .impostazioni, .pagina: return true
        case .giocatore, .collegaWidget: return false
        }
    }
}

/// Indirizzi accettati dall'app (schema `schieraxi://`), per aprirla dal tocco su una notifica di ntfy (intestazione `Click`), dai
/// widget e da «Da fare»: `schieraxi://formazione` (e `oggi`), `giornate` (e `diario`), `impostazioni` e `schieraxi://giocatore/<id>`.
/// Dal 13/11/2026 (#673 passo 3, come la web #675) Squadra e Altro non sono schede: `squadra`, `mercato`, `altro`, `lega` e `scambi`
/// aprono le Impostazioni su La mia lega; `lega/rose` Aggiorna le rose, `lega/regole` Regole e scadenza, `impostazioni/installazione`
/// Gestione. Il Diario è la pagina Giornate (#673 passo 2): `schieraxi://diario` e `schieraxi://lega/diario` aprono Giornate.
enum Collegamenti {
    static let schema = "schieraxi"

    /// Esempio da mostrare all'utente.
    static let esempioNtfy = "Click: schieraxi://formazione"

    static func interpreta(_ url: URL) -> Destinazione? {
        guard let schemaUrl = url.scheme?.lowercased(), schemaUrl == schema, let host = url.host?.lowercased() else { return nil }
        // pathComponents di "schieraxi://giocatore/12" è ["/", "12"]
        let parte = url.pathComponents.dropFirst().first
        if host == "widget" {
            // "schieraxi://widget/collega" (e, per tolleranza, "schieraxi://widget")
            guard parte == nil || parte?.lowercased() == "collega" else { return nil }
            return .collegaWidget
        }
        if host == "giocatore" {
            guard let parte, let id = Int(parte), id > 0 else { return nil }
            return .giocatore(id)
        }
        return perNome(host, parte: parte)
    }

    /// Una destinazione da un nome di sezione (l'host di un indirizzo, la sezione scritta a parole di «Da fare», un nome vecchio) e,
    /// se c'è, dalla pagina che segue.
    static func perNome(_ nome: String, parte: String? = nil) -> Destinazione? {
        let nome = nome.lowercased(), parte = parte?.lowercased() ?? ""
        if Self.lega.contains(nome) {
            switch parte {
            case "diario": return .sezione(.giornate)          // il Diario stava in Altro, ora è la pagina Giornate
            case "rose", "importa": return .pagina(.importa)
            case "regole": return .pagina(.regole)
            default: return .impostazioni(.lega)
            }
        }
        if nome == "impostazioni" {
            switch parte {
            case "installazione", "gestione": return .pagina(.gestione)
            case "account": return .pagina(.account)
            case "informazioni": return .pagina(.informazioni)
            default: return .impostazioni(ParteImpostazioni(rawValue: parte))   // «avvisi», «lega», «aspetto»; altrimenti in cima
            }
        }
        return Sezione.da(nome: nome).map { .sezione($0) }
    }

    /// I nomi delle schede e delle pagine tolte che portano a La mia lega: Squadra, Altro e quelle che stavano lì (#634).
    private static let lega: Set<String> = ["squadra", "mercato", "altro", "lega", "scambi"]
}
