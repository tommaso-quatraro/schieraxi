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

/// Due colonne: casa a sinistra, trasferta a destra, una riga per evento, altezza minima. Con testo molto grande diventa una colonna
/// sola (prima la casa, poi la trasferta, ciascuna col nome della squadra).
struct ColonneEventi: View {
    let eventi: [EventoLive]
    var nomeCasa = ""
    var nomeTrasferta = ""
    var font: Font = .caption
    var colore: Color = .secondary
    var coloreRosso: Color = .red
    var coloreAutogol: Color = .orange
    /// nil = quante servono (app); 1 = una riga per evento, il testo si stringe (widget).
    var righeMax: Int?

    @Environment(\.dynamicTypeSize) private var dimensione

    private var colonneEventi: (casa: [EventoLive], trasferta: [EventoLive]) { EventiPartita.colonne(eventi) }

    var body: some View {
        let c = colonneEventi
        if c.casa.isEmpty && c.trasferta.isEmpty {
            EmptyView()
        } else if dimensione.isAccessibilitySize {
            VStack(alignment: .leading, spacing: 4) {
                colonna(c.casa, nome: nomeCasa, allineata: .leading)
                colonna(c.trasferta, nome: nomeTrasferta, allineata: .leading)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            HStack(alignment: .top, spacing: 12) {
                colonna(c.casa, nome: "", allineata: .leading).frame(maxWidth: .infinity, alignment: .leading)
                colonna(c.trasferta, nome: "", allineata: .trailing).frame(maxWidth: .infinity, alignment: .trailing)
            }
        }
    }

    @ViewBuilder
    private func colonna(_ lista: [EventoLive], nome: String, allineata: HorizontalAlignment) -> some View {
        if !lista.isEmpty {
            VStack(alignment: allineata, spacing: 1) {
                if !nome.isEmpty {
                    Text(nome.capitalized).font(font.weight(.semibold)).foregroundStyle(colore)
                }
                ForEach(Array(lista.enumerated()), id: \.offset) { _, e in riga(e, allineata: allineata) }
            }
        }
    }

    private func riga(_ e: EventoLive, allineata: HorizontalAlignment) -> some View {
        let aDestra = allineata == .trailing
        return HStack(alignment: .firstTextBaseline, spacing: 3) {
            if !aDestra { icona(e) }
            Text(e.testoCompatto)
                .font(font)
                .foregroundStyle(e.tipoVisibile == .rosso ? coloreRosso : colore)
                .lineLimit(righeMax)
                .minimumScaleFactor(righeMax == nil ? 1 : 0.7)
                .multilineTextAlignment(aDestra ? .trailing : .leading)
                .fixedSize(horizontal: false, vertical: true)
            if aDestra { icona(e) }
        }
    }

    @ViewBuilder
    private func icona(_ e: EventoLive) -> some View {
        switch e.tipoVisibile {
        case .some(.rosso): Image(systemName: "rectangle.portrait.fill").font(font).foregroundStyle(coloreRosso)
        case .some(.autogol): Image(systemName: "soccerball").font(font).foregroundStyle(coloreAutogol)
        case .some(.rigoreFallito): Image(systemName: "xmark.circle").font(font).foregroundStyle(coloreAutogol)
        default: Image(systemName: "soccerball").font(font).foregroundStyle(colore)
        }
    }
}
