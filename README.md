# mastertool-rankine-bridge

Ponte entre o **MasterTool** (Altus) e ferramentas externas em Python 3, em duas
metades que se sustentam:

- **Ler** — exportação estruturada, indexação semântica, análise estática e
  versionamento em Git de projetos existentes (IEC XE 3.63/3.70).
- **Escrever** — uma **fábrica de projetos** para o MasterTool X (MT9000
  4.1.0.11): de uma especificação declarativa em JSON sai um projeto que
  compila, sob um gate de escrita controlada que autoriza uma operação por vez.

```text
spec.json → planner (offline) → plano de autoria → executor → .project → build
```

> **Somente leitura continua sendo a base.** `READ_ONLY_PHASE = True` nunca é
> desligado; a escrita acontece por uma **fase nomeada** cuja allowlist literal
> autoriza operações uma a uma, sempre em cópia descartável. Nenhum script aqui
> faz download, entra em modo online ou toca o CLP — e isso não é configurável.

## O que a fábrica prova, e como

Treze operações de autoria, cada uma **exercida contra o produto real** dentro
de uma cadeia que persistiu (`save_as`) e compilou (`build`) — nunca declarada a
partir da existência da API:

| | |
| --- | --- |
| Objetos IEC | GVL, PROGRAM, FUNCTION, FUNCTION_BLOCK, DUT (STRUCT/ENUM) |
| Estrutura | task, vínculo de programa, chamada idiomática, tempo de task |
| Cadeia | texto, persistência, reabertura, compilação, verificação |

Um projeto de máquina com 7 objetos de 5 famílias, gerado **duas vezes** sobre
cópias novas: 0 erros, 0 avisos, 7 de 7 objetos verificados, conteúdo
equivalente entre as duas gerações. Os registros de execução estão em
`docs/37` a `docs/49`, um por marco — incluindo os que reprovaram.

### A distinção que sustenta o resto

`cataloged` (a API existe no catálogo) **≠** `field_proven` (a operação foi
medida numa cadeia completa). O planner é *fail-closed* na segunda: ele recusa
emitir plano executável com operação não provada, e a prova exige citar a
execução que a produziu. Marcar sem medir seria declarar em vez de medir — e um
teste que fazia exatamente isso foi o primeiro defeito que essa separação pegou.

> **Nomes de projeto neste repositório são fictícios.** A ferramenta foi
> desenvolvida e validada contra um projeto real de planta, que não é publicado.
> Todo identificador de exemplo na documentação e nos testes (`ExemploPlanta`,
> `TemplateExemplo v1`, `FB_PISCA_EXEMPLO`, `VarEquipamentosExemplo`, GUIDs
> `00000000-...`) é um substituto neutro, **não** uma API do MasterTool nem um
> valor a copiar. Os nomes que pertencem à plataforma CODESYS/Altus —
> `Application`, `Device`, `Plc Logic`, `MainPrg`, `SystemPOUs`,
> `Task Configuration`, `UserPrg` — foram mantidos porque documentam o
> ambiente, não um projeto específico.
>
> Consequência prática: os `expected_*_guid` de configuração vêm como
> placeholder. Isso é deliberado — os probes **falham fechado** até você
> configurar a identidade do seu próprio projeto, em vez de carregar a
> identidade de outra pessoa. Os SHA-256 citados nos registros de execução
> referem-se ao projeto-base real e, portanto, a um arquivo que não está aqui.

## O que o projeto faz (hoje)

- Scripts IronPython para rodar **dentro** do MasterTool (menu de scripting):
  - `00_smoke_test.py` — verifica que o ambiente de scripting funciona;
  - `01_discover_environment.py` — inventaria objetos globais e APIs disponíveis;
  - `02_dump_api_surface.py` — introspecção segura da superfície de API (whitelist);
  - `scripts/mastertool/probes/` — probes de descoberta empírica, executados e
    confirmados em runtime real contra `ExemploPlanta V1.0.project` (navegação,
    identidade de nós, coleção de filhos em múltiplos níveis — ver
    `docs/api/mastertool-api-observations.md` e `docs/10-roadmap.md`);
  - `common/read_only_project_scanner.py` — **`ReadOnlyProjectScanner`**:
    varredura recursiva, somente leitura, com limites obrigatórios
    (profundidade/total de nós/filhos por nó), isolamento de falhas por ramo
    e saída inteiramente serializável (ver
    `docs/11-read-only-project-scanner.md`). Implementado e testado
    externamente; execução real ainda não autorizada.
  - `common/read_only_text_exporter.py` — **`ReadOnlyTextExporter`**:
    exportação textual somente leitura da subárvore da Application
    (declaração/implementação ST), com portões booleanos obrigatórios
    (`has_textual_declaration`/`has_textual_implementation`) antes de
    qualquer leitura de texto, limites obrigatórios adicionais (objetos
    textuais/caracteres) e preservação exata do texto (sem normalização,
    com SHA-256 por documento — ver `docs/12-read-only-text-export.md`).
    Implementado e testado externamente; execução real ainda não autorizada.
- CLI externa `mastertool-bridge` (Python 3.11+) para validar, inspecionar, indexar
  e analisar os exports gerados.
- Schemas JSON, política de segurança formalizada, testes unitários da camada externa.

## O que o projeto NÃO faz

- Não altera o projeto original do MasterTool.
- Não compila (feature `compile` desabilitada por padrão).
- Não importa alterações (scripts 09–11 são estruturas desabilitadas).
- Não realiza nenhuma operação online: login, download, start/stop, force, escrita em saídas.
- Não altera configuração de hardware.

## Requisitos

- Windows com MasterTool IEC XE 3.63 instalado (para os scripts internos).
- Python 3.11+ (para a camada externa).
- Git.

O interpretador interno do MasterTool é assumido como **IronPython 2.7**
(ecossistema CODESYS ScriptEngine) até evidência em contrário — ver
`docs/03-scripting-discovery.md`.

## Instalação da camada externa

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
pytest
mastertool-bridge --help
```

## Como executar os scripts internos no MasterTool

1. Abra o MasterTool IEC XE 3.63 com um projeto carregado.
2. Localize o menu de scripting (tipicamente *Ferramentas → Scripting → Executar script*;
   registre o caminho real em `docs/03-scripting-discovery.md`).
3. Execute, nesta ordem:
   1. `scripts/mastertool/00_smoke_test.py`
   2. `scripts/mastertool/01_discover_environment.py`
   3. `scripts/mastertool/02_dump_api_surface.py`
   4. `scripts/mastertool/03_list_project_tree.py`
4. Os artefatos são gravados em `workspace/exports/<timestamp>/` e logs em `workspace/logs/`.

Atalhos `.bat` em `scripts/windows/` abrem as pastas e mostram instruções.

## Validando um export

```bash
mastertool-bridge validate-export workspace/exports/<diretorio>
mastertool-bridge inspect workspace/exports/<diretorio>
mastertool-bridge index workspace/exports/<diretorio>
mastertool-bridge find-symbol workspace/exports/<diretorio> NomeDoSimbolo
```

## Política de segurança

Formalizada em `config/safety-policy.yaml` e `docs/08-safety.md`. Resumo:

1. Toda operação de escrita futura exigirá: cópia de trabalho → backup → diff textual
   → validação estrutural → compilação → **aprovação humana**.
2. Operações online e download são proibidos pela política, não apenas desencorajados.
3. Alterações de risco **crítico** (saídas físicas, `%Q`, segurança de máquina,
   hardware, redes industriais) nunca são aplicadas automaticamente.

## Estado das fases

| Fase | Descrição | Estado |
|------|-----------|--------|
| 0 | Descoberta do ambiente | Scripts prontos — aguardando execução no MasterTool |
| 1 | Exportação somente leitura | Parcial: árvore (`03`); exportador completo (`04`) pendente de validação da Fase 0 |
| 2 | Análise externa | Base implementada (parser tolerante, busca de referências, validador) |
| 3 | Compilação e validação | Não implementada (desabilitada por configuração) |
| 4 | Importação controlada | Não implementada (bloqueada por política) |

## Limitações conhecidas

- Nenhuma API do MasterTool foi confirmada ainda neste ambiente; os scripts usam
  acesso defensivo (introspecção + adaptadores) e registram o que não encontrarem.
- O parser IEC 61131-3 é **tolerante e heurístico**, não um compilador; resultados de
  análise são alertas para revisão humana.
- Objetos gráficos (LD/FBD/SFC) podem não ter exportação textual; o export registra
  metadados e segue adiante.

## Dependências

Runtime externo: `pyyaml`, `jsonschema`. Dev: `pytest`. Qualquer dependência nova
deve ser justificada aqui antes de adicionada. Scripts IronPython não usam nenhuma
dependência externa.

## Documentação

Comece por `docs/00-overview.md` e `docs/01-architecture.md`.
Agentes de IA devem ler `AGENTS.md` antes de qualquer tarefa.
