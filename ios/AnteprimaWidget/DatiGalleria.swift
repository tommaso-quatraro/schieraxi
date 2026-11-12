import SwiftUI
import WidgetKit

/// I dati finti della galleria (nessuna rete) e la tabella «widget -> misure -> vista». I dati sono quelli della lega della demo
/// dell'app (`LegaDemo`, la stessa fonte): nelle foto widget e app dicono le stesse cose (nomi, «gioca 62%», scadenza, Diario).
enum DatiGalleria {
    /// `-DATI`: pieni (prima della scadenza), parziali (un server senza scambio, svincolo e Diario), salvati (copia vecchia),
    /// in_corso, finita, vuoto (widget da collegare).
    static func voce(_ tipo: String) -> Voce {
        let adesso = Date()
        if tipo == "vuoto" {
            return Voce(date: adesso, riassunto: nil, datiSalvati: false, indirizzoMancante: true)
        }
        let fase: LegaDemo.Fase
        switch tipo {
        case "in_corso": fase = .inCorso
        case "finita": fase = .finita
        default: fase = .prima
        }
        // a giornata in corso la demo vive nel suo momento (alle 18:48, ora italiana: `LegaDemo.momento`, #417): i widget scrivono
        // «si è chiusa ieri 20:35» e gli orari delle partite da quell'ora, come Oggi dell'app, anche se la foto si scatta di notte
        let quando = LegaDemo.momento(adesso: adesso, fase: fase)
        let w = RiassuntoWidget.leggi(LegaDemo.widget(adesso: quando, fase: fase, parziali: tipo == "parziali"))
        return Voce(date: quando, riassunto: w?.comeRiassuntoOggi(scaricatoIl: quando), datiSalvati: tipo == "salvati", widget: w)
    }

    static func famiglie(_ widget: String) -> [WidgetFamily] {
        let blocco: [WidgetFamily] = [.accessoryCircular, .accessoryRectangular, .accessoryInline]
        switch widget {
        case "formazione": return [.systemSmall, .systemMedium, .systemLarge, .systemExtraLarge] + blocco
        case "dubbi": return [.systemMedium, .systemLarge, .accessoryRectangular]
        default: return [.systemSmall, .systemMedium] + blocco   // «oggi» (Prossima giornata)
        }
    }

    @ViewBuilder
    static func vista(_ widget: String, voce: Voce) -> some View {
        switch widget {
        case "formazione": VistaFormazione(voce: voce)
        case "dubbi": VistaDubbi(voce: voce)
        default: VistaWidget(voce: voce)   // «oggi» (Prossima giornata)
        }
    }
}
