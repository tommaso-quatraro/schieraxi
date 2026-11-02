import SwiftUI

/// La scheda «Partite del turno» di Oggi: orari, e quando c'è una partita in corso il punteggio con il minuto (badge LIVE),
/// marcatori (con assist), rigori e cartellini rossi, tutti, in due colonne. Le partite in cui giocano miei titolari hanno lo sfondo lime,
/// un segno lime a sinistra e i loro avatarini. Tutte le righe stanno sulla stessa griglia: stato, squadre e punteggio in colonna.
struct PartiteDelTurnoView: View {
    @ObservedObject var vm: OggiViewModel

    var body: some View {
        let giorni = vm.partitePerGiorno
        if !giorni.isEmpty {
            let live = vm.risultatiLive
            // La colonna del punteggio c'è in tutte le righe appena una partita ha un punteggio: così avatarini e punteggi restano in colonna.
            let conPunteggio = giorni.contains { g in g.partite.contains { RigaPartitaView.haPunteggio(vm.dalVivo($0)) } }
            Carta("Partite del turno", simbolo: "soccerball") {
                ForEach(giorni) { giorno in
                    Text(giorno.titolo).titoletto().padding(.top, 4)
                    ForEach(giorno.partite) { p in
                        RigaPartitaView(partita: p, live: vm.dalVivo(p), titolari: vm.mieiTitolari(p), colonnaPunteggio: conPunteggio)
                    }
                }
                if let nota = DirettaLogica.nota(fonte: live?.fonte), !(live?.partite ?? []).isEmpty {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(nota)
                        if let agg = DirettaLogica.aggiornatoAlle(live) { Text(agg) }
                    }
                    .font(.caption2)
                    .foregroundStyle(Color.testoSecondario)
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
    /// Riserva lo spazio del punteggio anche se questa partita non ce l'ha (perché ce l'ha un'altra del turno).
    var colonnaPunteggio = true

    @Environment(\.accessibilityReduceMotion) private var ridotto
    @Environment(\.colorScheme) private var schema
    @Environment(\.dynamicTypeSize) private var dimensioneTesto
    /// Larghezze fisse della griglia (crescono con la dimensione del testo): stato/ora e un numero di gol.
    @ScaledMetric(relativeTo: .caption) private var larghezzaStato: CGFloat = 60
    @ScaledMetric(relativeTo: .title3) private var larghezzaGol: CGFloat = 14
    /// Lo sfondo che si accende per un attimo quando c'è un gol.
    @State private var lampo = false

    private var ora: String? { Quando.data(partita.data).map { Quando.ora($0) } }
    static func haPunteggio(_ live: PartitaLive?) -> Bool { live?.golCasa != nil && live?.golTrasferta != nil }
    private var haPunteggio: Bool { Self.haPunteggio(live) }
    private var mia: Bool { !titolari.isEmpty }
    /// Con le misure di accessibilità lo stato va sopra le squadre: in colonna non ci starebbe.
    private var impilata: Bool { dimensioneTesto.isAccessibilitySize }
    private var inGioco: Bool { live?.inGioco ?? false }
    private var finita: Bool { live?.finita ?? (partita.giocata == true || partita.stato == "finita") }
    private var eventi: [EventoLive] { haPunteggio ? EventiPartita.visibili(live?.eventi) : [] }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if impilata {
                stato
                HStack(spacing: 8) {
                    squadre.frame(maxWidth: .infinity, alignment: .leading)
                    if mia { avatar }
                    punteggio
                }
            } else {
                // Griglia unica: stato a larghezza fissa, squadre nello spazio che resta, avatarini e punteggio a destra.
                HStack(spacing: 10) {
                    stato.lineLimit(1).minimumScaleFactor(0.8).frame(width: larghezzaStato, alignment: .leading)
                    squadre.frame(maxWidth: .infinity, alignment: .leading)
                    if mia { avatar }
                    punteggio
                }
            }
            if !eventi.isEmpty { elencoEventi.padding(.leading, impilata ? 0 : larghezzaStato + 10) }
        }
        // Stessi margini per tutte le righe: le mie si riconoscono da sfondo e segno, senza spostare il contenuto.
        .padding(.vertical, 6)
        .padding(.horizontal, 10)
        .frame(minHeight: Tema.areaTocco)
        .background {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(mia ? Color.capitano.opacity(schema == .dark ? 0.12 : 0.16) : Color.primary.opacity(schema == .dark ? 0.05 : 0.035))
                if mia {
                    Capsule().fill(Color.capitano).frame(width: 3).padding(.vertical, 9).padding(.leading, 3)
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
            // Chi usa VoiceOver non vede il lampo: il gol si annuncia a voce.
            if let frase = DirettaLogica.annuncioGol(casa: partita.casa, trasferta: partita.trasferta, prima: prima, dopo: dopo) {
                AccessibilityNotification.Announcement(frase).post()
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(DirettaLogica.frase(casa: partita.casa, trasferta: partita.trasferta, live: live, ora: ora, titolari: titolari))
    }

    // MARK: pezzi

    /// Come la web: le sigle, prima la squadra di casa («MIL vs INT»). VoiceOver legge i nomi interi (etichetta della riga).
    private var squadre: some View {
        Text("\(ColoriSquadra.sigla(partita.casa)) vs \(ColoriSquadra.sigla(partita.trasferta))")
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(finita ? Color.testoSecondario : Color.primary)
            .lineLimit(2)
            .fixedSize(horizontal: false, vertical: true)
    }

    /// Il punteggio in tre pezzi a larghezza fissa (gol di casa a destra, trattino, gol in trasferta a sinistra) con cifre tabulari:
    /// i trattini di tutte le righe stanno in colonna. Senza punteggio lo spazio resta, vuoto, se un'altra partita del turno ce l'ha.
    @ViewBuilder
    private var punteggio: some View {
        if haPunteggio || colonnaPunteggio {
            HStack(spacing: 3) {
                gol(live?.golCasa).frame(minWidth: larghezzaGol, alignment: .trailing)
                Text("–")
                gol(live?.golTrasferta).frame(minWidth: larghezzaGol, alignment: .leading)
            }
            .font(.title3.weight(.bold))
            .monospacedDigit()
            .opacity(haPunteggio ? 1 : 0)
            .fixedSize()
            .accessibilityHidden(true)
        }
    }

    private func gol(_ n: Int?) -> some View {
        Text(n.map(String.init) ?? "")
            .contentTransition(ridotto ? .opacity : .numericText(value: Double(n ?? 0)))
    }

    @ViewBuilder
    private var stato: some View {
        switch live?.stato ?? "" {
        case "primo_tempo", "secondo_tempo", "in_corso":
            VStack(alignment: .leading, spacing: 1) {
                badgeLive
                if let m = live?.minuto { Text(m).font(.caption).monospacedDigit().foregroundStyle(Color.testoSecondario) }
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
            Text("Finita").font(.caption).foregroundStyle(Color.testoSecondario)
        case "rinviata":
            Text("Rinviata").font(.caption).foregroundStyle(Color.attenzione)
        default:
            if inGioco {
                badgeLive
            } else if (partita.giocata == true || partita.stato == "finita") && !haPunteggio {
                Text("Finita").font(.caption).foregroundStyle(Color.testoSecondario)
            } else if partita.stato == "in_corso" {
                // senza la diretta (spenta o non raggiungibile) lo stato arriva da Oggi
                Text("In corso").font(.caption.weight(.semibold)).foregroundStyle(Color.informazione)
            } else if partita.stato == "rinviata" {
                Text("Rinviata").font(.caption).foregroundStyle(Color.attenzione)
            } else {
                Text(ora ?? "–").font(.caption).monospacedDigit().foregroundStyle(Color.testoSecondario)
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
                Text("+\(titolari.count - 4)").font(.caption2.weight(.semibold)).foregroundStyle(Color.testoSecondario).padding(.leading, 10)
            }
        }
    }

    /// Lo slug della squadra del titolare, come nella partita (la chiave del server può avere i separatori cambiati).
    private func squadraDi(_ t: MioTitolare) -> String {
        MieiTitolari.chiave(t.squadra ?? "") == MieiTitolari.chiave(partita.trasferta) ? partita.trasferta : partita.casa
    }

    private var elencoEventi: some View {
        ColonneEventi(eventi: eventi, nomeCasa: partita.casa, nomeTrasferta: partita.trasferta, font: .caption,
                      coloreRosso: Color.malus, coloreAutogol: Color.attenzione)
            .padding(.top, 1)
    }
}
