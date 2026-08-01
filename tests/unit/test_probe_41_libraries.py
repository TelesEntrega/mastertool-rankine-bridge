"""Testes de `probes/41_inventory_libraries_readonly.py`, com dubles ESTRITOS
e verificacao estatica por RECEPTOR.

O perigo deste probe nao e igual ao do probe 36. La o mutador irmao morava num
tipo vizinho; aqui os TRES mutadores de biblioteca moram no MESMO objeto e na
MESMA interface que a leitura (stub oficial `ScriptLibManObject.pyi`, linhas
413-462). Nao existe fronteira de tipo protegendo ninguem, entao a fronteira
tem de ser verificada:

* os dubles LEVANTAM se qualquer membro fora da lista de leitura for tocado --
  inclusive os mutadores, que assim nao podem passar despercebidos;
* a analise de AST e por RECEPTOR e por MAPA CONGELADO, nao por lista de nomes
  proibidos: uma chamada nova sobre um proxy do MasterTool derruba o teste
  tenha ela o nome que tiver, o que cobre tambem os mutadores que ninguem
  lembrou de listar;
* o fonte nao pode sequer MENCIONAR os nomes mutadores, porque a distancia
  entre ler e escrever aqui e uma linha copiada de lugar errado.

O wrapper `run_inventory_libraries.ps1` e verificado por texto: ASCII puro, sem
`--noUI`, sem matar processo, gravando JSON sem BOM, e recusando a sessao se um
nome mutador aparecer no fonte do probe.
"""

import ast
import io
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

PROBE41_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "41_inventory_libraries_readonly.py")
WRAPPER_PATH = os.path.join(_MASTERTOOL_DIR, "run_inventory_libraries.ps1")

# Os nomes que alteram bibliotecas ou CRIAM o gerenciador. Vivem aqui, no
# teste, e em lugar nenhum do probe -- e essa e a ideia.
NOMES_MUTADORES = (
    "add_library", "add_placeholder", "remove_library", "get_library_manager",
    "install_library", "uninstall_library", "set_redirection",
    "insert_repository", "remove_repository", "update_repository",
    "move_repository", "download_missing_libraries",
)


def _load_module(path, name):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                            # IronPython 2.7
        import imp
        return imp.load_source(name, path)


probe41 = _load_module(PROBE41_PATH, "probe41_inventory_libraries")


# =============================================================================
# Dubles ESTRITOS -- qualquer acesso fora da leitura medida LEVANTA
# =============================================================================

class _Estrito(object):
    """Base dos dubles: tudo o que nao for declarado explicitamente levanta.

    `__getattr__` so e chamado quando a busca normal falha, entao propriedades
    e metodos declarados nas subclasses continuam funcionando -- e QUALQUER
    outro nome, inclusive os tres mutadores de biblioteca, vira falha de teste
    com o nome do membro tocado.
    """

    _ROTULO = "objeto"

    def __getattr__(self, nome):
        raise AssertionError(
            "probe 41 tocou %r em %s -- fora da leitura medida" % (nome, self._ROTULO))


class ColecaoEstrita(_Estrito):
    """Colecao CLR de filhos: so `Count` e indexador, como o scanner ja usa."""

    _ROTULO = "colecao de filhos"

    def __init__(self, itens, count=None, erro_indice=None):
        self._itens = list(itens)
        self.Count = len(self._itens) if count is None else count
        self._erro_indice = erro_indice

    def __getitem__(self, indice):
        if self._erro_indice is not None:
            raise self._erro_indice
        return self._itens[indice]


class ReferenciaEstrita(_Estrito):
    """Uma `ScriptLibraryReference`: os CINCO campos do contrato e nada mais.

    `parameters` e a leitura de dependencias ficam de fora de proposito -- o
    stub avisa (linha 580) que dependencia ciclica leva a recursao infinita, e
    o probe nao pode toca-la. Se um dia tocar, este duble levanta.
    """

    _ROTULO = "referencia de biblioteca"

    def __init__(self, name=None, namespace=None, is_placeholder=False,
                 is_managed=True, system_library=False, erros=None):
        self._valores = {
            "name": name, "namespace": namespace,
            "is_placeholder": is_placeholder, "is_managed": is_managed,
            "system_library": system_library,
        }
        self._erros = erros or {}
        self.lidos = []

    def _ler(self, campo):
        self.lidos.append(campo)
        if campo in self._erros:
            raise self._erros[campo]
        return self._valores[campo]

    @property
    def name(self):
        return self._ler("name")

    @property
    def namespace(self):
        return self._ler("namespace")

    @property
    def is_placeholder(self):
        return self._ler("is_placeholder")

    @property
    def is_managed(self):
        return self._ler("is_managed")

    @property
    def system_library(self):
        return self._ler("system_library")


class ReferenciasEstritas(_Estrito):
    """`ScriptLibraryReferences`: so `__len__` e indexador por inteiro."""

    _ROTULO = "colecao de referencias"

    def __init__(self, itens, erro_len=None, erro_indice=None):
        self._itens = list(itens)
        self._erro_len = erro_len
        self._erro_indice = erro_indice

    def __len__(self):
        if self._erro_len is not None:
            raise self._erro_len
        return len(self._itens)

    def __getitem__(self, indice):
        if self._erro_indice is not None:
            raise self._erro_indice
        return self._itens[indice]


class NoEstrito(_Estrito):
    """No qualquer da arvore: `is_libman`, `get_name`, `get_children`."""

    _ROTULO = "no da arvore"

    def __init__(self, nome="no", filhos=None, is_libman=False,
                 erro_is_libman=None, erro_children=None):
        self._nome = nome
        self._filhos = list(filhos or [])
        self._is_libman = is_libman
        self._erro_is_libman = erro_is_libman
        self._erro_children = erro_children

    @property
    def is_libman(self):
        if self._erro_is_libman is not None:
            raise self._erro_is_libman
        return self._is_libman

    def get_name(self, recursivo):
        assert recursivo is False
        return self._nome

    def get_children(self, recursivo):
        assert recursivo is False
        if self._erro_children is not None:
            raise self._erro_children
        return ColecaoEstrita(self._filhos)


class LibmanEstrito(NoEstrito):
    """O no do library manager: alem do no comum, `references` e
    `get_libraries`. Qualquer outro membro -- e os mutadores sao os outros
    membros mais provaveis -- levanta pelo `__getattr__` da base."""

    _ROTULO = "no de library manager"

    def __init__(self, referencias=None, nomes_simples=None, nome="LibMan",
                 filhos=None, erro_references=None, erro_get_libraries=None,
                 references_none=False, simples_none=False):
        NoEstrito.__init__(self, nome=nome, filhos=filhos, is_libman=True)
        self._referencias = referencias
        self._nomes_simples = nomes_simples
        self._erro_references = erro_references
        self._erro_get_libraries = erro_get_libraries
        self._references_none = references_none
        self._simples_none = simples_none
        self.chamadas_get_libraries = []

    @property
    def references(self):
        if self._erro_references is not None:
            raise self._erro_references
        if self._references_none:
            return None
        return ReferenciasEstritas(self._referencias or [])

    def get_libraries(self, recursive):
        self.chamadas_get_libraries.append(recursive)
        if self._erro_get_libraries is not None:
            raise self._erro_get_libraries
        if self._simples_none:
            return None
        return list(self._nomes_simples or [])


class ProjetoEstrito(_Estrito):
    """Projeto: `get_children` e `path`. NAO expoe `is_libman` de proposito --
    se o probe tentasse marcar a propria raiz, este duble levantaria."""

    _ROTULO = "projeto"

    def __init__(self, filhos=None, path="C:/w/proj.project", erro_children=None):
        self._filhos = list(filhos or [])
        self.path = path
        self._erro_children = erro_children

    def get_children(self, recursivo):
        assert recursivo is False
        if self._erro_children is not None:
            raise self._erro_children
        return ColecaoEstrita(self._filhos)


def _projeto_com_libman(libman, profundidade=3):
    """Enterra o libman alguns niveis, para que a varredura tenha de descer."""
    no = libman
    for indice in range(profundidade):
        no = NoEstrito(nome="nivel%d" % indice, filhos=[no])
    return ProjetoEstrito(filhos=[NoEstrito(nome="irmao"), no])


def _referencia_padrao():
    return ReferenciaEstrita(name="Standard, 3.5.17.0 (System)",
                             namespace="Standard", is_placeholder=False,
                             is_managed=True, system_library=True)


# =============================================================================
# O duble e mesmo um alarme? (falsificacao permanente)
# =============================================================================

@pytest.mark.parametrize("mutador", NOMES_MUTADORES)
def test_o_duble_levanta_se_um_mutador_for_tocado(mutador):
    """Prova que o duble e um alarme e nao um enfeite. Se um dia
    `LibmanEstrito` ganhar um `__getattr__` permissivo, este teste cai antes de
    qualquer outro -- e sem ele, "o duble levantaria" seria so uma frase de
    docstring."""
    libman = LibmanEstrito(referencias=[_referencia_padrao()])
    with pytest.raises(AssertionError) as capturado:
        getattr(libman, mutador)
    assert mutador in str(capturado.value)


def test_o_duble_de_referencia_levanta_em_membro_de_dependencia():
    ref = _referencia_padrao()
    with pytest.raises(AssertionError):
        getattr(ref, "get_dependencies")
    with pytest.raises(AssertionError):
        getattr(ref, "parameters")


# =============================================================================
# As cadeias e a fonte -- o stub tem de continuar sendo citado com precisao
# =============================================================================

def test_a_fonte_e_o_stub_oficial_com_arquivo_e_linhas():
    """A fonte nao pode ser "a documentacao diz": tem de nomear o arquivo e as
    linhas, para que outra pessoa abra o stub e confira."""
    assert probe41.STUB_PATH.endswith("ScriptLibManObject.pyi")
    assert "MT9000 4.1.0" in probe41.STUB_PATH
    assert "376-391" in probe41.MARKER_CHAIN_SOURCE
    assert "is_libman" in probe41.MARKER_CHAIN_SOURCE
    assert "401-411" in probe41.ROUTE_SIMPLE_SOURCE
    assert "464-473" in probe41.ROUTE_RICH_SOURCE
    assert "509-575" in probe41.ROUTE_RICH_SOURCE
    for fonte in (probe41.MARKER_CHAIN_SOURCE, probe41.ROUTE_SIMPLE_SOURCE,
                  probe41.ROUTE_RICH_SOURCE):
        assert probe41.STUB_PATH in fonte


def test_o_booleano_de_get_libraries_tem_nome_e_significado():
    """Nos metadados do ScriptEngine3.dll o parametro e um `Boolean` SEM NOME.
    Um booleano sem nome so pode ser chutado; o stub o nomeia `recursive` e diz
    o que ele faz. A constante do probe tem de carregar as duas coisas."""
    assert probe41.GET_LIBRARIES_RECURSIVE is False
    assert "recursive" in probe41.ROUTE_SIMPLE_CHAIN
    assert "recursive" in probe41.ROUTE_SIMPLE_SOURCE
    assert "sublibraries" in probe41.ROUTE_SIMPLE_SOURCE
    assert "SEM NOME" in probe41.ROUTE_SIMPLE_SOURCE
    assert "recursive=False" in probe41.GET_LIBRARIES_RECURSIVE_RATIONALE


def test_a_rota_rica_declara_os_cinco_campos_do_contrato():
    for campo in ("name", "namespace", "is_placeholder", "is_managed",
                  "system_library"):
        assert campo in probe41.ROUTE_RICH_CHAIN


# =============================================================================
# nucleo puro
# =============================================================================

def test_evidencia_medida_exige_valor():
    ev = probe41.build_evidence([{"name": "Standard"}], "fonte", None)
    assert ev["status"] == probe41.EVIDENCE_MEASURED
    assert ev["reason"] is None
    assert ev["source"] == "fonte"


def test_evidencia_lacuna_exige_valor_nulo_e_razao():
    ev = probe41.build_evidence(None, "fonte", "razao escrita")
    assert ev["status"] == probe41.EVIDENCE_UNRESOLVED
    assert ev["value"] is None
    assert ev["reason"] == "razao escrita"


def test_lacuna_sem_razao_ainda_tem_razao():
    assert probe41.build_evidence(None, "fonte", None)["reason"]


@pytest.mark.parametrize("nome,versao,empresa", [
    ("Standard, 3.5.17.0 (System)", "3.5.17.0", "System"),
    ("Util, 4.1.0.0 (Altus S.A.)", "4.1.0.0", "Altus S.A."),
    ("  IoStandard, 3.5.16.0 (System)  ", "3.5.16.0", "System"),
])
def test_versao_derivada_do_padrao_de_nome(nome, versao, empresa):
    assert probe41.parse_version_from_name(nome) == (versao, empresa)


@pytest.mark.parametrize("nome", [
    None, "", "   ", "#Placeholder", "SemVirgula (System)",
    "Nome, naoversao (System)", "Nome, 3.5 sem parenteses",
])
def test_nome_fora_do_padrao_nao_produz_versao_inventada(nome):
    """Placeholder ("#Name") e referencia nao gerenciada NAO trazem versao no
    nome. Devolver algo aqui seria inventar o dado que o probe existe para
    medir."""
    assert probe41.parse_version_from_name(nome) == (None, None)


def test_entrada_de_biblioteca_marca_versao_como_derivada():
    entrada = probe41.build_library_entry(
        "root/1/0/0/0", "Standard, 3.5.17.0 (System)", "Standard",
        False, True, True, {})
    assert entrada["name"] == "Standard, 3.5.17.0 (System)"
    assert entrada["namespace"] == "Standard"
    assert entrada["version"]["status"] == probe41.EVIDENCE_MEASURED
    assert entrada["version"]["value"] == "3.5.17.0"
    assert "DERIVACAO" in entrada["version"]["source"]
    assert entrada["is_placeholder"] is False
    assert entrada["system_library"] is True


def test_entrada_de_placeholder_declara_versao_como_lacuna():
    entrada = probe41.build_library_entry(
        "root/0", "#PlaceholderQualquer", "PH", True, False, False, {})
    assert entrada["version"]["status"] == probe41.EVIDENCE_UNRESOLVED
    assert entrada["version"]["value"] is None
    assert entrada["version"]["reason"] == probe41.REASON_VERSION_NOT_IN_NAME


def test_confronto_de_rotas_detecta_discordancia():
    resultado = probe41.compare_routes(["A", "B"], ["A", "C"], True, True)
    assert resultado["agree"] is False
    assert resultado["only_in_rich"] == ["B"]
    assert resultado["only_in_simple"] == ["C"]


def test_confronto_nao_afirma_concordancia_quando_uma_rota_falhou():
    """`agree` fica None, nunca True: duas leituras das quais so uma aconteceu
    nao concordam -- nao ha com o que concordar."""
    resultado = probe41.compare_routes(["A"], [], True, False)
    assert resultado["agree"] is None
    assert resultado["rich_route_ok"] is True
    assert resultado["simple_route_ok"] is False


def test_classify_deriva_status_da_evidencia_e_da_conferencia():
    medida = probe41.build_evidence([{"name": "A"}], "f", None)
    lacuna = probe41.build_evidence(None, "f", "razao")
    assert probe41.classify(medida, {"simple_route_ok": True}) == probe41.STATUS_MEASURED
    assert probe41.classify(medida, {"simple_route_ok": False}) == probe41.STATUS_PARTIAL
    assert probe41.classify(lacuna, {"simple_route_ok": True}) == probe41.STATUS_UNRESOLVED
    assert probe41.classify(None, {}) == probe41.STATUS_UNRESOLVED


# =============================================================================
# varredura pelo marcador -- por TIPO, nunca por nome
# =============================================================================

def test_encontra_o_libman_pelo_marcador_e_nao_pelo_nome():
    libman = LibmanEstrito(referencias=[_referencia_padrao()],
                           nome="Gerenciador de Bibliotecas")
    achados, varredura = probe41.collect_libman_nodes(_projeto_com_libman(libman))
    assert [a["node_id"] for a in achados] == ["root/1/0/0/0"]
    assert achados[0]["name"] == "Gerenciador de Bibliotecas"
    assert achados[0]["node"] is libman
    assert varredura["errors"] == []
    assert varredura["truncated"] is False


def test_varredura_sem_no_marcado_nao_inventa_nenhum():
    achados, varredura = probe41.collect_libman_nodes(
        ProjetoEstrito(filhos=[NoEstrito(nome="a"), NoEstrito(nome="b")]))
    assert achados == []
    assert varredura["visited"] == 3


def test_erro_de_marcador_num_no_nao_derruba_a_varredura():
    libman = LibmanEstrito(referencias=[_referencia_padrao()])
    projeto = ProjetoEstrito(filhos=[
        NoEstrito(nome="ruim", erro_is_libman=RuntimeError("sem membro")),
        libman])
    achados, varredura = probe41.collect_libman_nodes(projeto)
    assert [a["node_id"] for a in achados] == ["root/1"]
    assert any("sem membro" in e for e in varredura["errors"])


def test_erro_de_filhos_num_ramo_nao_derruba_a_varredura():
    libman = LibmanEstrito(referencias=[_referencia_padrao()])
    projeto = ProjetoEstrito(filhos=[
        NoEstrito(nome="ruim", erro_children=RuntimeError("colecao morreu")),
        libman])
    achados, varredura = probe41.collect_libman_nodes(projeto)
    assert [a["node_id"] for a in achados] == ["root/1"]
    assert any("colecao morreu" in e for e in varredura["errors"])


def test_profundidade_limitada_nao_desce_para_sempre():
    libman = LibmanEstrito(referencias=[_referencia_padrao()])
    fundo = _projeto_com_libman(libman, profundidade=probe41.MAX_DEPTH + 3)
    achados, _ = probe41.collect_libman_nodes(fundo)
    assert achados == []


def test_sem_projeto_a_varredura_registra_o_motivo_e_nao_levanta():
    achados, varredura = probe41.collect_libman_nodes(None)
    assert achados == []
    assert probe41.REASON_NO_PROJECT in varredura["errors"]


# =============================================================================
# as duas rotas
# =============================================================================

def test_rota_simples_chama_get_libraries_uma_vez_com_recursive_false():
    libman = LibmanEstrito(nomes_simples=["Standard, 3.5.17.0 (System)"])
    resultado = probe41.read_route_simple(libman)
    assert resultado["ok"] is True
    assert resultado["names"] == ["Standard, 3.5.17.0 (System)"]
    # UMA chamada, com o booleano NOMEADO pelo stub e valor False.
    assert libman.chamadas_get_libraries == [False]


def test_rota_simples_falha_vira_erro_escrito_e_nao_segunda_tentativa():
    libman = LibmanEstrito(erro_get_libraries=RuntimeError("boom"))
    resultado = probe41.read_route_simple(libman)
    assert resultado["ok"] is False
    assert probe41.REASON_SIMPLE_ROUTE_FAILED in resultado["error"]
    assert "boom" in resultado["error"]
    assert libman.chamadas_get_libraries == [False]


def test_rota_simples_com_none_e_lacuna():
    resultado = probe41.read_route_simple(LibmanEstrito(simples_none=True))
    assert resultado["ok"] is False
    assert "devolveu None" in resultado["error"]


def test_rota_rica_le_os_cinco_campos_de_cada_referencia():
    referencia = _referencia_padrao()
    libman = LibmanEstrito(referencias=[referencia])
    resultado = probe41.read_route_rich(libman, "root/1/0/0/0")
    assert resultado["ok"] is True
    assert resultado["count"] == 1
    entrada = resultado["libraries"][0]
    assert entrada["libman_node_id"] == "root/1/0/0/0"
    assert entrada["namespace"] == "Standard"
    assert entrada["is_managed"] is True
    assert entrada["system_library"] is True
    assert entrada["version"]["value"] == "3.5.17.0"
    assert entrada["field_errors"] == {}
    assert sorted(referencia.lidos) == [
        "is_managed", "is_placeholder", "name", "namespace", "system_library"]


def test_campo_que_falha_nao_leva_junto_os_outros_quatro():
    referencia = ReferenciaEstrita(
        name="Standard, 3.5.17.0 (System)", namespace="Standard",
        erros={"system_library": RuntimeError("propriedade ausente")})
    resultado = probe41.read_route_rich(LibmanEstrito(referencias=[referencia]),
                                        "root/0")
    entrada = resultado["libraries"][0]
    assert resultado["ok"] is True
    assert entrada["name"] == "Standard, 3.5.17.0 (System)"
    assert entrada["system_library"] is None
    assert "propriedade ausente" in entrada["field_errors"]["system_library"]


def test_rota_rica_falha_vira_erro_escrito():
    libman = LibmanEstrito(erro_references=RuntimeError("sem references"))
    resultado = probe41.read_route_rich(libman, "root/0")
    assert resultado["ok"] is False
    assert probe41.REASON_RICH_ROUTE_FAILED in resultado["error"]
    assert "sem references" in resultado["error"]


def test_rota_rica_com_none_e_lacuna():
    resultado = probe41.read_route_rich(LibmanEstrito(references_none=True),
                                        "root/0")
    assert resultado["ok"] is False
    assert "devolveu None" in resultado["error"]


# =============================================================================
# read_inventory -- as duas rotas juntas, e o que cada falha significa
# =============================================================================

def _libman_completo():
    return LibmanEstrito(
        referencias=[
            ReferenciaEstrita(name="Standard, 3.5.17.0 (System)",
                              namespace="Standard", system_library=True),
            ReferenciaEstrita(name="#Placeholder", namespace="PH",
                              is_placeholder=True, is_managed=False),
        ],
        nomes_simples=["Standard, 3.5.17.0 (System)", "#Placeholder"])


def test_inventario_medido_e_conferido_pelas_duas_rotas():
    evidencia, cross_check, detalhe = probe41.read_inventory(
        _projeto_com_libman(_libman_completo()))
    assert evidencia["status"] == probe41.EVIDENCE_MEASURED
    assert len(evidencia["value"]) == 2
    assert cross_check["agree"] is True
    assert cross_check["rich_count"] == 2 and cross_check["simple_count"] == 2
    assert detalhe["libman_nodes"] == [
        {"node_id": "root/1/0/0/0", "name": "LibMan"}]
    assert probe41.classify(evidencia, cross_check) == probe41.STATUS_MEASURED


def test_rota_rica_ok_e_simples_falha_e_partial_e_nao_sucesso():
    libman = LibmanEstrito(referencias=[_referencia_padrao()],
                           erro_get_libraries=RuntimeError("boom"))
    evidencia, cross_check, _ = probe41.read_inventory(
        _projeto_com_libman(libman))
    assert evidencia["status"] == probe41.EVIDENCE_MEASURED
    assert cross_check["simple_route_ok"] is False
    assert probe41.classify(evidencia, cross_check) == probe41.STATUS_PARTIAL


def test_rota_simples_ok_e_rica_falha_nao_e_medida():
    """A metade que importa: nomes sozinhos NAO preenchem o contrato de saida,
    e uma rota nao cobre a outra (docs/36 secao 4)."""
    libman = LibmanEstrito(erro_references=RuntimeError("sem references"),
                           nomes_simples=["Standard, 3.5.17.0 (System)"])
    evidencia, cross_check, _ = probe41.read_inventory(
        _projeto_com_libman(libman))
    assert evidencia["status"] == probe41.EVIDENCE_UNRESOLVED
    assert evidencia["value"] is None
    assert probe41.REASON_RICH_ROUTE_FAILED in evidencia["reason"]
    assert probe41.REASON_ONLY_SIMPLE_ROUTE in evidencia["reason"]
    assert cross_check["simple_route_ok"] is True


def test_zero_referencias_nao_vira_medida():
    """O precedente e a run-011 (docs/36): o no foi alcancado e devolveu zero.
    Lista vazia le como "medido: nenhuma biblioteca"; o que se tem e "nao
    mensuravel por este caminho". Sao conclusoes opostas."""
    libman = LibmanEstrito(referencias=[], nomes_simples=[])
    evidencia, _, _ = probe41.read_inventory(_projeto_com_libman(libman))
    assert evidencia["status"] == probe41.EVIDENCE_UNRESOLVED
    assert evidencia["value"] is None
    assert "run-011" in evidencia["reason"]


def test_sem_no_marcado_a_lacuna_nomeia_o_elo():
    evidencia, _, detalhe = probe41.read_inventory(
        ProjetoEstrito(filhos=[NoEstrito(nome="a")]))
    assert evidencia["status"] == probe41.EVIDENCE_UNRESOLVED
    assert evidencia["reason"] == probe41.REASON_NO_LIBMAN_NODE
    assert detalhe["libman_nodes"] == []


def test_dois_nos_marcados_produzem_inventario_agregado_e_rastreavel():
    """Projeto e aplicacao podem ter gerenciadores distintos. Cada linha diz de
    qual no veio -- somar sem dizer de onde apagaria a diferenca."""
    libman_a = LibmanEstrito(
        referencias=[ReferenciaEstrita(name="A, 1.0.0.0 (X)", namespace="A")],
        nomes_simples=["A, 1.0.0.0 (X)"], nome="LibManA")
    libman_b = LibmanEstrito(
        referencias=[ReferenciaEstrita(name="B, 2.0.0.0 (X)", namespace="B")],
        nomes_simples=["B, 2.0.0.0 (X)"], nome="LibManB")
    projeto = ProjetoEstrito(filhos=[libman_a, libman_b])
    evidencia, cross_check, detalhe = probe41.read_inventory(projeto)
    assert evidencia["status"] == probe41.EVIDENCE_MEASURED
    assert [b["libman_node_id"] for b in evidencia["value"]] == ["root/0", "root/1"]
    assert cross_check["agree"] is True
    assert len(detalhe["routes"]) == 2


# =============================================================================
# run_probe -- orquestracao, com dubles de io/cli
# =============================================================================

class ProbeCliFalso(object):
    def __init__(self, output="C:/fora/artefatos"):
        self._output = output

    def find_arg(self, argv, name):
        return self._output if name == "output" else None

    def validate_output_path(self, raw, repo_root, problems):
        if not raw:
            problems.append("--output e obrigatorio")
            return None
        return raw

    def runtime_identity(self):
        return {"file_version": "4.1.0.11"}


class ProjectAccessFalso(object):
    def __init__(self, project, error=None):
        self._project = project
        self._error = error

    def get_primary_project(self, script_globals):
        return self._project, self._error

    def get_project_path(self, project):
        return project.path


class FileIoFalso(object):
    def __init__(self):
        self.json_writes = {}
        self.text_writes = {}

    def iso_now(self):
        return "2026-07-31T00:00:00"

    def ensure_dir(self, path):
        return path

    def write_json(self, path, data):
        self.json_writes[os.path.basename(path)] = data
        return path

    def write_text(self, path, text):
        self.text_writes[os.path.basename(path)] = text
        return path


def test_run_probe_sucesso_grava_os_tres_artefatos():
    projeto = _projeto_com_libman(_libman_completo())
    file_io = FileIoFalso()
    resultado = probe41.run_probe({}, [], ProjectAccessFalso(projeto), file_io,
                                  ProbeCliFalso())
    assert resultado["status"] == probe41.STATUS_MEASURED
    assert resultado["exit_code"] == 0
    assert resultado["problems"] == []
    assert resultado["mutating_calls"] == []

    completion = probe41.build_completion(resultado)
    assert completion["is_success"] is True
    assert completion["libraries_count"] == 2
    assert completion["libraries_names"] == ["Standard, 3.5.17.0 (System)",
                                             "#Placeholder"]
    assert completion["marker_chain"] == probe41.MARKER_CHAIN
    assert completion["route_rich_chain"] == probe41.ROUTE_RICH_CHAIN

    probe41.write_artifacts(resultado, file_io)
    assert "libraries-completion.json" in file_io.json_writes
    assert "libraries-analysis.json" in file_io.json_writes
    assert "libraries-report.md" in file_io.text_writes


def test_run_probe_lacuna_nao_e_sucesso_e_nao_sai_zero():
    projeto = _projeto_com_libman(LibmanEstrito(referencias=[], nomes_simples=[]))
    resultado = probe41.run_probe({}, [], ProjectAccessFalso(projeto),
                                  FileIoFalso(), ProbeCliFalso())
    assert resultado["status"] == probe41.STATUS_UNRESOLVED
    assert resultado["exit_code"] == 2
    assert probe41.build_completion(resultado)["is_success"] is False
    assert resultado["problems"]


def test_run_probe_partial_nao_sai_zero_e_diz_que_faltou_conferencia():
    libman = LibmanEstrito(referencias=[_referencia_padrao()],
                           erro_get_libraries=RuntimeError("boom"))
    resultado = probe41.run_probe({}, [], ProjectAccessFalso(_projeto_com_libman(libman)),
                                  FileIoFalso(), ProbeCliFalso())
    assert resultado["status"] == probe41.STATUS_PARTIAL
    assert resultado["exit_code"] == 4
    assert probe41.build_completion(resultado)["is_success"] is False
    assert any("conferido" in p for p in resultado["problems"])


def test_run_probe_registra_discordancia_entre_rotas():
    libman = LibmanEstrito(
        referencias=[ReferenciaEstrita(name="A, 1.0.0.0 (X)", namespace="A")],
        nomes_simples=["A, 1.0.0.0 (X)", "B, 2.0.0.0 (X)"])
    resultado = probe41.run_probe({}, [], ProjectAccessFalso(_projeto_com_libman(libman)),
                                  FileIoFalso(), ProbeCliFalso())
    assert resultado["cross_check"]["agree"] is False
    assert any("DISCORDAM" in p for p in resultado["problems"])
    assert resultado["status"] == probe41.STATUS_MEASURED


def test_run_probe_sem_output_e_fatal_antes_de_tocar_o_projeto():
    """Se o argumento for recusado, o projeto nem chega a ser acessado -- o
    duble levantaria se fosse tocado."""
    resultado = probe41.run_probe({}, [], ProjectAccessFalso(None, "n/a"),
                                  FileIoFalso(), ProbeCliFalso(output=None))
    assert resultado["status"] == probe41.STATUS_FATAL
    assert resultado["exit_code"] == 1


def test_run_probe_sem_projeto_primario_e_fatal():
    resultado = probe41.run_probe({}, [], ProjectAccessFalso(None, "nada aberto"),
                                  FileIoFalso(), ProbeCliFalso())
    assert resultado["status"] == probe41.STATUS_FATAL
    assert resultado["libraries"]["status"] == probe41.EVIDENCE_UNRESOLVED


def test_relatorio_markdown_mostra_a_lista_junto_das_cadeias():
    projeto = _projeto_com_libman(_libman_completo())
    resultado = probe41.run_probe({}, [], ProjectAccessFalso(projeto),
                                  FileIoFalso(), ProbeCliFalso())
    texto = probe41.build_report_markdown(resultado)
    assert "Standard, 3.5.17.0 (System)" in texto
    assert probe41.MARKER_CHAIN in texto
    assert probe41.ROUTE_RICH_CHAIN in texto
    assert probe41.ROUTE_SIMPLE_CHAIN in texto


def test_exit_codes_cobrem_todos_os_status():
    for status in probe41.ALL_STATUSES:
        assert status in probe41.EXIT_BY_STATUS
    assert probe41.EXIT_BY_STATUS[probe41.STATUS_MEASURED] == 0
    for status in probe41.ALL_STATUSES:
        zero = probe41.EXIT_BY_STATUS[status] == 0
        assert zero == (status in probe41.SUCCESS_STATUSES)


# =============================================================================
# Verificacao estatica (AST) -- probe 41 e SOMENTE LEITURA, por RECEPTOR
# =============================================================================

@pytest.fixture(scope="module")
def tree41():
    return ast.parse(io.open(PROBE41_PATH, encoding="utf-8").read())


def _receptor(no):
    """Rende o receptor de uma chamada como texto estavel.

    E o RECEPTOR que decide se uma chamada e perigosa, nunca o nome do metodo:
    `.append(...)` numa lista Python e inofensivo, e `.remove(...)` num proxy
    do MasterTool apaga objeto do projeto. Proibir NOMES reprovaria codigo
    legitimo e ainda assim deixaria passar o mutador que ninguem listou.
    """
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return _receptor(no.value) + "." + no.attr
    if isinstance(no, ast.Subscript):
        return "<subscript>"
    if isinstance(no, ast.Call):
        return "<call>"
    if isinstance(no, ast.Constant):
        return "<literal>"
    return "<expr>"


def _mapa_de_chamadas(tree):
    mapa = {}
    for no in ast.walk(tree):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            mapa.setdefault(_receptor(no.func.value), set()).add(no.func.attr)
    return dict((k, sorted(v)) for k, v in mapa.items())


# O mapa COMPLETO de "quem chama o que" no probe, congelado. Qualquer chamada
# nova -- inclusive uma que este arquivo nunca imaginou -- muda o mapa e
# derruba o teste. Os UNICOS receptores que sao proxies do MasterTool sao
# `node` e `libman`, e o que eles podem receber esta escrito abaixo.
MAPA_DE_CHAMADAS_CONGELADO = {
    # --- proxies do MasterTool: SOMENTE LEITURA -----------------------------
    "node": ["get_children", "get_name"],
    "libman": ["get_libraries"],
    # --- estruturas Python e modulos proprios ------------------------------
    "<call>": ["strip"],
    "<expr>": ["get"],
    "<literal>": ["join"],
    "<subscript>": ["append"],
    "EXIT_BY_STATUS": ["get"],
    "_MANAGED_NAME_RE": ["match"],
    "achados": ["append"],
    "biblioteca": ["get"],
    "bibliotecas": ["append"],
    # `simples.get("names")` -- dict Python. Entrou quando a rota simples
    # passou a correr ANTES da rica, para lhe fornecer os nomes da indexacao
    # por nome (run-015: a indexacao por posicao levanta NullReference no
    # TemplateExemplo v1). Os DOIS receptores de proxy acima ficaram inalterados, que e o
    # que este mapa existe para vigiar.
    "simples": ["get"],
    "casado": ["group"],
    "cross_check": ["get"],
    "erros": ["append"],
    "evidencia": ["get"],
    "file_io": ["ensure_dir", "write_json", "write_text"],
    "filhos": ["append"],
    "lines": ["append"],
    "no_marcado": ["get"],
    "nomes": ["append"],
    "os.path": ["abspath", "dirname", "join"],
    "passo": ["get"],
    "passos": ["append"],
    "pilha": ["append", "pop"],
    "probe_cli": ["find_arg", "runtime_identity", "validate_output_path"],
    "project_access": ["get_primary_project", "get_project_path"],
    "re": ["compile"],
    "result": ["get"],
    "sys": ["exit"],
    "sys.path": ["insert"],
    "traceback": ["print_exc"],
    "value": ["strip"],
    "versao": ["get"],
    "written": ["append"],
}


def test_mapa_de_chamadas_por_receptor_esta_congelado(tree41):
    assert _mapa_de_chamadas(tree41) == MAPA_DE_CHAMADAS_CONGELADO, (
        "o conjunto de chamadas por receptor mudou. Se a mudanca for legitima, "
        "atualize MAPA_DE_CHAMADAS_CONGELADO -- e leia com atencao a linha de "
        "`node` e a de `libman`, que sao os proxies do MasterTool")


def test_os_proxies_do_mastertool_so_recebem_leitura(tree41):
    """A metade que sobrevive a uma atualizacao do mapa: mesmo que alguem
    acrescente um receptor novo, os dois proxies conhecidos continuam limitados
    a estes tres metodos, que o stub documenta como leitura."""
    mapa = _mapa_de_chamadas(tree41)
    assert mapa["node"] == ["get_children", "get_name"]
    assert mapa["libman"] == ["get_libraries"]


def test_nenhuma_atribuicao_de_atributo_no_probe_inteiro(tree41):
    """`namespace`, `optional`, `qualified_only` e `default_resolution` TEM
    setter no stub. Uma unica atribuicao de atributo escreveria no projeto sem
    chamar metodo nenhum, e passaria por baixo de qualquer guarda que so olhe
    chamadas."""
    escritas = [(no.attr, no.lineno) for no in ast.walk(tree41)
                if isinstance(no, ast.Attribute)
                and isinstance(no.ctx, (ast.Store, ast.Del))]
    assert escritas == []


@pytest.mark.parametrize("membro", ["is_libman", "references", "Count", "name",
                                    "namespace", "is_placeholder", "is_managed",
                                    "system_library", "get_libraries",
                                    "get_children", "get_name"])
def test_cada_membro_do_produto_aparece_uma_unica_vez(tree41, membro):
    """Uma ocorrencia no fonte inteiro. Duas seriam retentativa, cascata de
    acessores ou segunda rota nao declarada -- as tres proibidas por contrato."""
    ocorrencias = [no for no in ast.walk(tree41)
                   if isinstance(no, ast.Attribute) and no.attr == membro]
    assert len(ocorrencias) == 1


MUTADORES_PROIBIDOS = (
    "create_gvl", "create_pou", "create_program", "create_folder", "create_dut",
    "create_function", "create_function_block", "create_interface",
    "create_persistentvars", "create_task", "create_task_configuration",
    "create_boot_application", "replace", "replace_line", "insert", "remove",
    "save", "save_as", "save_archive", "build", "rebuild", "clean", "close",
    "import_xml", "import_native", "import_device", "rename", "move", "add",
    "unplug", "update", "set_gateway_and_ip_address", "remove_device",
    "set_compilerversion_to_newest", "set_project_defines", "set_sourcedownload",
    "download_missing_libraries", "remove_library", "add_library",
    "add_placeholder", "install_library", "uninstall_library",
    "set_redirection", "get_library_manager",
)

# O RECEPTOR decide, nunca o nome do metodo: `.insert(...)` existe em `list`
# (`sys.path.insert(0, ...)`, presente neste probe) E em `IScriptTextDocument`.
_RECEPTORES_SEGUROS_CONHECIDOS = {
    "insert": (("sys", "path"),),
}


def _method_calls(tree, nome):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == nome]


def _method_calls_sobre_proxy(tree, nome):
    seguros = _RECEPTORES_SEGUROS_CONHECIDOS.get(nome, ())
    encontrados = []
    for chamada in _method_calls(tree, nome):
        receptor = chamada.func.value
        if isinstance(receptor, ast.Attribute) and isinstance(receptor.value, ast.Name):
            if (receptor.value.id, receptor.attr) in seguros:
                continue
        encontrados.append(chamada)
    return encontrados


@pytest.mark.parametrize("metodo", MUTADORES_PROIBIDOS)
def test_probe_41_nao_contem_mutador(tree41, metodo):
    assert _method_calls_sobre_proxy(tree41, metodo) == [], (
        "probe 41 e read-only e nao pode chamar .%s() sobre proxy do "
        "MasterTool" % metodo)


@pytest.mark.parametrize("nome", NOMES_MUTADORES)
def test_probe_41_nao_menciona_nenhum_mutador_de_biblioteca(nome):
    """A guarda de AST pega a CHAMADA; esta pega a MENCAO -- inclusive em
    comentario, string ou docstring, de onde alguem poderia copiar por engano.

    Aqui ela vale mais que no probe 36: la o mutador morava num tipo vizinho,
    aqui os tres moram no MESMO objeto que a leitura, a poucos caracteres de
    distancia no autocompletar. `get_library_manager` entra na mesma lista por
    outro motivo: o stub diz, na linha 820, que ele CRIA o gerenciador quando
    nao existe."""
    fonte = io.open(PROBE41_PATH, encoding="utf-8").read()
    assert nome not in fonte


@pytest.mark.parametrize("nome", ["getattr", "setattr", "delattr", "hasattr",
                                  "eval", "exec", "compile", "__import__",
                                  "vars", "locals", "dir"])
def test_probe_41_sem_acesso_dinamico(tree41, nome):
    """Reflexao foi o instrumento de INVESTIGACAO das DLLs, fora do produto.
    Dentro do probe ela seria a invencao de API que este arquivo elimina."""
    encontrados = [n for n in ast.walk(tree41)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nome]
    assert encontrados == []


def test_probe_41_sem_fstring_e_identificadores_ascii(tree41):
    assert [n for n in ast.walk(tree41)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []
    for node in ast.walk(tree41):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_probe_41_compativel_com_ironpython_27(tree41):
    fonte = io.open(PROBE41_PATH, encoding="utf-8").read()
    assert "from __future__ import print_function" in fonte
    assert "yield from" not in fonte
    assert "pathlib" not in fonte
    for node in ast.walk(tree41):
        assert not isinstance(node, ast.AnnAssign)
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None
            for arg in node.args.args:
                assert getattr(arg, "annotation", None) is None


# =============================================================================
# Wrapper .ps1 -- fail-closed, ASCII puro, sem --noUI, sem matar processo
# =============================================================================

@pytest.fixture(scope="module")
def wrapper_fonte():
    return io.open(WRAPPER_PATH, encoding="utf-8").read()


@pytest.fixture(scope="module")
def wrapper_codigo(wrapper_fonte):
    """So as linhas EXECUTAVEIS: bloco `<# ... #>` e linhas de comentario
    removidos. As proibicoes valem para o que o PowerShell executa -- proibir a
    MENCAO tambem apagaria a explicacao de por que a proibicao existe, que e
    justamente o que impede alguem de reintroduzir o defeito."""
    linhas = []
    dentro_do_bloco = False
    for linha in wrapper_fonte.splitlines():
        texto = linha.strip()
        if texto.startswith("<#"):
            dentro_do_bloco = True
        if dentro_do_bloco:
            if texto.endswith("#>"):
                dentro_do_bloco = False
            continue
        if texto.startswith("#"):
            continue
        linhas.append(linha)
    return "\n".join(linhas)


def test_wrapper_existe_e_e_ascii_puro():
    dados = io.open(WRAPPER_PATH, "rb").read()
    fora = [b for b in bytearray(dados) if b > 127]
    assert fora == [], "wrapper tem %d byte(s) > 127" % len(fora)


def test_wrapper_nunca_usa_noui_nem_mata_processo(wrapper_fonte, wrapper_codigo):
    assert "--noUI" not in wrapper_codigo
    assert "Stop-Process" not in wrapper_codigo
    assert "CloseMainWindow" in wrapper_fonte


def test_wrapper_default_nao_abre_nada(wrapper_fonte):
    assert "assumindo -ValidateOnly (default)" in wrapper_fonte
    assert "[switch]$Execute" in wrapper_fonte
    assert "Modos mutuamente exclusivos" in wrapper_fonte


def test_wrapper_grava_json_sem_bom(wrapper_fonte, wrapper_codigo):
    assert "System.Text.UTF8Encoding($false)" in wrapper_fonte
    assert "[System.IO.File]::WriteAllText" in wrapper_fonte
    assert "Out-File" not in wrapper_codigo


def test_wrapper_verifica_hash_antes_e_depois(wrapper_fonte):
    assert "Get-FileHash" in wrapper_fonte
    assert "A copia MUDOU durante a leitura read-only." in wrapper_fonte
    assert "O PROJETO-BASE ORIGINAL foi tocado." in wrapper_fonte


@pytest.mark.parametrize("nome", NOMES_MUTADORES)
def test_wrapper_recusa_a_sessao_se_um_mutador_aparecer_no_probe(wrapper_codigo, nome):
    """A guarda tem de estar no CODIGO do wrapper, nao no comentario: o teste
    de mencao acima protege o probe, este protege a sessao."""
    assert "'%s'" % nome in wrapper_codigo
    assert "Sessao recusada" in wrapper_codigo


def test_wrapper_recusa_probe_sem_fase_read_only(wrapper_fonte):
    assert "READ_ONLY_PHASE" in wrapper_fonte


def test_wrapper_cria_a_copia_ele_mesmo_a_partir_do_base_project(wrapper_codigo):
    """Achado de W1.5: aceitar caminho de copia pre-existente transforma "nao
    tocar o original" num passo manual, e passo manual e onde o erro entra.
    Quatro dos cinco wrappers do repo ja criavam a copia; o quinto nao, e foi o
    que falhou. Este cria, e ainda RECUSA copia que ja exista."""
    assert "[string]$BaseProject" in wrapper_codigo
    assert "Copy-Item -LiteralPath $BaseProject" in wrapper_codigo
    assert "nunca reaproveita copia pre-existente" in wrapper_codigo
    # sha do original e da copia, antes e depois.
    assert wrapper_codigo.count("Get-FileHash") >= 4
    assert "$baseShaAfter -ne $baseSha" in wrapper_codigo
    assert "$copyShaAfter -ne $copySha" in wrapper_codigo


def test_wrapper_diz_qual_botao_clicar_no_dialogo_de_salvar(wrapper_fonte):
    """Achado de W1.5: o MasterTool marca o projeto como alterado so de abrir,
    entao o dialogo "Deseja salvar as alteracoes?" aparece mesmo numa sessao
    read-only. O wrapper tem de dizer QUAL botao, e por que os outros dois sao
    piores -- "cancele qualquer dialogo" seria instrucao errada aqui."""
    assert "Deseja salvar as alteracoes?" in wrapper_fonte
    assert 'CLIQUE "NAO".' in wrapper_fonte
    assert "CANCELAR" in wrapper_fonte


def test_o_aviso_do_dialogo_vem_ANTES_do_lancamento(wrapper_codigo):
    """Aviso que chega junto com o evento nao e aviso. A instrucao tem de estar
    impressa antes da copia e antes do Start-Process -- quando o dialogo
    aparecer, o operador ja precisa saber o que fazer."""
    posicao_aviso = wrapper_codigo.find('CLIQUE "NAO".')
    posicao_copia = wrapper_codigo.find("Copy-Item -LiteralPath $BaseProject")
    # O LANCAMENTO e a CHAMADA de Invoke-MasterTool, nao a linha `Start-Process`
    # dentro da definicao da funcao: a definicao aparece antes no texto e depois
    # na execucao, e comparar com ela mediria a ordem errada.
    posicao_lancamento = wrapper_codigo.find("$obs = Invoke-MasterTool")
    assert posicao_aviso > 0
    assert posicao_aviso < posicao_copia < posicao_lancamento


def test_o_host_nao_responde_o_dialogo_de_salvar_por_conta_propria(wrapper_fonte,
                                                                  wrapper_codigo):
    """Automatizar o clique num dialogo de salvamento daria ao host o poder de
    gravar. O host fecha a janela (CloseMainWindow) e para por ai."""
    assert "responde-lo por voce" in wrapper_fonte
    for envio in ("SendKeys", "AppActivate", "SendMessage", "PostMessage",
                  "SendWait"):
        assert envio not in wrapper_codigo


def test_wrapper_le_o_artefato_do_probe_41_e_nao_o_exit_do_launcher(wrapper_fonte):
    assert "libraries-completion.json" in wrapper_fonte
    assert "O exit code do launcher NAO decide nada." in wrapper_fonte


def test_wrapper_separa_sessao_medida_e_conferencia(wrapper_fonte):
    """Tres camadas, nao uma. Sessao que roda e nao mede nao sai com 0; medida
    sem conferencia tambem nao."""
    assert "exit 4" in wrapper_fonte
    assert "libraries_measured" in wrapper_fonte
    assert "routes_agree" in wrapper_fonte
