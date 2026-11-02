"""Legge un file .xlsx e stampa le sue celle come JSON. Gira SEMPRE in un processo separato (vedi importa_sicuro.py): se il file
è ostile o enorme muore questo processo, non il server. Non importa niente del pacchetto fanta: solo la libreria standard e openpyxl.

Uso:  python -I _excel_figlio.py FILE '{"fogli": 10, "righe": 1500, "colonne": 60, "cella": 200, "memoria": 1073741824, "cpu": 30}'
Uscita: 0 = ok (JSON su stdout), 3 = file non leggibile, 4 = troppa memoria, altro = fermato dai limiti.
"""
import json
import sys


def _testo(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def main() -> int:
    percorso, limiti = sys.argv[1], json.loads(sys.argv[2])
    try:
        import resource                                   # solo Linux: tetto di memoria e di tempo di calcolo
        resource.setrlimit(resource.RLIMIT_AS, (limiti["memoria"], limiti["memoria"]))
        resource.setrlimit(resource.RLIMIT_CPU, (limiti["cpu"], limiti["cpu"]))
    except (ImportError, ValueError, OSError):
        pass
    try:
        import openpyxl
        wb = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
        try:
            fogli = [(ws.title, [[_testo(v)[:limiti["cella"]] for v in r]
                                 for r in ws.iter_rows(max_row=limiti["righe"], max_col=limiti["colonne"], values_only=True)])
                     for ws in wb.worksheets[:limiti["fogli"]]]
        finally:
            wb.close()
    except MemoryError:
        return 4
    except Exception:                                     # noqa: BLE001 - XML rotto, zip rovinato...: per il chiamante è un file non leggibile
        return 3
    sys.stdout.write(json.dumps(fogli))
    return 0


if __name__ == "__main__":
    sys.exit(main())
