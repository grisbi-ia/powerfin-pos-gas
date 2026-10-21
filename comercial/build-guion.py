#!/usr/bin/env python3
"""Genera GUION_REUNION.pdf a partir de GUION_REUNION.md.

Uso:
    cd comercial && python3 build-guion.py

Requiere pandoc (convierte el Markdown) y weasyprint (imprime el PDF).
El Markdown es la fuente; el PDF y el HTML temporal no se editan a mano.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

BASE = pathlib.Path(__file__).resolve().parent
MD = BASE / "GUION_REUNION.md"
CSS = BASE / "guion-print.css"
OUT = BASE / "GUION_REUNION.pdf"

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Guión de la reunión comercial — Powerfin ERP + POS GAS</title>
<style>
{css}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def main() -> int:
    for bin_name in ("pandoc", "weasyprint"):
        if shutil.which(bin_name) is None:
            print(f"ERROR: falta '{bin_name}' en el PATH.", file=sys.stderr)
            return 1
    for path in (MD, CSS):
        if not path.exists():
            print(f"ERROR: no existe {path}", file=sys.stderr)
            return 1

    fragment = subprocess.run(
        ["pandoc", str(MD), "-f", "gfm", "-t", "html5"],
        check=True, capture_output=True, text=True,
    ).stdout

    html = TEMPLATE.format(css=CSS.read_text(encoding="utf-8"), body=fragment)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", prefix="guion-", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(html)
        tmp_path = tmp.name

    try:
        subprocess.run(["weasyprint", tmp_path, str(OUT)], check=True)
    finally:
        pathlib.Path(tmp_path).unlink(missing_ok=True)

    info = subprocess.run(
        ["pdfinfo", str(OUT)], capture_output=True, text=True
    ).stdout
    pages = next(
        (line.split(":", 1)[1].strip() for line in info.splitlines()
         if line.startswith("Pages:")),
        "?",
    )
    print(f"OK → {OUT.relative_to(BASE.parent)} ({pages} páginas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
