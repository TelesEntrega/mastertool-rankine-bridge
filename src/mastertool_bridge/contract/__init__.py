"""O contrato entre o NÚCLEO e o PRODUTO OPERACIONAL.

Seis schemas descrevem tudo que atravessa a fronteira entre as duas árvores:

    authoring-plan          o que o planner emite e o executor consome
    execution-manifest      o que a sessão de escrita registra sobre si mesma
    execution-completion    o veredito da execução
    verification-result     o veredito da releitura independente
    capability-attestation  a maturidade medida, carregada em runtime
    evidence-bundle         o manifesto do pacote selado

POR QUE UM CONTRATO, E POR QUE AGORA
====================================
A separação entre núcleo público e produto interno já é física. O que não
existia era o acordo explícito: o probe gravava, o host lia, e **nada conferia
a forma**. Quatro dos seis artefatos nunca tiveram schema — eles eram um
acordo entre dois arquivos de código que ninguém tinha escrito num terceiro
lugar.

UM LUGAR CANÔNICO POR SCHEMA
============================
`authoring-plan` e `capability-attestation` moraram, cada um, dentro do pacote
que os produzia. Agora moram aqui, e o código carrega daqui.

O motivo não é arrumação: **duas cópias de um schema divergem**. É a mesma
disciplina que faz `MATURITY_SCALE` não ser redefinida no loader de
attestation, e seria estranho criar um contrato entre árvores já duplicado.

Isso difere da regra "classificar, não mover" que vale para `docs/`: lá o
caminho é citado em mensagem de commit e em artefato de run, e mover quebraria
o rastro. Schema é consumido por CÓDIGO — o caminho vive em import, não em
registro histórico.

ELE VIAJA COM O PACOTE
======================
Está dentro de `mastertool_bridge/` e não num diretório de topo porque
diretório de topo não entra na wheel. Um contrato que só existe em checkout
não é honrado por um core instalado.

Achado ao mover: os dois schemas anteriores **nunca foram empacotados** —
`package-data` só listava `schemas/*.json`. O código os carregava por caminho,
e numa instalação eles simplesmente não estavam lá.

DUAS FAMÍLIAS DE `schema_version`, E ISSO NÃO É INCONSISTÊNCIA
=============================================================
    artefatos de probe/export   "1.0"   (string)
    camada `src/`               1       (inteiro)

Está em `docs/19` §7. Um contrato único que exigisse inteiro em todos
recusaria todo artefato de campo já produzido — inclusive os que sustentam a
qualificação R1 e R2. As duas famílias estão codificadas, cada uma no seu
schema, e `SCHEMA_FAMILY` diz qual é qual.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_DIR = Path(__file__).resolve().parent

# Nome lógico -> arquivo. Lista LITERAL e fechada: um schema que não está aqui
# não faz parte do contrato, e acrescentar um é decisão, não consequência de
# alguém ter deixado um `.json` na pasta.
SCHEMAS = {
    "authoring-plan": "authoring-plan.schema.json",
    "execution-manifest": "execution-manifest.schema.json",
    "execution-completion": "execution-completion.schema.json",
    "verification-result": "verification-result.schema.json",
    "capability-attestation": "capability-attestation.schema.json",
    "evidence-bundle": "evidence-bundle.schema.json",
}

# Qual família de `schema_version` cada artefato usa. Ver o cabeçalho.
FAMILY_PROBE = "probe"          # string "1.0"
FAMILY_SRC = "src"              # inteiro 1

SCHEMA_FAMILY = {
    "authoring-plan": FAMILY_SRC,
    "execution-manifest": FAMILY_PROBE,
    "execution-completion": FAMILY_PROBE,
    "verification-result": FAMILY_PROBE,
    "capability-attestation": FAMILY_SRC,
    "evidence-bundle": FAMILY_SRC,
}


def schema_path(name: str) -> Path:
    """Caminho do schema. Nome fora do contrato levanta, e isso é o ponto.

    Devolver `None` faria um erro de digitação virar "sem schema", e sem
    schema tudo passa.
    """
    if name not in SCHEMAS:
        raise KeyError(
            "%r não faz parte do contrato. Os seis são: %s"
            % (name, ", ".join(sorted(SCHEMAS))))
    return CONTRACT_DIR / SCHEMAS[name]


def load_schema(name: str) -> dict[str, Any]:
    return json.loads(schema_path(name).read_text(encoding="utf-8"))


def validate(name: str, payload: Any) -> list[str]:
    """Valida `payload` contra o schema. Devolve a lista de problemas.

    Lista vazia é aprovação. Nunca levanta por causa do payload — quem decide
    o que fazer com um artefato inválido é o chamador, e um validador que
    levanta no meio de um pipeline esconde o problema atrás de um traceback.
    """
    try:
        import jsonschema
    except ImportError:                                        # pragma: no cover
        return ["jsonschema não está instalado: a validação não foi feita. "
                "Ausência de validação não é validação bem-sucedida"]

    validador = jsonschema.Draft202012Validator(load_schema(name))
    return ["%s: %s" % ("/".join(str(p) for p in erro.absolute_path) or "(raiz)",
                        erro.message)
            for erro in sorted(validador.iter_errors(payload),
                               key=lambda e: list(e.absolute_path))]
