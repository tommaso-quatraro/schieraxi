import SwiftUI

/// La scheda «Partite del turno» di Oggi: orari, e quando c'è una partita in corso il punteggio con il minuto (badge LIVE),
/// marcatori e cartellini. Le partite in cui giocano miei titolari hanno lo sfondo lime e i loro avatarini.
struct PartiteDelTurnoView: View {
    @ObservedObject var vm: OggiViewModel

    var body: some View {
        let giorni = vm.partitePerGiorno
        if !giorni.isEmpty {
            let live = vm.risultatiLive
            Carta("Partite del turno", simbolo: "soccerball") {
                ForEach(giorni) { giorno in
                    Text(giorno.titolo).titoletto().padding(.top, 4)
                    ForEach(giorno.partite) { p in
                        RigaPartitaView(partita: p, live: vm.dalVivo(p), titolari: vm.mieiTitolari(p))
                    }
                }
                if let nota = DirettaLogica.nota(fonte: live?.fonte), !(live?.partite ?? []).isEmpty {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(nota)
                        if let agg = DirettaLogica.aggiornatoAlle(live) { Text(agg) }
                    }
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.top, 2)
                }
            }
        }
    }
}

/// Una partita del turno. Con `live` mostra stato e punteggio; senza, solo l'orario.
struct RigaPartitaView: View {
    let partita: Partita
    let live: PartitaLive?
    let titolari: [MioTitolare]

    @Environment(\.accessibilityReduceMotion) private var ridotto
    @Environment(\.colorScheme) private var schema
    /// Lo sfondo che si accende per un attimo quando c'è un gol.
    @State private var lampo = false

    private var ora: String? { Quando.data(partita.data).map { Quando.ora($0) } }
    private var haPunteggio: Bool { live?.golCasa != nil && live?.golTrasferta != nil }
    private var inGioco: Bool { live?.inGioco ?? false }
    private var finita: Bool { live?.finita ?? (partita.giocata == true) }
    private var eventi: [EventoLive] { (haPunteggio ? live?.eventi : nil) ?? [] }
    private static let eventiVisibili = 6

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 10) {
                stato.frame(minWidth: 52, alignment: .leading)
                Text("\(partita.casa.capitalized) – \(partita.trasferta.capitalized)")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(finita ? Color.secondary : Color.primary)
                    .lineLimit(2)
                Spacer(minLength: 4)
                if !titolari.isEmpty { avatar }
                if haPunteggio {
                    Text(live?.punteggio ?? "–")
                        .font(.title3.weight(.bold)).monospacedDigit()
                        .contentTransition(ridotto ? .opacity : .numericText())
                }
            }
            if !eventi.isEmpty { elencoEventi }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, titolari.isEmpty ? 0 : 8)
        .background {
            ZStack {
                if !titolari.isEmpty {
                    RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color.capitano.opacity(schema == .dark ? 0.12 : 0.16))
                }
                RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color.capitano.opacity(lampo ? (ridotto ? 0.25 : 0.5) : 0))
            }
        }
        .animation(Tema.morbida, value: live?.punteggio)
        .onChange(of: live) { prima, dopo in
            guard DirettaLogica.golSegnato(prima: prima, dopo: dopo) else { return }
            lampo = true
            // Il lampo si spegne piano; con «Ridurre movimento» è più tenue e più lento, senza altro movimento.
            withAnimation(.easeOut(duration: ridotto ? 1.6 : 1.1)) { lampo = false }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(DirettaLogica.frase(casa: partita.casa, trasferta: partita.trasferta, live: live, ora: ora, titolari: titolari))
    }

    // MARK: pezzi

    @ViewBuilder
    private var stato: some View {
        switch live?.stato ?? "" {
        case "primo_tempo", "secondo_tempo", "in_corso":
            VStack(alignment: .leading, spacing: 1) {
                badgeLive
                if let m = live?.minuto { Text(m).font(.caption).monospacedDigit().foregroundStyle(.secondary) }
            }
        case "intervallo":
            VStack(alignment: .leading, spacing: 1) {
                badgeLive
                Text("Intervallo").font(.caption).foregroundStyle(Color.attenzione)
            }
        case "sospesa":
            VStack(alignment: .leading, spacing: 1) {
                badgeLive
                Text("Sospesa").font(.caption).foregroundStyle(Color.attenzione)
            }
        case "finita":
            Text("Finita").font(.caption).foregroundStyle(.secondary)
        case "rinviata":
            Text("Rinviata").font(.caption).foregroundStyle(Color.attenzione)
        default:
            if inGioco {
                badgeLive
            } else if partita.giocata == true && !haPunteggio {
                Text("Finita").font(.caption).foregroundStyle(.secondary)
            } else {
                Text(ora ?? "–").font(.caption).monospacedDigit().foregroundStyle(.secondary)
            }
        }
    }

    private var badgeLive: some View {
        Text("LIVE")
            .font(.caption2.weight(.heavy))
            .foregroundStyle(.white)
            .padding(.horizontal, 6).padding(.vertical, 1)
            .background(Color(red: 0.78, green: 0.13, blue: 0.13), in: Capsule())
    }

    /// Fino a quattro avatarini sovrapposti e «+N» per gli altri.
    private var avatar: some View {
        HStack(spacing: -7) {
            ForEach(Array(titolari.prefix(4))) { t in
                AvatarGiocatore(id: t.id, squadra: squadraDi(t), dimensione: 24, conNumero: false, nome: t.nome, ruolo: t.ruolo)
                    .background(Circle().fill(Color.sfondoScheda))
            }
            if titolari.count > 4 {
                Text("+\(titolari.count - 4)").font(.caption2.weight(.semibold)).foregroundStyle(.secondary).padding(.leading, 10)
            }
        }
    }

    /// Lo slug della squadra del titolare, come nella partita (la chiave del server può avere i separatori cambiati).
    private func squadraDi(_ t: MioTitolare) -> String {
        MieiTitolari.chiave(t.squadra ?? "") == MieiTitolari.chiave(partita.trasferta) ? partita.trasferta : partita.casa
    }

    private var elencoEventi: some View {
        VStack(alignment: .leading, spacing: 2) {
            ForEach(Array(eventi.prefix(Self.eventiVisibili).enumerated()), id: \.offset) { _, e in
                HStack(spacing: 4) {
                    if e.squadra == "trasferta" { Spacer(minLength: 0) }
                    simbolo(e)
                    Text("\(e.minuto ?? "") \(e.chi ?? "")\(e.tipo == "autogol" ? " (autogol)" : (e.tipo == "rigore" ? " (rigore)" : ""))")
                        .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    if e.squadra != "trasferta" { Spacer(minLength: 0) }
                }
            }
            if eventi.count > Self.eventiVisibili {
                Text("e altri \(eventi.count - Self.eventiVisibili)").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .padding(.leading, 62)
    }

    @ViewBuilder
    private func simbolo(_ e: EventoLive) -> some View {
        switch e.tipo ?? "" {
        case "giallo": Image(systemName: "rectangle.portrait.fill").foregroundStyle(Color.yellow).font(.caption2)
        case "rosso": Image(systemName: "rectangle.portrait.fill").foregroundStyle(Color.red).font(.caption2)
        case "autogol": Image(systemName: "soccerball").foregroundStyle(Color.malus).font(.caption2)
        default: Image(systemName: "soccerball").foregroundStyle(.secondary).font(.caption2)
        }
    }
}
