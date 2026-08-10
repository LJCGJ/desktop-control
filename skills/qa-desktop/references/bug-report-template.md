# Template de relatório de bug

Use este formato para cada bug encontrado. A meta é que o desenvolvedor consiga
reproduzir o problema sem precisar te perguntar nada. Um bug que não pode ser
reproduzido raramente é corrigido.

```
### Bug #<n>: <título curto e específico>

**Severidade:** Crítica | Alta | Média | Baixa
**Ambiente:** <app e versão, se conhecida> | Windows | <resolução da tela>

**Passos para reproduzir:**
1. <passo 1>
2. <passo 2>
3. <passo 3>

**Resultado esperado:**
<o que deveria acontecer>

**Resultado obtido:**
<o que de fato aconteceu>

**Evidência:**
<caminho do screenshot, ex: ./evidencias/bug-1-erro-login.png>

**Observações:**
<qualquer detalhe extra: só acontece em certas condições, intermitente, etc.>
```

## Como escolher a severidade

A severidade descreve o impacto no usuário, não o quão fácil é corrigir. Ajuda o
time a priorizar.

- **Crítica:** trava o app, corrompe dados, ou bloqueia completamente uma
  funcionalidade principal. Não há como contornar.
- **Alta:** funcionalidade importante quebrada, mas existe algum contorno; ou o
  problema atinge muitos usuários.
- **Média:** funcionalidade secundária com defeito, ou problema com contorno
  fácil.
- **Baixa:** cosmético, texto errado, desalinhamento — não atrapalha o uso.

## Dicas para um bom título

O título deve dizer *o quê* e *onde*, de forma que dê para entender o bug só de
ler. Compare:

- Ruim: "Erro no login"
- Bom: "Login trava com tela branca ao usar e-mail com maiúsculas"

- Ruim: "Botão não funciona"
- Bom: "Botão 'Salvar' do cadastro fica inativo mesmo com todos os campos preenchidos"
