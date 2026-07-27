"""Servidor MCP (Model Context Protocol) fino sobre `mastertool_bridge.api`.

Princípio central (dado pelo usuário, EXATO): "tool MCP -> valida argumentos
-> chama ProjectIndex -> devolve to_dict(). Não coloque lógica semântica
dentro do MCP." Este módulo NUNCA reimplementa lógica de domínio -- toda
decisão (resolução de símbolo, ambiguidade, formatação de evidência,
intenção de pergunta em linguagem natural) já vive 100% em
`mastertool_bridge.api.ProjectIndex` (e, por baixo dela,
`mastertool_bridge.indexer.*`, nunca importado diretamente aqui).

Padrão de implementação: cada tool tem uma função `_*_impl` comum, pura e
diretamente testável (sem subir o transporte MCP), e o tool MCP registrado
via `@mcp.tool()` é um wrapper fino que só chama essa função.

Estado: cada chamada recebe `index_dir: str` explícito (sem "índice atual"
implícito). Um cache interno (`dict[str, ProjectIndex]`, chave = caminho
absoluto resolvido) evita reabrir/reler o índice do disco a cada chamada --
lazy: qualquer tool abre e cacheia o índice na hora, se ainda não estiver
cacheado.

Dependência nova: pacote `mcp` (SDK oficial do Model Context Protocol,
API de alto nível `FastMCP`). Isto é uma EXCEÇÃO EXPLÍCITA E DELIBERADA à
disciplina de "zero dependência nova" seguida em todo o resto do indexer --
implementar o protocolo MCP à mão (JSON-RPC sobre stdio, handshake de
capacidades, etc.) seria descabido quando o SDK oficial já resolve isso.
API confirmada por inspeção direta do pacote instalado (`mcp==1.28.1`):
`from mcp.server.fastmcp import FastMCP`; tools sync registrados com
`@mcp.tool()` funcionam sem exigir `async def`; transporte padrão de
`FastMCP.run()` é `"stdio"`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mastertool_bridge.api import ProjectIndex
from mastertool_bridge.exceptions import ProjectIndexError

# ---------------------------------------------------------------------------
# Cache de índices já abertos (chave = index_dir normalizado)
# ---------------------------------------------------------------------------

_INDEX_CACHE: dict[str, ProjectIndex] = {}


def _normalize_index_dir(index_dir: str) -> str:
    return str(Path(index_dir).resolve())


def _get_or_open_index(index_dir: str) -> ProjectIndex:
    """Abre e cacheia `index_dir` se ainda não estiver no cache; devolve a
    instância cacheada caso contrário. Única função que fala com
    `ProjectIndex.open()` -- todo o resto do módulo passa por aqui."""
    key = _normalize_index_dir(index_dir)
    cached = _INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    index = ProjectIndex.open(key)
    _INDEX_CACHE[key] = index
    return index


# ---------------------------------------------------------------------------
# Validação de argumentos (400-like) -- nunca deixa TypeError/AttributeError
# cru atravessar para a lógica interna.
# ---------------------------------------------------------------------------


def _validation_error(message: str) -> dict[str, Any]:
    return {"error": "invalid_argument", "message": message}


def _index_error(exc: Exception) -> dict[str, Any]:
    return {"error": "invalid_index", "message": str(exc)}


def _unexpected_error(exc: Exception) -> dict[str, Any]:
    return {"error": "unexpected_error", "message": str(exc)}


def _require_nonempty_str(value: Any, field_name: str) -> str | None:
    """Devolve uma mensagem de erro (str) se `value` não for uma string
    não-vazia (após strip); devolve None se válido."""
    if not isinstance(value, str):
        return f"'{field_name}' deve ser uma string, recebido {type(value).__name__}."
    if not value.strip():
        return f"'{field_name}' não pode ser vazio."
    return None


# ---------------------------------------------------------------------------
# Implementações puras e testáveis (`_*_impl`) -- chamadas diretamente pelos
# testes, SEM subir o transporte MCP.
# ---------------------------------------------------------------------------


def _metadata_impl(index_dir: str) -> dict[str, Any]:
    """Implementação compartilhada por `open_project_index` e
    `get_index_metadata` (mesmo comportamento: abre/cacheia + devolve
    metadata)."""
    error = _require_nonempty_str(index_dir, "index_dir")
    if error is not None:
        return _validation_error(error)
    try:
        index = _get_or_open_index(index_dir)
    except ProjectIndexError as exc:
        return _index_error(exc)
    except Exception as exc:  # noqa: BLE001 - rede de seguranca deliberada
        return _unexpected_error(exc)
    return dict(index.metadata)


def open_project_index_impl(index_dir: str) -> dict[str, Any]:
    return _metadata_impl(index_dir)


def get_index_metadata_impl(index_dir: str) -> dict[str, Any]:
    return _metadata_impl(index_dir)


def _run_query(index_dir: str, name: str, method_name: str) -> dict[str, Any]:
    """Helper comum às 5 consultas `find_*`: valida argumentos, abre/cacheia
    o índice, chama `getattr(index, method_name)(name)` e devolve
    `.to_dict()`."""
    error = _require_nonempty_str(index_dir, "index_dir")
    if error is not None:
        return _validation_error(error)
    error = _require_nonempty_str(name, "name")
    if error is not None:
        return _validation_error(error)
    try:
        index = _get_or_open_index(index_dir)
        result = getattr(index, method_name)(name)
    except ProjectIndexError as exc:
        return _index_error(exc)
    except Exception as exc:  # noqa: BLE001 - rede de seguranca deliberada
        return _unexpected_error(exc)
    return result.to_dict()


def find_symbol_impl(index_dir: str, name: str) -> dict[str, Any]:
    return _run_query(index_dir, name, "find_symbol")


def find_reads_impl(index_dir: str, name: str) -> dict[str, Any]:
    return _run_query(index_dir, name, "find_reads")


def find_writes_impl(index_dir: str, name: str) -> dict[str, Any]:
    return _run_query(index_dir, name, "find_writes")


def find_calls_impl(index_dir: str, name: str) -> dict[str, Any]:
    return _run_query(index_dir, name, "find_calls")


def find_callers_impl(index_dir: str, name: str) -> dict[str, Any]:
    return _run_query(index_dir, name, "find_callers")


def ask_project_impl(index_dir: str, question: str) -> dict[str, Any]:
    error = _require_nonempty_str(index_dir, "index_dir")
    if error is not None:
        return _validation_error(error)
    error = _require_nonempty_str(question, "question")
    if error is not None:
        return _validation_error(error)
    try:
        index = _get_or_open_index(index_dir)
        answer = index.ask(question)
    except ProjectIndexError as exc:
        return _index_error(exc)
    except Exception as exc:  # noqa: BLE001 - rede de seguranca deliberada
        return _unexpected_error(exc)
    return answer.to_dict()


# ---------------------------------------------------------------------------
# Servidor MCP -- wrappers finos em cima das implementações acima.
# ---------------------------------------------------------------------------


def _build_server() -> Any:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("mastertool-bridge")

    @mcp.tool()
    def open_project_index(index_dir: str) -> dict[str, Any]:
        """Abre (ou reutiliza do cache) o índice em `index_dir` e devolve
        seus metadados (symbol_count, type_count, reference_count,
        call_count, run_id)."""
        return open_project_index_impl(index_dir)

    @mcp.tool()
    def get_index_metadata(index_dir: str) -> dict[str, Any]:
        """Devolve os metadados do índice em `index_dir` (abre/cacheia se
        necessário)."""
        return get_index_metadata_impl(index_dir)

    @mcp.tool()
    def find_symbol(index_dir: str, name: str) -> dict[str, Any]:
        """Localiza a declaração de um símbolo (POU ou variável) pelo
        nome."""
        return find_symbol_impl(index_dir, name)

    @mcp.tool()
    def find_reads(index_dir: str, name: str) -> dict[str, Any]:
        """Localiza leituras de uma variável."""
        return find_reads_impl(index_dir, name)

    @mcp.tool()
    def find_writes(index_dir: str, name: str) -> dict[str, Any]:
        """Localiza escritas de uma variável."""
        return find_writes_impl(index_dir, name)

    @mcp.tool()
    def find_calls(index_dir: str, name: str) -> dict[str, Any]:
        """Localiza chamadas feitas de dentro de um POU."""
        return find_calls_impl(index_dir, name)

    @mcp.tool()
    def find_callers(index_dir: str, name: str) -> dict[str, Any]:
        """Localiza quem chama um POU."""
        return find_callers_impl(index_dir, name)

    @mcp.tool()
    def ask_project(index_dir: str, question: str) -> dict[str, Any]:
        """Responde uma pergunta em linguagem natural sobre o projeto,
        fundamentada nas evidências do índice."""
        return ask_project_impl(index_dir, question)

    return mcp


def main() -> None:
    """Ponto de entrada (`python -m mastertool_bridge.mcp_server` e o
    console script `mastertool-bridge-mcp`). Roda o servidor MCP sobre
    stdio -- o transporte padrão para uso com Claude Desktop/Claude Code."""
    server = _build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
