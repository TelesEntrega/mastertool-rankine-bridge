# Registro de pendências — roadmap R0 a R12

> **PROVENIÊNCIA DESTE LEVANTAMENTO.** Produzido em 2026-08-01 por auditoria
> multiagente sobre o repositório: 1 inventário mecânico, 6 varreduras (uma por
> frente do roadmap) e 6 verificações adversariais, consolidadas por um
> revisor final. **91 pendências levantadas, 0 refutadas, 10 corrigidas** pelos
> verificadores; a filtragem por veredito é aplicada em código, não por prompt.
>
> **Zero refutações não é prova de acerto** — é dado sobre a auditoria, não
> sobre o repositório: ou os levantamentos estavam corretos, ou os
> verificadores não foram suficientemente adversariais. Três itens foram
> reconferidos à mão depois, por leitura direta do código
> (`r1-gate-repeatable-aceita-2-runs`, `r3-ordem-de-chamadas` e
> `nova-higiene-regex-ponto-cego`), e os três se sustentaram — inclusive com
> um enunciado MAIS forte que o do agente no terceiro caso, onde o alvo exato
> é `probes/43_bind_program_to_task.py:105`, invisível ao verificador de
> higiene.
>
> **Nenhum item foi verificado com o MasterTool aberto.** Toda evidência é de
> repositório, e o que exige medição contra o produto está marcado como tal.
> Este documento é levantamento, não plano: ele NÃO decide ordem de execução.

## Itens já fechados depois deste levantamento

As tabelas abaixo preservam o enunciado original — elas são o registro do que
foi encontrado em 2026-08-01, e reescrevê-las apagaria a razão de o conserto
ter existido. O que fecha entra aqui, com o commit.

| ID | Fechado em | O que mudou |
|---|---|---|
| `r1-runner-n-execucoes-ausente` | `3fe6907` | `automation/repeatability.py`: orquestrador de N execuções com executor injetado, diretórios isolados, recusa de saída preexistente **antes** da primeira execução, conferência do sha da entrada antes e depois, e continuação após falha com reprovação do lote |
| `r1-comparador-so-pareado` | `3fe6907` | `compare_many`: veredito do conjunto. Equivalência contra referência (transitiva) e independência entre **todos os pares** (anti-reflexiva e não transitiva) |
| `r1-gate-repeatable-aceita-2-runs` | `4f13238` | Piso normativo (`MIN_INDEPENDENT_RUNS = 10`), herdado por monotonicidade nos níveis acima |
| `r3-ordem-de-chamadas` | `4f13238` | Ordem declarada preservada no planner e no `creation_order` do validador |
| `nova-higiene-regex-ponto-cego` | `4f13238` | Separador `\\{1,2}`; `probes/43` entrou na catraca |
| `r2-evidence-bundle-inexistente` | `6f2726e` | `evidence/bundle.py` com o layout de §2.7, manifesto com sha256 por arquivo e detecção de alteração, remoção e acréscimo após o selo |
| `r6-maquina-de-estados-inexistente` | `6f2726e` | `changes/lifecycle.py`: os dez estados do roadmap, journal com as transições recusadas, rollback como rejeição que nomeia o artefato |
| `r6-aprovacao-nao-executavel` | `6f2726e` | `changes/approval.py`: decisão amarrada ao `bundle_sha256` — pacote alterado invalida a aprovação |
| `r11-deteccao-mastertool-hardcoded` | `42179ee` | `automation/mastertool_detect.py` + `detect-mastertool`. **Parcial:** a ferramenta existe e os 15 wrappers ainda não foram migrados (ver abaixo) |
| `r11-visualizador-evidencias-ausente` | `c35c1ec` | `reports/qualification_report.py`: HTML autocontido no padrão Rankine, determinístico, com voláteis exibidos e seção de Limites |
| `r0-cobertura-nao-medida` | `24518cf` | `pytest-cov` declarado, escopo configurado, baseline de **86%** publicada em `COVERAGE_BASELINE.md` — sem meta imposta |
| `r2-before-sha256-de-alvo-preexistente` | `c66a508` + este slice | Procedência `measured` no planner, conferência no executor com status próprio (`before_hash_mismatch`), e a **fonte** do hash: `spec/modification_source.py` + `verify-modifications` conferem a spec contra um inventário MEDIDO em sessão read-only. Os nove testes negativos de R2 estão em `tests/unit/test_r2_negativos.py` |
| `r1-lote-piloto-n3` | `848af94` | **Executado no MT9000 em 2026-08-02 e aprovado.** 3/3 `build_verified` e `factory_output_verified`, 0 avisos do fabricante, 3/3 equivalentes, independência limpa nos 3 pares. Achou três defeitos mecânicos antes da qualificação (raiz lida como nó, diagnóstico não persistido, plano de build trocado) — todos corrigidos com teste. **Não promoveu nada:** o piso é 10 |
| `r6-forbidden-effects-sem-evidencia` | `24518cf` | Retirado: era proposta, não requisito (§7.1) |
| `r1-gate-repeatable-aceita-2-runs` | `4f13238` | O piso passou a ser o da norma: `MIN_INDEPENDENT_RUNS = 10` para `repeatable` e para todos os níveis acima, derivado do gate de R1. Níveis superiores herdam o piso por monotonicidade, com teste que reprova um piso decrescente |
| `r3-ordem-de-chamadas` | `4f13238` | `_check_program_calls` e o `creation_order` do validador passam a devolver a ordem **declarada**. Em IEC essa é a ordem de execução no ciclo; alfabetizar gerava um programa diferente do pedido, sem diagnóstico |
| `nova-higiene-regex-ponto-cego` | `4f13238` | O separador da regra virou `\\{1,2}`: as duas formas de barra passam a casar. `probes/43_bind_program_to_task.py` entrou na catraca de dívida — não como exceção — e duas fixtures do próprio teste, invisíveis pelo mesmo motivo, foram montadas em partes |

*Como ler:* "Fechado em" é o commit que fecha, não a data. Um item só sai desta
lista se o conserto for revertido — e aí a reversão também vira linha.



Este registro consolida **88 pendências** a partir dos 91 registros que sobreviveram à verificação adversarial nas 6 frentes (governança-produto 17, transacional 17, IEC-textual 21, gráficas 7, hardware-engenharia 9, agentes-qualificação 20). A diferença entre 91 e 88 vem de 4 fusões de itens duplicados entre frentes, 2 itens reclassificados como "não é pendência" (§5) e 3 pendências novas trazidas pelos verificadores. Das 88: **29 são offline** (dá para resolver sem abrir o MasterTool), **38 exigem sessão de campo no MT9000 com o operador presente** e **21 dependem de decisão de escopo/priorização do usuário** antes de virarem trabalho. O caminho crítico é a trilha A do roadmap (R1 → R2 → R6 → R11 → R12), e o primeiro nó real dela não é técnico e sim de gate: o validador de Template Profile hoje aprova maturidade `repeatable` com **2** execuções, enquanto o roadmap exige **≥10** — ou seja, é possível promover maturidade hoje sem ter medido o que o roadmap manda medir. Nenhum item deste registro foi verificado com o MasterTool aberto; toda evidência é de repositório.

---

## 1. Quadro geral

| Fase | Pendências | Offline | Sessão de campo | Decisão do usuário | Risco máximo |
|---|---|---|---|---|---|
| R0/R0b residual | 5 | 4 | 0 | 1 | médio |
| R1 | 8 | 5 | 2 | 1 | alto |
| R2 | 5 | 1 | 3 | 1 | alto |
| R3 | 21 | 0 | 19 | 2 | alto |
| R4 | 2 | 0 | 0 | 2 | alto |
| R5 | 3 | 0 | 2 | 1 | alto |
| R6 | 5 | 4 | 0 | 1 | alto |
| R7 | 2 | 0 | 1 | 1 | alto |
| R8 | 6 | 0 | 6 | 0 | alto |
| R9 | 3 | 0 | 0 | 3 | alto |
| R10 | 9 | 0 | 1 | 8 | alto |
| R11 | 14 | 14 | 0 | 0 | médio |
| R12 | 5 | 1 | 4 | 0 | alto |
| **Total** | **88** | **29** | **38** | **21** | **alto** |

Como ler: "Offline" é o que pode ser feito sem abrir o MasterTool — e, por regra desta auditoria, **trabalho offline nunca promove maturidade de capacidade**; "Sessão de campo" só fecha com o MT9000 aberto e o operador presente; "Decisão do usuário" é o que está bloqueado por escopo/sequência do roadmap, não por falta de trabalho técnico. Um item que precisa das duas coisas (construir offline e medir em campo) foi contado em "Sessão de campo", porque é lá que ele fecha. "Risco máximo" é o maior risco de ignorar entre as pendências daquela fase.

---

## 2. O que destrava o resto

Oito pendências que, resolvidas, desbloqueiam mais trabalho do que consomem. Estão em ordem de risco e depois de dependência.

**2.1 — O gate codificado de `repeatable` aceita 2 runs; o roadmap exige 10** (`r1-gate-repeatable-aceita-2-runs`)
`_validate_capability_qualification` só reprova a declaração `repeatable` se houver **menos de 2** runs distintas em `item_runs` (`src/mastertool_bridge/templates/profile.py:465-469`), enquanto o gate normativo de R1 é "≥10 execuções independentes" (`docs/ROADMAP.md`, R1). Destrava porque toda a escala de maturidade de 6 níveis passa por esse validador: enquanto ele estiver frouxo, qualquer promoção de capacidade acima de `field_proven` é uma declaração sem lastro, e todo o resto de R1/R12 é medido contra um gate errado. Corrigir é barato e é pré-condição de confiabilidade de tudo que vier depois.

**2.2 — Não existe orquestrador que rode a fábrica N≥10 vezes, nem comparador N-ário** (`r1-runner-n-execucoes-ausente` + `r1-comparador-so-pareado`)
`scripts/mastertool/run_project_factory.ps1` executa uma rodada por invocação (os `foreach` do arquivo iteram gaps/probes dentro de UMA execução, não relançam a fábrica) e `compare_generations(artifacts_a, artifacts_b, layout)` tem assinatura fixa para exatamente duas gerações (`src/mastertool_bridge/automation/generation_equivalence.py:219-230`). O máximo medido para a fábrica atual (W7-W9) é n=2 (docs/44 run-029/030, docs/47 run-034/035). Destrava porque R1 é o primeiro nó da trilha crítica A (R1 → R2 → R6 → R11 → R12): sem repetibilidade medida, nenhuma das quatro fases seguintes tem base para abrir. O mecanismo é offline; as 10 execuções são de campo.

**2.3 — Não há cadeia de aprovação executável nem máquina de estados de change set** (`r6-aprovacao-nao-executavel` + `r6-maquina-de-estados-inexistente`)
`record_approval` e `check_approval` levantam `NotImplementedPhaseError` (`src/mastertool_bridge/changes/approval.py:13-14` e `:18-19`), e o `status.enum` do schema tem 6 valores (`draft, validated, approved, rejected, applied, rolled_back`) contra os 10 estados do roadmap, sem nenhum motor de transição em `changes/` (`src/mastertool_bridge/schemas/change-set.schema.json:11-14`). Destrava porque o roadmap declara "nenhuma mutação antes de R6": R2 (alteração de objeto existente), R7 (autoria gráfica) e a classe de execução do R10 estão todas represadas atrás desta ausência. É trabalho offline.

**2.4 — `expected_before_sha256` nunca carrega o hash de um objeto pré-existente** (`r2-before-sha256-nunca-populado-com-alvo-preexistente`)
O campo existe no passo do plano, mas só assume dois valores simbólicos (`EXPECTED_BEFORE_CREATED_IN_THIS_PLAN`, `EXPECTED_BEFORE_NOT_APPLICABLE`), porque nenhuma operação lê e hasheia um objeto que a spec não criou (`src/mastertool_bridge/planner/planner.py:363-378` e `:652-694`; o próprio comentário diz que "declarar um hash inventado aqui seria pior que declarar None"). Destrava porque o invariante de R2 é "cada alvo tem before_sha256": sem esse mecanismo não existe R2, e sem R2 não existem `configure_existing_task` (que R3 precisa para editar task existente), diff de alteração real, nem rollback com ponto de retorno verificável.

**2.5 — Evidence Bundle imutável não existe como módulo** (`r2-evidence-bundle-inexistente`)
Não há diretório `src/mastertool_bridge/evidence/`; a única aproximação é `changes/package_builder.py:9-14`, que levanta `NotImplementedPhaseError`. Destrava porque três gates diferentes dependem dele: o visualizador de evidências de R11 (não há o que visualizar), o rollback de R6 ("preservar evidências") e a qualificação de R12. É trabalho offline.

**2.6 — Ordem de chamadas de programas numa task é reordenada alfabeticamente, em silêncio** (`r3-ordem-de-chamadas`)
`_check_program_calls` devolve `sorted(pairs)` (`src/mastertool_bridge/planner/planner.py:844`) e o validador itera `sorted(program_call_pairs)` (`src/mastertool_bridge/spec/validator.py:699`); o executor escreve as chamadas em UserPrg na ordem dos passos, que já chega alfabetizada (`scripts/mastertool/probes/46_execute_authoring_plan.py:1523-1570`). Nenhum teste em `tests/unit/test_planner.py` exercita uma task com dois `program_calls` distintos. Em IEC, a ordem de chamada dentro de uma task **é** a ordem de execução no ciclo: o produto gera um programa com comportamento diferente do que o autor pediu, sem nenhum diagnóstico. Destrava confiança em todo o pipeline de autoria já `field_proven`, e o conserto é pequeno.

**2.7 — Semântica simbólica Ladder (L5) tem contrato íntegro e zero linhas de código** (`r4-l5-semantica-ladder`)
`docs/21-contrato-semantica-ladder.md` está completo até identidade determinística e critérios de fechamento, mas nenhuma classe `LadderSemantics`/`SymbolAccess`/`LadderCall` existe em `src/`. Destrava porque L6 (resolução contra o índice ST), o grafo unificado de R5, as consultas MCP sobre índice unificado e a autoria gráfica de R7 dependem, em cadeia, de L5 existir primeiro (`docs/21` §7.1 e §15; `docs/14-ladder-roadmap.md` Fase L6, linhas 599-651). Está em backlog por decisão registrada — a pendência é a decisão, não a falta de especificação.

**2.8 — [NOVA — dos verificadores] O verificador de higiene tem falso negativo silencioso contra strings escapadas** (`nova-higiene-regex-ponto-cego`)
O padrão `local_path_mastertool_x_install` de `tools/check_repo_hygiene.py:247-251` espera uma única barra invertida, mas o literal real nos probes usa barra invertida duplicada (escape de string Python), que no texto bruto do arquivo aparece como duas barras — e portanto nunca casa com o literal perigoso. Executando `find_local_path_findings` diretamente: zero achados para `scripts/mastertool/probes/43_bind_program_to_task.py`, que tem `STUB_PATH` com o caminho de instalação fixo e nenhuma menção incidental; os probes 36, 41 e 42 só são pegos por acidente, numa linha de docstring que cita o mesmo caminho com barra simples, não na linha que importa. Destrava porque este é o gate de CI que sustenta a afirmação "sem dado de cliente, sem caminho local no repositório": um regex que falha contra o padrão de código mais comum torna toda a varredura — e a catraca de dívida — não confiável, inclusive para as varreduras de segredo.

---

## 3. Pendências por fase

Legenda comum a todas as tabelas desta seção — **Tipo**: `não iniciado` (não existe nada), `stub` (existe e levanta `NotImplementedPhaseError`), `parcial` (existe e funciona só em parte), `só documentado` (existe em doc/allowlist, nunca exercido em código), `contradição documental` (doc e código discordam), `dívida técnica` (escolha registrada com custo conhecido). **Bloqueio**: `offline` = resolvível sem MasterTool, e **não promove maturidade de capacidade**; `campo` = só fecha em sessão supervisionada no MT9000 com o operador presente; `decisão` = trancado por escopo/sequência do roadmap. **Esforço**: P (pequeno), M (médio), G (grande). **Risco**: risco de **ignorar** a pendência, não de executá-la.

### 3.1 R0/R0b residual

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `nova-higiene-regex-ponto-cego` | **[NOVA]** Verificador de higiene não detecta caminho de instalação em string escapada; probe 43 invisível à varredura e à catraca | Falso negativo silencioso | `tools/check_repo_hygiene.py:247-251` (padrão com barra simples) vs `scripts/mastertool/probes/43_bind_program_to_task.py` (`STUB_PATH` com barra dupla); `find_local_path_findings` retorna 0 achados para o probe 43 | contradição documental | offline | P | médio |
| `nova-r0-fechamento-nao-declarado` | **[NOVA]** A moldura desta auditoria trata R0/R0b como fechadas em 2026-08-01; `CURRENT_STATUS.md` não declara isso em nenhum trecho | Estado de fase ambíguo | `docs/CURRENT_STATUS.md:37-38` ("A fase corrente do roadmap é R0 — consolidação e rebaseline") e §R0b com três lacunas abertas dependentes de campo; `CHANGELOG.md` tem `0.2.0a1` para R0 mas `[Unreleased]` para o conteúdo de R0b | contradição documental | decisão | P | médio |
| `r0-protecao-branch-nao-documentada` | "Proteção de branch documentada" é entregável nomeado da R0 sem registro de entrega nem de dispensa | Nenhum documento trata do tema | Exigência em `docs/ROADMAP.md` §3, item 2.1/R0; grep por "proteção de branch\|branch protection" em `docs/` só retorna o próprio ROADMAP; `docs/CURRENT_STATUS.md` (269 linhas, lido inteiro) não menciona o termo, nem no §7 "Publicação" | contradição documental | offline | P | baixo |
| `r0-sbom-ausente` *(funde `r12-sbom-nao-localizado`)* | Nenhum SBOM e nenhum lockfile de hashes é gerado ou versionado | Dependências só como `pyproject.toml` + `requirements-dev.txt` (5 dependências, sem hashes) | grep por `sbom\|SPDX\|CycloneDX` em todo o repositório: 0 ocorrências, inclusive em `.github/workflows/ci.yml`; `pyproject.toml:13-30` | não iniciado | offline | P | baixo |
| `r2.8-releases-nao-assinadas` *(funde `r12-pacote-assinado-nao-localizado`)* | "Releases assinadas" (item 2.8) sem mecanismo, chave ou workflow | CI empacota mas nunca publica nem assina | Glob `.github/workflows/*` → só `ci.yml`, cujo passo "Empacotar (build)" roda `python -m build` sem assinatura; grep `GPG\|gpg\|cosign\|sigstore\|codesign` sem ocorrência relevante; `requirements-dev.txt` sem ferramenta de assinatura | não iniciado | offline | M | baixo |

### 3.2 R1 — Repetibilidade e manifesto de execução

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r1-gate-repeatable-aceita-2-runs` | Validador aceita `repeatable` com 2 runs; roadmap exige ≥10 | Gate codificado ≠ gate normativo | `src/mastertool_bridge/templates/profile.py:465-469` (`if maturidade == 'repeatable' and len(set(item_runs)) < 2`) vs `docs/ROADMAP.md`, R1 | contradição documental | offline | P | **alto** |
| `r1-runner-n-execucoes-ausente` *(funde `r12-determinismo-n10-nao-medido`)* | Nenhum orquestrador repete a fábrica atual (W7-W9) N vezes; máximo medido para essa fábrica é n=2 | Uma rodada por invocação | `scripts/mastertool/run_project_factory.ps1` (sem laço de repetição da fábrica); `docs/CAPABILITY_MATRIX.md:91-102`; `docs/CURRENT_STATUS.md:50` ("repeatable — 0 — R1 não foi executada"); histórico n=2 em docs/44 (run-029/030) e docs/47 (run-034/035) | não iniciado | campo | G | **alto** |
| `r1-testes-negativos-parcialmente-cobertos` | Dos 10 testes negativos exigidos, 2 cobertos no pipeline atual, 2 cobertos só em probes históricos, 1 propaga sem tratamento, 1 só com teste estático de string, 3 sem evidência | Cobertura fragmentada | Cobertos: `run_workspace.py:64-65` + `tests/unit/test_supervised_run_host.py` (saída já existe); `tests/unit/test_planner.py` ~1079 (template/hash incompatível). Históricos, fora da fábrica atual: `tests/unit/test_probe_31_32_w1_3a.py:330` (objeto já existente), `tests/unit/test_probe_40_build_w1_4.py:504` (falha na reabertura). Sem tratamento dedicado: `automation/supervised_run.py:239-243` (permissão, declarado no próprio docstring). Só estático: `tests/unit/test_w1_4_wrapper_static.py:259` (biblioteca ausente). Sem evidência: build com erro intencional, interrupção antes e depois do `save_as` | parcial | campo | G | **alto** |
| `r1-execution-capability-manifest-ausente` | Execution Capability Manifest não existe como schema nem módulo | Nada existe | Busca por `execution_capability_manifest` / "Execution Capability Manifest" em todo o repositório: sem resultado; `schemas/execution_capability_manifest.json` ausente; exigência em `docs/ROADMAP.md` §3, item 2.3 | não iniciado | offline | G | médio |
| `nova-capmatrix-determinismo-inconsistente` | **[NOVA]** A seção "Determinismo medido" do CAPABILITY_MATRIX é internamente inconsistente | Diz "duas medições" e lista três; diz "n máximo medido é 2" logo abaixo de uma linha que registra 5 | `docs/CAPABILITY_MATRIX.md:91-102` (tabela com docs/40, docs/44, docs/47; a linha docs/40 registra 5 gerações independentes da mesma spec comparadas em 10 pares, cadeia W1.4) | contradição documental | offline | P | médio |
| `r1-maturity-scale-desconectada-do-executor-contract` | Escala de 6 níveis só existe no Template Profile; o EXECUTOR_CONTRACT só tem `cataloged`/`field_proven` | Operação individual não sabe carregar `repeatable`/`template_qualified` | `src/mastertool_bridge/templates/profile.py:61-68` (MATURITY_SCALE) vs `src/mastertool_bridge/planner/planner.py:188-316` | parcial | offline | M | baixo |
| `r1-comparador-so-pareado` | `compare_generations` só compara pares, não agrega N execuções | Assinatura fixa para duas gerações | `src/mastertool_bridge/automation/generation_equivalence.py:219-230` | parcial | offline | M | baixo |
| `r1-roadmap-contagem-13-desatualizada` | ROADMAP ainda cita "13 operações" no gate de R1; CURRENT_STATUS já corrigiu para 14 | Documentos discordam | `docs/ROADMAP.md:207` vs `docs/CURRENT_STATUS.md:33-66` (contagem 14 e nota de que registros anteriores diziam "treze") | contradição documental | decisão | P | baixo |

### 3.3 R2 — Alteração transacional de objeto existente

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r2-vocabulario-inexistente-no-executor` | Nenhuma das 5 operações de R2/W10 existe no EXECUTOR_CONTRACT ou em qualquer probe | Ausência total do vocabulário | grep pelos 5 nomes em `src/` só retorna `src/mastertool_bridge/schemas/change-set.schema.json` (vocabulário de proposta, não de execução); probes numerados até 48, nenhum ligado a W10; `docs/CAPABILITY_MATRIX.md` §4 já declara a ausência | não iniciado | campo | G | **alto** |
| `r2-before-sha256-nunca-populado-com-alvo-preexistente` | `expected_before_sha256` nunca carrega hash real de objeto pré-existente | Só dois valores simbólicos | `src/mastertool_bridge/planner/planner.py:363-378` (constantes `EXPECTED_BEFORE_*` e comentário) e `:652-694` | não iniciado | campo | G | **alto** |
| `r2-diff-nunca-exercido-sobre-alteracao-real` | `object_diff`/`project_diff` nunca compararam antes/depois de uma alteração real | Testado só com fixtures sintéticas | `src/mastertool_bridge/diff/object_diff.py`, `project_diff.py`, `tests/unit/test_project_diff.py` (dois `PlcObject` construídos à mão) | parcial | campo | M | médio |
| `r2-evidence-bundle-inexistente` | Evidence Bundle imutável não existe como módulo dedicado | Aproximação é stub | Ausência de `src/mastertool_bridge/evidence/`; `src/mastertool_bridge/changes/package_builder.py:9-14`; `docs/CURRENT_STATUS.md:193` já declara a dívida com alvo R2 | não iniciado | offline | G | médio |
| `r2-changeset-schema-vocabulario-diverge-do-roadmap` | Enum de `operation` do change-set não corresponde à lista de R2 | Faltam 2, sobram 2 | `src/mastertool_bridge/schemas/change-set.schema.json:28-32` (`replace_implementation, replace_declaration, add_object, remove_object, rename_object`) vs `docs/ROADMAP.md` R2 (faltam `replace_documents` e `configure_existing_task`) | contradição documental | decisão | P | baixo |

### 3.4 R3 — Cobertura IEC textual

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r3-ordem-de-chamadas` | Ordem de chamadas de múltiplos programs é reordenada alfabeticamente, em silêncio | Comportamento gerado diverge do declarado, sem diagnóstico | `planner.py:844` (`return sorted(pairs)`); `validator.py:699`; `probes/46_execute_authoring_plan.py:1523-1570`; `tests/unit/test_planner.py` só usa listas de 1 elemento (linhas 131, 145, 149, 918, 935) | dívida técnica | decisão | P | **alto** |
| `r3-task-edicao-existente` | Task marcada `existing: true` nunca é configurada, mesmo com `kind_of_task`/`interval`/`priority` na spec | Laço pula com `continue` | `planner.py:1249-1256` e `:1269-1280`; `docs/CAPABILITY_MATRIX.md:130` (`configure_existing_task` reservada para R2/W10) | não iniciado | decisão | G | médio |
| `r3-task-freewheeling-nao-provado` | `Freewheeling` passa na validação e sai `executable: True`, mas nunca foi exercido contra o produto | Fail-open no nível de valor de enum | `validator.py:446` (`_KINDS_OF_TASK_SUPPORTED`); `docs/49-execucao-w9-tempo-da-task.md:12` (só Cyclic testado); `planner.py:291-294` (`field_proven` declarado no nível da operação) | dívida técnica | campo | P | médio |
| `r3-idempotencia-already-satisfied` | Resultado `already_satisfied` não existe; sem checagem de pré-existência no pipeline atual | 1 de 14 operações tem equivalente parcial | grep `already_satisfied`: 0 ocorrências em código (só a frase do ROADMAP); `probes/46_execute_authoring_plan.py:1546-1554` (`already_present`, só `OP_CREATE_PROGRAM_CALL`); precedente histórico fora do pipeline em `probes/43_bind_program_to_task.py:847-858` (`STATUS_ALREADY_BOUND`) | parcial | campo | G | médio |
| `r3-library-lock-formal` | Library Lock formal (versão, fornecedor, namespace, origem, hash) inexistente | `$def library` só tem `name` | `spec/project_spec.schema.json:132-139`; `docs/CAPABILITY_MATRIX.md:148-152`; `docs/CURRENT_STATUS.md:197` (17 bibliotecas placeholder, alvo R3) | não iniciado | campo | G | médio |
| `r3-library-incompativel-vs-ausente` | Não se distingue biblioteca incompatível de não instalada | `_check_libraries` só detecta duplicata na spec | `planner.py:787-810`; `docs/CAPABILITY_MATRIX.md:127-129,148-152` | não iniciado | campo | G | médio |
| `r3-fb-actions-transitions` | Actions e transitions textuais de FB inexistentes | Sem campo no schema; rejeição só genérica | `spec/project_spec.schema.json:95-106` (`additionalProperties: false`); `validator.py:270-272`; `docs/CAPABILITY_MATRIX.md:123,141-142`. Reforço dos verificadores: `create_action`/`create_transition` não aparecem nem em `MASTERTOOL_MUTATING_OPERATIONS` | não iniciado | campo | G | médio |
| `r3-fb-methods` | Methods de FUNCTION_BLOCK inexistentes | Sem campo no schema | `spec/project_spec.schema.json:95-106`; `validator.py:270-272`; `docs/CAPABILITY_MATRIX.md:123`. Reforço: `create_method` ausente de `safety.py` | não iniciado | campo | G | médio |
| `r3-fb-properties-getset` | Properties com corpo Get/Set inexistentes | Sem campo no schema | `spec/project_spec.schema.json:95-106`; `validator.py:270-272`; `docs/CAPABILITY_MATRIX.md:141-142`. Reforço: `create_property` ausente de `safety.py` | não iniciado | campo | G | médio |
| `r3-interfaces` | INTERFACE e `FB.interfaces` inexistentes | Catalogado mas inalcançável | `scripts/mastertool/common/safety.py:64` (`create_interface`) vs `planner.py:110-124` (PLAN_OPERATIONS não a contém); `spec/project_spec.schema.json:95-106`; `docs/CAPABILITY_MATRIX.md:123` | não iniciado | campo | G | médio |
| `r3-extends-implements` | Leitura captura EXTENDS/IMPLEMENTS como texto bruto; na autoria o canal existe (campo `declaration`) mas nunca foi exercido nem validado semanticamente | Parcial dos dois lados | Leitura: `indexer/declaration_parser.py:164-189` ("texto bruto, não é o foco desta fatia"); `docs/CAPABILITY_MATRIX.md:110`. Autoria: `spec/project_spec.schema.json:95-106` e `tests/unit/test_planner.py:91` (o campo `declaration` aceitaria a sintaxe; nunca medido, sem checagem do tipo-base/interface referenciado) | parcial | campo | G | médio |
| `r3-persistentvars` | PersistentVars inalcançável pela spec | Catalogado como API mutável, sem operação | `safety.py:65` (`create_persistentvars`); `planner.py:110-124`; `validator.py:99` (`_TOP_LEVEL_KNOWN_KEYS` sem `persistentvars`); `docs/CAPABILITY_MATRIX.md:141-147` | não iniciado | campo | G | baixo |
| `r3-dut-alias` | DUT Alias não suportado | Recusa nomeada | `spec/project_spec.schema.json:65` (`enum: [STRUCT, ENUM]`); `validator.py:289-293`; `docs/CAPABILITY_MATRIX.md:122` | não iniciado | campo | M | baixo |
| `r3-dut-union` | DUT Union não suportado | Recusa nomeada | `spec/project_spec.schema.json:65`; `validator.py:289-293`; `docs/CAPABILITY_MATRIX.md:122` | não iniciado | campo | M | baixo |
| `r3-namespaces` | Namespaces IEC inexistentes | Sem campo, sem menção | `spec/project_spec.schema.json` (ausência); `validator.py:88-97` ("namespace" só como nome do container Application); `docs/CAPABILITY_MATRIX.md:141-142` | não iniciado | campo | G | baixo |
| `r3-atributos-pragmas` | Só um pragma (`qualified_only`) foi exercido; nenhum outro pragma/atributo foi medido e o validador não reconhece pragma como conceito | Canal existe, medição não | `docs/CAPABILITY_MATRIX.md:66` (pragma medido, docs/33/37) e `:141-142`; `tests/unit/test_planner.py:79,122,395`; grep `qualified_only` só aparece em `indexer/` (leitura), nunca em `planner.py` nem no probe 46 | parcial | campo | M | baixo |
| `r3-task-watchdog` | `watchdog.*` recusado deliberadamente (fora da allowlist) | Fail-closed com motivo no código | `safety.py:107-113` (comentário normativo: receptor próprio `ScriptWatchdog`, exige receptor e verificação novos); `docs/CAPABILITY_MATRIX.md:125` | não iniciado | campo | G | baixo |
| `r3-task-event` | `kind_of_task = Event` recusado por falta de gatilho | Recusa nomeada | `validator.py:439,446,477-482`; `docs/CAPABILITY_MATRIX.md:124` | não iniciado | campo | G | baixo |
| `r3-task-external-event` | `ExternalEvent` recusado por falta de gatilho | Recusa nomeada | `validator.py:439,446,477-482`; `docs/CAPABILITY_MATRIX.md:124` | não iniciado | campo | G | baixo |
| `r3-task-parent-synchron` | `ParentSynchron` e `parent_synchron_task` recusados | Fora de `_KINDS_OF_TASK_SUPPORTED` e da allowlist | `validator.py:439-446,477-482`; `safety.py:107-113`; `docs/CAPABILITY_MATRIX.md:126` | não iniciado | campo | G | baixo |
| `r3-task-core-binding` | `core_binding` recusado deliberadamente | Settable no stub, fora da allowlist | `safety.py:107-113`; `docs/CAPABILITY_MATRIX.md:126` | não iniciado | campo | G | baixo |

### 3.5 R4 — Semântica Ladder

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r4-l5-semantica-ladder` | Semântica simbólica Ladder (leituras/escritas/chamadas por network) não implementada | Contrato íntegro, zero linhas de código | `docs/21-contrato-semantica-ladder.md` (completo, sem código); `docs/CURRENT_STATUS.md:196,209-210`; `docs/CAPABILITY_MATRIX.md:113`; `docs/14-ladder-roadmap.md` ~474-480 ("BACKLOG desde 2026-07-31"); grep `LadderSemantics\|SymbolAccess\|LadderCall` em `src/` sem resultado | não iniciado | decisão | G | **alto** |
| `r4-l6-unificacao-indice-mcp` | Resolução contra o índice ST (L6), grafo unificado ST+Ladder e consultas MCP sobre índice unificado inexistentes | Nada em `indexer/` ou MCP toca Ladder | grep `ladder` em `src/mastertool_bridge/indexer/*.py` e `mcp_server.py` → sem resultado; `docs/21` §7.1 e §15 (L6 fora do escopo de L5 e dependente dele); `docs/CAPABILITY_MATRIX.md:162`; `docs/14-ladder-roadmap.md` linhas 599-651 | não iniciado | decisão | G | **alto** |

### 3.6 R5 — FBD, SFC e modelo unificado

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r5-fbd-leitura` | Leitura de FBD (parser, modelo canônico, mapeamento de schema real) não iniciada | `FBD` é só valor de enum de validação | `plcopen/canonical_model.py:44,584-587`; `plcopen/ladder_parser.py:116` (só itera elementos `<LD>`) e `:536` (`language="LD"` fixo); `docs/CAPABILITY_MATRIX.md:156-158`; `docs/17-plcopen-ladder-schema.md` (mapeamento existe só para LD); nenhum export FBD real jamais obtido | não iniciado | campo | G | **alto** |
| `r5-sfc-leitura` | Leitura de SFC (steps/transitions/actions) não iniciada | Mesma situação do FBD | `plcopen/canonical_model.py:44`; grep `FBD\|SFC` em `src/` só retorna `canonical_model.py:44` e `discovery/graphic_language_scan.py` (classificação L0, não parsing); `docs/14-ladder-roadmap.md` §L8, linhas 718-762; `docs/CAPABILITY_MATRIX.md:156-158` | não iniciado | campo | G | **alto** |
| `r5-vocabulario-unificado-nao-especificado` | `control_flow` e `data_flow` (exigidos pelo gate) nunca foram especificados para nenhuma linguagem | Termo só existe numa linha do ROADMAP | grep `control_flow\|data_flow` em `docs/` e `src/` → único resultado `docs/ROADMAP.md:253`; `docs/21` §4 define schema diferente (`accesses[]`, `calls[]`, `diagnostics[]`); `indexer/query.py:66` usa reads/writes/calls/callers | contradição documental | decisão | M | médio |

### 3.7 R6 — Ciclo de vida transacional do change set

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r6-aprovacao-nao-executavel` *(funde `r10-confirmacao-humana-por-risco`)* | `record_approval`/`check_approval` são stub; não há confirmação humana por nível de risco em lugar nenhum, nem amarrada ao MCP | Stub que sempre levanta | `changes/approval.py:13-14` e `:18-19` (`NotImplementedPhaseError`); `docs/CURRENT_STATUS.md:192`; nenhuma tool MCP aceita ou produz campo de risco (`src/mastertool_bridge/mcp_server.py`) | stub | offline | M | **alto** |
| `r6-maquina-de-estados-inexistente` | Enum estático de 6 estados contra os 10 do roadmap; nenhum motor de transição | Sem FSM de change set | `schemas/change-set.schema.json:11-14`; grep `transition` em `src/mastertool_bridge/changes/` sem resultado; `automation/run_states.py:16-19` (docstring: "não é uma máquina de estados: não há motor de transição", e é vocabulário de probe, não de change set) | contradição documental | offline | G | **alto** |
| `r6-rollback-nao-implementado` | Nenhum módulo implementa rollback de change set | Único artefato com o nome é legado desabilitado | `scripts/mastertool/11_rollback.py:1-8` (mensagem "Importacao desabilitada… Fase 4", sem lógica); ausência de módulo de rollback em `src/mastertool_bridge/changes/` | não iniciado | offline | G | **alto** |
| `r6-analise-de-impacto-inexistente` | Nenhuma função de análise de impacto existe | Só booleans estáticos preenchidos à mão | grep `impact\|impacto` (case-insensitive) em `src/` → nenhum arquivo; `changes/validator.py:8-55` (consome `safety_checks` fornecido, não calcula) | não iniciado | offline | G | médio |
| ~~`r6-forbidden-effects-sem-evidencia`~~ | ~~`forbidden_effects` não tem ocorrência no repositório~~ | **RETIRADO — não era requisito.** O termo foi uma **proposta** do próprio roadmap conversado, sem fonte externa a conferir. `status: proposal_removed`, `origin: assistant_roadmap_2026-08-01`, `repository_evidence: []`. Não gera tarefa, não entra em critério de aceite e não conta como funcionalidade faltante. Se for retomado, entra como decisão arquitetural nova | — | — | — | — |

### 3.8 R7 — Autoria gráfica

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r7-vocabulario-autoria-grafica-ausente` | Nenhuma operação de autoria gráfica existe no vocabulário do executor | 14 chaves, todas textuais | `planner.py:176` (EXECUTOR_CONTRACT); `docs/CURRENT_STATUS.md:57-58`; `docs/CAPABILITY_MATRIX.md:156-158` | não iniciado | decisão | G | **alto** |
| `r7-import-plcopen-nunca-exercido` | `import_xml` autorizado desde a W1 e nunca invocado nenhuma vez | Linha em allowlist, inalcançável pelo planner | `docs/28-contrato-escrita-controlada-mastertool-x.md:74,319-320`; `safety.py:74`; as únicas 3 ocorrências de `.import_xml(` no repositório são guardas de AST verificando **ausência** da chamada (`tests/unit/test_probe_44_w3_preflight.py:364`, `test_probe_45_w3_author.py:468`, `test_probe_47_verify_factory.py:293`) | só documentado | campo | G | **alto** |

### 3.9 R8 — Hardware, I/O e comunicação

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r8-hardware-tree-unclassified` | Nenhum código lê a árvore de hardware (rack/CPU/cartão/canal); a classificação existente é inventário achatado por `type_guid` | No template vigente (42 nós): 11 reconhecidos como dispositivo/hardware sem decomposição, 13 `unclassified` presumidos (não medidos) como hardware/configuração | `docs/36-qualificacao-template-tmf-v1.md:60-77,145-153`; `docs/CAPABILITY_MATRIX.md:164-167` | não iniciado | campo | G | **alto** |
| `r8-io-address-validations` | Nenhuma validação de endereçamento (duplicado, canal sem variável, variável sem canal, módulo ausente, revisão incompatível, gap, overlap) | Depende do modelo estrutural inexistente | `docs/CAPABILITY_MATRIX.md:164-167` ("não implementadas; reservado para R8"); sem evidência localizada de implementação em `src/` | não iniciado | campo | G | **alto** |
| `r8-fieldbus-topology-partial` | Fieldbus cobre parâmetros de comunicação, não a topologia scanner→adaptador nem assemblies/RPI com confiança alta | Parâmetros presos em confiança "média" | `inventory/device_inventory.py:92-143`; `docs/25-inventario-de-comunicacao.md:132-156` ("Achado registrado": IP/RPI/assemblies vêm de tipos genéricos, ARRAY OF BYTE/DWORD) | parcial | campo | M | médio |
| `r8-opcua-nao-iniciado` | Leitura de OPC UA sem nenhuma evidência de implementação ou investigação | Termo só aparece como categoria de risco de escrita | grep "OPC UA"/"opcua": 6 arquivos, e fora do `ROADMAP.md` as 5 ocorrências (`SAFETY_MODEL.md`, `08-safety.md`, `safety-policy.yaml`, `change-request-template.md`, `risk-assessment-template.md`) tratam OPC UA como risco em escrita, não como leitura | não iniciado | campo | G | médio |
| `r8-variable-io-binding-isolado` | Vínculo variável↔I/O existe só como reconhecimento textual de `AT %I/%Q/%M`, isolado do modelo físico e não documentado como capacidade R8 | Elo real, mas de uma ponta só | `indexer/declaration_parser.py:386-459`; `indexer/st_lexer.py:44,145`; `indexer/query.py:130`; `docs/13-static-project-indexer.md:56`; ausente de `CAPABILITY_MATRIX.md` e `CURRENT_STATUS.md` como capacidade R8 | parcial | campo | M | baixo |
| `r8-diagnosticos-nao-iniciado` | Leitura de diagnósticos de dispositivo/hardware sem evidência | Nem tentativa, nem recusa nomeada | sem evidência localizada (distinto de diagnóstico online, proibido por escopo) | não iniciado | campo | M | baixo |

### 3.10 R9 — Engenharia assistida

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r9-engineering-ir-nao-iniciado` | Pipeline documentos→Engineering IR→design congelado→Project IR→planner não existe em nenhuma forma | Só o contrato de entrada manual existe | grep "Engineering IR", "Project IR", "design congelado" no repositório inteiro → só `docs/ROADMAP.md`; `spec/validator.py:1-14` (escopo declarado: gate do `project_spec` já estruturado, não extração de documentos) | não iniciado | decisão | G | **alto** |
| `r9-biblioteca-padroes-nao-iniciada` | Biblioteca de padrões versionada (motor, válvula, transportador, dosagem, intertravamento, alarmes, modos) sem implementação e sem descrição fora do ROADMAP | Nem código, nem documento descritivo | Nenhum módulo/diretório/teste correspondente; os termos não aparecem em nenhum outro documento — `docs/14-ladder-roadmap.md:1077-1108` é genérico (memorial, matriz de I/O, hardware, POUs) e não cita esses padrões; "permissivos"/"intertravamentos" aparecem isolados em `docs/14` linhas 848-849, 881-882, 1046 | não iniciado | decisão | G | médio |
| `r9-gate-equivalencia-semantica-nao-iniciado` | Gate de R9 (mesma especificação → resultados semanticamente equivalentes) sem mecanismo nem teste | Não há o que comparar | consequência direta de `r9-engineering-ir-nao-iniciado`; sem evidência localizada de teste ou probe. Distinto do determinismo já medido para o planner de autoria manual (docs/40, docs/44), que opera sobre spec já estruturada | não iniciado | decisão | M | baixo |

### 3.11 R10 — Ferramentas de agente (MCP)

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r10-classe-execucao-isolada-inexistente` | Classe "execução isolada" não existe como camada MCP | Nenhuma ponte MCP→planner/executor | `src/mastertool_bridge/mcp_server.py` (arquivo inteiro, nenhuma referência a planner ou executor); único caminho de execução hoje é manual, via CLI/scripts fora do MCP | não iniciado | decisão | G | **alto** |
| `r10-recusa-automatica-critica-nao-testavel` | Recusa automática de operação crítica não é auditável no MCP porque não há superfície mutadora para recusar | Guardas existem, mas fora do MCP | `mcp_server.py` (sem chamada a `safety.py`); `scripts/mastertool/common/safety.py` (`assert_operation_allowed`, `assert_controlled_write_allowed`, `FORBIDDEN_OPERATIONS`, acionados só pelos probes IronPython); `docs/SAFETY_MODEL.md` §6 | não iniciado | decisão | M | **alto** |
| `r10-classe-proposta-inexistente` | Classe "proposta" (spec, change set, plano, impacto, riscos, testes) não existe no MCP | 8 tools, todas de leitura pura | `mcp_server.py:184-234`; `tests/test_mcp_server_e2e.py:113-122` (`EXPECTED_TOOL_NAMES` com exatamente 8); `docs/CURRENT_STATUS.md:215-217` | não iniciado | decisão | G | médio |
| `r10-auditoria-de-chamadas-mcp-nao-localizada` | Sem trilha de auditoria das chamadas ao MCP (quem, quando, com quais argumentos, qual resultado) | Nenhum registro persistente por chamada | `mcp_server.py` (não importa `logging_config`, não escreve em disco além do cache em memória `_INDEX_CACHE`) | não iniciado | decisão | P | médio |
| `r10-schemas-estritos-ok-mas-so-para-leitura` | Schemas estritos existem só para os parâmetros string das 8 tools de leitura | Coerente e testado no que existe | `mcp_server.py:82-90,189-233`; `tests/test_mcp_server_e2e.py:320-339`; ausência de schema para proposta/execução é consequência de `r10-classe-proposta-inexistente` | parcial | decisão | M | baixo |
| `r10-timeouts-server-side-nao-localizados` | Timeout de tool só existe no cliente de teste, não no servidor | `CALL_TIMEOUT` no lado errado | `tests/test_mcp_server_e2e.py:129-131,188` (`timedelta(seconds=20)`, `anyio.fail_after`); `mcp_server.py` sem timeout configurado | não iniciado | decisão | P | baixo |
| `r10-limites-de-carga-nao-localizados` | Sem limites explícitos (rate limit, tamanho de payload, concorrência) | Única validação é de forma | `mcp_server.py:82-89` (`_require_nonempty_str`) | não iniciado | decisão | P | baixo |
| `r10-e2e-so-cobre-caminho-de-leitura` | E2E do MCP cobre só a classe leitura; 4 dos 7 testes pulam se o export local não existir | 7 testes `@pytest.mark.asyncio`, todos de leitura | `tests/test_mcp_server_e2e.py:219,234,250,268,283,298,321`; os 4 que usam `real_index_dir` (250,268,283,298) pulam via `pytest.skip` (linha 153) **se e somente se** `workspace/exports/2026-07-23_17-29-54_13_validate_text_exporter` não existir — comportamento condicional ao ambiente, documentado nas linhas 146-151 | parcial | campo | M | baixo |
| `r10-r12-fase-do-roadmap-ainda-nao-alcancada` | R10/R12 auditadas como entregáveis correntes, mas a sequência do roadmap não chegou lá | Explica por que quase todo item R10/R12 é "não iniciado" | `docs/CURRENT_STATUS.md:37-38`; `docs/ROADMAP.md:377-379` (trilha A: R0→R1→R2→R6→R11→R12; trilha C depende de "nenhuma mutação antes de R6") | contradição documental | decisão | P | baixo |

### 3.12 R11 — Produto instalável

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r11-deteccao-mastertool-hardcoded` | 16 arquivos fixam o caminho de instalação em literal, contra a política escrita de "resolver o atalho .lnk sempre" | 12 wrappers `.ps1` + 4 probes (36, 41, 42, 43) | `scripts/mastertool/run_project_factory.ps1:55` e família (grep `Program Files\Altus\MT9000`); `tools/check_repo_hygiene.py:247-251` e `:272-312`; `docs/27-reconhecimento-mastertool-x.md` (regra escrita, nunca implementada); grep `.lnk` no repo só retorna menções documentais em docs/18 e docs/27. Ver também `nova-higiene-regex-ponto-cego` | stub | offline | M | médio |
| `r11-visualizador-evidencias-ausente` | Não há visualizador de evidências porque o evidence bundle não existe | Pré-condição bloqueante do gate R11 | `changes/package_builder.py:9-14`; `docs/CURRENT_STATUS.md:193` | stub | offline | G | médio |
| `r11-logs-rotativos-ausentes` | Sem rotação de log, e o único config que a mencionaria é órfão | `logging.yaml` não é lido por nenhum código | `logging_config.py:30-42` (só `StreamHandler`); `config/logging.yaml:22-28` (`FileHandler`, sem rotação); grep `logging\.yaml` em `src/` → 0 arquivos; grep `RotatingFileHandler\|logging\.handlers` em `src/` → 0 ocorrências | parcial | offline | P | médio |
| `r11-diagnostico-erro-nao-estruturado` | Exceções não carregam etapa, operação, objeto, projeto, versão, causa, consequência, ação recomendada nem ponteiro de evidência | Só mensagem livre (e uma lista de strings) | `src/mastertool_bridge/exceptions.py:1-42` (arquivo completo: `BridgeError`, `ExportNotFoundError`, `ValidationError`, `SafetyPolicyViolation`, `NotImplementedPhaseError`, `ProjectIndexError`, `InvalidIndexError`, `UnsupportedSchemaError`) | não iniciado | offline | M | médio |
| `r11-instalador-ausente` | Instalador do produto não existe | `pip install -e .` manual no README | Glob `tools/*` (10 arquivos, nenhum de instalação); `README.md:51-59` | não iniciado | offline | G | baixo |
| `r11-verificador-prerequisitos-ausente` | Nenhum verificador de pré-requisitos como componente do produto | Só há checagem do ambiente de teste | Glob `scripts/host/*` → 2 arquivos (`run_cli_probe_test.ps1`, `run_supervised_snapshot.ps1`), nenhum com esse propósito; `tests/unit/test_test_infrastructure.py` verifica o ambiente de teste, não o uso por operador | não iniciado | offline | M | baixo |
| `r11-cli-sem-contrato-de-estabilidade` | CLI funcional, sem declaração de superfície estável vs. experimental nem política de depreciação | 13 subcomandos, nenhum contrato | `cli.py:413-483` (subparsers) e `:410-411` (`--version`); busca por "estabilidade da CLI\|CLI stability\|deprecat" em `docs/` sem ocorrência; sem teste de contrato de schema de saída entre versões | parcial | offline | M | baixo |
| `r11-gerenciamento-runs-parcial` | Infra de workspace de run existe; não há gerenciamento exposto ao operador (listar, comparar, podar, reter) | Infraestrutura interna só | `automation/run_workspace.py:1-118` (sem função de listagem); `automation/run_states.py`; `cli.py:413-483` sem subparser `runs` | parcial | offline | M | baixo |
| `r11-visualizador-diff-so-texto` | Diff existe e é exposto por CLI, mas só como texto | Sem HTML, sem lado a lado, sem navegação | `tools/compare-exports.py:1-9`; `cli.py` `cmd_compare` (linha 96); `diff/semantic_diff.py:1-12` é stub, já atribuído à R2 | parcial | offline | M | baixo |
| `r11-exportacao-html-pdf-ausente` | Exportação HTML/PDF não existe — só Markdown | Pacote de export vazio | `src/mastertool_bridge/export/__init__.py` (arquivo vazio); `tools/generate-project-docs.py:1-9`; `docs/pou_documenter.py:9` (stub, alvo R2) | não iniciado | offline | M | baixo |
| `r11-politicas-por-organizacao-ausentes` | "Políticas por organização" não existe como conceito | Política única e global | `config/safety-policy.yaml`; Glob `config/**` (7 arquivos, nenhum com escopo por organização) | não iniciado | offline | G | baixo |
| `r11-atualizacao-controlada-ausente` | "Atualização controlada" não existe como mecanismo | `pip install`/`git pull` implícitos | sem evidência localizada de componente de atualização em `src/`, `tools/` ou `scripts/` | não iniciado | offline | G | baixo |
| `r11-desinstalacao-limpa-ausente` | "Desinstalação limpa" não existe | Depende de instalador inexistente | sem evidência localizada; dependente de `r11-instalador-ausente` | não iniciado | offline | P | baixo |
| `r11-fronteiras-runtime-nao-separadas` | As sete fronteiras de runtime não existem como pacotes separados | Um único pacote `mastertool-bridge` | `pyproject.toml:5-40`; grep pelos sete nomes só retorna nome de console script, README, ROADMAP e docstring; Glob `src/mastertool_bridge/adapters/**`, `ir/**`, `evidence/**` → nenhum arquivo (pré-requisitos 2.5-2.7 também ausentes) | não iniciado | offline | G | baixo |

### 3.13 R12 — Qualificação industrial

| ID | Pendência | Estado atual | Evidência | Tipo | Bloqueio | Esf. | Risco |
|---|---|---|---|---|---|---|---|
| `r12-matriz-nove-projetos-nao-localizada` | Matriz de 9 classes de projeto de qualificação não existe em documento nem em fixture | Fixtures isoladas, sem organização | sem evidência localizada de matriz formal; buscas em `docs/*.md` e `tests/` não retornaram documento ou fixture organizada; existem fixtures pontuais (`ExemploPlanta V1.0.project`, `TemplateExemplo_v1.project`) usadas em W1-W9 e R0b | não iniciado | campo | G | **alto** |
| `r12-falhas-induzidas-so-parcialmente-cobertas` | Dos ~11 tipos de falha induzida exigidos, só 2 têm teste, e são mocks unitários de escrita de artefato local | Não exercitam o pipeline de autoria/executor real | `tests/unit/test_common_artifacts.py:128` e `test_probe_42_43_tasks.py:998` (disco cheio, via IOError/RuntimeError mockado); `test_common_artifacts.py:157,169` (permissão negada); `templates/selector.py:70` (`DIAG_AMBIGUOUS` existe como diagnóstico do R0b, sem teste formal de matriz R12). Sem evidência: processo encerrado, arquivo bloqueado, library ausente, build interrompido, projeto alterado externamente, hash inválido, schema inválido | parcial | campo | G | **alto** |
| `r12-versoes-diferentes-mastertool-nao-qualificadas` | Só uma versão (MasterTool X 4.1.0.11) foi exercida para autoria | Leitura tem mais versões; escrita não | `docs/CAPABILITY_MATRIX.md` (coluna "Qualificada em" = MasterTool X 4.1.0.11 nas 14 linhas de autoria); leitura exercida também em MasterTool IEC XE 3.63/3.70; `docs/ROADMAP.md:153-159` §2.5 ("equivalência não se presume") | não iniciado | campo | G | **alto** |
| `r12-escala-nao-medida` | Escala nunca medida: limite do executor é 512 passos, maior spec exercida tem 24 | Nenhuma execução se aproximou do limite | `docs/CURRENT_STATUS.md:104` (dentro da lista de itens que "exigem medição em campo") | não iniciado | campo | G | médio |
| `r12-cobertura-nao-medida-e-nao-configurada` | Cobertura exigida (90%/80%/100% dos caminhos de recusa) não é medida: `pytest-cov` não instalado nem declarado, sem configuração no `pyproject.toml` nem no CI | Não foi possível medir; nenhum número estimado | `.venv/Scripts/python.exe -m pip show pytest-cov` → "WARNING: Package(s) not found: pytest-cov"; grep `-i cov` em `pyproject.toml` e `requirements-dev.txt` sem ocorrência; `.github/workflows/ci.yml` roda `pytest` puro | não iniciado | offline | P | médio |

---

## 4. Contradições documentais encontradas

Onde documento e código (ou documento e documento) discordam. Cada linha tem as duas evidências.

| # | Contradição | Evidência A | Evidência B |
|---|---|---|---|
| C1 | Gate de repetibilidade: o roadmap exige ≥10 execuções; o código aprova com 2 | `docs/ROADMAP.md`, R1 ("Critérios: ≥10 execuções independentes") | `templates/profile.py:465-469` (`len(set(item_runs)) < 2`) |
| C2 | Estados do change set: 10 no roadmap, 6 no schema, e nomes que não se correspondem (`applied`/`rolled_back` não estão no roadmap) | `docs/ROADMAP.md`, R6 (draft→validated→planned→authorized→executed→verified→build_passed→awaiting_approval→approved\|rejected→archived) | `schemas/change-set.schema.json:11-14` |
| C3 | Vocabulário de operação do change set diverge de R2: faltam `replace_documents` e `configure_existing_task`; sobram `add_object`/`remove_object` | `docs/ROADMAP.md`, R2 | `schemas/change-set.schema.json:28-32` |
| C4 | Contagem de operações: ROADMAP diz 13, CURRENT_STATUS diz 14 e declara que registros anteriores estavam errados | `docs/ROADMAP.md:207` | `docs/CURRENT_STATUS.md:33-66` |
| C5 | **[NOVA]** `CAPABILITY_MATRIX.md` se contradiz internamente: texto diz "duas medições de determinismo", tabela lista três; frase de fechamento diz "n máximo medido é 2" imediatamente abaixo da linha docs/40, que registra 5 gerações independentes comparadas em 10 pares | `docs/CAPABILITY_MATRIX.md:91-102` (texto e frase final) | `docs/CAPABILITY_MATRIX.md:91-102` (linha docs/40, cadeia W1.4) e `docs/40-medicao-determinismo-w1-4.md` |
| C6 | **[NOVA]** Estado da fase: a moldura desta auditoria trata R0/R0b como fechadas em 2026-08-01; a fonte canônica declara R0 como fase corrente e R0b com só a parte offline concluída | Moldura da auditoria e memória do usuário | `docs/CURRENT_STATUS.md:37-38` + §R0b (três lacunas abertas: inventário de dispositivo, trava de biblioteca, qualificação de capacidade); `CHANGELOG.md` (`0.2.0a1` para R0, `[Unreleased]` para R0b) |
| C7 | **[NOVA]** O verificador de higiene declara varrer caminhos locais de instalação, mas o regex não casa com o literal escapado que os probes realmente usam — o probe 43 escapa da varredura e da catraca de dívida | `tools/check_repo_hygiene.py:247-251` (regra `local_path_mastertool_x_install`) e `:272-312` (catraca) | Execução direta de `find_local_path_findings` → 0 achados para `probes/43_bind_program_to_task.py`, que tem `STUB_PATH` com o caminho fixo |
| C8 | `config/logging.yaml` declara um handler de arquivo que nenhum código lê; o código só instala `StreamHandler` | `config/logging.yaml:22-28` | `logging_config.py:30-42`; grep `logging\.yaml` em `src/` → 0 |
| C9 | Vocabulário unificado de R5 (`control_flow`, `data_flow`) só existe numa linha do ROADMAP; a única especificação semântica real define outro schema | `docs/ROADMAP.md:253` | `docs/21-contrato-semantica-ladder.md` §4 (`accesses[]`, `calls[]`, `diagnostics[]`); `indexer/query.py:66` |
| C10 | `CAPABILITY_MATRIX.md:141-142` classifica atributos/pragmas e herança como "fora do schema", quando o canal (`declaration`, texto livre) existe e já foi exercido para `{attribute 'qualified_only'}` | `docs/CAPABILITY_MATRIX.md:141-142` | `docs/CAPABILITY_MATRIX.md:66` (pragma medido, docs/33/37); `spec/project_spec.schema.json:95-106`; `tests/unit/test_planner.py:79,91,122,395` |
| C11 | `Freewheeling` sai `executable: True` porque `field_proven` é declarado no nível da operação, mas nenhuma execução real exerceu esse valor — o mesmo padrão de fail-open já corrigido uma vez para FB | `validator.py:446`; `planner.py:291-294` | `docs/49-execucao-w9-tempo-da-task.md:12` (só Cyclic testado); `docs/CURRENT_STATUS.md` §2 (correção anterior do mesmo padrão) |
| C12 | Sequência do roadmap: R10 e R12 foram auditadas como entregáveis correntes, mas dependem de R1/R2/R6/R11 (trilha A) e de "nenhuma mutação antes de R6" (trilha C), nenhuma delas aberta | Escopo da auditoria | `docs/ROADMAP.md:377-379`; `docs/CURRENT_STATUS.md:37-38` |
| C13 | `r8-variable-io-binding` existe como capacidade real de leitura, mas não aparece em `CAPABILITY_MATRIX.md` nem em `CURRENT_STATUS.md` como capacidade endereçada à R8 — só em `docs/13`, no contexto do indexador ST | `indexer/declaration_parser.py:386-459`; `indexer/query.py:130`; `docs/13-static-project-indexer.md:56` | Ausência do tema nas duas matrizes |

---

## 5. O que NÃO é pendência

Coisas que parecem lacuna e não são. Registradas para que ninguém as reabra como dívida.

**5.1 — Probes 27/30/32/34/38 usam parâmetros posicionais de propósito.** É evidência histórica preservada, já registrada como dívida consciente. Convertê-los apagaria a prova de como a descoberta foi feita.

**5.2 — Ausência de string de script livre no MCP é conformidade, não lacuna** (`r10-ausencia-string-script-livre`). Nenhuma das 8 tools aceita ou executa código arbitrário; todas chamam métodos nomeados de `ProjectIndex` via `getattr(index, method_name)` com `method_name` **fixado no código-fonte** (`mcp_server.py:122-176`), nunca vindo do usuário.

**5.3 — Ausência de caminho online e de dado de cliente já está declarada e reforçada por CI** (`r12-caminho-online-e-dado-cliente`). `docs/ROADMAP.md:49-52` lista como fora de escopo permanente download, login, modo online, start/stop, force e acionamento de saídas; `docs/CURRENT_STATUS.md:242-247` declara que dado de cliente nunca entra no repositório; `.github/workflows/ci.yml` roda `tools/check_repo_hygiene.py --profile interno` como gate. *Ressalva:* a eficácia desse gate está parcialmente comprometida por C7 — a política está certa, o verificador é que tem falso negativo.

**5.4 — Nunca baixar nem atualizar biblioteca sozinho já está satisfeito.** `download_missing_libraries` e `set_compilerversion_to_newest` estão catalogados como API mutável mas são inalcançáveis pelo planner e proibidos nominalmente (`docs/CAPABILITY_MATRIX.md:127-128`; `docs/28` §140-142). Essa parte específica da exigência de R3 **não** é pendência — a pendência é só a distinção entre biblioteca incompatível e não instalada.

**5.5 — As recusas nomeadas de task (`watchdog`, `core_binding`, `parent_synchron_task`, `Event`, `ExternalEvent`) são fail-closed correto.** O comportamento de recusar por não estar catalogado é o comportamento desejado, com motivo escrito no próprio código (`safety.py:107-113`). A pendência é a **capacidade ausente**, não o mecanismo de recusa — que está funcionando exatamente como deve.

**5.6 — Seleção de container por nome + `type_guid` com cardinalidade 1, e `node_path` como diagnóstico.** Decisão de arquitetura de R0b, já fechada (`templates/selector.py`, `select_unique_node` em `probes/46_execute_authoring_plan.py`). Não é lacuna.

**5.7 — `CONTROLLED_WRITE_PHASE = None` fora de sessão** não é regressão: é o estado seguro por padrão entre sessões supervisionadas.

**5.8 — O `pytest.skip` dos 4 testes E2E do MCP é condicional e deliberado**, documentado nas linhas 146-151 de `tests/test_mcp_server_e2e.py`. A pendência é a ausência de cobertura das classes proposta/execução, não o skip.

---

## 6. Limites deste levantamento

**6.1 — Cobertura das frentes: completa.** As 6 frentes aparecem nos dados, com as contagens declaradas conferidas item a item (17+17+21+7+9+20 = 91). As fases R9, R10 e R12 aparecem e estão representadas (R9 com 3 pendências, R10 com 9 após dedupe, R12 com 5 após dedupe). Nenhuma frente ficou de fora, e nenhuma fase entre R0 e R12 ficou sem registro.

**6.2 — Nenhum item marcado `SEM_VERIFICACAO`.** Dos 91 registros recebidos, **78 vieram CONFIRMADA** e **13 vieram CORRIGIDA** (nos 13, o enunciado adotado aqui é o da correção, não o do scout: `r0-sbom`, `r2.8-releases`, `r11-deteccao-mastertool`, `r1-runner-n-execucoes`, `r1-testes-negativos`, `r3-extends-implements`, `r3-atributos-pragmas`, `r3-idempotencia`, `r8-hardware-tree`, `r8-opcua`, `r9-biblioteca-padroes`, `r10-confirmacao-humana`, `r10-e2e`). **Nenhuma linha deste registro está marcada `SEM_VERIFICACAO`**, porque nenhum item chegou com esse veredito.

**6.3 — Nada foi verificado com o MasterTool aberto.** Toda evidência deste registro é de repositório: código, teste, documento, saída de CI. **38 das 88 pendências só podem ser confirmadas ou fechadas em sessão de campo no MT9000 com o operador presente** — e nenhuma delas pode ser promovida em maturidade por trabalho offline, por regra desta auditoria. Isso vale em particular para: todas as 19 pendências de campo de R3 (o que o produto aceita de fato quando a spec declara Alias, Union, methods, properties, interfaces, namespaces, pragmas arbitrários, Freewheeling, watchdog); as 6 de R8 (o que a árvore de hardware realmente contém — inclusive o que são os 13 nós `unclassified` do template vigente); FBD e SFC de R5 (nenhum export real dessas linguagens jamais foi obtido); `import_xml` de R7 (autorizado desde a W1, nunca invocado); e todas as medições de escala, determinismo n≥10 e falhas induzidas de R1/R12.

**6.4 — A ressalva de amostragem do verificador em `r3-idempotencia-already-satisfied`.** O enunciado e as evidências centrais foram reconferidos (grep de `already_satisfied`, bloco `already_present` do probe 46, `STATUS_ALREADY_BOUND` do probe 43), mas **a lista completa das 8 operações sem checagem de idempotência não foi reconferida linha a linha** — foi amostrada. Se o número exato importar para uma decisão, ele precisa ser recontado.

**6.5 — Cobertura de teste: não medida, e nenhum número estimado.** `pytest-cov` não está instalado no `.venv` nem declarado em `requirements-dev.txt`, e não há configuração de cobertura em `pyproject.toml` nem no CI. A auditoria tentou rodar e não conseguiu. **Não há estimativa de cobertura neste documento**, nem para as camadas onde R12 exige 90%.

**6.6 — Ausência de evidência não é evidência de ausência.** Sete itens estão registrados literalmente como "sem evidência localizada", o que significa que a busca não achou — não que se provou que não existe: `r11-atualizacao-controlada`, `r11-desinstalacao-limpa`, `r8-diagnosticos`, `r8-io-address-validations` (implementação), `r6-forbidden-effects`, `r12-matriz-nove-projetos`, `r9-gate-equivalencia`. Nenhum arquivo, função ou número foi inventado para preencher esses vazios.

**6.7 — Dois termos do enunciado da auditoria não têm origem localizada no roadmap.** `forbidden_effects` não aparece em nenhum arquivo do repositório (código ou documento), e "análise de impacto" não é detalhada em `ROADMAP.md` R6 — foi tratada como pressuposto do gate, não como requisito literal.

> **RESOLVIDO pelo operador em 2026-08-01.** Não havia fonte externa: `forbidden_effects` foi **proposta do próprio roadmap conversado**, não requisito preexistente. Retirado do registro normativo com `status: proposal_removed` e `origin: assistant_roadmap_2026-08-01`. A regra que fica: **nenhum requisito normativo sem origem explícita** — e a origem é um dos cinco valores de §7.

**6.8 — O estado de fase precisa ser resolvido pelo operador antes de priorizar.** A moldura desta auditoria assume R0 e R0b fechadas em 2026-08-01; `docs/CURRENT_STATUS.md` — a fonte canônica declarada — diz que a fase corrente é R0 e que R0b tem três lacunas abertas dependentes de campo. Enquanto isso não for resolvido, a severidade de `r0-protecao-branch-nao-documentada` fica indeterminada: é dívida de uma fase encerrada (mais grave) ou entregável pendente de uma fase ainda aberta (menos grave)? Esta auditoria não tem como decidir isso sem o operador.

---

## 7. Proveniência de requisito, e o vocabulário de evidência

Duas correções normativas de 2026-08-01, aplicadas depois do levantamento e
válidas para tudo que vier depois dele.

### 7.1 — Nenhum requisito normativo sem origem explícita

Todo requisito citado como pendência carrega, daqui em diante, uma `origin`:

| `origin` | Significado |
|---|---|
| `repository` | está escrito em documento normativo ou em código deste repositório |
| `field_measurement` | veio de uma execução real contra o produto, com run citável |
| `operator_decision` | o operador decidiu, e a decisão está registrada |
| `assistant_proposal` | foi proposto durante uma conversa de roadmap e **ainda não foi aceito** |
| `external_document` | veio de fonte fora do repositório, que precisa ser citada |

**`assistant_proposal` não gera tarefa.** Enquanto não for formalmente aceito,
um item nessa classe não aparece como funcionalidade faltante, não entra em
critério de aceite e não conta como dívida. Foi o caso de `forbidden_effects`,
retirado em §3/R6 e em §6.7.

*Como ler:* a coluna existe para tornar impossível a confusão que motivou a
regra — uma sugestão de conversa reaparecer, semanas depois, como requisito
que "sempre esteve lá". Item sem `origin` é item que ainda não foi
classificado, e não item de origem óbvia.

### 7.2 — `no_evidence_located` nunca é `contradicted`

O vocabulário de evidência passou a ser fechado e executável, em
`src/mastertool_bridge/audit/evidence_status.py`:

| Estado | Significado |
|---|---|
| `proven` | existe evidência positiva suficiente |
| `contradicted` | foi testado e a hipótese foi refutada |
| `no_evidence_located` | a busca não encontrou evidência suficiente |
| `requires_field` | só pode ser resolvido com o MasterTool aberto |
| `not_applicable` | não se aplica ao escopo avaliado |
| `blocked` | há pré-condição ainda não satisfeita |

Os **sete itens** que este registro marcou como "sem evidência localizada"
(§6.6) são `no_evidence_located`, e não negações. O módulo torna a distinção
estrutural: `proven` e `contradicted` exigem evidência citável;
`no_evidence_located` exige dizer **o que foi procurado, onde, por que nada
concluiu e qual é o próximo método**; e a transição de ausência para refutação
sem medição nova é recusada com nome próprio. Termos que serviriam para as
duas leituras — `false`, `unsupported`, `rejected`, `missing`, `unknown` — são
proibidos como status, em vez de mapeados para o palpite mais próximo.

*Como ler:* a tabela é o vocabulário inteiro; não há um sétimo estado
implícito. Um item que não caiba em nenhum dos seis é um achado sobre o
vocabulário, não uma licença para inventar um sétimo.

### 7.3 — Os 38 itens de campo são fila própria, não pendência de R1

Ver [`FIELD_QUALIFICATION.md`](FIELD_QUALIFICATION.md). Eles não são
"não implementados", nem negados, nem falhas, nem requisitos que um teste
Python encerraria: são **não resolvíveis offline**, e cada um está ligado ao
primeiro marco que de fato depende dele. R1 fecha apenas o que qualifica a
repetibilidade das operações atuais.

---

## 8. Pendências ABERTAS por este trabalho

Trabalho fecha lacuna e abre lacuna. Estas nasceram na madrugada de
2026-08-02 e não estavam no levantamento original.

| ID | Pendência | Por que ficou aberta | Bloqueio |
|---|---|---|---|
| `r11-migrar-wrappers-para-deteccao` | Os 15 wrappers e probes continuam com o caminho do MT9000 fixado; a ferramenta que os substituiria (`detect-mastertool`) já existe | Cada um é roteiro de sessão supervisionada cujo comportamento precisa ser **remedido** depois da troca. Reescrever quinze em lote sem ninguém olhando o produto é como uma regressão silenciosa entra | offline para o código, **campo** para a remedição |
| ~~`r1-lote-piloto-n3`~~ | **FECHADA** — piloto N=3 rodou, achou três defeitos, e os dois lotes N=10 saíram verdes (`docs/50`, `docs/51`) | — | — |
| ~~`r2-before-sha256-de-alvo-preexistente`~~ | **FECHADA** — `e3b0c442…b855` medido nas dez runs de `docs/50` e conferido no campo antes do `replace` (`docs/52`) | — | — |
| ~~`r2-repetir-w10-n10`~~ | **FECHADA** — dez execuções independentes, 10/10 em tudo (`docs/53`); `replace` sobre alvo preexistente é `repeatable` | — | — |
| ~~`r2-reversao-medida`~~ | **FECHADA** — `docs/54`: alteração desfeita pelo mesmo mecanismo, spec inversa **emitida** e não escrita, e o revertido é indistinguível do template original. O pacote ganhou a seção `rollback/` com o CONTEÚDO anterior | — | — |
| ~~`r2-repetir-reversao-n10`~~ | **FECHADA** — `run_rollback_batch.ps1` construído, e dez reversões independentes medidas (`docs/55`): 10/10 em tudo, e nas dez o texto original de volta | — | — |
| ~~`r2-reverter-a-reversao`~~ | **FECHADA** — dez execuções (`docs/56`), 10/10 com o texto da W10 de volta. Não exigiu par de fases novo: *redo* é a alteração sobre outra base, e roda sob `W10_EDIT_EXISTING` | — | — |
| `r2-ciclo-mais-longo-que-tres-voltas` | Foram medidas três voltas: alterar → reverter → re-alterar | Nada nas trinta execuções diz o que acontece na décima volta. Não há motivo conhecido para degradar, e "não há motivo conhecido" não é medição | **campo** |
| `r2-qualificacao-de-template-sem-identidade` | Artefatos de `qualify-analysis.json` gerados antes de 2026-08-02 não carregam `project.sha256`, e a fábrica agora os recusa | Não é regressão: o artefato antigo nunca disse de qual arquivo falava, e a fábrica é que deixava passar. Remedir custa uma sessão read-only de 20 s por template | **campo**, barato |
| `r2-reverter-criacao-e-reversao-parcial` | A spec inversa desfaz alteração de texto, e desfaz **todas** as do plano | Desfazer criação exigiria `delete`/`remove`, que não está no `EXECUTOR_CONTRACT` e não tem fase. Reversão parcial é escolha de subconjunto, e ninguém escreveu o critério | offline |
| `r2-alvo-com-texto-anterior-nao-vazio` | O único alvo exercido tem implementação **vazia**: `e3b0c442…b855` é o sha256 da string vazia | A conferência do "antes" nunca rodou contra conteúdo real. É o mesmo código com outro dado, mas "o mesmo código com outro dado" é exatamente o que a medição existe para não presumir | **campo** |
| `r2-configure-existing-task-metade-do-executor` | O host sabe conferir o "antes" de propriedade de task (`spec/task_property_source.py`, `verify-modifications`); o executor **não** sabe achar uma task preexistente | A busca por task já existente não está escrita, e sem ela o passo não tem alvo. O lado do host foi escrito primeiro de propósito: é ele que impede escrita cega | offline para o executor, **campo** para a prova |
| `r2-antes-textual-cobre-so-os-objetos-lidos` | Na comparação antes×depois, a camada de ÁRVORE cobre o projeto inteiro (42 nós) e a de TEXTO cobre só os objetos que o inventário leu | Um inventário textual do projeto inteiro exige varredura que ninguém escreveu — o `probes/21` devolve a árvore, não os textos. Os dois lados hoje leem o mesmo conjunto, então a comparação é coerente; o que ela não é, é ampla | offline para o varredor, **campo** para a medição |
| `r6-analise-de-impacto` | A máquina de estados existe; a análise de impacto (símbolos, POUs, tasks, I/O, writers/readers) não foi construída | Depende do índice unificado ST+Ladder (R4), que está em backlog por decisão registrada | offline, **bloqueada por R4** |
| `r12-classificar-modulos-de-cobertura-zero` | A baseline mostra módulos em 0%; ninguém separou código morto de caminho só exercido em campo de lacuna real de teste | Sem essa classificação, qualquer limiar vira pressão para escrever teste que cobre linha sem verificar comportamento | offline |

<caption>

**Como ler:** nenhuma destas é regressão — são consequências nomeadas do que
foi construído. A primeira é a mais importante: existe agora uma ferramenta
melhor que a prática vigente, e a distância entre as duas é dívida até que
alguém a percorra com o produto aberto.

</caption>
