#!/usr/bin/env python3
"""Atualiza o status de estoque do catálogo consultando o site da editora.

Para cada livro do index.html, visita a página do produto em
editorasantacruz.com.br e verifica a disponibilidade:
  - formulário "avise-me" (email_avise) sem botão de compra  -> Esgotado
  - botão de compra (button_buy) sem "avise-me"              -> Disponível
  - sinal ambíguo ou erro de rede                            -> mantém o status atual

Depois aplica no index.html (selo "Esgotado" nos cards, esgotados ao final
de cada categoria) e na coluna Status do Catalogo.xlsx.

Substitui a automação local atualizar_status_catalogo.ps1 (Agendador do
Windows). Roda via GitHub Actions — ver .github/workflows/atualizar-status.yml.
"""
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
XLSX = ROOT / "Catalogo.xlsx"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CatalogoSantaCruz/1.0)"}
BADGE = '<span class="badge-esgotado">Esgotado</span>\n'


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(2 * (i + 1))


def availability(raw):
    """'esgotado', 'disponivel' ou None (indeterminado)."""
    if raw is None:
        return None
    has_buy = b"button_buy" in raw
    has_avise = b"email_avise" in raw
    if has_buy and not has_avise:
        return "disponivel"
    if has_avise and not has_buy:
        return "esgotado"
    return None


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def main():
    html = INDEX.read_text(encoding="utf-8")
    novos_status = {}  # título -> 'Esgotado' | 'Disponível'
    mudancas = []

    # percorre cada seção de categoria reordenando e atualizando selos
    out = []
    for sec in re.finditer(r'<section class="category"[^>]*>', html):
        sec_start = sec.start()
        sec_end = html.find("</section>", sec_start)
        grid_start = html.find('<div class="grid">', sec_start, sec_end)
        if grid_start < 0:
            continue
        grid_open_end = grid_start + len('<div class="grid">')
        grid_close = html.rfind("</div>", grid_start, sec_end)
        body = html[grid_open_end:grid_close]
        starts = [m.start() for m in re.finditer(r'<div class="card">', body)]
        if not starts:
            continue
        prefix = body[: starts[0]]
        cards = [body[s:e] for s, e in zip(starts, starts[1:] + [len(body)])]

        novas = []
        for card in cards:
            titulo_m = re.search(r'<div class="book-title">([^<]*)</div>', card)
            url_m = re.search(r'href="(https://www\.editorasantacruz\.com\.br/[^"]+)"', card)
            titulo = titulo_m.group(1) if titulo_m else "?"
            estava_esgotado = "badge-esgotado" in card
            status = availability(fetch(url_m.group(1))) if url_m else None
            time.sleep(0.5)  # gentileza com o servidor

            if status == "esgotado" and not estava_esgotado:
                card = card.replace('<div class="cover">\n', '<div class="cover">\n' + BADGE, 1)
                mudancas.append(f"ESGOTOU: {titulo}")
            elif status == "disponivel" and estava_esgotado:
                card = card.replace(BADGE, "", 1)
                mudancas.append(f"VOLTOU: {titulo}")
            elif status is None:
                print(f"  aviso: status indeterminado, mantido: {titulo}", file=sys.stderr)

            if status:
                novos_status[norm(titulo)] = "Esgotado" if status == "esgotado" else "Disponível"
            novas.append(card)

        reordenadas = [c for c in novas if "badge-esgotado" not in c] + [
            c for c in novas if "badge-esgotado" in c
        ]
        out.append((grid_open_end, grid_close, prefix + "".join(reordenadas)))

    for start, end, new_body in reversed(out):
        html = html[:start] + new_body + html[end:]
    INDEX.write_text(html, encoding="utf-8")

    # planilha: coluna Status (D), casando por título normalizado
    try:
        import openpyxl

        wb = openpyxl.load_workbook(XLSX)
        ws = wb.active
        alterou = False
        for row in ws.iter_rows(min_row=2):
            titulo = str(row[1].value or "")
            chave = norm(titulo)
            atual = str(row[3].value or "")
            if atual == "Pré-venda":  # gerido manualmente
                continue
            novo = novos_status.get(chave)
            if novo is None:  # tenta casar por prefixo
                cand = [v for k, v in novos_status.items() if k.startswith(chave) or chave.startswith(k)]
                novo = cand[0] if len(set(cand)) == 1 else None
            if novo and novo != atual:
                row[3].value = novo
                alterou = True
        if alterou:
            wb.save(XLSX)
    except ImportError:
        print("aviso: openpyxl ausente, planilha não atualizada", file=sys.stderr)

    print(f"{len(mudancas)} mudança(s) de status:")
    for m in mudancas:
        print(" -", m)


if __name__ == "__main__":
    main()
