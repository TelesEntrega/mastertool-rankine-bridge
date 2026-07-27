"""Testa scripts/mastertool/common/capabilities.py contra um proxy sintetico
que reproduz o comportamento real confirmado em 2026-07-23:
`dir(projects.primary) == []` mas `getattr(projects.primary, "path")` funciona.

Este modulo IronPython vive fora de src/mastertool_bridge (nao depende do
MasterTool em si, so de dir()/getattr genericos), entao e importado aqui via
manipulacao explicita de sys.path — nao faz parte do pacote instalado.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import capabilities  # noqa: E402


class DynamicProxyStub:
    """Reproduz o proxy dinamico real: dir() vazio, getattr funciona."""

    def __init__(self, path):
        self._path = path

    def __dir__(self):
        return []

    @property
    def path(self):
        return self._path


class NoMemberStub:
    """Objeto comum: getattr de nome inexistente levanta AttributeError."""

    def __dir__(self):
        return []


class FlakyStub:
    """Objeto cujo getter lanca uma excecao AMBIGUA (nao AttributeError) —
    nao deve ser interpretado como 'membro ausente'."""

    def __dir__(self):
        return []

    @property
    def flaky(self):
        raise RuntimeError("proxy temporariamente indisponivel")


def test_dir_is_actually_empty_on_dynamic_proxy():
    proxy = DynamicProxyStub("C:\\fake\\project.project")
    assert dir(proxy) == []


def test_direct_getattr_still_works_despite_empty_dir():
    proxy = DynamicProxyStub("C:\\fake\\project.project")
    assert getattr(proxy, "path") == "C:\\fake\\project.project"


def test_diagnostic_dir_never_asserts_absence():
    proxy = DynamicProxyStub("C:\\fake\\project.project")
    members, note = capabilities.diagnostic_dir(proxy)
    assert members == []
    assert "NAO significa" in note or "nao significa" in note.lower()


def test_explicit_probe_confirms_known_member_despite_empty_dir():
    proxy = DynamicProxyStub("C:\\fake\\project.project")
    record = capabilities.probe_member(
        proxy, "project", "path", capabilities.EVIDENCE_RUNTIME_CONFIRMED)
    assert record["state"] == capabilities.STATE_CONFIRMED
    assert record["success"] is True
    assert record["value_type"] == "str"


def test_probe_object_reports_confirmed_member_and_non_authoritative_dir():
    # CAPABILITY_PROBES["project"] = ["path", "is_root", "handle",
    # "active_application"] (2026-07-23: is_root/handle promovidos via
    # probes/03_project_navigation.py; active_application via
    # probes/04_project_identity.py). O stub so tem "path" de verdade, entao
    # os outros devem sair "unsupported" (AttributeError), nao sumir.
    proxy = DynamicProxyStub("C:\\fake\\project.project")
    result = capabilities.probe_object(
        proxy, "project", capabilities.EVIDENCE_RUNTIME_CONFIRMED)
    assert result["diagnostic_dir"]["members"] == []
    assert result["diagnostic_dir"]["authoritative"] is False
    known = {m["member"]: m for m in result["known_members"]}
    assert set(known) == {"path", "is_root", "handle", "active_application"}
    assert known["path"]["state"] == capabilities.STATE_CONFIRMED
    assert known["is_root"]["state"] == capabilities.STATE_UNSUPPORTED
    assert known["handle"]["state"] == capabilities.STATE_UNSUPPORTED
    assert known["active_application"]["state"] == capabilities.STATE_UNSUPPORTED


def test_missing_member_marked_unsupported_via_attribute_error():
    record = capabilities.probe_member(
        NoMemberStub(), "project", "nonexistent_member",
        capabilities.EVIDENCE_UNVERIFIED)
    assert record["state"] == capabilities.STATE_UNSUPPORTED
    assert record["exception_type"] == "AttributeError"


def test_ambiguous_exception_marked_unknown_not_unsupported():
    record = capabilities.probe_member(
        FlakyStub(), "project", "flaky", capabilities.EVIDENCE_UNVERIFIED)
    assert record["state"] == capabilities.STATE_UNKNOWN
    assert record["exception_type"] == "RuntimeError"


def test_unregistered_object_label_probes_nothing():
    proxy = DynamicProxyStub("C:\\fake\\project.project")
    assert capabilities.probe_known_members(proxy, "unregistered_label",
                                            capabilities.EVIDENCE_UNVERIFIED) == []
