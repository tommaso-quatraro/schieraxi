import SwiftUI
import WidgetKit

/// I dati finti della galleria (nessuna rete) e la tabella «widget -> misure -> vista». I dati sono quelli della lega della demo
/// dell'app (`LegaDemo`, la stessa fonte): nelle foto widget e app dicono le stesse cose (nomi, «gioca 62%», scadenza, Diario).
enum DatiGalleria {
    /// `-DATI`: pieni (prima della scadenza), parziali (un server senza scambio, svincolo e Diario), salvati (copia vecchia),
    /// in_corso, finita, vuoto (widget da collegare). Il widget Live con i dati pieni si fotografa a giornata in corso: prima della
    /// scadenza nessuna partita può essere in gioco, e il widget delle partite in diretta sarebbe solo un elenco di orari.
    static func voce(_ tipo: String, widget: String) -> Voce {
        let adesso = Date()
        if tipo == "vuoto" {
            return Voce(date: adesso, riassunto: nil, datiSalvati: false, indirizzoMancante: true)
        }
        let fase: LegaDemo.Fase
        switch tipo {
        case "in_corso": fase = .inCorso
        case "finita": fase = .finita
        case "pieni" where widget == "live": fase = .inCorso
        default: fase = .prima
        }
        let w = RiassuntoWidget.leggi(LegaDemo.widget(adesso: adesso, fase: fase, parziali: tipo == "parziali"))
        return Voce(date: adesso, riassunto: w?.comeRiassuntoOggi(scaricatoIl: adesso), datiSalvati: tipo == "salvati", widget: w)
    }

    static func famiglie(_ widget: String) -> [WidgetFamily] {
        let blocco: [WidgetFamily] = [.accessoryCircular, .accessoryRectangular, .accessoryInline]
        switch widget {
        case "oggi": return [.systemSmall, .systemMedium] + blocco
        case "formazione": return [.systemSmall, .systemMedium, .systemLarge, .systemExtraLarge] + blocco
        case "cruscotto": return [.systemLarge, .systemExtraLarge] + blocco
        case "dubbi": return [.systemMedium, .systemLarge, .accessoryRectangular]
        case "rosa": return [.systemMedium, .systemLarge, .systemExtraLarge, .accessoryRectangular, .accessoryInline]
        case "punti": return [.systemSmall, .systemMedium, .systemLarge] + blocco
        case "live": return [.systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline]
        case "osservato": return [.systemSmall, .systemMedium] + blocco
        case "scambio": return [.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline]
        case "crediti": return [.systemSmall, .systemMedium] + blocco
        case "stato": return [.systemSmall] + blocco
        default: return [.systemLarge]
        }
    }

    @ViewBuilder
    static func vista(_ widget: String, voce: Voce) -> some View {
        switch widget {
        case "oggi": VistaWidget(voce: voce)
        case "formazione": VistaFormazione(voce: voce)
        case "dubbi": VistaDubbi(voce: voce)
        case "rosa": VistaRosa(voce: voce)
        case "punti": VistaPunti(voce: voce)
        case "scambio": VistaScambio(voce: voce)
        // Marténi, in dubbio come in Oggi: «In dubbio · gioca 62%» con le parole dell'app
        case "osservato": VistaOsservato(voce: voce, scelto: 120)
        case "live": VistaLive(voce: voce)
        case "crediti": VistaCrediti(voce: voce)
        case "stato": VistaStato(voce: voce)
        default: VistaCruscotto(voce: voce)
        }
    }
}
