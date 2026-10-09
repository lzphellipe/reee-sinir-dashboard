"""Gera dist/index.html autocontido (CSS e JS embutidos) + dados, para hospedagens
que exigem um único HTML. O GitHub Pages usa a pasta dashboard/ diretamente.

Uso: python scripts/build_single.py [--fragment]
  --fragment  omite <!doctype>/<html>/<head>/<body> (para plataformas que já
              envolvem a página num esqueleto próprio).
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dashboard"
DIST = ROOT / "dist"


def main(fragment: bool) -> None:
    html = (SRC / "index.html").read_text(encoding="utf-8")
    style = (SRC / "css" / "style.css").read_text(encoding="utf-8")
    app = (SRC / "js" / "app.js").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="css/style.css">', f"<style>\n{style}\n</style>")
    html = html.replace('<script src="js/app.js"></script>', f"<script>\n{app}\n</script>")
    if fragment:
        head = re.search(r"<head>(.*?)</head>", html, re.S).group(1)
        head = re.sub(r'<meta charset="utf-8">\s*|<meta name="viewport"[^>]*>\s*', "", head)
        body = re.search(r"<body>(.*?)</body>", html, re.S).group(1)
        html = head.strip() + "\n" + body.strip() + "\n"
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "data").mkdir(parents=True)
    (DIST / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(SRC / "data", DIST / "data", dirs_exist_ok=True)
    print(f"ok: {DIST / 'index.html'} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main("--fragment" in sys.argv)
