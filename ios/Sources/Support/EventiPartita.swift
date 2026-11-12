import SwiftUI

// Gli eventi di una partita come si vedono in Oggi e nel widget «Partite live»: SOLO gol (con l'assist, se c'è), autogol, rigori
// (segnati e sbagliati/parati) e cartellini rossi, anche per doppia ammonizione. I gialli non si mostrano mai (anche se un server
// vecchio li manda ancora). Nessun limite di numero: la lista è in due colonne, casa a sinistra e trasferta a destra.
// Questo file sta sia nell'app sia nel widget: niente dipendenze dal resto dell'app.

enum TipoEventoVisibile: Equatable {
    case gol, rigore, autogol, rigoreFallito, rosso
}

extension EventoLive {
    /// Il tipo da mostrare, o nil se l'evento non va in elenco (giallo, tipi nuovi che non conosciamo).
    var tipoVisibile: TipoEventoVisibile? {
        let t = (tipo ?? "").lowercased()
        switch t {
        case "gol": return .gol
        case "rigore": return .rigore
        case "autogol": return .autogol
        case "rosso": return .rosso
        case "doppio_giallo", "secondo_giallo", "doppia_ammonizione", "giallo_rosso", "rosso_doppio_giallo": return .rosso
        default:
            // «rigore_sbagliato», «rigore_parato», «rigore_fallito»…
            if t.hasPrefix("rigore_") || t.hasPrefix("rigore-") { return .rigoreFallito }
            return nil
        }
    }

    var daMostrare: Bool { tipoVisibile != nil }
    var inTrasferta: Bool { squadra == "trasferta" }

    private var perDoppiaAmmonizione: Bool { (tipo ?? "").lowercased() != "rosso" && tipoVisibile == .rosso }
    private var rigoreParato: Bool { (tipo ?? "").lowercased().contains("parat") }
    private var nomeOCosa: String {
        if let c = chi?.trimmingCharacters(in: .whitespaces), !c.isEmpty { return c }
        switch tipoVisibile {
        case .some(.autogol): return "Autogol"
        case .some(.rosso): return "Espulsione"
        case .some(.rigore), .some(.rigoreFallito): return "Rigore"
        default: return "Gol"
        }
    }

    /// Una riga compatta: «6' Varsone (rig.)», «33' Poberga (ass. Lemao)», «40' Djorsati (aut.)», «71' De Valk».
    var testoCompatto: String {
        var nota = ""
        switch tipoVisibile {
        case .some(.rigore): nota = "rig."
        case .some(.rigoreFallito): nota = rigoreParato ? "rig. parato" : "rig. sbagl."
        case .some(.autogol): nota = "aut."
        case .some(.rosso): nota = perDoppiaAmmonizione ? "2° giallo" : ""
        case .some(.gol): if let a = assistPulito { nota = "ass. \(a)" }
        case .none: break
        }
        let minutoTesto = (minuto ?? "").trimmingCharacters(in: .whitespaces)
        return [minutoTesto, nomeOCosa, nota.isEmpty ? "" : "(\(nota))"].filter { !$0.isEmpty }.joined(separator: " ")
    }

    var assistPulito: String? {
        guard let a = assist?.trimmingCharacters(in: .whitespaces), !a.isEmpty else { return nil }
        return a
    }
}

enum EventiPartita {
    /// Solo gli eventi da mostrare, nell'ordine del server (cronologico).
    static func visibili(_ eventi: [EventoLive]?) -> [EventoLive] {
        (eventi ?? []).filter(\.daMostrare)
    }

    static func colonne(_ eventi: [EventoLive]?) -> (casa: [EventoLive], trasferta: [EventoLive]) {
        let v = visibili(eventi)
        return (v.filter { !$0.inTrasferta }, v.filter(\.inTrasferta))
    }

    /// Quante righe occupa l'elenco a due colonne (serve al widget per decidere quante partite entrano).
    static func righe(_ eventi: [EventoLive]?) -> Int {
        let c = colonne(eventi)
        return max(c.casa.count, c.trasferta.count)
    }
}
