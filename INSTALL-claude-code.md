# Instalação no Claude Code (terminal) — Windows

O Claude Code roda localmente por natureza, então este é o caminho mais direto.

## 1. Pré-requisitos

- **Python 3.10+** instalado e no PATH (teste: `python --version`)
- **Claude Code** instalado (teste: `claude --version`)

## 2. Coloque a pasta num local fixo

Descompacte o projeto em, por exemplo, `C:\ferramentas\t2m-desktop-control`.

## 3. Instale as dependências

```powershell
cd C:\ferramentas\t2m-desktop-control
pip install -r requirements.txt
```

## 4. Registre o servidor MCP

Opção A — comando direto (recomendado):

```powershell
claude mcp add t2m-desktop-control -- python C:\ferramentas\t2m-desktop-control\server\server.py
```

Opção B — pelo arquivo `.mcp.json` do projeto: edite o `.mcp.json`, troque `C:/CAMINHO/PARA/...` pelo caminho real, e copie o bloco `mcpServers` para a configuração do Claude Code.

## 5. Confirme

Abra o Claude Code e rode:

```
/mcp
```

Você deve ver `t2m-desktop-control` conectado e as 15 ferramentas listadas.

## 6. Use

Converse normalmente, por exemplo:

> "Tira um screenshot, acha a janela do T2M Security, traz ela pra frente e me diz o que aparece."

Cada ação que mexe na máquina abre um popup de permissão. Emergência: jogue o mouse pro canto superior esquerdo da tela para abortar tudo.

## Configuração opcional

Variáveis de ambiente:

- `T2M_APPROVAL_MODE=auto` — sobe já no modo automático (sem popups). Use com cuidado.
- `T2M_AUDIT_LOG=C:\caminho\meu_log.log` — muda onde o log de auditoria é gravado.

Para passá-las no registro:

```powershell
claude mcp add t2m-desktop-control -e T2M_APPROVAL_MODE=ask -- python C:\ferramentas\t2m-desktop-control\server\server.py
```
