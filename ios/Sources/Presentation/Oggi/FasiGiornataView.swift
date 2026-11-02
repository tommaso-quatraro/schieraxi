import SwiftUI

// Le schede di Oggi durante e dopo la giornata (campo `fase` del server). Testi in `TestiFase` (Domain/FasiGiornata.swift).
// Durante la giornata non si mostrano consigli su chi schierare: solo punti, chi va a punteggio e cambi dalla panchina.

/// Fase `in_corso`: punti fatti finora (grandi), punti previsti a fine giornata, quanti voti mancano, partite.
struct CartaGiornataInCorso: View {
    let blocco: GiornataInCorso?
    /// I punti attesi della formazione prima della giornata (`formazione.punteggio_atteso`).
    let attesiPrima: Double?
    let partite: ContoPartite?
    @ScaledMetric(relativeTo: .largeTitle) private var corpoGrande: CGFloat = 46

    var body: some View {
        Carta("Giornata in corso", simbolo: "dot.radiowaves.left.and.right") {
            if let b = blocco {
                Text(TestiFase.formazioneDi(b.formazioneDi))
                    .font(.subheadline).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        fatti(b)
                        Spacer(minLength: 0)
                        previsti(b, allineamento: .trailing)
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        fatti(b)
                        previsti(b, allineamento: .leading)
                    }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(voce(b))
                if let a = TestiFase.ancora(b.ancoraDaGiocare) {
                    Label(a, systemImage: "hourglass").font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let m = TestiFase.modificatore(b.modificatore) {
                    Label(m, systemImage: "shield.lefthalf.filled").font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                }
            } else {
                Text("La giornata è in corso. I punti compariranno qui appena si sa quale formazione hai schierato.")
                    .font(.subheadline).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let c = partite, let testo = TestiFase.partite(c) {
                Label(testo, systemImage: "soccerball")
                    .font(.footnote).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityLabel(TestiFase.partiteVoce(c) ?? testo)
            }
        }
    }

    private func fatti(_ b: GiornataInCorso) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            NumeroCheSale(valore: b.puntiFatti ?? 0)
                .font(.system(size: corpoGrande, weight: .bold, design: .rounded))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Text("punti fatti finora").font(.caption).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func previsti(_ b: GiornataInCorso, allineamento: HorizontalAlignment) -> some View {
        let testo: TextAlignment = allineamento == .trailing ? .trailing : .leading
        VStack(alignment: allineamento, spacing: 1) {
            if let p = b.puntiPrevisti {
                Text(Formato.punti(p)).font(.title2.bold()).monospacedDigit()
                Text("a fine giornata, circa").font(.caption).foregroundStyle(.secondary)
            }
            if let prima = attesiPrima {
                Text("attesi prima: \(Formato.punti(prima))").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .multilineTextAlignment(testo)
    }

    private func voce(_ b: GiornataInCorso) -> String {
        var frasi = ["Punti fatti finora: \(Formato.punti(b.puntiFatti))"]
        if let p = b.puntiPrevisti { frasi.append("a fine giornata, circa \(Formato.punti(p))") }
        if let prima = attesiPrima { frasi.append("attesi prima della giornata: \(Formato.punti(prima))") }
        return frasi.joined(separator: ". ")
    }
}

/// Fase `in_corso`: i cambi dalla panchina, già fatti o probabili.
struct CartaCambiPanchina: View {
    let cambi: [CambioPanchina]
    @ScaledMetric(relativeTo: .body) private var latoIcona: CGFloat = 26

    var body: some View {
        Carta("Cambi dalla panchina", simbolo: "arrow.left.arrow.right") {
            ForEach(Array(cambi.enumerated()), id: \.offset) { i, c in
                RigaConFilo(prima: i == 0) { riga(c) }
            }
        }
    }

    private func riga(_ c: CambioPanchina) -> some View {
        let colore: Color = c.certa ? .verde : .attenzione
        return HStack(alignment: .center, spacing: 10) {
            Image(systemName: c.certa ? "checkmark.circle.fill" : "clock")
                .font(.body).foregroundStyle(colore)
                .frame(width: latoIcona)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(TestiFase.cambio(c)).font(.subheadline.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)
                if let m = TestiFase.motivo(c.motivo) {
                    Text(m).font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer(minLength: 6)
            Capsula(testo: TestiFase.etichettaCambio(c), colore: colore)
        }
        .frame(minHeight: Tema.areaTocco)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel([TestiFase.etichettaCambio(c), TestiFase.cambio(c), TestiFase.motivo(c.motivo)].compactMap { $0 }.joined(separator: ". "))
    }
}

/// Fase `in_corso`: chi va a punteggio (titolari, chi entra dalla panchina) con il fantavoto, l'ora o lo stato della partita.
struct CartaChiGioca: View {
    let blocco: GiornataInCorso
    @Environment(\.apriGiocatore) private var apri
    @State private var panchinaAperta = false

    private var titolari: [GiocatoreInCorso] { blocco.giocatori.filter(\.titolare) }
    private var entrano: [GiocatoreInCorso] { blocco.giocatori.filter { !$0.titolare && $0.aPunteggio } }
    private var panchina: [GiocatoreInCorso] { blocco.giocatori.filter { !$0.titolare && !$0.aPunteggio } }

    var body: some View {
        Carta(blocco.formazioneDi == "tua" ? "La tua formazione" : "La formazione consigliata", simbolo: "person.3") {
            ForEach(Array(titolari.enumerated()), id: \.element.id) { i, g in
                RigaConFilo(prima: i == 0) { RigaGiocatoreInCorso(g: g, nota: g.aPunteggio ? nil : "Sostituito", apri: apri) }
            }
            if !entrano.isEmpty {
                Text("Entrano dalla panchina").titoletto().padding(.top, 6)
                ForEach(Array(entrano.enumerated()), id: \.element.id) { i, g in
                    RigaConFilo(prima: i == 0) { RigaGiocatoreInCorso(g: g, nota: "Dalla panchina", apri: apri) }
                }
            }
            if !panchina.isEmpty {
                DisclosureGroup(isExpanded: $panchinaAperta) {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(panchina.enumerated()), id: \.element.id) { i, g in
                            RigaConFilo(prima: i == 0) { RigaGiocatoreInCorso(g: g, nota: nil, apri: apri) }
                        }
                    }
                    .padding(.top, 6)
                } label: {
                    Text("Panchina (\(Formato.giocatori(panchina.count)))").font(.subheadline.weight(.semibold))
                        .frame(minHeight: Tema.areaTocco, alignment: .leading)
                }
                .tint(.secondary)
                .padding(.top, 4)
            }
        }
    }
}

/// Una riga di chi gioca: ruolo, nome, squadra (per esteso) e a destra il fantavoto, oppure l'ora o lo stato della partita.
/// Chi non va più a punteggio (sostituito) è più tenue e lo dice anche a parole.
struct RigaGiocatoreInCorso: View {
    let g: GiocatoreInCorso
    let nota: String?
    let apri: (Int) -> Void

    private var squadra: String? {
        guard let s = g.squadra, !s.isEmpty else { return nil }
        return s.replacingOccurrences(of: "_", with: " ").replacingOccurrences(of: "-", with: " ").capitalized
    }

    var body: some View {
        Button { apri(g.id) } label: {
            HStack(alignment: .center, spacing: 10) {
                BadgeRuolo(ruolo: g.ruolo ?? "?")
                VStack(alignment: .leading, spacing: 2) {
                    Text(g.nome).font(.headline).lineLimit(2)
                    let sotto = [squadra, nota].compactMap { $0 }.joined(separator: " · ")
                    if !sotto.isEmpty {
                        Text(sotto).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                    }
                }
                Spacer(minLength: 6)
                valore
            }
            .opacity(g.aPunteggio || !g.titolare ? 1 : 0.6)
            .frame(minHeight: Tema.areaTocco)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(voce)
        .accessibilityHint("Apre la scheda del giocatore")
    }

    @ViewBuilder
    private var valore: some View {
        switch g.stato {
        case "fatto":
            Text(TestiFase.valore(g))
                .font(.title3.bold()).monospacedDigit()
                .foregroundStyle(coloreVoto)
        case "in_corso":
            Capsula(testo: TestiFase.valore(g), colore: .informazione)
        case "senza_voto":
            Capsula(testo: TestiFase.valore(g), colore: .malus)
        case "rinviata":
            Capsula(testo: TestiFase.valore(g), colore: .attenzione)
        case "attesa_voti":
            Capsula(testo: TestiFase.valore(g), colore: .secondary)
        default:
            Text(TestiFase.valore(g)).font(.subheadline).monospacedDigit().foregroundStyle(.secondary)
        }
    }

    /// Verde dal 7 in su, rosso sotto il 6: il numero resta comunque scritto (il colore non è l'unica informazione).
    private var coloreVoto: Color {
        guard let v = g.fantavoto else { return .primary }
        if v >= 7 { return .verde }
        if v < 6 { return .malus }
        return .primary
    }

    private var voce: String {
        var parti = [g.nome, nomeRuolo(g.ruolo ?? "")]
        if let squadra { parti.append(squadra) }
        var frase = parti.joined(separator: ", ") + ": " + TestiFase.valoreVoce(g)
        if let nota { frase += ". " + nota }
        return frase
    }
}

/// Fase `finita`: com'è andata la giornata appena chiusa (fatti contro attesi, fascia, confronto con la consigliata) e il Diario.
struct CartaRiepilogoGiornata: View {
    let riepilogo: RiepilogoGiornata?
    @Environment(\.funzioni) private var funzioni
    @EnvironmentObject private var nav: Navigazione
    @ScaledMetric(relativeTo: .largeTitle) private var corpoGrande: CGFloat = 46

    var body: some View {
        Carta("Com'è andata", simbolo: "flag.checkered") {
            if let r = riepilogo, let fatti = r.puntiFatti {
                let chi = r.formazioneDi == "tua" ? "con la tua formazione" : "con la formazione consigliata"
                Text([TestiFase.giornata(serieA: r.giornata, lega: r.giornataLega), chi].compactMap { $0 }.joined(separator: ", ").primaMaiuscola)
                    .font(.subheadline).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        numeroFatti(fatti)
                        Spacer(minLength: 0)
                        attesi(r, allineamento: .trailing)
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        numeroFatti(fatti)
                        attesi(r, allineamento: .leading)
                    }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(voce(r, fatti: fatti))
                if let s = TestiFase.scarto(fatti: fatti, attesi: r.puntiAttesi) {
                    let sopra = fatti >= (r.puntiAttesi ?? fatti)
                    Label(s, systemImage: sopra ? "arrow.up.right" : "arrow.down.right")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(sopra ? Color.esitoBuono : Color.malus)
                }
                if let f = TestiFase.fascia(r) {
                    Text(f).font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                if let c = TestiFase.confronto(r) {
                    Label(c, systemImage: "sportscourt").font(.subheadline).fixedSize(horizontal: false, vertical: true)
                }
                if let n = TestiFase.notaDiario(r) {
                    Text(n).font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
            } else {
                Text("La giornata è finita. I punti compariranno qui appena escono i voti.")
                    .font(.subheadline).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if funzioni.acceso(Funzione.diario) {
                Button { nav.vai(a: .pagina(.diario)) } label: {
                    Label("Apri il Diario", systemImage: "book").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .pulsanteVetro()
                .accessibilityHint("Mostra tutte le giornate giocate, con la formazione consigliata")
            }
        }
    }

    private func numeroFatti(_ fatti: Double) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            NumeroCheSale(valore: fatti)
                .font(.system(size: corpoGrande, weight: .bold, design: .rounded))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Text("punti fatti").font(.caption).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func attesi(_ r: RiepilogoGiornata, allineamento: HorizontalAlignment) -> some View {
        if let a = r.puntiAttesi {
            VStack(alignment: allineamento, spacing: 1) {
                Text(Formato.punti(a)).font(.title2.bold()).monospacedDigit()
                Text("punti attesi").font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func voce(_ r: RiepilogoGiornata, fatti: Double) -> String {
        var frasi = ["Punti fatti: \(Formato.punti(fatti))"]
        if let a = r.puntiAttesi { frasi.append("punti attesi: \(Formato.punti(a))") }
        return frasi.joined(separator: ", ")
    }
}

// MARK: - Anteprime

private enum EsempiFase {
    static let inCorso = GiornataInCorso(
        giornata: 11, giornataLega: 8, formazioneDi: "tua", puntiFatti: 39, puntiAttesiRestanti: 38.7, puntiPrevisti: 77.7,
        ancoraDaGiocare: 6,
        giocatori: [
            GiocatoreInCorso(id: 1, nome: "Ivo Sorvani", ruolo: "P", squadra: "inter", stato: "fatto", fantavoto: 5),
            GiocatoreInCorso(id: 2, nome: "Alvise Bastrani", ruolo: "D", squadra: "inter", aPunteggio: false, stato: "senza_voto"),
            GiocatoreInCorso(id: 3, nome: "Glauco Brevisi", ruolo: "D", squadra: "juventus", stato: "in_corso"),
            GiocatoreInCorso(id: 4, nome: "Aurelio Buonvicini", ruolo: "D", squadra: "napoli", stato: "da_giocare", data: "2026-11-08 18:00"),
            GiocatoreInCorso(id: 5, nome: "Marvin Thorvan", ruolo: "A", squadra: "inter", stato: "fatto", fantavoto: 10),
            GiocatoreInCorso(id: 6, nome: "Fabio Dimarzi", ruolo: "D", squadra: "inter", titolare: false, stato: "fatto", fantavoto: 6.5),
            GiocatoreInCorso(id: 7, nome: "Milo Magrenti", ruolo: "P", squadra: "milan", titolare: false, aPunteggio: false, stato: "in_corso"),
        ],
        sostituzioni: [
            CambioPanchina(esce: PersonaCambio(id: 2, nome: "Alvise Bastrani", ruolo: "D"), entra: PersonaCambio(id: 6, nome: "Fabio Dimarzi", ruolo: "D"),
                           certa: true, motivo: "senza_voto"),
        ],
        partite: ContoPartite(inCorso: 2, finite: 1, daGiocare: 7))

    static let riepilogo = RiepilogoGiornata(giornata: 11, giornataLega: 8, formazioneDi: "tua", nelDiario: true, puntiFatti: 74.5, puntiAttesi: 71.2,
                                             intervallo: IntervalloPunti(basso: 63.2, alto: 79.7, confidenza: 0.8),
                                             consigliata: PuntiConsigliata(puntiFatti: 78, puntiAttesi: 73.7))
}

#Preview("Giornata in corso") {
    ScrollView {
        VStack(spacing: 14) {
            CartaGiornataInCorso(blocco: EsempiFase.inCorso, attesiPrima: 73.7, partite: EsempiFase.inCorso.partite)
            CartaCambiPanchina(cambi: EsempiFase.inCorso.sostituzioni)
            CartaChiGioca(blocco: EsempiFase.inCorso)
        }
        .padding()
    }
    .background(Color.sfondoBase)
}

#Preview("Giornata finita") {
    CartaRiepilogoGiornata(riepilogo: EsempiFase.riepilogo)
        .padding()
        .background(Color.sfondoBase)
        .environmentObject(Navigazione())
}
