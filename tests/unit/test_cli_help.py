"""`--help` do CLI, e por que ele não era testado.

O comando `--help` do CLI inteiro morria com `TypeError: %o format: an
integer is required, not dict`. A causa era **uma** string: `"100% offline"`
no `help=` de `verify-cli-probe`. `argparse` interpola todo `help=` contra um
dicionário (`self._get_help_string(action) % params`), e `% o` virava a
conversão `%o`.

O defeito atravessou a suíte porque nada aqui chamava `format_help()`. Cada
subcomando tinha teste de comportamento; a ajuda, que é o primeiro contato de
quem opera a ferramenta, não tinha nenhum. Estes testes fecham isso pela
propriedade e não pelo caso: **toda** ajuda tem que formatar, inclusive as que
ainda não existem.
"""

import argparse

import pytest

from mastertool_bridge.cli import build_parser


def _subparsers(parser):
    for acao in parser._actions:
        if isinstance(acao, argparse._SubParsersAction):
            return acao
    raise AssertionError("o CLI deixou de ter subcomandos")


def _nomes():
    return sorted(_subparsers(build_parser()).choices)


def test_a_ajuda_do_cli_inteiro_formata():
    """O teste que faltava. `--help` quebrado é a ferramenta inutilizável para
    quem ainda não sabe usá-la."""
    texto = build_parser().format_help()
    assert "usage" in texto.lower()


@pytest.mark.parametrize("nome", _nomes())
def test_a_ajuda_de_cada_subcomando_formata(nome):
    sub = _subparsers(build_parser()).choices[nome]
    assert sub.format_help()


def test_toda_string_de_ajuda_sobrevive_a_interpolacao():
    """A regra, e não o caso: `argparse` aplica `% params` a cada `help=`.
    Um `%` literal precisa ser `%%`, e isto vale para argumento que ninguém
    escreveu ainda."""
    parser = build_parser()
    fila = [parser]
    vistos = []
    while fila:
        atual = fila.pop()
        for acao in atual._actions:
            if isinstance(acao, argparse._SubParsersAction):
                fila.extend(acao.choices.values())
                vistos.extend(acao._choices_actions)
                continue
            vistos.append(acao)
    quebradas = []
    for acao in vistos:
        ajuda = getattr(acao, "help", None)
        if not isinstance(ajuda, str):
            continue
        try:
            ajuda % {"prog": "x", "default": "x"}
        except (TypeError, ValueError, KeyError):
            quebradas.append(ajuda)
    assert quebradas == []


def test_o_texto_que_quebrava_continua_LEGIVEL_na_ajuda_impressa():
    """Guarda contra a "correção" que apaga o texto em vez de escapá-lo:
    `100%` tem que continuar aparecendo para quem lê a ajuda."""
    bruto = [a.help or "" for a in _subparsers(build_parser())._choices_actions]
    assert any("100%% offline" in a for a in bruto), "o literal tem que ser %%"
    # E o que sai IMPRESSO é o `%` de verdade — a interpolação desfaz o escape.
    # A ajuda quebra linha, então a comparação é sobre o texto normalizado.
    impresso = " ".join(build_parser().format_help().split())
    assert "100% offline" in impresso
