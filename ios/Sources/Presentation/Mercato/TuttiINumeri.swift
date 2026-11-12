import SwiftUI

/// «Tutti i numeri» della scheda del giocatore, chiusi sotto le cose che servono per decidere, come `riempiScheda` di app.js
/// (#616): squadra o svincolato e quotazione, questa partita, prossime partite, forma, grafico dei voti, gol e assist rispetto
/// alle occasioni, stagione e statistiche avanzate. Parole dal catalogo comune, numeri del server.
struct TuttiINumeri: View {
    let scheda: SchedaGiocatore
    let prossime: [PartitaCalendario]

    @Environment(\.dynamicTypeSize) private var taglia

    private var previsione: Giocatore? { scheda.previsione }
    private var portiere: Bool { scheda.calciatore.ruolo == "P" }
    /// Le tessere: con il testo molto grande una per riga, perché tre affiancate tagliavano le etichette con «…» (foto del
    /// collaudo con il testo al massimo).
    private var griglia: [GridItem] {
        taglia.isAccessibilitySize ? [GridItem(.flexible())] : [GridItem(.adaptive(minimum: 96), spacing: 10)]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            PilloleEtichette(etichette: etichette)
            questaPartita
            prossimePartite
            forma
            grafico
            rendimento
            stagione
            avanzate
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Il proprietario (o «Svincolato», arancio) e la quotazione.
    private var etichette: [Etichetta] {
        [
            Etichetta(testo: scheda.proprietario ?? Catalogo.Mercato.svincolato, tono: scheda.proprietario == nil ? .attenzione : .neutro),
            Etichetta(testo: Catalogo.Mercato.quot(n: String(Formato.intero(scheda.calciatore.quotazione))), tono: .neutro),
        ]
    }

    private func titolo(_ testo: String) -> some View {
        Text(testo).font(.subheadline.bold()).accessibilityAddTraits(.isHeader)
    }

    /// Una riga piccola sotto i numeri; con il testo grande il «·» resta in fondo alla riga prima.
    private func nota(_ testo: String) -> some View {
        Text(TestoACapo.puntoInFondo(testo)).font(.caption).foregroundStyle(Color.testoSecondario)
            .fixedSize(horizontal: false, vertical: true)
    }

    // MARK: questa partita e prossime

    @ViewBuilder
    private var questaPartita: some View {
        if let p = previsione, LetturaScheda.conQuestaPartita(p) {
            VStack(alignment: .leading, spacing: 8) {
                titolo(Catalogo.Formazione.questaPartita)
                FilaAdattiva(spazio: 8) {
                    PillDifficolta(difficolta: p.difficolta)
                    Spacer(minLength: 0)
                    if let risultato = LetturaScheda.risultatoAtteso(p) {
                        Text(risultato).font(.caption).foregroundStyle(Color.testoSecondario)
                            .accessibilityLabel(LetturaScheda.voceRisultatoAtteso(p, squadra: scheda.calciatore.squadra) ?? risultato)
                    }
                }
                let motivi = LetturaScheda.motiviPartita(p)
                if !motivi.isEmpty {
                    PilloleEtichette(etichette: motivi.map { Etichetta(testo: $0.primaMaiuscola, tono: .neutro) })
                }
                if taglia.isAccessibilitySize {
                    LazyVGrid(columns: griglia, spacing: 12) { tesserePartita(p) }
                } else {
                    FilaTessere { tesserePartita(p) }
                }
            }
        }
    }

    /// Segna, assist, giallo e rosso; per un portiere porta inviolata, gol che può subire e giallo.
    @ViewBuilder
    private func tesserePartita(_ p: Giocatore) -> some View {
        if portiere {
            TesseraDato(valore: percento(p.portaInviolata), etichetta: Catalogo.Mercato.portaInviolata)
            TesseraDato(valore: Formato.decimali(p.golAvversario), etichetta: Catalogo.Mercato.golSubitiAttesi)
            TesseraDato(valore: percento(p.pGiallo), etichetta: Catalogo.Mercato.giallo)
        } else {
            TesseraDato(valore: percento(p.pGol), etichetta: Catalogo.Mercato.segna)
            TesseraDato(valore: percento(p.pAssist), etichetta: Catalogo.Mercato.assist)
            TesseraDato(valore: percento(p.pGiallo), etichetta: Catalogo.Mercato.giallo)
            TesseraDato(valore: percento(p.pRosso), etichetta: Catalogo.Mercato.rosso)
        }
    }

    private func percento(_ p: Double?) -> String {
        String(Formato.percento(p)) + "%"
    }

    @ViewBuilder
    private var prossimePartite: some View {
        if !prossime.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                titolo(Catalogo.Mercato.prossimePartite)
                ProssimePartite(partite: prossime)
                nota(Catalogo.Mercato.coloriVerdePartita)
            }
        }
    }

    // MARK: forma, grafico, rendimento

    @ViewBuilder
    private var forma: some View {
        if let f = Forma.calcola(scheda.voti ?? []) {
            VStack(alignment: .leading, spacing: 6) {
                titolo(Catalogo.Mercato.forma)
                HStack(alignment: .firstTextBaseline) {
                    Text(Catalogo.Mercato.andamento).font(.caption).foregroundStyle(Color.testoSecondario)
                    Spacer(minLength: 8)
                    Text(f.andamento.freccia + " " + Self.testoAndamento(f.andamento)).font(.subheadline.bold())
                        .foregroundStyle(f.andamento == .crescita ? Color.verde : f.andamento == .calo ? Color.malus : .primary)
                }
                .accessibilityElement(children: .combine)
            }
        }
    }

    /// Le parole dell'andamento dal catalogo (`mercato.in_crescita`, …), come la web.
    static func testoAndamento(_ a: Forma.Andamento) -> String {
        switch a {
        case .pochiDati: return Catalogo.Mercato.pochiDati
        case .crescita: return Catalogo.Mercato.inCrescita
        case .calo: return Catalogo.Mercato.inCalo
        case .stabile: return Catalogo.Mercato.stabile
        }
    }

    @ViewBuilder
    private var grafico: some View {
        if let voti = scheda.voti, !voti.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                titolo(Catalogo.Mercato.votoFantavotoPer)
                GraficoVoti(voti: voti)
            }
        }
    }

    @ViewBuilder
    private var rendimento: some View {
        if let r = scheda.rendimento, let sovra = r.sovraRendimento {
            VStack(alignment: .leading, spacing: 6) {
                titolo(Catalogo.Mercato.rendeSopraSotto)
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(Formato.conSegno(sovra, cifre: 2)).font(.title2.bold()).monospacedDigit()
                        .foregroundStyle(sovra > 0.3 ? Color.verde : sovra < -0.3 ? Color.malus : .primary)
                    Text(Catalogo.Mercato.puntiPartita).font(.caption).foregroundStyle(Color.testoSecondario)
                }
                .accessibilityElement(children: .combine)
                nota(Catalogo.Mercato.rendimentoRiga(a: Formato.conSegno(r.assistMenoXa ?? 0), g: Formato.conSegno(r.golMenoXg ?? 0))
                     + " " + (sovra > 0.3 ? Catalogo.Mercato.rendCala : sovra < -0.3 ? Catalogo.Mercato.rendSblocca : Catalogo.Mercato.rendLinea))
            }
        }
    }

    // MARK: stagione e statistiche avanzate

    @ViewBuilder
    private var stagione: some View {
        if let st = scheda.stagione {
            VStack(alignment: .leading, spacing: 8) {
                titolo(Catalogo.Mercato.stagione)
                LazyVGrid(columns: griglia, spacing: 12) {
                    TesseraDato(valore: "\(Formato.intero(st.presenze))/\(Formato.intero(st.giornateGiocateSerieA))", etichetta: Catalogo.Mercato.presenze)
                    TesseraDato(valore: Formato.decimali(st.mediaVoto, cifre: 2), etichetta: Catalogo.Mercato.mediaVoto)
                    TesseraDato(valore: Formato.decimali(st.fantamedia, cifre: 2), etichetta: Catalogo.Mercato.fantamedia)
                    TesseraDato(valore: String(Formato.intero(st.gol) + Formato.intero(st.rigSegnati)),
                                etichetta: Catalogo.Mercato.golRig(n: String(Formato.intero(st.rigSegnati))))
                    TesseraDato(valore: String(Formato.intero(st.assist)), etichetta: Catalogo.Mercato.assist)
                    TesseraDato(valore: "\(Formato.intero(st.ammonizioni))/\(Formato.intero(st.espulsioni))", etichetta: Catalogo.Mercato.gialliRossi)
                    if portiere {
                        TesseraDato(valore: String(Formato.intero(st.golSubiti)), etichetta: Catalogo.Mercato.golSubiti)
                        TesseraDato(valore: String(Formato.intero(st.rigParati)), etichetta: Catalogo.Mercato.rigoriParati)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var avanzate: some View {
        if let a = scheda.avanzate, (a.minuti ?? 0) > 0 {
            VStack(alignment: .leading, spacing: 8) {
                titolo(Catalogo.Mercato.statisticheAvanzate)
                LazyVGrid(columns: griglia, spacing: 12) {
                    TesseraDato(valore: Formato.decimali(a.xg, cifre: 2), etichetta: Catalogo.Mercato.golAttesiTot)
                    TesseraDato(valore: Formato.decimali(a.xa, cifre: 2), etichetta: Catalogo.Mercato.assistAttesiTot)
                    TesseraDato(valore: "\(Formato.intero(a.minuti))'", etichetta: Catalogo.Mercato.minuti)
                    TesseraDato(valore: Formato.decimali(a.per90?.xg, cifre: 2), etichetta: Catalogo.Mercato.xg90)
                    TesseraDato(valore: Formato.decimali(a.per90?.xa, cifre: 2), etichetta: Catalogo.Mercato.xa90)
                    TesseraDato(valore: Formato.decimali(a.per90?.tiri), etichetta: Catalogo.Mercato.tiri90)
                    TesseraDato(valore: String(Formato.intero(a.rigoriCalciati)), etichetta: Catalogo.Mercato.rigoriCalciati)
                    TesseraDato(valore: String(Formato.intero(a.passaggiChiave)), etichetta: Catalogo.Mercato.passaggiChiave)
                    TesseraDato(valore: String(Formato.intero(a.punizioni)), etichetta: Catalogo.Mercato.punizioni)
                }
                ForEach(a.stagioniPrecedenti ?? []) { p in
                    nota(Catalogo.Mercato.stagionePrec(a: String(Formato.intero(p.assist)), g: String(Formato.intero(p.gol)),
                                                       m: String(Formato.intero(p.minuti)), s: p.stagione,
                                                       xa: Formato.decimali(p.xa), xg: Formato.decimali(p.xg)))
                }
            }
        }
    }
}
