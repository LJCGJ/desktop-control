---
name: setup
description: >-
  Guia a instalação e a configuração inicial do plugin t2m-desktop-control:
  verificação de Python, instalação das dependências (pyautogui, pygetwindow
  etc.) e diagnóstico dos problemas comuns de primeira execução. Use quando o
  usuário acabou de instalar o plugin, quando qualquer ferramenta do
  t2m-desktop-control falhar com erro de dependência ("pyautogui nao esta
  disponivel", "pygetwindow nao instalado", ModuleNotFoundError), quando as
  ferramentas do plugin não aparecerem na sessão, ou quando o usuário pedir
  ajuda para "instalar", "configurar" ou "fazer funcionar" o controle de
  desktop.
---

# Setup do t2m-desktop-control

Este plugin roda um servidor MCP local em Python que controla mouse, teclado
e janelas do **Windows**. A instalação pela loja registra o servidor
automaticamente, mas as dependências Python são instaladas pelo usuário —
seu papel é conduzir esse processo com calma e verificar cada etapa.

## Pré-requisitos

- **Windows** (o plugin usa APIs do Windows; não funciona em macOS/Linux).
- **Python 3.10+** no PATH. Verifique pedindo ao usuário para rodar
  `python --version` num terminal. Se não houver Python, indique
  https://www.python.org/downloads/ e a opção "Add python.exe to PATH" no
  instalador.
- A tarefa/conversa precisa rodar **no computador do usuário** (não na
  nuvem), pois o servidor controla a máquina local.

## Instalação das dependências

Peça ao usuário para rodar no terminal, na pasta do plugin instalado:

```powershell
pip install mcp pyautogui pillow pygetwindow opencv-python pyperclip
```

(Se ele tiver o repositório clonado, `pip install -r requirements.txt` na
raiz do projeto faz o mesmo.)

## Verificação

1. Chame `get_approval_status` — deve responder com `versao_do_servidor`.
2. Chame `get_screen_size` e depois `screenshot` — a primeira captura
   confirma que pyautogui e Pillow estão funcionando.
3. Chame `list_windows` — confirma o pygetwindow.

Se as três passarem, o plugin está pronto. Sugira ao usuário experimentar a
skill `qa-desktop` com um app de teste.

## Problemas comuns

- **"pyautogui nao esta disponivel" / ModuleNotFoundError** — as dependências
  não foram instaladas no MESMO Python que o app usa para rodar o servidor.
  Peça `python -c "import pyautogui"` no terminal: se falhar ali também, é só
  instalar; se funcionar no terminal mas falhar no plugin, há mais de um
  Python na máquina — descubra qual está no PATH com `where python`.
- **As ferramentas do plugin não aparecem na conversa** — as ferramentas de
  uma sessão são fixadas quando ela começa. Feche o aplicativo pela bandeja,
  reabra e **inicie uma conversa nova**.
- **O conector do plugin fica "não conectado" na tela do plugin** — bug
  conhecido do app desktop (anthropics/claude-code#85623). Alternativas
  enquanto não é corrigido: usar o plugin pelo Claude Code
  (`claude mcp add t2m-desktop-control -- python <pasta>\server\server.py`)
  ou registrar o servidor manualmente no `claude_desktop_config.json`.
- **Ações não executam / nada acontece** — confira o modo de aprovação do
  próprio aplicativo (o consentimento é mediado por ele no modo `host`).
- **Emergência** — lembre o usuário: jogar o mouse no canto superior
  esquerdo da tela aborta qualquer ação (failsafe).
