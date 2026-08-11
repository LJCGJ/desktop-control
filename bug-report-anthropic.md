# Bug report para a Anthropic — conector de plugin local preso em "não conectado"

> Onde reportar (em ordem de recomendação):
>
> 1. **GitHub**: https://github.com/anthropics/claude-code/issues/new — é onde os
>    bugs do app desktop são registrados na prática (use o texto em inglês abaixo).
> 2. **Suporte no app**: iniciais/nome no canto inferior esquerdo → "Get help" →
>    chat (versão curta em português no fim deste arquivo).
>
> Tudo preenchido (app 1.26832.0.0; Windows 11 Pro 25H2, build 26200.8655).
> Só falta anexar os prints citados na hora de enviar.

---

## Versão para o GitHub (inglês)

**Title:**
`[BUG] Desktop (Windows/MS Store): local stdio MCP server from an uploaded plugin stuck "Not connected" — Install button just opens the public Connector Directory`

**Body:**

### Environment

- Claude Desktop for Windows, installed from the **Microsoft Store** (MSIX,
  package id `Claude_pzs8sxrjxfjjc`)
- App version: **1.26832.0.0** (per Windows → Installed apps; installed 2026-08-07)
- Windows 11 Pro 25H2 (OS build 26200.8655), x64 — Dell Vostro 3400,
  i7-1165G7, 12 GB RAM
- Plugin installed via **Settings → Plugins → "Upload plugin"** (zip file)

### Plugin

- Name: `t2m-desktop-control` v0.8.2 (repo: https://github.com/LJCGJ/desktop-control)
- `.claude-plugin/plugin.json` declares a **local stdio MCP server** via
  `mcpServers` using `${CLAUDE_PLUGIN_ROOT}` (command: `python`, args:
  `server/server.py`)
- The plugin also ships a skill (`skills/qa-desktop/`)

### Steps to reproduce

1. Upload the plugin zip via Settings → Plugins → "Upload plugin". It installs
   and shows as enabled.
2. Open the plugin page → **Connectors** tab. The `t2m-desktop-control`
   connector is listed as **not connected**, with an **"Install" button** and
   the text "Connect each one so Claude can use them".
3. Click **Install**.

### Expected

The local MCP server declared by the plugin is started/connected (or a
connection flow for it opens).

### Actual

The Install button **opens the public Connector Directory** (the store of
public connectors). An uploaded/local plugin is of course not listed there, so
this is a **dead end**: there is no path in the UI to connect the plugin's own
local server.

Consequences in sessions: the plugin's **skill appears** (skills don't depend
on the server), but **none of the plugin's MCP tools are available** — the
server never starts.

### What we ruled out (it's not the plugin)

- Zip layout and `.claude-plugin/plugin.json` verified OK (`mcpServers`
  declared correctly).
- `server.py` compiles (`py_compile`) and **starts cleanly** when run from the
  project folder (audit log shows `server_start version 0.8.2`).
- Tried: toggling the plugin off/on, quitting the app from the tray and
  reopening, starting brand-new conversations. The connector stays
  "not connected".

### Note / possible regression

Earlier the **same day** (morning of Aug 10), with the same machine and an
earlier build of the same plugin, the plugin's MCP tools **did work** in
sessions (they were even proxied to a cloud session by the device bridge). By
the afternoon, after uninstall → upload of the new zip → restart, the
connector was stuck "not connected" with no way to connect it. So either the
connector had been auto-connected by another path before, or behavior changed.

### Workaround found

Registering the server directly in `claude_desktop_config.json` works —
noting that for the **Microsoft Store install** the real file is in the
virtualized path
`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
(not the classic `%APPDATA%\Claude`). With that, the server starts and all
tools work, including UI actions (validated: click/drag/keys with the server
running in that context). Possibly related: #25600 (local MCP servers ignored
on MS Store installs), #47819 and anthropics/claude-ai-mcp#185 (plugin
connectors failing to connect, remote/HTTP cases).

### Evidence available

- Screenshot of the plugin's Connectors tab showing "not connected" +
  "Install" [ANEXAR print]
- Screenshot of the Install button landing on the public Connector Directory
  [ANEXAR print]
- Plugin zip and manifest on request; repo is public.

---

## Versão curta para o suporte no app (português)

Instalei um plugin local por zip ("Fazer upload de plugin") no app desktop do
Windows (instalado pela Microsoft Store). O plugin declara um servidor MCP
local (stdio) no `plugin.json` via `mcpServers`. Na aba **Conectores** da tela
do plugin, o conector aparece como **"não conectado"**, e o botão **"Instalar"**
apenas abre o **Diretório público de conectores** — onde um plugin local
obviamente não está. Ou seja: não existe caminho na interface para conectar o
servidor local do próprio plugin. Resultado: a skill do plugin aparece nas
conversas, mas nenhuma ferramenta MCP dele fica disponível.

Já verifiquei que não é o plugin: o zip e o manifesto estão corretos e o
servidor inicia sem erros fora do app. Toggle off/on, reiniciar pela bandeja e
abrir conversas novas não resolvem. Workaround que funcionou: registrar o
servidor no `claude_desktop_config.json` — que na instalação da Store fica em
`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\`.

Posso enviar prints e o zip do plugin. Windows 11 Pro 25H2 (build
26200.8655). Versão do app: 1.26832.0.0.
