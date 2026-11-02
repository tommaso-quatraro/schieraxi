"""Le frasi degli avvisi sul telefono, in italiano e in inglese (chiave -> (italiano, inglese)).

Le scrive il server (non l'app), nella lingua che l'utente ha scelto nelle impostazioni degli avvisi (`lingua`, predefinito italiano):
per questo l'inglese sta qui e non in `fanta/web/testi.js`. Le usa `fanta/frasi.py` (`Frase.in_lingua`); `notifiche.invia` sceglie la lingua.
Le chiavi cominciano per `n.`; i plurali sono `chiave.one` e `chiave.other` con il parametro `n`.
"""
from __future__ import annotations

NOTIFICHE: dict[str, tuple[str, str]] = {
    # ---- giocatori seguiti
    "n.t_osservato_libero": ("SchieraXI · un osservato è libero", "SchieraXI · a player you follow is free"),
    "n.osservato_libero": ("{nome} ({ruolo}): lasciato libero da {squadra}", "{nome} ({ruolo}): released by {squadra}"),
    # ---- cambi nelle probabili
    "n.t_cambi": ("SchieraXI · giornata {giornata}: cambi nelle probabili", "SchieraXI · matchday {giornata}: changes in the probable lineups"),
    "n.ora_infortunato": ("{nome}: ora infortunato", "{nome}: now injured"),
    "n.ora_squalificato": ("{nome}: ora squalificato", "{nome}: now suspended"),
    "n.torna_titolare": ("{nome}: torna disponibile (titolare)", "{nome}: back and available (starter)"),
    "n.torna_panchina": ("{nome}: torna disponibile (panchina)", "{nome}: back and available (bench)"),
    "n.titolare_a_panchina": ("{nome}: dalla formazione titolare alla panchina", "{nome}: from the starting lineup to the bench"),
    "n.ora_titolare": ("{nome}: ora titolare", "{nome}: now a starter"),
    "n.non_convocato": ("{nome}: non è più tra i convocati previsti", "{nome}: no longer among the expected squad"),
    "n.ora_ballottaggio": ("{nome}: ora in ballottaggio per partire titolare", "{nome}: now contested for a starting spot"),
    "n.ora_titolare_sicuro": ("{nome}: ora probabile titolare", "{nome}: now a likely starter"),
    "n.ora_dubbio": ("{nome}: ora in dubbio", "{nome}: now in doubt"),
    "n.diffidato": ("{nome}: diffidato (con un altro giallo salta la partita dopo)",
                    "{nome}: one yellow card from a suspension (another one and they miss the next match)"),
    "n.osservato_riga": ("★ {riga}", "★ {riga}"),
    "n.formazione_aggiornata": ("Formazione consigliata aggiornata ({modulo}): entra {entrano}, esce {escono}",
                                "Recommended lineup updated ({modulo}): in {entrano}, out {escono}"),
    "n.riga_consiglio": ("{riga} {consiglio}", "{riga} {consiglio}"),
    "n.altre_novita": ("…e altre {n} novità", "…and {n} more updates"),
    # ---- cambio pronto
    "n.t_cambio_pronto": ("SchieraXI · cambio pronto", "SchieraXI · substitution ready"),
    "n.tuo_infortunato": ("Il tuo {nome} è infortunato.", "Your {nome} is injured."),
    "n.tuo_squalificato": ("Il tuo {nome} è squalificato.", "Your {nome} is suspended."),
    "n.tuo_panchina": ("Il tuo {nome} parte dalla panchina.", "Your {nome} starts on the bench."),
    "n.meglio": ("Meglio {alt}.", "Better {alt}."),
    "n.meglio_guadagno": ("Meglio {alt} (+{punti} punti attesi).", "Better {alt} (+{punti} expected points)."),
    "n.frase_consiglio": ("{frase} {consiglio}", "{frase} {consiglio}"),
    # ---- reparto scoperto (il testo viene da copertura.py, già nella lingua)
    "n.t_reparto_scoperto": ("SchieraXI · un reparto della rosa è scoperto", "SchieraXI · a position in your roster is uncovered"),
    "n.t_reparto_rischio": ("SchieraXI · un reparto della rosa è a rischio", "SchieraXI · a position in your roster is at risk"),
    # ---- promemoria prima della scadenza
    "n.t_titolare_rischio": ("SchieraXI · un tuo titolare è a rischio", "SchieraXI · one of your starters is at risk"),
    "n.rischio.one": ("Hai già schierato, ma {nomi} non è più sicuro come titolare. La formazione della giornata {giornata} si chiude alle {ora}: controlla.",
                      "You have already fielded a lineup, but {nomi} is no longer a sure starter. The lineup for matchday {giornata} closes at {ora}: check it."),
    "n.rischio.other": ("Hai già schierato, ma {nomi} non sono più sicuri come titolare. La formazione della giornata {giornata} si chiude alle {ora}: controlla.",
                        "You have already fielded a lineup, but {nomi} are no longer sure starters. The lineup for matchday {giornata} closes at {ora}: check it."),
    "n.t_un_ora": ("SchieraXI · formazione tra un'ora", "SchieraXI · lineup in one hour"),
    "n.tra_un_ora": ("La formazione della giornata {giornata} si chiude tra circa un'ora (scadenza alle {ora}).",
                     "The lineup for matchday {giornata} closes in about an hour (deadline at {ora})."),
    "n.consigliato": ("Consigliato: {modulo}, {punti} punti attesi.", "Recommended: {modulo}, {punti} expected points."),
    "n.da_controllare": ("Da controllare: {nomi}.", "To check: {nomi}."),
    "n.t_ultimi_minuti": ("SchieraXI · ultimi minuti per la formazione", "SchieraXI · last minutes for the lineup"),
    "n.ultimi_minuti": ("Ultimi minuti: la formazione della giornata {giornata} si chiude alle {ora}. L'hai inserita su Leghe?",
                        "Last minutes: the lineup for matchday {giornata} closes at {ora}. Have you entered it on Leghe?"),
    # ---- «cambia la formazione»
    "n.t_cambia": ("SchieraXI · cambia la formazione", "SchieraXI · change your lineup"),
    "n.t_cambia_consigliata": ("SchieraXI · cambia la formazione consigliata", "SchieraXI · the recommended lineup has changed"),
    "n.m_infortunato": ("{nome} è infortunato", "{nome} is injured"),
    "n.m_squalificato": ("{nome} è squalificato", "{nome} is suspended"),
    "n.m_panchina": ("{nome} parte dalla panchina", "{nome} starts on the bench"),
    "n.m_non_citato": ("{nome} non è tra i convocati", "{nome} is not among the squad"),
    "n.m_dubbio": ("{nome} è in dubbio", "{nome} is in doubt"),
    "n.elenco_altri.one": ("{lista} e un altro", "{lista} and one more"),
    "n.elenco_altri.other": ("{lista} e altri {n}", "{lista} and {n} more"),
    "n.metti": ("{motivi}: metti {entrano}", "{motivi}: field {entrano}"),
    "n.conviene": ("Con le ultime probabili conviene {entrano}", "With the latest probable lineups it is better to field {entrano}"),
    "n.conviene_al_posto": ("Con le ultime probabili conviene {entrano} al posto di {senza}",
                            "With the latest probable lineups it is better to field {entrano} instead of {senza}"),
    "n.altra_formazione": ("Con le ultime probabili conviene un'altra formazione", "With the latest probable lineups another lineup is better"),
    "n.e_passa": ("{frase} e passa al {modulo}", "{frase} and switch to {modulo}"),
    "n.testo_scadenza": ("{frase} (+{punti} punti attesi). La formazione si chiude alle {ora}.",
                         "{frase} (+{punti} expected points). The lineup closes at {ora}."),
    # ---- riepilogo di giornata
    "n.t_riepilogo": ("SchieraXI · riepilogo giornata {giornata}", "SchieraXI · matchday {giornata} recap"),
    "n.riepilogo": ("Giornata {giornata}: {fonte} ha fatto circa {punti} punti (il modello ne aspettava {attesi}). Il massimo possibile con la tua rosa era {massimo}.",
                    "Matchday {giornata}: {fonte} scored about {punti} points (the model expected {attesi}). The maximum possible with your roster was {massimo}."),
    "n.fonte_scelta": ("la tua scelta salvata", "your saved choice"),
    "n.fonte_consigliata": ("la formazione consigliata", "the recommended lineup"),
    "n.migliori": ("Migliori: {elenco}.", "Best: {elenco}."),
    "n.nome_voto": ("{nome} {voto}", "{nome} {voto}"),
    "n.senza_voto": ("Senza voto: {nomi}.", "No rating: {nomi}."),
    "n.prossima": ("Prossima: giornata {giornata}, la formazione si chiude {data} alle {ora}.",
                   "Next: matchday {giornata}, the lineup closes {data} at {ora}."),
    # ---- formazione pronta e prova
    "n.pronta": ("Giornata {giornata}: la formazione è pronta. Apri l'app e controlla le probabili.",
                 "Matchday {giornata}: the lineup is ready. Open the app and check the probable lineups."),
    "n.t_prova": ("SchieraXI · prova", "SchieraXI · test"),
    "n.prova": ("Se leggi questo, gli avvisi funzionano.", "If you can read this, the alerts work."),
}
