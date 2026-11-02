# axe-core (strumento di collaudo, non fa parte dell'app)

`axe.min.js` è axe-core di Deque Systems, il motore standard per i controlli di accessibilità (licenza MPL-2.0, testo in
`LICENSE-MPL-2.0.txt`). Serve solo ai collaudi nel browser: non va mai dentro `fanta/web/` né nel sito.

- Versione: **4.14.0** (pacchetto npm `axe-core`, file `axe.min.js` senza modifiche).
- SHA-256 di `axe.min.js`: `20c09fe157a8a34a30e241aaa1fcdade657734f08ab379ecfbeb7d45cc46e878`
- SHA-512 del pacchetto npm (`dist.integrity`): `9WTZxEjsZ7b13TH8JPmbV2z8CHbl80/2hm3XPEG4JgNdQLK81IBRXmSxHfMAOkSqQeRxT/0dwNDz2GOm3zzpcQ==`

Controllo: `sha256sum tests/strumenti/axe/axe.min.js` (Linux, Git Bash) o `Get-FileHash -Algorithm SHA256 tests\strumenti\axe\axe.min.js` (PowerShell).

Uso: aprire la schermata, iniettare il file nella pagina (`page.add_script_tag(path=...)` in Playwright, o il contenuto con
`browser_evaluate`), poi `await axe.run()` e leggere `violations` (prima quelle `critical` e `serious`).
Per cambiare versione: scaricare il pacchetto nuovo, ricontrollare l'hash e aggiornare questo file nella stessa PR.
