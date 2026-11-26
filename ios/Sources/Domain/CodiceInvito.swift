import Foundation

/// Il codice d'invito scritto nel campo «Codice d'invito» della registrazione (anche dopo «Continua con Google»). Il messaggio
/// d'invito della web contiene solo il link (`https://<indirizzo>/?invito=CODICE`, `linkInvito` in `fanta/web/app.js`): chi lo
/// incolla qui (anche con il messaggio intero) registra il codice che c'è dentro (#880).
enum CodiceInvito {
    /// Il codice da mandare al server: quello dentro un link d'invito incollato; altrimenti quello scritto, senza spazi ai lati e
    /// in maiuscolo, come i codici del server.
    static func daCampo(_ scritto: String) -> String {
        let pulito = scritto.trimmingCharacters(in: .whitespacesAndNewlines)
        return dalLink(pulito) ?? pulito.uppercased()
    }

    /// Il codice del primo link d'invito nel testo, pulito come `invitoDaIndirizzo` della web: in maiuscolo, solo lettere, cifre
    /// e trattini, da 4 a 40 caratteri. nil se nel testo non c'è un link con un codice così.
    static func dalLink(_ testo: String) -> String? {
        for pezzo in testo.split(whereSeparator: \.isWhitespace) where pezzo.contains("invito=") {
            guard let voci = URLComponents(string: String(pezzo))?.queryItems,
                  let valore = voci.first(where: { $0.name == "invito" })?.value else { continue }
            var codice = ""
            for carattere in valore.uppercased().unicodeScalars where ammessi.contains(carattere) {
                codice.unicodeScalars.append(carattere)
            }
            if (4...40).contains(codice.count) { return codice }
        }
        return nil
    }

    /// I caratteri di un codice d'invito, come `[A-Z0-9-]` della web.
    private static let ammessi = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
}
