"""R4.1 — semântica local por network.

A REGRA QUE TODOS OS TESTES DEFENDEM
====================================
    ausência de evidência  ≠  ligação provável

Os testes centrais aqui são os que provam que NADA foi inventado: literal não
vira símbolo, pino sem aresta não vira ligação, aresta de fluxo de energia não
vira acesso, e tipo de elemento não observado não ganha interpretação.

Fixtures sintéticas. Nenhum nome de projeto real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastertool_bridge.plcopen.ladder_parser import parse_ladder
from mastertool_bridge.plcopen.ladder_semantics import (
    EVIDENCE_BASES,
    INTERPRETED_KINDS,
    MODES,
    UNRESOLVED_REASONS,
    Evidence,
    classify_text,
    derive_ladder_semantics,
)
from mastertool_bridge.plcopen.logical_topology import derive_logical_topology

FIXTURE = (Path(__file__).resolve().parents[1] / "fixtures" / "plcopen" /
           "ladder_sample.xml")
GOLDEN = (Path(__file__).resolve().parents[1] / "fixtures" / "plcopen" /
          "ladder_sample_semantics.json")


@pytest.fixture(scope="module")
def semantica() -> dict:
    pou = parse_ladder(FIXTURE)
    return derive_ladder_semantics(pou, derive_logical_topology(pou)).to_dict()


def _acessos(semantica: dict) -> list:
    return [a for net in semantica["networks"] for a in net["accesses"]]


def _chamadas(semantica: dict) -> list:
    return [c for net in semantica["networks"] for c in net["calls"]]


def _pinos(semantica: dict) -> list:
    return [p for c in _chamadas(semantica) for p in c["pins"]]


# =============================================================================
# classificação lexical — o problema que define o slice
# =============================================================================

@pytest.mark.parametrize("texto", [
    "0", "42", "-7", "3.14", "1.5e3", "16#FF", "2#1010", "8#17",
    "T#5s", "TIME#100ms", "DATE#2026-08-03", "TRUE", "FALSE", "true",
    "'texto'", '"outro"',
])
def test_literal_NUNCA_e_classificado_como_simbolo(texto: str) -> None:
    """`in_variable` chega sempre como `expression`, inclusive para `0`.

    Um `read` de `0` seria uma variável que nunca existiu no projeto — e ela
    apareceria em toda consulta de leitores dali em diante.
    """
    assert classify_text(texto) == "literal"


@pytest.mark.parametrize("texto", [
    "ESTADO", "TEMPO", "_privado", "a1", "Estrutura.campo",
    "FB_Motor.Q", "x.y.z",
])
def test_identificador_e_reconhecido_sem_consultar_indice(texto: str) -> None:
    """`identifier` afirma que o TEXTO é sintaticamente uma referência. Não
    afirma que o símbolo existe — isso é R4.2."""
    assert classify_text(texto) == "identifier"


@pytest.mark.parametrize("texto", [
    "A + B", "f(x)", "vetor[3]", "a-b", "1abc", "%IX0.0", "x y",
])
def test_expressao_vira_ABERTO_e_nao_palpite(texto: str) -> None:
    assert classify_text(texto) == "expression"


@pytest.mark.parametrize("texto", [None, "", "   ", "\n"])
def test_texto_vazio_e_estado_proprio(texto) -> None:
    assert classify_text(texto) == "empty"


def test_TRUE_e_literal_apesar_de_casar_com_a_gramatica_de_identificador(
        ) -> None:
    """A ordem das conferências importa, e este é o caso que a revela."""
    assert classify_text("TRUE") == "literal"
    assert classify_text("TRUE_ALARME") == "identifier"


# =============================================================================
# o que a fixture produz
# =============================================================================

def test_contato_LE_a_propria_variavel(semantica) -> None:
    leituras = [a for a in _acessos(semantica)
                if a["element_kind"] == "contact"]
    assert leituras, "nenhum contato interpretado"
    assert {a["mode"] for a in leituras} == {"read"}
    assert {a["symbol"] for a in leituras} == {"ENTRADA"}


def test_negacao_NAO_muda_o_modo_do_acesso(semantica) -> None:
    """Contato NF lê a mesma variável que o NA; bobina negada escreve na dela.

    O que muda é o sentido lógico do valor, não a natureza do acesso.
    Registrar NF como não-leitura quebraria "quem lê isto?" em troca de nada.
    """
    contatos = {a["element_id"]: a for a in _acessos(semantica)
                if a["element_kind"] == "contact"}
    negados = [a for a in contatos.values()
               if a["evidence"]["detail"].get("negated")]
    normais = [a for a in contatos.values()
               if not a["evidence"]["detail"].get("negated")]
    assert negados and normais, "a fixture precisa dos dois casos"
    assert all(a["mode"] == "read" for a in negados + normais)


def test_bobina_ESCREVE_inclusive_com_SET_e_RESET(semantica) -> None:
    bobinas = [a for a in _acessos(semantica) if a["element_kind"] == "coil"]
    assert bobinas
    assert {a["mode"] for a in bobinas} == {"write"}
    armazenamentos = {a["evidence"]["detail"].get("storage") for a in bobinas}
    assert "reset" in armazenamentos, (
        "a fixture tem uma bobina RESET e ela precisa aparecer na evidência")


def test_instancia_de_FB_e_LIDA_E_ESCRITA(semantica) -> None:
    """A instância é uma variável do projeto, e chamar o bloco a lê e a
    escreve: o estado interno persiste entre ciclos."""
    instancias = [a for a in _acessos(semantica)
                  if a["evidence"]["basis"] == "declared_instance"]
    assert instancias
    assert all(a["mode"] == "read_write" for a in instancias)
    assert "TEMPORIZADOR_0" in {a["symbol"] for a in instancias}


def test_operador_nao_tem_instancia_e_FB_tem(semantica) -> None:
    por_tipo = {}
    for chamada in _chamadas(semantica):
        por_tipo.setdefault(chamada["call_type"], []).append(chamada)
    assert all(c["instance"] is None for c in por_tipo["operator"])
    assert all(c["instance"] for c in por_tipo["functionblock"])


# =============================================================================
# nada é inventado
# =============================================================================

def test_o_literal_liga_no_pino_mas_NAO_vira_acesso(semantica) -> None:
    literais = [p for p in _pinos(semantica) if p["status"] == "bound_literal"]
    assert literais, "a fixture liga `0` num pino"
    for pino in literais:
        assert pino["bound_symbol"] is None
        assert pino["bound_literal"] not in {a["symbol"]
                                             for a in _acessos(semantica)}


def test_aresta_de_FLUXO_DE_ENERGIA_nao_vira_acesso(semantica) -> None:
    """O defeito que a primeira versão deste módulo tinha.

    `EQ.Out1` ligado a um contato `ENTRADA` produzia `ENTRADA write` — o bloco
    "escrevendo" a variável que o contato apenas lê. A aresta existia; o
    significado atribuído a ela, não.

    Contato e bobina carregam o próprio acesso. A aresta entre eles e um bloco
    é condição de rung, não ligação de dado.
    """
    fluxo = [p for p in _pinos(semantica) if p["status"] == "power_flow"]
    assert fluxo, "a fixture tem bloco ligado a contato e a bobina"
    for pino in fluxo:
        assert pino["bound_symbol"] is None and pino["bound_literal"] is None

    # Nenhum acesso da fixture nasce de um bloco por causa de rung.
    de_bloco = [a for a in _acessos(semantica)
                if a["element_kind"] == "block"]
    assert all(a["evidence"]["basis"] == "declared_instance"
               for a in de_bloco), (
        "acesso de bloco só pode vir da instância declarada")


def test_pino_sem_aresta_fica_ABERTO_e_nunca_vira_ligacao(semantica) -> None:
    soltos = [p for p in _pinos(semantica) if p["status"] == "unbound"]
    assert soltos
    for pino in soltos:
        assert pino["bound_symbol"] is None and pino["bound_literal"] is None
    motivos = {u["reason"] for net in semantica["networks"]
               for u in net["unresolved"]}
    assert "pin_unbound" in motivos, (
        "pino solto tem de aparecer em `unresolved`; silenciá-lo faria o "
        "modelo parecer mais completo do que é")


def test_o_mesmo_fato_NAO_aparece_duas_vezes(semantica) -> None:
    """A primeira versão criava acesso no elemento E no pino ligado a ele, e
    `ESTADO` aparecia duas vezes na mesma network. Duas linhas para um fato só
    fazem qualquer contagem de leitores mentir."""
    for net in semantica["networks"]:
        chaves = [(a["symbol"], a["mode"], a["element_id"])
                  for a in net["accesses"]]
        assert len(chaves) == len(set(chaves))
        # E o operando ligado a um pino não gera acesso pelo bloco também.
        por_simbolo = {}
        for acesso in net["accesses"]:
            por_simbolo.setdefault(acesso["symbol"], set()).add(
                acesso["element_kind"])
        for simbolo, tipos in por_simbolo.items():
            assert not ({"in_variable", "block"} <= tipos), (
                "%s tem acesso pelo operando E pelo bloco" % simbolo)


def test_elemento_NAO_interpretado_fica_explicito(semantica) -> None:
    """`vendor_element` não recebe interpretação por antecipação — a mesma
    disciplina de `OBSERVED_ELEMENT_KINDS` no modelo canônico."""
    abertos = [u for net in semantica["networks"] for u in net["unresolved"]
               if u["reason"] == "element_kind_not_interpreted"]
    assert abertos
    assert "vendor_element" in {u["detail"]["element_kind"] for u in abertos}


def test_tipos_nao_observados_nao_ganham_implementacao_por_antecipacao(
        ) -> None:
    """`connector`, `jump`, `label` e `return` existem no canônico e NÃO estão
    entre os interpretados. Interpretá-los sem export que os contenha seria
    escrever comportamento por suposição."""
    from mastertool_bridge.plcopen.canonical_model import ELEMENT_KINDS

    for kind in ("connector", "continuation", "jump", "return"):
        assert kind in ELEMENT_KINDS
        assert kind not in INTERPRETED_KINDS


# =============================================================================
# evidência e determinismo
# =============================================================================

def test_toda_conclusao_aponta_para_POU_network_e_elemento(semantica) -> None:
    """Exigência literal do gate de R4.1."""
    for net in semantica["networks"]:
        for acesso in net["accesses"]:
            evidencia = acesso["evidence"]
            assert evidencia["pou"] and evidencia["network_id"]
            assert evidencia["element_id"] == acesso["element_id"]
            assert evidencia["basis"] in EVIDENCE_BASES
        for chamada in net["calls"]:
            assert chamada["evidence"]["network_id"] == net["network_id"]
            for pino in chamada["pins"]:
                if pino["status"] != "unbound":
                    assert pino["evidence"]["supporting"] or (
                        pino["evidence"]["basis"] == "element_value_text")


def test_a_base_de_evidencia_e_um_vocabulario_FECHADO() -> None:
    with pytest.raises(ValueError):
        Evidence(pou="P", network_id="n", element_id="e", basis="chutei")


def test_o_modo_e_um_vocabulario_FECHADO() -> None:
    from mastertool_bridge.plcopen.ladder_semantics import Access

    with pytest.raises(ValueError):
        Access(symbol="X", mode="talvez", element_id="e",
               element_kind="contact",
               evidence=Evidence(pou="P", network_id="n", element_id="e",
                                 basis="element_value_text"))
    assert set(MODES) == {"read", "write", "read_write"}


def test_o_motivo_de_ABERTO_e_um_vocabulario_FECHADO() -> None:
    from mastertool_bridge.plcopen.ladder_semantics import Unresolved

    with pytest.raises(ValueError):
        Unresolved(reason="sei_la", element_id="e", network_id="n")
    assert "expression_not_a_plain_symbol" in UNRESOLVED_REASONS


def test_o_resultado_e_DETERMINISTICO_byte_a_byte() -> None:
    """Duas derivações da mesma entrada produzem o mesmo JSON.

    Ordem de dicionário do parser não é contrato de nada, e um golden file que
    dependesse dela viraria ruído no primeiro Python diferente.
    """
    def render() -> str:
        pou = parse_ladder(FIXTURE)
        modelo = derive_ladder_semantics(pou, derive_logical_topology(pou))
        return json.dumps(modelo.to_dict(), ensure_ascii=False, indent=2,
                          sort_keys=True)

    assert render() == render()


def test_NAO_ha_dependencia_do_indice_ST() -> None:
    """R4.1 é local por network. Importar o indexador aqui misturaria duas
    fontes de erro num resultado só — e R4.2 existe exatamente para essa
    junção, com evidência própria."""
    fonte = (Path(__file__).resolve().parents[2] / "src" /
             "mastertool_bridge" / "plcopen" / "ladder_semantics.py")
    texto = fonte.read_text(encoding="utf-8")
    codigo = "\n".join(l for l in texto.splitlines()
                       if not l.lstrip().startswith("#"))
    for proibido in ("indexer", "symbol_resolver", "st_index"):
        assert proibido not in codigo, proibido


def test_o_golden_file_esta_estavel(semantica) -> None:
    """Se este teste falhar, a semântica mudou. Atualizar o golden é uma
    decisão — nunca um reflexo."""
    atual = json.dumps(semantica, ensure_ascii=False, indent=2,
                       sort_keys=True) + "\n"
    if not GOLDEN.is_file():
        GOLDEN.write_text(atual, encoding="utf-8", newline="\n")
        pytest.skip("golden criado agora")
    assert atual == GOLDEN.read_text(encoding="utf-8")
