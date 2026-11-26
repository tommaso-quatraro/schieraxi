import SwiftUI
import WidgetKit

/// I dati finti della galleria (nessuna rete) e la tabella «widget -> misure -> vista». I dati sono quelli della lega della demo
/// dell'app (`LegaDemo`, la stessa fonte): nelle foto widget e app dicono le stesse cose (nomi, «gioca 62%», scadenza, Diario).
enum DatiGalleria {
    /// `-DATI`: pieni (prima della scadenza), parziali (un server senza scambio, svincolo e Diario), salvati (copia di due giorni
    /// prima), salvati_oggi (copia di oggi), in_corso, in_corso_recupero (più avanti nella giornata: la frase lunga del server su
    /// chi aspetta il recupero, #900), finita, campionato_finito (la frase del server al posto della giornata, #727), senza_formazione (entrato a
    /// giornata iniziata: la prossima da preparare, #687), vuoto (widget da collegare).
    static func voce(_ tipo: String) -> Voce {
        let adesso = Date()
        if tipo == "vuoto" {
            return Voce(date: adesso, riassunto: nil, datiSalvati: false, indirizzoMancante: true)
        }
        if tipo == "campionato_finito" {
            let w = RiassuntoWidget.leggi(LegaDemo.widgetCampionatoFinito(adesso: adesso))
            return Voce(date: adesso, riassunto: w?.comeRiassuntoOggi(scaricatoIl: adesso), datiSalvati: false, widget: w)
        }
        if tipo == "senza_formazione" {
            let quando = LegaDemo.momento(adesso: adesso, fase: .inCorso)
            let w = RiassuntoWidget.leggi(senzaFormazione(LegaDemo.widget(adesso: quando, fase: .inCorso), adesso: quando))
            return Voce(date: quando, riassunto: w?.comeRiassuntoOggi(scaricatoIl: quando), datiSalvati: false, widget: w)
        }
        if tipo == "in_corso_recupero" {
            let quando = LegaDemo.momento(adesso: adesso, fase: .inCorso)
            let w = RiassuntoWidget.leggi(conRecupero(LegaDemo.widget(adesso: quando, fase: .inCorso)))
            return Voce(date: quando, riassunto: w?.comeRiassuntoOggi(scaricatoIl: quando), datiSalvati: false, widget: w)
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
        // la copia salvata (#834): «salvati» è di due giorni prima, la riga più lunga, con il giorno (per esempio «dati di mer 18
        // 09:41»); «salvati_oggi» è di adesso, «dati delle 09:41»
        let scaricatoIl = tipo == "salvati" ? quando.addingTimeInterval(-2 * 86_400) : quando
        let salvati = tipo == "salvati" || tipo == "salvati_oggi"
        return Voce(date: quando, riassunto: w?.comeRiassuntoOggi(scaricatoIl: scaricatoIl), datiSalvati: salvati, widget: w)
    }

    /// La giornata in corso della demo più avanti (#900): hanno giocato tutti tranne tre titolari della partita rinviata e mancano i
    /// voti, quindi nessuno deve più giocare e la riga sotto i punti è la frase lunga del server (`LegaDemo.situazioneRecupero`).
    private static func conRecupero(_ dati: Data) -> Data {
        guard var w = (try? JSONSerialization.jsonObject(with: dati)) as? [String: Any],
              var inCorso = w["in_corso"] as? [String: Any] else { return dati }
        inCorso["ancora_da_giocare"] = 0
        inCorso["situazione"] = LegaDemo.situazioneRecupero
        w["in_corso"] = inCorso
        return (try? JSONSerialization.data(withJSONObject: w)) ?? dati
    }

    /// La giornata in corso della demo come la vede chi è entrato dopo la scadenza senza una formazione (`fanta/fasi.py`, #651):
    /// senza `in_corso` (niente punti di una formazione che non ha schierato), con `senza_formazione` e la `prossima` da preparare.
    private static func senzaFormazione(_ dati: Data, adesso: Date) -> Data {
        guard var w = (try? JSONSerialization.jsonObject(with: dati)) as? [String: Any] else { return dati }
        w["in_corso"] = nil
        w["senza_formazione"] = true
        w["prossima"] = LegaDemo.prossimaDopoFinita(adesso: adesso)
        return (try? JSONSerialization.data(withJSONObject: w)) ?? dati
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
