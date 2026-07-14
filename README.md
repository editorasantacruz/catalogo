# Catálogo — Editora Santa Cruz

Site estático do catálogo, publicado via GitHub Pages em
**https://catalogo.editorasantacruz.com.br**.

- `index.html` — catálogo completo
- `Catalogo.xlsx` — planilha de títulos

## Automação de estoque

Toda segunda-feira às 05:00 (horário de Brasília) a GitHub Action
[`atualizar-status.yml`](.github/workflows/atualizar-status.yml) roda o script
[`scripts/atualizar_status.py`](scripts/atualizar_status.py), que consulta a
disponibilidade de cada livro no site da editora, atualiza os selos de
"Esgotado" no `index.html` (mantendo os esgotados ao final de cada categoria)
e a coluna Status do `Catalogo.xlsx`, e faz commit das mudanças.

Também é possível rodá-la manualmente na aba **Actions** do GitHub
(botão "Run workflow").

> A antiga automação local (`atualizar_status_catalogo.ps1`, no Agendador de
> Tarefas do Windows) foi substituída por esta e deve permanecer desativada —
> ela sobrescreveria as correções feitas diretamente neste repositório.
