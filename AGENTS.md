# AGENTS.md — Regras para agentes de IA neste repositório

Este repositório manipula projetos de automação industrial (MasterTool IEC XE 3.63,
CLPs Altus Nexto/NX3008). Erros aqui podem parar planta ou movimentar equipamento.
Leia e obedeça integralmente antes de qualquer tarefa.

## Regras invioláveis

1. **Não invente APIs.** Nunca escreva chamadas a métodos do MasterTool/CODESYS
   ScriptEngine que não foram observados neste ambiente. Fontes válidas:
   `docs/api/mastertool-api-observations.md`, saídas reais de
   `01_discover_environment.py` / `02_dump_api_surface.py`. Se a API não existe:
   registre relatório técnico e deixe a funcionalidade desabilitada — jamais crie
   implementação fictícia que aparenta funcionar.
2. **Não altere o projeto original** do MasterTool. Toda escrita futura opera em
   cópia de trabalho, com backup e hash de origem.
3. **Não habilite importação** (`09/10/11`, `features.import`) sem que as fases de
   leitura, backup, validação e compilação estejam concluídas, testadas e aprovadas
   por humano.
4. **Nenhuma operação online**: login, download, start/stop/reset, force, escrita em
   saídas, modo simulação online. `config/safety-policy.yaml` é lei.
5. **Compatibilidade IronPython 2.7** em `scripts/mastertool/`: sem f-strings,
   `pathlib`, type hints, `dataclasses`, dependências pip. Sempre
   `from __future__ import print_function`. Python 3.11+ só em `src/`, `tools/`,
   `tests/`, `scripts/maintenance/`.
6. **Warning heurístico ≠ erro confirmado.** As análises (`analysis/`) são
   heurísticas; apresente-as como alertas para revisão humana, nunca como certeza.
7. **Commits são autônomos dentro de uma tarefa autorizada** (decisão do
   operador, 2026-08-01/02). Não peça permissão a cada commit — mas mantenha a
   disciplina: um assunto por commit, suíte verde antes, documentação afetada
   no mesmo slice, e **abertura/fechamento de gate sempre em commit isolado**,
   sem implementação junto (`docs/28` §14). Push, PR, merge e tag continuam
   exigindo pedido explícito, e esta árvore **não tem remote por arquitetura**.
8. **Não instale bibliotecas** sem autorização explícita; justifique no README.
9. **`dir()` nunca é fonte de verdade** sobre objetos do ScriptEngine (proxies
   dinâmicos como `ExtendedObject<T>` retornam `dir()` vazio mesmo com membros
   funcionais). Sondagem sempre via `common/capabilities.py: probe_member()`
   contra a whitelist `CAPABILITY_PROBES`, nunca por enumeração livre.
10. **Nunca `repr()`/`str()`/`.ToString()`/formatação implícita em objetos
    `.NET` desconhecidos** — só em primitivos Python nativos ou tipos `.NET`
    confirmados seguros (`common/capabilities.py: build_representation()`).
    `ToString()` é convenção, não garantia técnica.
11. **Limpeza de artefatos reais de runtime** (`workspace/logs/`,
    `workspace/exports/`) só via `scripts/maintenance/safe_clean_artifact.py`
    (dry-run por padrão, exige `--confirm`, exige sentinela). **Nunca** `rm -rf`
    com glob por sufixo — já causou perda de dados reais uma vez (ver
    `docs/api/mastertool-api-observations.md`).
12. **`tree_walker.py` permanece suspenso.** Navegação recursiva da árvore
    passa por `common/read_only_project_scanner.py: ReadOnlyProjectScanner`
    (ver `docs/11-read-only-project-scanner.md`) — limites obrigatórios
    (`max_depth`/`max_total_nodes`/`max_children_per_node`), isolamento de
    falhas por ramo, nunca itera a coleção CLR diretamente
    (`collection[index]` via `range()` Python local, nunca
    `for x in collection`/`iter()`/`GetEnumerator()`). Reativar
    `tree_walker.py` diretamente, ou pular esses limites, exige aprovação
    humana explícita.
13. **Exportação textual (`common/read_only_text_exporter.py:
    ReadOnlyTextExporter`) nunca usa `replace()`/`append()`/`get_line()`/
    `create_pou()`/`create_gvl()`/`create_dut()`/`find()`/`build()`/
    `rebuild()`/`clean()`/`generate_code()`/`save()`/`save_as()`/`close()`,
    nem nenhum setter.** `has_textual_declaration`/`has_textual_implementation`
    são **portões obrigatórios**: `textual_declaration`/`textual_implementation`
    (e seus `.text`) só podem ser acessados depois que o indicador booleano
    correspondente vier **confirmado e estritamente `True`** — nunca acesso
    especulativo. Ver `docs/12-read-only-text-export.md`.

14. **Execução autônoma da bateria de verificação e dos lotes qualificados.**
    Decisão do operador em 2026-08-02, registrada com o risco à vista. Rode
    **sem pedir confirmação a cada vez**:

    - a bateria offline inteira: suíte `pytest`, `tools/check_repo_hygiene.py`,
      guarda de coerência documental, `preflight-batch`, geração de relatório;
    - probes **read-only** no MasterTool;
    - o **lote de repetibilidade com escrita**, incluindo abrir e fechar
      `CONTROLLED_WRITE_PHASE` e rodar `run_repeatability_batch.ps1 -Execute`.

    O que esta regra **não** afrouxa, e continua valendo integralmente:

    - regra 4 (nenhuma operação online: login, download, start/stop, force,
      escrita em saída) e `config/safety-policy.yaml`;
    - regra 2 (o projeto original nunca é alterado — toda escrita é em cópia
      descartável, com hash de origem conferido antes e depois);
    - o gate **fecha assim que o estágio termina**. Não se deixa fase de
      escrita aberta enquanto se prepara o estágio seguinte, nem entre
      sessões;
    - `preflight-batch` verde é **precondição**, não formalidade: qualquer
      recusa impede a sessão;
    - promoção de maturidade continua exigindo medição — nenhum lote promove
      capacidade por si só, e um lote reprovado é reportado como reprovado.

    **Risco aceito e nomeado pelo operador:** com a janela do produto sem
    ninguém olhando, um diálogo inesperado do MasterTool não é visto por
    ninguém. A mitigação existente é a cópia descartável, o timeout do wrapper
    e o journal — não a supervisão humana. Se um diálogo travar a sessão, o
    sintoma será timeout e artefato ausente, e isso **reprova o lote** em vez
    de passar despercebido.

## Como trabalhar

- Gere mudanças pequenas e revisáveis; um assunto por change set.
- Escreva/atualize testes `pytest` para toda alteração na camada externa (`src/`).
- Atualize a documentação afetada no mesmo change set (`docs/`, README).
- Registre decisões técnicas e observações de API em
  `docs/api/mastertool-api-observations.md` (formato de diário definido lá).
- Toda proposta de alteração de código de CLP vira um **change set**
  (`workspace/change-sets/<id>/`, schema em `src/mastertool_bridge/schemas/`),
  com avaliação de risco preenchida (`templates/risk-assessment-template.md`).
- Classifique risco conforme `docs/08-safety.md` (baixo/médio/alto/crítico).
  Crítico = nunca aplicação automática.
- Não marque funcionalidade incompleta como concluída; não oculte falhas.

## Estrutura relevante

- `scripts/mastertool/` — IronPython, roda DENTRO do MasterTool, só exporta dados.
  Numeração `00`-`11` reservada aos scripts FUNCIONAIS da Fase 0-4 (ver
  `docs/10-roadmap.md`). Scripts exploratórios/probes de investigação de API
  vivem em `scripts/mastertool/probes/` (numeração própria, não reutilize um
  número já ocupado por um script funcional).
- `src/mastertool_bridge/` — Python 3, roda FORA, lê exports, analisa, documenta.
- `workspace/` — artefatos gerados (não versionados, exceto `.gitkeep`). Todo
  diretório de execução tem um arquivo sentinela `.mastertool-bridge-run`
  (gravado por `common/file_io.new_export_dir`) — exigido por
  `safe_clean_artifact.py` antes de qualquer remoção.
- `config/safety-policy.yaml` — bloqueios formais; não relaxe sem aprovação humana.
- `config/scanner-defaults.yaml` — limites do `ReadOnlyProjectScanner`
  (genéricos, sem valores específicos de projeto — `expected_root_count`
  específico de um projeto só é passado explicitamente pelo script que
  valida aquele projeto, nunca fixado aqui).

## Fluxo aprovado

```text
descoberta → exportação → validação → análise → documentação → compilação → alteração controlada
```

Nenhuma etapa pode pular as anteriores.
