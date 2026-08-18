"""O registro CANÔNICO de capacidades, derivado do contrato do executor.

POR QUE ELE EXISTE (achado RV1-3)
=================================
`load_attestation` aceitava `known_capabilities=None` e, nesse caso, **não
conferia nome de capacidade nenhum**. O caminho de produção nunca passava o
conjunto, então uma attestation podia declarar `voar` e o carregador
promovia — porque quem tinha de lembrar de ligar a conferência era o chamador.

Validação que depende de o chamador lembrar não é validação. O registro agora
é derivado do `EXECUTOR_CONTRACT`, e o carregador o usa por padrão. Substituir
o conjunto continua possível (um teste precisa disso); **desligá-lo, não**.

14 OPERAÇÕES, 13 CAPACIDADES
============================
O espaço de capacidades é o das APIs exercidas, não o dos verbos do plano:

- `create_program_call` e `replace` consomem a MESMA API (`replace` sobre o
  documento da POU de perfil) e convergem para a mesma capacidade;
- `configure_task` NÃO tem `mastertool_operation` — é o conjunto das quatro
  escritas de propriedade, e não uma chamada de método. Derivar capacidade só
  de `mastertool_operation` deixava essa de fora, e ela caía como não provada
  mesmo com attestation completa.

A derivação mora aqui, num lugar só, porque as duas regras acima já foram
reimplementadas de formas divergentes em pontos diferentes do código.
"""

from __future__ import annotations

from mastertool_bridge.planner.planner import EXECUTOR_CONTRACT


def _capacidade(operation: str, contract: dict) -> str:
    """A capacidade que uma operação de plano exige.

    Ordem: `required_capability` explícito, depois a API do MasterTool,
    depois o próprio nome da operação. O último caso é `configure_task`, e ele
    é a razão de a função existir em vez de um `contract["mastertool_operation"]`
    espalhado.
    """
    return (contract.get("required_capability")
            or contract.get("mastertool_operation")
            or operation)


OPERATION_TO_CAPABILITY: dict[str, str] = {
    operation: _capacidade(operation, contract)
    for operation, contract in EXECUTOR_CONTRACT.items()
}

# Conjunto FECHADO. Capacidade fora dele é recusada — attestar o que o planner
# não sabe executar é declarar sobre coisa nenhuma.
KNOWN_CAPABILITIES: frozenset[str] = frozenset(OPERATION_TO_CAPABILITY.values())


def capability_of(operation: str) -> str:
    """Capacidade de uma operação. Operação desconhecida devolve o próprio
    nome, e cabe a quem chama recusá-la — aqui não se inventa capacidade."""
    return OPERATION_TO_CAPABILITY.get(operation, operation)
