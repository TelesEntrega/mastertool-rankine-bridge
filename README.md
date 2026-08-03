# mastertool-rankine-bridge

Ponte offline entre o **MasterTool** (IEC XE 3.63/3.70 e **MasterTool X /
MT9000 4.1.0.11**) e Python 3: leitura de projeto, análise estática, indexação
IEC 61131-3, consultas determinísticas, servidor MCP e — sob aprovação
humana, gate por gate — **autoria controlada de objetos de projeto**.

> **Este README é um resumo.** O estado vigente, verificável e datado é
> [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md) — é ele, não este
> arquivo, a fonte canônica. Em caso de conflito entre os dois, vale
> `CURRENT_STATUS.md`.

## Estado em uma frase

A autoria de objetos (GVL, PROGRAM, FUNCTION, FUNCTION_BLOCK, DUT, Task,
Program Call, propriedades de Task) foi **provada em execuções de campo reais
contra o MasterTool X**, incluindo sobre o projeto-base real do cliente, com
build limpo e verificação por reabertura independente (`docs/37`, `docs/39`,
`docs/42`, `docs/46`, `docs/47`, `docs/48`, `docs/49`). Isso é capacidade
medida, não intenção — e não é a mesma coisa que "autorizado a rodar agora":
ver a seção seguinte.

Detalhe completo, marco a marco: [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md),
[`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) e
[`docs/18-estado-e-proximo-passo.md`](docs/18-estado-e-proximo-passo.md).

## Todo portão de escrita está fechado

`CONTROLLED_WRITE_PHASE = None` e `READ_ONLY_PHASE = True` em
`scripts/mastertool/common/safety.py`. Nenhuma operação mutável roda hoje.
Abrir uma fase de escrita é **decisão humana, em commit isolado**, que nunca
carrega implementação junto — o procedimento está em
[`docs/28-contrato-escrita-controlada-mastertool-x.md`](docs/28-contrato-escrita-controlada-mastertool-x.md)
§14. Capacidade provada em campo e gate aberto para uso são coisas
diferentes; este projeto nunca confunde as duas.

## Limites de segurança (permanentes, não negociáveis)

Estes limites não mudam com nenhuma fase futura do roadmap:

- **nunca** modifica o arquivo original de um projeto — toda escrita ocorre
  em cópia de trabalho descartável, com `save_as` para arquivo novo;
- **nunca** faz download, login, modo online, `start`/`stop`, `force` ou
  qualquer acionamento de saída física;
- **nunca** toca o CLP;
- **nenhuma mudança crítica é aplicada sem aprovação humana explícita.**

Formalizado em `config/safety-policy.yaml`, [`docs/08-safety.md`](docs/08-safety.md)
e no contrato [`docs/28`](docs/28-contrato-escrita-controlada-mastertool-x.md).

## Instalação e execução dos testes

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
pytest
```

Duas armadilhas de medição, documentadas por terem custado tempo real:

- **rode com o diretório de trabalho na raiz deste repositório.** Executado
  a partir do diretório pai, o `pytest` também coleta o repositório
  sanitizado vizinho e a coleta morre com dezenas de erros — isso é ambiente,
  não regressão do projeto;
- **não passe `-q` de novo.** `addopts = "-q"` já está em `pyproject.toml`;
  repetir a flag vira `-qq` e o `pytest` suprime a linha de resumo — a suíte
  parece não reportar contagem nenhuma, quando na verdade só ficou silenciosa.

O Python base da máquina não é fonte válida de dependência — instale sempre
pela `.venv` provisionada por `requirements-dev.txt` (há guarda em
`tests/unit/test_test_infrastructure.py`).

## Pontos de entrada

CLI externa (`src/mastertool_bridge/cli.py`, comando `mastertool-bridge`):

```bash
mastertool-bridge validate-export <export_dir>
mastertool-bridge inspect <export_dir>
mastertool-bridge index <export_dir>
mastertool-bridge analyze <export_dir>
mastertool-bridge document <export_dir>
mastertool-bridge compare <export_dir_a> <export_dir_b>
mastertool-bridge find-symbol <export_dir> <nome>
mastertool-bridge find-reads <export_dir> <variavel>
mastertool-bridge find-writes <export_dir> <variavel>
mastertool-bridge build-agent-context <export_dir>
mastertool-bridge validate-change-set <change_set.json>
mastertool-bridge verify-cli-probe --results-dir <dir>
mastertool-bridge supervised-snapshot ...   # orquestração avançada, ver docs/16
```

Servidor MCP (`src/mastertool_bridge/mcp_server.py`, comando
`mastertool-bridge-mcp`), ferramentas expostas via `@mcp.tool()`:
`open_project_index`, `get_index_metadata`, `find_symbol`, `find_reads`,
`find_writes`, `find_calls`, `find_callers`, `ask_project`. Todas operam
sobre um índice já construído em disco — nenhuma escreve no MasterTool.

Scripts internos (IronPython, executados **dentro** do MasterTool, com UI
visível e supervisão humana) ficam em `scripts/mastertool/` — ver
[`docs/03-scripting-discovery.md`](docs/03-scripting-discovery.md) e
[`docs/16-supervised-runner-contract.md`](docs/16-supervised-runner-contract.md).

## Como isto é verificado

Nenhuma fase fecha por declaração. A escala de maturidade — normativa em
[`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) — é:

```text
discovered           API identificada por reflexão/catálogo
field_proven         executada uma vez contra o produto, com evidência real
repeatable           repetida em execuções independentes
template_qualified   validada sobre um Template Profile específico
version_qualified    validada sobre uma versão específica do MasterTool
production_qualified passou por testes negativos, falhas induzidas e escala
```

`field_proven` exige uma execução real citável (relatório de run numerado em
`docs/`), nunca uma alegação. **Trabalho offline nunca promove uma
capacidade** — só constrói o instrumento de medida; a medição em si exige
sessão de campo com operador humano presente.

## Documentação

- [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md) — estado canônico e vigente
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — plano até o v1.0
- [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) — capacidades e maturidade
- [`docs/COMPATIBILITY_MATRIX.md`](docs/COMPATIBILITY_MATRIX.md) — versões e produtos suportados
- [`docs/SAFETY_MODEL.md`](docs/SAFETY_MODEL.md) — modelo de segurança consolidado
- [`docs/28-contrato-escrita-controlada-mastertool-x.md`](docs/28-contrato-escrita-controlada-mastertool-x.md) — contrato de escrita controlada
- [`docs/INDEX.md`](docs/INDEX.md) — índice completo de toda a documentação

Agentes de IA devem ler `AGENTS.md` antes de qualquer tarefa neste repositório.

## Licença e distribuição

Esta árvore é uso interno da Rankine Systems — ver `LICENSE`. O mirror
público sanitizado é publicado separadamente em
[`github.com/TelesEntrega/mastertool-rankine-bridge`](https://github.com/TelesEntrega/mastertool-rankine-bridge),
sob Apache-2.0, por um fluxo próprio (portar mudanças → remover
identificadores → revisar diff → testar → publicar de lá).

**Esta árvore não tem remote git, por arquitetura.** Não adicionar um.
