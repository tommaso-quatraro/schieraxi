import WidgetKit
import SwiftUI

/// Widget «Partite live»: punteggio e minuto delle partite in corso, con i tuoi titolari evidenziati (volto e cognome).
/// Senza partite in gioco mostra le prossime col loro orario. Dati dal campo `live` di /api/widget (copia piccola di /api/live).
/// Misure: medio, grande, rettangolo e riga della schermata di blocco. Si aggiorna ogni 2 minuti nelle finestre di gioco (iOS puo' rimandare).
struct WidgetLive: Widget {
    let kind = "SchieraxiLive"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: ConfigurazioneWidget.self, provider: Fornitore()) { voce in
            VistaLive(voce: voce)
        }
        .configurationDisplayName("Partite live")
        .description("Punteggio e minuto delle partite in corso, con i tuoi titolari in evidenza.")
        .supportedFamilies([.systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline])
    }
}

/// Una partita su una riga: squadre, punteggio, minuto; sotto (se ci sono) i tuoi titolari.
struct RigaPartitaLive: View {
    let p: PartitaLive
    let miei: [GiocatoreWidget]
    var conEventi = false
    var lato: CGFloat = 20
    /// Tutto su una riga (avatar dopo la sigla) per il Cruscotto, dove lo spazio e' poco.
    var compatto = false
    @Environment(\.widgetRenderingMode) private var modoSistema
    @Environment(\.renderForzato) private var modoForzato
    private var modo: WidgetRenderingMode { modoForzato ?? modoSistema }

    var body: some View {
        Link(destination: Vai.url("oggi")) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(ColoriSquadra.sigla(p.casa)).font(.footnote.weight(.semibold)).frame(width: 34, alignment: .trailing)
                    Text(p.punteggio).font(.system(.body, design: .rounded).weight(.bold)).monospacedDigit()
                        .foregroundStyle(p.inGioco ? TintaWidget.accento(modo) : .white).widgetAccentable(p.inGioco)
                    Text(ColoriSquadra.sigla(p.trasferta)).font(.footnote.weight(.semibold)).frame(width: 34, alignment: .leading)
                    if compatto {
                        HStack(spacing: -4) { ForEach(miei.prefix(3)) { g in AvatarMini(g: g, lato: lato) } }.padding(.leading, 4)
                    }
                    Spacer(minLength: 4)
                    Text(p.etichetta).font(.caption.weight(p.inGioco ? .bold : .regular)).monospacedDigit()
                        .foregroundStyle(p.inGioco ? TintaWidget.accento(modo) : TintaWidget.testo2).lineLimit(1)
                }
                if !miei.isEmpty && !compatto {
                    HStack(spacing: 4) {
                        ForEach(miei.prefix(4)) { g in AvatarMini(g: g, lato: lato) }
                        Text(miei.prefix(3).map(\.cognome).joined(separator: ", ") + (miei.count > 3 ? " +\(miei.count - 3)" : ""))
                            .font(.caption2).foregroundStyle(TintaWidget.testo2).lineLimit(1)
                    }
                }
                if conEventi {
                    ColonneEventi(eventi: EventiPartita.visibili(p.eventi), nomeCasa: ColoriSquadra.sigla(p.casa), nomeTrasferta: ColoriSquadra.sigla(p.trasferta),
                                  font: .caption2, colore: TintaWidget.testo2, coloreRosso: TintaWidget.malus, coloreAutogol: TintaWidget.attenzione, righeMax: 1)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(p.frase + (miei.isEmpty ? "" : ". Tuoi titolari: " + miei.map(\.cognome).joined(separator: ", ")))
    }
}

struct VistaLive: View {
    @Environment(\.widgetFamily) private var famigliaSistema
    @Environment(\.famigliaForzata) private var famigliaForzata
    private var famiglia: WidgetFamily { famigliaForzata ?? famigliaSistema }
    let voce: Voce

    private var accessorio: Bool { famiglia == .accessoryRectangular || famiglia == .accessoryInline }

    var body: some View {
        Group {
            if let w = voce.completo {
                if w.partiteLive.isEmpty { senzaPartite(w) } else { contenuto(w) }
            } else {
                SenzaDatiWidget(voce: voce, compatto: accessorio)
            }
        }
        .sfondoWidget(accessorio: accessorio)
        .widgetURL(voce.tocco(Vai.url("oggi")))
    }

    /// Quelle da mostrare: se qualcuna e' in gioco quelle, altrimenti le prossime (e per ultime le finite).
    private func scelte(_ w: RiassuntoWidget, massimo: Int) -> [PartitaLive] {
        let inGioco = w.partiteInGioco
        if !inGioco.isEmpty {
            // in grande, dopo quelle in gioco anche le prossime
            return Array((inGioco + (famiglia == .systemLarge ? w.partiteLive.filter { !$0.inGioco && !$0.finita } : [])).prefix(massimo))
        }
        let prossime = w.partiteLive.filter { !$0.finita }
        return Array((prossime.isEmpty ? w.partiteLive : prossime).prefix(massimo))
    }

    private func titolo(_ w: RiassuntoWidget) -> String {
        let n = w.partiteInGioco.count
        return n > 0 ? (n == 1 ? "1 partita in corso" : "\(n) partite in corso") : "Partite del turno"
    }

    private func senzaPartite(_ w: RiassuntoWidget) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            if famiglia == .accessoryInline {
                Label("Nessuna partita live", systemImage: "soccerball")
            } else {
                TitoloBlocco(testo: "Partite live", icona: "soccerball")
                Text("Nessuna partita in corso").font(.headline)
                Text("Compaiono qui quando il server le vede in gioco.").font(.caption).foregroundStyle(accessorio ? Color.secondary : TintaWidget.testo2)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func contenuto(_ w: RiassuntoWidget) -> some View {
        switch famiglia {
        case .systemLarge: elenco(w, massimo: 5, eventi: true)
        case .accessoryRectangular:
            if let p = scelte(w, massimo: 1).first {
                let miei = w.mieiTitolari(in: p)
                VStack(alignment: .leading, spacing: 1) {
                    Text("\(ColoriSquadra.sigla(p.casa)) \(p.punteggio) \(ColoriSquadra.sigla(p.trasferta)) \(p.etichetta)").font(.headline).lineLimit(1).minimumScaleFactor(0.7)
                    Text(miei.isEmpty ? titolo(w) : "Tuoi: " + miei.prefix(3).map(\.cognome).joined(separator: ", ")).font(.caption).lineLimit(1)
                    if let e = EventiPartita.visibili(p.eventi).last {
                        Text(e.testoCompatto).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        case .accessoryInline:
            if let p = scelte(w, massimo: 1).first {
                Label("\(ColoriSquadra.sigla(p.casa)) \(p.punteggio) \(ColoriSquadra.sigla(p.trasferta)) \(p.etichetta)", systemImage: "soccerball")
            }
        default: elenco(w, massimo: 3, eventi: false)
        }
    }

    /// Con gli eventi in colonna ogni partita occupa piu' righe: se non entrano tutte se ne mostrano meno (almeno una), mai eventi tagliati.
    private func entranti(_ w: RiassuntoWidget, massimo: Int, conEventi: Bool) -> [PartitaLive] {
        let tutte = scelte(w, massimo: massimo)
        guard conEventi else { return tutte }
        var usate = 0, scelta: [PartitaLive] = []
        for p in tutte {
            let costo = 2 + (w.mieiTitolari(in: p).isEmpty ? 0 : 1) + EventiPartita.righe(p.eventi)
            if !scelta.isEmpty && usate + costo > 19 { break }
            usate += costo; scelta.append(p)
        }
        return scelta
    }

    private func elenco(_ w: RiassuntoWidget, massimo: Int, eventi: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            IntestazioneWidget(titolo: titolo(w), icona: "soccerball", destra: Quando.data(w.live?.aggiornatoIl).map { "agg. \(Quando.ora($0))" })
            ForEach(entranti(w, massimo: massimo, conEventi: eventi)) { p in
                RigaPartitaLive(p: p, miei: w.mieiTitolari(in: p), conEventi: eventi, lato: eventi ? 24 : 18)
            }
            Spacer(minLength: 0)
            PiedeDati(voce: voce)
        }
    }
}
