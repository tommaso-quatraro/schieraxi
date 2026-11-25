import Foundation

/// Una riga delle Impostazioni che apre una pagina: il nome, sotto una riga piccola, e la pagina. L'`id` è il gruppo della stessa
/// riga sulla web (`rigaImp` di `fanta/web/impostazioni.js`: rose, squadra, regole, squadre, account, informazioni, gestione).
struct VoceImpostazioni: Identifiable, Equatable {
    let id: String
    let nome: String
    let sotto: String?
    let pagina: PaginaImpostazioni
}

/// Quali righe mostra la pagina Impostazioni, come `paginaImpostazioni` della web (#673 passo 3, web #675). Logica pura: la provano
/// `ImpostazioniComeLaWebTests`.
enum VociImpostazioni {
    /// La mia lega: Aggiorna le rose; La mia squadra (solo con le rose: sotto il suo nome o «Non l'hai ancora scelta»); Regole e
    /// scadenza; Le altre squadre (solo con più squadre e la funzione `squadre_altrui` accesa), con il numero delle squadre senza la
    /// mia, quello dell'elenco che apre (`altreSquadre`).
    static func lega(squadre: [SquadraLega], squadreAltrui: Bool) -> [VoceImpostazioni] {
        var voci = [VoceImpostazioni(id: "rose", nome: Catalogo.Lega.voceImporta, sotto: Catalogo.Lega.voceImportaSub, pagina: .importa)]
        if !squadre.isEmpty {
            let mia = squadre.first { $0.mia == true }?.nome
            // senza una squadra scelta si apre la sua scelta, come la web (`vistaRosa("")`, #863)
            voci.append(VoceImpostazioni(id: "squadra", nome: Catalogo.Lega.miaSquadra, sotto: mia ?? Catalogo.Imp.miaSquadraNessuna,
                                         pagina: mia.map { .rosa($0) } ?? .sceltaSquadra))
        }
        voci.append(VoceImpostazioni(id: "regole", nome: Catalogo.Imp.regole, sotto: Catalogo.Imp.regoleSub, pagina: .regole))
        if squadre.count > 1, squadreAltrui {
            voci.append(VoceImpostazioni(id: "squadre", nome: Catalogo.Imp.altreSquadre,
                                         sotto: Catalogo.Lega.nSquadre(altreSquadre(squadre).count), pagina: .squadre))
        }
        return voci
    }

    /// Le squadre di «Le altre squadre», come `vistaAltreSquadre` della web (#779, #788): tutte tranne la mia. Finché la mia non è
    /// scelta sono tutte (la propria si sceglie in «La mia squadra», #863).
    static func altreSquadre(_ squadre: [SquadraLega]) -> [SquadraLega] {
        squadre.filter { $0.mia != true }
    }

    /// «Il tuo account», solo con un account: sotto il nome con cui si mostra.
    static func account(nome: String?) -> VoceImpostazioni? {
        nome.map { VoceImpostazioni(id: "account", nome: Catalogo.Imp.account, sotto: $0, pagina: .account) }
    }

    /// Sotto «Gestione» solo quello che c'è sull'iPhone (aggiornare i dati e il loro stato): inviti e utenti sono della web.
    static let sottoGestione = "\(Catalogo.Shell.aggiorna) · \(Catalogo.Av.stato)"

    /// Informazioni per tutti; Gestione solo per chi gestisce il server (invisibile a un utente normale).
    static func informazioni(gestisce: Bool) -> [VoceImpostazioni] {
        var voci = [VoceImpostazioni(id: "informazioni", nome: Catalogo.Imp.informazioni, sotto: Catalogo.Imp.informazioniSub,
                                     pagina: .informazioni)]
        if gestisce {
            voci.append(VoceImpostazioni(id: "gestione", nome: Catalogo.Imp.gestione, sotto: sottoGestione, pagina: .gestione))
        }
        return voci
    }
}
