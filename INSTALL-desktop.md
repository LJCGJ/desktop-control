# Instalação no app desktop (Cowork "Na sua máquina") — Windows

No app desktop, o ponto crítico é: a tarefa precisa rodar **na sua máquina**, não na nuvem. Um servidor que controla o seu mouse/teclado só funciona se o Claude estiver rodando localmente.

## 1. Pré-requisitos

- **Python 3.10+** instalado e no PATH (teste: `python --version`)
- **App desktop do Claude** instalado e atualizado

## 2. Coloque a pasta num local fixo

Descompacte o projeto em, por exemplo, `C:\ferramentas\t2m-desktop-control`.

## 3. Instale as dependências

```powershell
cd C:\ferramentas\t2m-desktop-control
pip install -r requirements.txt
```

## 4. Instale o plugin

O projeto já vem no formato de plugin (`.claude-plugin\plugin.json`), que aponta para o servidor via `${CLAUDE_PLUGIN_ROOT}` — ou seja, funciona a partir de qualquer pasta, sem editar caminho.

No app desktop, adicione o plugin a partir desta pasta (Configurações → Plugins → adicionar a partir de uma pasta local / marketplace local apontando para `C:\ferramentas\t2m-desktop-control`). O app lê o `plugin.json` e registra o servidor automaticamente.

> Se a sua versão do app ainda não tiver instalação de plugin por pasta, use o caminho alternativo: registre como servidor MCP pelo `.mcp.json` (edite o caminho real) na configuração de conectores/MCP do app.

## 5. Rode a tarefa NA SUA MÁQUINA

Este passo é o que faz tudo funcionar:

1. Comece uma nova tarefa no Cowork.
2. No seletor **"Run this task"** (canto superior direito, ao iniciar), escolha **"Na sua máquina"** (On your computer), **não** "Na nuvem".
3. Opcional: em Configurações → Cowork, ligue "Run new tasks on your computer" para virar o padrão.

Se você rodar "Na nuvem", o servidor local não é alcançado e as ações não acontecem na sua tela.

## 6. Use

Converse normalmente:

> "Abre o T2M Security, faz login com o usuário de teste e me diz se a tela inicial carregou."

Cada ação que mexe na máquina abre um popup de permissão. Emergência: jogue o mouse pro canto superior esquerdo da tela para abortar tudo.

## Configuração opcional

No bloco `env` do `plugin.json` você pode definir:

- `T2M_APPROVAL_MODE`: `ask` (padrão) ou `auto`
- `T2M_AUDIT_LOG`: caminho do log de auditoria
