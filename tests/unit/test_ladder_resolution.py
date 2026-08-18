"""R4.2 — resolução Ladder × índice ST, e a camada unificada.

O QUE ESTES TESTES DEFENDEM
===========================
1. **Nenhuma segunda precedência.** A resolução é a do indexador. Um teste
   varre o módulo procurando reimplementação.
2. **Zero promoção por semelhança.** Mais de um candidato válido permanece
   ambíguo; nome parecido não resolve.
3. **`power_flow` nunca vira símbolo.** Ele sobrevive como evidência da
   lógica.
4. **Literal nunca vira acesso**, nem sequer como não-resolvido.
5. **Um fato, uma linha.** Duas evidências do mesmo uso não são dois
   leitores; dois contatos reais da mesma variável são dois usos.

Fixtures sintéticas.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastertool_bridge.indexer.models import (
    PouSymbol,
    Reference,
    SourceLocation,
    VariableDeclaration,
)
from mastertool_bridge.indexer.reference_resolver import (
    ResolvedReference,
    build_symbol_index,
)
from mastertool_bridge.plcopen.ladder_parser import parse_ladder
from mastertool_bridge.plcopen.ladder_resolution import (
    GROUP_TO_SCOPE,
    UNRESOLVED_CATEGORIES,
    UnifiedSymbolView,
    pou_symbol_from_graphic,
    resolve_ladder_semantics,
)
from mastertool_bridge.plcopen.ladder_semantics import derive_ladder_semantics
from mastertool_bridge.plcopen.logical_topology import derive_logical_topology

FIXTURE = (Path(__file__).resolve().parents[1] / "fixtures" / "plcopen" /
           "ladder_sample.xml")
GOLDEN = (Path(__file__).resolve().parents[1] / "fixtures" / "plcopen" /
          "ladder_sample_resolved.json")


def _resolver(simbolos_extra=(), owner=True):
    pou = parse_ladder(FIXTURE)
    semantica = derive_ladder_semantics(pou, derive_logical_topology(pou))
    simbolo, diagnosticos = pou_symbol_from_graphic(pou)
    index = build_symbol_index([simbolo, *simbolos_extra])
    return resolve_ladder_semantics(
        semantica, index, simbolo if owner else None,
        extra_diagnostics=diagnosticos)


@pytest.fixture(scope="module")
def resolvido():
    return _resolver()


@pytest.fixture(scope="module")
def visao(resolvido):
    return UnifiedSymbolView(ladder=resolvido).with_calls(resolvido)


def _var(nome, tipo, escopo="VAR"):
    return VariableDeclaration(name=nome, declared_type=tipo, scope=escopo)


def _pou(node_id, nome, variaveis=(), kind="FUNCTION_BLOCK"):
    return PouSymbol(node_id=node_id, pou_kind=kind, name=nome,
                     file="%s.st" % nome, variables=list(variaveis))


# =============================================================================
# a fixture — as respostas que o gate exige
# =============================================================================

def test_SAIDA_A_tem_exatamente_dois_writes(visao) -> None:
    escritores = visao.writers("SAIDA_A")
    assert len(escritores) == 2
    assert {f["network_id"] for f in escritores} == {"net:0001", "net:0002"}
    assert all(f["source_language"] == "LD" for f in escritores)


def test_ENTRADA_tem_dois_reads_DISTINTOS(visao) -> None:
    """Contato NA e contato NF são dois usos reais. O operador desenhou dois,
    e uma consulta de leitores tem de mostrar dois."""
    leitores = visao.readers("ENTRADA")
    assert len(leitores) == 2
    assert len({f["element_id"] for f in leitores}) == 2
    assert len({f["access_id"] for f in leitores}) == 2


def test_ESTADO_tem_um_read(visao) -> None:
    assert len(visao.readers("ESTADO")) == 1


def test_TEMPO_tem_um_read_no_pino_PT(visao, resolvido) -> None:
    leitores = visao.readers("TEMPO")
    assert len(leitores) == 1
    assert leitores[0]["network_id"] == "net:0002"
    ton = [c for c in resolvido.calls if c.target_text == "TON"][0]
    pt = [p for p in ton.pins if p["formal_parameter"] == "PT"][0]
    assert pt["bound_symbol"] == "TEMPO"


def test_o_literal_0_NAO_aparece_em_lugar_nenhum(resolvido, visao) -> None:
    """Nem como acesso, nem como leitor, nem como não-resolvido."""
    assert "0" not in {a.symbol_text for a in resolvido.accesses}
    assert visao.readers("0") == [] and visao.writers("0") == []
    assert "0" not in {u.get("symbol_text") for u in resolvido.unresolved}
    assert "0" not in visao.symbols()


def test_EQ_Out1_NAO_vira_escritor(visao, resolvido) -> None:
    """A aresta `EQ.Out1 → contato ENTRADA` é fluxo de energia. Tratá-la como
    escrita criaria uma dependência falsa sustentada por uma aresta
    verdadeira."""
    assert visao.writers("ENTRADA") == []
    fluxo = [p for c in resolvido.calls for p in c.pins
             if p["status"] == "power_flow"]
    assert fluxo, "a fixture tem bloco ligado a contato e bobina"
    for pino in fluxo:
        assert pino["bound_symbol"] is None


def test_TEMPORIZADOR_0_e_read_write(resolvido) -> None:
    instancias = [a for a in resolvido.accesses
                  if a.symbol_text == "TEMPORIZADOR_0"]
    assert len(instancias) == 1
    assert instancias[0].mode == "read_write"


def test_TON_e_call_com_instancia_e_os_dois_fatos_sao_SEPARADOS(
        resolvido) -> None:
    """`acesso à instância` e `chamada ao tipo` não se colapsam: a instância
    pode existir com o tipo ausente, e vice-versa."""
    ton = [c for c in resolvido.calls if c.target_text == "TON"]
    assert len(ton) == 1
    assert ton[0].call_kind == "functionblock"
    assert ton[0].instance_symbol_text == "TEMPORIZADOR_0"
    # Dois campos, rastreados em separado. Que eles COINCIDAM aqui é acidente
    # desta fixture; que sejam independentes é o contrato, e está provado em
    # `test_INSTANCIA_resolvida_com_TIPO_nao_resolvido` e no seu inverso.
    assert ton[0].instance_resolution_status is not None
    assert ton[0].resolved_target_id is None
    assert ton[0].instance_symbol_id is None
    # E o acesso à instância é um fato SEPARADO da chamada.
    assert any(a.symbol_text == "TEMPORIZADOR_0" and a.mode == "read_write"
               for a in resolvido.accesses)


def test_operador_do_padrao_nao_e_declarado_INEXISTENTE(resolvido) -> None:
    """`EQ` e `MOVE` são operadores IEC, não POUs do projeto. Procurá-los no
    índice devolveria "inexistente" sobre algo que existe — só não aqui."""
    operadores = [c for c in resolvido.calls if c.call_kind == "operator"]
    assert operadores
    assert {c.resolution_status for c in operadores} == {"not_applicable"}
    assert all(c.unresolved_category is None for c in operadores)


def test_NAO_ha_duplicacao_elemento_mais_pino(resolvido) -> None:
    ids = [a.access_id for a in resolvido.accesses]
    assert len(ids) == len(set(ids))
    for simbolo in ("ESTADO", "TEMPO"):
        acessos = [a for a in resolvido.accesses if a.symbol_text == simbolo]
        assert len(acessos) == 1, simbolo


# =============================================================================
# resolução — os casos exigidos
# =============================================================================

def test_simbolo_LOCAL_resolve_com_escopo_e_tipo(resolvido) -> None:
    estado = [a for a in resolvido.accesses if a.symbol_text == "ESTADO"][0]
    assert estado.resolution_status == "resolved"
    assert estado.declaration_scope == "VAR"
    assert estado.declared_type == "INT"


def test_parametro_de_entrada_e_saida_resolvem(resolvido) -> None:
    por_nome = {a.symbol_text: a for a in resolvido.accesses}
    assert por_nome["ENTRADA"].declaration_scope == "VAR_INPUT"
    assert por_nome["SAIDA_A"].declaration_scope == "VAR_OUTPUT"


def test_simbolo_GLOBAL_resolve_pela_precedencia_do_indexador() -> None:
    gvl = _pou("gvl:G", "G", [_var("ESTADO_GLOBAL", "BOOL", "VAR_GLOBAL")],
               kind="GVL")
    resolvido = _resolver(simbolos_extra=[gvl])
    # A fixture não cita a global; o que se prova aqui é que o índice a
    # conhece e que a resolução da POU continua correta com ela presente.
    assert any(a.resolution_status == "resolved" for a in resolvido.accesses)


def test_INSTANCIA_de_FB_resolve_quando_declarada() -> None:
    """`TEMPORIZADOR_0` não está na interface exportada. Declarando-a numa
    POU com o mesmo nome, a instância passa a resolver — e o tipo também,
    se o FB estiver no índice."""
    pou_com_instancia = _pou(
        "ld:FB_EXEMPLO", "FB_EXEMPLO",
        [_var("TEMPORIZADOR_0", "TON", "VAR")])
    tipo = _pou("fb:TON", "TON")
    pou = parse_ladder(FIXTURE)
    semantica = derive_ladder_semantics(pou, derive_logical_topology(pou))
    index = build_symbol_index([pou_com_instancia, tipo])
    resolvido = resolve_ladder_semantics(semantica, index, pou_com_instancia)

    instancia = [a for a in resolvido.accesses
                 if a.symbol_text == "TEMPORIZADOR_0"][0]
    assert instancia.resolution_status == "resolved"
    ton = [c for c in resolvido.calls if c.target_text == "TON"][0]
    assert ton.resolution_status == "resolved"
    assert ton.resolved_target_id == "fb:TON"


def test_simbolo_INEXISTENTE_fica_unresolved_e_nao_resolve_por_semelhanca(
        resolvido) -> None:
    """`TEMPORIZADOR_0` não está declarado, e não existe nada parecido que o
    resolvedor possa escolher."""
    instancia = [a for a in resolvido.accesses
                 if a.symbol_text == "TEMPORIZADOR_0"][0]
    assert instancia.resolution_status == "unresolved"
    assert instancia.unresolved_category == "symbol_not_found"
    assert instancia.resolved_symbol_id is None


def test_simbolo_AMBIGUO_nao_e_reduzido_a_unresolved() -> None:
    """Os diagnósticos e as ações de correção são diferentes: ambíguo é erro
    de escopo, inexistente é erro de projeto."""
    duplicado = PouSymbol(
        node_id="ld:FB_EXEMPLO", pou_kind="FUNCTION_BLOCK", name="FB_EXEMPLO",
        file="x", variables=[_var("ESTADO", "INT", "VAR"),
                             _var("ESTADO", "BOOL", "VAR_TEMP")])
    pou = parse_ladder(FIXTURE)
    semantica = derive_ladder_semantics(pou, derive_logical_topology(pou))
    resolvido = resolve_ladder_semantics(
        semantica, build_symbol_index([duplicado]), duplicado)

    estado = [a for a in resolvido.accesses if a.symbol_text == "ESTADO"][0]
    assert estado.resolution_status == "ambiguous"
    assert estado.unresolved_category == "symbol_ambiguous"
    categorias = {u["category"] for u in resolvido.unresolved}
    assert "symbol_ambiguous" in categorias
    assert estado.resolution_status != "unresolved"


def test_tipo_de_FB_AMBIGUO_deixa_a_chamada_ambigua() -> None:
    pou_com_instancia = _pou("ld:FB_EXEMPLO", "FB_EXEMPLO",
                             [_var("TEMPORIZADOR_0", "TON", "VAR")])
    pou = parse_ladder(FIXTURE)
    semantica = derive_ladder_semantics(pou, derive_logical_topology(pou))
    index = build_symbol_index([pou_com_instancia, _pou("fb:TON#a", "TON"),
                                _pou("fb:TON#b", "TON")])
    resolvido = resolve_ladder_semantics(semantica, index, pou_com_instancia)
    ton = [c for c in resolvido.calls if c.target_text == "TON"][0]
    assert ton.resolution_status == "ambiguous"
    assert ton.resolved_target_id is None


def test_INSTANCIA_resolvida_com_TIPO_nao_resolvido() -> None:
    """Os dois estados são independentes — este é o caso que prova."""
    pou_com_instancia = _pou("ld:FB_EXEMPLO", "FB_EXEMPLO",
                             [_var("TEMPORIZADOR_0", "TON", "VAR")])
    pou = parse_ladder(FIXTURE)
    semantica = derive_ladder_semantics(pou, derive_logical_topology(pou))
    resolvido = resolve_ladder_semantics(
        semantica, build_symbol_index([pou_com_instancia]), pou_com_instancia)
    ton = [c for c in resolvido.calls if c.target_text == "TON"][0]
    assert ton.instance_resolution_status == "resolved"
    assert ton.resolution_status == "unresolved"


def test_TIPO_resolvido_com_INSTANCIA_ausente(resolvido) -> None:
    pou = parse_ladder(FIXTURE)
    semantica = derive_ladder_semantics(pou, derive_logical_topology(pou))
    simbolo, _ = pou_symbol_from_graphic(pou)
    index = build_symbol_index([simbolo, _pou("fb:TON", "TON")])
    saida = resolve_ladder_semantics(semantica, index, simbolo)
    ton = [c for c in saida.calls if c.target_text == "TON"][0]
    assert ton.resolution_status == "resolved"
    assert ton.instance_resolution_status == "unresolved"


def test_sem_POU_dona_e_CONTEXTO_INSUFICIENTE_e_nao_inexistente() -> None:
    """Sem a POU, os níveis 1/2 e 3 não têm onde procurar. Chamar isso de
    "não encontrado" mandaria alguém procurar um defeito de projeto onde há
    um defeito de setup."""
    resolvido = _resolver(owner=False)
    assert {a.unresolved_category for a in resolvido.accesses} == {
        "insufficient_context"}
    assert "insufficient_context" in {u["category"]
                                      for u in resolvido.unresolved}


def test_as_quatro_categorias_de_ABERTO_sao_distintas() -> None:
    assert set(UNRESOLVED_CATEGORIES) == {
        "symbol_not_found", "symbol_ambiguous", "expression_not_supported",
        "insufficient_context"}


# =============================================================================
# cross-language
# =============================================================================

def _ref_st(nome, classificacao, node_id="st:PRG", linha=1):
    referencia = Reference(node_id=node_id, file="PRG.st", name=nome,
                           context="assignment_target",
                           location=SourceLocation(file="PRG.st", line=linha,
                                                   column=1))
    return ResolvedReference(reference=referencia, resolution_state="resolved",
                             resolved_symbol="sym:%s" % nome,
                             classification=classificacao)


def test_variavel_escrita_em_ST_e_em_LADDER(resolvido) -> None:
    visao = UnifiedSymbolView(ladder=resolvido,
                              st_resolved_references=[
                                  _ref_st("SAIDA_A", "write")])
    escritores = visao.writers("SAIDA_A")
    assert len(escritores) == 3
    assert {f["source_language"] for f in escritores} == {"LD", "ST"}


def test_variavel_lida_em_ST_e_escrita_em_LADDER(resolvido) -> None:
    visao = UnifiedSymbolView(ladder=resolvido,
                              st_resolved_references=[
                                  _ref_st("SAIDA_B", "read")])
    assert {f["source_language"] for f in visao.readers("SAIDA_B")} == {"ST"}
    assert {f["source_language"] for f in visao.writers("SAIDA_B")} == {"LD"}


def test_cross_language_mantem_as_ORIGENS_separadas(resolvido) -> None:
    visao = UnifiedSymbolView(ladder=resolvido,
                              st_resolved_references=[
                                  _ref_st("SAIDA_A", "write"),
                                  _ref_st("ENTRADA", "read")])
    cruzados = visao.cross_language()
    assert set(cruzados) == {"SAIDA_A", "ENTRADA"}
    for simbolo, dados in cruzados.items():
        assert dados["languages"] == ["LD", "ST"]
        for fato in dados["facts"]:
            assert fato["source_language"] in ("LD", "ST")
            if fato["source_language"] == "LD":
                assert fato["network_id"] and fato["element_id"]
            else:
                assert fato["file"] and fato["location"]


def test_multi_writers_MISTOS_aparecem(resolvido) -> None:
    visao = UnifiedSymbolView(ladder=resolvido,
                              st_resolved_references=[
                                  _ref_st("SAIDA_B", "write")])
    multiplos = visao.multi_writers()
    assert "SAIDA_A" in multiplos          # dois writers só em Ladder
    assert "SAIDA_B" in multiplos          # um Ladder + um ST
    assert {f["source_language"] for f in multiplos["SAIDA_B"]} == {"LD", "ST"}


def test_multi_writers_so_em_ladder(visao) -> None:
    multiplos = visao.multi_writers()
    assert list(multiplos) == ["SAIDA_A"]
    assert len(multiplos["SAIDA_A"]) == 2


# =============================================================================
# adversariais
# =============================================================================

def test_ordem_dos_simbolos_no_indice_nao_muda_o_resultado() -> None:
    a = _pou("p:A", "A", [_var("X", "BOOL")])
    b = _pou("p:B", "B", [_var("Y", "BOOL")])
    um = _resolver(simbolos_extra=[a, b]).to_dict()
    outro = _resolver(simbolos_extra=[b, a]).to_dict()
    assert json.dumps(um, sort_keys=True) == json.dumps(outro, sort_keys=True)


def test_indice_INCOMPLETO_nao_promove_nada_por_omissao() -> None:
    """Índice sem a POU dona: tudo cai, e cai pela razão certa."""
    resolvido = _resolver(owner=False)
    assert all(a.resolution_status == "unresolved" for a in resolvido.accesses)
    assert all(a.resolved_symbol_id is None for a in resolvido.accesses)


def test_power_flow_ligado_a_identificador_continua_power_flow(
        resolvido) -> None:
    """A aresta liga a um contato cujo texto É um identificador válido. Ela
    continua sendo condição de rung — o identificador já produziu o próprio
    acesso, no elemento dele."""
    fluxo = [p for c in resolvido.calls for p in c.pins
             if p["status"] == "power_flow"]
    assert fluxo
    for pino in fluxo:
        assert pino["bound_symbol"] is None
        assert pino["evidence"]["detail"].get("source_element_kind") in (
            "contact", "coil")


def test_literal_parecido_com_identificador_nao_resolve(resolvido) -> None:
    """`TRUE` casa com a gramática de identificador e é literal. Se algum dia
    ele virar acesso, esta asserção cai antes de a consulta mentir."""
    assert "TRUE" not in {a.symbol_text for a in resolvido.accesses}


def test_identificador_valido_mas_INEXISTENTE_nao_vira_simbolo(
        resolvido) -> None:
    aberto = [a for a in resolvido.accesses
              if a.resolution_status == "unresolved"]
    assert aberto
    for acesso in aberto:
        assert acesso.resolved_symbol_id is None
        assert acesso.declared_type is None


def test_grupo_de_interface_DESCONHECIDO_vira_diagnostico_e_nao_escopo(
        ) -> None:
    """Errar o escopo mudaria a precedência de resolução inteira. Um grupo
    fora do mapa não vira escopo por semelhança de nome."""
    class _Entrada:
        def __init__(self, nome, grupo, tipo):
            self.name, self.group, self.type_name = nome, grupo, tipo

    class _POU:
        name = "P"
        pou_type = "functionBlock"
        source_file = "p.xml"
        interface = [_Entrada("X", "grupoInventado", "BOOL")]

    simbolo, diagnosticos = pou_symbol_from_graphic(_POU())
    assert simbolo.variables[0].scope == "grupoInventado"
    assert not simbolo.variables[0].scope.startswith("VAR")
    assert any(d["code"] == "interface_group_not_mapped" for d in diagnosticos)


def test_o_mapa_de_grupos_usa_o_vocabulario_IEC() -> None:
    """`_POU_LOCAL_SCOPE_PREFIXES` aceita qualquer coisa que comece com
    `VAR`; um nome inventado aqui resolveria pelo motivo errado."""
    for grupo, escopo in GROUP_TO_SCOPE.items():
        assert escopo.startswith("VAR"), grupo


# =============================================================================
# a fronteira com o indexador
# =============================================================================

def test_NAO_existe_segunda_precedencia_de_escopo() -> None:
    """Uma resolução específica para Ladder divergiria da do ST no dia em que
    alguém corrigisse só uma delas — e a divergência apareceria como "o mesmo
    símbolo resolve diferente dependendo da linguagem"."""
    fonte = (Path(__file__).resolve().parents[2] / "src" /
             "mastertool_bridge" / "plcopen" / "ladder_resolution.py")
    codigo = "\n".join(
        linha for linha in fonte.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#"))
    assert "resolve_identifier" in codigo, "o resolvedor do indexador é usado"
    for reimplementacao in ("def resolve_identifier", "def find_pou_local",
                            "_POU_LOCAL_SCOPE_PREFIXES", "def _resolve_level"):
        assert reimplementacao not in codigo, reimplementacao


def test_o_resultado_e_DETERMINISTICO() -> None:
    assert (json.dumps(_resolver().to_dict(), sort_keys=True)
            == json.dumps(_resolver().to_dict(), sort_keys=True))


def test_toda_aresta_e_consultavel_com_ORIGEM(resolvido, visao) -> None:
    for simbolo in visao.symbols():
        for fato in visao.readers(simbolo) + visao.writers(simbolo):
            assert fato["source_language"]
            if fato["source_language"] == "LD":
                assert fato["pou"] and fato["network_id"]
                assert fato["element_id"] and fato["access_id"]


def test_o_golden_de_resolucao_esta_estavel(resolvido) -> None:
    atual = json.dumps(resolvido.to_dict(), ensure_ascii=False, indent=2,
                       sort_keys=True) + "\n"
    if not GOLDEN.is_file():
        GOLDEN.write_text(atual, encoding="utf-8", newline="\n")
        pytest.skip("golden criado agora")
    assert atual == GOLDEN.read_text(encoding="utf-8")
