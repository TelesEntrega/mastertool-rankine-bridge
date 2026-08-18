"""`METHOD` na `project_spec` — escopo, retorno ausente e `language` fora.

Contrato `docs/87`. Medições: `docs/api` §4 (defaults de `create_method`) e §5
(`language` do membro).

As duas decisões que estes testes congelam saíram de medição, não de escolha:

* **`return_type` ausente ou `null` é MÉTODO SEM RETORNO.** É a representação
  nativa da API — `create_method` tem default `null`, enquanto
  `create_property` tem default `int`: o produto distingue as duas famílias.
  Converter ausência em `BOOL` ou `VOID` seria inventar IEC.
* **O membro não carrega `language`.** O parâmetro é `Nullable<Guid>` com
  default `null`, e a varredura não encontrou rota para LER a linguagem do
  owner. Duplicá-la criaria duas fontes de verdade para um valor que nem se
  confere contra o produto.

E o escopo: `methods` só existe em `function_blocks`. A matriz do `docs/86`
mediu `create_method` alcançável também em `PROGRAM` e `FUNCTION` — e isso
**não é autorização**. Deixar o campo fora dessas famílias faz a rejeição ser de
**schema**, não de convenção.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastertool_bridge.spec.validator import validate_project_spec

from mastertool_bridge.spec.validator import ST_LANGUAGE_GUID

from tests.support_spec import minimal_valid_spec as _minimal_valid_spec

SCHEMA = (Path(__file__).resolve().parent.parent.parent
          / "src" / "mastertool_bridge" / "spec" / "project_spec.schema.json")


def _com_metodos(metodos, familia="function_blocks"):
    spec = _minimal_valid_spec()
    spec[familia][0] = dict(spec[familia][0])
    spec[familia][0]["methods"] = metodos
    return spec


def _problemas(metodos, familia="function_blocks"):
    return validate_project_spec(_com_metodos(metodos, familia)).problems


# =============================================================================
# schema
# =============================================================================

def test_o_schema_define_method() -> None:
    d = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert "method" in d["$defs"]


def test_o_schema_poe_methods_SO_em_function_block() -> None:
    d = json.loads(SCHEMA.read_text(encoding="utf-8"))
    defs = d["$defs"]
    assert "methods" in defs["function_block"]["properties"]
    assert "methods" not in defs["program"]["properties"]
    assert "methods" not in defs["function"]["properties"]


def test_o_method_do_schema_NAO_tem_language() -> None:
    d = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert "language" not in d["$defs"]["method"]["properties"]


def test_o_return_type_do_schema_aceita_null() -> None:
    d = json.loads(SCHEMA.read_text(encoding="utf-8"))
    metodo = d["$defs"]["method"]
    assert metodo["properties"]["return_type"]["type"] == ["string", "null"]
    assert "return_type" not in metodo["required"]


# =============================================================================
# validator — as três formas VÁLIDAS de retorno
# =============================================================================

def test_o_caso_canonico_passa() -> None:
    """`FB_Diagnostico` da nota 25 §5.3: três métodos, nenhum com retorno."""
    assert _problemas([
        {"name": "IniciarPasso", "declaration": "METHOD IniciarPasso",
         "implementation": "xPrimeiroCiclo := TRUE;"},
        {"name": "Condicao", "declaration": "METHOD Condicao",
         "implementation": "byIndice := byIndice + 1;"},
        {"name": "CondicaoValor", "declaration": "METHOD CondicaoValor",
         "implementation": "Passo.xTemValor := TRUE;"},
    ]) == []


def test_return_type_AUSENTE_e_valido() -> None:
    assert _problemas([{"name": "M", "declaration": "d",
                        "implementation": "i"}]) == []


def test_return_type_NULL_explicito_e_valido() -> None:
    """Ausente e `null` significam a mesma coisa, e as duas formas passam: quem
    escreve a spec pode querer dizer "sem retorno" em voz alta."""
    assert _problemas([{"name": "M", "declaration": "d", "implementation": "i",
                        "return_type": None}]) == []


def test_return_type_string_e_valido() -> None:
    assert _problemas([{"name": "M", "declaration": "d", "implementation": "i",
                        "return_type": "BOOL"}]) == []


# =============================================================================
# validator — recusas
# =============================================================================

def test_language_no_MEMBRO_e_recusado() -> None:
    problemas = _problemas([{"name": "M", "declaration": "d",
                             "implementation": "i",
                             "language": {"guid": ST_LANGUAGE_GUID}}])
    assert len(problemas) == 1
    assert "desconhecido" in problemas[0] and "language" in problemas[0]


def test_return_type_VAZIO_e_recusado() -> None:
    """String vazia não é "sem retorno" — é campo mal preenchido. Aceitá-la
    tornaria indistinguíveis "não declarei" e "declarei nada"."""
    problemas = _problemas([{"name": "M", "declaration": "d",
                             "implementation": "i", "return_type": ""}])
    assert len(problemas) == 1
    assert "return_type" in problemas[0]
    assert "BOOL" in problemas[0] and "VOID" in problemas[0]


@pytest.mark.parametrize("campo", ["name", "declaration", "implementation"])
def test_campo_obrigatorio_ausente_e_recusado(campo) -> None:
    metodo = {"name": "M", "declaration": "d", "implementation": "i"}
    del metodo[campo]
    problemas = _problemas([metodo])
    assert problemas and any(campo in p for p in problemas)


def test_nome_nao_IEC_e_recusado() -> None:
    problemas = _problemas([{"name": "2M", "declaration": "d",
                             "implementation": "i"}])
    assert len(problemas) == 1 and "name" in problemas[0]


def test_nome_REPETIDO_no_mesmo_owner_e_recusado() -> None:
    """A identidade do membro é owner + METHOD + nome (`docs/87` §6). Dois de
    mesmo nome não são dois objetos — são um pedido que o executor não saberia
    reencontrar depois."""
    problemas = _problemas([
        {"name": "M", "declaration": "d", "implementation": "i"},
        {"name": "M", "declaration": "d2", "implementation": "i2"},
    ])
    assert len(problemas) == 1
    assert "repetido" in problemas[0]


def test_methods_precisa_ser_LISTA() -> None:
    problemas = _problemas({"name": "M"})
    assert problemas and "lista" in problemas[0]


def test_campo_desconhecido_no_metodo_e_recusado() -> None:
    problemas = _problemas([{"name": "M", "declaration": "d",
                             "implementation": "i", "inventado": 1}])
    assert len(problemas) == 1 and "inventado" in problemas[0]


# =============================================================================
# escopo — a rejeição é de SCHEMA, não de convenção
# =============================================================================

@pytest.mark.parametrize("familia", ["programs", "functions"])
def test_methods_fora_de_function_block_e_recusado(familia) -> None:
    problemas = _problemas([{"name": "M", "declaration": "d",
                             "implementation": "i"}], familia=familia)
    assert problemas
    assert any("methods" in p and "desconhecido" in p for p in problemas), problemas
