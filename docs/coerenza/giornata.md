## Giornata: le forme (#299, dal 5/11/2026)
Decisione del proprietario: come su Leghe Fantacalcio si mostrano **tutti e due i numeri**, quello della lega e quello di Serie A.
I due numeri arrivano dal server in ogni risposta che parla di una giornata: `giornata` (Serie A) e `giornata_lega` (lega; `null`
per le stagioni passate e prima che la lega parta). Il testo lo costruisce **una sola funzione per piattaforma**, mai a mano:
web `nomeGiornata(lega, serieA)` in `fanta/web/app.js`; server `frasi.nome_giornata(serie_a, lega)` in `fanta/frasi.py`
(avvisi, Da fare, testo per i Comandi); iPhone `NomeGiornata` in `ios/Sources/Domain/TempiLega.swift` (app e widget), con le stesse forme.

| Forma | Quando | Italiano | Inglese |
|---|---|---|---|
| Intera | dove c'è spazio: testata, Oggi, Formazione, Diario, scheda, Confronto, avvisi, Da fare, testo e immagine da condividere | «Giornata 8 · 11ª di Serie A» | «Matchday 8 · Serie A matchday 11» |
| Corta | dove lo spazio è poco (widget piccoli, righe strette, cerchi della schermata di blocco) | «Giornata 8» e sotto, più piccolo, «11ª di Serie A»; solo «Giornata 8» come ultimo ripiego. Mai «G8» (nei widget: `ParoleWidget.formeGiornata`) | «Matchday 8» e sotto «Serie A matchday 11» |
| Solo Serie A | `giornata_lega` nullo (stagioni passate, prima che la lega parta) e dove si parla solo di Serie A | «11ª giornata di Serie A» | «Serie A matchday 11» |
| Colonna stretta | colonne del calendario e del grafico «Attesi e fatti» dei widget, sotto un titolo | «G11» | «G11» |

- VoiceOver e lettori di schermo leggono **sempre la forma intera** (o «11ª giornata di Serie A» per la colonna «G11»).
- Lega partita con la Serie A (`prima_giornata_lega` = 1): si scrivono tutti e due anche se uguali, «Giornata 8 · 8ª di Serie A».
- «ª» è il carattere dell'ordinale femminile (U+00AA), non una «a» piccola.
- Davanti all'8ª e all'11ª (ottava, undicesima) l'articolo perde la vocale: «l'11ª giornata di Serie A», «dall'8ª all'11ª»,
  «per l'11ª»; «la 1ª» e «la Giornata 8» restano. Una funzione per lato: web `elidiOrdinali`, server `frasi.elidi_ordinali`, iPhone `TempiLega.elidiOrdinali`.
- **In una frase** la forma intera va in testa, seguita dai due punti: «Giornata 8 · 11ª di Serie A: la formazione si chiude sab 31 14:50.»
  Così la frase resta grammaticale in ogni lingua e non nasce una terza forma.
- Se manca anche `giornata` (server vecchio) si scrive «Giornata 8»; se mancano tutti e due, niente.

Frasi esatte, schermata per schermata (italiano; l'inglese è in `fanta/web/testi.js` con le stesse chiavi):

| Dove | Testo |
|---|---|
| Testata (web) | «Giornata 8 · 11ª di Serie A» |
| Oggi, sopra il conto alla rovescia | «Giornata 8 · 11ª di Serie A»; dopo la scadenza sotto «Chiusa» c'è «La formazione si è chiusa sab 31 14:50» (senza numero: è scritto sopra) |
| Oggi, giornata finita (titolo del riepilogo) | «Giornata 7 · 10ª di Serie A: finita» |
| Oggi, prossima giornata | «Giornata 9 · 12ª di Serie A: la formazione si chiude sab 7 14:50.» |
| Formazione, intestazione | «Giornata 8 · 11ª di Serie A · modulo consigliato» (o «la tua scelta», «modulo scelto») |
| Formazione, giornata saltata | «Giornata 8 · 11ª di Serie A: è già iniziata. Questa è la formazione per la Giornata 9 · 12ª di Serie A.» |
| Testo da condividere, prima riga | «Giornata 8 · 11ª di Serie A · 3-4-3» (uguale nel testo per i Comandi, `GET /api/formazione/testo`) |
| Immagine da condividere | titolo «Giornata 8 · 11ª di Serie A · 3-4-3» (il carattere si rimpicciolisce se non ci sta); titolo della condivisione «Formazione · Giornata 8 · 11ª di Serie A» |
| Scheda del giocatore, prossima partita | «Giornata 8 · 11ª di Serie A · in casa contro Como · sab 31 20:45» |
| Confronto, titolo | «Chi schierare? Giornata 8 · 11ª di Serie A» |
| Diario, titolo di ogni giornata | «Giornata 8 · 11ª di Serie A»; stagione passata «11ª giornata di Serie A» (con la stagione accanto) |
| Diario, correggi | «Giornata 8 · 11ª di Serie A: tocca i giocatori che hai schierato. Servono 11 titolari.» |
| Diario, «Quando hai scelto diversamente» | «Giornata 8 · 11ª di Serie A: Rossi, Bianchi invece di Verdi, Neri» |
| Diario, «Quanto ci abbiamo preso» | righe «Giornata 8 · 11ª di Serie A · …»; «Calcolato su 5 giornate, dalla Giornata 4 · 7ª di Serie A alla Giornata 8 · 11ª di Serie A.»; sotto le barre del grafico solo il numero della lega |
| Da fare (testo del server) | «Giornata 7 · 10ª di Serie A: è finita, dimmi se hai schierato la consigliata.»; «È il momento di aste e scambi nella lega: se le rose sono cambiate, aggiornale prima della Giornata 12 · 15ª di Serie A.» |
| Widget (iPhone) | forma corta; nel widget piccolo solo «Giornata 8»; etichetta di VoiceOver con la forma intera |
| Calendario di Serie A | colonne «G11», lettori di schermo «11ª giornata di Serie A» |
| Scheda, grafico dei voti | al passaggio sul punto «11ª giornata di Serie A: 6,5» |
| Stato dei dati, probabili | «11ª giornata di Serie A» |
| Stato dei dati, registro delle giornate (giornate perse) | «9ª giornata di Serie A · 2026-27» (`sd.reg_giornata`) |
| Prova del modello (Diario) | «dalla 5ª alla 10ª giornata di Serie A» |

Avvisi sul telefono (testi del server, `fanta/frasi_avvisi.py`): i titoli non hanno più il numero, la forma intera sta in testa al testo.
- Cambi nelle probabili: titolo «SchieraXI · cambi nelle probabili», prima riga del testo «Giornata 8 · 11ª di Serie A».
- Un'ora prima: «Giornata 8 · 11ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 14:50).»
- Ultimi minuti: «Giornata 8 · 11ª di Serie A: la formazione si chiude alle 14:50. L'hai inserita su Leghe?»
- Titolare a rischio: «Hai già schierato, ma Rossi non è più sicuro come titolare. Giornata 8 · 11ª di Serie A: la formazione si chiude alle 14:50, controlla.»
- Riepilogo: titolo «SchieraXI · riepilogo della giornata»; testo «Giornata 7 · 10ª di Serie A: la formazione consigliata ha fatto circa 70,5 punti …» e «Prossima: Giornata 8 · 11ª di Serie A. La formazione si chiude 08/11 alle 14:50.»
- Formazione pronta: «Giornata 8 · 11ª di Serie A: la formazione è pronta. Apri l'app e controlla le probabili.»

Scelte già prese con la forma dell'iPhone (da portare sulla web): «INT @ MIL» nelle righe, «in trasferta contro», il
cognome senza iniziale sul campo, «Ho schierato la consigliata» nel Diario.
