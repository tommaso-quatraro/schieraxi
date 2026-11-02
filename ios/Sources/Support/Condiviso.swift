import Foundation
import Security

// Dati condivisi tra l'app e il widget, SENZA che l'utente scriva niente.
//
// Con l'Apple ID gratuito SideStore firma di nuovo l'app e il widget (sorgenti di SideStore, ramo develop, novembre 2026):
// - il gruppo `group.it.schieraxi.app` diventa `group.it.schieraxi.app.<SQUADRA>` (la squadra = il Team ID dell'Apple ID) ed è lo
//   stesso per l'app e per il widget (`FetchProvisioningProfilesOperation.adjustedGroupIdentifier`);
// - fino a settembre 2026 il nome vero si leggeva in Info.plist (`ALTAppGroups`); dal commit 7866508 SideStore NON lo scrive più.
//   Resta il profilo `embedded.mobileprovision` che SideStore mette in ogni pacchetto (app e widget): da lì si leggono i gruppi
//   concessi e la squadra (`ProfiloFirma`). Poi si provano i candidati con `containerURL(forSecurityApplicationGroupIdentifier:)`;
// - firma con i permessi del profilo, ma solo quelli che l'app dichiara (ldid nel workflow IPA); per `keychain-access-groups`
//   tiene i gruppi dell'app e cambia solo il prefisso con la squadra vera (`ALTSigner.swift` di AltSign). Così c'è anche un
//   ripiego senza App Group: un elemento del Keychain nel gruppo `<SQUADRA>.it.schieraxi.app.condiviso` (`PortachiaviCondiviso`).
//
// Nel contenitore c'è UN file (`condiviso.json`): l'indirizzo del server, il token del WIDGET (`fw_`, mai quello della sessione; protetto dalla protezione dei dati
// di iOS e dal sandbox, mai in UserDefaults) e l'ultimo riassunto di «Oggi», così il widget mostra subito qualcosa. Lo scrive solo
// l'app; il widget lo legge. Se né il gruppo né il Keychain condiviso funzionano il widget dice «Tocca per collegare»: l'app copia
// il codice di collegamento e l'utente lo incolla una volta in «Modifica widget» > «Collegamento manuale» (`CollegamentoWidget`).

/// Il server pubblico dell'app (un dominio pubblico, lo stesso per tutti): l'unico indirizzo nel repository e nell'IPA.
/// L'app lo usa quando l'utente non ne ha scelto un altro; il widget quando l'app non gli ha passato niente.
enum ServerPubblico {
    static let indirizzo = "https://app.schieraxi.it"
}

/// Cosa dice il profilo con cui SideStore (o AltStore, o Xcode) ha firmato QUESTO pacchetto: `embedded.mobileprovision`, un
/// plist dentro una busta firmata (CMS). Ognuno legge il suo: l'app il suo, il widget il suo. Nel simulatore non c'è (nil).
struct ProfiloFirma: Equatable, Sendable {
    /// Il Team ID (10 lettere maiuscole e cifre).
    var squadra: String?
    /// `com.apple.security.application-groups` concessi (con SideStore: `group.it.schieraxi.app.<SQUADRA>`).
    var gruppi: [String]
    /// `keychain-access-groups` del profilo (di solito `<SQUADRA>.*`).
    var gruppiPortachiavi: [String]
    /// `application-identifier`: il gruppo del Keychain privato dell'app (`<SQUADRA>.<bundle id>`).
    var identificativoApp: String?

    /// Legge il profilo (dati grezzi del file). nil se non si capisce.
    static func leggi(_ dati: Data) -> ProfiloFirma? {
        guard dati.count < 2_000_000, let inizio = dati.range(of: Data("<?xml".utf8)),
              let fine = dati.range(of: Data("</plist>".utf8), in: inizio.lowerBound..<dati.endIndex) else { return nil }
        let pezzo = dati.subdata(in: inizio.lowerBound..<fine.upperBound)
        guard let plist = try? PropertyListSerialization.propertyList(from: pezzo, options: [], format: nil) as? [String: Any] else { return nil }
        let permessi = plist["Entitlements"] as? [String: Any] ?? [:]
        let squadra = (permessi["com.apple.developer.team-identifier"] as? String) ?? (plist["TeamIdentifier"] as? [String])?.first
        return ProfiloFirma(squadra: squadra.flatMap(Self.squadraValida),
                            gruppi: permessi["com.apple.security.application-groups"] as? [String] ?? [],
                            gruppiPortachiavi: permessi["keychain-access-groups"] as? [String] ?? [],
                            identificativoApp: permessi["application-identifier"] as? String)
    }

    /// Un Team ID: 10 caratteri, solo lettere maiuscole e cifre.
    static func squadraValida(_ testo: String) -> String? {
        testo.count == 10 && testo.unicodeScalars.allSatisfy({ ($0.value >= 0x30 && $0.value <= 0x39) || ($0.value >= 0x41 && $0.value <= 0x5A) }) ? testo : nil
    }

    /// SideStore aggiunge la squadra al bundle id: `it.schieraxi.app.<SQUADRA>` (widget: `it.schieraxi.app.<SQUADRA>.widget`).
    static func squadraDalBundle(_ id: String?, base: String = "it.schieraxi.app") -> String? {
        guard let id, id.hasPrefix(base + ".") else { return nil }
        return id.dropFirst(base.count + 1).split(separator: ".").first.map(String.init).flatMap(squadraValida)
    }

    /// Il profilo di questo pacchetto (app o widget). nil nel simulatore e senza profilo.
    static let questo: ProfiloFirma? = {
        guard let url = Bundle.main.url(forResource: "embedded", withExtension: "mobileprovision"),
              let dati = try? Data(contentsOf: url) else { return nil }
        return leggi(dati)
    }()

    /// Le squadre possibili, senza doppioni: quella del profilo, poi quella nel bundle id.
    static func squadre(profilo: ProfiloFirma?, bundle: String?) -> [String] {
        var elenco: [String] = []
        for s in [profilo?.squadra, squadraDalBundle(bundle)].compactMap({ $0 }) where !elenco.contains(s) { elenco.append(s) }
        return elenco
    }
}

/// Un giocatore della formazione da controllare (dubbio, infortunio, squalifica), per il widget «Da controllare».
struct DubbioRiassunto: Codable, Equatable, Identifiable {
    var id: Int
    var nome: String
    var ruolo: String?
    var tipo: String?
    /// Probabilità di giocare (0-1), per i dubbi.
    var pVoto: Double?

    /// «Dubbio 55%», «Infortunato»...: una riga breve.
    var descrizione: String {
        let base = (tipo ?? "da controllare").prefix(1).uppercased() + (tipo ?? "da controllare").dropFirst()
        guard let p = pVoto else { return base }
        return "\(base) \(Int((p * 100).rounded()))%"
    }
}

/// Quello che serve al widget, in forma compatta e salvabile.
struct RiassuntoOggi: Codable, Equatable {
    var giornata: Int?
    var inizio: Date?
    var modulo: String?
    var punti: Double?
    var daControllare: Int
    var probabili: Bool?
    var scaricatoIl: Date
    /// Chi della formazione ha un dubbio (al massimo 6). Opzionale: un riassunto salvato da una versione vecchia non li ha.
    var dubbi: [DubbioRiassunto]?
    /// Il numero nella lega (opzionale: un riassunto salvato da una versione vecchia non ce l'ha).
    var giornataLega: Int?

    var etichettaGiornata: String { giornata.map { TempiLega.etichetta(serieA: $0, lega: giornataLega) } ?? "Nessuna giornata" }
    var siglaGiornata: String { giornata.map { TempiLega.sigla(serieA: $0, lega: giornataLega) } ?? "G–" }

    static let esempio = RiassuntoOggi(giornata: 9, inizio: Date().addingTimeInterval(3 * 3600 + 25 * 60), modulo: "3-4-3", punti: 64.5,
                                       daControllare: 2, probabili: true, scaricatoIl: Date())

    init(giornata: Int?, inizio: Date?, modulo: String?, punti: Double?, daControllare: Int, probabili: Bool?, scaricatoIl: Date,
         dubbi: [DubbioRiassunto]? = nil, giornataLega: Int? = nil) {
        self.giornata = giornata
        self.inizio = inizio
        self.modulo = modulo
        self.punti = punti
        self.daControllare = daControllare
        self.probabili = probabili
        self.scaricatoIl = scaricatoIl
        self.dubbi = dubbi
        self.giornataLega = giornataLega
    }

    /// Dalla risposta di «oggi» (la stessa per l'app e per il widget).
    init(oggi: Oggi, scaricatoIl: Date = Date()) {
        let daControllare = (oggi.avvisi ?? []).filter { $0.inFormazione == true }
        self.init(giornata: oggi.giornata,
                  inizio: Quando.data(oggi.chiusura),
                  modulo: oggi.formazione?.modulo,
                  punti: oggi.formazione?.punteggioAtteso,
                  daControllare: daControllare.count,
                  probabili: oggi.conProbabili,
                  scaricatoIl: scaricatoIl,
                  dubbi: daControllare.prefix(6).map { DubbioRiassunto(id: $0.id, nome: $0.nome, ruolo: $0.ruolo, tipo: $0.tipo, pVoto: $0.pVoto) },
                  giornataLega: oggi.giornataLega)
    }
}

/// Il contenuto del file condiviso.
struct DatiCondivisi: Codable, Equatable {
    var indirizzo: String?
    /// Il token del widget (`fw_`) e il server a cui appartiene (non si manda mai a un altro indirizzo).
    var token: String?
    var tokenPerIndirizzo: String?
    var riassunto: RiassuntoOggi?
    var aggiornato: Date?

    /// Il token valido per questo indirizzo, se c'è.
    func token(per indirizzo: String) -> String? {
        guard let token, !token.isEmpty, tokenPerIndirizzo == indirizzo else { return nil }
        return token
    }
}

enum Condiviso {
    static let gruppoBase = "group.it.schieraxi.app"
    private static let nomeFile = "condiviso.json"
    private static let blocco = NSLock()
    /// Per i test: una cartella al posto del contenitore del gruppo.
    nonisolated(unsafe) static var cartellaDiProva: URL?

    /// Gli identificativi da provare, in ordine e senza doppioni, solo quelli che derivano dal nome base: quelli scritti dalle
    /// versioni vecchie di SideStore e da AltStore (`ALTAppGroups`), quelli concessi dal profilo, il nome base con la squadra
    /// (profilo o bundle id), il nome base (simulatore e installazione normale).
    static func identificativi(info: [String: Any]? = Bundle.main.infoDictionary, profilo: ProfiloFirma? = ProfiloFirma.questo,
                               bundle: String? = Bundle.main.bundleIdentifier) -> [String] {
        var elenco: [String] = []
        func aggiungi(_ g: String) {
            if (g == gruppoBase || g.hasPrefix(gruppoBase + ".")) && !elenco.contains(g) { elenco.append(g) }
        }
        (info?["ALTAppGroups"] as? [String] ?? []).forEach(aggiungi)
        (profilo?.gruppi ?? []).forEach(aggiungi)
        for s in ProfiloFirma.squadre(profilo: profilo, bundle: bundle) { aggiungi(gruppoBase + "." + s) }
        aggiungi(gruppoBase)
        return elenco
    }

    /// La cartella condivisa, se il gruppo funziona su questo dispositivo.
    static func cartella() -> URL? {
        if let prova = cartellaDiProva { return prova }
        for g in identificativi() {
            if let url = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: g) { return url }
        }
        return nil
    }

    /// true se l'App Group c'è (la condivisione funziona).
    static var disponibile: Bool { cartella() != nil }

    private static func percorso() -> URL? { cartella()?.appendingPathComponent(nomeFile) }

    static func leggi() -> DatiCondivisi {
        blocco.lock(); defer { blocco.unlock() }
        return leggiSenzaBlocco()
    }

    private static func leggiSenzaBlocco() -> DatiCondivisi {
        guard let url = percorso(), let dati = try? Data(contentsOf: url) else { return DatiCondivisi() }
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return (try? d.decode(DatiCondivisi.self, from: dati)) ?? DatiCondivisi()
    }

    /// Cambia i dati condivisi (lo fa solo l'app). Scrittura atomica, protetta fino al primo sblocco: il widget e l'aggiornamento
    /// in background leggono anche a telefono bloccato.
    @discardableResult
    static func aggiorna(_ modifica: (inout DatiCondivisi) -> Void) -> Bool {
        blocco.lock(); defer { blocco.unlock() }
        guard let url = percorso() else { return false }
        var dati = leggiSenzaBlocco()
        let prima = dati
        modifica(&dati)
        if dati == prima { return true }
        dati.aggiornato = Date()
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        guard let fuori = try? e.encode(dati) else { return false }
        do {
            try fuori.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
            return true
        } catch {
            return false
        }
    }

    /// Dice al widget dove sta il server e (se c'è una sessione) con quale token parlare. false se il gruppo non c'è.
    @discardableResult
    static func sincronizza(indirizzo: String, token: String?) -> Bool {
        aggiorna {
            $0.indirizzo = indirizzo.isEmpty ? nil : indirizzo
            if let token, !token.isEmpty, !indirizzo.isEmpty {
                $0.token = token
                $0.tokenPerIndirizzo = indirizzo
            } else if $0.tokenPerIndirizzo != indirizzo {
                $0.token = nil
                $0.tokenPerIndirizzo = nil
            }
        }
    }

    /// Via il token e il riassunto (uscita da un account): chi entra dopo non deve vedere niente di chi c'era prima.
    static func dimentica() {
        aggiorna {
            $0.token = nil
            $0.tokenPerIndirizzo = nil
            $0.riassunto = nil
        }
        PortachiaviCondiviso.cancella()
    }

    static func salvaRiassunto(_ r: RiassuntoOggi) {
        aggiorna { $0.riassunto = r }
    }

    // MARK: diagnostica

    /// Com'è messa la condivisione su questo dispositivo: serve a capire perché il widget non vede i dati dell'app.
    struct Diagnostica: Equatable {
        /// I gruppi scritti da SideStore in Info.plist (`ALTAppGroups`), come sono.
        var scrittiDaSideStore: [String]
        /// I gruppi provati, in ordine.
        var provati: [String]
        /// Il primo gruppo di cui iOS ha dato la cartella (nil = il gruppo non c'è per questo programma).
        var gruppoFunzionante: String?
        var filePresente: Bool
        var ultimaScrittura: Date?
        var haIndirizzo: Bool
        var haToken: Bool
        var haRiassunto: Bool
        /// I gruppi concessi dal profilo della firma (`embedded.mobileprovision`).
        var gruppiDelProfilo: [String] = []
        /// true se c'è il collegamento nel Keychain condiviso (il ripiego senza App Group).
        var portachiavi = false

        /// Una riga breve per il widget.
        var breve: String {
            func s(_ b: Bool) -> String { b ? "sì" : "no" }
            return "gruppo \(s(gruppoFunzionante != nil)) · portachiavi \(s(portachiavi)) · file \(s(filePresente)) · indirizzo \(s(haIndirizzo)) · token \(s(haToken))"
        }

        /// Il dettaglio per le Impostazioni (Avanzate).
        var lungo: String {
            func s(_ b: Bool) -> String { b ? "sì" : "no" }
            func elenco(_ gruppi: [String]) -> String { gruppi.isEmpty ? "nessuno" : gruppi.joined(separator: ", ") }
            // una riga alla volta: un unico elenco con tutti questi pezzi era troppo per il controllo dei tipi del compilatore
            var righe: [String] = []
            righe.append("Gruppo di SideStore (ALTAppGroups): " + elenco(scrittiDaSideStore))
            righe.append("Gruppi del profilo: " + elenco(gruppiDelProfilo))
            righe.append("Gruppi provati: " + provati.joined(separator: ", "))
            righe.append("Keychain condiviso: " + s(portachiavi))
            let cartella: String = gruppoFunzionante.map { "sì (\($0))" } ?? "NO (iOS non dà il gruppo a questo programma)"
            righe.append("Cartella condivisa: " + cartella)
            righe.append("File presente: " + s(filePresente))
            if let ultimaScrittura { righe.append("Ultima scrittura dell'app: " + ultimaScrittura.formatted(date: .abbreviated, time: .standard)) }
            righe.append("Indirizzo: \(s(haIndirizzo)) · token: \(s(haToken)) · riassunto: \(s(haRiassunto))")
            return righe.joined(separator: "\n")
        }
    }

    static func diagnostica(info: [String: Any]? = Bundle.main.infoDictionary, profilo: ProfiloFirma? = ProfiloFirma.questo) -> Diagnostica {
        let provati = identificativi(info: info, profilo: profilo)
        var funzionante: String?
        if cartellaDiProva == nil {
            funzionante = provati.first { FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: $0) != nil }
        } else {
            funzionante = provati.first
        }
        let url = cartella()?.appendingPathComponent(nomeFile)
        let presente = url.map { FileManager.default.fileExists(atPath: $0.path) } ?? false
        let dati = leggi()
        return Diagnostica(scrittiDaSideStore: (info?["ALTAppGroups"] as? [String]) ?? [], provati: provati, gruppoFunzionante: funzionante,
                           filePresente: presente, ultimaScrittura: dati.aggiornato, haIndirizzo: dati.indirizzo != nil,
                           haToken: dati.token != nil, haRiassunto: dati.riassunto != nil,
                           gruppiDelProfilo: profilo?.gruppi ?? [], portachiavi: PortachiaviCondiviso.leggi() != nil)
    }
}

/// Dove si tiene il collegamento nel Keychain condiviso: il Keychain vero, o la memoria (test).
protocol ArchivioCollegamento: AnyObject, Sendable {
    func leggi() -> Data?
    /// Scrive nel primo gruppo che iOS accetta e dice quale; nil se nessuno.
    func scrivi(_ dati: Data, gruppi: [String]) -> String?
    func cancella()
}

/// Il Keychain vero. Un solo elemento (servizio + conto fissi). Si scrive SOLO in un gruppo condiviso esplicito (mai in quello
/// predefinito, che è privato dell'app e il widget non lo vedrebbe); si legge senza gruppo: iOS cerca in tutti quelli del programma.
final class KeychainCollegamento: ArchivioCollegamento, @unchecked Sendable {
    private let servizio = "it.schieraxi.app.collegamento"
    private let conto = "widget"

    private var base: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: servizio, kSecAttrAccount as String: conto]
    }

    func leggi() -> Data? {
        var cerca = base
        cerca[kSecReturnData as String] = true
        cerca[kSecMatchLimit as String] = kSecMatchLimitOne
        var risultato: CFTypeRef?
        guard SecItemCopyMatching(cerca as CFDictionary, &risultato) == errSecSuccess else { return nil }
        return risultato as? Data
    }

    func scrivi(_ dati: Data, gruppi: [String]) -> String? {
        cancella()
        for g in gruppi {
            var nuovo = base
            nuovo[kSecAttrAccessGroup as String] = g
            nuovo[kSecValueData as String] = dati
            // dopo il primo sblocco: il widget si aggiorna anche a telefono bloccato; solo su questo telefono
            nuovo[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            if SecItemAdd(nuovo as CFDictionary, nil) == errSecSuccess { return g }
        }
        return nil
    }

    func cancella() {
        SecItemDelete(base as CFDictionary)
    }
}

/// In memoria, per i test: «gruppi» dice quali gruppi esistono.
final class MemoriaCollegamento: ArchivioCollegamento, @unchecked Sendable {
    private let blocco = NSLock()
    private var dati: Data?
    let ammessi: Set<String>?

    /// `ammessi` nil = qualsiasi gruppo va bene.
    init(ammessi: Set<String>? = nil) { self.ammessi = ammessi }

    func leggi() -> Data? { blocco.lock(); defer { blocco.unlock() }; return dati }

    func scrivi(_ nuovi: Data, gruppi: [String]) -> String? {
        blocco.lock(); defer { blocco.unlock() }
        dati = nil
        guard let g = gruppi.first(where: { ammessi?.contains($0) ?? true }) else { return nil }
        dati = nuovi
        return g
    }

    func cancella() { blocco.lock(); defer { blocco.unlock() }; dati = nil }
}

/// Il ripiego senza App Group: l'indirizzo e il token del WIDGET (`fw_`, mai quello della sessione) in un elemento del Keychain
/// condiviso tra app e widget. Il gruppo di accesso si dichiara nei permessi come `<prefisso>.it.schieraxi.app.condiviso` e
/// SideStore ci mette la squadra vera (AltSign, `ALTSigner.swift`); qui si ricostruisce con la squadra letta dal profilo.
/// Anche i nomi degli App Group valgono come gruppi del Keychain: si provano dopo.
enum PortachiaviCondiviso {
    static let suffisso = "it.schieraxi.app.condiviso"
    nonisolated(unsafe) static var archivio: any ArchivioCollegamento = KeychainCollegamento()

    /// I gruppi del Keychain da provare, in ordine.
    static func gruppiCandidati(profilo: ProfiloFirma? = ProfiloFirma.questo, bundle: String? = Bundle.main.bundleIdentifier) -> [String] {
        var elenco = ProfiloFirma.squadre(profilo: profilo, bundle: bundle).map { $0 + "." + suffisso }
        for g in Condiviso.identificativi(info: nil, profilo: profilo, bundle: bundle) where !elenco.contains(g) && g != Condiviso.gruppoBase {
            elenco.append(g)
        }
        return elenco
    }

    /// Lo scrive l'app. true se ora il widget lo può leggere (uno dei gruppi condivisi ha accettato).
    @discardableResult
    static func salva(indirizzo: String, token: String?, gruppi: [String] = gruppiCandidati()) -> Bool {
        guard !indirizzo.isEmpty else { cancella(); return false }
        let contenuto = CodiceWidget.Contenuto(i: indirizzo, t: (token?.isEmpty ?? true) ? nil : token)
        if let attuale = leggi(), attuale == contenuto { return true }
        guard let dati = try? JSONEncoder().encode(contenuto) else { return false }
        return archivio.scrivi(dati, gruppi: gruppi) != nil
    }

    /// Lo legge il widget (e l'app per sapere se c'è).
    static func leggi() -> CodiceWidget.Contenuto? {
        guard let dati = archivio.leggi(), dati.count <= 4000,
              let c = try? JSONDecoder().decode(CodiceWidget.Contenuto.self, from: dati), !c.i.isEmpty else { return nil }
        return c
    }

    static func cancella() { archivio.cancella() }
}

/// Il codice di collegamento del widget: indirizzo e (se c'è una sessione) token in un testo breve da copiare dall'app e incollare
/// nelle impostazioni del widget (l'app lo copia da `schieraxi://widget/collega`, vedi `CollegamentoWidget`). È il ripiego quando l'App Group non c'è. Il token è quello del WIDGET (`fw_`, solo lettura di
/// /api/oggi e /api/widget, 90 giorni, revocabile): mai quello della sessione.
enum CodiceWidget {
    static let prefisso = "schieraxi1."

    struct Contenuto: Codable, Equatable {
        var i: String
        var t: String?
    }

    static func crea(indirizzo: String, token: String?) -> String {
        let c = Contenuto(i: indirizzo, t: (token?.isEmpty ?? true) ? nil : token)
        let dati = (try? JSONEncoder().encode(c)) ?? Data()
        let b64 = dati.base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        return prefisso + b64
    }

    /// Legge un codice (o, per comodità, un semplice indirizzo https). `nil` se non si capisce.
    static func leggi(_ testo: String) -> Contenuto? {
        let t = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard t.count <= 2000 else { return nil }
        if t.hasPrefix(prefisso) {
            var b64 = String(t.dropFirst(prefisso.count)).replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
            while b64.count % 4 != 0 { b64.append("=") }
            guard let dati = Data(base64Encoded: b64), let c = try? JSONDecoder().decode(Contenuto.self, from: dati), !c.i.isEmpty else { return nil }
            return c
        }
        return t.lowercased().hasPrefix("http") ? Contenuto(i: t, t: nil) : nil
    }

    /// Da dove il widget prende indirizzo e token, in ordine: i dati dell'app CON il token (App Group) > il Keychain condiviso con il
    /// token > il codice di collegamento incollato nel widget (collegamento manuale) > l'indirizzo dell'app senza token (gruppo, poi
    /// Keychain) > il server pubblico dell'app. Così un codice incollato vale anche quando l'app passa l'indirizzo ma non il token.
    /// `pulisci` accetta solo indirizzi ammessi.
    static func destinazione(condiviso: DatiCondivisi, portachiavi: Contenuto? = nil, codice: String,
                             predefinito: String = ServerPubblico.indirizzo,
                             pulisci: (String) -> String?) -> (indirizzo: String, token: String?)? {
        var dellApp: (indirizzo: String, token: String?)?
        if let base = condiviso.indirizzo, let pulito = pulisci(base) { dellApp = (pulito, condiviso.token(per: base)) }
        if let d = dellApp, d.token != nil { return d }
        var delPortachiavi: (indirizzo: String, token: String?)?
        if let p = portachiavi, let pulito = pulisci(p.i) { delPortachiavi = (pulito, (p.t?.isEmpty ?? true) ? nil : p.t) }
        if let d = delPortachiavi, d.token != nil { return d }
        if let c = leggi(codice), let pulito = pulisci(c.i) { return (pulito, c.t) }
        if let d = dellApp ?? delPortachiavi { return d }
        guard let pulito = pulisci(predefinito) else { return nil }
        return (pulito, nil)
    }
}

/// Il collegamento del widget. Di solito è automatico (App Group o Keychain condiviso, vedi in cima al file). Se non lo è, il
/// widget dice «Tocca per collegare» e apre `schieraxi://widget/collega`; l'app prova di nuovo il collegamento automatico e, solo
/// se non va, crea il codice e lo mette negli appunti di QUESTO telefono per pochi minuti: l'utente lo incolla una volta in
/// «Modifica widget» > «Collegamento manuale» > «Codice di collegamento».
enum CollegamentoWidget {
    static let indirizzo = "schieraxi://widget/collega"
    static var url: URL? { URL(string: indirizzo) }
    /// Quanto resta il codice negli appunti (poi iOS lo toglie da solo).
    static let durataAppunti: TimeInterval = 5 * 60
    /// Il testo grande del widget non collegato.
    static let tocca = "Tocca per collegare"
    /// La riga sotto, nel widget: il resto lo spiega l'app.
    static let poi = "Si apre SchieraXI e lo collega"
    /// L'istruzione in una riga, nell'app (solo quando il collegamento automatico non va).
    static let istruzione = "Tieni premuto il widget, tocca «Modifica widget», attiva «Collegamento manuale» e incolla il codice."

    /// Il widget è collegato senza fare niente: l'app riesce a passargli i dati (App Group o Keychain condiviso) e, se il server
    /// ha gli account, c'è il token del widget da passargli.
    static func automatico(canale: Bool, conAccount: Bool, haToken: Bool) -> Bool {
        canale && (!conAccount || haToken)
    }

    /// Il widget va (ri)collegato: il server non accetta più il suo codice (401: token scaduto, rinnovato dall'app o revocato;
    /// anche se mostra ancora una copia vecchia), oppure non sa dove sta il server e non ha niente da mostrare. Un problema di
    /// rete non conta: lì basta aspettare.
    static func daCollegare(haDati: Bool, indirizzoMancante: Bool, accessoRichiesto: Bool) -> Bool {
        accessoRichiesto || (!haDati && indirizzoMancante)
    }
}
