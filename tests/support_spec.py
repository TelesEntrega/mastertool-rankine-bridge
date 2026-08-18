"""Fixtures de SPEC compartilhadas, e por que elas moram FORA de um `test_`.

Um módulo de teste que importa outro módulo de teste amarra a publicação do
primeiro à do segundo. Isso deixou de ser teórico: `test_spec_method_r3_1b`
importava `test_project_spec_validator` e `test_member_rollback` importava
`test_planner` — dois módulos que o publicador RECUSA por conteúdo. O núcleo
público saiu com os importadores dentro e os importados fora, e a suíte de lá
não COLETAVA. Erro de coleta é a pior forma de suíte quebrada: ela não reprova,
ela nem roda.

O `template.id` daqui é sintético de propósito. O identificador do cliente não
tem por que aparecer num fixture que não exercita o template real — quem
exercita (`test_planner`, nas asserções sobre o sha do template de campo)
continua com o nome verdadeiro, e continua fora da publicação, que é o certo.

Mesma ideia de `support_attestation.py`: o que é compartilhado entre testes é
apoio, não teste.
"""

from __future__ import annotations

from mastertool_bridge.spec.validator import ST_LANGUAGE_GUID

# Sintético. Não corresponde a template nenhum em disco, e o `sha256` de `a`
# repetido existe para deixar isso óbvio na leitura.
TEMPLATE_SINTETICO = {"id": "TPL-v1", "sha256": "a" * 64}


def minimal_valid_spec() -> dict:
    """Spec mínima, mas com dependências cruzadas em TODAS as direções
    permitidas, para que os testes de ordem de criação e de referência
    tenham algo real para exercitar."""
    return {
        "schema_version": 1,
        "template": dict(TEMPLATE_SINTETICO),
        "duts": [
            {
                "name": "ST_Point",
                "kind": "STRUCT",
                "language": {"guid": ST_LANGUAGE_GUID},
                "declaration": "TYPE ST_Point :\nSTRUCT\n x : INT;\nEND_STRUCT\nEND_TYPE\n",
            },
        ],
        "gvls": [
            {
                "name": "GVL_AI_TESTE",
                "declaration": "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR",
                "uses": ["ST_Point"],
            },
        ],
        "functions": [
            {
                "name": "FUNC_Add",
                "language": {"guid": ST_LANGUAGE_GUID},
                "declaration": "FUNCTION FUNC_Add : INT\nVAR_INPUT\n a: INT;\nEND_VAR\n",
                "implementation": "FUNC_Add := a;\n",
                "return_type": "INT",
                "uses": [],
            },
        ],
        "function_blocks": [
            {
                "name": "FB_Counter",
                "language": {"guid": ST_LANGUAGE_GUID},
                "declaration": "FUNCTION_BLOCK FB_Counter\nVAR\n c: INT;\nEND_VAR\n",
                "implementation": "c := c + 1;\n",
                "uses": ["FUNC_Add"],
            },
        ],
        "programs": [
            {
                "name": "PRG_AI_TESTE",
                "language": {"guid": ST_LANGUAGE_GUID},
                "declaration": "PROGRAM PRG_AI_TESTE\nVAR\n xLocal : BOOL;\nEND_VAR\n",
                "implementation": "xLocal := FALSE;\n",
                "uses": ["FB_Counter", "GVL_AI_TESTE"],
            },
        ],
        "tasks": [
            {"name": "MainTask", "program_calls": ["PRG_AI_TESTE"]},
        ],
        "libraries": [
            {"name": "Standard"},
        ],
    }


def spec_with_methods() -> dict:
    """A mínima, com MEMBROS no FUNCTION_BLOCK (R3.1B, `docs/87`).

    As duas formas de retorno convivem no MESMO owner de propósito:
    `IniciarPasso` sem tipo de retorno — a forma do caso canônico, e a
    representação nativa da API, não convenção nossa — e `Calcular : BOOL`
    com retorno. Um fixture com só uma das formas deixaria passar um planner
    que trata `return_type` ausente como string vazia.
    """
    spec = minimal_valid_spec()
    spec["tasks"] = [
        {"name": "MainTask", "program_calls": ["PRG_AI_TESTE"]},
        # Com tempo declarado: sem isso a task nasceria a `t#20ms` com
        # prioridade 1, mais rápida e mais prioritária que a MainTask
        # (`docs/48` seção 4).
        {"name": "TaskDiagnostico", "program_calls": ["PRG_AI_TESTE"],
         "kind_of_task": "Cyclic", "interval": "t#500ms", "priority": 20},
    ]
    spec["function_blocks"][0]["methods"] = [
        {"name": "IniciarPasso",
         "declaration": "METHOD IniciarPasso\nVAR_INPUT\n i : INT;\nEND_VAR",
         "implementation": "c := i;"},
        {"name": "Calcular",
         "declaration": "METHOD Calcular : BOOL",
         "implementation": "Calcular := c > 0;",
         "return_type": "BOOL"},
    ]
    return spec
