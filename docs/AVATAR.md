# Avatar illustrati di SchieraXI: specifica (versione 3)

Ogni calciatore ha un **volto disegnato**, generato dal suo codice (`id`, il codice calciatore di Fantacalcio.it).
Stesso `id` (e stessi tratti) = stesso volto, sempre e su ogni piattaforma (web, iOS, Android). Nessuna foto: solo disegni.
**Dal 31/10/2026 (decisione dell'utente) il volto può avere un'aria del giocatore, tipo caricatura molto semplice: carnagione, colore e tipo dei capelli, barba (sezione 8).**
Chi non ha tratti (per esempio ogni giocatore nuovo, o chiunque nel progetto pubblico) ha la **carnagione neutra fissa**, mai una a caso. Tutto il resto
(forma del viso, occhi, naso, bocca, espressione, ombre, maglia, sfondo) viene sempre dal seme e non dice nulla della persona vera.
I limiti (cosa non fare mai): niente tratti del viso, età, nazionalità o segni particolari presi da persone vere, nessuna regola per nome; chi cambia gli avatar li rispetta.
Implementazione di riferimento: `fanta/web/avatar.js`. Test: `tests/test_avatar.py` (rifà l'estrazione in Python e controlla i vettori di questo file).
Pagina di prova con 120 volti: `prove/avatar_griglia.html` (aprirla dal disco: `?da=N` primo codice, `?g=N` colonne, `?t=scuro`).

Chi porta il generatore (SwiftUI, Compose) deve riprodurre **gli stessi indici** (sezioni 1 e 2, vettori in sezione 7) e lo stesso disegno (sezioni 3-6).
Il disegno è fatto solo di primitive semplici (cerchi, ellissi, rettangoli arrotondati, path brevi) su una **griglia 100x100**, origine in alto a sinistra, y verso il basso.

## 1. Numeri casuali

- Generatore **mulberry32** a 32 bit. Stato `a` (uint32). Ogni estrazione:
  ```
  a = (a + 0x6D2B79F5) mod 2^32
  t = a
  t = imul(t XOR (t >> 15), t OR 1)          // imul = prodotto modulo 2^32
  t = t XOR (t + imul(t XOR (t >> 7), t OR 61))   // la somma è modulo 2^32
  risultato = ((t XOR (t >> 14)) come uint32) / 4294967296      // numero in [0, 1)
  ```
- **Seme**: `seme = (imul(id, 0x9E3779B1) XOR 0xA5C1D1CE)` come uint32. `id` deve essere un intero tra 0 e 4294967295; altrimenti si usa 0.
- **Scelta con pesi** (pesi interi, somma 100): `n = floor(estrazione * somma_pesi)` (esatto in `Double`), poi si scorrono le parti sommando i pesi:
  la prima parte con `n < somma_parziale` è quella scelta.
- **Ordine fisso delle estrazioni**, una per parte, sempre tutte e dieci (anche quando poi la parte non si vede):
  `pelle, forma, acconciatura, colore, barba, sopracciglia, occhi, bocca, accessorio, orecchie`.
  **La pelle si estrae sempre (così l'ordine delle altre non cambia) ma il valore estratto si scarta**: la carnagione finale è quella dei tratti (`p`, sezione 8) oppure, senza tratti, la neutra `2` (`#e0a97e`).

## 2. Parti, indici e pesi

| Parte | Indici (peso %) |
|---|---|
| pelle (7) | 0 `#f6d5bd` (20), 1 `#efc2a0` (26), 2 `#e0a97e` (24, **la neutra**), 3 `#c98e5f` (12), 4 `#a56a43` (8), 5 `#7a4a2d` (6), 6 `#5a3722` (4). I pesi servono solo all'estrazione scartata; la pelle vera viene da `p` o è la 2 |
| forma viso (3) | 0 ovale (50), 1 larga (25), 2 stretta (25) |
| acconciatura (12) | 0 rasata (10), 1 corta (16), 2 riccia (8), 3 afro (5), 4 lunga (7), 5 chignon (6), 6 riga di lato (12), 7 cresta bassa (7), 8 ondulata (8), 9 calvo (5), 10 pettinata indietro (9), 11 frangia (7) |
| colore capelli (8) | 0 nero `#17171b` (24), 1 castano scuro `#3a2618` (22), 2 castano `#6a4328` (18), 3 biondo scuro `#a9793a` (10), 4 biondo `#d9b45a` (8), 5 ramato `#a8441f` (6), 6 grigio `#9aa0a6` (4), 7 platino `#e8dcc0` (8) |
| barba (5) | 0 nessuna (40), 1 ombra (20), 2 corta (16), 3 piena (14), 4 baffi (10) |
| sopracciglia (3) | 0 sottili (40), 1 spesse (30), 2 inclinate (30) |
| occhi (3) | 0 tondi (40), 1 allungati (30), 2 grandi con bianco (30) |
| bocca (4) | 0 neutra (30), 1 sorriso leggero (35), 2 seria (20), 3 sorriso con denti (15) |
| accessorio (4) | 0 nessuno (78), 1 fascia (8), 2 orecchino (8), 3 cerotto (6) |
| orecchie (2) | 0 piccole (70), 1 grandi (30) |

Combinazioni delle estrazioni: 7 x 3 x 12 x 8 x 5 x 3 x 3 x 4 x 4 x 2 = 2.903.040. Senza tratti la pelle è fissa: 414.720 volti di base e, su 3000 codici consecutivi, 2928 volti distinti (le ripetizioni sono rare e dovute ai pesi; i dettagli della sezione 9 le separano ancora).

**Regole di coerenza** (si applicano dopo le dieci estrazioni; cambiano solo l'accessorio):
- R1: se acconciatura è 3 (afro), 4 (lunga) o 8 (ondulata) e accessorio è 2 (orecchino) -> accessorio = 0.
- R2: se acconciatura è 7 (cresta bassa) e accessorio è 1 (fascia) -> accessorio = 0.

## 3. Colori derivati (aritmetica intera, uguale ovunque)

- `scuri(c, k)`: ogni canale `floor(canale * (1 - k) + 0.5)`. `misce(a, b, t)`: ogni canale `floor(a*(1-t) + b*t + 0.5)`.
- Luminanza `lum(c)`: WCAG (canali sRGB linearizzati, pesi 0,2126 / 0,7152 / 0,0722).
- `ombra = scuri(pelle, 0.14)` (collo e scollo); `capScuro = scuri(capelli, 0.3)` (dettagli dei capelli); sopracciglia `scuri(capelli, 0.2)`; naso `scuri(pelle, 0.22)`.
- Bocca: se pelle >= 4 `misce(pelle, #f0b8a8, 0.55)`, altrimenti `scuri(pelle, 0.45)`.
- **Sfondo** (cerchio centro (50,50) raggio 50, sfumatura lineare da in alto a sinistra a in basso a destra) dai colori della squadra `c1`, `c2` (tabella `COLORI_SQUADRA` in `app.js`; senza squadra `#6b7280` e `#e5e7eb`):
  `L = lum(c1)`. Se L > 0.25: `[scuri(c1,.55), scuri(c1,.3)]`; se L < 0.04: `[misce(c1,#fff,.3), misce(c1,#fff,.12)]`; altrimenti `[scuri(c1,.5), scuri(c1,.25)]`.
  Colore di partenza = `misce(primo, c2, 0.22)`, di arrivo = il secondo.
- **Maglia**: `c1` con colletto `c2`. **Portieri** (ruolo P): maglia grigia neutra `#8d99a8`, colletto `#1f2937`, guanti (vedi sotto). Lo stesso id con ruolo P cambia solo maglia e guanti, non il volto.

## 4. Ordine di disegno (dal fondo)

1. Sfondo (cerchio con sfumatura).
2. Capelli **dietro** (se l'acconciatura li ha).
3. Collo: rettangolo `x42 y58 w16 h26 rx6`, colore `ombra`.
4. Maglia: path `M10 100 C12 84 28 77 50 77 S88 84 90 100 Z`, poi lo scollo (pelle `ombra`) `M41 77 Q50 87 59 77 Z`, poi il colletto `M37 77.5 Q50 92 63 77.5 L59 76.5 Q50 85 41 76.5 Z`.
5. Solo portieri, due guanti: rettangoli `x18 y81` e `x66 y81`, `w16 h18 rx6`, riempimento `#d4f34a`, bordo `#1f2937` 1.2; dita: due linee verticali `#1f2937` 1 a `x+5.3` e `x+10.7` da y87 a y93.
6. Orecchie: ellissi a `(50 - rx, 44)` e `(50 + rx, 44)` con raggi dalla tabella orecchie (piccole 3.2x4.6, grandi 4.4x6), colore pelle.
7. Viso: ellisse centro (50,42), raggi (rx, ry) per forma: ovale (18,21), larga (20,20), stretta (16,22).
8. Barba (sezione 5), **ritagliata dentro l'ellisse del viso** (clip). Ombra, corta, piena.
9. Naso: `M49.5 46.5 Q47.5 51.5 51 52`, linea 1.6 tonda, senza riempimento.
10. Occhi a x 42.5 e 57.5, y 43 (sezione 6). Sopracciglia, bocca.
11. Baffi (barba 4), cerotto (accessorio 3).
12. Capelli **davanti**.
13. Fascia (accessorio 1) e orecchino (accessorio 2).

## 5. Capelli e barba

`c` = colore capelli, `s` = capScuro. Tutti i riempimenti pieni, senza bordo salvo dove scritto. `CAP` = `M30.5 43 C29.5 26 40 19 50 19 S70.5 26 69.5 43 C67 36 62 33.5 50 33.5 S33 36 30.5 43 Z`.

| # | Acconciatura | Dietro | Davanti |
|---|---|---|---|
| 0 | rasata | - | `M32.5 40 C32.5 28 41 22 50 22 S67.5 28 67.5 40 C65 35 59 32 50 32 S35 35 32.5 40 Z` opacità .8 |
| 1 | corta | - | `CAP` |
| 2 | riccia | cerchi (cx,cy,r): (32,38,6.5) (68,38,6.5) (36,28,8) (50,22,9) (64,28,8) | `CAP` + cerchi (37,33,3.6) (44,32,3.6) (51,32,3.6) (58,32,3.6) (64,33,3.6) |
| 3 | afro | cerchio (50,33) r26 | `CAP` |
| 4 | lunga | `M29 38 C27 22 38 17 50 17 S73 22 71 38 L74 70 Q74 80 66 82 H34 Q26 80 26 70 Z` | `M31 44 C30 27 40 19 50 19 S70 27 69 44 C67 37 62 31 54 30 C46 35 38 36 31 44 Z` |
| 5 | chignon | cerchio (50,14) r7.5 | `CAP` |
| 6 | riga di lato | - | `M30.5 43 C29 26 40 19 50 19 S70 26 69.5 40 C66 33 58 30 44 33 C38 35 34 38 30.5 43 Z` + linea `s` 1.2 tonda `M44 32.4 Q41 27 40 22` |
| 7 | cresta bassa | - | la forma della rasata con opacità .4 + cresta `M43.5 31 C43 22 46 16 50 16 S57 22 56.5 31 C54 29.5 46 29.5 43.5 31 Z` |
| 8 | ondulata | ellisse (50,36) r(22,21) + cerchi (28,52,7) (72,52,7) (26,62,5.5) (74,62,5.5) | `M30.5 43 C29 26 40 19 50 19 S71 26 69.5 43 C68 38 66 34 61 33 C58 36 54 31 50 33 C46 36 42 31 39 33 C34 34 32 38 30.5 43 Z` |
| 9 | calvo | - | - |
| 10 | pettinata indietro | - | `M30.5 41 C29.5 25 40 18.5 50 18.5 S70.5 25 69.5 41 C67 33 60 28 50 28 S33 33 30.5 41 Z` + linee `s` 1 tonde `M40 29 Q42 22 46 19.5 M50 28 V19.5 M60 29 Q58 22 54 19.5` |
| 11 | frangia | - | `M30.5 43 C29.5 26 40 19 50 19 S70.5 26 69.5 43 L67 33 Q63 34.5 59 33 Q54 35 50 33 Q45 35 41 33 Q37 34.5 33 33 Z` |

Barba (colore `c`, ritagliata nell'ellisse del viso della forma scelta):
- 0 nessuna.
- 1 ombra: `M30 44 Q50 56 70 44 V70 H30 Z`, opacità .25.
- 2 corta: `M30 44 H33.5 Q35 56 44 57.5 H56 Q65 56 66.5 44 H70 V70 H30 Z`, poi ellisse "bocca libera" in colore pelle centro (50,57.5) raggi (7.5, 3.6) (dentro il clip).
- 3 piena: `M30 40 H33 Q35 50 42 51.5 Q50 49.5 58 51.5 Q65 50 67 40 H70 V70 H30 Z`, poi ellisse pelle (50,57.5) raggi (8, 4).
- 4 baffi (non ritagliati, dopo la bocca): `M42 54.5 Q46 51.5 50 54 Q54 51.5 58 54.5 Q54 57.2 50 55.6 Q46 57.2 42 54.5 Z`.

## 6. Occhi, sopracciglia, bocca, accessori

- Occhi (x = 42.5 e 57.5, y = 43): 0 cerchio r1.9 `#1d1d22`; 1 ellisse (2.6, 1.5) `#1d1d22`; 2 ellisse bianca (3.3, 2.4) + cerchio r1.6 `#2a1d14`.
  Con pelle >= 5 e occhi 0 o 1 sotto l'occhio va un'ellisse `#f3ede4` raggi (3.1, 2.1) (altrimenti sparirebbero).
- Sopracciglia (linea tonda, colore `scuri(capelli, 0.2)`): 0 `M37.5 37.5 H47` e `M53 37.5 H62.5` spessore 2.2; 1 stesse linee spessore 3.4;
  2 `M37.5 36.5 L47 38.5` e `M53 38.5 L62.5 36.5` spessore 2.4.
- Bocca (colore dalla sezione 3, linea tonda): 0 `M44.5 57.5 H55.5` spessore 2; 1 `M44 56 Q50 61 56 56` spessore 2; 2 `M45.5 58 H54.5` spessore 2.4;
  3 `M44 56 Q50 63.5 56 56 Z` riempita di bianco, bordo spessore 1.6.
- Accessori: 1 fascia `M31 33 Q50 27 69 33 V37 Q50 31 31 37 Z` nel colore `c2` della squadra, bordo `scuri(c2, .35)` .8; 2 orecchino: cerchio r1.9 a `(50 - rx, 50.5)` `#e9c24a`, bordo `#a8841c` .6;
  3 cerotto: gruppo ruotato di -20 gradi attorno a (63.5, 52): rettangolo `x59 y50 w9 h4 rx1.2` `#f1e3c8` bordo `#c9b48e` .6 e due puntini r.5 a (62,52) e (65,52).

## 7. Vettori di prova

Ordine: `pelle forma acconciatura colore barba sopracciglia occhi bocca accessorio orecchie` (indici finali, dopo le regole di coerenza). Le righe `VETTORE` sono lette dai test.

```
VETTORE 1: 2 0 10 0 3 1 0 1 0 1
VETTORE 2: 2 0 0 1 4 0 0 1 0 0
VETTORE 3: 2 2 7 7 0 0 0 0 0 0
VETTORE 100: 2 2 2 7 3 0 1 0 1 1
VETTORE 4567: 2 0 0 7 0 2 2 0 0 0
VETTORE 7627: 2 0 4 1 2 1 2 0 0 0
```
(Senza tratti: il primo numero è sempre 2, la carnagione neutra. Prima del 31/10/2026 era la pelle estratta dal seme: 5 3 0 1 2 0 per questi sei codici.)

Regole di coerenza (estratti grezzi -> finali; cambia solo l'accessorio, penultimo numero):
```
COERENZA 140: 2 2 4 3 1 2 0 1 2 1 -> 2 2 4 3 1 2 0 1 0 1
COERENZA 170: 2 2 7 7 1 1 0 1 1 0 -> 2 2 7 7 1 1 0 1 0 0
```

Primi numeri del generatore (per provare solo mulberry32, con il **seme** scritto qui, non con un id):
```
MULBERRY 12345: 0.9797282678 0.3067522645 0.4842054215
MULBERRY 0: 0.2664292087 0.0003297457
```
(confronto con 10 cifre decimali.)

## 8. Tratti del giocatore (contratto versione 3, facoltativi)

Dal 31/10/2026 il volto può seguire il giocatore in cinque cose grossolane: **carnagione, colore dei capelli, famiglia di acconciatura, barba sì/no, barba folta**.
La decisione è dell'utente: i volti devono somigliare di più ai giocatori veri, in modo semplice, tipo caricatura. Restano vietati i tratti del viso, l'età, la nazionalità,
i segni particolari e ogni regola per nome; la forma esatta di acconciatura e barba viene dal seme.
I tratti sono pochi numeri per giocatore, salvati in `fanta/avatar_tratti.json` (nessuna foto serve a runtime, nessuna foto va in git). **Il progetto pubblico non ha né quel file né lo script che lo ricalcola**:
lì ogni volto ha la carnagione neutra (sezione 1) e il resto dal seme.
I tratti sono approssimativi (barba e carnagione dipendono dalla luce della foto): servono a dare un'aria, non a descrivere con precisione. Chi non li ha (giocatori senza ritaglio) ha la carnagione neutra.

**Dove arrivano**: `GET /api/avatar` -> `{"versione": 3, "tratti": {"<id>": {...}}}` (tutti insieme, da scaricare una volta); il campo `avatar` con gli stessi tratti
c'è anche in ogni elemento di `GET /api/giocatori` e nella scheda `GET /api/giocatore/{id}` (solo per chi li ha).

**Formato** (ogni campo è facoltativo; un campo mancante o non valido si ignora): `p` carnagione 0-6 (indice di "pelle"; il server oggi manda 1-6, a grana grossa),
`c` colore capelli 0-7 (indice di "colore capelli"), `a` famiglia di acconciatura, `b` barba 0 (no) o 1 (sì), `f` barba folta 0 o 1 (conta solo con `b` = 1).
Famiglie: `R` rasati o calvi = {0, 9}; `C` corti = {1, 6, 7, 10, 11}; `L` lunghi = {4, 5, 8}; `I` ricci = {2, 3}.

**Algoritmo** (si parte SEMPRE dalle dieci estrazioni della sezione 1, poi si fanno due estrazioni in più, `u11` e `u12`, anche senza tratti):
0. pelle = `p` se c'è, altrimenti 2 (neutra). L'estrazione della pelle si scarta sempre.
1. se c'è `c`: colore = c.
2. se c'è `a` e l'acconciatura estratta NON è nella famiglia: si sceglie tra i membri della famiglia con i pesi dell'acconciatura (sezione 2) usando `n = floor(u11 * somma_pesi)`.
3. se `b` = 0: barba = 0. Se `b` = 1 e la barba estratta è 0 o 1 (nessuna, ombra): si sceglie tra 2, 3, 4 con pesi 16, 14, 10 usando `n = floor(u12 * 40)`.
3b. (dopo il punto 3) se `b` = 1 e `f` = 1: barba = 3 (piena). Se `b` = 1 e `f` = 0 e la barba è 3: si sceglie tra 2 e 4 con pesi 16, 10 usando `n = floor(u12 * 26)`.
4. poi le regole di coerenza R1 e R2 (sezione 2) sui valori finali.

**Compatibilità**: un client della versione 2 (ignora `p` e `f`) continua a funzionare ma disegna la pelle dal seme: va aggiornato per avere gli stessi volti. Le estrazioni e l'ordine non cambiano; cambia solo il significato
del primo indice (la pelle) senza tratti. Il disegno (sezioni 3-6) non cambia.

Vettori (stesso ordine della sezione 7; i tratti sono JSON compatto):
```
VETTORE2 1 {"p":4,"c":3,"a":"L","b":1}: 4 0 4 3 3 1 0 1 0 1
VETTORE2 2 {"c":0,"a":"R","b":0}: 2 0 0 0 0 0 0 1 0 0
VETTORE2 3 {"p":1,"c":5,"a":"C","b":1,"f":1}: 1 2 7 5 3 0 0 0 0 0
VETTORE2 100 {"a":"I","b":1,"f":0}: 2 2 2 7 2 0 1 0 1 1
VETTORE2 4567 {"p":6,"c":6}: 6 0 0 6 0 2 2 0 0 0
VETTORE2 7627 {"c":9,"a":"X"}: 2 0 4 1 2 1 2 0 0 0
VETTORE2 1 {"b":1,"f":0}: 2 0 10 0 4 1 0 1 0 1
```
(il 7627 ha campi non validi: vale come senza tratti; il 3 mostra la barba folta forzata a piena; il 100 e l'ultimo mostrano la barba non folta che sposta una piena su baffi o corta.)

## 9. Versione 3: più dettagli, tutti dal seme

Dopo `u11` e `u12` si fanno **altre nove estrazioni** con la stessa scelta a pesi (sezione 1), in questo ordine fisso, sempre tutte e nove. I tratti del giocatore (sezione 8) NON le toccano.
Le dieci estrazioni della sezione 1, `u11` e `u12` e i vettori `VETTORE` e `VETTORE2` restano identici: un client che non conosce la versione 3 funziona come prima, senza i dettagli nuovi.

| Parte | Indici (peso %) |
|---|---|
| espressione | 0 normale (52), 1 sorriso largo con denti (20), 2 concentrato (12), 3 urlo (8), 4 occhiolino (8) |
| ritocco capelli | 0 nessuno (50), 1 riflessi chiari (28), 2 ombra alle tempie (22) |
| guance | 0 nessuna (62), 1 colorite (38) |
| rughe | 0 nessuna (84), 1 leggere ai lati della bocca (16) |
| naso | 0 quello di sempre (50), 1 tondo con narici (28), 2 lungo e dritto (22) |
| sfondo | 0 liscio (28), 1 strisce diagonali (24), 2 cerchi concentrici (18), 3 scudetto neutro (16), 4 raggi (14) |
| maglia | 0 liscia (40), 1 strisce verticali (22), 2 fascia sul petto (20), 3 bordo maniche (18) |
| colletto | 0 tondo (55), 1 a V (25), 2 polo con bottone (20) |
| spalle | 0 normali (60), 1 larghe (40) |

Disegno (griglia 100x100, come sempre; i numeri esatti sono in `fanta/web/avatar.js`, che è l'implementazione di riferimento):
- **Espressione**: 1 sostituisce la bocca con un sorriso aperto bianco `M42.5 55.5 Q50 65.5 57.5 55.5 Z`; 2 sopracciglia inclinate verso il naso (spessore 2.8) e bocca stretta `M46 58.5 H54`;
  3 occhi chiusi ad arco, sopracciglia alzate e bocca aperta (ellisse scura (50,59) raggi (5,5.6) con lingua rosa); 4 occhio destro chiuso ad arco e sorriso leggero. Con 0 non cambia niente.
- **Ombre e luci**: un'ellisse del viso con sfumatura orizzontale (luce a sinistra, ombra a destra), ombra sotto la frangia e sotto il mento (dentro l'ellisse del viso, nero opacità .1 e .09),
  ombra sotto il mento sul collo (rettangolo nero opacità .16), sfumatura verticale sulla maglia (bianco .12 in alto, nero .24 in basso).
- **Ritocchi dei capelli** (non su rasata, calvo, cresta bassa): 1 due linee chiare in alto; 2 due ombre alle tempie con `capScuro` opacità .5.
- **Sfondo**: i motivi sono disegnati nel colore `c2` della squadra con opacità .1-.16, dentro il cerchio. Lo scudetto è una forma neutra, non lo stemma di nessun club.
- **Maglia**: le varianti 1-3 usano `c2` (strisce con opacità .3, fascia, bordi con .55). I portieri hanno sempre la maglia grigia senza varianti.
- **Numero** (facoltativo, `numero` 1-99 passato da chi disegna, mai ricavato dal server): scritto in `col` sulla maglia, centro (50, 97.5), 9 di corpo, grassetto. Fuori da 1-99 non si disegna.
  È un fatto pubblico mostrato come testo, non il disegno di una maglia ufficiale.

Vettori della versione 3 (stesso ordine della tabella; le righe sono lette dai test):
```
VETTORE3 1: 2 1 0 0 1 2 3 2 0
VETTORE3 2: 2 2 0 0 2 3 0 0 0
VETTORE3 3: 0 1 1 0 1 2 1 1 0
VETTORE3 100: 0 1 0 0 1 2 0 0 1
VETTORE3 4567: 0 0 0 0 2 3 0 0 0
VETTORE3 7627: 1 2 0 0 0 0 3 0 1
```
Ordine di disegno della versione 3 (sostituisce la sezione 4 dove diverso): sfondo, motivo, capelli dietro, collo, ombra del collo, maglia (forma delle spalle), disegno della maglia ritagliato nella maglia,
sfumatura della maglia, colletto, numero, guanti, orecchie, viso, sfumatura del viso, ombre e guance (ritagliate nel viso), barba, rughe, naso, occhi, sopracciglia, bocca, baffi, cerotto, capelli davanti, ritocchi dei capelli, fascia, orecchino.

**Per iOS e Android**: aggiungere le nove estrazioni dopo `u12` (con i vettori sopra) e i disegni; l'API (`/api/avatar`, campo `avatar`) non cambia. `numero` è facoltativo e oggi l'app non lo passa (non c'è nei dati).

## 10. Uso nell'interfaccia

- Web: `AvatarSchieraXI.svg(id, { ruolo, c1, c2, numero })` restituisce l'SVG (con `viewBox 0 0 100 100`, `aria-hidden`); `fanta/web/app.js` lo mette dentro `.avatar` (`role="img"`, `aria-label` = nome del giocatore).
- Il resto resta come prima: anello del ruolo o dell'indice e badge con il numero attorno al cerchio.
- Animazione d'ingresso breve con molla (scala da .86 a 1, circa .4 s); con "riduci movimento" solo dissolvenza.
- Dimensioni provate: 40 e 92 px (cerchio intero visibile, volto leggibile anche a 40).
