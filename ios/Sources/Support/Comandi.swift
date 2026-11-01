import AppIntents
import SwiftUI

// Siri e app Comandi (Shortcuts): le frasi sono in italiano. Funzionano con l'Apple ID gratuito e non servono estensioni.

/// Errore letto da Siri a voce.
enum ErroreComando: Error, CustomLocalizedStringResourceConvertible {
    case senzaServer
    case senzaPartite
    case senzaFormazione
    case senzaGiornata

    var localizedStringResource: LocalizedStringResource {
        switch self {
        case .senzaFormazione: return "La formazione non è ancora disponibile."
        case .senzaServer: return "Non riesco a raggiungere il server. Controlla la connessione e che il server sia acceso."
        case .senzaGiornata: return "Non c'è nessuna giornata in programma per ora."
        case .senzaPartite: return "Non trovo la prossima partita della giornata."
        }
    }
}

/// Riquadro mostrato da Siri e da Comandi.
struct RiquadroComando: View {
    let titolo: String
    let grande: String
    let dettaglio: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(titolo).font(.caption).foregroundStyle(.secondary)
            Text(grande).font(.system(.largeTitle, design: .rounded).weight(.bold))
            Text(dettaglio).font(.subheadline).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
    }
}

struct FormazioneComando: AppIntent {
    static var title: LocalizedStringResource = "Qual è la mia formazione"
    static var description = IntentDescription("Dice il modulo e i punti attesi della formazione consigliata per la prossima giornata.")

    func perform() async throws -> some IntentResult & ProvidesDialog & ShowsSnippetView {
        guard let risultato = await Aggiornamento.leggiOggi() else { throw ErroreComando.senzaServer }
        let oggi = risultato.oggi
        guard let f = oggi.formazione, f.disponibile, let modulo = f.modulo else {
            throw ErroreComando.senzaFormazione
        }
        guard let numero = oggi.giornataMostrata else { throw ErroreComando.senzaGiornata }
        let punti = Formato.punti(f.punteggioAtteso)
        var frase = Self.fraseBase(oggi, modulo: modulo, punti: punti)
        if oggi.conProbabili == false { frase += " Le probabili formazioni non sono ancora uscite." }
        if risultato.salvato { frase += " Attenzione: sono dati salvati, il server non risponde." }
        return .result(
            dialog: "\(frase)",
            view: RiquadroComando(titolo: "Giornata \(numero)", grande: modulo, dettaglio: "\(punti) punti attesi")
        )
    }

    /// Il numero è quello della LEGA (lo stesso che si vede nell'app e che dice «Quanto manca alla partita»), non quello di Serie A.
    static func fraseBase(_ oggi: Oggi, modulo: String, punti: String) -> String {
        "Per la giornata \(oggi.giornataMostrata.map(String.init) ?? "in programma") ti consiglio il \(modulo), con \(punti) punti attesi."
    }
}

struct QuantoMancaComando: AppIntent {
    static var title: LocalizedStringResource = "Quanto manca alla partita"
    static var description = IntentDescription("Dice quanto manca alla scadenza della formazione.")

    func perform() async throws -> some IntentResult & ProvidesDialog & ShowsSnippetView {
        guard let risultato = await Aggiornamento.leggiOggi() else { throw ErroreComando.senzaServer }
        let oggi = risultato.oggi
        guard let numero = oggi.giornataMostrata else { throw ErroreComando.senzaGiornata }
        guard let inizio = Quando.data(oggi.chiusura) else { throw ErroreComando.senzaPartite }
        if inizio <= Date() {
            return .result(
                dialog: "La formazione della giornata \(numero) è già chiusa.",
                view: RiquadroComando(titolo: "Giornata \(numero)", grande: "In corso", dettaglio: "formazione chiusa \(Quando.leggibile(oggi.chiusura))")
            )
        }
        var calendario = Calendar(identifier: .gregorian)
        calendario.locale = Locale(identifier: "it_IT")
        let formato = DateComponentsFormatter()
        formato.calendar = calendario
        formato.unitsStyle = .full
        formato.allowedUnits = [.day, .hour, .minute]
        formato.maximumUnitCount = 2
        let manca = formato.string(from: Date(), to: inizio) ?? "poco"
        return .result(
            dialog: "Alla scadenza della formazione della giornata \(numero) mancano \(manca).",
            view: RiquadroComando(titolo: "Giornata \(numero)", grande: manca, dettaglio: "alla scadenza, \(Quando.leggibile(oggi.chiusura))")
        )
    }
}

/// Le frasi che Siri riconosce (devono contenere il nome dell'app) e le voci nell'app Comandi.
struct FantaScorciatoie: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: FormazioneComando(),
            phrases: [
                "Qual è la mia formazione su \(.applicationName)",
                "Formazione su \(.applicationName)",
                "Mostra la formazione su \(.applicationName)"
            ],
            shortTitle: "La mia formazione",
            systemImageName: "sportscourt"
        )
        AppShortcut(
            intent: QuantoMancaComando(),
            phrases: [
                "Quanto manca alla partita su \(.applicationName)",
                "Quanto manca al calcio d'inizio su \(.applicationName)",
                "Quanto manca su \(.applicationName)"
            ],
            shortTitle: "Quanto manca",
            systemImageName: "timer"
        )
    }
}
