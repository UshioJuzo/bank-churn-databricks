"""
Strip identifying data from saved notebook outputs before committing.

    python tools/clean_outputs.py            report only, changes nothing
    python tools/clean_outputs.py --write    apply the replacements

Why this exists rather than relying on silencing the libraries: MLflow, Spark and
the SDK all print URLs and identifiers through their own logging setups, and each
release moves where. Silencing them is worth doing, but it is not a guarantee.
This script is the guarantee, because it works on the file that actually gets
committed.

It only touches cell OUTPUTS. Source code and markdown are never modified, so a
notebook cleaned here still runs identically.

What it replaces:

    workspace host       dbc-xxxx-xxxx.cloud.databricks.com  ->  <workspace>
    email addresses      someone@example.com                 ->  <user>
    MLflow run ids       32 hex characters                   ->  <run_id>
    local Windows paths  C:\\Users\\name\\...                  ->  <path>
    local POSIX paths    /home/name/... or /Users/name/...    ->  <path>
    bearer tokens        dapi...                             ->  <redacted>

It also drops interactive widget outputs. Progress bars from artifact downloads
are saved as widget state, and GitHub renders those as an empty "Loading widget"
box, which makes a perfectly good notebook look broken. They carry no result, so
removing them loses nothing.

Run it before every commit. It is idempotent: running it twice changes nothing
the second time.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Order matters: the token pattern has to run before the generic hex one, and
# the workspace host before anything that could match part of a URL.
REGLAS = [
    ("token",     re.compile(r"dapi[0-9a-fA-F]{16,}"),                    "<redacted>"),
    ("workspace", re.compile(r"(?:dbc-[0-9a-f]{4}-[0-9a-f]{4}|adb-\d{10,})"
                             r"\.(?:cloud|azuredatabricks|gcp)\.databricks\.com"), "<workspace>"),
    ("email",     re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}"),              "<user>"),
    ("run_id",    re.compile(r"\b[0-9a-f]{32}\b"),                        "<run_id>"),
    ("win_path",  re.compile(r"[A-Za-z]:\\\\?(?:Users|Andres)\\\\?[^\"\\s,)\\]]*"), "<path>"),
    ("posix_path", re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+/[^\"\\s,)\\]]*"),   "<path>"),
]


def limpiar_texto(texto: str, cuenta: dict) -> str:
    for nombre, patron, reemplazo in REGLAS:
        texto, n = patron.subn(reemplazo, texto)
        if n:
            cuenta[nombre] = cuenta.get(nombre, 0) + n
    return texto


WIDGET_MIME = "application/vnd.jupyter.widget-view+json"


def es_widget(salida: dict) -> bool:
    """True for an interactive widget output: a progress bar, typically."""
    return WIDGET_MIME in salida.get("data", {})


def limpiar_salida(salida: dict, cuenta: dict) -> dict:
    """Walk one output object, cleaning only the places text can hide."""
    tipo = salida.get("output_type")

    if tipo == "stream":
        salida["text"] = [limpiar_texto(t, cuenta) for t in salida.get("text", [])]

    elif tipo in ("execute_result", "display_data"):
        data = salida.get("data", {})
        for mime in list(data):
            # Images are base64 and cannot contain a readable identifier.
            if mime.startswith("image/"):
                continue
            valor = data[mime]
            if isinstance(valor, list):
                data[mime] = [limpiar_texto(t, cuenta) for t in valor]
            elif isinstance(valor, str):
                data[mime] = limpiar_texto(valor, cuenta)

    elif tipo == "error":
        salida["evalue"] = limpiar_texto(salida.get("evalue", ""), cuenta)
        salida["traceback"] = [limpiar_texto(t, cuenta) for t in salida.get("traceback", [])]

    return salida


def procesar(ruta: Path, escribir: bool):
    nb = json.loads(ruta.read_text(encoding="utf-8"))
    cuenta: dict = {}

    for celda in nb.get("cells", []):
        if celda.get("cell_type") != "code":
            continue
        salidas = celda.get("outputs", [])

        restantes = [o for o in salidas if not es_widget(o)]
        if len(restantes) != len(salidas):
            cuenta["widget"] = cuenta.get("widget", 0) + (len(salidas) - len(restantes))

        celda["outputs"] = [limpiar_salida(o, cuenta) for o in restantes]

    # The notebook-level widget state can be hundreds of kilobytes of nothing.
    if nb.get("metadata", {}).pop("widgets", None) is not None:
        cuenta["widget_state"] = cuenta.get("widget_state", 0) + 1

    if cuenta and escribir:
        ruta.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")

    return cuenta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="apply the changes. Without it, only reports")
    args = ap.parse_args()

    notebooks = sorted((RAIZ / "notebooks").glob("*.ipynb"))
    if not notebooks:
        print(f"no notebooks found in {RAIZ / 'notebooks'}")
        return 2

    total = 0
    for nb in notebooks:
        cuenta = procesar(nb, args.write)
        total += sum(cuenta.values())
        detalle = ", ".join(f"{k}:{v}" for k, v in sorted(cuenta.items())) or "clean"
        print(f"  {nb.name:32} {detalle}")

    if total == 0:
        print("\nNothing to redact.")
        return 0

    if args.write:
        print(f"\n{total} replacements applied.")
        print("Re-run without --write to confirm the notebooks are clean.")
    else:
        print(f"\n{total} items would be redacted. Re-run with --write to apply.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
