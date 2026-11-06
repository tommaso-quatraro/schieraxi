import SwiftUI

// Le carte di Oggi durante e dopo la giornata (campo `fase` del server), come la web (`cardInCorso`, `cardSenzaFormazione` e
// `cardRiepilogo` di `fanta/web/app.js`, #436). Testi in `TestiFase` (Domain/FasiGiornata.swift).
// Durante la giornata non si mostrano consigli su chi schierare: solo punti, chi va a punteggio e cambi dalla panchina.

/// Fase `in_corso`: una carta sola, senza titolo, come la web. Le cifre (punti fatti finora | a fine giornata, con gli attesi di
/// prima), quanti devono ancora giocare, chi va a punteggio (con «entrato dalla panchina» e la data di chi deve ancora giocare) e
/// i cambi dalla panchina con «già fatto» o «probabile».
struct CartaGiornataInCorso: View {
    let blocco: GiornataInCorso
    /// I punti attesi della formazione prima della giornata (`formazione.punteggio_atteso`).
    let attesiPrima: Double?
    @Environment(\.apriGiocatore) private var apri
    @ScaledMetric(relativeTo: .largeTitle) private var corpoGrande: CGFloat = 46

    /// Solo chi va a punteggio, come la web (titolari e chi entra dalla panchina, nell'ordine del server).
    private var aPunteggio: [GiocatoreInCorso] { blocco.giocatori.filter(\.aPunteggio) }
    /// La web salta i cambi senza chi esce.
    private var cambi: [CambioPanchina] { blocco.sostituzioni.filter { $0.esce != nil } }

    var body: some View {
        Carta {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 12) {
                    fatti
                    Spacer(minLength: 0)
                    previsti(allineamento: .trailing)
                }
                VStack(alignment: .leading, spacing: 8) {
                    fatti
                    previsti(allineamento: .leading)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(voce)
            if let a = TestiFase.ancora(blocco.ancoraDaGiocare) {
                Text(a).font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            ForEach(Array(aPunteggio.enumerated()), id: \.element.id) { i, g in
                RigaConFilo(prima: i == 0) {
                    // sotto il nome, come la web: «entrato dalla panchina» per chi non era titolare
                    RigaGiocatoreInCorso(g: g, nota: g.titolare ? nil : TestiFase.dallaPanchina, apri: apri)
                }
            }
            if !cambi.isEmpty {
                Text(TestiFase.cambiPanchina).titoletto().padding(.top, 6)
                ForEach(Array(cambi.enumerated()), id: \.offset) { i, c in
                    RigaConFilo(prima: i == 0) { RigaCambioPanchina(cambio: c) }
                }
            }
        }
    }

    private var fatti: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(TestiFase.puntiFinora).font(.caption).foregroundStyle(Color.testoSecondario)
            // Scritto subito giusto, come la web (#416): un numero che sale da 0 resta a metà in una foto o con l'app lenta.
            // Quando arrivano voti nuovi le cifre scorrono (`numerico`).
            Text(Formato.punti(blocco.puntiFatti))
                .monospacedDigit()
                .numerico(blocco.puntiFatti ?? 0)
                .font(.system(size: corpoGrande, weight: .bold, design: .rounded))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
    }

    private func previsti(allineamento: HorizontalAlignment) -> some View {
        VStack(alignment: allineamento, spacing: 1) {
            Text(TestiFase.aFineGiornata).font(.caption).foregroundStyle(Color.testoSecondario)
            Text(TestiFase.previsti(blocco.puntiPrevisti)).font(.title2.bold()).monospacedDigit()
            if let prima = attesiPrima {
                Text(TestiFase.attesiPrima(prima)).font(.caption2).foregroundStyle(Color.testoSecondario)
            }
        }
        .multilineTextAlignment(allineamento == .trailing ? .trailing : .leading)
    }

    private var voce: String {
        var frasi = ["\(TestiFase.puntiFinora): \(Formato.punti(blocco.puntiFatti))",
                     "\(TestiFase.aFineGiornata), circa \(Formato.punti(blocco.puntiPrevisti))"]
        if let prima = attesiPrima { frasi.append(TestiFase.attesiPrima(prima).primaMaiuscola) }
        return frasi.joined(separator: ". ")
    }
}

/// Una riga di chi va a punteggio: ruolo, nome, sigla della squadra («GEN», come la web) e, per chi è entrato dalla panchina,
/// «entrato dalla panchina»; a destra il fantavoto, la data della partita o lo stato.
struct RigaGiocatoreInCorso: View {
    let g: GiocatoreInCorso
    /// La riga sotto il nome e la squadra (per chi è entrato dalla panchina, «entrato dalla panchina»); nil = niente.
    let nota: String?
    let apri: (Int) -> Void

    /// La sigla sulla riga («GEN»); a voce il nome per esteso, più chiaro di tre lettere.
    private var squadra: String? {
        guard let s = g.squadra, !s.isEmpty else { return nil }
        return ColoriSquadra.sigla(s)
    }

    private var squadraPerEsteso: String? {
        guard let s = g.squadra, !s.isEmpty else { return nil }
        return s.replacingOccurrences(of: "_", with: " ").replacingOccurrences(of: "-", with: " ").capitalized
    }

    var body: some View {
        Button { apri(g.id) } label: {
            HStack(alignment: .center, spacing: 10) {
                BadgeRuolo(ruolo: g.ruolo ?? "?")
                // nome e riga sotto vanno a capo interi, anche con il testo grande: mai «…» (#254, `NomiInteriTests`)
                VStack(alignment: .leading, spacing: 2) {
                    Text(g.nome).font(.headline)
                        .fixedSize(horizontal: false, vertical: true)
                    if let squadra {
                        Text(squadra).font(.caption).foregroundStyle(Color.testoSecondario)
                    }
                    if let nota {
                        Text(nota).font(.caption).foregroundStyle(Color.testoSecondario)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Spacer(minLength: 6)
                valore
            }
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
                .foregroundStyle(.primary)          // voto vero neutro, come la web app (niente verde o rosso)
        case "in_corso":
            Capsula(testo: TestiFase.valore(g), colore: .informazione)
        case "senza_voto":
            Capsula(testo: TestiFase.valore(g), colore: .malus)
        case "rinviata":
            Capsula(testo: TestiFase.valore(g), colore: .attenzione)
        case "attesa_voti":
            Capsula(testo: TestiFase.valore(g), colore: .secondary)
        default:
            // chi deve ancora giocare: la data della partita («sab 8 18:00»), come la web
            Text(TestiFase.valore(g)).font(.subheadline).monospacedDigit().foregroundStyle(Color.testoSecondario)
                .multilineTextAlignment(.trailing)
        }
    }

    private var voce: String {
        var parti = [g.nome, nomeRuolo(g.ruolo ?? "")]
        if let squadraPerEsteso { parti.append(squadraPerEsteso) }
        var frase = parti.joined(separator: ", ") + ": " + TestiFase.valoreVoce(g)
        if let nota { frase += ". " + nota }
        return frase
    }
}

/// Fase `finita`: la giornata appena chiusa e la prossima, in una carta sola come `cardRiepilogo` della web. Titolo «Giornata 7 ·
/// 10ª di Serie A: finita», cifre (la tua formazione o la consigliata | punti attesi), confronto con la consigliata, recuperi e menu
/// del rinvio, nota del Diario, «Apri il Diario», poi «Giornata 8 · 11ª di Serie A: la formazione si chiude …».
struct CartaRiepilogoGiornata: View {
    let riepilogo: RiepilogoGiornata?
    let prossima: ProssimaGiornata?
    /// Partite rinviate ancora da recuperare: il menu «per questa giornata» (nil = niente menu, per esempio nelle anteprime).
    var rinvioInCorso = false
    var cambiaRinvio: (@MainActor (SceltaRinvio, String) async -> Void)? = nil
    @Environment(\.funzioni) private var funzioni
    @EnvironmentObject private var nav: Navigazione
    @ScaledMetric(relativeTo: .largeTitle) private var corpoGrande: CGFloat = 46

    private var rigaProssima: String? { prossima.flatMap { TestiFase.prossima($0) } }

    var body: some View {
        // come la web: senza riepilogo né prossima giornata la carta non c'è
        if riepilogo != nil || rigaProssima != nil {
            Carta {
                if let r = riepilogo { giornata(r) }
                if let riga = rigaProssima {
                    Text(riga).font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, riepilogo == nil ? 0 : 4)
                }
            }
        }
    }

    @ViewBuilder
    private func giornata(_ r: RiepilogoGiornata) -> some View {
        if let titolo = TestiFase.giornataFinita(serieA: r.giornata, lega: r.giornataLega) {
            Text(titolo).font(.headline)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityLabel(TestiFase.giornataFinita(serieA: r.giornata, lega: r.giornataLega, voce: true) ?? titolo)
                .accessibilityAddTraits(.isHeader)
        }
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 12) {
                fatti(r)
                Spacer(minLength: 0)
                attesi(r, allineamento: .trailing)
            }
            VStack(alignment: .leading, spacing: 8) {
                fatti(r)
                attesi(r, allineamento: .leading)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(voce(r))
        if let c = TestiFase.confronto(r) {
            Text(c).font(.subheadline).fixedSize(horizontal: false, vertical: true)
        }
        if let m = TestiRinvio.recuperoManca(r.recuperi) {
            Label(m, systemImage: "calendar.badge.clock")
                .font(.subheadline).foregroundStyle(Color.attenzione)
                .fixedSize(horizontal: false, vertical: true)
        }
        if let s = r.rinvio, let cambia = cambiaRinvio {
            MenuRinvio(scelta: s, inCorso: rinvioInCorso, cambia: cambia)
        }
        if let n = TestiFase.notaDiario(r) {
            Text(n).font(.footnote).foregroundStyle(Color.testoSecondario).fixedSize(horizontal: false, vertical: true)
        }
        if funzioni.acceso(Funzione.diario) {
            Button { nav.vai(a: .pagina(.diario)) } label: {
                Label(TestiFase.apriDiario, systemImage: "book").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro()
            .accessibilityHint("Mostra tutte le giornate giocate, con la formazione consigliata")
        }
    }

    private func fatti(_ r: RiepilogoGiornata) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(TestiFase.formazioneDi(r)).font(.caption).foregroundStyle(Color.testoSecondario)
            Text(Formato.punti(r.puntiFatti))   // subito giusto, come la web (#416)
                .monospacedDigit()
                .font(.system(size: corpoGrande, weight: .bold, design: .rounded))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Text(TestiFase.puntiFatti).font(.caption2).foregroundStyle(Color.testoSecondario)
        }
    }

    @ViewBuilder
    private func attesi(_ r: RiepilogoGiornata, allineamento: HorizontalAlignment) -> some View {
        if let a = r.puntiAttesi {
            VStack(alignment: allineamento, spacing: 1) {
                Text(TestiFase.puntiAttesi).font(.caption).foregroundStyle(Color.testoSecondario)
                Text(Formato.punti(a)).font(.title2.bold()).monospacedDigit()
            }
        }
    }

    private func voce(_ r: RiepilogoGiornata) -> String {
        var frasi = ["\(TestiFase.formazioneDi(r)): \(Formato.punti(r.puntiFatti)) \(TestiFase.puntiFatti)"]
        if let a = r.puntiAttesi { frasi.append("\(Formato.punti(a)) \(TestiFase.puntiAttesi)") }
        return frasi.joined(separator: ", ")
    }
}

// MARK: - Anteprime

private enum EsempiFase {
    static let inCorso = GiornataInCorso(
        giornata: 11, giornataLega: 8, formazioneDi: "tua", puntiFatti: 39, puntiAttesiRestanti: 38.7, puntiPrevisti: 77.7,
        ancoraDaGiocare: 2,
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

    static let prossima = ProssimaGiornata(giornata: 12, giornataLega: 9, scadenza: "2026-11-14 14:30", preparaDa: "2026-11-11 14:30")
}

#Preview("Giornata in corso") {
    ScrollView {
        CartaGiornataInCorso(blocco: EsempiFase.inCorso, attesiPrima: 73.7)
            .padding()
    }
    .background(Color.sfondoBase)
}

#Preview("Giornata finita") {
    CartaRiepilogoGiornata(riepilogo: EsempiFase.riepilogo, prossima: EsempiFase.prossima)
        .padding()
        .background(Color.sfondoBase)
        .environmentObject(Navigazione())
}
