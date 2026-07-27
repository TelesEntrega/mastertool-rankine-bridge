"""Testa a política de serialização ESTRITA de common/capabilities.py.

Motivo (2026-07-23, 1a correção): uma execução real usou repr()/str() para
"representação segura" de um objeto retornado — em IronPython isso
tipicamente invoca ToString() no objeto .NET, uma chamada de método fora do
escopo aprovado. Estes testes garantem que build_representation() NUNCA
chama repr()/str()/__str__/__repr__ em um objeto CLR desconhecido — só
serializa primitivos nativos ou tipos confirmados seguros (via dotnet_type
já obtido).

Motivo (2026-07-23, 2a correção): uma execução real (`get_name(False)`)
retornou uma string, mas o campo de conveniência `value` do script ficou
`null` porque a checagem dependia de `dotnet_type` confirmado como
`System.String` — que falha para primitivos nativos do IronPython (não
respondem a `GetType()` de forma confiável neste host). Corrigido:
`build_representation()` reconhece `str`/`unicode` nativos via
`isinstance(value, _STRING_TYPES)` (onde `_STRING_TYPES` resolve para
`(basestring,)` no Python 2/IronPython e `(str,)` no Python 3), SEM
depender de `GetType()`, e expõe isso via `value_available`/
`serialization_mode` além dos campos originais.
"""

import sys
from pathlib import Path

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import capabilities  # noqa: E402


class StringifyingBomb:
    """Objeto CLR desconhecido simulado: __repr__/__str__ levantam se
    chamados. Se build_representation() acidentalmente invocar repr()/str(),
    o teste falha com a exceção, provando a violação de política."""

    def __repr__(self):
        raise AssertionError("repr() foi chamado em objeto CLR desconhecido — violação de política")

    def __str__(self):
        raise AssertionError("str() foi chamado em objeto CLR desconhecido — violação de política")


def test_none_is_serialized_directly():
    rep = capabilities.build_representation(None, {"name": "NoneType"}, {"full_name": None})
    assert rep["mode"] == "value"
    assert rep["value"] is None
    assert rep["instance_stringification_performed"] is False
    assert rep["value_available"] is True
    assert rep["serialization_mode"] == "none"


def test_bool_is_serialized_directly_not_as_int():
    rep = capabilities.build_representation(True, {"name": "bool"}, {"full_name": "System.Boolean"})
    assert rep["mode"] == "value"
    assert rep["value"] is True
    assert rep["instance_stringification_performed"] is False
    assert rep["value_available"] is True
    assert rep["serialization_mode"] == "native_bool"


def test_int_is_serialized_directly():
    rep = capabilities.build_representation(42, {"name": "int"}, {"full_name": "System.Int32"})
    assert rep["mode"] == "value"
    assert rep["value"] == 42
    assert rep["instance_stringification_performed"] is False
    assert rep["value_available"] is True
    assert rep["serialization_mode"] == "native_int"


def test_float_is_serialized_directly():
    rep = capabilities.build_representation(3.14, {"name": "float"}, {"full_name": "System.Double"})
    assert rep["mode"] == "value"
    assert rep["value"] == 3.14
    assert rep["value_available"] is True
    assert rep["serialization_mode"] == "native_float"


def test_python_string_is_serialized_directly():
    rep = capabilities.build_representation("hello", {"name": "str"}, {"full_name": "System.String"})
    assert rep["mode"] == "value"
    assert rep["value"] == "hello"
    assert rep["instance_stringification_performed"] is False
    assert rep["value_available"] is True
    assert rep["serialization_mode"] == "native_string"


def test_native_string_recognized_without_dotnet_type_confirmed():
    # O CASO REAL que motivou a correcao: dotnet_type indisponivel (GetType()
    # falhou para o primitivo nativo), mas a string ja e um valor Python
    # nativo — deve ser reconhecida MESMO ASSIM, sem depender de GetType().
    rep = capabilities.build_representation(
        "Project Settings", {"module": "__builtin__", "name": "str"},
        {"full_name": None, "available": False})
    assert rep["value_available"] is True
    assert rep["value"] == "Project Settings"
    assert rep["serialization_mode"] == "native_string"
    assert rep["instance_stringification_performed"] is False


def test_unicode_string_recognized_when_available():
    # 'unicode' so existe no Python 2 / IronPython 2.7. Sob CPython 3 (onde
    # os testes rodam), o proprio nome nao existe — o que importa validar
    # aqui e que _STRING_TYPES cobre basestring quando disponivel (Python 2)
    # e cai para (str,) sem quebrar em Python 3 (ja coberto pelos testes de
    # string acima). Este teste documenta a intencao e verifica o fallback.
    try:
        text = unicode("valor unicode")  # noqa: F821
    except NameError:
        import pytest
        pytest.skip("'unicode' nao existe nesta versao do Python (CPython 3); "
                    "comportamento real so testavel em IronPython 2.7.")
    rep = capabilities.build_representation(
        text, {"name": "unicode"}, {"full_name": None, "available": False})
    assert rep["value_available"] is True
    assert rep["value"] == "valor unicode"
    assert rep["serialization_mode"] == "native_string"


def test_confirmed_system_guid_type_allows_stringification():
    # Guid.ToString() e formato padronizado e documentado da BCL (value type
    # selado) — permitido APOS confirmar o tipo via GetType(), nao por
    # suposicao. Usamos uma string python para simular o valor (o teste
    # foca na POLITICA de decisao, nao em ter um Guid .NET real disponivel
    # fora do IronPython).
    class FakeGuidLike:
        def __str__(self):
            return "00000000-0000-0000-0000-000000000001"

    value = FakeGuidLike()
    rep = capabilities.build_representation(
        value, {"name": "Guid"}, {"full_name": "System.Guid", "available": True})
    assert rep["mode"] == "value"
    assert rep["value"] == "00000000-0000-0000-0000-000000000001"
    assert rep["instance_stringification_performed"] is True
    assert rep["value_available"] is True
    assert rep["serialization_mode"] == "confirmed_dotnet_type"


def test_confirmed_system_string_type_allows_stringification():
    # Fixture para o ramo "dotnet_type == System.String, mas NAO e um
    # str/unicode nativo" — na pratica raro (IronPython converte
    # System.String em str/unicode automaticamente, entao o ramo
    # native_string quase sempre pega primeiro), mas o fallback existe como
    # defesa e precisa continuar seguro (so str() apos confirmar o tipo).
    class FakeSystemStringLike:
        def __str__(self):
            return "confirmed-string-value"

    value = FakeSystemStringLike()
    rep = capabilities.build_representation(
        value, {"name": "FakeSystemStringLike"}, {"full_name": "System.String", "available": True})
    assert rep["mode"] == "value"
    assert rep["value"] == "confirmed-string-value"
    assert rep["value_available"] is True
    assert rep["serialization_mode"] == "confirmed_dotnet_type"


def test_unknown_clr_object_never_calls_repr_or_str():
    """O teste CRITICO: um objeto cujo __repr__/__str__ levantam excecao NAO
    deve fazer build_representation() falhar — prova que nem repr() nem
    str() sao chamados quando o tipo nao esta em KNOWN_SAFE_DOTNET_TYPES."""
    bomb = StringifyingBomb()
    rep = capabilities.build_representation(
        bomb, {"name": "StringifyingBomb"},
        {"full_name": "_3S.CoDeSys.ScriptDriverProjects.ScriptObject", "available": True})
    assert rep["mode"] == "type_only"
    assert rep["value"] == "<_3S.CoDeSys.ScriptDriverProjects.ScriptObject>"
    assert rep["instance_stringification_performed"] is False
    assert rep["value_available"] is False
    assert rep["serialization_mode"] == "type_only"


def test_unknown_type_without_dotnet_full_name_falls_back_to_python_type_name():
    bomb = StringifyingBomb()
    rep = capabilities.build_representation(
        bomb, {"name": "ExtendedObject[IScriptObject]"}, {"full_name": None, "available": False})
    assert rep["mode"] == "type_only"
    assert rep["value"] == "<ExtendedObject[IScriptObject]>"
    assert rep["value_available"] is False


def test_strict_object_repr_handles_missing_type_name():
    assert capabilities.strict_object_repr(None) == "<unknown-object>"
    assert capabilities.strict_object_repr("") == "<unknown-object>"
    assert capabilities.strict_object_repr("Foo.Bar") == "<Foo.Bar>"


def test_dotnet_type_info_never_raises_on_missing_gettype():
    class NoGetType:
        pass

    info = capabilities.dotnet_type_info(NoGetType())
    assert info == {"full_name": None, "available": False}


def test_python_type_info_basic():
    info = capabilities.python_type_info(42)
    assert info["name"] == "int"
