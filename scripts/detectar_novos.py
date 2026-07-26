#!/usr/bin/env python3
"""Lista os produtos que estão no site da editora e ainda não estão no catálogo.

Não altera nada: só compara e escreve um relatório em Markdown na saída padrão
(o workflow joga isso no resumo do job e abre uma issue quando aparece título novo).

O cadastro em si não roda aqui: a capa de cada card vem da pasta do Google Drive
da editora, que o runner do GitHub não enxerga. Quem monta o card é a skill
/catalogo, na máquina do Lucas, que tem o Drive montado.

ATENÇÃO ao comparar: o site usa MAIS DE UM padrão de URL para produto — hoje
/livros/, /livro/ e /editora-santa-cruz/ aparecem nos cards do catálogo. Por isso
a comparação é feita pelo último segmento da URL (o slug), e não pelo caminho
inteiro. Filtrar por "/livros/" deixa produto de fora e inventa problema que não
existe.

Combos, kits e papelaria ficam fora do catálogo por decisão da editora — ver
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
DOMINIO = "https://www.editorasantacruz.com.br"

# Seções do site que contêm produto. As três primeiras são as que os cards já usam;
# as outras existem no site mas não entram no catálogo (ver ignorar-no-catalogo.json).
SECOES_DE_PRODUTO = {
    "livros", "livro", "editora-santa-cruz",
    "combos", "combos-santa-cruz", "papelaria",
}


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


def slug(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def produtos_do_site():
    """O sitemap.xml é um índice — aponta pro sitemap com as URLs de verdade.
    Devolve {slug: url} das seções de produto."""
    indice = fetch(SITEMAP)
    if indice is None:
        return None
    achados = {}
    for filho in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", indice.decode("utf-8", "ignore")):
        corpo = fetch(filho)
        if corpo is None:
            return None
        for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", corpo.decode("utf-8", "ignore")):
            partes = u.split("/")
            if len(partes) > 4 and partes[3] in SECOES_DE_PRODUTO:
                achados[slug(u)] = u
    return achados


def main():
    do_site = produtos_do_site()
    if not do_site:
        print("Sitemap indisponível — comparação não foi feita.")
        return 0  # não derruba o job de estoque por causa disso

    html = INDEX.read_text(encoding="utf-8")
    cards = re.findall(r'<div class="card">.*?(?=<div class="card">|</div>\s*</section>)',
                       html, re.S)
    do_catalogo, sem_link = set(), []
    for c in cards:
        m = re.search(rf'href="({re.escape(DOMINIO)}/[^"]+)"', c)
        if m:
            do_catalogo.add(slug(m.group(1)))
        else:
            t = re.search(r'book-title">([^<]*)', c)
            sem_link.append(t.group(1).strip() if t else "(card sem título)")

    ignorados, prefixos = set(), []
    if IGNORAR.exists():
        dados = json.loads(IGNORAR.read_text(encoding="utf-8"))
        ignorados, prefixos = set(dados.get("slugs", [])), dados.get("prefixos", [])

    faltando = [s for s in sorted(set(do_site) - do_catalogo)
                if s not in ignorados and not any(s.startswith(p) for p in prefixos)]
    sumidos = sorted(do_catalogo - set(do_site))

    print(f"Site: **{len(do_site)}** produtos · Catálogo: **{len(cards)}** cards\n")
    if faltando:
        print(f"### {len(faltando)} título(s) novo(s) para cadastrar\n")
        for s in faltando:
            print(f"- [{s}]({do_site[s]})")
        print("\nPara publicar, na máquina com o Drive montado:\n")
        print("```\n/catalogo\n```")
    else:
        print("Nenhum título novo. Catálogo em dia com o site.")

    if sem_link:
        print(f"\n### {len(sem_link)} card(s) sem link de produto\n")
        print("Sem link, a atualização de estoque não consegue verificar o card.\n")
        for t in sem_link:
            print(f"- {t}")

    if sumidos:
        print(f"\n### {len(sumidos)} no catálogo mas fora do sitemap\n")
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
