# CLAUDE.md — Contexto do projeto para sessões futuras

> Este arquivo é lido pelo Claude no início de cada sessão para retomar o
> contexto do projeto sem depender de memória entre conversas. Mantenha-o
> atualizado conforme o projeto evolui.

## O que é

**T2M Desktop Control** é um servidor MCP (Model Context Protocol) em Python que
dá ao Claude a capacidade de operar **mouse, teclado e janelas do Windows**, com
um sistema de aprovação no estilo do Claude Code (cada ação pede permissão antes
de acontecer). O objetivo principal é **automação de QA de aplicativos desktop**,
em especial o app **T2M Security**.

- Autor: Leonardo Gonzaga Junior (LeonardoJoseCordeiro)
- Repositório: https://github.com/LJCGJ/desktop-control
- Pasta local: `C:\Users\LeonardoJoseCordeiro\Documents\t2m-desktop-control`
- Máquina de desenvolvimento: Windows (device `t2m0249`), editor VS Code
- Versão atual: 0.3.0

## Como o Claude trabalha neste projeto

- O Claude edita os arquivos **direto na pasta** via a ponte de dispositivos.
- O Leonardo faz os commits/push manualmente no VS Code (mantém o controle do repo).
- **Combinação de fluxo:** não editar o mesmo arquivo ao mesmo tempo. Se o
  Leonardo alterar algo, avisar para o Claude reler antes de mexer.

## Arquitetura

- `server/server.py` — servidor FastMCP com 15 ferramentas. Contém toda a lógica
  de aprovação, auditoria e as ferramentas de controle.
- `server/approval.py` — popup nativo de aprovação (tkinter), executado como
  **processo separado** para não conflitar com a thread stdio do servidor.
  Retorna `once` / `always` / `deny` pelo stdout.
- `.claude-plugin/plugin.json` — manifesto de plugin (usado pelo app desktop /
  Cowork). Aponta para o servidor via `${CLAUDE_PLUGIN_ROOT}`.
- `.mcp.json` — registro direto de servidor MCP (usado pelo Claude Code).
- `requirements.txt` — mcp, pyautogui, pillow, pygetwindow, opencv-python, pyperclip.
- `INSTALL-claude-code.md` / `INSTALL-desktop.md` — guias por cliente.
- `skills/qa-desktop/` — skill de QA de desktop (SKILL.md + references/
  bug-report-template.md). Ensina o Claude a testar apps de forma metódica
  (ciclo Observar → Agir → Verificar) e a gerar relatório de bugs.

## Ferramentas (15)

Leitura (não pedem aprovação): `screenshot`, `get_screen_size`,
`get_mouse_position`, `locate_on_screen`, `list_windows`.

Ação (pedem aprovação): `move_mouse`, `click`, `type_text`, `press_keys`,
`scroll`, `drag`, `focus_window`.

Controle de aprovação: `set_approval_mode`, `get_approval_status`,
`reset_approvals`.

## Sistema de aprovação e segurança (decisões tomadas)

- Modos: `ask` (padrão, pede confirmação a cada ação) e `auto` (sem popups).
- Popup nativo com 3 opções: Permitir uma vez / Sempre permitir esta ferramenta /
  Negar. Fechar no X ou Esc = negar; Enter = permitir uma vez.
- "Sempre permitir" memoriza por ferramenta durante a sessão.
- **O modelo NÃO consegue afrouxar a própria segurança:** mudar para `auto` exige
  confirmação humana no popup. Voltar para `ask` é livre.
- **Log de auditoria** em `t2m_audit.log` (uma linha JSON por evento). Caminho
  configurável via `T2M_AUDIT_LOG`. NÃO deve ser versionado (está no .gitignore).
- **Texto sensível:** `type_text(..., sensitive=True)` oculta o conteúdo no popup
  e no log (para senhas).
- **Failsafe:** mouse no canto superior esquerdo aborta qualquer ação.
- **Acentos:** `type_text` usa colagem via clipboard (com save/restore) quando há
  caracteres não-ASCII (ç, ã, é…), evitando o problema do typewrite.

## Restrições importantes

- **Windows only** (usa pygetwindow, atalhos do Windows).
- **Precisa rodar localmente**, não na nuvem. No app desktop, a tarefa tem que
  estar no modo "Na sua máquina"; no Claude Code, já é local por natureza.

## Pendências / próximos passos

Da revisão de código (itens ainda abertos, prioridade baixa):
- [ ] #4 — "Sempre permitir" é grosso (libera a ferramenta em qualquer contexto).
  Ideia: restringir por janela (ex: só age quando a janela ativa é o T2M Security).
- [x] Skill de QA — FEITA (v0.3.0). Em `skills/qa-desktop/`. Ainda não testada
  na prática com o app real; iterar conforme o feedback do primeiro uso.

Publicação:
- [ ] Diretório da Anthropic exige repo público e passa por revisão de segurança;
  um plugin de controle de desktop pode receber escrutínio extra. Reforçar
  salvaguardas antes de submeter (lista de apps permitidos, mais auditoria).
- Alternativa sem curadoria: publicar nos registros da comunidade MCP
  (mcpservers.org, PulseMCP).

Nomenclatura:
- Repo = `desktop-control`; nome do plugin no plugin.json = `t2m-desktop-control`.
  (A definir se alinha os dois nomes.)

## Como testar rápido (na máquina do Leonardo)

```powershell
cd C:\Users\LeonardoJoseCordeiro\Documents\t2m-desktop-control
pip install -r requirements.txt
# Claude Code:
claude mcp add t2m-desktop-control -- python .\server\server.py
# depois, no Claude Code: /mcp  (deve listar as 15 ferramentas)
```
