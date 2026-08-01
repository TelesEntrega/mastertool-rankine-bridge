# Varredura completa da árvore do projeto

`probes/21_scan_project_tree_full.py` — varredura recursiva **somente
leitura** de toda a árvore de um projeto aberto, com isolamento de erro por
nó e limites recebidos por argumento.

## Por que existe

`03_list_project_tree.py` é código morto: ele chama `common/tree_walker.py`,
suspenso desde 2026-07-23 porque presumia nomes de navegação sem evidência.
Toda função dele levanta `TreeNavigationSuspended`.

`probes/12_validate_recursive_scanner.py` usa o scanner real, mas com limites
fixos no módulo (`MAX_DEPTH=6`, `EXPECTED_ROOT_COUNT=4`) calibrados para um
projeto de 92 nós, e grava dentro de `workspace/logs/`.

Este probe é o runner fino que faltava: mesmos limites, mas **por argumento**;
`expected_root_count=None`, porque a quantidade de raízes de um projeto não se
presume a partir de outro; e saída **obrigatoriamente fora do repositório**.

## O que entrega

```text
project-tree.json    árvore completa, um registro por nó
flat-nodes.json      lista achatada com node_id, pai, profundidade, índice
node-indexes.json    índices auxiliares
errors.json          erros por nó, isolados
manifest.json        procedência e veredito
report.md            resumo legível
```

## Argumentos

| Argumento | Default | Observação |
|---|---|---|
| `--output` | — | **obrigatório**, sem espaço, fora do repositório |
| `--max-depth` | 32 | finito sempre; profundidade ilimitada não é oferecida |
| `--max-total-nodes` | 20000 | idem |
| `--max-children-per-node` | 1024 | idem |

Sem espaço no `--output` porque o MT8500 quebra o valor de `--scriptargs` em
espaço em branco (achado do probe 15). Fora do repositório porque a árvore de
um projeto real carrega nomes de equipamento e de variável do cliente.

## Status e código de saída

| Status | Quando | Exit |
|---|---|---|
| `complete` | nenhum limite atingido, nenhum erro de nó | 0 |
| `complete_with_node_errors` | erros isolados, registrados em `errors.json` | 0 |
| `truncated` | **qualquer** limite atingido | 2 |
| `fatal` | não foi possível varrer | 1 |

`truncated` tem **precedência sobre erro de nó**: árvore incompleta não vira
"completa" só porque os nós visitados foram bem. **Nenhuma varredura truncada
pode ser apresentada como árvore completa.**

A propagação do exit code pelo MT8500 nunca foi observada — só `exit_code=0`
apareceu até hoje. O `status` do manifesto é a fonte autoritativa.

## Manifesto

Registra versão e build do MasterTool (via `FileVersionInfo` do assembly de
entrada), runtime de script, caminho e **SHA-256 do projeto aberto**, limites
configurados, raízes observadas, total de nós, profundidade máxima,
`limits_hit`, erros por nó e a safety declaration do scanner.

## Execução

Sobre **cópia descartável**, offline, UI visível, sem salvar:

```text
MT8500.exe --project="<...>\_descartavel\<Projeto> COPIA.project"
           --runscript="<repo>\scripts\mastertool\probes\21_scan_project_tree_full.py"
           --scriptargs:"--output=C:\saida-scan"
```

Aspas **embutidas no token**: `Start-Process -ArgumentList` no PowerShell 5.1
não acrescenta aspas em elemento que contém espaço (achado t1 de 2026-07-24).

## Resultado real observado

Projeto industrial de 194 nós, MasterTool 3.70.300.00:
`complete`, 4 raízes, profundidade máxima **7**, 0 erros por nó, nenhum limite
atingido, cópia byte a byte idêntica antes e depois.

A profundidade real ficou muito abaixo do default de 32 — a preocupação com
profundidade era infundada, e o dado corrige a suposição.

**A varredura alcançou o que o export XML monolítico não escreve.** No mesmo
projeto, o export do projeto inteiro truncava numa subárvore e perdia
servidor e cliente MODBUS, sete escravos, os adaptadores EtherNet/IP e duas
interfaces de rede. A navegação nó a nó trouxe todos. Ver
[23-export-por-dispositivo.md](23-export-por-dispositivo.md).

## `object_guid` não é identidade estável

Duas varreduras do mesmo projeto, em sessões diferentes do MasterTool:

```text
194 nos comparados    0 nomes diferentes    0 type_guid diferentes
4 object_guid diferentes
```

Os quatro: o POU de programa referenciado pela task principal, os dois POUs de
task do scanner EtherNet/IP, e `__VisualizationStyle`. São nós de
**referência** sob Task Configuration e um nó de estilo — o MasterTool lhes
atribui GUID novo a cada sessão.

Consequência prática: **não use `object_guid` como identidade ao comparar duas
varreduras**, ou aparecerão mudanças que não existem. `name` e `type_guid` se
mantiveram estáveis nos 194 nós.

## Limites do probe

- não lê parâmetro de dispositivo e não toca `ScriptDriverDeviceObject`:
  enumerar a árvore **não** autoriza ler parâmetro;
- não toca `device_repository` nem nada de `online`;
- não compila, não salva, não fecha, não cria e não modifica objeto;
- não importa, reativa ou substitui `tree_walker`.

A lógica testável (argumentos, validação de caminho, identidade do runtime)
vive em `common/probe_cli.py`, com testes em `tests/unit/test_probe_cli.py`.
Probe que roda dentro do MasterTool não é testável; módulo comum é.
