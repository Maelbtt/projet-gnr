"""Génère le PDF A4 de chaque lettre (docs/contenu/lettres/*.md -> même nom en .pdf).

Utilisé par l'Action GitHub « PDF des lettres » à chaque publication d'une lettre.
En local : py -3.13 -m pip install playwright && py -3.13 -m playwright install chromium
           py -3.13 scripts\\lettres_pdf.py
"""
import functools
import http.server
import json
import pathlib
import threading

from playwright.sync_api import sync_playwright

DOCS = pathlib.Path(__file__).resolve().parents[1] / "docs"


class Silencieux(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    lettres = json.loads((DOCS / "contenu" / "index.json").read_text(encoding="utf-8")).get("lettres", [])
    handler = functools.partial(Silencieux, directory=str(DOCS))
    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = serveur.server_address[1]
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page()
        for l in lettres:
            md = DOCS / l["fichier"]
            pdf = md.with_suffix(".pdf")
            page.goto(f"http://127.0.0.1:{port}/lettres.html#{md.stem}")
            page.wait_for_function("document.querySelector('#article').children.length > 0")
            page.wait_for_timeout(300)
            page.emulate_media(media="print")
            page.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True)
            print("PDF :", pdf.relative_to(DOCS.parent))
        nav.close()
    serveur.shutdown()


if __name__ == "__main__":
    main()
