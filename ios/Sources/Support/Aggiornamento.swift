import Foundation
import BackgroundTasks
import WidgetKit

/// Aggiornamento in background: ogni tanto iOS sveglia l'app (BGAppRefreshTask), che riscarica la giornata,
/// riprogramma i promemoria e, se la formazione consigliata è cambiata, manda una notifica locale.
/// iOS decide quando svegliarla (di solito poche volte al giorno, di più se usi spesso l'app): non c'è un orario garantito.
enum Aggiornamento {
    static let identificativo = "<vecchio identificativo>.aggiorna"

    /// Chiede a iOS di svegliare l'app fra non meno di due ore.
    static func programma() {
        let richiesta = BGAppRefreshTaskRequest(identifier: identificativo)
        richiesta.earliestBeginDate = Date(timeIntervalSinceNow: 2 * 3600)
        try? BGTaskScheduler.shared.submit(richiesta)
    }

    /// Riprogramma i promemoria sulla scadenza del certificato (se il profilo si legge).
    static func riprogrammaScadenza() async {
        if let scadenza = Certificato.scadenza() { await Notifiche.programmaScadenza(scadenza) }
    }

    /// Il lavoro vero: scarica /api/oggi, lo salva nella cache e confronta con l'ultima volta.
    static func esegui() async {
        programma()   // prima di tutto: riprogramma il prossimo risveglio
        await riprogrammaScadenza()
        guard let oggi = try? await OggiRepository(server: ServerCorrente.condiviso).aggiornato() else { return }
        await elabora(oggi, avvisaSeCambia: true)
    }

    /// Promemoria, widget e (se richiesto) notifica quando la formazione consigliata cambia nella stessa giornata.
    static func elabora(_ oggi: Oggi, avvisaSeCambia: Bool) async {
        if let inizio = Quando.data(oggi.inizio) {
            await Notifiche.programma(giornata: oggi.giornata, inizio: inizio, modulo: oggi.formazione?.modulo)
        }
        WidgetCenter.shared.reloadAllTimelines()
        // Senza una formazione vera (modulo mancante o «–», punti assenti) non si confronta né si ricorda niente.
        guard let f = oggi.formazione, f.disponibile, let modulo = f.modulo else { return }
        let memoria = UserDefaults.standard
        let probabili = oggi.conProbabili ?? false
        let giornataPrima = memoria.object(forKey: "bg.giornata") as? Int
        let moduloPrima = memoria.string(forKey: "bg.modulo")
        let probabiliPrima = memoria.object(forKey: "bg.probabili") as? Bool

        if avvisaSeCambia, giornataPrima == oggi.giornata {
            let punti = Formato.punti(f.punteggioAtteso)
            if let moduloPrima, moduloPrima != modulo {
                await Notifiche.avviso(id: "fanta-cambio", titolo: "La formazione consigliata è cambiata",
                                       corpo: "Giornata \(oggi.giornata): ora \(modulo), \(punti) punti attesi (prima \(moduloPrima)).")
            } else if probabiliPrima == false, probabili {
                await Notifiche.avviso(id: "fanta-probabili", titolo: "Sono uscite le probabili formazioni",
                                       corpo: "Giornata \(oggi.giornata): modulo consigliato \(modulo), \(punti) punti attesi.")
            }
        }
        memoria.set(oggi.giornata, forKey: "bg.giornata")
        memoria.set(modulo, forKey: "bg.modulo")
        memoria.set(probabili, forKey: "bg.probabili")
    }

    /// La giornata di oggi per Siri e Comandi: dal server, o dalla cache se non risponde.
    static func leggiOggi() async -> (oggi: Oggi, salvato: Bool)? {
        await OggiRepository(server: ServerCorrente.condiviso).ultimo()
    }
}
