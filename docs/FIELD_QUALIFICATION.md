# FIELD-QUALIFICATION — o que só fecha com o MasterTool aberto

```text
status: requires_mastertool_runtime
total: 38
origin: auditoria multiagente de 2026-08-01 (docs/PENDENCIAS.md)
```

Estes itens **não são** não-implementados, negados, falhas, pendências
documentais nem requisitos que um teste Python encerraria. São
**não resolvíveis offline**: dependem do comportamento real do produto e
exigem journal e evidência de campo. Trabalho de escritório não promove
nenhum deles — no máximo prepara o instrumento que os medirá.

Cada item está ligado ao **primeiro marco que de fato depende dele**, e não
empilhado em R1. A R1 fecha apenas o que qualifica a repetibilidade das
operações que já existem; um item de R3 continua sendo de R3, mesmo que a
sessão de campo que o mediria pudesse acontecer no mesmo dia.

| Fase | Itens |
|---|---:|
| R1 | 1 |
| R10 | 1 |
| R12 | 5 |
| R2 | 3 |
| R3 | 19 |
| R5 | 2 |
| R7 | 1 |
| R8 | 6 |
| **Total** | **38** |

<caption>

**Como ler:** a fase é o marco que precisa da evidência, não a fase em que
a medição seria conveniente. Um item aparece uma vez só, no primeiro marco
que depende dele.

</caption>

## R1

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r1-testes-negativos-parcialmente-cobertos` | Dos 10 testes negativos exigidos por R1, apenas 2 têm evidência de cobertura automatizada localizada | Dos 10 testes negativos de R1: 'saída já existe' e 'hash/template incompatível' cobertos (como já dito). 'Objeto já existente' e 'falha na reabertura' TÊM teste automatizado, mas em probes mais antigos (W1.3A: tests/unit/test_probe_31_32_w1_3a.py:330 test_alvo_duplicado; W1.4: tests/unit/test_probe_40_build_w1_4.py:504 | src/mastertool_bridge/automation/run_workspace.py:64-65 + tests/unit/test_supervised_run_host.py (saída já existe); tests/unit/test_planner.py linha ~1079 test_expected_template_mismatch_is_refused (template/hash incompatível); src/mastertool_bridge/automation/supervised_run.py:2 | **alto** |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## R10

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r10-e2e-so-cobre-caminho-de-leitura` | Testes E2E do MCP cobrem só a classe de leitura; nenhum teste de proposta, execução, confirmação de risco ou recusa crítica existe porque essas classes não existem | tests/test_mcp_server_e2e.py tem exatamente 7 testes @pytest.mark.asyncio (linhas 219,234,250,268,283,298,321), todos exercitando só a classe leitura das 8 tools. Os 4 que dependem de real_index_dir (250,268,283,298) pulam via pytest.skip (linha 153) SE E SOMENTE SE workspace/exports/2026-07-23_17-29-54_13_validate_tex | tests/test_mcp_server_e2e.py:139-163,218-339 | baixo |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## R12

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r12-determinismo-n10-nao-medido` | Determinismo com n≥10 (exigência R12) não foi medido; máximo medido é n=2 | docs/CAPABILITY_MATRIX.md linhas 91-102 documenta explicitamente: 'n máximo medido é 2 execuções independentes por spec. R1 exige ≥10 — a lacuna é de escala de medição, não de mecanismo.' R1 (pré-requisito estrutural de R12 na trilha A) ainda não foi executada. | docs/CAPABILITY_MATRIX.md:91-102 (tabela docs/40, docs/44, docs/47, e a frase 'n máximo medido é 2'); docs/CURRENT_STATUS.md:50 ('repeatable — 0 — R1 não foi executada') | **alto** |
| `r12-escala-nao-medida` | Medição de escala exigida pela R12 não foi feita; limite do executor (512 passos) nunca foi testado contra a maior spec exercida (24 passos) | docs/CURRENT_STATUS.md linha 104 declara: 'escala real — o limite do executor é 512 passos e a maior spec exercida tem 24' — dentro da lista de itens que 'exigem medição em campo'. Nenhuma execução aproximou-se do limite declarado. | docs/CURRENT_STATUS.md:104 | medio |
| `r12-falhas-induzidas-so-parcialmente-cobertas-e-mockadas` | Dos 10 tipos de falha induzida exigidos pela R12, só "disco cheio" e "permissão negada" têm algum teste, e são mocks unitários de escrita de artefato local, não do pipeline de autoria/executor real | Busca por cada um dos 10 termos em tests/ só encontrou 'disco cheio' (tests/unit/test_common_artifacts.py:128, tests/unit/test_probe_42_43_tasks.py:998, via IOError/RuntimeError mockado) e 'permissão negada' (tests/unit/test_common_artifacts.py:157,169). Não encontrei testes correspondentes a: processo encerrado, arqui | tests/unit/test_common_artifacts.py:128,157,169; tests/unit/test_probe_42_43_tasks.py:998; src/mastertool_bridge/templates/selector.py:70 (DIAG_AMBIGUOUS, sem teste formal de matriz R12 localizado) | **alto** |
| `r12-matriz-nove-projetos-nao-localizada` | Matriz de 9 classes de projeto de qualificação industrial não existe em documento nem em fixture de teste | Busca por 'sintético pequeno', 'sintético grande', 'disco cheio', 'permissão negada' e termos correlatos em docs/*.md e tests/ não encontrou nenhuma matriz nem plano formal cobrindo as 9 classes descritas. Existem fixtures isoladas (ex.: ExemploPlanta V1.0.project, TemplateExemplo_v1.project) usadas para provas pontuais de W1-W9 e R0 | sem evidência localizada de matriz formal; buscas em docs/*.md e tests/ não retornaram documento ou fixture organizada como a matriz de 9 classes | **alto** |
| `r12-versoes-diferentes-mastertool-nao-qualificadas` | Qualificação separada por versões diferentes do MasterTool (uma das 9 classes de projeto da R12) não foi feita — só uma versão (4.1.0.11) foi exercida para autoria | docs/COMPATIBILITY_MATRIX.md e docs/CAPABILITY_MATRIX.md só citam MasterTool X 4.1.0.11 para toda a cadeia de autoria (as 14 operações field_proven). Leitura foi exercida também contra MasterTool IEC XE 3.63/3.70, mas autoria/escrita nunca foi tentada em outra versão. Equivalência entre produtos/versões 'não se presume | docs/CAPABILITY_MATRIX.md (coluna 'Qualificada em' = 'MasterTool X 4.1.0.11' em todas as 14 linhas da tabela de operações de autoria); docs/ROADMAP.md:153-159 (§2.5) | **alto** |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## R2

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r2-before-sha256-nunca-populado-com-alvo-preexistente` | expected_before_sha256 nunca carrega o hash real de um objeto pré-existente — mecanismo de origem do dado não existe | O campo expected_before_sha256 existe no formato do passo do plano, mas hoje só é usado com dois valores simbólicos — EXPECTED_BEFORE_CREATED_IN_THIS_PLAN (objeto criado neste mesmo plano) e EXPECTED_BEFORE_NOT_APPLICABLE — porque nenhuma operação atual lê e hasheia um objeto pré-existente antes de alterá-lo. O comentá | src/mastertool_bridge/planner/planner.py:363-378 (comentário e constantes EXPECTED_BEFORE_*) e :652-694 (_step, campo sempre None nas chamadas atuais) | **alto** |
| `r2-diff-nunca-exercido-sobre-alteracao-real` | object_diff/project_diff funcionam e têm teste, mas nunca foram exercidos comparando antes/depois de uma alteração real de objeto existente | diff_objects/compare_projects estão implementados e cobertos por testes unitários com fixtures sintéticas (dois PlcObject construídos à mão), mas nunca compararam exports reais de antes/depois de uma edição de objeto pré-existente no MasterTool, porque essa operação (R2/W10) nunca rodou. | src/mastertool_bridge/diff/object_diff.py, src/mastertool_bridge/diff/project_diff.py, tests/unit/test_project_diff.py (fixtures sintéticas, não exports reais de edição) | medio |
| `r2-vocabulario-inexistente-no-executor` | Nenhuma das 5 operações de R2/W10 existe no EXECUTOR_CONTRACT ou em qualquer probe | Busca em src/ pelos 5 nomes literais só retorna ocorrências dentro do enum do JSON schema de change-set (que é vocabulário de proposta, não de execução) — nenhuma aparece em planner.py/EXECUTOR_CONTRACT. Os probes vão até o 48 (48_probe_enums_readonly.py); nenhum probe de alteração de objeto pré-existente existe. Confi | grep por "replace_declaration\|replace_implementation\|replace_documents\|configure_existing_task\|rename_object" em src/ só encontra src/mastertool_bridge/schemas/change-set.schema.json; find em scripts/mastertool/probes mostra numeração até 48, nenhum ligado a W10 | **alto** |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## R3

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r3-atributos-pragmas` | Atributos e pragmas customizados inexistentes na spec | A lacuna real não é 'sem vocabulário para pragmas/atributos' — o canal (campo 'declaration' de texto livre) já existe e já foi exercido com sucesso para UM pragma ({attribute 'qualified_only'} em GVL, field_proven em docs/33/37, escrito pelo autor da spec). A lacuna correta é: nenhum OUTRO pragma/atributo IEC foi exerc | docs/CAPABILITY_MATRIX.md:66 (pragma qualified_only medido, embutido); docs/CAPABILITY_MATRIX.md:141-142 ('atributos e pragmas customizados — fora do schema'); src/mastertool_bridge/spec/project_spec.schema.json (sem campo) | baixo |
| `r3-dut-alias` | DUT Alias não suportado | Recusado com nome próprio: o schema só aceita kind em {STRUCT, ENUM} e o validador repete a checagem. Nenhum código do planner/executor referencia 'Alias'. | src/mastertool_bridge/spec/project_spec.schema.json:65 ("enum": ["STRUCT","ENUM"]); src/mastertool_bridge/spec/validator.py:289-293; docs/CAPABILITY_MATRIX.md:122 | baixo |
| `r3-dut-union` | DUT Union não suportado | Mesma recusa nomeada que Alias — kind fora de {STRUCT, ENUM} reprova no schema e no validador. Nunca medido contra o produto. | src/mastertool_bridge/spec/project_spec.schema.json:65; src/mastertool_bridge/spec/validator.py:289-293; docs/CAPABILITY_MATRIX.md:122 | baixo |
| `r3-extends-implements` | EXTENDS/IMPLEMENTS: lido como texto bruto, sem semântica, e inexistente na autoria | Leitura: confirmada como descrita (declaration_parser.py:164-189; CAPABILITY_MATRIX.md:110). Autoria: a lacuna não é 'nenhum campo declarável' — o campo 'declaration' (string livre, já usado para o cabeçalho completo do FB, field_proven para create_function_block) comportaria a sintaxe EXTENDS/IMPLEMENTS sem rejeição d | src/mastertool_bridge/indexer/declaration_parser.py:164-190 (comentário 'texto bruto, não é o foco desta fatia'); src/mastertool_bridge/spec/project_spec.schema.json:95-106; docs/CAPABILITY_MATRIX.md:110,123 | medio |
| `r3-fb-actions-transitions` | Actions e transitions textuais de FB inexistentes | O $def function_block do schema só tem name/language/declaration/implementation/uses, com additionalProperties:false — não há campo para lista de actions ou transitions. Uma spec que tentasse declará-las reprova por 'campo(s) desconhecido(s)' genérico. | src/mastertool_bridge/spec/project_spec.schema.json:95-106; src/mastertool_bridge/spec/validator.py:270-272; docs/CAPABILITY_MATRIX.md:123,141-142 | medio |
| `r3-fb-methods` | Methods de FUNCTION_BLOCK inexistentes | Mesma ausência estrutural: schema do function_block não declara campo para métodos; rejeição só é genérica ('campo desconhecido'), não nomeada especificamente para 'methods'. | src/mastertool_bridge/spec/project_spec.schema.json:95-106; src/mastertool_bridge/spec/validator.py:270-272; docs/CAPABILITY_MATRIX.md:123 | medio |
| `r3-fb-properties-getset` | Properties e getter/setter de FUNCTION_BLOCK inexistentes | Sem campo de schema para properties com corpo Get/Set. Declarar isso reprova apenas de forma genérica. | src/mastertool_bridge/spec/project_spec.schema.json:95-106; src/mastertool_bridge/spec/validator.py:270-272; docs/CAPABILITY_MATRIX.md:141-142 | medio |
| `r3-idempotencia-already-satisfied` | Idempotência com resultado already_satisfied inexistente no pipeline atual (planner + probe 46); existe precedente isolado e não generalizado | Enunciado e evidência centrais confirmados tal como escritos: grep 'already_satisfied' no repo só aparece em ROADMAP.md; probe 46 (bloco ~1546-1554) tem outcome 'already_present' exclusivo de OPERATION_CREATE_PROGRAM_CALL; probes/43_bind_program_to_task.py (bloco ~849-858) tem STATUS_ALREADY_BOUND como precedente histó | grep 'already_satisfied' em todo o repo: 0 ocorrências em código-fonte (só a frase do próprio ROADMAP.md); scripts/mastertool/probes/46_execute_authoring_plan.py:1546-1554 (outcome 'already_present', só para OP_CREATE_PROGRAM_CALL); scripts/mastertool/probes/43_bind_program_to_ta | medio |
| `r3-interfaces` | Interfaces (INTERFACE...END_INTERFACE e FB.interfaces) inexistentes | 'create_interface' está catalogado como API mutável, mas sem operação correspondente em PLAN_OPERATIONS/EXECUTOR_CONTRACT — mesma classe de 'catalogado mas inalcançável' de PersistentVars. FB também não tem campo 'interfaces' no schema. | scripts/mastertool/common/safety.py:64 (create_interface); src/mastertool_bridge/planner/planner.py:110-124; src/mastertool_bridge/spec/project_spec.schema.json:95-106; docs/CAPABILITY_MATRIX.md:123 | medio |
| `r3-library-incompativel-vs-ausente` | Distinguir biblioteca incompatível de não instalada — inexistente | _check_libraries só detecta duplicata declarada na spec; não há nenhuma checagem — nem offline nem em campo — que compare a versão/fornecedor de uma biblioteca contra o que está instalado. O comportamento normativo de NUNCA baixar/atualizar biblioteca sozinho está, por outro lado, já garantido: download_missing_librari | src/mastertool_bridge/planner/planner.py:787-810 (_check_libraries só checa duplicata); docs/CAPABILITY_MATRIX.md:127-129,148-152 | medio |
| `r3-library-lock-formal` | Library Lock formal (nome, versão, fornecedor, namespace, origem, hash) inexistente | O $def 'library' do schema só tem o campo 'name' (obrigatório), sem versão, fornecedor, namespace, origem ou hash. As 17 bibliotecas do template são placeholder e nenhum build fixa a versão resolvida. Já documentado corretamente como pendente de R3 pela própria CAPABILITY_MATRIX — não é contradição, é lacuna corretamen | src/mastertool_bridge/spec/project_spec.schema.json:132-139 (library só tem 'name'); docs/CAPABILITY_MATRIX.md:148-152; docs/CURRENT_STATUS.md linha 197 ('bibliotecas: 17 placeholder, sem library lock; alvo da R3') | medio |
| `r3-namespaces` | Namespaces inexistentes | Nenhum campo de schema, nenhuma menção no planner/validator/executor além da palavra 'namespace' usada para descrever o container compartilhado da Application (uso interno, não a feature IEC de namespace). | src/mastertool_bridge/spec/project_spec.schema.json (ausência de campo); src/mastertool_bridge/spec/validator.py:88-97 ('namespace' só como nome do container Application); docs/CAPABILITY_MATRIX.md:141-142 | baixo |
| `r3-persistentvars` | PersistentVars inexistente no vocabulário de autoria | 'create_persistentvars' está catalogado como API mutável do MasterTool, mas nenhuma operação do planner a consome — inalcançável pela spec. Uma spec que declarasse 'persistentvars' no nível raiz cairia no reprovo genérico de chave desconhecida, não numa recusa específica. | scripts/mastertool/common/safety.py:65 (create_persistentvars em MASTERTOOL_MUTATING_OPERATIONS); src/mastertool_bridge/planner/planner.py:110-124 (PLAN_OPERATIONS não a contém); src/mastertool_bridge/spec/validator.py:99 (_TOP_LEVEL_KNOWN_KEYS sem 'persistentvars'); docs/CAPABIL | baixo |
| `r3-task-core-binding` | core_binding de task recusado deliberadamente | Settable no stub, mas fora de MASTERTOOL_PROPERTY_WRITES por decisão — mesma classe de recusa que watchdog e parent_synchron_task. | scripts/mastertool/common/safety.py:107-113; docs/CAPABILITY_MATRIX.md:126 | baixo |
| `r3-task-event` | kind_of_task Event recusado explicitamente por falta de gatilho | Recusado com nome próprio: validador aceita Event como membro do enum KindOfTask mas reprova porque exige o campo 'event' (gatilho), que a spec não sabe escrever — mensagem nomeada. | src/mastertool_bridge/spec/validator.py:439,446,477-482 ('{kind!r} exige um gatilho (event ou external_event) que esta spec não sabe escrever'); docs/CAPABILITY_MATRIX.md:124 | baixo |
| `r3-task-external-event` | kind_of_task ExternalEvent recusado explicitamente por falta de gatilho | Mesma recusa nomeada que Event — falta o campo external_event que a spec não sabe escrever. | src/mastertool_bridge/spec/validator.py:439,446,477-482; docs/CAPABILITY_MATRIX.md:124 | baixo |
| `r3-task-freewheeling-nao-provado` | kind_of_task Freewheeling é aceito pelo validador e sai executável, mas nunca foi exercido contra o produto | _KINDS_OF_TASK_SUPPORTED inclui ('Cyclic', 'Freewheeling') — uma spec com kind_of_task=Freewheeling passa na validação e o planner marca a operação configure_task como field_proven (porque o contrato é medido no nível da OPERAÇÃO, não por valor de enum), saindo executable:True. Mas a única execução real medida (run-037 | src/mastertool_bridge/spec/validator.py:446 (_KINDS_OF_TASK_SUPPORTED); docs/49-execucao-w9-tempo-da-task.md:12 (tabela mostra só Cyclic testado nas 3 colunas); src/mastertool_bridge/planner/planner.py:291-294 (field_proven declarado no nível da operação configure_task, sem disti | medio |
| `r3-task-parent-synchron` | kind_of_task ParentSynchron e a propriedade parent_synchron_task recusados | ParentSynchron é membro do enum medido, mas fica fora de _KINDS_OF_TASK_SUPPORTED (só Cyclic/Freewheeling), então a validação de kind_of_task recusa (mesma mensagem de gatilho ausente aplicada genericamente aos não suportados). A propriedade correlata parent_synchron_task está deliberadamente fora de MASTERTOOL_PROPERT | src/mastertool_bridge/spec/validator.py:439-446,477-482; scripts/mastertool/common/safety.py:107-113 ('parent_synchron_task' citado como settable no stub e fora da allowlist); docs/CAPABILITY_MATRIX.md:126 | baixo |
| `r3-task-watchdog` | watchdog.* de task recusado deliberadamente | Ausência deliberada da allowlist de propriedade: watchdog tem receptor próprio no stub (ScriptWatchdog) e nunca foi adicionado a MASTERTOOL_PROPERTY_WRITES. Nome nunca alcança a porta de segurança — recusado por não estar catalogado, fail-closed, com motivo documentado no próprio código. | scripts/mastertool/common/safety.py:107-113 (comentário normativo: 'watchdog.* tem RECEPTOR proprio ... receptor novo e verificacao nova'); scripts/mastertool/common/safety.py:111-113 (MASTERTOOL_PROPERTY_WRITES só tem as 4 propriedades); docs/CAPABILITY_MATRIX.md:125 | baixo |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## R5

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r5-fbd-leitura` | Leitura de FBD (parser, modelo canônico e mapeamento de schema real) não iniciada | canonical_model.py:44 declara LANGUAGES=('LD','FBD','SFC') e validate() (linhas 584-587) aceita qualquer um dos três como language válido de um GraphicPOU — mas isso é só um enum de validação. ladder_parser.py:116 só itera elementos <LD> ('ld_bodies = [e for e in root.iter() if _local_name(e.tag) == "LD"]') e ladder_pa | src/mastertool_bridge/plcopen/canonical_model.py:44,584-587; src/mastertool_bridge/plcopen/ladder_parser.py:116,536; docs/CAPABILITY_MATRIX.md:156-158 ('FBD e SFC, em leitura ou autoria — nenhum parser, nenhum modelo canônico. Reservado para R5 ... e R7 ..., ambos não iniciados') | **alto** |
| `r5-sfc-leitura` | Leitura de SFC (modelo de steps/transitions/actions, análises de estado) não iniciada | Mesma situação do FBD: LANGUAGES aceita 'SFC' só como valor de enum de validação, sem parser ou modelo associado. Nenhum export SFC real foi obtido — o único censo real disponível (docs/21 §17, docs/17) é de uma POU LD. Nenhum arquivo em src/mastertool_bridge/plcopen/ trata steps, transitions ou actions. | src/mastertool_bridge/plcopen/canonical_model.py:44; grep 'FBD\|SFC' em src/ → só canonical_model.py:44 e discovery/graphic_language_scan.py (classificação L0, não parsing); docs/CAPABILITY_MATRIX.md:156-158; docs/14-ladder-roadmap.md §L8, linhas 718-762 (modelo nunca implementad | **alto** |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## R7

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r7-import-plcopen-nunca-exercido` | `import_xml` está autorizado no contrato de segurança desde a W1 mas nunca foi invocado nem uma vez — a rota de importação PLCopen preferida pelo roadmap é só uma linha em uma allowlist | docs/28-contrato-escrita-controlada-mastertool-x.md:74 já lista 'import_xml -> permitido' desde o contrato original da primeira mutação (W1), e scripts/mastertool/common/safety.py:74 cataloga import_xml em MASTERTOOL_MUTATING_OPERATIONS — mas nenhuma operação em EXECUTOR_CONTRACT o consome, no mesmo padrão já documenta | docs/28-contrato-escrita-controlada-mastertool-x.md:74,319-320; scripts/mastertool/common/safety.py:74; grep '\.import_xml\(' no repositório inteiro → só tests/unit/test_probe_44_w3_preflight.py:364, test_probe_45_w3_author.py:468, test_probe_47_verify_factory.py:293, todos checa | **alto** |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## R8

| ID | O que precisa ser medido | Estado hoje | Evidência | Risco |
|---|---|---|---|---|
| `r8-diagnosticos-nao-iniciado` | Leitura de diagnósticos de dispositivo/hardware não tem evidência de implementação | Nenhum probe, módulo ou documento de execução trata leitura de diagnóstico de dispositivo/hardware (distinto de diagnóstico online, que é operação proibida por escopo). Não há registro de tentativa nem de recusa nomeada. | sem evidência localizada | baixo |
| `r8-fieldbus-topology-partial` | Leitura de fieldbus (EtherNet/IP, Modbus) cobre parâmetros de comunicação, mas não a topologia scanner→adaptador nem assemblies/RPI com confiança alta | device_inventory.py interpreta parâmetros de IP/subnet/gateway/unit_id/porta a partir do export XML por dispositivo, com hierarquia de evidência declarada. O próprio achado registrado no doc admite que parâmetros de comunicação (IP, RPI, assemblies) ficam presos em confiança 'média' por virem de tipos genéricos (ARRAY  | src/mastertool_bridge/inventory/device_inventory.py:92-143 (vocabulário de parâmetros); docs/25-inventario-de-comunicacao.md:132-156 ("Achado registrado") | medio |
| `r8-hardware-tree-unclassified` | Leitura estrutural de racks/CPUs/cartões/canais não existe — nem os nós de hardware do template atual estão identificados | Enunciado correto: 'Nenhum código lê a árvore de configuração de hardware (rack/CPU/cartão/canal). No template de qualificação vigente (42 nós), o inventário por type_guid classifica 11 nós como dispositivo/hardware (categoria reconhecida, mas sem decomposição em rack/CPU/cartão/canal/endereço) e deixa outros 13 nós co | docs/36-qualificacao-template-tmf-v1.md:60-77 e :145-153 ("O que são os 13 nós não catalogados... ninguém sabe o que são"); docs/CAPABILITY_MATRIX.md:164-167 declara a lacuna explicitamente | **alto** |
| `r8-io-address-validations` | Nenhuma validação de endereçamento de I/O implementada (duplicado, canal sem variável, variável sem canal, módulo ausente, revisão incompatível, gap, overlap) | Busca no repo inteiro por overlap/gap/duplicidade de endereço não encontrou nenhuma lógica de validação de hardware. Depende do modelo estrutural de rack/cartão/canal (pendência r8-hardware-tree-unclassified), que ainda não existe. | docs/CAPABILITY_MATRIX.md:164-167 ("validações... não implementadas; reservado para R8"); nenhum arquivo em src/ com lógica correspondente — sem evidência localizada de implementação | **alto** |
| `r8-opcua-nao-iniciado` | Leitura de OPC UA não tem nenhuma evidência de implementação ou investigação | Enunciado correto da evidência: 'Nenhuma menção a OPC UA como capacidade de leitura em código, testes ou documentação de execução. O termo aparece em 6 arquivos do repo, mas fora do ROADMAP.md as outras 5 ocorrências (SAFETY_MODEL.md, 08-safety.md, safety-policy.yaml, change-request-template.md, risk-assessment-templat | sem evidência localizada (grep por "OPC UA"/"opcua" no repositório inteiro só retorna ROADMAP.md) | medio |
| `r8-variable-io-binding-isolado` | Vínculo variável↔I/O existe só como reconhecimento textual do binding ST (`AT %I/%Q/%M`), sem correlação com o modelo físico de rack/cartão/canal nem documentado como capacidade R8 | st_lexer.py e declaration_parser.py reconhecem `AT %IX0.0` etc. na declaração de variável e expõem `hardware_address` nas consultas do indexador (query.py). Isso é o único elo real hoje, mas fica isolado do lado físico (rack/cartão/canal), que não existe (ver r8-hardware-tree-unclassified), e não aparece em CAPABILITY_ | src/mastertool_bridge/indexer/declaration_parser.py:386-459; src/mastertool_bridge/indexer/st_lexer.py:44,145; src/mastertool_bridge/indexer/query.py:130; docs/13-static-project-indexer.md:56 | baixo |

<caption>

**Como ler:** "Estado hoje" é o que o repositório mostra agora, com a
correção do verificador aplicada quando houve. "Evidência" aponta onde
conferir. Nenhuma linha afirma que o produto não suporta o recurso —
afirma que ninguém mediu.

</caption>

## Limite desta fila

Nenhum destes itens foi verificado com o MasterTool aberto — é essa
exatamente a razão de existirem aqui. A fila diz o que medir e onde
conferir; ela não antecipa o resultado da medição, e um item pode sair
daqui tanto como `proven` quanto como `contradicted`. Ver o vocabulário em
`PENDENCIAS.md` §7.2.
