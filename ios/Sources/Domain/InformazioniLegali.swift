import Foundation

/// Le pagine di Privacy, Termini d'uso e Crediti e fonti sono sul server di chi usa SchieraXI: l'app non ha indirizzi dentro (il repository e l'IPA sono pubblici),
/// compone il collegamento con l'indirizzo che l'utente ha scritto. Qui solo logica pura, provata nei test.
enum PaginaServer: String, CaseIterable {
    case privacy
    case termini
    case crediti

    var titolo: String {
        switch self {
        case .privacy: return "Privacy"
        case .termini: return "Termini d'uso"
        case .crediti: return "Crediti e fonti"
        }
    }

    var icona: String {
        switch self {
        case .privacy: return "hand.raised"
        case .termini: return "doc.text"
        case .crediti: return "text.badge.checkmark"
        }
    }
}

/// Una voce di Impostazioni > Informazioni: una pagina del server da aprire nel browser, oppure «Crediti e fonti» letta dentro l'app.
enum VoceInformazioni: Hashable {
    case browser(PaginaServer, URL)
    case creditiNellApp

    var titolo: String {
        switch self {
        case .browser(let pagina, _): return pagina.titolo
        case .creditiNellApp: return PaginaServer.crediti.titolo
        }
    }

    var icona: String {
        switch self {
        case .browser(let pagina, _): return pagina.icona
        case .creditiNellApp: return PaginaServer.crediti.icona
        }
    }
}

enum InformazioniLegali {
    /// Le voci di Impostazioni > Informazioni. Con un server vero: Privacy, Termini d'uso e Crediti e fonti, le sue pagine, nel
    /// browser e nell'ordine della web. Nella prova con dati di esempio (e nelle foto, che usano la stessa demo) non c'è un server
    /// da aprire: resta solo «Crediti e fonti», dentro l'app.
    static func vociInformazioni(prova: Bool, server: String) -> [VoceInformazioni] {
        if prova { return [.creditiNellApp] }
        return PaginaServer.allCases.compactMap { pagina in indirizzo(pagina, server: server).map { .browser(pagina, $0) } }
    }

    /// Il collegamento a una pagina del server (`<server>/privacy`, `<server>/termini`, `<server>/crediti`). `nil` se l'indirizzo del server manca o non è valido.
    static func indirizzo(_ pagina: PaginaServer, server: String) -> URL? {
        var base = server.trimmingCharacters(in: .whitespacesAndNewlines)
        while base.hasSuffix("/") { base.removeLast() }
        guard !base.isEmpty, IndirizzoServer.valido(base) else { return nil }
        return URL(string: base + "/" + pagina.rawValue)
    }

    /// Il collegamento al codice sorgente, come lo manda il server (campo facoltativo `sorgente` di `/api/stato`).
    /// Solo `https://` con un nome di sito, senza utente e password e non troppo lungo: tutto il resto si ignora e la voce non compare.
    static func sorgente(_ testo: String?) -> URL? {
        guard let testo else { return nil }
        let pulito = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !pulito.isEmpty, pulito.count <= 300,
              let url = URL(string: pulito),
              url.scheme?.lowercased() == "https",
              let host = url.host, !host.isEmpty,
              url.user == nil, url.password == nil else { return nil }
        return url
    }
}

/// Solo il campo che serve a questa parte dell'app: `/api/stato` ha molto altro, qui non interessa.
struct StatoSorgente: Decodable {
    let sorgente: String?
}
