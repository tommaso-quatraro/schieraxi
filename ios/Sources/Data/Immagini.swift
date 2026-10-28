import SwiftUI
import UIKit

/// Foto dei giocatori e stemmi/maglie delle squadre della lega: si scaricano dal server una volta sola e restano in memoria
/// (NSCache) e su disco (cartella Caches/img). Le viste leggono sempre dalla memoria, senza attese (`memoriaFoto`), e chiedono
/// il caricamento con `caricaFoto`: appena arriva, `versione` cambia e le viste si ridisegnano.
@MainActor
final class Immagini: ObservableObject {
    static let condivise = Immagini()

    /// Chi ha la foto sul server (`/api/foto-disponibili`): per gli altri non si chiede niente, e si vede la maglia della squadra.
    @Published private(set) var fotoDisponibili: Set<Int> = []
    /// Stemma e maglia caricati per ogni squadra della lega.
    @Published private(set) var squadre: [String: ImmaginiSquadra] = [:]
    /// Aumenta a ogni immagine nuova arrivata: serve a ridisegnare le viste.
    @Published private(set) var versione = 0

    /// Il server da usare; se è nil quello dell'app (`ServerCorrente`). I test ne mettono uno finto.
    var server: (any ServerClient)?
    private var attivo: any ServerClient { server ?? ServerCorrente.condiviso }

    private let memoria = NSCache<NSString, UIImage>()
    /// Indirizzi per cui il server non ha niente (404): non si richiedono di nuovo finché non cambia qualcosa.
    private var senzaImmagine = Set<String>()
    private var inCorso = Set<String>()
    /// Cambia quando l'utente carica uno stemma o una maglia nuovi: le copie vecchie non valgono più.
    private var edizione = 0

    init(server: (any ServerClient)? = nil) {
        self.server = server
        memoria.countLimit = 200
    }

    // MARK: indirizzi

    static func percorsoFoto(_ id: Int) -> String { "/api/foto/\(id)" }

    static func percorsoSquadra(_ nome: String, tipo: String) -> String {
        "/api/squadre/immagine?squadra=\(IndirizzoServer.codifica(nome))&tipo=\(tipo)"
    }

    private func chiaveSquadra(_ nome: String, _ tipo: String) -> String {
        Self.percorsoSquadra(nome, tipo: tipo) + "&v=\(edizione)"
    }

    // MARK: lettura dalla memoria (senza attese)

    func memoriaFoto(_ id: Int) -> UIImage? { memoria.object(forKey: Self.percorsoFoto(id) as NSString) }

    func memoriaSquadra(_ nome: String, tipo: String) -> UIImage? { memoria.object(forKey: chiaveSquadra(nome, tipo) as NSString) }

    func haFoto(_ id: Int) -> Bool { fotoDisponibili.contains(id) }

    func haImmagine(_ nome: String, tipo: String) -> Bool {
        let presenti = squadre[nome]
        return (tipo == "stemma" ? presenti?.stemma : presenti?.maglia) == true
    }

    // MARK: elenchi

    /// Chi ha la foto e quali squadre hanno stemma e maglia. Se il server non risponde restano gli elenchi di prima.
    func caricaElenchi() async {
        if let foto: FotoDisponibili = try? await attivo.get("/api/foto-disponibili") {
            fotoDisponibili = Set(foto.ids)
        }
        if let elenco: [SquadraLega] = try? await attivo.get("/api/squadre") {
            var nuove: [String: ImmaginiSquadra] = [:]
            for s in elenco { nuove[s.nome] = s.immagini ?? ImmaginiSquadra(stemma: false, maglia: false) }
            squadre = nuove
        }
    }

    // MARK: caricamento

    /// Carica la foto di un giocatore (disco, poi server) e la mette in memoria.
    func caricaFoto(_ id: Int) async {
        guard fotoDisponibili.contains(id) else { return }
        await carica(percorso: Self.percorsoFoto(id), chiave: Self.percorsoFoto(id))
    }

    func caricaSquadra(_ nome: String, tipo: String) async {
        guard haImmagine(nome, tipo: tipo) else { return }
        await carica(percorso: Self.percorsoSquadra(nome, tipo: tipo), chiave: chiaveSquadra(nome, tipo))
    }

    private func carica(percorso: String, chiave: String) async {
        if memoria.object(forKey: chiave as NSString) != nil || senzaImmagine.contains(chiave) || inCorso.contains(chiave) { return }
        inCorso.insert(chiave)
        defer { inCorso.remove(chiave) }
        let indirizzo = attivo.indirizzo
        // Prima il disco: si vede subito anche con il server spento.
        if let copia = await Cache.leggi(chiave, indirizzo: indirizzo, cartella: "img"), let img = UIImage(data: copia.dati) {
            memoria.setObject(img, forKey: chiave as NSString)
            versione += 1
            return
        }
        do {
            let dati = try await attivo.binario(percorso)
            guard let img = UIImage(data: dati) else { senzaImmagine.insert(chiave); return }
            memoria.setObject(img, forKey: chiave as NSString)
            Cache.salva(dati, chiave, indirizzo: indirizzo, cartella: "img")
            versione += 1
        } catch {
            // 404 o rete: per una foto mancante basta non riprovare in questa sessione.
            if case ErroreApi.server = error { senzaImmagine.insert(chiave) }
        }
    }

    // MARK: caricamento dell'utente

    /// Manda al server lo stemma o la maglia scelti (JPEG o PNG) e aggiorna gli elenchi.
    func invia(_ dati: Data, squadra: String, tipo: String) async throws {
        let percorso = Self.percorsoSquadra(squadra, tipo: tipo)
        _ = try await attivo.carica(percorso, nome: "immagine.jpg", dati: dati)
        edizione += 1   // le copie in memoria della squadra non valgono più (nuova chiave)
        await caricaElenchi()
        versione += 1
    }

    /// Per i test: svuota memoria e ricordi.
    func azzera() {
        memoria.removeAllObjects()
        senzaImmagine.removeAll()
        fotoDisponibili = []
        squadre = [:]
    }
}

extension UIImage {
    /// Ridimensiona (lato massimo `lato`) e codifica in JPEG: lo stemma o la maglia scelti dalla libreria possono pesare molti MB,
    /// il server ne accetta al massimo 4.
    func jpegPerServer(latoMassimo lato: CGFloat = 800, qualita: CGFloat = 0.85) -> Data? {
        let massimo = max(size.width, size.height)
        let fattore = massimo > lato ? lato / massimo : 1
        let nuova = CGSize(width: size.width * fattore, height: size.height * fattore)
        let formato = UIGraphicsImageRendererFormat.default()
        formato.scale = 1
        let ridotta = UIGraphicsImageRenderer(size: nuova, format: formato).image { _ in draw(in: CGRect(origin: .zero, size: nuova)) }
        return ridotta.jpegData(compressionQuality: qualita)
    }
}
