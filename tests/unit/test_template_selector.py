"""Testes de `mastertool_bridge.templates.selector` — a identidade semântica
que substitui `node_path` na fase R0b.

Cada regra é exercida nos dois sentidos. As recusas têm teste próprio porque
são o produto principal deste módulo: um seletor que só sabe acertar não
protege ninguém — o que protege é ele saber dizer "não sei" quando a árvore
não sustenta a afirmação.
"""

import pytest

from mastertool_bridge.templates import selector as sel

APPLICATION_GUID = "639b491f-5557-464c-af91-1471bac9f549"
POU_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


class No(object):
    """Nó sintético. `nome`/`tipo`/`filhos` podem ser marcados como ilegíveis
    para exercitar o caminho de exceção do adaptador."""

    ILEGIVEL = object()

    def __init__(self, nome, tipo=None, filhos=None):
        self.nome = nome
        self.tipo = tipo
        self.filhos = filhos if filhos is not None else []


def _nome(no):
    if no.nome is No.ILEGIVEL:
        raise RuntimeError("COMException ao ler get_name")
    return no.nome


def _tipo(no):
    if no.tipo is No.ILEGIVEL:
        raise RuntimeError("COMException ao ler type")
    return no.tipo


def _filhos(no):
    if no.filhos is No.ILEGIVEL:
        raise RuntimeError("COMException ao ler get_children")
    return no.filhos


VIEW = sel.NodeView(name_of=_nome, type_guid_of=_tipo, children_of=_filhos)


def _arvore(cartoes_de_io=0):
    """A árvore do TemplateExemplo v1, reduzida — com `cartoes_de_io` cartões inseridos
    ANTES do `Plc Logic`, que é exatamente o que a troca de projeto-base de
    2026-07-31 fez e o que desloca os índices."""
    application = No("Application", APPLICATION_GUID, [
        No("MainPrg", POU_GUID),
        No("MainTask", "task"),
    ])
    plc = No("Plc Logic", "plc", [application])
    filhos_do_device = [No("Cartao_%d" % i, "io") for i in range(cartoes_de_io)]
    filhos_do_device.append(plc)
    device = No("Device", "device", filhos_do_device)
    return No("projeto", "projeto", [No("Project Settings", "cfg"), device])


def _selector(**kwargs):
    base = dict(name="Application", type_guid=APPLICATION_GUID,
                ancestor_names=("Device", "Plc Logic"))
    base.update(kwargs)
    return sel.SemanticSelector(**base)


# =============================================================================
# o caso que motiva a fase
# =============================================================================

def test_resolve_o_application_na_arvore_sem_cartoes():
    resultado = sel.select_node(_arvore(), _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_RESOLVED
    assert resultado.resolved is True
    assert resultado.node is not None
    assert resultado.candidates[0].node_path == "root/1/0/0"


@pytest.mark.parametrize("cartoes", [1, 2, 5])
def test_cartao_de_io_desloca_o_node_path_e_o_seletor_continua_resolvendo(cartoes):
    """A tese inteira da R0b, como teste.

    Com cartões de I/O sob o `Device`, `root/1/0/0` deixa de apontar para o
    `Application` — e a seleção semântica acha o mesmo nó, agora em outro
    caminho. O `node_path` do resultado MUDA, prova de que ele é diagnóstico e
    não identidade.
    """
    resultado = sel.select_node(_arvore(cartoes_de_io=cartoes), _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_RESOLVED
    assert resultado.node.nome == "Application"
    assert resultado.candidates[0].node_path == "root/1/%d/0" % cartoes
    assert resultado.candidates[0].node_path != "root/1/0/0"


def test_o_node_path_posicional_apontaria_para_o_no_errado():
    """A contraprova: descer `root/1/0/0` por índice, na árvore com cartão,
    chega no cartão. Sem este teste, o teste acima provaria apenas que o
    seletor funciona — não que ele resolve um problema real."""
    raiz = _arvore(cartoes_de_io=1)
    atual = raiz
    for indice in (1, 0):
        atual = _filhos(atual)[indice]
    # `root/1/0` já não é o `Plc Logic`: é o cartão.
    assert atual.nome == "Cartao_0"
    # E o quarto segmento do caminho medido nem existe mais — descer
    # `root/1/0/0` levanta, em vez de devolver o nó errado em silêncio. As
    # duas falhas são possíveis; qual delas acontece depende de quantos
    # cartões o operador acrescentou, o que é precisamente o problema.
    assert _filhos(atual) == []
    with pytest.raises(IndexError):
        _filhos(atual)[0]


# =============================================================================
# cardinalidade — as duas recusas, que são erros DIFERENTES
# =============================================================================

def test_zero_alvos_e_no_match():
    resultado = sel.select_node(_arvore(), _selector(name="Nao_Existe"), VIEW)
    assert resultado.diagnostic == sel.DIAG_NO_MATCH
    assert resultado.node is None
    assert resultado.candidates == ()


def test_dois_alvos_sao_ambiguidade_e_nao_escolha():
    raiz = _arvore()
    segundo = No("Application", APPLICATION_GUID, [])
    # Mesmo nome de camada: a ancestralidade não desempata, e é isso que
    # torna o caso ambíguo de verdade.
    _filhos(raiz)[1].filhos.append(No("Plc Logic", "plc", [segundo]))

    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_AMBIGUOUS
    assert len(resultado.candidates) == 2
    # O ponto: mesmo com candidatos em mãos, `node` não entrega nenhum.
    assert resultado.node is None


def test_candidatos_saem_em_ordem_deterministica():
    raiz = _arvore()
    _filhos(raiz)[1].filhos.append(
        No("Plc Logic 2", "plc", [No("Application", APPLICATION_GUID)]))
    resultado = sel.select_node(raiz, _selector(), VIEW)
    caminhos = [c.node_path for c in resultado.candidates]
    assert caminhos == sorted(caminhos)


def test_cardinalidade_esperada_maior_que_um():
    raiz = No("projeto", "projeto", [
        No("A", POU_GUID), No("B", POU_GUID), No("C", "outro")])
    seletor = sel.SemanticSelector(name="A", type_guid=POU_GUID,
                                   expected_cardinality=2)
    faltando = sel.select_node(raiz, seletor, VIEW)
    assert faltando.diagnostic == sel.DIAG_NO_MATCH

    _filhos(raiz).append(No("A", POU_GUID))
    agora = sel.select_node(raiz, seletor, VIEW)
    assert agora.diagnostic == sel.DIAG_RESOLVED
    # Com cardinalidade 2, `node` continua `None`: não há "o" nó.
    assert agora.node is None
    assert len(agora.candidates) == 2


# =============================================================================
# varredura incompleta — as recusas que um seletor ingênuo chamaria de sucesso
# =============================================================================

def test_orcamento_de_nos_estourado_recusa_mesmo_com_um_candidato_achado():
    """A recusa mais sutil do módulo.

    O alvo foi encontrado, e mesmo assim o veredito é recusa: com parte da
    árvore não varrida, "existe exatamente um" é afirmação sem suporte. O
    segundo alvo pode estar no pedaço que não foi lido.
    """
    raiz = _arvore()
    resultado = sel.select_node(raiz, _selector(max_nodes=4), VIEW)
    assert resultado.diagnostic == sel.DIAG_BUDGET_EXCEEDED
    assert resultado.node is None
    assert resultado.visited == 4


def test_profundidade_maxima_com_filhos_nao_varridos_recusa():
    resultado = sel.select_node(_arvore(), _selector(max_depth=2), VIEW)
    assert resultado.diagnostic == sel.DIAG_BUDGET_EXCEEDED
    assert any("profundidade" in p for p in resultado.problems)


def test_profundidade_maxima_em_folha_nao_e_recusa():
    """O fundo declarado só é problema quando há subárvore não lida. Uma folha
    no limite foi varrida por inteiro."""
    raiz = No("projeto", "projeto", [No("Application", APPLICATION_GUID)])
    seletor = sel.SemanticSelector(name="Application", type_guid=APPLICATION_GUID,
                                   max_depth=1)
    resultado = sel.select_node(raiz, seletor, VIEW)
    assert resultado.diagnostic == sel.DIAG_RESOLVED


def test_teto_de_filhos_excedido_recusa():
    muitos = [No("filho_%d" % i, "x") for i in range(10)]
    raiz = No("projeto", "projeto", muitos + [No("Application", APPLICATION_GUID)])
    seletor = sel.SemanticSelector(name="Application", type_guid=APPLICATION_GUID,
                                   max_children=5)
    resultado = sel.select_node(raiz, seletor, VIEW)
    assert resultado.diagnostic == sel.DIAG_BUDGET_EXCEEDED


def test_nome_ilegivel_recusa_mesmo_com_o_alvo_encontrado():
    raiz = _arvore()
    _filhos(raiz)[0].nome = No.ILEGIVEL
    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_UNREADABLE
    assert resultado.unreadable == 1
    assert resultado.node is None
    # O candidato continua sendo reportado -- recusar não é esconder.
    assert len(resultado.candidates) == 1


def test_filhos_ilegiveis_recusam_porque_escondem_uma_subarvore():
    raiz = _arvore()
    _filhos(raiz)[0].filhos = No.ILEGIVEL
    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_UNREADABLE
    assert any("subárvore" in p for p in resultado.problems)


def test_type_guid_ilegivel_recusa():
    raiz = _arvore()
    _filhos(raiz)[0].tipo = No.ILEGIVEL
    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_UNREADABLE


def test_ilegibilidade_vence_estouro_de_orcamento():
    """Ordem das recusas: as duas descrevem varredura incompleta, e a mensagem
    tem de nomear a causa que o operador consegue investigar primeiro."""
    raiz = _arvore()
    _filhos(raiz)[0].nome = No.ILEGIVEL
    resultado = sel.select_node(raiz, _selector(max_nodes=3), VIEW)
    assert resultado.diagnostic == sel.DIAG_UNREADABLE


# =============================================================================
# a regra de casamento, isolada
# =============================================================================

def test_nome_diferente_nao_casa():
    assert not sel.matches(_selector(), "Outro", APPLICATION_GUID,
                           ("Device", "Plc Logic"))


def test_type_guid_diferente_nao_casa():
    assert not sel.matches(_selector(), "Application", POU_GUID,
                           ("Device", "Plc Logic"))


def test_type_guid_compara_sem_caixa():
    assert sel.matches(_selector(), "Application", APPLICATION_GUID.upper(),
                       ("Device", "Plc Logic"))


def test_selector_sem_type_guid_casa_so_por_nome_e_ancestralidade():
    seletor = _selector(type_guid=None)
    assert sel.matches(seletor, "Application", None, ("Device", "Plc Logic"))


def test_type_guid_ausente_no_no_nao_casa_quando_o_seletor_exige():
    assert not sel.matches(_selector(), "Application", None,
                           ("Device", "Plc Logic"))


def test_ancestralidade_e_subsequencia_nao_caminho_contiguo():
    """Um nível intermediário a mais não invalida o seletor — exigir
    contiguidade reintroduziria a suposição posicional que esta fase remove."""
    assert sel.matches(_selector(), "Application", APPLICATION_GUID,
                       ("Device", "Camada Nova", "Plc Logic"))


def test_ancestralidade_fora_de_ordem_nao_casa():
    assert not sel.matches(_selector(), "Application", APPLICATION_GUID,
                           ("Plc Logic", "Device"))


def test_ancestralidade_incompleta_nao_casa():
    assert not sel.matches(_selector(), "Application", APPLICATION_GUID,
                           ("Device",))


def test_ancestralidade_e_conferida_na_arvore_inteira():
    """Dois nós de mesmo nome e tipo, um deles fora da ancestralidade pedida:
    a ancestralidade é o que desempata, e o resultado é resolvido."""
    raiz = No("projeto", "projeto", [
        No("Outra Coisa", "x", [No("Application", APPLICATION_GUID)]),
        No("Device", "device", [
            No("Plc Logic", "plc", [No("Application", APPLICATION_GUID)])]),
    ])
    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_RESOLVED
    assert resultado.candidates[0].node_path == "root/1/0/0"


# =============================================================================
# parsing declarativo
# =============================================================================

def test_parse_selector_minimo():
    seletor, problemas = sel.parse_selector({"name": "Application"})
    assert problemas == []
    assert seletor.name == "Application"
    assert seletor.type_guid is None
    assert seletor.expected_cardinality == 1
    assert seletor.max_depth == sel.DEFAULT_MAX_DEPTH


def test_parse_selector_completo():
    seletor, problemas = sel.parse_selector({
        "name": "Application",
        "type_guid": APPLICATION_GUID,
        "ancestor_names": ["Device", "Plc Logic"],
        "expected_cardinality": 1,
        "max_depth": 6, "max_nodes": 100, "max_children": 32,
    })
    assert problemas == []
    assert seletor.ancestor_names == ("Device", "Plc Logic")
    assert seletor.max_nodes == 100


def test_campo_desconhecido_reprova():
    """`typeguid` sem underscore seria lido como "seletor sem type_guid" e
    passaria a casar só por nome — uma seleção mais fraca do que a pedida,
    aceita em silêncio."""
    seletor, problemas = sel.parse_selector({"name": "A", "typeguid": "x"})
    assert seletor is None
    assert any("desconhecido" in p for p in problemas)


def test_type_guid_malformado_reprova():
    seletor, problemas = sel.parse_selector({"name": "A", "type_guid": "nao-guid"})
    assert seletor is None
    assert any("type_guid" in p for p in problemas)


def test_type_guid_string_vazia_reprova():
    """String vazia não é "sem GUID": é um GUID que ninguém mediu."""
    seletor, problemas = sel.parse_selector({"name": "A", "type_guid": ""})
    assert seletor is None


@pytest.mark.parametrize("cardinalidade", [0, -1, True, 1.0, "1"])
def test_cardinalidade_invalida_reprova(cardinalidade):
    seletor, problemas = sel.parse_selector(
        {"name": "A", "expected_cardinality": cardinalidade})
    assert seletor is None
    assert any("expected_cardinality" in p for p in problemas)


@pytest.mark.parametrize("entrada", [None, [], "Application", 3, True])
def test_entrada_degenerada_nao_levanta(entrada):
    seletor, problemas = sel.parse_selector(entrada)
    assert seletor is None
    assert problemas


def test_nome_vazio_reprova():
    seletor, problemas = sel.parse_selector({"name": "   "})
    assert seletor is None


def test_ancestor_names_com_item_nao_string_reprova():
    seletor, problemas = sel.parse_selector(
        {"name": "A", "ancestor_names": ["Device", 7]})
    assert seletor is None


def test_vocabulario_de_diagnostico_e_fechado_e_sem_repeticao():
    assert len(set(sel.SELECTOR_DIAGNOSTICS)) == len(sel.SELECTOR_DIAGNOSTICS)
    assert set(sel.SELECTOR_DIAGNOSTICS) == {
        sel.DIAG_RESOLVED, sel.DIAG_NO_MATCH, sel.DIAG_AMBIGUOUS,
        sel.DIAG_INVALID, sel.DIAG_BUDGET_EXCEEDED, sel.DIAG_UNREADABLE,
    }


def test_todo_resultado_carrega_diagnostico_do_vocabulario():
    raiz = _arvore()
    for seletor in (_selector(), _selector(name="X"), _selector(max_nodes=2)):
        resultado = sel.select_node(raiz, seletor, VIEW)
        assert resultado.diagnostic in sel.SELECTOR_DIAGNOSTICS
        assert resultado.message


# =============================================================================
# a raiz é o PROJETO -- achado do piloto de 2026-08-02
# =============================================================================

def test_raiz_sem_nome_legivel_nao_impede_a_selecao():
    """`ScriptProject` não expõe `get_name`.

    A primeira versão deste módulo lia o nome de TODO nó, inclusive da raiz, e
    o `AttributeError` do projeto virava "1 nó ilegível" — recusa nas três
    runs do piloto, antes de qualquer escrita. Ler nome de um projeto é erro
    de categoria, não evidência de árvore ilegível.
    """
    raiz = _arvore()
    raiz.nome = No.ILEGIVEL      # como o `ScriptProject` real se comporta
    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_RESOLVED
    assert resultado.unreadable == 0
    assert resultado.node.nome == "Application"


def test_a_raiz_nunca_e_candidata_mesmo_com_nome_e_tipo_certos():
    """Se a raiz casasse, um projeto chamado `Application` seria escolhido
    como container de si mesmo."""
    raiz = No("Application", APPLICATION_GUID, [
        No("Device", "device", [
            No("Plc Logic", "plc", [No("Application", APPLICATION_GUID)])])])
    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_RESOLVED
    assert resultado.candidates[0].node_path == "root/0/0/0"


def test_filhos_ilegiveis_NA_RAIZ_continuam_reprovando():
    """A exceção é só para o nome da raiz. Se a subárvore inteira não pode ser
    lida, a varredura não sustenta nada — e isso não afrouxou."""
    raiz = _arvore()
    raiz.nome = No.ILEGIVEL
    raiz.filhos = No.ILEGIVEL
    resultado = sel.select_node(raiz, _selector(), VIEW)
    assert resultado.diagnostic == sel.DIAG_UNREADABLE
    assert resultado.node is None
