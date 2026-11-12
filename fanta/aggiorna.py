"""Aggiornamento dell'archivio da tutte le fonti. Scarica solo quello che manca o che può essere cambiato.

- listone: una volta al giorno
- calendario: tutto se manca o ha più di 7 giorni, altrimenti solo le giornate in corso
- voti: le giornate giocate che mancano o con squadre ancora senza voti, più quelle finite da meno di 4 giorni (le correzioni
  arrivano dopo)
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

import requests

from . import archivio, controlli, fonti_attive, funzioni, listone, rete, squadre
from .fonti import fantacalcio as fc
from .fonti import footballdata as fd
from .fonti import understat as us

GIORNATE = 38
MAX_STAGIONI_STORICHE = 6     # tetto: ogni stagione in più sono circa 420 richieste (10-15 minuti)
SOGLIA_COPIA = 0.95           # probabili uguali oltre questa quota alla giornata prima = copia (Aggiornamento._copia_della_giornata_prima)
ORE_SENZA_PROBABILI = 96      # una giornata senza formazioni è normale se la prima partita è più lontana di così; più vicina è un errore
#                               (le probabili escono 3-4 giorni prima: così il guasto si vede prima delle ultime 24 ore)
CALO_ACCETTABILE = 2          # voti in meno di quelli salvati che possono essere una correzione della redazione...
LETTURE_UGUALI = 3            # ...e si accettano dopo tante letture uguali di fila (Aggiornamento._accetta_calo_o_ferma)


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


class AltraStagione(ValueError):
    """La pagina mostra ancora (o già) un'altra stagione: d'estate è normale, il passo riesce senza dati (vedi `calendario`)."""


class VotiCalati(ValueError):
    """La pagina dei voti di una giornata ha meno righe di quelle già salvate: non si salva (Aggiornamento._salva_voti)."""


class StatisticheCalate(ValueError):
    """La rilettura delle statistiche di una partita ha meno righe di quelle già salvate: restano quelle (Aggiornamento.understat)."""


def _ora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ultimo(db: sqlite3.Connection, cosa: str) -> datetime | None:
    r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = ?", (cosa,)).fetchone()
    return datetime.fromisoformat(r[0]) if r else None


def _recente(db, cosa: str, durata: timedelta) -> bool:
    u = _ultimo(db, cosa)
    return u is not None and datetime.now() - u < durata


def _ora_breve(quando: str | None) -> str:
    """'2026-11-02T08:03:04' -> '02/11 alle 08:03' (per i messaggi d'errore)."""
    try:
        return datetime.fromisoformat(str(quando)[:19]).strftime("%d/%m alle %H:%M")
    except ValueError:
        return str(quando)


def _da_quando(prima: dict | None) -> str:
    """Coda dell'errore di un passo seguito: da quando non riesce (se non è la prima volta) e l'ultimo successo."""
    if not prima:
        return ""
    parti = [f"non riesce dal {_ora_breve(prima['dal'])}"] if prima.get("dal") else []
    parti.append(f"ultimo riuscito il {_ora_breve(prima['ultimo_successo'])}" if prima.get("ultimo_successo") else "mai riuscito")
    return f" ({'; '.join(parti)})"


class Aggiornamento:
    def __init__(self, db: sqlite3.Connection, stagione: Stagione, scrivi: Callable[[str], None] = print):
        self.db = db
        self.st = stagione
        self.scrivi = scrivi
        self.errori: list[str] = []
        self.riusciti: list[str] = []
        self.slug_noti: set[str] = set()
        # righe di `aggiornamenti` con un'ora nuova da scrivere a fine giro: dentro `esegui` si scrivono tutte insieme alla riga
        # generale, così la «versione» dei dati (consigli._versione, che guarda le ore di quelle righe) cambia una volta sola per
        # aggiornamento e il riscaldamento ricalcola una volta. None = fuori da `esegui` (giri del pianificatore): subito.
        self._a_fine: list[tuple[str, str, str | None]] | None = None

    def _passo(self, nome: str, funzione, fonte: str | None = None) -> None:
        """Esegue un passo; se una fonte non risponde, gli altri passi continuano. Se la fonte è spenta il passo si salta.
        I passi seguiti (`archivio.PASSI`) scrivono il loro esito: ultimo successo (a fine giro, vedi `_a_fine`), o errore con l'ora
        del primo fallimento di fila; nell'errore della corsa c'è da quando il passo non riesce (così la riga generale non lo fa
        sembrare fresco). Un errore cambia solo il dettaglio della riga, non la sua ora: la versione dei dati non cambia."""
        if fonte and not fonti_attive.acceso(fonte):
            self.scrivi(f"  - {nome}: saltato, {fonti_attive.FONTI[fonte][0]} è spenta")
            self._segna_esito(nome, saltato=True)
            return
        try:
            funzione()
            if self._a_fine is None:
                self._segna_esito(nome)
            else:
                self._a_fine.append(("passo", nome, _ora()))
            self.db.commit()
            self.riusciti.append(nome)
        except Exception as e:  # noqa: BLE001 - una fonte rotta non deve fermare le altre
            self.db.rollback()
            errore = f"{type(e).__name__}: {e}"
            prima = self._segna_esito(nome, errore=errore)
            self.errori.append(f"{nome}: {errore}{_da_quando(prima)}")
            self.scrivi(f"  ! {nome}: non riuscito ({errore}){_da_quando(prima)}")

    def _segna_esito(self, nome: str, errore: str | None = None, saltato: bool = False) -> dict | None:
        """Esito del passo in `aggiornamenti` (`archivio.segna_passo`). Se l'archivio non lo accetta (occupato) si scrive nel registro
        e si va avanti: il passo vero conta più del suo resoconto."""
        try:
            if saltato:
                archivio.passo_saltato(self.db, nome)
                self.db.commit()
                return None
            prima = archivio.segna_passo(self.db, nome, _ora(), errore)
            if errore is not None:
                self.db.commit()
            return prima
        except sqlite3.Error as e:
            self.scrivi(f"  ! {nome}: esito del passo non salvato ({type(e).__name__})")
            return None

    def _segna(self, cosa: str, quando: str) -> None:
        """Una riga di `aggiornamenti` con un'ora nuova: a fine giro dentro `esegui`, subito fuori."""
        if self._a_fine is None:
            archivio.segna(self.db, cosa, quando)
        else:
            self._a_fine.append(("riga", cosa, quando))

    def _scrivi_a_fine(self) -> None:
        """Le righe tenute da parte durante il giro (`_a_fine`), nella stessa conferma della riga generale."""
        righe, self._a_fine = self._a_fine or [], None
        for tipo, cosa, quando in righe:
            try:
                if tipo == "passo":
                    archivio.segna_passo(self.db, cosa, quando)
                else:
                    archivio.segna(self.db, cosa, quando)
            except sqlite3.Error as e:
                self.scrivi(f"  ! {cosa}: esito del passo non salvato ({type(e).__name__})")

    def slug(self, nome: str) -> str | None:
        return squadre.slug(nome, self.slug_noti)

    # ---------- passi ----------
    def listone(self) -> None:
        # severo: se la pagina non si legge il passo non riesce (prima: si usava la copia di ieri senza dirlo)
        calciatori, quando = listone.carica(severo=True)
        self.db.execute("DELETE FROM calciatori")
        archivio.inserisci(self.db, "calciatori", [{**asdict(c), "aggiornato": quando} for c in calciatori])
        self.slug_noti = {c.squadra_slug for c in calciatori}
        archivio.inserisci(self.db, "quotazioni", [
            {"stagione": self.st.codice, "calciatore_id": c.id, "nome": c.nome, "ruolo": c.ruolo, "squadra": c.squadra_slug,
             "qi": c.quotazione_iniziale, "qa": c.quotazione, "fvm": c.fvm} for c in calciatori])
        self.scrivi(f"  listone: {len(calciatori)} calciatori (scaricato {_ora_breve(quando)})")

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
            try:
                totale += self._calendario_giornata(g)
            except AltraStagione as e:  # d'estate: niente da aggiornare, una richiesta sola, nessun guasto
                self.scrivi(f"  calendario {st.codice}: {e}, niente da aggiornare")
                return
            self.db.commit()            # una giornata alla volta: il cron e il server non restano bloccati ad aspettare
        if len(giornate) == GIORNATE:
            self._segna(cosa, _ora())
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
        calate, scartate = [], 0
        for g in giornate:
            html = rete.scarica(fc.url_voti(st.codice, g)).text
            righe, n = fc.leggi_voti_e_scarti(html, g)
            scartate += n
            if st is not self.st:  # la pagina dei voti contiene anche le partite della giornata
                partite = fc.leggi_calendario(html, g, st.codice)
                if len(partite) != 10:
                    raise ValueError(f"voti {st.codice} giornata {g}: trovate {len(partite)} partite invece di 10")
                self._salva_partite(partite, st)
            try:
                self._salva_voti(st, g, righe)
            except VotiCalati as e:      # le altre giornate si salvano lo stesso; il passo poi non riesce, con il motivo
                calate.append(str(e))
        self.scrivi(f"  voti {st.codice}: {len(giornate)} giornate scaricate"
                    + (f" ({min(giornate)}-{max(giornate)})" if giornate else "")
                    + (f", {scartate} righe senza i tre voti scartate" if scartate else ""))
        if calate:
            raise VotiCalati("; ".join(calate))

    def _calendario_giornata(self, g: int) -> int:
        """Una richiesta: il calendario (orari, risultati, giocata) di una giornata della stagione in corso."""
        st = self.st
        html = rete.scarica(fc.url_calendario(g)).text
        partite = fc.leggi_calendario(html, g, st.codice)
        if not partite and self._altra_stagione_ammessa(altre := fc.stagioni_nel_calendario(html) - {st.codice}):
            raise AltraStagione(f"il sito mostra ancora la stagione {', '.join(sorted(altre))}")
        if len(partite) != 10:
            raise ValueError(f"giornata {g}: trovate {len(partite)} partite della stagione {st.codice} "
                             "invece di 10 (a cavallo dell'estate il sito può mostrare l'altra stagione)")
        return self._salva_partite(partite, st)

    def _stagione_iniziata(self, st: Stagione) -> bool:
        """Almeno una partita della stagione già giocata, secondo il calendario in archivio."""
        return self.db.execute("SELECT 1 FROM partite WHERE stagione = ? AND giocata = 1 LIMIT 1", (st.codice,)).fetchone() is not None

    def _altra_stagione_ammessa(self, altre: set[str] | list[str]) -> bool:
        """Una pagina che mostra un'altra stagione è l'estate (passo riuscito senza dati) solo se la stagione in corso non è ancora
        iniziata o se quella mostrata è proprio la precedente. Altrimenti (in stagione, una stagione qualunque o scritta in un altro
        modo, per esempio «2026-2027») è un cambio del sito: errore del passo, se no calendario, risultati e voti si fermano zitti."""
        return bool(altre) and (not self._stagione_iniziata(self.st) or set(altre) == {self.st.precedente().codice})

    def _salva_voti(self, st: Stagione, g: int, righe: list[dict]) -> None:
        """Riscrive i voti di una giornata, ma non con meno righe di quelle salvate (`VotiCalati`, i voti di prima restano): una
        pagina letta a metà o cambiata non cancella voti buoni. Una correzione vera della redazione (fino a CALO_ACCETTABILE righe
        in meno) si accetta quando la stessa pagina più corta arriva LETTURE_UGUALI volte di fila, e si scrive nel registro; un calo
        più grande resta bloccato e il passo voti non riesce (errore visibile, salute dopo 24 ore). Pagina vuota senza voti salvati =
        voti non ancora usciti."""
        prima = self.db.execute("SELECT COUNT(*) FROM voti WHERE stagione = ? AND giornata = ?", (st.codice, g)).fetchone()[0]
        if len(righe) < prima:
            self._accetta_calo_o_ferma(st, g, len(righe), prima)      # alza VotiCalati se il calo non si accetta
        self.db.execute("DELETE FROM voti_calati WHERE stagione = ? AND giornata = ?", (st.codice, g))
        if not righe:
            return
        self.db.execute("DELETE FROM voti WHERE stagione = ? AND giornata = ?", (st.codice, g))
        archivio.inserisci(self.db, "voti", [{**r, "stagione": st.codice} for r in righe])
        self.db.commit()

    def _accetta_calo_o_ferma(self, st: Stagione, g: int, righe: int, prima: int) -> None:
        """Una pagina dei voti con meno righe di quelle salvate: conta le letture uguali di fila (`voti_calati`, confermato subito,
        così il conto resta anche se il passo poi non riesce) e alza `VotiCalati` finché il calo non si accetta."""
        r = self.db.execute("SELECT righe, volte, dal FROM voti_calati WHERE stagione = ? AND giornata = ?", (st.codice, g)).fetchone()
        stessa = r is not None and r[0] == righe
        volte = (r[1] + 1) if stessa else 1
        piccolo = righe > 0 and prima - righe <= CALO_ACCETTABILE
        if piccolo and volte >= LETTURE_UGUALI:
            self.scrivi(f"  voti {st.codice} giornata {g}: accettata la pagina con {righe} voti (prima {prima}) "
                        f"dopo {volte} letture uguali")
            return
        self.db.execute("INSERT OR REPLACE INTO voti_calati VALUES (?, ?, ?, ?, ?, ?)",
                        (st.codice, g, righe, prima, volte, r[2] if stessa else _ora()))
        self.db.commit()
        motivo = (f"lettura {volte} di {LETTURE_UGUALI}" if piccolo
                  else f"lettura {volte}, {prima - righe} in meno: troppi per accettarla da sola")
        raise VotiCalati(f"voti {st.codice} giornata {g}: la pagina ha {righe} voti, prima erano {prima}: tenuti quelli di prima "
                         f"({motivo})")

    def risultati_giornata(self, g: int) -> None:
        """Il giro leggero dopo le partite (pianificatore.py): solo risultati e voti di UNA giornata della stagione in corso,
        due richieste in tutto. Il calendario prima: i voti di una partita valgono quando il calendario la dà per giocata."""
        n = self._calendario_giornata(g)
        self.db.commit()
        righe, _ = fc.leggi_voti_e_scarti(rete.scarica(fc.url_voti(self.st.codice, g)).text, g)
        self._salva_voti(self.st, g, righe)
        self.scrivi(f"  risultati {self.st.codice} giornata {g}: {n} partite, {len(righe)} voti")

    def _giornate_voti_da_scaricare(self) -> list[int]:
        """Le giornate con partite giocate senza voti, quelle con partite ancora da giocare, quelle finite da meno di 4 giorni (le
        correzioni arrivano dopo) e quelle in cui una squadra di una partita giocata non ha nessun voto: i voti arrivati a metà,
        con la fonte poi ferma per giorni, si riprendono al ritorno (#658)."""
        presenti = {r[0] for r in self.db.execute("SELECT DISTINCT giornata FROM voti WHERE stagione = ?", (self.st.codice,))}
        a_meta = controlli.squadre_senza_voti(self.db, self.st.codice)
        recente = (datetime.fromisoformat(_ora()) - timedelta(days=4)).strftime("%Y-%m-%d %H:%M")
        giornate = []
        for g, giocate, ultima in self.db.execute(
                "SELECT giornata, SUM(giocata), MAX(data) FROM partite WHERE stagione = ? GROUP BY giornata",
                (self.st.codice,)):
            if not giocate:
                continue
            if g not in presenti or giocate < 10 or (ultima or "") >= recente or g in a_meta:
                giornate.append(g)
        return giornate

    def probabili(self) -> None:
        giornata, righe = fc.leggi_probabili(rete.scarica(fc.URL_PROBABILI).text)
        partite = {r["partita_id"] for r in righe}
        titolari = sum(r["stato"] == "titolare" for r in righe)
        non_riconosciuta = (f"pagina probabili non riconosciuta (giornata {giornata}, {len(partite)} partite, "
                            f"{titolari} titolari)")
        if giornata is None:
            raise ValueError(non_riconosciuta)
        # le partite devono essere di questa stagione e di quella giornata (a luglio il sito mostra ancora maggio)
        note = {r[0] for r in self.db.execute("SELECT id FROM partite WHERE stagione = ? AND giornata = ?",
                                              (self.st.codice, giornata))}
        if partite and not partite <= note:
            altre = self._stagioni_delle_partite(partite)
            if self._altra_stagione_ammessa(altre):     # d'estate la pagina mostra ancora la stagione finita: niente da salvare
                self.scrivi(f"  probabili: la pagina è ancora della stagione {', '.join(altre)} (giornata {giornata}), "
                            "niente da salvare")
                return
            raise ValueError(f"le probabili non corrispondono alla giornata {giornata} della stagione {self.st.codice}")
        if titolari < 20 * max(1, len(partite)):
            if self._ore_alla_giornata(giornata) > ORE_SENZA_PROBABILI:
                # giornata lontana senza formazioni (per esempio la prima, ad agosto): normale, la giornata resta senza probabili
                self.scrivi(f"  probabili giornata {giornata}: non ancora uscite ({titolari} titolari), niente da salvare")
                return
            raise ValueError(non_riconosciuta)   # vicino alle partite una pagina senza titolari non è normale
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

    def _stagioni_delle_partite(self, partite: set[int]) -> list[str]:
        """Le altre stagioni a cui appartengono TUTTE queste partite secondo l'archivio ([] se anche una sola non si conosce)."""
        segnaposto = ", ".join("?" * len(partite))
        righe = self.db.execute(f"SELECT id, stagione FROM partite WHERE id IN ({segnaposto}) AND stagione <> ?",
                                (*partite, self.st.codice)).fetchall()
        return sorted({r[1] for r in righe}) if {r[0] for r in righe} == partite else []

    def _ore_alla_giornata(self, giornata: int) -> float:
        """Ore da adesso alla prima partita della giornata (stagione in corso); -inf se la giornata non è in calendario."""
        r = self.db.execute("SELECT MIN(data) FROM partite WHERE stagione = ? AND giornata = ?", (self.st.codice, giornata)).fetchone()
        try:
            inizio = datetime.fromisoformat(str(r[0]).replace(" ", "T")[:16]) if r and r[0] else None
        except ValueError:
            inizio = None
        return float("-inf") if inizio is None else (inizio - datetime.fromisoformat(_ora())).total_seconds() / 3600

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

    def understat(self, stagione: Stagione | None = None, dettaglio_partite: bool = True) -> None:
        st = stagione or self.st
        # una pagina web al posto dei dati (manutenzione, blocco) ferma il passo qui, con un errore che lo dice: nessuna altra richiesta
        partite, giocatori = us.leggi_lega(us.dati_json(rete.scarica(us.url_lega(st.anno), headers=us.HEADERS).content))
        if not partite:
            if not self._stagione_iniziata(st):     # d'estate la stagione nuova può non esserci ancora: niente da leggere
                self.scrivi(f"  Understat {st.codice}: stagione non ancora iniziata, niente da leggere")
                return
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
        nuove, calate = 0, []
        if dettaglio_partite:
            # le partite mancanti, e quelle degli ultimi giorni (gli xG vengono rivisti dopo la partita)
            recente = (datetime.fromisoformat(_ora()) - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")
            for pid, casa, trasferta in self.db.execute(
                    "SELECT id, casa, trasferta FROM partite_understat WHERE stagione = ? AND giocata = 1 "
                    "AND (scaricata = 0 OR data >= ?)", (st.codice, recente)).fetchall():
                righe = us.leggi_partita(us.dati_json(rete.scarica(us.url_partita(pid), headers=us.HEADERS).content), pid, casa,
                                         trasferta)
                prima = self.db.execute("SELECT COUNT(*) FROM prestazioni WHERE understat_partita = ?", (pid,)).fetchone()[0]
                if len(righe) < prima:
                    # una rilettura senza tabellino (o più corta) non cancella le righe buone: restano, e il passo non riesce (#658)
                    calate.append(f"partita {pid} ({casa}-{trasferta}): la rilettura ha {len(righe)} righe, prima erano {prima}")
                    continue
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
        if calate:
            raise StatisticheCalate(f"statistiche {st.codice}: " + "; ".join(calate) + ": tenute quelle di prima")

    def dati_extra(self, stagione: Stagione | None = None) -> None:
        """Statistiche di squadra di football-data.co.uk (solo misure, il modello non le legge). Stagione in corso al massimo ogni
        6 ore: l'ora dell'ultima lettura è quella delle righe salvate (la riga «dati-extra» di `aggiornamenti` è l'esito del passo,
        `archivio.PASSI`); una stagione passata una volta sola."""
        st = stagione or self.st
        if st is self.st:
            r = self.db.execute("SELECT MAX(rilevato) FROM partite_extra WHERE stagione = ?", (st.codice,)).fetchone()
            if r and r[0] and datetime.fromisoformat(_ora()) - datetime.fromisoformat(str(r[0])[:19]) < timedelta(hours=6):
                self.scrivi("  dati extra di squadra: già aggiornati di recente")
                return
            urls = (fd.url_stagione(st.fd), fd.URL_PROSSIME)
        else:  # stagione passata: una volta sola
            if _ultimo(self.db, f"dati-extra {st.codice}"):
                return
            urls = (fd.url_stagione(st.fd),)
        extra = []
        for url in urls:
            try:
                risposta = rete.scarica(url)
            except requests.HTTPError as e:
                # il file di una stagione esce dopo le prime partite: prima di allora «non trovato» è normale
                if url != fd.url_stagione(st.fd) or getattr(e.response, "status_code", None) != 404 or self._stagione_iniziata(st):
                    raise
                self.scrivi(f"  dati extra di squadra {st.codice}: file della stagione non ancora uscito")
                continue
            extra += fd.leggi_extra(risposta.content.decode("utf-8-sig", errors="replace"), self.slug)
        quando = _ora()
        archivio.inserisci(self.db, "partite_extra", [{**r, "stagione": st.codice, "rilevato": quando} for r in extra])
        if st is not self.st:
            self._segna(f"dati-extra {st.codice}", quando)
        self.scrivi(f"  dati extra di squadra {st.codice}: {len(extra)} partite")

    # ---------- tutto ----------
    def esegui(self, storico: bool = False, stagioni_storiche: int = 1) -> list[str]:
        """storico: scarica anche le stagioni passate (una volta sola, poi saltano ciò che c'è già);
        stagioni_storiche: quante, dalla più recente (1 = solo la scorsa, come sempre)."""
        if not 1 <= stagioni_storiche <= MAX_STAGIONI_STORICHE:
            raise ValueError(f"stagioni storiche: da 1 a {MAX_STAGIONI_STORICHE}")
        self._a_fine = []                   # le ore nuove di `aggiornamenti` a fine giro, tutte insieme (vedi __init__)
        self._passo("listone", self.listone, "fantacalcio")
        if not self.slug_noti:
            self.slug_noti = {r[0] for r in self.db.execute("SELECT DISTINCT squadra_slug FROM calciatori")}
        # anche le squadre delle stagioni passate (retrocesse) già in archivio
        self.slug_noti |= {r[0] for r in self.db.execute("SELECT DISTINCT casa FROM partite WHERE casa IS NOT NULL")}
        self._passo("calendario", self.calendario, "fantacalcio")
        self._passo("voti", self.voti, "fantacalcio")
        self._passo("probabili", self.probabili, "fantacalcio")
        self._passo("Understat", self.understat, "understat")
        if funzioni.acceso("fonti_ombra"):               # la fonte «in ombra» (football-data) serve solo a misurare il modello
            self._passo("dati extra", self.dati_extra, "footballdata")
        else:
            self.scrivi("  - dati extra: saltato, le fonti in ombra sono spente")
            self._segna_esito("dati extra", saltato=True)
        if storico:
            for k in range(1, stagioni_storiche + 1):
                precedente = self.st.precedente(k)
                self._passo(f"voti {precedente.codice}", lambda p=precedente: self.voti(p), "fantacalcio")
                self._passo(f"Understat {precedente.codice}", lambda p=precedente: self.understat(p), "understat")
                self._passo(f"dati extra {precedente.codice}", lambda p=precedente: self.dati_extra(p), "footballdata")
                self._passo(f"quotazioni {precedente.codice}", lambda p=precedente: self.quotazioni(p), "fantacalcio")
        self._passo("controlli", self.controlli)
        self._scrivi_a_fine()
        errori = json.dumps(self.errori, ensure_ascii=False)
        if any(n != "controlli" for n in self.riusciti):
            archivio.segna(self.db, "aggiornamento", _ora(), errori)
        else:
            # nessun passo dei dati è riuscito: l'ora resta quella dell'ultimo aggiornamento riuscito almeno in parte (così «I dati non
            # si aggiornano» e la salute se ne accorgono), gli errori sono quelli di adesso
            if not self.db.execute("UPDATE aggiornamenti SET dettaglio = ? WHERE cosa = 'aggiornamento'", (errori,)).rowcount:
                archivio.segna(self.db, "aggiornamento", None, errori)
        self.db.commit()
        return self.errori

    def controlli(self) -> None:
        """Controlli di coerenza dei dati appena scaricati. Gli avvisi si mostrano ma non contano come passi falliti; un «errore» dei
        controlli che sui dati veri danno sempre zero (`controlli.CONTANO_COME_ERRORI`) conta tra gli errori della corsa."""
        risultati = controlli.esegui(self.db)
        storti = [r for r in risultati if r["esito"] != "ok"]
        self.scrivi(f"  controlli dei dati: {len(risultati) - len(storti)} ok, {len(storti)} da guardare")
        for r in storti:
            self.scrivi(f"  ! {r['stagione']} {r['nome']}: {r['dettaglio']}")
            if r["nome"] in controlli.CONTANO_COME_ERRORI and r["esito"] == "errore":
                self.errori.append(f"controlli: {r['nome']}: {r['dettaglio']}")


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
