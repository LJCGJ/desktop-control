# CLAUDE.md — Contexto do projeto para sessões futuras

> Este arquivo é lido pelo Claude no início de cada sessão para retomar o
> contexto do projeto sem depender de memória entre conversas. Mantenha-o
> atualizado conforme o projeto evolui.

## ✅ RETOMADA CONCLUÍDA em 10/08/2026 ~17h50 — B1 VALIDADO, click com window OK

**Resultado:** o PLANO B1 (registro via `claude_desktop_config.json` da pasta
virtualizada da Store, modo `host`) FUNCIONOU por completo. Numa sessão nova
as ferramentas apareceram na ponte com o prefixo
`mcp__remote-devices__t2m-desktop-control__*` (sem o `plugin_...` — esse é o
sinal de que quem respondeu foi o servidor do config, não o do plugin).

Validado em campo nesta sessão (contexto do config, SESSIONNAME vazio):
- `get_approval_status` → `versao_do_servidor: 0.8.2`, `mode: host`,
  audit log na pasta do projeto. ✔
- **AÇÕES FUNCIONAM sem popup nesse contexto** (o risco aberto do B1 caiu):
  `focus_window`, `press_keys`, `drag` e `click` executaram de verdade. ✔
- **TESTE PENDENTE CONCLUÍDO:** `click(942, 110, window="T2M Security")` no
  botão "Configuracoes" do T2M Security Manager v4.2 → a janela
  "Configuracoes" ABRIU (evidência `qa-resume-02.png`); fechada em seguida
  com `click(..., window="Configuracoes")` no Cancelar. A verificação de
  janela alvo funcionou inclusive com a janela no 2º monitor. ✔

Aprendizados novos (10/08, fim de tarde):
- **`screenshot` só captura o monitor principal (1366x768).** O T2M estava
  no 2º monitor (x=1525) e ficava invisível. Solução usada: `drag` na barra
  de título (1900,50 → 600,60) trouxe a janela para o monitor principal.
  Melhoria futura: capturar todos os monitores (`ImageGrab.grab(all_screens=True)`).
- **`press_keys` com atalhos do shell (Win+Shift+Left) não surtiu efeito**,
  mesmo após click na janela — a janela não se moveu (2 tentativas). Hotkeys
  de sistema via pyautogui são pouco confiáveis nesse contexto; mover janela
  por `drag` funciona.
- `screenshot(path=<pasta do projeto>)` é o jeito de a nuvem VER a captura:
  a pasta do projeto é alcançável pela ponte; a Temp padrão não é.
- Estado deixado: janela do T2M movida para o monitor principal (225,47);
  diálogo Configuracoes fechado com Cancelar (nada salvo).

**[x] Bug report ENVIADO à Anthropic (10/08 ~18h10):** issue pública
**anthropics/claude-code#85623** —
https://github.com/anthropics/claude-code/issues/85623 — criada pelo Claude
preenchendo o formulário no Chrome do Leonardo (extensão Claude in Chrome),
com confirmação do Leonardo antes do envio. Sem prints anexados (os originais
não foram salvos); o texto avisa que podem ser recapturados sob demanda.
Fonte do texto: `bug-report-anthropic.md` na raiz do projeto. Acompanhar
respostas no issue.

**Pendências que restam:** (1) itens de "Publicação" e nomenclatura abaixo;
(2) melhoria do screenshot multi-monitor (`ImageGrab.grab(all_screens=True)`).

Nota de 10/08 ~17h55: a versão do app foi obtida com o PRÓPRIO plugin
navegando em Configurações do Windows → Aplicativos instalados → Claude →
Opções avançadas (o app Claude não mostra a versão na própria UI de
Configurações). Validados em uso real também `type_text` e `scroll`; o
`scroll` de roda não rolou o painel do modal de configurações do Claude
(rolou a sidebar) — arrastar a barra de rolagem com `drag` funcionou.
Durante a sessão o usuário ligou o "uso do computador" nativo do app
(ferramentas `computer_*` apareceram na ponte) — coexistiu sem conflito com
o plugin.

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
- Versão atual: 0.8.2 (instalada como plugin no app desktop em 10/08/2026 ~16:38)

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

## Foco de janela: o Windows bloqueia processo em segundo plano (v0.8.1)

`pygetwindow.activate()` falhou em uso real com **erro 183** — o Windows impede
que um processo que não está em primeiro plano roube o foco (proteção contra
apps que se impõem). Como o servidor MCP roda em segundo plano, isso sempre vai
acontecer.

`_forcar_frente()` tenta, em cascata: restaurar se minimizada e pedir foco;
`AttachThreadInput` na thread em primeiro plano (o Windows então libera a troca);
e, por último, apenas **elevar** a janela com `SetWindowPos` sem ativar — não dá
foco de teclado, mas coloca a janela por cima, que é o suficiente para clique por
coordenadas. A verificação `_window_at_point` continua sendo o juiz final: se o
alvo não estiver sob o ponto, aborta.

Consequência prática: **clicar** costuma funcionar; **digitar** pode exigir que a
janela tenha foco de teclado — nesse caso, clicar nela uma vez antes resolve.

## Consentimento é do aplicativo anfitrião (v0.8.0) — decisão de arquitetura

Ideia do Leonardo, e ele estava certo: se o app do Claude já tem configuração de
aprovação (manual / automática / ignorar tudo), por que o servidor abre um
**segundo** pedido? No MCP quem media o consentimento é o cliente; o servidor
expõe capacidades e executa. O popup próprio duplicava a pergunta, ignorava a
escolha já feita pelo usuário, e — não por acaso — foi a origem de quase todos os
problemas de 10/08 (contexto gráfico, monitor errado, timeouts, travamento).

Modo padrão passou a ser `host`: sem pedido próprio. `T2M_APPROVAL_MODE` aceita
`host` (padrão), `ask` (barreira própria, para clientes que não mediam) e `auto`.
Sair de `ask` exige confirmação do usuário; entrar em `ask` é livre.

**O que foi mantido, porque não é consentimento e sim segurança de execução:**
verificação de que a janela alvo está sob o ponto antes de clicar, log de
auditoria (agora registra `action_executed` com o modo de consentimento e a
janela), mascaramento de texto sensível, e o failsafe do PyAutoGUI.

Para submissão na loja, esta é uma história melhor: "o plugin delega o
consentimento ao anfitrião, como o MCP prevê, e acrescenta auditoria e
verificação de alvo" — em vez de "o plugin abre diálogos próprios do sistema".

## Popup de aprovação (modo `ask`): diálogo nativo, não tkinter (v0.7.0)

O `tkinter.Tk()` **trava** quando o servidor roda em contexto restrito — provado
pela ferramenta `diagnostico` (não retorna em 8s). Isso aconteceu tanto com o
servidor registrado por configuração quanto, mais tarde, com o plugin. Sintoma
para o usuário: nenhuma janela aparece em nenhum monitor e a ação expira.

Em v0.7.0 o `approval.py` usa primeiro a **caixa de diálogo nativa do Windows**
(`MessageBoxTimeoutW` via ctypes) — chamada direta ao user32, sem inicializar
toolkit gráfico. Mapeamento dos botões: **Sim** = sempre permitir nesta janela,
**Não** = permitir uma vez, **Cancelar** = negar. O tkinter ficou como
alternativa, e se ambos falharem o retorno é `deny`.

> Comportamento correto observado no meio do problema: mesmo sem conseguir
> perguntar, o plugin **não executou nada** — falhou fechado. Vale citar isso
> numa eventual submissão de segurança.

## ⚠️ INSTALAR COMO PLUGIN, NÃO PELO claude_desktop_config.json

**Descoberta de 10/08/2026, com evidência da ferramenta `diagnostico`.** Tentamos
registrar o servidor apontando para a pasta do projeto (via
`claude_desktop_config.json`) para agilizar a iteração. O servidor sobe e as
ferramentas de leitura funcionam, **mas o popup de aprovação nunca aparece**.

O `diagnostico` mostrou por quê: nesse contexto o processo roda com
`SESSIONNAME` vazio e `cwd = C:\WINDOWS\system32`, e tanto criar um `tkinter.Tk()`
quanto abrir o popup **travam** (não retornam em 8s) — o processo não tem acesso
à área de trabalho interativa. Instalado **como plugin**, o mesmo código exibe os
popups normalmente (validado em uso real).

Consequência prática: sem popup não há como aprovar nada, e nem como trocar para
o modo `auto` (essa troca também exige confirmação por popup). Portanto: **use a
instalação como plugin**. O `.mcp.json` e o `configurar-mcp.ps1` continuam no
repositório para uso com o Claude Code (terminal), onde o servidor roda na sessão
interativa do usuário.

Ciclo de atualização do plugin (aprendido na prática): **desinstalar** o plugin
antigo → "Fazer upload de plugin" com o zip novo → **fechar o app pela bandeja**
e reabrir. Sem desinstalar, o upload não substitui; sem reiniciar, o processo
antigo continua no ar.

⚠️ **Sempre CONFERIR a instalação** (lição de 10/08, tarde): durante a
atualização para 0.8.2 o upload não se concretizou e o plugin ficou
simplesmente **desinstalado** sem ninguém perceber — a lista em Configurações →
Plugins só mostrava o "Engineering" da Anthropic. Sintoma na sessão: nenhuma
ferramenta `plugin_t2m-desktop-control` aparece, por mais que se recarregue.
Depois de qualquer upload, abrir Configurações → Plugins e confirmar que
"T2m desktop control" está na lista e habilitado.

## As ferramentas de uma sessão são fixadas quando ela COMEÇA (descoberta 10/08)

Instalar/reinstalar o plugin **não** faz as ferramentas aparecerem numa
conversa já aberta. Evidências da sessão da tarde de 10/08: (a) com o plugin
desinstalado, a skill `/qa-desktop` continuava listada na sessão antiga —
retrato de quando a sessão nasceu; (b) após reinstalar a 0.8.2 e reiniciar o
app, a sessão antiga seguiu vendo só as 8 ferramentas da ponte, mesmo com
vários refreshes ao longo de minutos.

Regra prática: mexeu no plugin (instalou, atualizou, reinstalou) → **abrir uma
tarefa/conversa NOVA** para ver o efeito. A nota antiga de que "recarregar
costuma resolver" vale para atraso de carga dentro de uma sessão que já nasceu
com o plugin instalado, não para plugin instalado depois.

Bônus descoberto no mesmo dia: o Claude consegue montar o zip do plugin
sozinho, da nuvem, lendo a pasta do projeto pela ponte e gravando o zip de
volta (ex.: `t2m-desktop-control-0.8.2.zip` na raiz do projeto). Conteúdo do
zip: `.claude-plugin/`, `server/` (sem `__pycache__`), `skills/`,
`requirements.txt`, `README.md`, `LICENSE`, `INSTALL-desktop.md`.

> Melhoria futura para robustez: tirar o popup do processo do servidor e usar um
> pequeno aplicativo de aprovação rodando na sessão do usuário (bandeja),
> conversando com o servidor por arquivo ou porta local. Resolveria de vez,
> inclusive se o servidor rodar como serviço.

## Restrições importantes

- **Windows only** (usa pygetwindow, atalhos do Windows).
- **Precisa rodar localmente**, não na nuvem. No app desktop, a tarefa tem que
  estar no modo "Na sua máquina"; no Claude Code, já é local por natureza.

## Pendências / próximos passos

**[x] TESTE CONCLUÍDO (10/08 ~17h50):** `click` com `window` confirmado no
botão "Configuracoes" do T2M Security Manager — ver seção "RETOMADA
CONCLUÍDA" no topo. Evidências: `qa-resume-01.png` / `qa-resume-02.png`.

**10/08 ~17h — tentativa numa sessão nuvem, ferramentas não apareceram.
Diagnóstico feito, causa provável: sessão nasceu antes do plugin subir.**
Sintoma NOVO documentado: a skill `/qa-desktop` aparecia na sessão, mas
NENHUMA ferramenta `plugin_t2m-desktop-control` (a ponte ficou nos 8 tools
básicos por vários refreshes ao longo de minutos). Ou seja: skill visível ≠
servidor MCP proxiado — são canais separados.

O que foi VERIFICADO e está OK (não perder tempo re-checando):
- Configurações → Plugins: "T2m desktop control" instalado, habilitado,
  atualizado (print do usuário).
- Zip 0.8.2 e `.claude-plugin/plugin.json`: corretos, `mcpServers` declarado.
- `server/server.py` da 0.8.2: sintaxe OK (py_compile), 16 `@mcp.tool`,
  imports de topo só stdlib+fastmcp (pyautogui é lazy).
- O servidor 0.8.2 INICIA sem erro: `t2m_audit.log` do projeto tem
  `server_start versao 0.8.2 mode host` às 15:48 (execução a partir da pasta).

Não foi possível conferir o audit log do plugin instalado (fica na pasta do
plugin em AppData, que a ponte não alcança — o padrão do caminho é relativo a
`__file__`). Pistas para a próxima sessão: (1) aba "Conectores" na tela do
plugin deve listar `t2m-desktop-control`; (2) abrir conversa NOVA com o app
já reiniciado e chamar `get_approval_status`.

**CAUSA ENCONTRADA (10/08 ~17h10, print do usuário):** na aba "Conectores"
da tela do plugin, `t2m-desktop-control` aparece listado mas **não
conectado** — há um botão "Instalar" ao lado e o texto "Conecte cada uma
para que Claude possa usá-las". Ou seja: instalar o plugin NÃO conecta o
servidor MCP automaticamente; é um passo separado, por conector. E o botão
"Instalar" estava **redirecionando para o Diretório geral de conectores**
em vez de instalar o servidor local do plugin (possível bug do app desktop).
Isso explica o sintoma inteiro: skill visível (skills não dependem do
servidor), ferramentas ausentes (servidor nunca subiu).

CONFIRMADO em seguida: o "Instalar" só abre o Diretório geral de conectores
(loja pública) — um plugin enviado por arquivo não está lá, então o fluxo é
um beco sem saída. Toggle off/on + reinício pela bandeja + conversa nova:
**nada funcionou** (testado pelo Leonardo, 10/08 ~17h30). Conclusão:
**BUG DO APP DESKTOP** — plugin local com `mcpServers` fica preso em
"não conectado" sem caminho de conexão na interface. Reportar à Anthropic.
Nota: nos testes da manhã de 10/08 as ferramentas funcionaram — então ou o
conector foi conectado naquela época por outro caminho, ou o app mudou de
comportamento entre as versões.

**PLANO B1 (em teste): voltar ao `claude_desktop_config.json`, agora viável.**
O veto da seção "⚠️ INSTALAR COMO PLUGIN" tinha um único motivo: o popup de
aprovação travava nesse contexto (sem área de trabalho interativa). Com o
modo `host` (padrão desde v0.8.0) NÃO EXISTE MAIS POPUP — o consentimento é
do app anfitrião — então o bloqueio documentado deixou de se aplicar.
Registro sugerido (em `%APPDATA%\Claude\claude_desktop_config.json`):
`mcpServers.t2m-desktop-control = { command: "python", args:
["C:\\Users\\LeonardoJoseCordeiro\\Documents\\t2m-desktop-control\\server\\server.py"],
env: { T2M_APPROVAL_MODE: "host" } }`. Depois fechar pela bandeja, reabrir,
conversa nova, `get_approval_status`. Riscos conhecidos do contexto
(SESSIONNAME vazio, cwd system32): leitura funcionava; ações sem popup nunca
foram testadas nesse contexto — o teste do `click` dirá.
**PLANO B2 (fallback já validado):** Claude Code no terminal com `.mcp.json`
/ `configurar-mcp.ps1` — roda na sessão interativa do usuário.

**B1 APLICADO em 10/08 ~17h27.** O registro foi gravado no config. Detalhe
importante descoberto: o app desktop é instalado via Microsoft Store
(pacote MSIX), então o `claude_desktop_config.json` REAL fica na pasta
virtualizada:
`C:\Users\LeonardoJoseCordeiro\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
(não no %APPDATA% clássico). A ponte do Cowork não alcança essa pasta
(protegida); a edição foi feita pelo Claude na nuvem e salva manualmente
pelo Leonardo. Próximo passo: reiniciar pela bandeja → conversa nova →
`get_approval_status` (deve responder 0.8.2) → teste do `click` com
`window` no botão Configurações do T2M Security Manager.


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
