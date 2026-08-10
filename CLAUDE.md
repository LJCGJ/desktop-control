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
- Versão atual: 0.6.0

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
- "Sempre permitir" memoriza por ferramenta **e por janela ALVO** (v0.5.0):
  para ações com coordenadas o escopo vem de `_window_at_point(x, y)` (a janela
  sob o clique); para teclado, da janela ativa; para `focus_window`, da janela
  que será focada. Antes usava a janela ativa para tudo, o que atribuía a
  permissão à janela errada quando o usuário trocava de foco enquanto decidia.
- **O modelo NÃO consegue afrouxar a própria segurança:** mudar para `auto` exige
  confirmação humana no popup. Voltar para `ask` é livre.
- **Log de auditoria** em `t2m_audit.log` (uma linha JSON por evento). Caminho
  configurável via `T2M_AUDIT_LOG`. NÃO deve ser versionado (está no .gitignore).
- **Texto sensível:** `type_text(..., sensitive=True)` oculta o conteúdo no popup
  e no log (para senhas).
- **Failsafe:** mouse no canto superior esquerdo aborta qualquer ação.
- **Acentos:** `type_text` usa colagem via clipboard (com save/restore) quando há
  caracteres não-ASCII (ç, ã, é…), evitando o problema do typewrite.

## Histórico de testes reais

**10/08/2026 — primeiro teste real (sucesso).** Plugin instalado no app desktop
via "Fazer upload de plugin" (zip com `.claude-plugin/` na raiz). Descoberta
importante: as ferramentas ficam acessíveis **até de uma sessão na nuvem**,
proxiadas pela ponte do dispositivo com o prefixo
`mcp__remote-devices__plugin_t2m-desktop-control_t2m-desktop-control__*`.
Funcionaram: `get_approval_status`, `get_screen_size` (1366x768), `list_windows`
e `screenshot`. Bug encontrado e corrigido (v0.4.1): `screenshot` sem `path`
falhava com *Permission denied* porque a pasta de trabalho do servidor instalado
não é gravável — agora o padrão é a pasta temporária, com criação de diretório
e fallback automático.

> Nota: as ferramentas podem demorar a carregar na sessão; se não aparecerem,
> recarregar/tentar de novo costuma resolver.

**10/08/2026 — segundo teste real: ação executada com sucesso.** `move_mouse`
moveu o cursor de fato (verificado com `get_mouse_position`) e o usuário clicou
"Sempre permitir (nesta janela)" — a restrição por janela foi validada em campo
(`always_allowed: [{tool: move_mouse, window: "Claude"}]`).

Bug de integração encontrado e corrigido (v0.4.2): o popup esperava 300s, mas a
**ponte do app desktop corta a chamada em ~60s**. Resultado: o chamador recebia
timeout mesmo com a ação sendo executada depois — e um retry executaria a ação
DUAS vezes. Agora `_APPROVAL_TIMEOUT` = 45s (env `T2M_APPROVAL_TIMEOUT`), o
popup se fecha sozinho aos 42s negando, e o erro devolvido diz explicitamente
que nada foi executado e que tentar de novo é seguro. O popup também mostra um
contador regressivo.

**10/08/2026 — primeiro QA real do T2M Security Manager v4.2.** Sessão completa
usando a skill `qa-desktop`: mapeada a tela inicial, aberto o Histórico, achado
1 bug confirmado no app (mojibake: "sÃEo" em vez de "são" no detalhe da execução)
e 4 observações. Relatório em `relatorio-qa-t2m-2026-08-10.md`, evidências em
`qa-01`..`qa-03.png`. Validadas em campo: `click`, `screenshot`, `list_windows`,
`move_mouse`, e o "Sempre permitir" por janela.

Bug de segurança do PLUGIN encontrado nessa sessão e corrigido (v0.5.0): a
permissão estava sendo vinculada à **janela ativa no momento do popup**. Como o
usuário troca de janela para ler o pedido no chat, a permissão foi parar na
janela "Claude" — errada e sensível. Agora o escopo vem da janela ALVO
(`_window_at_point` para coordenadas). Lição geral: "janela em foco" é um proxy
ruim para "janela que a ação atinge".

**10/08/2026 — v0.6.0: alvo declarado e verificado (lição mais importante até
agora).** Na tentativa de validar a v0.5.0, o clique em (930,63) foi de novo
atribuído a "Claude" — mas dessa vez o código estava CERTO: o usuário havia
trazido o Claude à frente para ler a mensagem do chat, então o Claude realmente
cobria aquele ponto. O clique foi parar na janela do chat.

Diagnóstico real: **coordenada de tela não determina o aplicativo alvo.** Corrigir
o escopo da permissão (v0.5.0) tratava o sintoma; a causa é agir por coordenadas
sem garantir quem está por cima. Em v0.6.0 as ações (`click`, `type_text`,
`press_keys`) aceitam `window="trecho do título"`: o plugin resolve a janela,
pede aprovação já com esse escopo, traz a janela à frente e **verifica com
`_window_at_point` que ela está sob o ponto** — se não estiver, aborta sem
clicar. A skill foi atualizada para sempre passar `window`.

> Padrão que vale lembrar: quando um agente e um humano compartilham a mesma
> tela, o foco muda o tempo todo. Qualquer ação que dependa de "o que está em
> foco" é uma corrida — declare o alvo e verifique antes de agir.

## Restrições importantes

- **Windows only** (usa pygetwindow, atalhos do Windows).
- **Precisa rodar localmente**, não na nuvem. No app desktop, a tarefa tem que
  estar no modo "Na sua máquina"; no Claude Code, já é local por natureza.

## Pendências / próximos passos

Da revisão de código (itens ainda abertos, prioridade baixa):
- [x] #4 — FEITO (v0.4.0). "Sempre permitir" agora é vinculado à janela ativa:
  `_always_allowed` guarda pares (ferramenta, título_janela) e `_active_window_key()`
  usa `pygetwindow.getActiveWindow()`. Se o foco muda, reaprovar. Sem janela
  detectada, "always" vira "uma vez" por segurança.
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
