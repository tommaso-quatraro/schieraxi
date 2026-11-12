"""Aggiornamento dell'archivio da tutte le fonti. Scarica solo quello che manca o che può essere cambiato.

- listone: una volta al giorno
- calendario: tutto se manca o ha più di 7 giorni, altrimenti solo le giornate in corso
- voti: le giornate giocate che mancano, più quelle finite da meno di 4 giorni (le correzioni arrivano dopo)
- probabili formazioni: a ogni aggiornamento
- Understat: totali di stagione a ogni aggiornamento, dettaglio delle partite giocate che mancano
- dati extra di squadra (football-data): al massimo ogni 6 ore
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Callable

from . import archivio, controlli, fonti_attive, funzioni, listone, rete, squadre
from . import probabili_fonte2 as pf2
from .fonti import fantacalcio as fc
from .fonti import footballdata as fd
from .fonti import understat as us

GIORNATE = 38
MAX_STAGIONI_STORICHE = 6     # tetto: ogni stagione in più sono circa 420 richieste (10-15 minuti)
SOGLIA_COPIA = 0.95           # probabili uguali oltre questa quota alla giornata prima = copia (Aggiornamento._copia_della_giornata_prima)


class Stagione:
    """Una stagione nei vari formati delle fonti: '2026-27' (Fantacalcio.it), 2026 (Understat), '2627' (football-data)."""

    def __init__(self, anno_inizio: int):
        self.anno = anno_inizio
        self.codice = f"{anno_inizio}-{str(anno_inizio + 1)[-2:]}"
        self.fd = f"{str(anno_inizio)[-2:]}{str(anno_inizio + 1)[-2:]}"

    @classmethod
    def di(cls, giorno: date) -> "Stagione":
        return cls(giorno.year if giorno.month >= 7 else giorno.year - 1)

    def precedente(self, quante: int = 1) -> "Stagione":
        return Stagione(self.anno - quante)


def _ora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ultimo(db: sqlite3.Connection, cosa: str) -> datetime | None:
    r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = ?", (cosa,)).fetchone()
    return datetime.fromisoformat(r[0]) if r else None


def _recente(db, cosa: str, durata: timedelta) -> bool:
    u = _ultimo(db, cosa)
    return u is not None and datetime.now() - u < durata


class Aggiornamento:
    def __init__(self, db: sqlite3.Connection, stagione: Stagione, scrivi: Callable[[str], None] = print):
        self.db = db
        self.st = stagione
        self.scrivi = scrivi
        self.errori: list[str] = []
        self.slug_noti: set[str] = set()

    def _passo(self, nome: str, funzione, fonte: str | None = None) -> None:
        """Esegue un passo; se una fonte non risponde, gli altri passi continuano. Se la fonte è spenta il passo si salta."""
        if fonte and not fonti_attive.acceso(fonte):
            self.scrivi(f"  - {nome}: saltato, {fonti_attive.FONTI[fonte][0]} è spenta")
            return
        try:
            funzione()
            self.db.commit()
        except Exception as e:  # noqa: BLE001 - una fonte rotta non deve fermare le altre
            self.db.rollback()
            self.errori.append(f"{nome}: {type(e).__name__}: {e}")
            self.scrivi(f"  ! {nome}: non riuscito ({type(e).__name__}: {e})")

    def slug(self, nome: str) -> str | None:
        return squadre.slug(nome, self.slug_noti)

    # ---------- passi ----------
    def listone(self) -> None:
        calciatori, quando = listone.carica()
        self.db.execute("DELETE FROM calciatori")
        archivio.inserisci(self.db, "calciatori", [{**asdict(c), "aggiornato": quando} for c in calciatori])
        self.slug_noti = {c.squadra_slug for c in calciatori}
        archivio.inserisci(self.db, "quotazioni", [
            {"stagione": self.st.codice, "calciatore_id": c.id, "nome": c.nome, "ruolo": c.ruolo, "squadra": c.squadra_slug,
             "qi": c.quotazione_iniziale, "qa": c.quotazione, "fvm": c.fvm} for c in calciatori])
        self.scrivi(f"  listone: {len(calciatori)} calciatori")

    def quotazioni(self, stagione: Stagione) -> None:
        """Quotazioni di una stagione passata (una volta sola)."""
        if self.db.execute("SELECT COUNT(*) FROM quotazioni WHERE stagione = ?", (stagione.codice,)).fetchone()[0] > 300:
            return
        calciatori = listone.analizza_html(rete.scarica(listone.url_stagione(stagione.codice)).text)
        archivio.inserisci(self.db, "quotazioni", [
            {"stagione": stagione.codice, "calciatore_id": c.id, "nome": c.nome, "ruolo": c.ruolo, "squadra": c.squadra_slug,
             "qi": c.quotazione_iniziale, "qa": c.quotazione, "fvm": c.fvm} for c in calciatori])
        self.scrivi(f"  quotazioni {stagione.codice}: {len(calciatori)} calciatori")

    def _salva_partite(self, partite: list[dict], st: Stagione) -> int:
        for p in partite:
            p["stagione"] = st.codice
            vecchia = self.db.execute("SELECT understat_id FROM partite WHERE id = ?", (p["id"],)).fetchone()
            p["understat_id"] = vecchia[0] if vecchia else None
        n = archivio.inserisci(self.db, "partite", partite)
        # le squadre del calendario contano come note (le retrocesse non sono più nel listone)
        self.slug_noti |= {p["casa"] for p in partite} | {p["trasferta"] for p in partite}
        return n

    def calendario(self) -> None:
        """Calendario della stagione in corso (le stagioni passate si ricavano dalle pagine dei voti)."""
        st = self.st
        cosa = f"calendario {st.codice}"
        n = self.db.execute("SELECT COUNT(*) FROM partite WHERE stagione = ?", (st.codice,)).fetchone()[0]
        if n < GIORNATE * 10 or not _recente(self.db, cosa, timedelta(days=7)):
            giornate = range(1, GIORNATE + 1)
        else:  # solo le giornate con partite non finite e già iniziate o vicine
            limite = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
            giornate = [r[0] for r in self.db.execute(
                "SELECT DISTINCT giornata FROM partite WHERE stagione = ? AND giocata = 0 AND data <= ?",
                (st.codice, limite))]
        totale = 0
        for g in giornate:
            totale += self._calendario_giornata(g)
            self.db.commit()            # una giornata alla volta: il cron e il server non restano bloccati ad aspettare
        if len(giornate) == GIORNATE:
            archivio.segna(self.db, cosa, _ora())
        self.scrivi(f"  calendario {st.codice}: {totale} partite aggiornate ({len(giornate)} giornate)")

    def voti(self, stagione: Stagione | None = None) -> None:
        st = stagione or self.st
        if st is self.st:
            giornate = self._giornate_voti_da_scaricare()
        else:  # stagione passata: quelle senza voti o senza partite
            con_voti = {r[0] for r in self.db.execute("SELECT DISTINCT giornata FROM voti WHERE stagione = ?", (st.codice,))}
            con_partite = {r[0] for r in self.db.execute(
                "SELECT giornata FROM partite WHERE stagione = ? GROUP BY giornata HAVING COUNT(*) = 10", (st.codice,))}
            giornate = [g for g in range(1, GIORNATE + 1) if g not in con_voti or g not in con_partite]
        for g in giornate:
            html = rete.scarica(fc.url_voti(st.codice, g)).text
            righe = fc.leggi_voti(html, g)
            if st is not self.st:  # la pagina dei voti contiene anche le partite della giornata
                partite = fc.leggi_calendario(html, g, st.codice)
                if len(partite) != 10:
                    raise ValueError(f"voti {st.codice} giornata {g}: trovate {len(partite)} partite invece di 10")
                self._salva_partite(partite, st)
            self._salva_voti(st, g, righe)
        self.scrivi(f"  voti {st.codice}: {len(giornate)} giornate scaricate"
                    + (f" ({min(giornate)}-{max(giornate)})" if giornate else ""))

    def _calendario_giornata(self, g: int) -> int:
        """Una richiesta: il calendario (orari, risultati, giocata) di una giornata della stagione in corso."""
        st = self.st
        partite = fc.leggi_calendario(rete.scarica(fc.url_calendario(g)).text, g, st.codice)
        if len(partite) != 10:
            raise ValueError(f"giornata {g}: trovate {len(partite)} partite della stagione {st.codice} "
                             "invece di 10 (a cavallo dell'estate il sito può mostrare l'altra stagione)")
        return self._salva_partite(partite, st)

    def _salva_voti(self, st: Stagione, g: int, righe: list[dict]) -> None:
        if not righe:
            return
        self.db.execute("DELETE FROM voti WHERE stagione = ? AND giornata = ?", (st.codice, g))
        archivio.inserisci(self.db, "voti", [{**r, "stagione": st.codice} for r in righe])
        self.db.commit()

    def risultati_giornata(self, g: int) -> None:
        """Il giro leggero dopo le partite (pianificatore.py): solo risultati e voti di UNA giornata della stagione in corso,
        due richieste in tutto. Il calendario prima: i voti di una partita valgono quando il calendario la dà per giocata."""
        n = self._calendario_giornata(g)
        self.db.commit()
        righe = fc.leggi_voti(rete.scarica(fc.url_voti(self.st.codice, g)).text, g)
        self._salva_voti(self.st, g, righe)
        self.scrivi(f"  risultati {self.st.codice} giornata {g}: {n} partite, {len(righe)} voti")

    def _giornate_voti_da_scaricare(self) -> list[int]:
        presenti = {r[0] for r in self.db.execute("SELECT DISTINCT giornata FROM voti WHERE stagione = ?", (self.st.codice,))}
        recente = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d %H:%M")
        giornate = []
        for g, giocate, ultima in self.db.execute(
                "SELECT giornata, SUM(giocata), MAX(data) FROM partite WHERE stagione = ? GROUP BY giornata",
                (self.st.codice,)):
            if not giocate:
                continue
            if g not in presenti or giocate < 10 or (ultima or "") >= recente:
                giornate.append(g)
        return giornate

    def probabili(self) -> None:
        giornata, righe = fc.leggi_probabili(rete.scarica(fc.URL_PROBABILI).text)
        partite = {r["partita_id"] for r in righe}
        titolari = sum(r["stato"] == "titolare" for r in righe)
        if giornata is None or not partite or titolari < 20 * len(partite):
            raise ValueError(f"pagina probabili non riconosciuta (giornata {giornata}, {len(partite)} partite, "
                             f"{titolari} titolari)")
        # le partite devono essere di questa stagione e di quella giornata (a luglio il sito mostra ancora maggio)
        note = {r[0] for r in self.db.execute("SELECT id FROM partite WHERE stagione = ? AND giornata = ?",
                                              (self.st.codice, giornata))}
        if not partite <= note:
            raise ValueError(f"le probabili non corrispondono alla giornata {giornata} della stagione {self.st.codice}")
        quando = _ora()
        nuove = [{**r, "stagione": self.st.codice, "giornata": giornata, "fonte": "fantacalcio", "rilevato": quando}
                 for r in righe]
        copia = self._copia_della_giornata_prima(giornata, righe)
        if copia:
            # la pagina ha il numero della giornata nuova ma le formazioni di quella finita: resta nella storia con il segno e
            # basta. Per il resto dell'app la giornata è ancora senza probabili (presenze recenti, nessun avviso di cambi)
            archivio.inserisci(self.db, "probabili_storia", [{**r, "copia": 1} for r in nuove])
            self.scrivi(f"  probabili giornata {giornata}: copia della giornata {copia[0]} (uguali {copia[1]:.0%}), "
                        "non ancora uscite: non usate")
            return
        # per ogni giornata si tiene l'ultima rilevazione (servono a verificare quanto erano giuste);
        # chi legge deve sempre filtrare per giornata
        self.db.execute("DELETE FROM probabili WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio'",
                        (self.st.codice, giornata))
        archivio.inserisci(self.db, "probabili", nuove)
        archivio.inserisci(self.db, "probabili_storia", nuove)     # in più: la rilevazione resta anche dopo la prossima
        conta = {s: sum(r["stato"] == s for r in righe) for s in ("titolare", "panchina", "infortunato", "squalificato")}
        self.scrivi(f"  probabili giornata {giornata}: {conta}")

    def _copia_della_giornata_prima(self, giornata: int, righe: list[dict]) -> tuple[int, float] | None:
        """(giornata prima, quota di righe uguali) se la lettura è una copia della giornata prima, altrimenti None.
        Copia = la giornata non ha ancora probabili accettate e più di SOGLIA_COPIA delle righe (stato, percentuale, in dubbio
        per giocatore) sono uguali all'ultima lettura accettata della giornata prima. Misurato sull'archivio vero: le copie sono
        uguali al 99-100%, la prima lettura vera di una giornata al 40% circa."""
        st = self.st.codice
        if self.db.execute("SELECT 1 FROM probabili WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio' LIMIT 1",
                           (st, giornata)).fetchone():
            return None                          # la giornata ha già probabili vere: le letture dopo valgono sempre
        prima = self.db.execute("SELECT MAX(giornata) FROM probabili WHERE stagione = ? AND giornata < ? AND fonte = 'fantacalcio'",
                                (st, giornata)).fetchone()[0]
        if prima is None or not righe:
            return None
        vecchie = {r[0]: (r[1], r[2], r[3] or 0) for r in self.db.execute(
            "SELECT calciatore_id, stato, percentuale, in_dubbio FROM probabili WHERE stagione = ? AND giornata = ? "
            "AND fonte = 'fantacalcio'", (st, prima))}
        uguali = sum(vecchie.get(r["calciatore_id"]) == (r["stato"], r["percentuale"], r["in_dubbio"] or 0) for r in righe)
        quota = uguali / len(righe)
        return (prima, quota) if quota > SOGLIA_COPIA else None

    def probabili_fonte2(self) -> None:
        """Seconda fonte di probabili (feed Sosfanta) in modalità ombra: una richiesta ogni 30 minuti al massimo."""
        calciatori = [listone.Calciatore(**{c: r[c] for c in r.keys() if c != "aggiornato"})
                      for r in self.db.execute("SELECT * FROM calciatori")]
        esito = pf2.raccogli(self.db, self.st.codice, calciatori, scrivi=self.scrivi)
        self.scrivi(f"  probabili fonte 2: {esito['motivo']}" if esito["motivo"] else f"  probabili fonte 2: {esito['righe']} segnali nuovi")

    def understat(self, stagione: Stagione | None = None, dettaglio_partite: bool = True) -> None:
        st = stagione or self.st
        partite, giocatori = us.leggi_lega(rete.scarica(us.url_lega(st.anno), headers=us.HEADERS).json())
        if not partite:
            raise ValueError("Understat non ha restituito partite")
        archivio.inserisci(self.db, "understat_stagione", [
            {**{k: v for k, v in g.items() if k != "nome"}, "stagione": st.codice} for g in giocatori])
        # anagrafica e abbinamento al listone (quello già trovato non si rifà)
        calciatori = [listone.Calciatore(**{k: r[k] for k in r.keys() if k != "aggiornato"})
                      for r in self.db.execute("SELECT * FROM calciatori")]
        # anche chi ha preso voti in quella stagione ma non è nel listone (giovani aggregati, ceduti, retrocessi)
        for r in self.db.execute(
                "SELECT calciatore_id, nome, ruolo, squadra, MAX(giornata) FROM voti v WHERE stagione = ? AND NOT EXISTS "
                "(SELECT 1 FROM calciatori c WHERE c.id = v.calciatore_id) GROUP BY calciatore_id", (st.codice,)):
            calciatori.append(listone.Calciatore(r[0], r[1], r[2], "", (r[3] or "")[:3].upper(), r[3], 0, 0, 0))
        if st is self.st:
            # gli abbinamenti sicuri restano; quelli per somiglianza si rifanno ogni volta (il listone cambia)
            fissi = "calciatore_id IS NOT NULL AND abbinamento IN ('squadra', 'altra_squadra')"
        else:
            # stagione passata: si cercano solo i non abbinati, senza toccare la squadra di quest'anno
            fissi = "calciatore_id IS NOT NULL"
        gia = {r[0] for r in self.db.execute(f"SELECT id FROM understat_giocatori WHERE {fissi}")}
        occupati = {r[0] for r in self.db.execute(f"SELECT calciatore_id FROM understat_giocatori WHERE {fissi}")}
        da_abbinare = [g for g in giocatori if g["understat_giocatore"] not in gia]
        abbinati = us.abbina(da_abbinare, [c for c in calciatori if c.id not in occupati], self.slug)
        for g in da_abbinare:
            cid, metodo = abbinati.get(g["understat_giocatore"], (None, None))
            esiste = self.db.execute("SELECT 1 FROM understat_giocatori WHERE id = ?", (g["understat_giocatore"],)).fetchone()
            if esiste and st is not self.st:
                self.db.execute("UPDATE understat_giocatori SET calciatore_id = ?, abbinamento = ? WHERE id = ?",
                                (cid, metodo, g["understat_giocatore"]))
            else:
                self.db.execute("INSERT OR REPLACE INTO understat_giocatori VALUES (?, ?, ?, ?, ?, ?)",
                                (g["understat_giocatore"], g["nome"], g["squadre"], g["posizione"], cid, metodo))
        # partite di qualunque stagione, collegate al calendario di Fantacalcio.it
        for p in partite:
            casa, trasferta = self.slug(p["casa"]), self.slug(p["trasferta"])
            if not casa or not trasferta:
                raise ValueError(f"squadra Understat non riconosciuta: {p['casa']} - {p['trasferta']}")
            vecchia = self.db.execute("SELECT scaricata FROM partite_understat WHERE id = ?", (p["id"],)).fetchone()
            archivio.inserisci(self.db, "partite_understat", [{
                **p, "casa": casa, "trasferta": trasferta, "stagione": st.codice,
                "scaricata": vecchia[0] if vecchia else 0}])
            self.db.execute("UPDATE partite SET understat_id = ? WHERE stagione = ? AND casa = ? AND trasferta = ?",
                            (p["id"], st.codice, casa, trasferta))
        self.db.commit()
        nuove = 0
        if dettaglio_partite:
            # le partite mancanti, e quelle degli ultimi giorni (gli xG vengono rivisti dopo la partita)
            recente = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")
            for pid, casa, trasferta in self.db.execute(
                    "SELECT id, casa, trasferta FROM partite_understat WHERE stagione = ? AND giocata = 1 "
                    "AND (scaricata = 0 OR data >= ?)", (st.codice, recente)).fetchall():
                righe = us.leggi_partita(rete.scarica(us.url_partita(pid), headers=us.HEADERS).json(), pid, casa, trasferta)
                self.db.execute("DELETE FROM prestazioni WHERE understat_partita = ?", (pid,))
                archivio.inserisci(self.db, "prestazioni", righe)
                completa = len(righe) >= 22   # tabellino non ancora pronto: si riprova la prossima volta
                self.db.execute("UPDATE partite_understat SET scaricata = ? WHERE id = ?", (int(completa), pid))
                self.db.commit()
                nuove += 1
        senza = sum(1 for g in giocatori if g["minuti"] > 0 and g["understat_giocatore"] not in gia
                    and g["understat_giocatore"] not in abbinati)
        self.scrivi(f"  Understat {st.codice}: {len(giocatori)} giocatori ({senza} con minuti non abbinati), "
                    f"{nuove} partite scaricate in dettaglio")

    def dati_extra(self, stagione: Stagione | None = None) -> None:
        """Statistiche di squadra di football-data.co.uk (solo misure, il modello non le legge)."""
        st = stagione or self.st
        if st is self.st:
            if _recente(self.db, "dati-extra", timedelta(hours=6)):
                self.scrivi("  dati extra di squadra: già aggiornati di recente")
                return
            urls = (fd.url_stagione(st.fd), fd.URL_PROSSIME)
        else:  # stagione passata: una volta sola
            if _ultimo(self.db, f"dati-extra {st.codice}"):
                return
            urls = (fd.url_stagione(st.fd),)
        extra = []
        for url in urls:
            extra += fd.leggi_extra(rete.scarica(url).content.decode("utf-8-sig", errors="replace"), self.slug)
        quando = _ora()
        archivio.inserisci(self.db, "partite_extra", [{**r, "stagione": st.codice, "rilevato": quando} for r in extra])
        archivio.segna(self.db, "dati-extra" if st is self.st else f"dati-extra {st.codice}", quando)
        self.scrivi(f"  dati extra di squadra {st.codice}: {len(extra)} partite")

    # ---------- tutto ----------
    def esegui(self, storico: bool = False, stagioni_storiche: int = 1) -> list[str]:
        """storico: scarica anche le stagioni passate (una volta sola, poi saltano ciò che c'è già);
        stagioni_storiche: quante, dalla più recente (1 = solo la scorsa, come sempre)."""
        if not 1 <= stagioni_storiche <= MAX_STAGIONI_STORICHE:
            raise ValueError(f"stagioni storiche: da 1 a {MAX_STAGIONI_STORICHE}")
        self._passo("listone", self.listone, "fantacalcio")
        if not self.slug_noti:
            self.slug_noti = {r[0] for r in self.db.execute("SELECT DISTINCT squadra_slug FROM calciatori")}
        # anche le squadre delle stagioni passate (retrocesse) già in archivio
        self.slug_noti |= {r[0] for r in self.db.execute("SELECT DISTINCT casa FROM partite WHERE casa IS NOT NULL")}
        self._passo("calendario", self.calendario, "fantacalcio")
        self._passo("voti", self.voti, "fantacalcio")
        self._passo("probabili", self.probabili, "fantacalcio")
        if funzioni.acceso("fonti_ombra"):               # le due fonti «in ombra» servono solo a misurare il modello
            self._passo("probabili fonte 2", self.probabili_fonte2, "sosfanta")
        else:
            self.scrivi("  - probabili fonte 2: saltato, le fonti in ombra sono spente")
        self._passo("Understat", self.understat, "understat")
        if funzioni.acceso("fonti_ombra"):
            self._passo("dati extra", self.dati_extra, "footballdata")
        else:
            self.scrivi("  - dati extra: saltato, le fonti in ombra sono spente")
        if storico:
            for k in range(1, stagioni_storiche + 1):
                precedente = self.st.precedente(k)
                self._passo(f"voti {precedente.codice}", lambda p=precedente: self.voti(p), "fantacalcio")
                self._passo(f"Understat {precedente.codice}", lambda p=precedente: self.understat(p), "understat")
                self._passo(f"dati extra {precedente.codice}", lambda p=precedente: self.dati_extra(p), "footballdata")
                self._passo(f"quotazioni {precedente.codice}", lambda p=precedente: self.quotazioni(p), "fantacalcio")
        self._passo("controlli", self.controlli)
        archivio.segna(self.db, "aggiornamento", _ora(), json.dumps(self.errori, ensure_ascii=False))
        self.db.commit()
        return self.errori

    def controlli(self) -> None:
        """Controlli di coerenza dei dati appena scaricati. Gli avvisi si mostrano ma non contano come passi falliti."""
        risultati = controlli.esegui(self.db)
        storti = [r for r in risultati if r["esito"] != "ok"]
        self.scrivi(f"  controlli dei dati: {len(risultati) - len(storti)} ok, {len(storti)} da guardare")
        for r in storti:
            self.scrivi(f"  ! {r['stagione']} {r['nome']}: {r['dettaglio']}")


def esegui(storico: bool = False, scrivi: Callable[[str], None] = print, stagioni_storiche: int = 1) -> list[str]:
    db = archivio.apri()
    try:
        st = Stagione.di(date.today())
        scrivi(f"Aggiornamento stagione {st.codice}" + (
            (" (con la stagione scorsa)" if stagioni_storiche == 1 else f" (con le {stagioni_storiche} stagioni scorse)")
            if storico else ""))
        errori = Aggiornamento(db, st, scrivi).esegui(storico, stagioni_storiche)
        scrivi(f"Fatto: {rete.contatore} richieste" + (f", {len(errori)} passi non riusciti" if errori else ""))
        return errori
    finally:
        db.close()
