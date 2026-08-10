# T2M Desktop Control

Servidor MCP (Model Context Protocol) que dá ao Claude a capacidade de operar o **mouse, o teclado e as janelas do Windows** — com um sistema de aprovação no estilo do Claude Code, onde cada ação pede sua permissão antes de acontecer.

Foi pensado para **automação de QA de aplicativos desktop** (como o T2M Security), mas serve para qualquer tarefa que precise controlar a interface do Windows.

> ⚠️ **Aviso de segurança.** Este servidor permite que uma IA controle seu computador de verdade. Rode apenas em uma máquina onde você entende o risco, mantenha o modo de aprovação em `ask` no dia a dia, e revise cada pedido de permissão. A tecla de emergência é: **jogue o mouse rapidamente para o canto superior esquerdo da tela** — isso aborta qualquer ação em andamento (failsafe do PyAutoGUI).

---

## O que ele faz

**Ferramentas de leitura** (não pedem aprovação, pois não alteram nada):

- `screenshot` — captura a tela e salva um PNG
- `get_screen_size` — resolução da tela
- `get_mouse_position` — posição atual do cursor
- `locate_on_screen` — encontra uma imagem de referência na tela (para clicar num botão/ícone)
- `list_windows` — lista as janelas abertas

**Ferramentas de ação** (pedem aprovação):

- `move_mouse` — move o cursor
- `click` — clica (esquerdo/direito/meio, simples ou duplo)
- `type_text` — digita um texto
- `press_keys` — aperta teclas e atalhos (ex.: `ctrl` + `c`)
- `scroll` — rola a tela
- `drag` — arrasta e solta
- `focus_window` — traz uma janela para frente

**Controle de aprovação:**

- `set_approval_mode` — alterna entre `ask` (pergunta) e `auto` (aprova tudo) — o "dropdown" manual vs. automático
- `get_approval_status` — mostra o modo atual e as ferramentas já liberadas
- `reset_approvals` — revoga tudo e volta para `ask`

---

## Como funciona a aprovação

Toda ação que mexe na máquina dispara um **popup nativo do Windows** com três botões:

- **Permitir uma vez** — executa só desta vez
- **Sempre permitir esta ferramenta** — libera aquela ferramenta específica pelo resto da sessão
- **Negar** — cancela; nada é executado

Fechar a janela no X, ou apertar `Esc`, também **nega**. `Enter` equivale a **Permitir uma vez**.

Se preferir não ver popups, troque o modo para automático (com `set_approval_mode` ou pela variável de ambiente `T2M_APPROVAL_MODE=auto`). As ações de leitura nunca pedem aprovação.

---

## Segurança embutida

- **O Claude não consegue desligar a própria trava.** Trocar para o modo `auto` (sem popups) exige uma confirmação sua no popup nativo — o modelo não afrouxa a segurança sozinho. Voltar para `ask` é sempre livre.
- **"Sempre permitir" é restrito à janela alvo.** Ao liberar permanentemente uma ferramenta, a liberação vale só para a janela em que a ação acontece — determinada pelas coordenadas do clique, não pela janela que está em foco. Clicar em qualquer outra janela pede permissão de novo, então uma autorização não vaza para o resto do sistema (nem para a janela do próprio Claude enquanto você lê o pedido).
- **Log de auditoria.** Toda ação e decisão de aprovação é gravada em `t2m_audit.log` (uma linha JSON por evento). Configure o caminho com `T2M_AUDIT_LOG`.
- **Texto sensível.** `type_text(..., sensitive=True)` não mostra o conteúdo no popup nem no log — use para senhas.
- **Failsafe.** Mouse no canto superior esquerdo aborta qualquer ação.
- **Prazo para responder.** O popup mostra um contador e nega automaticamente após ~45s sem resposta (ajustável em `T2M_APPROVAL_TIMEOUT`). Isso existe porque quem chama o servidor tem um limite próprio de espera — negar rápido garante que nada seja executado "atrasado" e que uma nova tentativa não repita a ação.
- **Acentos.** `type_text` cola via área de transferência quando há caracteres não-ASCII (ç, ã, é…) e restaura o clipboard depois.

## Instalação (Windows)

Requer **Python 3.10+**. Há um guia enxuto por cliente:

- **Claude Code (terminal):** veja [`INSTALL-claude-code.md`](./INSTALL-claude-code.md)
- **App desktop (Cowork "Na sua máquina"):** veja [`INSTALL-desktop.md`](./INSTALL-desktop.md)

Resumo comum aos dois: descompacte numa pasta fixa, rode `pip install -r requirements.txt`, registre o servidor (como plugin via `.claude-plugin/plugin.json`, ou direto via `.mcp.json`) e reinicie o Claude. No app desktop, garanta que a tarefa rode **"Na sua máquina"**, não na nuvem.

---

## Exemplo de uso

> "Tire um screenshot, encontre a janela do T2M Security, traga ela para frente e clique no botão de login."

O Claude vai: `screenshot` → `list_windows` → `focus_window` (pede aprovação) → `screenshot` de novo → `click` (pede aprovação). Você aprova cada passo, ou marca "Sempre permitir esta ferramenta" para agilizar.

---

## Publicação no diretório de plugins da Anthropic

Este projeto já está estruturado como plugin (`.claude-plugin/plugin.json`). Para publicá-lo no diretório da comunidade da Anthropic:

1. Suba o projeto para um repositório público no GitHub.
2. Envie pelo formulário oficial: **https://clau.de/plugin-directory-submission** (pull requests diretos no repositório da Anthropic são fechados automaticamente).
3. O plugin passa por um scan automatizado de segurança e por revisão manual da equipe da Anthropic.
4. Se aprovado, ele entra no marketplace da comunidade e qualquer pessoa poderá instalar.

> **Nota realista sobre a revisão:** um plugin que controla mouse e teclado é uma superfície de segurança sensível e pode receber escrutínio extra (ou ser recusado) na revisão. O sistema de aprovação embutido, o failsafe e o padrão `ask` existem justamente para demonstrar responsabilidade. Documente bem os riscos ao submeter.

---

## Licença

MIT — veja o arquivo `LICENSE`.
