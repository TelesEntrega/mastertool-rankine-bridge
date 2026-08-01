"""Impede que a infraestrutura de teste volte a mentir.

Este arquivo nao testa comportamento do produto. Ele testa a condicao que,
quando falhou, tornou a suite incapaz de distinguir regressao nova de ambiente
incompleto: sete testes `async def` de `tests/test_mcp_server_e2e.py` falhavam
em "async def functions are not natively supported" porque `pytest-asyncio`
nunca foi declarado em manifesto nenhum -- existia por instalacao manual num
interpretador, e nao no outro.

O padrao que estes testes guardam e sempre o mesmo: **uma capacidade que o
codigo do repositorio EXIGE tem de estar declarada num manifesto do
repositorio**, e nao apenas presente por acidente no ambiente de quem rodou.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REQUIREMENTS_DEV = REPO_ROOT / "requirements-dev.txt"
PYPROJECT = REPO_ROOT / "pyproject.toml"
TESTS_DIR = REPO_ROOT / "tests"
MCP_SERVER = REPO_ROOT / "src" / "mastertool_bridge" / "mcp_server.py"


def _declared_dev_requirements() -> list[str]:
    """Linhas uteis de `requirements-dev.txt`, sem comentario e sem vazia."""
    linhas = REQUIREMENTS_DEV.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in linhas if ln.strip() and not ln.lstrip().startswith("#")]


def _declared_runtime_dependencies() -> list[str]:
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return list(dados["project"]["dependencies"])


def _requirement_named(nome: str, declaradas: list[str]) -> str | None:
    """Devolve a linha que declara `nome`, ou None.

    Compara pelo nome normalizado (PEP 503: `_` e `.` equivalem a `-`), para
    que `pytest_asyncio` e `pytest-asyncio` nao sejam tratados como pacotes
    diferentes.
    """
    alvo = re.sub(r"[-_.]+", "-", nome).lower()
    for linha in declaradas:
        cabeca = re.split(r"[<>=!~;\[]", linha, maxsplit=1)[0].strip()
        if re.sub(r"[-_.]+", "-", cabeca).lower() == alvo:
            return linha
    return None


def _arquivos_de_teste() -> list[Path]:
    return sorted(TESTS_DIR.rglob("test_*.py"))


# ---------------------------------------------------------------------------
# Suporte assincrono
# ---------------------------------------------------------------------------


def test_existe_teste_assincrono_na_suite() -> None:
    """Ancora dos demais: se um dia nao houver mais teste `async def`, este
    teste falha e avisa que a exigencia abaixo virou obsoleta -- em vez de
    deixar uma dependencia declarada para sempre sem ninguem lembrar por que.
    """
    com_async = [
        caminho.relative_to(REPO_ROOT).as_posix()
        for caminho in _arquivos_de_teste()
        if re.search(r"^\s*async def test_", caminho.read_text(encoding="utf-8"), re.M)
    ]
    assert com_async, (
        "nenhum teste `async def` restou na suite; se isso for intencional, "
        "remova `pytest-asyncio` de requirements-dev.txt e apague este bloco"
    )


def test_pytest_asyncio_esta_declarado_no_manifesto_de_desenvolvimento() -> None:
    """A capacidade exigida pelos testes `async def` tem de estar no manifesto.

    Este e o teste que teria evitado o episodio inteiro: `pytest-asyncio`
    estava instalado em `C:\\Program Files\\Python311` e ausente da `.venv`,
    e nenhum arquivo do repositorio dizia que ele era necessario.
    """
    linha = _requirement_named("pytest-asyncio", _declared_dev_requirements())
    assert linha is not None, (
        "a suite tem testes `async def`, mas `pytest-asyncio` nao esta "
        "declarado em requirements-dev.txt; sem a declaracao, um ambiente "
        "montado a partir do repositorio falha em "
        '"async def functions are not natively supported"'
    )


def test_pytest_asyncio_esta_realmente_carregado(pytestconfig: pytest.Config) -> None:
    """Declarar nao basta: o ambiente em uso precisa de fato ter o plugin.

    Sem isto, o teste acima passaria num ambiente onde os `async def`
    continuam falhando -- declaracao verde sobre execucao vermelha.
    """
    assert pytestconfig.pluginmanager.hasplugin("asyncio"), (
        "pytest-asyncio esta declarado mas nao esta carregado neste "
        "ambiente; rode `pip install -r requirements-dev.txt`"
    )


def test_marcador_asyncio_e_explicito_e_nao_implicito() -> None:
    """O modo STRICT (padrao) e uma escolha, e ela depende de todo teste
    assincrono trazer `@pytest.mark.asyncio`. Se alguem escrever um `async def
    test_` sem o marcador, ele sera SILENCIOSAMENTE ignorado pelo pytest-asyncio
    em modo strict -- teste que nunca roda e nunca reclama. Este teste torna
    esse caso visivel sem precisar ligar `asyncio_mode = auto`, que
    transformaria todo assincrono futuro em execucao implicita.
    """
    sem_marcador: list[str] = []
    for caminho in _arquivos_de_teste():
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        for i, linha in enumerate(linhas):
            if not re.match(r"^\s*async def test_", linha):
                continue
            # Decoradores ficam acima da assinatura; ha decorador empilhado e
            # assinatura quebrada em varias linhas, entao a busca sobe ate a
            # primeira linha que nao e decorador nem continuacao.
            anteriores = [ln.strip() for ln in linhas[max(0, i - 8):i]]
            if not any(ln.startswith("@pytest.mark.asyncio") for ln in anteriores):
                sem_marcador.append(
                    "%s:%d" % (caminho.relative_to(REPO_ROOT).as_posix(), i + 1)
                )
    assert not sem_marcador, (
        "teste `async def` sem `@pytest.mark.asyncio` em modo strict e "
        "coletado e nunca executado: %s" % sem_marcador
    )


# ---------------------------------------------------------------------------
# Teto de versao do SDK MCP
# ---------------------------------------------------------------------------


def test_servidor_mcp_usa_a_api_fastmcp_da_serie_1() -> None:
    """Ancora do teto `<2`: o teto so faz sentido enquanto o codigo importar
    o modulo que a serie 2 removeu. Se a migracao acontecer, este teste falha
    primeiro e manda levantar o teto -- em vez de deixar o repositorio preso
    numa versao antiga por inercia.
    """
    fonte = MCP_SERVER.read_text(encoding="utf-8")
    assert "from mcp.server.fastmcp import FastMCP" in fonte, (
        "mcp_server.py nao usa mais `mcp.server.fastmcp`; reveja o teto "
        "`mcp<2` em pyproject.toml e requirements-dev.txt"
    )


@pytest.mark.parametrize(
    "origem",
    ["pyproject.toml", "requirements-dev.txt"],
)
def test_mcp_tem_teto_abaixo_da_serie_2(origem: str) -> None:
    """`mcp>=1.0` resolvia para 2.0.0, que removeu `mcp.server.fastmcp`.

    Medido, nao suposto: com 2.0.0 instalado, o subprocesso do servidor morre
    em ModuleNotFoundError e os sete testes E2E falham por dependencia. O teto
    tem de estar nos DOIS manifestos, porque cada um monta um ambiente
    diferente sozinho.
    """
    declaradas = (
        _declared_runtime_dependencies()
        if origem == "pyproject.toml"
        else _declared_dev_requirements()
    )
    linha = _requirement_named("mcp", declaradas)
    assert linha is not None, "`mcp` nao esta declarado em %s" % origem
    assert "<2" in linha.replace(" ", ""), (
        "%s declara `%s`, sem teto abaixo da serie 2; a serie 2 removeu "
        "`mcp.server.fastmcp`, que mcp_server.py importa" % (origem, linha)
    )


def test_mcp_instalado_respeita_o_teto_declarado() -> None:
    """Igual ao par acima: declaracao verde nao pode conviver com ambiente
    vermelho. Verifica a versao REAL em uso, nao a restricao no arquivo."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        instalada = version("mcp")
    except PackageNotFoundError:  # pragma: no cover - ambiente sem o pacote
        pytest.fail(
            "`mcp` esta declarado nos manifestos mas nao esta instalado; "
            "rode `pip install -r requirements-dev.txt`"
        )
    maior = int(instalada.split(".")[0])
    assert maior < 2, (
        "mcp %s instalado viola o teto `<2` dos manifestos; "
        "`mcp.server.fastmcp` nao existe nessa serie" % instalada
    )


def test_interpretador_de_teste_atende_o_requires_python() -> None:
    """A `.venv` ja rodou a suite sem `mcp` e sem `pytest-asyncio` instalados,
    apesar de `mastertool-bridge` estar instalado nela em modo editavel. O
    minimo que se verifica aqui e que o interpretador em uso e um que os
    manifestos admitem."""
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    exigido = dados["project"]["requires-python"]
    minimo = tuple(int(p) for p in re.search(r"(\d+)\.(\d+)", exigido).groups())
    assert sys.version_info[:2] >= minimo, (
        "interpretador %s.%s e anterior ao `requires-python = %s`"
        % (sys.version_info[0], sys.version_info[1], exigido)
    )
