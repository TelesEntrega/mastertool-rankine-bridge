# Estado corrente — fonte canônica

> **Esta página é a única fonte do estado vigente do projeto.** Qualquer outro
> documento que descreva "o estado atual" ou está apontando para cá, ou é
> histórico. Em caso de conflito, **esta página vence** — exceto contra um
> relatório de execução, que é evidência datada e nunca é sobrescrito: se um
> relatório contradiz esta página, a página é que está errada e precisa ser
> corrigida.
>
> **Regra de manutenção:** esta página é atualizada **no mesmo slice** que muda
> o estado, nunca depois. Slice que muda estado e não atualiza esta página não
> fecha.

| | |
|---|---|
| Medido em | 2026-08-02 |
| Branch | `main`, árvore limpa |
| `HEAD` | `96ad2a2` |
| Suíte | **4237 passed, 3 skipped, 0 failed** |
| Cobertura | **86%** linha+ramo em `src/mastertool_bridge/`, medida e **sem meta imposta** — [`COVERAGE_BASELINE.md`](COVERAGE_BASELINE.md) |
| Fase corrente | **R2 — as QUATRO palavras do gate medidas, e o ciclo fecha nas duas direções.** Atômica e verificável (`docs/52`), reprodutível N=10 (`docs/53`), reversível (`docs/54`), reversão repetível N=10 (`docs/55`), e desfazer a reversão N=10 (`docs/56`) |
| Interpretador | `.venv\Scripts\python.exe` |
| Remote | **nenhum, por arquitetura** — ver §7 |
| `READ_ONLY_PHASE` | `True` (`scripts/mastertool/common/safety.py:20`) |
| `CONTROLLED_WRITE_PHASE` | **`None`** (`safety.py:312`) — nenhuma fase de escrita aberta |

---

## 1. Estado em um parágrafo

O projeto tem duas bases funcionais e provadas contra o produto real: **leitura,
extração e análise** de projetos MasterTool, e **autoria controlada** de
projetos no MasterTool X (MT9000 4.1.0.11), partindo de uma especificação JSON,
passando por planner offline, executor IronPython, `save_as`, reabertura, build
e verificação.

**A fase R1 foi executada e aprovada em 2026-08-02** (`docs/50`): dez execuções
independentes da mesma spec sobre o mesmo template, dez builds verificados sem
aviso do fabricante, dez verificações aprovadas, **10/10 equivalentes** e
independência limpa nos **45 pares**. Onze operações passaram para
`repeatable`; três continuam `field_proven` porque a spec do lote reusa a
`MainTask` e não as toca.

**Antes dela houve um piloto `N = 3`, e ele pagou por si.** Achou três defeitos
mecânicos que teriam custado dez execuções cada:

| # | Defeito | Sintoma |
|---|---|---|
| 1 | o seletor semântico lia o nome da **raiz**, e `ScriptProject` não expõe `get_name` | `AttributeError` virava "1 nó ilegível" → recusa nas 3 runs, sem escrever nada |
| 2 | `container_selection` não era persistido | a recusa dizia "1 nó ilegível" e o artefato não dizia **qual** |
| 3 | `-BuildPlan` recebia o plano de **autoria** | o probe 40 espera outro documento; as 3 runs reprovaram antes de compilar |

<caption>

**Como ler:** o defeito 1 escapou do gate offline porque **todo fixture
sintético tinha raiz com nome legível** — o dublê era mais capaz que o produto.
É o achado de método mais caro desta fase.

</caption>

**Quem produziu a evidência, e quem não produziu:**

| Componente | Papel | O que o N=10 provou sobre ele |
|---|---|---|
| `run_repeatability_batch.ps1` | orquestrador operacional — abre o produto | aprovado em campo, 2 estágios × 10 runs |
| `automation/generation_equivalence.py` | comparador do conjunto | exercido sobre artefatos reais |
| `automation/batch_preflight.py` | precondições host-side | exercido nos dois preflights |
| `automation/repeatability.py` | **modelo testável do lote, fora do caminho de campo** | **nada** — continua validado só offline |

<caption>

**Como ler:** atribuir ao runner Python a evidência que o wrapper PowerShell
produziu seria creditar um componente pelo trabalho de outro. Ele não roda no
lote.

</caption>

**Próximo passo:** `template_qualified` exige fechar as duas lacunas do perfil
— inventário de dispositivos e library lock — e as três operações de task
exigem um lote com spec que crie task. O levantamento completo está em
[`PENDENCIAS.md`](PENDENCIAS.md); o que só fecha com o produto aberto, em
[`FIELD_QUALIFICATION.md`](FIELD_QUALIFICATION.md).

### Entradas congeladas da qualificação

```text
spec       C:\mastertool-x-r1\specs\w7-factory-full-v1.json   (somente leitura)
           sha256 2e382c763ce4796a99f44cdf58ae5f18003c8a4f44d3fdc174e1f37a08db1481
           cópia byte a byte da spec das runs 034 e 035 (docs/47) — as duas
           registram o MESMO sha256, e os bytes foram recuperados, não reconstruídos
template   C:\mastertool-x-w2	emplate\TemplateExemplo_v1.project
           sha256 596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5
produto    MT9000 4.1.0, v4.1.0.11 — caminho EXPLÍCITO: há onze instalações
           Altus nesta máquina, e a busca automática recusa com as onze nomeadas
lote       C:\mastertool-x-r1\qualificacao-n10
```

### Como um lote é executado

```powershell
# preflight fail-closed, ANTES de abrir o produto
mastertool-bridge preflight-batch --stage plan --runs 10 ...

# gate aberto em commit ISOLADO: CONTROLLED_WRITE_PHASE = "W7_FACTORY_FULL"
scripts\mastertool
un_repeatability_batch.ps1 -Stage plan -Runs 10 -Execute
# gate fechado em commit ISOLADO: None

# gate aberto em commit ISOLADO: CONTROLLED_WRITE_PHASE = "W7_VERIFY_BUILD"
scripts\mastertool
un_repeatability_batch.ps1 -Stage build -Runs 10 -Execute
# gate fechado em commit ISOLADO: None
```

O estágio `plan` **não emite veredito** — a verificação roda dentro do
`-ExecuteBuild`. Sem `-Execute`, o wrapper planeja e não abre nada.

## 2. O que está provado, e em que grau

A escala de maturidade e a lista operação a operação, com evidência, ficam em
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md). O resumo:

| Grau | Quantas operações | Significado |
|---|---|---|
| `production_qualified` | **0** | nenhuma operação passou por testes negativos, falhas induzidas e escala |
| `version_qualified` | **0** | nenhuma foi validada contra mais de uma versão do MasterTool |
| `template_qualified` | **0** | exige o perfil do template sem lacuna, e duas seguem abertas: inventário de dispositivos e library lock |
| `repeatable` | **14** | **todas.** R1 N=10 em duas specs canônicas (`docs/50` e `docs/51`): vinte execuções independentes ao todo, vinte builds verificados, 10/10 equivalentes em cada lote, independência limpa nos 45 pares de cada |
| `field_proven` | **0** | nenhuma operação parou neste grau: as catorze subiram |
| `discovered` | demais | catalogadas por reflexão, nunca exercidas |

As catorze são as chaves de `EXECUTOR_CONTRACT`
(`planner/planner.py:176-382`), e o número vem do código, não de contagem
manual: `create_gvl`, `create_program`, `create_function`,
`create_function_block`, `create_dut`, `create_task`, `create_program_call`,
`bind_program_to_task`, `configure_task`, `replace`, `save_as`, `reopen`,
`build`, `verify`. Dessas, **doze mutam o produto** — `reopen` e `verify` são
leitura. Note que `create_program_call` e `bind_program_to_task` são operações
**distintas** com receptores distintos (`replace` na `MainTask` × `add` na lista
da task criada), e `configure_task` não é chamada de método: é o conjunto das
quatro escritas de propriedade.

> Registros anteriores desta contagem diziam "treze". O número correto é o que o
> `EXECUTOR_CONTRACT` declara.

**O planner é fail-closed em `field_proven`** (`planner/planner.py:1379`,
`"executable": not gaps`): uma spec que exija operação apenas catalogada sai
`executable: False` com o gap nomeado. Essa distinção fechou um fail-open real
— spec com FB saía executável porque a API estava catalogada, embora W1.5 só a
tivesse exercido para ler o texto de nascimento e descartar a cópia sem salvar.

### O que a evidência comprova

- O sistema **cria, preenche, persiste e compila** um projeto lógico em ST
  sobre o projeto-base real, com 0 erros e 0 avisos (`docs/37`, `run-019`).
- A **fábrica completa** funciona: spec de máquina com 7 objetos de 5 famílias e
  dependência real → 0 erros, 0 avisos, 7 de 7 verificados, conteúdo equivalente
  entre duas gerações independentes (`docs/47`, runs 034/035).
- **`create_task` funciona** e a task criada recebe POU pela própria lista
  (`task.pous.add`) — `create_program_call` e `bind_program_to_task` são
  operações distintas, com receptores distintos (`docs/48`, `run-036`).
- **Escrita de propriedade existe e é verificada por releitura** (`docs/49`,
  `run-037`): quatro propriedades de task (`kind_of_task`, `interval`,
  `interval_unit`, `priority`).
- **Determinismo foi medido** em cinco gerações da mesma spec (`docs/40`) e na
  fábrica (`docs/44`). O critério é **equivalência de conteúdo**, não igualdade
  de bytes: o `.project` carrega GUID e timestamp, então comparar o arquivo
  reprova sempre.
- `save_as` **não toca a entrada** — mesmo SHA-256 antes e depois.
- **Alteração transacional de objeto PREEXISTENTE** (`docs/52`, W10,
  `w10-edit-existing-001`): a `UserPrg` do template — que o plano **não** cria —
  teve o texto substituído depois de o executor conferir, no campo e no instante
  anterior ao `replace`, que o sha256 do texto anterior era o **medido** nas dez
  runs de `docs/50`. Build verde sem aviso de convenção, e a comparação
  antes×depois deu `only_authorized_changed`: os 42 nós idênticos, e o único
  texto alterado é o autorizado. **Repetido N=10** (`docs/53`): dez execuções
  independentes, dez `before_hash_verified`, dez builds sem aviso de convenção,
  dez `only_authorized_changed`, template intacto nas dez, e dez pacotes de
  evidência `sealed_complete`. O grau é `repeatable`.
- **Reversão medida** (`docs/54`, par `w10-rev-001`/`w10-rev-002`): a alteração
  aceita foi desfeita **pelo mesmo mecanismo**, com o hash anterior conferido no
  campo nas duas direções, e a spec inversa **emitida** do plano e do texto
  anterior — não escrita à mão. Contra o template original, o projeto revertido
  não mudou em nada: 42 nós idênticos e `authorized_but_unchanged` no texto. O
  executor passou a gravar o CONTEÚDO anterior (`rollback/before-texts.json`),
  porque hash não reconstrói texto. A reversão tem **uma** execução: repeti-la
  exige mecanismo de lote que não existe, já que cada reversão amarra o
  `expected_before` a uma saída específica — mecanismo construído em
  `run_rollback_batch.ps1` e **medido N=10** em `docs/55`: dez reversões
  independentes, dez `before_hash_verified`, dez builds verdes, e nas dez o
  texto original de volta com o projeto indistinguível do template. E a volta
  seguinte também: `docs/56` re-aplica o texto nas dez, fechando o ciclo
  `template → alterado → revertido → re-alterado` com `UserPrg` alternando
  entre **exatamente dois** valores, nenhum deles declarado — todos medidos.
  *Redo* não ganhou fase própria porque não é operação nova: a spec inversa da
  reversão é a alteração original sobre outra base.

### O que exige medição em campo

Nada abaixo pode ser resolvido offline. Cada item exige o MasterTool executando,
com operador presente:

- repetibilidade (≥10 execuções independentes) — **R1**;
- ~~alteração de objeto **existente** — **R2/W10**, nunca exercida~~ — **EXERCIDA** em
  2026-08-02 (`docs/52`): `before_hash_verified` no campo, build verde,
  `only_authorized_changed`. **Repetida N=10 em `docs/53`** — dez execuções
  independentes, 10/10 em tudo: é `repeatable`;
- alteração de **propriedade de task preexistente** — o executor não tem a busca
  por task já existente; só o lado do host está escrito;
- `Alias` e `Union` de DUT; FB com `base_type`, interfaces, métodos, ações e
  propriedades; `watchdog.*`; `event` / `external_event` / `core_binding`;
- as 17 bibliotecas *placeholder* — nenhum build fixa para que versão resolvem;
- determinismo com task criada (**n = 1**);
- escala real — o limite do executor é 512 passos e a maior spec exercida tem 24;
- outra máquina, outra instalação, outro template;
- **e, permanente: que o CLP executa.** O `.project` declara `t#500ms`; ninguém
  mediu ciclo. Isso está fora do escopo do produto e continuará estando.

## 3. Baseline estrutural — remedida, ainda não formalizada como perfil

O projeto-base foi trocado em 2026-07-31 por um template com **cartões de I/O**,
e a base nova **já foi varrida** (`docs/36`, runs 010/011):

```text
arquivo                TemplateExemplo v1.project
sha256                 596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5
tamanho                503.040 bytes            (contra 287.152 da base anterior)
classe                 projeto sintético com controlador NX3008 e cartões de I/O configurados
cópia                  C:\mastertool-x-w2\template\TemplateExemplo_v1.project   (somente leitura)
árvore                 3 raízes, 42 nós         (a base anterior tinha 34)
persistent_tree_sha256 162d4fd747532bc0d9a6f22dc12eeaabcf59397ec4210e6787f68f1edf89f647
Application            root/1/0/0, match único por nome + type_guid
tasks                  MainTask em root/1/0/0/3
não catalogados        13 nós, contados e classificados `unclassified`
```

A identidade **posicional** da base anterior — 34 nós, `structure_sha256
b2825550…` — está invalidada e não deve mais ser citada. Note o achado de
método: `root/1/0/0` **continua valendo** apesar dos cartões de I/O, e isso foi
**medido, não presumido** — o probe resolve o container por busca (nome +
`type_guid`) e reporta o que achou. Presumir teria dado certo por sorte, o que
é o pior resultado possível.

Duas ressalvas que viajam com esses números:

- `persistent_tree_sha256` **cobre a árvore inteira**, não só os objetos
  persistentes: o scanner reaproveitado não lê `is_transient_object` por nó. A
  ressalva está no próprio campo do artefato;
- o `node_path` está amarrado ao `sha256` **deste** arquivo, e o registry
  recusa usá-lo com outro. Editar o template invalida a medição.

### Elegibilidade

`docs/36` fechou com o template **medido e NÃO elegível** — dois campos não
eram mensuráveis com a superfície catalogada (`compiler_version_unresolved`,
`libraries_unresolved`). Os dois foram resolvidos depois, por medição:
`compiler_version` = `3.5.18.50` (`run-012`, commit `59e8637`) e o inventário
de **17 bibliotecas**, conferido por duas rotas (`run-016`, commit `a3b17f9`).
As duas medições foram ligadas ao probe de qualificação em `a9dd252`, e desde a
`run-018` o template está **elegível para autoria** — que é o que permitiu W1.4
em diante.

> **Lacuna documental registrada:** essa resolução está nos commits e no
> histórico de `18-estado-e-proximo-passo.md`, mas **nenhum documento numerado
> de execução a registra**. Quem lesse apenas `docs/36` concluiria que o
> template segue inelegível, e concluiria errado. A correção não é editar o
> `docs/36` — ele é evidência datada. É esta nota, e o Template Profile da R0b.

**R0b — parte offline FECHADA.** Os números estão congelados como Template
Profile versionado em
[`config/template-profiles/mastertool-x-4.1.0.11-tmf-v1-io.json`](../config/template-profiles/mastertool-x-4.1.0.11-tmf-v1-io.json),
validado por `mastertool_bridge.templates.profile`. O perfil traz **proveniência
por campo** — a run e o documento que mediram cada número — que é o registro que
faltava para a lacuna acima: as entradas de `run-012`, `run-016` e `run-018`
estão no próprio perfil, e um campo medido sem origem reprova a carga.

A identidade posicional saiu do caminho de escrita: o executor resolve o
container por **nome + `type_guid` sobre a árvore inteira, com cardinalidade 1**
(`templates/selector.py` no host, `select_unique_node` no `probes/46`), e
`node_path` sai no artefato apenas como diagnóstico.

O que **continua aberto** na R0b, e depende de sessão de campo:

| Lacuna | Por quê |
|---|---|
| `device_inventory` | nenhuma run mediu o inventário de dispositivos deste arquivo — e hash de inventário não computado seria invenção |
| `library_lock` | as 17 bibliotecas são *placeholder*; sem versão resolvida não há trava a computar |
| `capability_qualification` | R1 não executada: nenhuma repetição independente medida. O perfil **não pode** declarar capacidade acima de `field_proven` enquanto houver lacuna — a carga recusa |

O perfil também é a prova de que **autorável e qualificado são coisas
diferentes**: ele deriva `authoring_eligible = True` (W6–W9 rodaram sobre este
arquivo com build verde) e `qualified = False` (as três lacunas acima), ao mesmo
tempo, sem contradição.

## 4. Dívida técnica conhecida e nomeada

| Onde | O que | Consequência |
|---|---|---|
| ~~`probes/46:281,507`~~ | ~~`CONTAINER_NODE_PATH = "root/1/0/0"` — seleção **posicional**~~ | **PAGA na R0b.** O executor seleciona o container por nome + `type_guid` sobre a árvore inteira, com cardinalidade 1 (`select_unique_node`); `node_path` sai no artefato como diagnóstico. A constante não existe mais, e um teste reprova se ela voltar |
| `probes/27, 30, 32, 34, 38` | continuam resolvendo o container por `plan["container"]["node_path"]` (4–5 ocorrências cada) | **escopo declarado da R0b**: o gate foi fechado no pipeline vigente (planner → `emit_authoring_plan` → `probes/46`), que não emite nem consome `node_path`. Esses cinco são probes de fase única das execuções W1.1–W1.4, com `CONTROLLED_WRITE_PHASE = None` — só rodam se a fase deles for reaberta. **Não foram migrados de propósito:** são o instrumento exato citado por `docs/33`, `docs/34` e `docs/37`, e reescrevê-los tornaria as runs documentadas irreproduzíveis. Migrar exige reabrir a fase e remedir |
| `tools/check_repo_hygiene.py` | a regra de caminho local não via barra **escapada** (`C:\\...`) | **PAGA.** O separador virou `\\{1,2}`. O achado real: `probes/43` tinha caminho de instalação fixo e produzia zero achados, e os outros três probes eram pegos por acidente, pela docstring. `probes/43` entrou na catraca |
| `tools/check_repo_hygiene.py` | varre só o que `git ls-files` devolve — **arquivo novo é invisível até ser commitado** | o gate acerta o veredito e o dá tarde: a suíte ficou verde antes de `3d2d7a6` e vermelha depois, com seis achados nas próprias fixtures do teste. Documentado no docstring do verificador; incluir untracked tornaria o local mais estrito que a CI, e a escolha é do operador |
| ~~`changes/approval.py:9`~~ | ~~`record_approval`/`check_approval` levantam `NotImplementedPhaseError`~~ | **PAGA.** Aprovação implementada sobre a máquina de estados (`changes/lifecycle.py`), com a decisão **amarrada ao `bundle_sha256`**: se o pacote muda depois da decisão, a aprovação deixa de valer — ninguém aprovou aquele conteúdo |
| ~~`changes/package_builder.py:9`~~ | ~~`build_package` levanta `NotImplementedPhaseError`~~ | **SUPERADA.** O pacote da R2 é `evidence/bundle.py`, com o layout de `ROADMAP` §2.7, manifesto com sha256 por arquivo e detecção de alteração, remoção e acréscimo após o selo. O nome antigo continua levantando **de propósito**: descrevia outro layout, e não tem chamador |
| `diff/semantic_diff.py:9` | `semantic_diff` levanta `NotImplementedPhaseError` | diff é textual e estrutural, não semântico; alvo da R2 |
| `scripts/host/run_cli_probe_test.ps1` | procura processo por `MT8500*` | contra o MT9000 diria "sem instância" e "sem órfão" **sempre** |
| `plcopen/` | não há semântica simbólica (L5), resolução contra o índice ST (L6), nem FBD/SFC (L8) | Ladder é estrutura e topologia, não significado; alvo das R4/R5 |
| bibliotecas | 17 *placeholder*, sem library lock | build não fixa versão; alvo da R3 |

## 5. O que existe hoje, por camada

**Structured Text** — cadeia completa e validada: árvore → export textual →
parser ST → símbolos/DUT → referências → read/write → chamadas → consultas
determinísticas → API Python → servidor MCP.

**Autoria** — `spec` (validador offline) → `planner` (plano literal, sem texto
final, só hashes) → `probes/46` (executor IronPython, mutadores guardados) →
`save_as` → reabertura → `build` → verificação.

**Ladder** — `structure_map` → `ladder_parser` → `canonical_model` →
`logical_topology`. Semântica em backlog, promovida a fase R4 do roadmap.

**Dispositivos** — trilha encerrada. Cobertura final 35/35 dispositivos, 1894
parâmetros, por export isolado dispositivo a dispositivo.

**Superfícies externas** — CLI com 13 subcomandos (`cli.py:405-588`); servidor
MCP com 8 ferramentas, **todas somente leitura** sobre um índice já construído
em disco (`mcp_server.py:189-232`).

## 6. Modelo de segurança — resumo

O detalhe está em [`SAFETY_MODEL.md`](SAFETY_MODEL.md) e o contrato normativo em
[`28-contrato-escrita-controlada-mastertool-x.md`](28-contrato-escrita-controlada-mastertool-x.md).
O essencial:

- **Duas portas separadas**, porque são dois modos de falha diferentes:
  `assert_controlled_write_allowed` (chamada de método) e
  `assert_controlled_property_write_allowed` (atribuição a atributo). A segunda
  existe porque a primeira **não recusava** `task.interval = x` — ela **não
  via**: guarda de chamada procura `Call`, e atribuição é `Assign` com alvo
  `Attribute`.
- **Fail-closed em nome desconhecido.** Já houve um `assert_operation_allowed`
  que falhava **aberto** para todo nome fora da lista legada; a correção foi
  registro literal de mutadores + porta única.
- **Sem `setattr` no executor**, com teste de AST proibindo. `getattr` continua
  permitido, com a assimetria declarada: leitura errada devolve dado errado,
  escrita errada muda o produto.
- **Estar no mapa de allowlists ≠ estar autorizada.** Quem autoriza é
  `CONTROLLED_WRITE_PHASE`; as entradas ficam no mapa como registro histórico.
- **Três estados, nunca dois**: presente, ausente, **não medido**. Ausência de
  mensagem nunca é aprovação (`no_build_messages`).

## 7. Publicação

Esta árvore **não tem e não terá remote**. Publicação acontece apenas pelo repo
sanitizado `github.com/TelesEntrega/mastertool-rankine-bridge`, por fluxo
separado. Dado de cliente nunca entra em nenhum dos dois: XML, árvore de
projeto e inventário de dispositivo ficam fora, e as fixtures são sintéticas.

**Achado de 2026-08-03 — o repositório público contradiz a política.** Esta
seção diz Apache-2.0, e o `LICENSE` desta árvore (§3b) declara a mesma coisa:
*"o núcleo sanitizado é publicado separadamente, sob Apache-2.0"*. Mas o
arquivo `LICENSE` **que está no repositório público** nunca foi trocado: ele
ainda é o provisório, diz *"Uso interno. Todos os direitos reservados"* e pede
para ser substituído "quando a política de distribuição for definida" — que já
está definida, aqui.

Não é a página que está errada: é o arquivo publicado que ficou para trás. O
guarda `test_licenca_nao_e_provisoria` reprova sobre ele, e **a troca não foi
feita por mim**: licença é instrumento jurídico e a decisão é do operador.
Pendência aberta.

**A sanitização virou código** em `tools/sanitize_for_publication.py`. Até
2026-08-02 ela era feita à mão, arquivo por arquivo; as regras foram DERIVADAS
do que já estava publicado, comparando os dois repositórios, e o comando é
fail-closed: termo proibido que sobreviva à substituição impede a cópia. O
próprio módulo e o teste dele **não** são publicados — eles carregam o mapa
entre nome real e nome fictício de cada cliente.

## 8. Como retomar

1. Ler esta página, depois [`ROADMAP.md`](ROADMAP.md) e
   [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).
2. Para o histórico detalhado de como se chegou aqui, ler
   [`18-estado-e-proximo-passo.md`](18-estado-e-proximo-passo.md) — que passa a
   ser **registro histórico de retomada**, não fonte de estado.
3. Rodar a suíte **com cwd na raiz do repo** (do diretório pai ela coleta o repo
   sanitizado vizinho e morre com 49 erros de coleta) e **sem passar `-q`**
   (`addopts = "-q"` já está no `pyproject.toml`; `-qq` suprime a linha de
   resumo). **Ler a linha inteira** — `3660 passed` sem o prefixo `1 failed`
   seria relato incompleto, e isso já foi cometido neste projeto.
4. Nenhuma fase de escrita abre sem commit próprio e isolado (`docs/28` §14).

## 9. Ordem de fechamento de slice

```text
1 contrato documental → 2 validação → 3 COMMIT DOCUMENTAL (antes do código)
→ 4 implementação → 5 gate (testes + suíte + validador) → 6 CURRENT_STATUS
→ 7 memórias → 8 commit da implementação → 9 push/tag só se autorizado
```
