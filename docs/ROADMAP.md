# Roadmap até o v1.0 — `MasterTool Rankine Bridge`

> **Status deste documento:** NORMATIVO E VIGENTE. Substitui
> [`10-roadmap.md`](10-roadmap.md) e [`14-ladder-roadmap.md`](14-ladder-roadmap.md)
> como plano corrente. Os dois continuam válidos como registro histórico do
> planejamento anterior e recebem cabeçalho `HISTÓRICO`.
>
> O estado **vigente** não é descrito aqui. Ele fica em
> [`CURRENT_STATUS.md`](CURRENT_STATUS.md), que é a única fonte canônica.
> Este documento diz para **onde** se vai; o outro diz **onde se está**.

---

## 1. O que "100% completo" significa

Um roadmap sem critério de parada não termina. O v1.0 está completo quando o
sistema executa esta cadeia inteira, de ponta a ponta, sem operação manual
oculta:

```text
documentação de engenharia
    → modelo normalizado do sistema
    → plano de criação ou alteração
    → validação de riscos e permissões
    → cópia descartável do projeto
    → criação/alteração controlada
    → save_as
    → reabertura independente
    → extração completa
    → diff estrutural e textual
    → compilação
    → relatório de evidências
    → aprovação humana
    → artefato final para revisão no MasterTool
```

E quando ele consegue: compreender projetos existentes; responder perguntas
técnicas; identificar dependências e impactos; gerar documentação; propor
alterações; criar novos projetos; alterar projetos existentes; gerar ou
importar lógica textual e gráfica; compilar e verificar; produzir um pacote de
auditoria.

### O que v1.0 nunca fará

Fora de escopo por decisão permanente, não por falta de tempo — a política de
[`08-safety.md`](08-safety.md) e do contrato [`28`](28-contrato-escrita-controlada-mastertool-x.md)
continua valendo integralmente:

- modificar o arquivo original de um projeto;
- download, login, modo online, start/stop, force, acionamento de saídas;
- qualquer atuação física sobre o CLP;
- aplicação automática de mudança crítica sem aprovação humana.

### A definição operacional

> **Tudo que é suportado está formalmente qualificado; tudo que não é suportado
> é detectado e recusado explicitamente.**

Suportar toda extensão proprietária que a Altus venha a criar **não** é
critério de v1.0. Recusar com diagnóstico nomeado o que não se suporta **é**.

---

## 2. A regra que governa este roadmap

Nenhuma fase deste roadmap pode ser fechada por declaração. A escala de
maturidade de [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md) é normativa:

```text
discovered           API identificada por reflexão/catálogo
field_proven         executada uma vez contra o produto, com evidência real
repeatable           repetida em execuções independentes
template_qualified   validada sobre um Template Profile específico
version_qualified    validada sobre uma versão específica do MasterTool
production_qualified passou por testes negativos, falhas induzidas e escala
```

**O planner de produção emite apenas operações `production_qualified`.** Os
níveis inferiores existem para laboratório e probes.

Consequência direta e incontornável: **as promoções acima de `discovered`
exigem execução real do MasterTool, com operador humano presente.** Nenhuma
quantidade de trabalho offline promove uma operação. Trabalho offline constrói
o instrumento de medida; a medição é sessão de campo.

---

## 3. Correções estruturais que antecedem funcionalidade nova

Oito itens, todos anteriores a qualquer capacidade nova.

| # | Correção | Onde vive |
|---|---|---|
| 2.1 | Fonte canônica única de estado | [`CURRENT_STATUS.md`](CURRENT_STATUS.md) |
| 2.2 | Template Profile substitui baseline posicional | `schemas/template_profile.json` |
| 2.3 | Execution Capability Manifest substitui fase literal acumulada | `schemas/execution_capability_manifest.json` |
| 2.4 | Escala de maturidade de seis níveis | [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md) |
| 2.5 | Adaptadores por geração do MasterTool | `src/mastertool_bridge/adapters/` |
| 2.6 | Project IR unificado | `src/mastertool_bridge/ir/` |
| 2.7 | Evidence Bundle imutável | `src/mastertool_bridge/evidence/` |
| 2.8 | Apresentação, versionamento, licença e distribuição | `pyproject.toml`, `LICENSE`, `.github/` |

### 2.1 Fonte canônica única

Antes de R0 havia documentos ativos afirmando que a compilação não estava
implementada, que a importação estava bloqueada, que nenhuma API de escrita
fora confirmada e que o projeto era somente leitura — todas contraditas por
W1 a W9. A correção **não** é editar o registro histórico: relatórios de
execução são evidência e são imutáveis. A correção é hierarquia:

- `CURRENT_STATUS.md` é a única fonte do estado vigente;
- relatórios de execução (`33`, `34`, `37`, `39`, `41`, `42`, `43`, `46`, `47`,
  `48`, `49`) permanecem **imutáveis**, como evidência datada;
- documentos superados recebem cabeçalho `HISTÓRICO` que aponta para o
  substituto, sem apagar o conteúdo;
- o README consome um resumo do estado canônico;
- um teste automatizado verifica links, cabeçalhos e afirmações contraditórias.

> **Desvio deliberado do plano original:** os documentos numerados **não** são
> movidos para `docs/history/`. Seus caminhos estão citados em mensagens de
> commit, em relatórios de execução e nos próprios artefatos de run — mover os
> arquivos quebraria a cadeia de evidência para ganhar arrumação. A
> classificação é feita por cabeçalho e por
> [`docs/history/README.md`](history/README.md), não por movimentação.

### 2.2 Template Profile

A base do projeto foi trocada em 2026-07-31 por um template com cartões de
I/O, o que invalidou toda identidade posicional: contagem de nós, hash
estrutural e `node_path`. `node_path` é caminho de **índices** — um cartão a
mais sob o `Device` desloca o índice e `root/1/0/0` deixa de apontar para o
`Application`.

**`node_path` deixa de ser identidade e passa a ser diagnóstico.** O seletor
semântico combina nome, tipo, `type_guid`, ancestralidade semântica,
aplicação, assinatura estrutural e cardinalidade esperada. `object_guid` entra
apenas onde já foi medido como estável — e há medição registrada de que ele
**não** é estável entre sessões.

### 2.3 Execution Capability Manifest

Fases literais (`W1.3A`, `W7`, `W9`) são excelentes para probe e não escalam
para produção: cada projeto novo viraria uma fase codificada em Python. As
fases literais **permanecem** para qualificação; a produção passa a usar um
manifesto por execução, validado por hash, que declara plano, projeto de
origem, template profile, saída, operações permitidas com `expected_before_sha256`,
risco máximo e exigência de aprovação.

O comportamento *fail-closed* é preservado: o executor recusa plano sem hash
correspondente, operação não comprovada, alvo ambíguo, conteúdo anterior
divergente ou saída dentro do caminho de origem.

### 2.5 Adaptadores por geração

Leitura foi construída sobre MasterTool IEC XE 3.63/3.70; autoria foi provada
no MasterTool X 4.1.0.11. Equivalência entre produtos **não se presume**.
Cada adaptador declara recursos suportados, seletores, métodos de exportação e
de autoria, propriedades qualificadas, limitações, faixa de versão e template
profiles compatíveis. Nada de `if version == ...` espalhado pelo código.

---

## 4. Fases

Cada fase tem gate de saída explícito. Fase sem gate cumprido não fecha, e a
versão correspondente não é emitida.

### R0 — Consolidação e rebaseline · `v0.2.0-alpha.1`

Tornar o estado atual confiável antes de continuar.

**Entregáveis:** `CURRENT_STATUS.md`; este roadmap; matriz de capacidades;
matriz de compatibilidade; modelo de segurança consolidado; documentação
histórica classificada; README corrigido; versão corrigida; licença definida;
Template Profile novo com I/O; CI offline; proteção de branch documentada.

**Testes obrigatórios:** validação de todos os links internos; ausência de
documento ativo contraditório; suíte Python em ambiente limpo; build do
pacote; validação de schemas; varredura de dado de cliente; verificação de
arquivos grandes e binários indevidos.

**Gate:** baseline identificada por hash + documentação coerente + CI verde +
capability matrix publicada.

### R0b — Template Profile e seletor semântico

Congelar o perfil do template novo por medição read-only e substituir a
seleção posicional. **A medição da árvore exige sessão de campo.**

**Gate:** nenhum caminho de escrita depende de `node_path`; o preflight recusa
seletor ambíguo (0 ou ≥2 alvos) com diagnóstico nomeado.

### R1 — Repetibilidade da fábrica atual · `v0.2.0`

Transformar W7–W9 de provas individuais em operações repetíveis.

**Critérios:** ≥10 execuções independentes; diretórios de saída distintos;
entrada idêntica; plano semanticamente idêntico; árvore, textos e build
equivalentes; projeto de entrada intacto; nenhum arquivo temporário órfão;
journal consistente; nenhuma dependência da ordem interna de GUIDs.

**Testes negativos:** saída já existe; hash de projeto incorreto; template
incompatível; objeto já existente; biblioteca ausente; build com erro
intencional; interrupção antes do `save_as`; interrupção depois do `save_as`;
falha na reabertura; caminho de saída sem permissão.

**Gate:** as **14** operações do `EXECUTOR_CONTRACT` passam de `field_proven`
para `repeatable` e `template_qualified`. (Dizia treze; o número correto vem do
código, e a correção está em `CURRENT_STATUS.md` §2.)

### R2 — W10: alteração transacional de objeto existente · `v0.3.0`

Provar que o sistema **altera**, e não apenas cria. Marco crítico.

**Operações:** `replace_declaration`, `replace_implementation`,
`replace_documents`, `configure_existing_task`, `rename_object` (esta última
adiável se o produto provocar efeitos indiretos difíceis de controlar).

**Invariantes:** arquivo de entrada intacto byte a byte; somente alvos
listados mudam; cada alvo tem `before_sha256`; alteração inesperada invalida a
execução; build com erro invalida o artefato; a saída nunca substitui a origem
automaticamente; reabertura obrigatória; diff estrutural **e** textual.

**Gate:** uma alteração existente é atômica do ponto de vista do artefato
aprovado, verificável, reprodutível e reversível.

> **Nota de 2026-08-02 — o que *reversível* exigiu do Evidence Bundle.** O
> layout de §2.7 tinha seis seções e nenhuma delas guardava o **texto**
> anterior de um objeto alterado: o pacote registrava o `sha256` dele, e hash
> não reconstrói texto. Um pacote que registra uma mudança sem registrar como
> desfazê-la não fecha este gate. O layout ganhou a sétima seção, `rollback/`,
> com `before-texts.json` (gravado pelo `probes/46` no instante em que confere
> o hash) e `rollback-spec.json` (a spec inversa, emitida offline). Nenhum dos
> dois é obrigatório no layout — execução que só cria não tem o que reverter —
> mas plano **com** alteração e sem eles sela `sealed_incomplete`.

### R3 — Cobertura completa de IEC textual · `v0.4.0`

Alias, Union, PersistentVars, actions, transitions textuais, methods,
properties, getter/setter, interfaces, `EXTENDS`, `IMPLEMENTS`, namespaces,
atributos e pragmas. Tasks: edição de task existente, watchdog, prioridade,
cyclic, freewheeling, event, external event, parent synchron, core binding,
múltiplos programas e ordem de chamadas. Library Lock formal — detectar
biblioteca ausente, nunca baixar, nunca atualizar por conta própria,
distinguir incompatível de não instalada. Idempotência com resultado
`already_satisfied`.

**Gate:** uma aplicação ST industrial sintética criada e atualizada
integralmente, com build sem erros.

### R4 — Semântica Ladder e índice unificado · `v0.5.0`

Semântica local por network; resolução simbólica até declaração, escopo, tipo,
endereço e origem; grafo unificado ST + Ladder; evidência e confiança em cada
conclusão.

**Gate:** em projetos reais anonimizados, 100% dos elementos conhecidos
classificados, unknowns explícitos, nenhum vínculo silenciosamente inventado,
reads/writes/calls comparáveis à inspeção manual.

### R5 — FBD e SFC em leitura · `v0.6.0`

Todas as linguagens emitem o mesmo modelo: `reads`, `writes`, `calls`,
`control_flow`, `data_flow`, `evidence`, `unknowns`.

**Gate:** um projeto misto ST/Ladder/FBD/SFC produz um único grafo navegável.

### R6 — Change set, promoção e rollback · `v0.7.0`

Estados: `draft → validated → planned → authorized → executed → verified →
build_passed → awaiting_approval → approved | rejected → archived`.

Rollback, como o original nunca é alterado, significa invalidar e descartar o
artefato novo, preservar evidências e retornar ao último projeto aprovado —
**nunca** desfazer parcialmente dentro do projeto original.

**Gate:** um change set atravessa a cadeia inteira sem operação manual fora do
journal.

### R7 — Autoria gráfica controlada · `v0.8.0`

Ordem: importar POU gráfico completo → substituir POU gráfico completo →
criar POU Ladder mínimo → múltiplas networks → alterar network existente →
repetir para FBD → só então SFC. Preferir formato canônico + importação
PLCopen a manipular objeto gráfico por API interna instável.

**Limite de segurança:** autoria gráfica ligada a função de segurança exige
revisão humana especializada. A ferramenta gera e verifica estruturalmente;
**não** declara que uma função está certificada ou segura.

### R8 — Hardware, I/O e comunicação

Leitura integral: racks, CPUs, cartões, canais, endereçamento, devices,
fieldbus, EtherNet/IP, Modbus, OPC UA, EDS/devdesc, diagnósticos, vínculo de
variável com I/O. Validações: endereço duplicado, canal sem variável, variável
sem canal, módulo ausente, revisão incompatível, gaps, overlaps.

**Escrita de hardware fica fora do executor principal no v1.0.** O sistema
propõe, gera checklist, gera arquivo de importação quando seguro e compara
antes/depois — não altera CPU, rack, bus ou dispositivo automaticamente.

### R9 — Compilador de especificação de engenharia · `v0.9.0-alpha`

`documentos brutos → extração → Engineering IR → validação de consistência →
perguntas pendentes → design congelado → Project IR → planner → change set`,
com biblioteca de padrões versionada (motor direto, motor com inversor,
válvulas, transportador, elevador, balança, dosagem, sequência, permissivos,
intertravamentos, diagnóstico, alarmes, modos, manutenção).

**Gate:** a mesma especificação gera resultados semanticamente equivalentes em
execuções independentes.

### R10 — Agentes e MCP de engenharia · `v0.9.0-beta`

Três classes de ferramenta: **leitura** (livre), **proposta** (gera
especificação, change set, plano, impacto, riscos, testes) e **execução**
(nunca chamada diretamente pelo modelo). O caminho é
`IA propõe → validador determinístico → aprovação → planner → executor isolado`.

**Gate:** uma solicitação em linguagem natural gera um change set verificável e
**nunca** escapa do catálogo determinístico de operações.

### R11 — Produto operacional

Instalador, verificador de pré-requisitos, detecção do MasterTool, CLI
estável, gerenciamento de runs, visualizador de diff e de evidências,
diagnóstico de falhas, exportação HTML/PDF, políticas por organização, logs
rotativos, atualização controlada, desinstalação limpa. Fronteiras explícitas
entre `bridge-core-python3`, `bridge-mastertool-ironpython`, `bridge-schemas`,
`bridge-adapters`, `bridge-cli`, `bridge-mcp` e `bridge-reports`.

Todo erro indica etapa, operação, objeto, projeto, versão, causa,
consequência, ação recomendada e onde estão as evidências.

### R12 — Qualificação industrial · `v1.0.0-rc1` → `v1.0.0`

Nove classes de projeto: sintético pequeno; sintético grande; real ST; real
Ladder; misto; com hardware e comunicação; com elementos não suportados;
intencionalmente corrompido; versões diferentes do MasterTool qualificadas
separadamente.

Ensaios: determinismo (n ≥ 10, comparação semântica, exclusão documentada de
GUIDs inevitavelmente variáveis); falhas induzidas (processo encerrado, disco
cheio, permissão negada, saída existente, arquivo bloqueado, library ausente,
build interrompido, projeto alterado externamente, hash inválido, schema
inválido, objeto ambíguo); escala medida, nunca arbitrada antes do teste;
segurança; qualidade.

**Cobertura exigida no v1.0:** 90% em planner, gate, schemas, diff e changes;
80% nas demais camadas testáveis; **100% dos caminhos de recusa críticos**.

**Gate final:**

```text
todos os cenários obrigatórios aprovados
+ zero falha crítica aberta
+ documentação atualizada
+ instalador reproduzível
+ compatibilidade publicada
+ rollback comprovado
+ evidências auditáveis
+ UAT aprovado
```

---

## 5. Linha de releases

| Release | Marco |
|---|---|
| `v0.2.0-alpha.1` | Rebaseline, documentação, CI e governança |
| `v0.2.0` | Fábrica atual repetível e qualificada no template |
| `v0.3.0` | Alteração transacional de ST existente |
| `v0.4.0` | Cobertura IEC textual ampliada |
| `v0.5.0` | Semântica Ladder e índice unificado |
| `v0.6.0` | FBD e SFC em leitura |
| `v0.7.0` | Change set, aprovação e rollback completos |
| `v0.8.0` | Autoria gráfica controlada |
| `v0.9.0-alpha` | Compilador de especificação de engenharia |
| `v0.9.0-beta` | Agentes, MCP e produto instalável |
| `v1.0.0-rc1` | Qualificação industrial |
| `v1.0.0` | Produto offline qualificado |

## 6. Trilhas paralelas

| Trilha | Sequência | Observação |
|---|---|---|
| A — Plataforma e segurança | `R0 → R1 → R2 → R6 → R11 → R12` | caminho crítico |
| B — Linguagens IEC | `R4 → R5 → R7` | pode avançar após o rebaseline |
| C — Modelo de engenharia | `R8 → R9 → R10` | schemas e IR podem começar cedo; **nenhuma mutação antes de R6** |
| D — Produto e qualidade | `CI → packaging → observabilidade → instalador → qualificação` | acompanha todas as fases |

## 7. Sequência recomendada

```text
1. corrigir a governança e congelar a nova baseline
2. tornar W7-W9 repetíveis
3. executar W10 sobre objeto existente
4. fechar change set, diff e evidence bundle
5. ampliar o vocabulário IEC textual
6. concluir a compreensão Ladder/FBD/SFC
7. iniciar autoria gráfica
8. construir o compilador de engenharia
9. integrar agentes apenas como camada de proposta
10. qualificar e empacotar o produto
```

A arquitetura central — planner externo, executor IronPython, allowlist, cópia
descartável, reabertura e build — **está correta e não é refeita**. O que muda
é a orientação: de uma arquitetura organizada em torno de **provas W1–W9**
para uma organizada em torno de **execuções transacionais, perfis de
compatibilidade e capacidades qualificadas**.

## 8. Estimativa de esforço

| Estrutura | Estimativa |
|---|---|
| Um desenvolvedor principal, dedicação integral | 12–18 meses |
| Dois desenvolvedores + acesso frequente ao MasterTool | 8–12 meses |
| Três pessoas, com engenharia, testes e produto separados | 7–10 meses |

A maior incerteza não está no código Python externo. Está no comportamento das
APIs internas do MasterTool, na autoria gráfica, nas diferenças entre versões,
na dependência de UI, nas bibliotecas instaladas, na repetição de testes no
software real e na qualificação em projetos industriais diferentes.

**O fator limitante é acesso ao produto com operador presente, não capacidade
de escrever código.**
