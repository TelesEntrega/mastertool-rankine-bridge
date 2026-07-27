# Pipeline de análise externa

Entrada: um export validado. Todas as análises são **heurísticas** — apoio à
revisão humana, nunca veredito.

```text
export → validate-export → index → find-* / analyze / document / compare
```

## Componentes

| Comando | Módulo | O que faz |
|---------|--------|-----------|
| `validate-export` | `export/validator.py` | manifesto + schemas + checksums |
| `index` | `export/indexer.py` | objetos + variáveis declaradas (via parser) |
| `find-symbol` | `analysis/reference_finder.py` | todas as ocorrências de um símbolo |
| `find-writes` / `find-reads` | idem | filtra por classificação de uso |
| `analyze` | `analysis/safety_checks.py` | alertas de segurança |
| `document` | `docs/*.py` | inventário + dependências (Mermaid) |
| `compare` | `diff/project_diff.py` | diff textual entre dois exports |
| `build-agent-context` | vários | pacote de contexto para agentes de IA |

## Parser tolerante (`analysis/symbol_parser.py`)

Extrai: cabeçalho do POU (PROGRAM/FB/FUNCTION/TYPE, EXTENDS/IMPLEMENTS),
blocos `VAR*` (com RETAIN/PERSISTENT), variáveis (nome, tipo, array, `AT %...`,
valor inicial), comentários removidos preservando linhas. O que não entender
vai para `Symbol.uncertainties` — nunca é descartado em silêncio.

## Classificação de uso de variáveis

```text
confirmed_write   alvo direto de :=  ou saída "=> var"
probable_write    membro/índice/parâmetro: var.x := / var[i] := / F(par := ...)
confirmed_read    lado direito de := ou dentro de condição IF/WHILE/CASE
probable_read     demais ocorrências em expressão
unknown_usage     chamada var(...) — sem índice de tipos não se distingue
                  função (leitura) de instância FB (estado alterado)
```

## Fase 2 (pendente)

Máquinas de estado (`state_machine.py`), duplicatas, complexidade e diff
semântico levantam `NotImplementedPhaseError` até a segunda entrega.
