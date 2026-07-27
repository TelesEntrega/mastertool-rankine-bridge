"""Testa capabilities.probe_method_call() e capabilities.probe_indexer_access()
— extensões do modelo tri-state (confirmed/unsupported/unknown) para
chamadas de método com argumentos e acesso por índice, usadas pelo probe de
identidade do primeiro filho (06_first_child_identity.py).
"""

import sys
from pathlib import Path

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import capabilities  # noqa: E402


class NodeStub:
    def __dir__(self):
        return []

    def get_name(self, resolve_localized):
        if resolve_localized:
            raise AssertionError("get_name(True) nunca deveria ser chamado neste probe")
        return "MinhaPOU"


class ListStub:
    def __init__(self, items):
        self._items = items

    def __dir__(self):
        return []

    def __getitem__(self, index):
        return self._items[index]


def test_method_call_confirmed_with_correct_args():
    node = NodeStub()
    record = capabilities.probe_method_call(
        node, "first_child", "get_name", (False,),
        capabilities.EVIDENCE_STATIC_METADATA, capture_value=True)
    assert record["state"] == capabilities.STATE_CONFIRMED
    assert record["call_args"] == [False]
    assert record["raw_value"] == "MinhaPOU"
    assert record["access_method"] == "method_call"


def test_method_call_never_retries_with_alternate_args():
    # get_name(True) levantaria AssertionError no stub — mas nos NUNCA
    # chamamos com True, entao o teste so passa se get_name(False) foi a
    # UNICA chamada feita.
    node = NodeStub()
    capabilities.probe_method_call(
        node, "first_child", "get_name", (False,), capabilities.EVIDENCE_STATIC_METADATA)
    # se chegou aqui sem AssertionError, confirma que so (False,) foi usado


def test_method_call_missing_member_is_unsupported():
    class Empty:
        def __dir__(self):
            return []

    record = capabilities.probe_method_call(
        Empty(), "first_child", "get_name", (False,), capabilities.EVIDENCE_UNVERIFIED)
    assert record["state"] == capabilities.STATE_UNSUPPORTED
    assert record["exception_type"] == "AttributeError"


def test_method_call_ambiguous_exception_is_unknown():
    class Flaky:
        def __dir__(self):
            return []

        def get_name(self, resolve_localized):
            raise RuntimeError("erro interno do proxy")

    record = capabilities.probe_method_call(
        Flaky(), "first_child", "get_name", (False,), capabilities.EVIDENCE_UNVERIFIED)
    assert record["state"] == capabilities.STATE_UNKNOWN
    assert record["exception_type"] == "RuntimeError"


def test_indexer_access_confirmed():
    stub = ListStub(["a", "b", "c"])
    record = capabilities.probe_indexer_access(
        stub, "children", 0, capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    assert record["state"] == capabilities.STATE_CONFIRMED
    assert record["index"] == 0
    assert record["raw_value"] == "a"
    assert record["access_method"] == "indexer"


def test_indexer_access_out_of_range_is_unknown_not_unsupported():
    # IndexError NAO esta em _UNSUPPORTED_EXCEPTION_NAMES (so AttributeError
    # esta) — por design, uma falha de indice fica 'unknown', nao
    # 'unsupported', ate termos evidencia real de qual excecao o ScriptEngine
    # usa para "fora de alcance".
    stub = ListStub([])
    record = capabilities.probe_indexer_access(
        stub, "children", 0, capabilities.EVIDENCE_RUNTIME_CONFIRMED)
    assert record["state"] == capabilities.STATE_UNKNOWN
    assert record["exception_type"] == "IndexError"


def test_indexer_access_missing_getitem_is_unknown_not_unsupported():
    # Objeto sem __getitem__ levanta TypeError ("not subscriptable"), NAO
    # AttributeError — pela regra estrita (so AttributeError vira
    # unsupported), isso fica 'unknown', nunca concluindo ausencia por
    # engano a partir de um tipo de excecao nao catalogado.
    class NoIndexer:
        def __dir__(self):
            return []

    record = capabilities.probe_indexer_access(
        NoIndexer(), "children", 0, capabilities.EVIDENCE_UNVERIFIED)
    assert record["state"] == capabilities.STATE_UNKNOWN
    assert record["exception_type"] == "TypeError"
