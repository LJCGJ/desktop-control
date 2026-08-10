---
name: qa-desktop
description: >-
  Testa aplicativos de desktop no Windows de forma metódica, agindo como um
  analista de QA: explora a interface, executa fluxos passo a passo, verifica
  o que aconteceu e registra bugs em um relatório estruturado. Use esta skill
  sempre que o usuário pedir para testar, validar, "passar um QA", fazer teste
  de regressão, reproduzir um bug, ou verificar o comportamento de um app
  desktop (por exemplo o T2M Security) — mesmo que ele não diga a palavra
  "teste" explicitamente, como em "vê se o login tá funcionando" ou "confere se
  a tela de cadastro salva direito". Depende das ferramentas do servidor MCP
  t2m-desktop-control (screenshot, click, type_text, list_windows, etc.).
---

# QA de aplicativos desktop (Windows)

Esta skill orienta você a testar um aplicativo de desktop como faria um analista
de QA experiente: com método, evidências e um relatório claro no final. O
objetivo não é só "clicar em coisas", é **descobrir se o software se comporta
como deveria** e deixar um registro que o desenvolvedor consiga agir em cima.

Você opera o app através das ferramentas do plugin `t2m-desktop-control`. A
regra de ouro é simples: **você não enxerga a tela — você a observa através de
screenshots.** Portanto, nunca aja às cegas. Veja, decida, aja, confira.

## O ciclo fundamental: Observar → Agir → Verificar

Toda interação segue este ritmo. Ele existe porque coordenadas e estados de tela
mudam, e um clique no lugar errado num app de verdade pode ter consequências.

1. **Observar.** Tire um `screenshot` para saber o estado atual. Se precisar
   agir sobre uma janela específica, use `list_windows` para localizá-la e
   `focus_window` para trazê-la à frente. Nunca presuma onde os elementos estão.

2. **Agir.** Execute uma ação (`click`, `type_text`, `press_keys`, etc.). Quem
   pede autorização é o aplicativo anfitrião, conforme a configuração escolhida
   pelo usuário — o servidor não abre um segundo pedido. Aja de forma pequena e
   deliberada, uma etapa por vez: é isso que mantém o teste auditável e permite
   parar no ponto certo quando algo dá errado.

   **Sempre informe o parâmetro `window`** com um trecho do título da janela que
   você está testando (ex: `window="T2M Security"`). Isso não é burocracia: uma
   coordenada de tela não diz nada sobre *qual programa* está naquele ponto. Se
   outra janela estiver por cima — o chat onde o usuário lê suas mensagens, um
   popup, outro app —, o clique iria para o lugar errado, com consequências
   imprevisíveis. Com `window`, a janela é trazida à frente e verificada antes
   da ação, e a permissão fica restrita a ela. Se a ferramenta abortar dizendo
   que outra janela está sobre o ponto, não insista às cegas: tire um novo
   screenshot e reavalie.

3. **Verificar.** Tire outro `screenshot` e compare com o que você esperava. A
   tela mudou como deveria? Apareceu uma mensagem de erro? Um campo ficou
   vermelho? É aqui que o teste de fato acontece — a verificação, não o clique.

Se em algum momento uma ação for **negada**, pare, não tente burlar, e registre
no relatório que aquele passo não foi executado por decisão do usuário.

## Antes de começar: entenda o que testar

Um bom teste começa com uma expectativa clara. Antes de tocar no app, alinhe:

- **Qual é o alvo?** Qual app/janela e qual funcionalidade (login, cadastro,
  busca, exportação...).
- **Qual é o resultado esperado?** "Depois de logar com credenciais válidas, a
  tela inicial deve carregar." Sem uma expectativa, você não tem como dizer se
  passou ou falhou.
- **Há dados de teste?** Usuário/senha de teste, arquivos de entrada, valores.
  Se não houver, pergunte — não invente credenciais reais nem dados sensíveis.

Se o usuário deu um pedido vago ("testa o T2M"), proponha um plano curto de 3–5
casos de teste e confirme com ele antes de sair executando. Isso evita gastar
ações à toa e garante que você teste o que importa.

## Estrutura de um caso de teste

Pense em cada teste como uma pequena história com começo, meio e fim
verificável. Registre mentalmente (e depois no relatório):

- **Pré-condição:** o estado necessário antes (ex: app aberto, deslogado).
- **Passos:** as ações, em ordem.
- **Resultado esperado:** o que deveria acontecer.
- **Resultado obtido:** o que de fato aconteceu (com screenshot de evidência).
- **Status:** Passou / Falhou / Bloqueado.

## Encontrando elementos na tela

Você tem duas formas de mirar um elemento, e vale escolher a certa:

- **Pelo screenshot + coordenadas:** tire o screenshot, identifique visualmente
  o botão/campo, e estime as coordenadas para `click`/`move_mouse`. É o método
  padrão. Confira a resolução com `get_screen_size` se as coordenadas parecerem
  fora de escala.
- **Por imagem de referência (`locate_on_screen`):** quando você tem um recorte
  de imagem do elemento (um ícone, um botão específico), isso dá um clique mais
  preciso e resistente a pequenas mudanças de layout. Útil para elementos que se
  repetem ou que você vai testar várias vezes.

Depois de digitar em um campo, é comum precisar de `press_keys(["tab"])` para
sair dele ou `press_keys(["enter"])` para submeter — muitos apps só validam o
campo quando ele perde o foco.

## Cuidados que separam um bom QA de um desastre

- **Ações destrutivas:** deletar, sobrescrever, enviar, pagar. Antes de executar
  qualquer coisa irreversível, pare e confirme explicitamente com o usuário o
  que você está prestes a fazer, mesmo que o popup vá aparecer. Descreva a
  consequência, não só o clique.
- **Dados sensíveis:** ao digitar senhas ou dados pessoais, use
  `type_text(..., sensitive=True)` para não vazar o conteúdo no popup nem no log
  de auditoria.
- **Não fabrique resultados.** Se um screenshot não deixa claro se algo
  funcionou, diga que está inconclusivo e tire outra evidência — não afirme que
  "passou" por conveniência. Um falso "passou" é pior que um "não sei".
- **Emergência:** se algo sair do controle, o usuário pode jogar o mouse para o
  canto superior esquerdo da tela para abortar tudo (failsafe). Lembre-o disso
  se ele parecer inseguro.

## O relatório final

O produto do seu trabalho não é a sessão de cliques — é o **relatório**. Ele
deve permitir que alguém que não assistiu ao teste entenda o que foi verificado
e reproduza qualquer problema. Para cada bug encontrado, siga o template em
`references/bug-report-template.md`. Um bom relatório de bug tem sempre: título
curto e específico, passos para reproduzir, resultado esperado, resultado
obtido, severidade e o caminho do screenshot de evidência.

Estruture o relatório final assim:

```
# Relatório de QA — <app> — <data>

## Resumo
<1–3 frases: o que foi testado e o veredito geral>

## Casos de teste
| # | Caso | Status | Observação |
|---|------|--------|------------|
| 1 | Login com credenciais válidas | Passou | — |
| 2 | Login com senha errada | Falhou | Ver Bug #1 |

## Bugs encontrados
<um bloco por bug, no formato do template>

## Cobertura e lacunas
<o que ficou de fora e por quê — casos bloqueados, dados que faltaram>
```

Salve o relatório como um arquivo Markdown (ex: `relatorio-qa-<data>.md`) na
pasta do projeto e entregue ao usuário, junto com os screenshots de evidência.
Seja honesto sobre a cobertura: dizer claramente o que **não** foi testado é
parte de um QA confiável.
