"""Teste end-to-end do servidor MCP (`mastertool_bridge.mcp_server`) usando o
CLIENTE REAL do SDK `mcp` (nao chamadas diretas em processo).

Diferenca deliberada em relacao a `tests/test_mcp_server.py`: aquele arquivo
chama as funcoes `_*_impl`/`*_impl` diretamente, em processo, e portanto
nunca sobe o transporte MCP de verdade -- bugs de serializacao, de
registro via `@mcp.tool()`, de assinatura de parametro ou de transporte
passariam despercebidos. Este arquivo cobre exatamente essa lacuna: sobe o
servidor real como SUBPROCESSO (`python -m mastertool_bridge.mcp_server`),
conecta como cliente MCP real via stdio, e verifica as respostas que voltam
ATRAVES DO PROTOCOLO (JSON-RPC sobre stdio, com handshake de capacidades).

API real confirmada por inspecao direta do pacote `mcp` instalado, serie 1.x
(ver `mcp/__init__.py`, `mcp/client/stdio/__init__.py`,
`mcp/client/session.py` no site-packages):

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client, get_default_environment

    stdio_client(StdioServerParameters(command=..., args=..., cwd=..., env=...))
        -> async context manager -> (read_stream, write_stream)
    ClientSession(read_stream, write_stream, read_timeout_seconds=...)
        -> async context manager; precisa de `await session.initialize()`
           antes de qualquer outra chamada (handshake MCP)
    session.list_tools() -> mcp.types.ListToolsResult (.tools: list[Tool])
    session.call_tool(name, arguments) -> mcp.types.CallToolResult, com:
        - .isError: bool (True apenas se a ferramenta MCP levantar excecao
          nao tratada -- este servidor NUNCA deixa isso acontecer por design,
          ver `_index_error`/`_unexpected_error`/`_validation_error` em
          mcp_server.py; erros de dominio voltam como dict estruturado
          dentro do payload normal, com isError=False)
        - .structuredContent: dict[str, Any] | None -- o FastMCP serializa
          automaticamente o retorno `dict[str, Any]` das tools aqui; e
          o dict Python de volta, JA deserializado (sem precisar fazer
          json.loads em cima de `.content`)
        - .content: list[ContentBlock] -- normalmente um unico
          `TextContent` com o mesmo payload serializado como JSON string
          (redundante com `structuredContent` para tools que declaram
          retorno dict; usado aqui apenas como fallback/checagem extra)

EXECUCAO: AMBIENTE PROVISIONADO PELOS MANIFESTOS DO REPOSITORIO.

Rode com o interpretador montado a partir de `requirements-dev.txt`
(`pip install -r requirements-dev.txt`). **O Python base da maquina nao e
fonte valida de dependencia**: pacote presente nele por instalacao manual
nao esta declarado em lugar nenhum, some no proximo clone e faz a suite
dizer coisas diferentes em maquinas diferentes.

Uma versao anterior deste texto afirmava que "nenhuma dependencia nova foi
adicionada" porque `pytest-asyncio` e `anyio` "ja estavam disponiveis" no
Python base. A afirmacao era falsa no sentido que importa: disponivel num
interpretador nao e declarado no repositorio. O resultado foi que estes sete
testes falhavam em "async def functions are not natively supported" sempre
que a suite rodava pela `.venv` do projeto, e o repositorio perdeu a
capacidade de distinguir regressao nova de ambiente incompleto. Corrigido em
`c5a1f2c`; a guarda permanente esta em `tests/unit/test_test_infrastructure.py`.

Dependencias que ESTES testes exigem, todas declaradas:

    pytest-asyncio>=1.0,<2   os testes abaixo sao `async def`
    mcp>=1.0,<2              cliente real e servidor sob teste

O teto `<2` em `mcp` e TEMPORARIO e esta amarrado ao codigo: a serie 2
removeu `mcp.server.fastmcp`, que `mcp_server.py` importa. Quando o servidor
migrar para a API 2.x, o teto deve ser LEVANTADO nos dois manifestos --
`tests/unit/test_test_infrastructure.py` falha para lembrar disso, em vez de
deixar o repositorio preso na serie 1 por inercia.

`pyproject.toml` nao configura `asyncio_mode`, entao o plugin roda em modo
STRICT por padrao -- por isso cada teste assincrono abaixo usa
`@pytest.mark.asyncio` explicitamente. Isso e escolha, nao acaso: em modo
strict um `async def test_` SEM o marcador e coletado e nunca executado, e
ligar `asyncio_mode = auto` esconderia esse caso em vez de resolve-lo. Ha
teste de infraestrutura exigindo o marcador em todo teste assincrono da
suite.

O modulo do servidor (`mastertool_bridge.mcp_server`) tem
`if __name__ == "__main__": main()`, o que confirma que
`python -m mastertool_bridge.mcp_server` e uma forma valida de subi-lo.
O subprocesso e lancado com `PYTHONPATH=<repo>/src` explicito no `env` de
`StdioServerParameters` (mesmo mecanismo do `pythonpath = ["src"]` do
pytest, mas reproduzido manualmente): o subprocesso e um interpretador novo
e independente, sem os `sys.path` do processo de teste, e o explicito vale
tanto no ambiente em que `mastertool_bridge` esta instalado em modo editavel
quanto naquele em que ele nao esta.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from mastertool_bridge.indexer.export_loader import build_static_index

pytest_plugins: list[str] = []

# ---------------------------------------------------------------------------
# Constantes do cenario (numeros validados por commits/testes anteriores;
# reconfirmados nesta tarefa rodando `build_static_index` diretamente sobre
# o export real antes de escrever este arquivo)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
SAMPLE_EXPORT_DIR = REPO_ROOT / "workspace" / "exports" / "2026-07-23_17-29-54_13_validate_text_exporter"

EXPECTED_TOOL_NAMES = {
    "open_project_index",
    "get_index_metadata",
    "find_symbol",
    "find_reads",
    "find_writes",
    "find_calls",
    "find_callers",
    "ask_project",
}

EXPECTED_SYMBOL_COUNT = 60
EXPECTED_TYPE_COUNT = 8
EXPECTED_REFERENCE_COUNT = 534
EXPECTED_CALL_COUNT = 12

# Timeout generoso porem finito: nenhuma chamada deve travar o cliente
# indefinidamente (requisito explicito da tarefa).
CALL_TIMEOUT = timedelta(seconds=20)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_index_dir(tmp_path: Path) -> Path:
    """Constroi um indice estatico REAL (nao sintetico) a partir do export
    fixture `workspace/exports/2026-07-23_17-29-54_13_validate_text_exporter/`,
    escrito em um `tmp_path` isolado por teste (limpo automaticamente pelo
    pytest). Mesma funcao (`build_static_index`) usada pelos testes de
    indexer existentes (`tests/indexer/test_export_loader.py`)."""
    # O export real vive em `workspace/`, que e gitignored: ele e produto de uma
    # execucao dentro do MasterTool, nao artefato versionado. Num clone limpo ele
    # nao existe, e a ausencia nao e falha -- e falta de dado de entrada. Falhar
    # aqui reportaria como defeito do servidor MCP algo que e so ambiente sem
    # captura. Quem tem o export roda o E2E completo; quem nao tem, pula sabendo
    # exatamente o que gerar.
    if not SAMPLE_EXPORT_DIR.exists():
        pytest.skip(
            f"export real ausente: {SAMPLE_EXPORT_DIR}\n"
            f"Gere um com `mastertool-bridge supervised-snapshot` (ou "
            f"`scripts/host/run_supervised_snapshot.ps1 -Execute`) e copie o "
            f"diretorio de saida para `workspace/exports/` com este nome, ou "
            f"ajuste SAMPLE_EXPORT_DIR para apontar para a sua captura."
        )
    output_dir = tmp_path / "index_out"
    build_static_index(SAMPLE_EXPORT_DIR, output_dir)
    return output_dir


@asynccontextmanager
async def _mcp_client_session() -> AsyncIterator[Any]:
    """Sobe `python -m mastertool_bridge.mcp_server` como subprocesso real,
    conecta um `ClientSession` MCP real via stdio, faz o handshake
    (`initialize()`) e devolve a sessao pronta para uso. Fecha a sessao e
    garante o encerramento do subprocesso (via `stdio_client`, que
    implementa a sequencia de shutdown do spec MCP: fecha stdin -> aguarda
    saida -> SIGTERM/SIGKILL se necessario) ao sair do `with`."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import get_default_environment, stdio_client

    env = get_default_environment()
    env["PYTHONPATH"] = str(SRC_DIR)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mastertool_bridge.mcp_server"],
        cwd=str(REPO_ROOT),
        env=env,
    )

    import anyio

    with anyio.fail_after(CALL_TIMEOUT.total_seconds()):
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream, write_stream, read_timeout_seconds=CALL_TIMEOUT
            ) as session:
                await session.initialize()
                yield session


def _structured(result: Any) -> dict[str, Any]:
    """Extrai o payload de dominio de um `CallToolResult`. Prioriza
    `structuredContent` (dict Python ja deserializado pelo FastMCP); cai
    para `json.loads` do primeiro `TextContent` como checagem redundante
    caso `structuredContent` esteja ausente por algum motivo."""
    assert result.isError is False, f"tool retornou isError=True: {result}"
    if result.structuredContent is not None:
        return result.structuredContent
    import json

    assert result.content, "CallToolResult sem content nem structuredContent"
    first = result.content[0]
    assert first.type == "text"
    return json.loads(first.text)


# ---------------------------------------------------------------------------
# 1. Handshake / conexao
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handshake_connects_successfully() -> None:
    async with _mcp_client_session() as session:
        # Handshake ja aconteceu em _mcp_client_session (initialize()); uma
        # chamada trivial subsequente confirma que a sessao esta realmente
        # utilizavel (nao apenas que o subprocesso subiu).
        tools = await session.list_tools()
        assert len(tools.tools) > 0


# ---------------------------------------------------------------------------
# 2. list_tools() -- exatamente as 8 tools esperadas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_returns_exactly_the_eight_expected_tools() -> None:
    async with _mcp_client_session() as session:
        result = await session.list_tools()

    names = {tool.name for tool in result.tools}

    assert names == EXPECTED_TOOL_NAMES
    assert len(result.tools) == 8


# ---------------------------------------------------------------------------
# 3. Cenarios de sucesso via protocolo real, com indice real
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_project_index_returns_correct_metadata_through_protocol(
    real_index_dir: Path,
) -> None:
    async with _mcp_client_session() as session:
        result = await session.call_tool(
            "open_project_index", {"index_dir": str(real_index_dir)}
        )

    payload = _structured(result)

    assert payload["symbol_count"] == EXPECTED_SYMBOL_COUNT
    assert payload["type_count"] == EXPECTED_TYPE_COUNT
    assert payload["reference_count"] == EXPECTED_REFERENCE_COUNT
    assert payload["call_count"] == EXPECTED_CALL_COUNT
    assert "error" not in payload


@pytest.mark.asyncio
async def test_find_symbol_triptip_is_ambiguous_through_protocol(
    real_index_dir: Path,
) -> None:
    async with _mcp_client_session() as session:
        result = await session.call_tool(
            "find_symbol", {"index_dir": str(real_index_dir), "name": "TripTip"}
        )

    payload = _structured(result)

    assert payload["status"] == "ambiguous"
    assert payload["count"] == 2


@pytest.mark.asyncio
async def test_find_calls_mainprg_is_resolved_through_protocol(
    real_index_dir: Path,
) -> None:
    async with _mcp_client_session() as session:
        result = await session.call_tool(
            "find_calls", {"index_dir": str(real_index_dir), "name": "MainPrg"}
        )

    payload = _structured(result)

    assert payload["status"] == "resolved"
    assert payload["count"] == 3


@pytest.mark.asyncio
async def test_ask_project_portuguese_question_is_answered_through_protocol(
    real_index_dir: Path,
) -> None:
    question = "onde VarMotores.MT01.RetornoDisjuntor é escrito?"

    async with _mcp_client_session() as session:
        result = await session.call_tool(
            "ask_project", {"index_dir": str(real_index_dir), "question": question}
        )

    payload = _structured(result)

    assert payload["status"] == "answered"
    assert payload["limitations"] == []


# ---------------------------------------------------------------------------
# 4. index_dir invalido -- erro estruturado atraves do protocolo, sem
#    excecao crua vazando e sem travar o cliente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_symbol_invalid_index_dir_returns_structured_error_not_raw_exception(
    tmp_path: Path,
) -> None:
    nonexistent = tmp_path / "does_not_exist_at_all"

    async with _mcp_client_session() as session:
        result = await session.call_tool(
            "find_symbol", {"index_dir": str(nonexistent), "name": "TripTip"}
        )

    # A tool MCP nunca deixa a excecao de dominio (ProjectIndexError)
    # atravessar crua o transporte -- ela e capturada em mcp_server.py e
    # devolvida como payload estruturado normal (isError continua False).
    assert result.isError is False
    payload = _structured(result)
    assert payload["error"] == "invalid_index"
    assert "message" in payload
    assert isinstance(payload["message"], str)
    assert payload["message"]
