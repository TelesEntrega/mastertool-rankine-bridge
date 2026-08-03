"""A qualificação tem de ser DO arquivo que ela autoriza.

Verificação estática de `run_project_factory.ps1` e do artefato que o
`probes/35` grava.

O ACHADO
========
Até 2026-08-02 o bloco de elegibilidade da fábrica conferia
`authoring_eligible` e mais nada. `qualify-analysis.json` — o artefato que a
fábrica consulta — não dizia de qual projeto falava: o `sha256` do arquivo
existia só no `qualify-completion.json`, que a fábrica não lê.

Consequência: apresentar a qualificação de um projeto autorizava escrita em
outro, e nada detectava. Apareceu ao montar o lote de reversão, onde cada alvo
é uma saída diferente e o atalho seria reusar UMA qualificação para as dez —
com o lote inteiro parecendo conferido.
"""

import io
import os
import re

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FABRICA = os.path.join(_REPO, "scripts", "mastertool", "run_project_factory.ps1")
PROBE35 = os.path.join(_REPO, "scripts", "mastertool", "probes",
                       "35_qualify_template_readonly.py")


@pytest.fixture(scope="module")
def fabrica():
    return io.open(FABRICA, encoding="utf-8-sig").read()


@pytest.fixture(scope="module")
def probe35():
    return io.open(PROBE35, encoding="utf-8").read()


def test_a_fabrica_compara_o_sha_da_qualificacao_com_o_do_template(fabrica):
    assert "qualification.project.sha256" in fabrica
    assert re.search(r"qualification\.project\.sha256\.ToLower\(\)\s*-ne\s*"
                     r"\$templateSha", fabrica)


def test_qualificacao_SEM_identidade_e_recusa_e_nao_aviso(fabrica):
    """Campo ausente não é "confere", pelo mesmo motivo que
    `authoring_eligible` ausente não é "elegível"."""
    trecho = fabrica[fabrica.index("qualification.project"):]
    trecho = trecho[:trecho.index("Write-Host \"[OK] Qualificacao")]
    assert trecho.count("Fail (") == 2, trecho
    assert "Write-Warning" not in trecho


def test_a_recusa_explica_o_ESCOPO_de_uma_qualificacao(fabrica):
    assert ("vale para o arquivo onde " in fabrica
            and "para mais nenhum" in fabrica)


def test_o_probe_35_poe_a_identidade_NO_ARTEFATO_QUE_A_FABRICA_LE(probe35):
    """`qualify-completion.json` já tinha o `sha256`. Ele não servia: a decisão
    é tomada a partir do `qualify-analysis.json`."""
    trecho = probe35[probe35.index("def write_artifacts"):]
    trecho = trecho[:trecho.index("qualify-report.md")]
    assert 'analise["project"] = result.get("project")' in trecho
    assert "qualify-analysis.json" in trecho


def test_a_identidade_e_a_MEDIDA_e_nao_uma_nova(probe35):
    """`result["project"]` é o bloco que o probe já mediu (`sha256`, `size`,
    `path`). Recalcular aqui abriria espaço para as duas divergirem."""
    assert "_project_sha256_and_size" in probe35
    assert 'analise["project"] = result.get("project")' in probe35


def test_a_fabrica_nao_confere_identidade_no_estagio_de_BUILD_e_por_que(fabrica):
    """No `-ExecuteBuild` não existe `-TemplateProject`: o projeto relevante é
    a SAÍDA, que a etapa anterior produziu e cujo hash o host já confere contra
    o declarado. Amarrar a qualificação ali exigiria qualificar cada saída
    duas vezes, sem responder a nenhuma pergunta nova."""
    posicao_check = fabrica.index("qualification.project.sha256")
    posicao_build = fabrica.index("if ($Mode -eq 'ExecuteBuild')")
    assert posicao_check > posicao_build, (
        "a conferência mora no caminho de ExecutePlan, depois do desvio de "
        "build — se migrar para antes, este teste tem de ser reescrito com o "
        "motivo novo")
