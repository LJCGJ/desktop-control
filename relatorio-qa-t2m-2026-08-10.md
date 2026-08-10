# Relatório de QA — T2M Security Manager v4.2 (MCP Edition) — 10/08/2026

**Executado por:** Claude, via plugin `t2m-desktop-control` (skill `qa-desktop`)
**Ambiente:** Windows, tela 1366×768, janela do app 940×750 em (213, 0)
**Modo:** exploratório, sem autenticação (por decisão do solicitante)

## Resumo

Primeira passada exploratória na tela inicial e na tela de Histórico de execuções.
O aplicativo abriu, respondeu aos comandos e navegou entre telas sem travar.
Foi encontrado **1 bug confirmado** (corrupção de caracteres acentuados na
exibição de dados) e registradas **3 observações** que merecem verificação do
desenvolvedor. As áreas que executam ações reais (iniciar teste, remover script,
Copilot IA) **não foram testadas** por serem potencialmente destrutivas ou
onerosas — ver "Cobertura e lacunas".

## Casos de teste

| # | Caso | Status | Observação |
|---|------|--------|------------|
| 1 | Abrir o app e renderizar a tela inicial | Passou | Todos os painéis visíveis e legíveis |
| 2 | Abrir a tela de Histórico pelo botão do cabeçalho | Passou | Janela "Histórico de execuções" abre corretamente |
| 3 | Exibir dados de execuções passadas no histórico | Falhou | Ver Bug #1 (acentuação corrompida) |
| 4 | Fechar o Histórico e retornar à tela principal | Passou | Retorno limpo à janela principal |

## Bugs encontrados

### Bug #1: Caracteres acentuados aparecem corrompidos no detalhe do histórico

**Severidade:** Média
**Ambiente:** T2M Security Manager v4.2 (MCP Edition) | Windows | 1366×768

**Passos para reproduzir:**
1. Abrir o T2M Security Manager
2. Clicar em "Histórico" no cabeçalho
3. Observar o painel de detalhes da execução, campo "Objetivo"

**Resultado esperado:**
O texto do objetivo deve ser exibido com a acentuação original, por exemplo:
`conte os arquivos incluindo as subpastas e diga quantos são no total`

**Resultado obtido:**
O texto aparece corrompido:
`conte os arquivos incluindo as subpastas e diga quantos sÃEo no total`

**Evidência:** `qa-03-historico.png`

**Observações:**
Padrão clássico de *mojibake*: o texto foi gravado em UTF-8 e está sendo lido ou
renderizado como latin-1/cp1252 (a sequência `são` = `0xC3 0xA3` aparece como
`Ã` + outro caractere). Vale verificar a codificação em três pontos: na gravação
do registro, na leitura do arquivo/banco, e na exibição no widget. O impacto vai
além da tela — o log exportado provavelmente carrega a mesma corrupção, o que
prejudica auditoria e relatórios entregues a clientes.

## Observações (não confirmadas como bug)

**Obs. 1 — Alta proporção de execuções "NAO RODOU".** Das 13 linhas visíveis no
histórico, 10 estão marcadas em vermelho como "NAO RODOU", e o detalhe mostra
`Nao chegou a rodar: True`. Pode ser resultado esperado dos seus próprios testes,
mas se não for, indica uma falha recorrente na inicialização das execuções que
merece investigação.

**Obs. 2 — Coluna "Recusas" vazia em todas as linhas.** Nenhuma das execuções
listadas mostra valor nessa coluna. Pode ser legítimo (nenhuma recusa ocorreu) ou
indicar que o campo não está sendo populado. Vale confirmar com uma execução que
sabidamente gere uma recusa.

**Obs. 3 — Rótulos da interface sem acentuação.** Toda a interface usa texto sem
acentos: "Automacao", "seguranca", "Historico", "Configuracoes", "Saida dos
scripts e raciocinio da IA", "Exportar Log Tecnico", "Salvar configuracoes ao
sair". Diferente do Bug #1, isso parece ser ASCII escrito deliberadamente no
código-fonte, não corrupção. Não afeta o funcionamento, mas afeta a percepção de
acabamento do produto — especialmente num software entregue a clientes.

**Obs. 4 — Coluna extra sem cabeçalho.** A tabela do histórico tem uma coluna
vazia à direita de "Alvo", sem título. Provavelmente sobra de layout.

## Cobertura e lacunas

O que **não** foi testado nesta rodada, e por quê:

- **`▶ INICIAR TESTE`** — dispararia um scan real contra a URL alvo
  (`https://www.google.com/`). Ação com efeito externo; requer sua autorização
  explícita e uma URL de teste apropriada.
- **`Remover`** (scripts) — ação destrutiva, apagaria um arquivo de script.
- **`Limpar historico`** — ação destrutiva, apagaria o histórico que serviu de
  evidência para este relatório.
- **`T2M Copilot (IA)` e `Analisar saida com a IA`** — podem consumir créditos de
  provedores de IA (Groq/Gemini aparecem no histórico).
- **`Configurações`, `?` (ajuda) e `Tema Escuro`** — não alcançados nesta sessão;
  ficam para a próxima rodada.
- **Fluxos autenticados** (campo Token JWT, botão Login) — excluídos por decisão
  do solicitante nesta rodada.
- **Validações de campo** (URL inválida, token malformado) — não exercitadas.

## Sugestão para a próxima rodada

Priorizar, nesta ordem: (1) confirmar o Bug #1 também no log exportado, já que
isso amplia a severidade; (2) explorar `Configurações` e `Tema Escuro`, que são
seguros; (3) com sua autorização e uma URL de teste controlada, exercitar o fluxo
completo de `INICIAR TESTE`, que é o coração do produto e onde os defeitos mais
caros costumam estar.
