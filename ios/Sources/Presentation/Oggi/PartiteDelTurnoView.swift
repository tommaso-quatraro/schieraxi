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
            // La colonna del punteggio c'è in tutte le righe appena una partita ha un punteggio (in diretta o del calendario): così
            // avatarini e punteggi restano in colonna.
            let conPunteggio = giorni.contains { g in
                g.partite.contains { RigaPartitaView.golMostrati(live: vm.dalVivo($0), partita: $0) != nil }
            }
            Carta(TestiOggi.partiteDelTurno, simbolo: "soccerball") {
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

/// Una partita del turno. Con `live` mostra stato e punteggio; senza, l'orario (o lo stato che dice Oggi) e, se la partita è
/// giocata, il risultato del calendario, come la web.
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
    /// La diretta ha il punteggio della partita.
    nonisolated static func haPunteggio(_ live: PartitaLive?) -> Bool { live?.golCasa != nil && live?.golTrasferta != nil }

    /// Cosa scrive la riga al posto dell'ora senza uno stato in diretta, come `oraTesto` di `mostraOggi` della web: «Rinviata»,
    /// «In corso» (lo stato arriva da Oggi), «Finita» per una partita finita per l'orario ma senza il risultato del calendario;
    /// altrimenti l'ora d'inizio, anche per una partita giocata (accanto c'è il risultato, come sulla web).
    enum SenzaDiretta: Equatable { case ora, inCorso, finita, rinviata }

    nonisolated static func statoSenzaDiretta(_ p: Partita) -> SenzaDiretta {
        if p.stato == "rinviata" { return .rinviata }
        if p.stato == "in_corso" { return .inCorso }
        if p.stato == "finita" && p.giocata != true { return .finita }
        return .ora
    }

    /// I gol da scrivere nella colonna del punteggio: quelli in diretta se ci sono, altrimenti il risultato del calendario
    /// (`punteggioUfficiale`), che c'è anche con «Risultati in diretta» spenta, come sulla web (`pt || el.dataset.pt`).
    nonisolated static func golMostrati(live: PartitaLive?, partita: Partita) -> (casa: Int, trasferta: Int)? {
        if let c = live?.golCasa, let t = live?.golTrasferta { return (c, t) }
        return partita.punteggioUfficiale
    }

    /// La frase di VoiceOver della riga: con il risultato del calendario, se non c'è quello in diretta («Inter 2, Roma 1, finita»).
    nonisolated static func voce(partita: Partita, live: PartitaLive?, ora: String?, titolari: [MioTitolare]) -> String {
        var letta = live
        if !Self.haPunteggio(live), let u = partita.punteggioUfficiale {
            letta = PartitaLive(casa: partita.casa, trasferta: partita.trasferta, data: partita.data, stato: "finita",
                                golCasa: u.casa, golTrasferta: u.trasferta, eventi: live?.eventi)
        }
        return DirettaLogica.frase(casa: partita.casa, trasferta: partita.trasferta, live: letta, ora: ora, titolari: titolari)
    }

    private var mia: Bool { !titolari.isEmpty }
    /// Con le misure di accessibilità lo stato va sopra le squadre: in colonna non ci starebbe.
    private var impilata: Bool { dimensioneTesto.isAccessibilitySize }
    private var finita: Bool { live?.finita ?? (partita.giocata == true || partita.stato == "finita") }
    /// Marcatori, rigori e rossi: solo dalla diretta (il calendario dà soltanto il risultato).
    private var eventi: [EventoLive] { Self.haPunteggio(live) ? EventiPartita.visibili(live?.eventi) : [] }

    /// Cosa scrive la riga con la diretta, come `etichetta` di `fanta/web/live.js`: «LIVE» con il minuto (o «In aggiornamento»
    /// per uno stato nuovo con il punteggio), «LIVE» e «Intervallo», «Finita», «Rinviata», «Sospesa» senza «LIVE». Nil: niente
    /// diretta per questa partita (si scrive l'ora, o lo stato che dice Oggi).
    enum Diretta: Equatable { case inGioco(minuto: String?), intervallo, finita, rinviata, sospesa }

    nonisolated static func diretta(_ l: PartitaLive?) -> Diretta? {
        guard let l else { return nil }
        let minuto = l.minuto.flatMap { $0.trimmingCharacters(in: .whitespaces).isEmpty ? nil : $0 }
        switch l.stato ?? "" {
        case "primo_tempo", "secondo_tempo", "in_corso": return .inGioco(minuto: minuto)
        case "intervallo": return .intervallo
        case "finita": return .finita
        case "rinviata": return .rinviata
        case "sospesa": return .sospesa
        case "da_giocare", "": return nil
        default: return l.inGioco ? .inGioco(minuto: minuto ?? TestiOggi.inAggiornamento) : nil
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if impilata {
                stato
                HStack(spacing: 8) {
                    squadre.frame(maxWidth: .infinity, alignment: .leading)
                    punteggio
                }
            } else {
                // Griglia unica: stato a larghezza fissa, squadre nello spazio che resta, punteggio a destra.
                HStack(spacing: 10) {
                    stato.lineLimit(1).minimumScaleFactor(0.8).frame(width: larghezzaStato, alignment: .leading)
                    squadre.frame(maxWidth: .infinity, alignment: .leading)
                    punteggio
                }
            }
            // Sotto, come la web: i volti dei tuoi titolari e «2 tuoi titolari»
            if mia { miei.padding(.leading, impilata ? 0 : larghezzaStato + 10) }
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
        .accessibilityLabel(Self.voce(partita: partita, live: live, ora: ora, titolari: titolari))
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
    /// Senza la diretta il risultato del calendario (`golMostrati`).
    @ViewBuilder
    private var punteggio: some View {
        let mostrati = Self.golMostrati(live: live, partita: partita)
        if mostrati != nil || colonnaPunteggio {
            HStack(spacing: 3) {
                gol(mostrati?.casa).frame(minWidth: larghezzaGol, alignment: .trailing)
                Text("–")
                gol(mostrati?.trasferta).frame(minWidth: larghezzaGol, alignment: .leading)
            }
            .font(.title3.weight(.bold))
            .monospacedDigit()
            .opacity(mostrati != nil ? 1 : 0)
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
        switch Self.diretta(live) {
        case .inGioco(let minuto)?:
            VStack(alignment: .leading, spacing: 1) {
                badgeLive
                if let minuto {
                    // «In aggiornamento» è lungo per la colonna: va su due righe invece di tagliarsi
                    Text(minuto).font(.caption).monospacedDigit().foregroundStyle(Color.testoSecondario)
                        .lineLimit(2)
                }
            }
        case .intervallo?:
            VStack(alignment: .leading, spacing: 1) {
                badgeLive
                Text("Intervallo").font(.caption).foregroundStyle(Color.attenzione)
            }
        case .sospesa?:
            Text(TestiOggi.sospesa).font(.caption).foregroundStyle(Color.attenzione)
        case .finita?:
            Text("Finita").font(.caption).foregroundStyle(Color.testoSecondario)
        case .rinviata?:
            Text("Rinviata").font(.caption).foregroundStyle(Color.attenzione)
        case nil:
            // senza la diretta (spenta o non raggiungibile) lo stato arriva da Oggi, come `oraTesto` della web
            switch Self.statoSenzaDiretta(partita) {
            case .rinviata:
                Text("Rinviata").font(.caption).foregroundStyle(Color.attenzione)
            case .inCorso:
                Text("In corso").font(.caption.weight(.semibold)).foregroundStyle(Color.informazione)
            case .finita:
                Text("Finita").font(.caption).foregroundStyle(Color.testoSecondario)
            case .ora:
                Text(ora ?? "–").font(.caption).monospacedDigit().foregroundStyle(Color.testoSecondario)
            }
        }
    }

    /// I volti dei tuoi titolari (fino a quattro, poi «+N») e, accanto, «2 tuoi titolari», come la web (`oggi.n_titolari`).
    private var miei: some View {
        HStack(spacing: 12) {
            avatar
            Text(TestiOggi.tuoiTitolari(titolari.count)).font(.caption).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityHidden(true)          // la frase della riga dice già chi gioca
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
