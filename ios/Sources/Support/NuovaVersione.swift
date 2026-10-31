import Foundation

/// Controlla se su GitHub c'è una build più nuova di quella installata (le release si chiamano `build-N`)
/// e, una volta per build, manda una notifica locale con le istruzioni per aggiornare da SideStore.
/// L'app non si aggiorna da sola: iOS non lo permette a un'app che non viene dall'App Store.
enum NuovaVersione {
    struct Esito: Equatable {
        let build: Int
        let nome: String
    }

    static let indirizzo = "https://api.github.com/repos/tommaso-quatraro/schieraxi-ios/releases/latest"
    private static let chiaveAvvisata = "nuovaVersioneAvvisata"

    /// Numero della build installata (CFBundleVersion, impostato dalla compilazione su GitHub).
    static var buildInstallata: Int {
        Int(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "") ?? 0
    }

    /// «build-37» → 37.
    static func numero(daTag tag: String) -> Int? {
        Int(tag.replacingOccurrences(of: "build-", with: ""))
    }

    /// Il numero della build del tag, solo se è più nuova di quella installata.
    static func piuNuova(tag: String, installata: Int) -> Int? {
        guard let n = numero(daTag: tag), n > installata else { return nil }
        return n
    }

    /// Chiede a GitHub l'ultima release (il repository è pubblico: nessun accesso richiesto).
    static func controlla() async -> Esito? {
        if Demo.attivo { return nil }
        guard let url = URL(string: indirizzo) else { return nil }
        var richiesta = URLRequest(url: url, timeoutInterval: 15)
        richiesta.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        guard let (dati, risposta) = try? await URLSession.shared.data(for: richiesta),
              (risposta as? HTTPURLResponse)?.statusCode == 200,
              let o = try? JSONSerialization.jsonObject(with: dati) as? [String: Any],
              let tag = o["tag_name"] as? String,
              let n = piuNuova(tag: tag, installata: buildInstallata) else { return nil }
        return Esito(build: n, nome: tag)
    }

    /// Controlla e, se c'è una build mai segnalata, manda la notifica (una sola volta per build).
    @discardableResult
    static func controllaEAvvisa() async -> Esito? {
        guard let esito = await controlla() else { return nil }
        if UserDefaults.standard.integer(forKey: chiaveAvvisata) < esito.build {
            await Notifiche.avviso(
                id: "nuova-versione",
                titolo: "SchieraXI · C'è una versione nuova",
                corpo: "Aggiorna SchieraXI dall'app con cui l'hai installata (\(esito.nome)).")
            UserDefaults.standard.set(esito.build, forKey: chiaveAvvisata)
        }
        return esito
    }
}
