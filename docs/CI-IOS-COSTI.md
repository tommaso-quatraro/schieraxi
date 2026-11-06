# Quanto costano le corse iOS sui Mac di GitHub (issue #264)

I Mac di GitHub gratuiti sono 5 alla volta per tutto il repository. Quando sono tutti occupati, i job iOS aspettano in fila e
rallentano l'unione di tutte le pull request. Qui: cosa costa ogni corsa, cosa è stato cambiato per farle costare meno e cosa
è stato lasciato com'è, con i numeri misurati.

## Misura: 48 ore, dal 4 al 6 novembre 2026

Fonte: `gh run list` e `gh api .../jobs` su tutte le corse di `test.yml`, `ios.yml`, `ipa.yml` e `screenshot.yml`. 225 job Mac
eseguiti (i saltati non contano), 4515 minuti Mac, 29 pull request iOS unite (73 in tutto).

| Corsa | Quante | Minuti Mac | Durata media | Rosse / annullate | Per pull request iOS |
|---|---|---|---|---|---|
| A mano sul ramo (`ios.yml`) | 86 | 1846 | 21,5 | 28 / 10 | 2,3 corse, 50 min |
| `ios / test` della pull request (`test.yml`) | 50 | 1087 | 21,7 | 0 / 4 | 1,2 corse, 28 min |
| `ios / test` su `main` dopo l'unione (`prova-main`) | 27 | 627 | 23,2 | 1 / 0 | 0,9 corse, 22 min |
| Compila IPA (`ipa.yml`) | 32 | 136 | 4,3 | 0 / 0 | 1,1 corse, 5 min |
| Foto (`screenshot.yml`, app e widget) | 30 | 819 | 27,3 | 0 / 5 | fuori dal conto sotto |
| **Totale** | **225** | **4515** | | | **104 min per modifica tipica, foto escluse** |

Cosa dice la misura:
- **Le corse doppie sullo stesso codice sono già poche**: solo 3 commit in 48 ore hanno avuto due volte i test iOS. Il merito è del
  job `gia-verde` di `ios.yml` (il Mac non parte se una corsa riuscita ha già provato lo stesso albero di `ios/`, lo stesso `ios.yml` e
  gli stessi file esterni). Ha tenuto fermo il Mac 27 volte nei Controlli e 2 nelle corse a mano. Non può aiutare quando un'altra pull request
  unita nel frattempo ha cambiato `ios/`: l'albero è un altro e i test devono girare. Per questo la corsa su `main` dopo l'unione ha
  usato il Mac 27 volte a fronte di 29 pull request iOS unite.
- **Dentro una corsa** (21 minuti): scelta e accensione del simulatore circa 2, compilazione circa 6,5, test unitari circa 2,3,
  test di interfaccia 10,8 (30 test, di cui 14 in `FumoUITests` per 5 minuti).
- **In 23 delle 28 corse a mano rosse i test unitari erano rossi** (le altre 5: compilazione rotta o log senza righe d'errore) e
  l'interfaccia girava lo stesso per 11 minuti: circa 250 minuti Mac in 48 ore.
- Attesa in fila (dal job creato al job partito): media 5-8 minuti, massimo 44. Nelle ore piene sale a 1-2 ore.

## Cosa cambia con questa pull request

Tutti i controlli che c'erano restano: la pull request prova ancora compilazione, unitari e interfaccia prima dell'unione.

1. **Prima gli unitari, poi l'interfaccia** (`ios.yml`). Il Mac compila app e test una volta sola (`build-for-testing`), prova gli unitari
   (`test-without-building -only-testing:SchieraxiTests`) e, solo se sono verdi, l'interfaccia (`-only-testing:SchieraxiUITests`).
   Un unitario rosso ora costa circa 10 minuti invece di 21, e lo si vede prima. Se sono verdi entrambi, il lavoro è lo stesso di prima.
2. **Il simulatore si accende mentre si compila**. Prima il passo «Scegli il simulatore» aspettava l'accensione (da 1,9 a 2,4 minuti
   misurati); ora l'accensione parte e si aspetta solo prima dei test, quando ha già finito.
3. **Corsa a mano parziale**: `gh workflow run ios.yml --ref <ramo> -f parte=unitari` salta l'interfaccia (circa 10 minuti invece di 21).
   Non scrive il segno «verde» di `gia-verde`, quindi la corsa della pull request riprova tutto: nessun controllo si perde. Il valore
   predefinito è `tutti`, come prima. Va usata nelle prove a metà lavoro; l'ultima prova prima di aprire la pull request resta completa.
4. `COMPILER_INDEX_STORE_ENABLE=NO` nella compilazione dei test: niente indice per l'editor, che in CI non serve a nessuno.

### Stima prima / dopo (modello sui numeri misurati, non una nuova misura)

| Per una modifica iOS tipica | Minuti Mac |
|---|---|
| Prima (misurato) | 104 |
| Dopo, senza cambiare abitudini (1 + 2) | circa 90 (-13%) |
| Dopo, con `parte=unitari` nelle prove intermedie (3) | circa 83 (-20%) |
| Tutte le 48 ore, senza cambiare abitudini | da 4515 a circa 4020 (-11%) |

Come si controlla davvero: dopo l'unione, `gh run list --workflow ios.yml` e `gh api repos/<repo>/actions/runs/<id>/jobs` sui
passi «Compila ed esegui i test (1 di 3 …)»: la durata di compilazione, unitari e interfaccia si legge passo per passo.

## Cosa NON è stato fatto, e perché

- **Non si annulla nessuna corsa a mano** (`workflow_dispatch`): i lanci a mano sono voluti. Il gruppo di concorrenza con annullamento
  c'era già solo per le pull request (`controlli-<numero>`) e resta così.
- **La corsa su `main` dopo l'unione non salta i Mac "superati"**. Con più unioni ravvicinate, solo l'ultima corsa su `main` sarebbe
  necessaria (27 corse, 627 minuti in 48 ore). Ma `cambi` confronta ogni corsa con l'ultima riuscita: una corsa saltata e segnata
  come riuscita lascerebbe senza prova le modifiche a `ios/` che contiene. Servirebbe un segno sulle corse "superate" che
  `cambi` sappia escludere, e un cambio ai test di `tests/test_workflow_main.py`. È la prossima mossa per risparmiare, ma è un cambio alla
  decisione `0008`: da fare con un'issue a parte e il parere del coordinatore.
- **Foto**: restano a mano e non sono state toccate. Dal conto: 30 job in 48 ore, 819 minuti (18%). Di questi, 26 job (668 minuti) sono
  partiti su rami di pull request e 4 su `main`: la regola è fotografare `main` dopo l'unione (eccezione: «Foto prima dell'unione»,
  una alla volta). Fotografare meno sui rami è il risparmio più grande che resta, ma è una regola di lavoro, non di workflow.
- **Compila IPA**: 4 minuti a corsa, il gruppo `ipa-<ramo>` tiene già una sola corsa in attesa. Non vale la pena.
- **Test di interfaccia in parallelo su più simulatori**: accorcerebbe il tempo di attesa ma non i minuti Mac (anzi, li aumenta), e rende
  i test meno stabili sui Mac con 3 core.
