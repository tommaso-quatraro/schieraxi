import Foundation

/// Controlla se su GitHub c'è una build più nuova di quella installata (le release si chiamano `build-N`)
/// e, una volta per build, manda una notifica locale che invita ad aggiornarla dall'app con cui è installata (`avviso`).
/// L'app non si aggiorna da sola: iOS non lo permette a un'app che non viene dall'App Store.
enum NuovaVersione {
    struct Esito: Equatable {
        let build: Int
        let nome: String
    }

    /// L'ELENCO delle release del repository unico: nello stesso repository ci sono anche le release del server (`v1.x`),
    /// quindi la «latest» di GitHub potrebbe non essere una build dell'app. Si leggono le ultime 30 e si tengono solo le `build-N`.
    static let indirizzo = "https://api.github.com/repos/tommaso-quatraro/schieraxi/releases?per_page=30"
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

    /// Dall'elenco delle release di GitHub (JSON) prende il tag `build-N` col numero più alto.
    /// Ignora bozze, pre-release, tag che non sono `build-N` (per esempio `v1.250`) e voci malformate. Elenco vuoto o illeggibile: `nil`.
    static func tagPiuAlto(elenco dati: Data) -> String? {
        guard let voci = try? JSONSerialization.jsonObject(with: dati) as? [[String: Any]] else { return nil }
        var migliore: (n: Int, tag: String)?
        for voce in voci {
            if voce["draft"] as? Bool == true || voce["prerelease"] as? Bool == true { continue }
            guard let tag = voce["tag_name"] as? String, tag.hasPrefix("build-"), let n = numero(daTag: tag) else { continue }
            if let attuale = migliore, attuale.n >= n { continue }
            migliore = (n, tag)
        }
        return migliore?.tag
    }

    /// Chiede a GitHub l'elenco delle release (il repository è pubblico: nessun accesso richiesto).
    static func controlla() async -> Esito? {
        if Demo.attivo { return nil }
        guard let url = URL(string: indirizzo) else { return nil }
        var richiesta = URLRequest(url: url, timeoutInterval: 15)
        richiesta.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        guard let (dati, risposta) = try? await URLSession.shared.data(for: richiesta),
              (risposta as? HTTPURLResponse)?.statusCode == 200,
              let tag = tagPiuAlto(elenco: dati),
              let n = piuNuova(tag: tag, installata: buildInstallata) else { return nil }
        return Esito(build: n, nome: tag)
    }

    /// Avvisa della build se non è ancora stata segnalata, e la segna come avvisata solo se l'avviso è partito davvero: con «Avvisi
    /// su questo dispositivo» spento (o senza permesso) non parte, e riaccendendo arriva al controllo dopo.
    static func avvisaSeServe(_ esito: Esito, memoria: UserDefaults = .standard, manda: (Esito) async -> Bool) async {
        guard memoria.integer(forKey: chiaveAvvisata) < esito.build, await manda(esito) else { return }
        memoria.set(esito.build, forKey: chiaveAvvisata)
    }

    /// La versione che la compilazione dà alla build `build` («1.0.38»: `MARKETING_VERSION="1.0.$BUILD_N"` di ipa.yml), la stessa
    /// che Impostazioni › Informazioni mostra come «Versione dell'app». Se ipa.yml cambia il modo di numerare, va cambiata anche qui.
    static func versione(build: Int) -> String {
        "1.0.\(build)"
    }

    /// Titolo e testo dell'avviso, dal catalogo (`avv.versione_nuova_titolo`, `avv.versione_nuova_testo`), con la versione
    /// leggibile e non la sigla della release («build-38»).
    static func avviso(per esito: Esito) -> (titolo: String, testo: String) {
        (Catalogo.Avv.versioneNuovaTitolo, Catalogo.Avv.versioneNuovaTesto(versione: versione(build: esito.build)))
    }

    /// Controlla e, se c'è una build mai segnalata, manda la notifica (una sola volta per build).
    @discardableResult
    static func controllaEAvvisa() async -> Esito? {
        guard let esito = await controlla() else { return nil }
        await avvisaSeServe(esito) { e in
            let testi = Self.avviso(per: e)
            return await Notifiche.avviso(id: "nuova-versione", titolo: testi.titolo, corpo: testi.testo)
        }
        return esito
    }
}
