#!/usr/bin/env python3
"""Lista os produtos que estão no site da editora e ainda não estão no catálogo.

Não altera nada: só compara e escreve um relatório em Markdown na saída padrão
(o workflow joga isso no resumo do job e abre uma issue quando aparece título novo).

O cadastro em si não roda aqui: a capa de cada card vem da pasta do Google Drive
da editora, que o runner do GitHub não enxerga. Quem monta o card é a skill
/catalogo, na máquina do Lucas, que tem o Drive montado.

Combos ficam de fora do catálogo por decisão da editora (26/07/2026) — ver
ignorar-no-catalogo.json.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
IGNORAR = ROOT / "ignorar-no-catalogo.json"
SITEMAP = "https://www.editorasantacruz.com.br/sitemap.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CatalogoSantaCruz/1.0)"}


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                print(f"ERRO: não consegui ler {url} ({e})", file=sys.stderr)
                return None


def slugs_do_site():
    """O sitemap.xml é um índice — aponta pro sitemap com as URLs de verdade."""
    indice = fetch(SITEMAP)
    if indice is None:
        return None
    slugs = set()
    for filho in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", indice.decode("utf-8", "ignore")):
        corpo = fetch(filho)
        if corpo is None:
            return None
        for u in re.findall(r"editorasantacruz\.com\.br/livros/([^<\s\"]+)",
                            corpo.decode("utf-8", "ignore")):
            slugs.add(u.rstrip("/"))
    return slugs


def main():
    do_site = slugs_do_site()
    if not do_site:
        print("Sitemap indisponível — comparação não foi feita.")
        return 0  # não derruba o job de estoque por causa disso

    html = INDEX.read_text(encoding="utf-8")
    do_catalogo = {u.rstrip("/") for u in
                   re.findall(r'editorasantacruz\.com\.br/livros/([^"\s]+)"', html)}

    ignorados, prefixos = set(), []
    if IGNORAR.exists():
        dados = json.loads(IGNORAR.read_text(encoding="utf-8"))
        ignorados, prefixos = set(dados.get("slugs", [])), dados.get("prefixos", [])

    faltando = [s for s in sorted(do_site - do_catalogo)
                if s not in ignorados and not any(s.startswith(p) for p in prefixos)]
    sumidos = sorted(do_catalogo - do_site)

    # Card sem link e card que a atualizacao de estoque nao consegue verificar: o status
    # dele fica congelado no que estiver la, para sempre, sem ninguem perceber.
    cards = re.findall(r'<div class="card">.*?(?=<div class="card">|</div>\s*</section>)', html, re.S)
    sem_link = []
    for c in cards:
        if not re.search(r'href="https://www\.editorasantacruz\.com\.br/livros/', c):
            t = re.search(r'book-title">([^<]*)', c)
            sem_link.append(t.group(1).strip() if t else "(card sem titulo)")

    print(f"Site: **{len(do_site)}** produtos · Catálogo: **{len(do_catalogo)}**\n")
    if faltando:
        print(f"### {len(faltando)} título(s) novo(s) para cadastrar\n")
        for s in faltando:
            print(f"- [{s}](https://www.editorasantacruz.com.br/livros/{s})")
        print("\nPara publicar, na máquina com o Drive montado:\n")
        print("```\n/catalogo\n```")
    else:
        print("Nenhum título novo. Catálogo em dia com o site.")

    if sem_link:
        print(f"\n### {len(sem_link)} card(s) sem link de produto\n")
        print("O status destes **não é verificado** pela automação — fica congelado no")
        print("que estiver lá até alguém corrigir à mão.\n")
        for t in sem_link:
            print(f"- {t}")

    if sumidos:
        print(f"\n### {len(sumidos)} no catálogo mas fora do sitemap")
        for s in sumidos:
            print(f"- {s}")
        print("\n(produto despublicado, ou link do card errado)")

    # o workflow usa isto pra decidir se abre issue
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if saida:
        saida.write_text(f"novos={len(faltando)}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
