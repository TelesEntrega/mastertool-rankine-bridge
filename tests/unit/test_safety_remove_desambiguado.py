"""`remove` cru é identidade insuficiente — adversariais nas DUAS direções.

Contrato `docs/87` §4. Medição: `docs/api` §superfície de MEMBRO.

    IScriptTextDocument.remove(offset, length)   apaga CARACTERES
    IScriptObject.remove()                       apaga O OBJETO DA ÁRVORE

O nome nu estava em `MASTERTOOL_MUTATING_OPERATIONS` como operação de conteúdo
textual, e a allowlist é por nome. **Uma fase que autorizasse a primeira
autorizaria a segunda** — falso negativo no gate, que é o lado caro. É o inverso
do achado já documentado sobre `insert`/`append`/`remove` existirem em
`IScriptTextDocument` **e** em `list`/`sys.path`, onde o risco era falso
positivo na guarda.

A regra que estes testes congelam não é sobre `remove`:

> Quando um mesmo nome de método existe em superfícies com efeitos
> semanticamente diferentes, o nome nu não constitui identidade suficiente para
> autorização.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO_ROOT / "scripts" / "mastertool"
sys.path.insert(0, str(SCRIPTS))

from common import safety  # noqa: E402


TEXTO = "text:remove"
OBJETO = "object:remove"


def test_o_nome_nu_NAO_esta_no_registro() -> None:
    assert "remove" not in safety.MASTERTOOL_MUTATING_OPERATIONS
    assert TEXTO in safety.MASTERTOOL_MUTATING_OPERATIONS
    assert OBJETO in safety.MASTERTOOL_MUTATING_OPERATIONS


def test_o_nome_nu_recusa_COM_A_RAZAO_CERTA(monkeypatch) -> None:
    """Cair no "nome desconhecido" genérico mandaria o leitor catalogar algo
    que já está catalogado duas vezes."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", "FASE_QUALQUER")
    monkeypatch.setitem(safety.PHASE_ALLOWED_OPERATIONS, "FASE_QUALQUER",
                        frozenset([TEXTO, OBJETO]))
    with pytest.raises(safety.SafetyError) as erro:
        safety.assert_controlled_write_allowed("remove")
    mensagem = str(erro.value)
    assert "AMBIGUO" in mensagem
    assert TEXTO in mensagem and OBJETO in mensagem


# =============================================================================
# OS DOIS ADVERSARIAIS DO CONTRATO
# =============================================================================

def test_autorizar_TEXTO_nao_autoriza_OBJETO(monkeypatch) -> None:
    """Direção 1. Uma fase de edição textual não pode ganhar o poder de apagar
    objetos da árvore de brinde."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", "FASE_SO_TEXTO")
    monkeypatch.setitem(safety.PHASE_ALLOWED_OPERATIONS, "FASE_SO_TEXTO",
                        frozenset([TEXTO]))

    assert safety.assert_controlled_write_allowed(TEXTO) is True

    with pytest.raises(safety.SafetyError) as erro:
        safety.assert_controlled_write_allowed(OBJETO)
    assert OBJETO in str(erro.value)


def test_autorizar_OBJETO_nao_autoriza_TEXTO(monkeypatch) -> None:
    """Direção 2, e não é simetria decorativa: a fase de revert do R3.1B
    autoriza `object:remove` e NÃO pode escrever no texto de ninguém."""
    monkeypatch.setattr(safety, "CONTROLLED_WRITE_PHASE", "FASE_SO_OBJETO")
    monkeypatch.setitem(safety.PHASE_ALLOWED_OPERATIONS, "FASE_SO_OBJETO",
                        frozenset([OBJETO]))

    assert safety.assert_controlled_write_allowed(OBJETO) is True

    with pytest.raises(safety.SafetyError) as erro:
        safety.assert_controlled_write_allowed(TEXTO)
    assert TEXTO in str(erro.value)


# =============================================================================
# a regra, e não o caso
# =============================================================================

def test_nenhum_verbo_ambiguo_sobreviveu_NU_no_registro() -> None:
    """Se um nome entra no mapa de ambíguos, ele não pode continuar valendo
    sozinho — senão a divisão seria decorativa."""
    for nu, qualificados in safety.MASTERTOOL_AMBIGUOUS_BARE_VERBS.items():
        assert nu not in safety.MASTERTOOL_MUTATING_OPERATIONS, nu
        assert nu not in safety.MASTERTOOL_PROPERTY_WRITES, nu
        for q in qualificados:
            assert q in safety.MASTERTOOL_MUTATING_OPERATIONS, q
            # a identidade qualificada CARREGA a superfície, e não só um sufixo
            assert ":" in q and q.endswith(":" + nu), q


def test_nenhuma_fase_autoriza_verbo_nu() -> None:
    for fase, operacoes in safety.PHASE_ALLOWED_OPERATIONS.items():
        for nu in safety.MASTERTOOL_AMBIGUOUS_BARE_VERBS:
            assert nu not in operacoes, (fase, nu)


def test_a_divisao_NAO_afrouxou_o_registro() -> None:
    """Dividir não pode virar porta de entrada.

    A versão anterior afirmava `CONTROLLED_WRITE_PHASE is None`, o que era
    conveniência e não o invariante: ela quebraria assim que qualquer fase
    abrisse, por razão nenhuma. O que importa é que **a fase ativa não autorize
    nenhuma das duas identidades** — e o nome nu, jamais.
    """
    fase = safety.CONTROLLED_WRITE_PHASE
    autorizadas = (safety.PHASE_ALLOWED_OPERATIONS.get(fase) or frozenset()
                   if fase else frozenset())
    for operacao in (TEXTO, OBJETO):
        if operacao in autorizadas:
            continue
        with pytest.raises(safety.SafetyError):
            safety.assert_controlled_write_allowed(operacao)
    # O nome nu não passa NUNCA, com fase ou sem fase.
    with pytest.raises(safety.SafetyError):
        safety.assert_controlled_write_allowed("remove")
