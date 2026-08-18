"""R4-FIELD-FIX-01 — os dois defeitos que a medição de campo dimensionou.

O QUE ESTES TESTES DEFENDEM
===========================
1. **Forma e nome do tipo são fatos separados.** Guardar só a forma apagava o
   nome de todo tipo derivado (`<derived name="TON"/>` virava `"derived"`);
   substituir a forma pelo nome apagaria a distinção entre primitivo e
   derivado. Os dois campos existem para que nenhuma das duas perdas volte.
2. **Uma única resolução de alvo de chamada.** ST e Ladder respondem a mesma
   pergunta com o mesmo código: a cópia do lado Ladder procurava só entre
   FUNCTION_BLOCKs, e toda chamada a PROGRAM saía como símbolo inexistente com
   a POU presente no índice.
3. **Nenhuma precedência nova, nenhum palpite.** Ambiguidade nunca vira
   escolha do primeiro nome encontrado.

Fixtures sintéticas.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mastertool_bridge.indexer.models import PouSymbol, VariableDeclaration
from mastertool_bridge.indexer.symbol_resolver import (
    CALLABLE_POU_KINDS,
    ProjectSymbolIndex,
    resolve_callable_target,
)
from mastertool_bridge.plcopen.canonical_model import InterfaceVariable
from mastertool_bridge.plcopen.ladder_resolution import pou_symbol_from_graphic
from mastertool_bridge.plcopen.structure_map import (
    IEC_ELEMENTARY_TYPE_TAGS,
    map_structure,
)

REPO = Path(__file__).resolve().parents[2]


# =============================================================================
# fixtures
# =============================================================================

def _pou_xml(variaveis: str, tmp_path: Path, *, nome: str = "P") -> Path:
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<project xmlns="http://www.plcopen.org/xml/tc6_0200">'
           '<types><pous>'
           '<pou name="%s" pouType="functionBlock">'
           '<interface><localVars>%s</localVars></interface>'
           '<body><LD/></body></pou>'
           '</pous></types></project>' % (nome, variaveis))
    alvo = tmp_path / "pou.xml"
    alvo.write_text(xml, encoding="utf-8")
    return alvo


def _var(nome: str, interno: str) -> str:
    return '<variable name="%s"><type>%s</type></variable>' % (nome, interno)


def _tipos(caminho: Path) -> dict:
    estrutura = map_structure(caminho)
    return {v["name"]: v for v in estrutura.pou["interface_variables"]}


def _pou_falsa(interface):
    class _P:
        name = "P"
        pou_type = "functionBlock"
        source_file = ""

    p = _P()
    p.interface = interface
    return p


def _indice(*simbolos) -> ProjectSymbolIndex:
    return ProjectSymbolIndex(list(simbolos))


def _simbolo(nome: str, kind: str, variaveis=()) -> PouSymbol:
    return PouSymbol(node_id="%s:%s" % (kind.lower(), nome), pou_kind=kind,
                     name=nome, file="", variables=list(variaveis))


# =============================================================================
# correção 1 — o nome do tipo derivado sobrevive
# =============================================================================

def test_derived_preserva_FORMA_e_NOME(tmp_path) -> None:
    """O defeito medido: 55 de 122 declarações Ladder eram `derived`, e todas
    chegavam ao índice como a string "derived", que não casa com tipo nenhum."""
    tipos = _tipos(_pou_xml(_var("T", '<derived name="TON"/>'), tmp_path))
    assert tipos["T"]["type_kind"] == "derived"
    assert tipos["T"]["type_name"] == "TON"


def test_primitivo_tem_forma_E_nome_iguais(tmp_path) -> None:
    """Para elementar o nome do tipo É a tag. Os dois campos coincidem, e é
    isso que mantém o comportamento anterior intacto onde ele estava certo."""
    tipos = _tipos(_pou_xml(_var("B", "<BOOL/>") + _var("W", "<WORD/>"),
                            tmp_path))
    assert tipos["B"]["type_kind"] == tipos["B"]["type_name"] == "BOOL"
    assert tipos["W"]["type_kind"] == tipos["W"]["type_name"] == "WORD"


def test_derived_SEM_name_nao_inventa_nome(tmp_path) -> None:
    """O tipo existe no documento e o nome não é derivável dele. `None` é a
    resposta honesta; um nome montado por aproximação resolveria contra o
    símbolo errado."""
    caminho = _pou_xml(_var("X", "<derived/>"), tmp_path)
    tipos = _tipos(caminho)
    assert tipos["X"]["type_kind"] == "derived"
    assert tipos["X"]["type_name"] is None
    codigos = [d for d in map_structure(caminho).diagnostics
               if d.get("step") == "interface_type"]
    assert codigos and codigos[0]["variable"] == "X"


def test_elemento_de_tipo_DESCONHECIDO_mantem_a_forma(tmp_path) -> None:
    """Uma tag fora do vocabulário não vira elementar por semelhança de nome —
    confundir forma com nome foi exatamente o defeito corrigido aqui."""
    tipos = _tipos(_pou_xml(_var("Z", "<coisaNova/>"), tmp_path))
    assert tipos["Z"]["type_kind"] == "coisaNova"
    assert tipos["Z"]["type_name"] is None
    assert "coisaNova" not in IEC_ELEMENTARY_TYPE_TAGS


def test_array_e_string_nao_ganham_nome_montado(tmp_path) -> None:
    """Montar `ARRAY[..] OF X` aqui produziria um tipo que o resto do produto
    nunca produz."""
    tipos = _tipos(_pou_xml(
        _var("A", "<array><dimension/></array>") + _var("S", "<string/>"),
        tmp_path))
    assert tipos["A"]["type_kind"] == "array"
    assert tipos["A"]["type_name"] is None
    assert tipos["S"]["type_name"] is None


def test_declared_type_usa_o_NOME_quando_existe() -> None:
    derivada = InterfaceVariable(name="T", group="localVars",
                                 type_kind="derived", type_name="TON")
    primitiva = InterfaceVariable(name="B", group="localVars",
                                  type_kind="BOOL", type_name="BOOL")
    sem_nome = InterfaceVariable(name="A", group="localVars",
                                 type_kind="array", type_name=None)
    assert derivada.declared_type == "TON"
    assert primitiva.declared_type == "BOOL"
    # Sem nome derivável, a FORMA sobrevive: apagá-la esconderia a declaração
    # inteira em vez de só o nome.
    assert sem_nome.declared_type == "array"


def test_a_declaracao_chega_ao_indice_com_o_NOME_do_tipo() -> None:
    """A ponta do defeito: é `declared_type` que o nível 3 da precedência
    compara contra o nome de um FUNCTION_BLOCK."""
    simbolo, _ = pou_symbol_from_graphic(_pou_falsa([
        InterfaceVariable(name="T", group="localVars", type_kind="derived",
                          type_name="TON")]))
    assert simbolo.variables[0].declared_type == "TON"


def test_derived_sem_nome_produz_DIAGNOSTICO_na_montagem() -> None:
    _, diagnosticos = pou_symbol_from_graphic(_pou_falsa([
        InterfaceVariable(name="X", group="localVars", type_kind="derived",
                          type_name=None)]))
    codigos = [d["code"] for d in diagnosticos]
    assert "derived_type_without_name" in codigos


def test_instancia_de_FB_volta_a_resolver_pelo_tipo() -> None:
    """O efeito completo da correção 1: com o nome preservado, o nível 3 da
    precedência — que já existia — volta a disparar. Nenhuma regra nova."""
    from mastertool_bridge.indexer.symbol_resolver import resolve_identifier

    dono, _ = pou_symbol_from_graphic(_pou_falsa([
        InterfaceVariable(name="TEMPO", group="localVars",
                          type_kind="derived", type_name="TON")]))
    indice = _indice(dono, _simbolo("TON", "FUNCTION_BLOCK"))
    ref = resolve_identifier("TEMPO", dono, indice)
    assert ref.state == "resolved"


# =============================================================================
# correção 2 — o alvo da chamada usa o resolvedor compartilhado
# =============================================================================

def test_alvo_PROGRAM_resolve() -> None:
    """O defeito medido: 21 chamadas, todas com alvo PROGRAM presente no
    índice, saíam como símbolo inexistente."""
    ref = resolve_callable_target("Acionar", _indice(
        _simbolo("Acionar", "PROGRAM")))
    assert ref.state == "resolved"
    assert ref.rule_applied == "program_direct"


def test_alvo_FUNCTION_BLOCK_resolve() -> None:
    ref = resolve_callable_target("FB", _indice(_simbolo("FB",
                                                        "FUNCTION_BLOCK")))
    assert ref.state == "resolved"
    assert ref.rule_applied == "function_block_direct"


def test_alvo_FUNCTION_resolve() -> None:
    ref = resolve_callable_target("Fun", _indice(_simbolo("Fun", "FUNCTION")))
    assert ref.state == "resolved"
    assert ref.rule_applied == "function_direct"


def test_alvo_AUSENTE_do_corpus_volta_unresolved_sem_palpite() -> None:
    """Classificar isso como ausência de artefato é decisão de quem consome,
    com evidência do corpus — não do resolvedor, que não sabe o que o export
    trouxe."""
    ref = resolve_callable_target("TON", _indice(_simbolo("P", "PROGRAM")))
    assert ref.state == "unresolved"
    assert ref.resolved_symbol is None
    assert ref.candidates == []


def test_alvo_AMBIGUO_nunca_escolhe_o_primeiro() -> None:
    indice = _indice(_simbolo("Dup", "PROGRAM"),
                     PouSymbol(node_id="outro", pou_kind="PROGRAM",
                               name="Dup", file=""))
    ref = resolve_callable_target("Dup", indice)
    assert ref.state == "ambiguous"
    assert ref.resolved_symbol is None
    assert len(ref.candidates) == 2


def test_mesmo_nome_em_CATEGORIAS_diferentes_para_no_primeiro_nivel() -> None:
    """A ordem das categorias decide, exatamente como na precedência de
    identificadores: para no primeiro nível com candidato e não desce. Num
    projeto IEC o nome de POU é único, então esta é uma defesa contra índice
    malformado — e ela é determinística, não arbitrária."""
    indice = _indice(_simbolo("X", "FUNCTION_BLOCK"), _simbolo("X", "PROGRAM"))
    ref = resolve_callable_target("X", indice)
    assert ref.state == "resolved"
    assert ref.rule_applied == "function_block_direct"
    assert CALLABLE_POU_KINDS.index("FUNCTION_BLOCK") < (
        CALLABLE_POU_KINDS.index("PROGRAM"))


def test_o_dialeto_do_ST_exclui_FUNCTION_BLOCK_por_NOME() -> None:
    """Em ST um FUNCTION_BLOCK só é chamado por variável de instância. Isso é
    dialeto, e por isso `kinds` é parâmetro — não uma segunda regra."""
    indice = _indice(_simbolo("FB", "FUNCTION_BLOCK"))
    assert resolve_callable_target("FB", indice).state == "resolved"
    assert resolve_callable_target(
        "FB", indice, kinds=("FUNCTION", "PROGRAM")).state == "unresolved"


def test_ST_e_LADDER_dao_a_MESMA_resposta_para_PROGRAM() -> None:
    """A propriedade que o corretivo existe para garantir: o mesmo símbolo não
    pode resolver diferente dependendo da linguagem."""
    from mastertool_bridge.indexer.call_resolver import resolve_calls
    from mastertool_bridge.indexer.models import Call, SourceLocation

    chamador = _simbolo("Main", "PROGRAM")
    alvo = _simbolo("Acionar", "PROGRAM")
    indice = _indice(chamador, alvo)

    st, _ = resolve_calls(
        [Call(node_id="program:Main#stmt1", file="f", callee="Acionar",
              location=SourceLocation(file="f", line=1, column=1))],
        indice)
    ld = resolve_callable_target("Acionar", indice)

    assert st[0].resolution_state == ld.state == "resolved"
    assert st[0].resolved_symbol == ld.resolved_symbol == alvo.node_id
    assert st[0].rule_applied == ld.rule_applied == "program_direct"


def test_operador_IEC_continua_NOT_APPLICABLE() -> None:
    """Um operador do padrão não é POU do projeto, e procurá-lo no índice
    devolveria "inexistente" sobre algo que existe — só não aqui."""
    from mastertool_bridge.plcopen.ladder_resolution import (
        resolve_ladder_semantics,
    )

    dono = _simbolo("P", "PROGRAM")
    resolvido = resolve_ladder_semantics(
        _semantica(chamadas=[{"element_id": "e1", "target": "EQ",
                              "instance": None, "call_type": "operator",
                              "pins": []}]),
        _indice(dono), dono)
    assert resolvido.calls[0].resolution_status == "not_applicable"
    assert resolvido.calls[0].unresolved_category is None


def test_chamada_LADDER_a_PROGRAM_resolve_ponta_a_ponta() -> None:
    from mastertool_bridge.plcopen.ladder_resolution import (
        resolve_ladder_semantics,
    )

    dono = _simbolo("P", "PROGRAM")
    alvo = _simbolo("Acionar", "PROGRAM")
    resolvido = resolve_ladder_semantics(
        _semantica(chamadas=[{"element_id": "e1", "target": "Acionar",
                              "instance": None, "call_type": "function_block",
                              "pins": []}]),
        _indice(dono, alvo), dono)
    assert resolvido.calls[0].resolution_status == "resolved"
    assert resolvido.calls[0].resolved_target_id == alvo.node_id
    assert not resolvido.unresolved


def _semantica(*, chamadas=(), acessos=()):
    return {"pou": "P", "networks": [{
        "network_id": "net:1", "accesses": list(acessos),
        "calls": list(chamadas), "unresolved": []}]}


# =============================================================================
# guardas arquiteturais
# =============================================================================

def test_ladder_resolution_NAO_consulta_os_indices_por_categoria() -> None:
    """A guarda estrutural contra uma segunda precedência: o módulo Ladder não
    pode voltar a consultar `function_blocks_by_name` e companhia direto — foi
    assim que a divergência nasceu. Ele chama o serviço compartilhado.

    Inspeção de ATRIBUTO na AST, não busca de substring: o nome pode aparecer
    legitimamente numa docstring, e proibir texto pegaria a explicação junto.
    """
    fonte = (REPO / "src" / "mastertool_bridge" / "plcopen"
             / "ladder_resolution.py")
    proibidos = {"function_blocks_by_name", "functions_by_name",
                 "programs_by_name", "gvls_by_name"}
    acessados = {no.attr for no in ast.walk(ast.parse(
        fonte.read_text(encoding="utf-8"))) if isinstance(no, ast.Attribute)}
    assert not (acessados & proibidos), sorted(acessados & proibidos)


def test_a_resolucao_de_alvo_vive_no_MODULO_DA_PRECEDENCIA() -> None:
    """Se ela migrasse para o módulo Ladder, voltaria a ser uma segunda
    implementação — com outro nome."""
    fonte = (REPO / "src" / "mastertool_bridge" / "indexer"
             / "symbol_resolver.py").read_text(encoding="utf-8")
    definidas = {no.name for no in ast.walk(ast.parse(fonte))
                 if isinstance(no, ast.FunctionDef)}
    assert "resolve_callable_target" in definidas


def test_o_call_resolver_do_ST_usa_o_SERVICO_e_nao_uma_copia() -> None:
    fonte = (REPO / "src" / "mastertool_bridge" / "indexer"
             / "call_resolver.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    chamadas = {no.func.id for no in ast.walk(arvore)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)}
    assert "resolve_callable_target" in chamadas
    acessados = {no.attr for no in ast.walk(arvore)
                 if isinstance(no, ast.Attribute)}
    assert "programs_by_name" not in acessados
    assert "functions_by_name" not in acessados


def test_a_resolucao_de_alvo_e_DETERMINISTICA() -> None:
    indice = _indice(_simbolo("A", "PROGRAM"), _simbolo("B", "FUNCTION"))
    for _ in range(5):
        assert resolve_callable_target("A", indice).resolved_symbol == (
            "program:A")
        assert resolve_callable_target("B", indice).rule_applied == (
            "function_direct")
