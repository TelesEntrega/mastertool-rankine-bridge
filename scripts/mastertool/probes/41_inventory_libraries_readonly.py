# -*- coding: utf-8 -*-
r"""41_inventory_libraries_readonly.py - inventario SOMENTE LEITURA das
bibliotecas referenciadas pelo projeto aberto, pelas DUAS cadeias literais
documentadas pelo stub oficial que o proprio produto versiona.

MOTIVO DE EXISTIR
-----------------
`libraries_unresolved` e o ULTIMO bloqueador de elegibilidade de autoria do
`TemplateExemplo v1.project` (docs/36 secao 3). A run-011 alcancou o no "Library Manager"
(`root/1/0/0/0`, status `resolved`) e leu ZERO filhos, num projeto industrial
com cartoes de I/O. A conclusao correta nao era "o projeto nao tem biblioteca":
era "bibliotecas NAO sao filhas daquele no". `get_children` e o instrumento
errado para esta grandeza, e probe 35 passou a emitir `resolved_but_empty` em
vez de uma lista vazia que se leria como medida.

Este probe substitui o instrumento errado pelo certo.

FONTE DE PRIMEIRA CLASSE: O STUB QUE O PRODUTO VERSIONA
-------------------------------------------------------
Todas as assinaturas abaixo vem de

    C:\Program Files\Altus\MT9000 4.1.0\MT9000\ScriptLib\Stubs\scriptengine\
    ScriptLibManObject.pyi

que e o stub oficial instalado com o MT9000 4.1.0 -- o mesmo tipo de fonte que
resolveu a compiler version em `59e8637`. Ele e melhor que reflexao adivinhada
por um motivo concreto e verificavel neste caso: os metadados do
`ScriptEngine3.dll` expoem `IList<System.String> get_libraries(Boolean)` com o
parametro booleano SEM NOME, e um booleano sem nome so pode ser chutado. O stub
o nomeia e o descreve.

  linhas 376-391  `ScriptLibManObjectMarker.is_libman` -> bool
                  "Every ScriptObject instance will be extended with this
                   method" / ":version added: 3.4.3.0". E por AQUI que o no do
                  Library Manager e reconhecido: por TIPO, nunca pelo nome
                  "Library Manager", que depende do idioma do projeto.

  linhas 401-411  `ScriptLibManObject.get_libraries(recursive=False)`
                  ":type recursive: bool"
                  ":param recursive: If set to ``True``, sublibraries are also
                   queried recursively."
                  ":rtype: list [str]  :returns: The list of library names."
                  O booleano e `recursive`, e o default do produto e False.

  linhas 464-473  `ScriptLibManObject.references` -> `ScriptLibraryReferences`
                  ":version added: 3.5.5.0"

  linhas 476-506  `ScriptLibraryReferences.__len__()` e `__getitem__(int)` /
                  `__getitem__(str)`.

  linhas 509-575  `ScriptLibraryReference.name` / `.namespace` /
                  `.is_placeholder` / `.is_managed` / `.system_library`.
                  Linha 543: para item gerenciado, `name` segue o padrao
                  "Name, Version (Company)"; para placeholder, "#Name".

DUAS ROTAS, ESCRITAS UMA A UMA, E O PAPEL DE CADA UMA
-----------------------------------------------------
ROTA RICA (primaria) -- `references`. E a UNICA que devolve os campos que o
contrato de saida exige (namespace, is_placeholder, is_managed,
system_library). Por isso e ela que decide se a grandeza foi medida.

ROTA SIMPLES (conferencia) -- `get_libraries(False)`. Devolve so nomes. NAO e
fallback da rota rica: se a rota rica falhar, os nomes sozinhos nao preenchem o
contrato, e o resultado e LACUNA -- fingir que uma rota cobre a outra e
exatamente o defeito que docs/36 secao 4 nomeia. Ela existe para CONFERIR a
rota rica: duas leituras independentes que discordam sao um achado, e uma
leitura unica nunca revela discordancia nenhuma.

`recursive=False` de proposito: o inventario que interessa e o das referencias
DIRETAS do projeto. `True` traria sub-bibliotecas de dependencia e faria a
contagem divergir da rota rica sem que a divergencia significasse defeito.

O PERIGO DESTE PROBE, E COMO ELE E CONTIDO
------------------------------------------
Os tres mutadores de biblioteca -- o que adiciona biblioteca, o que adiciona
placeholder e o que remove biblioteca -- moram no MESMO objeto e na MESMA
interface que a leitura (stub, linhas 413-462). Leitura e escrita ficam a
poucos caracteres de distancia no autocompletar. As defesas que NAO dependem de
atencao humana:

  1. Nenhum dos tres nomes aparece em NENHUMA linha deste arquivo -- nem em
     comentario, nem em docstring, de onde alguem poderia copiar por engano.
     O teste verifica a ausencia; o wrapper recusa a sessao se aparecerem.
  2. A verificacao de AST dos testes e por RECEPTOR, nao por nome de metodo:
     o mapa completo de "quem chama o que" e congelado, e qualquer chamada
     nova sobre um proxy do MasterTool derruba o teste, tenha o nome que tiver.
  3. Os dubles dos testes LEVANTAM se um membro mutavel for tocado.

TAMBEM NAO USADO, DE PROPOSITO
------------------------------
- O acessor de conveniencia do container (`ScriptLibManObjectContainer`, stub
  linhas 802-826) NAO e usado nem nomeado: o proprio stub diz, na linha 820,
  que ele obtem o gerenciador "implicitly creating one if none is existing
  yet". Um acessor que CRIA nao entra num probe read-only, por mais comodo que
  seja. O no e encontrado pelo marcador `is_libman`, que so LE.
- As dependencias de cada referencia NAO sao lidas: o stub avisa, linha 580,
  que bibliotecas com dependencia ciclica levam a recursao infinita. Um probe
  que pode nao terminar nao e um instrumento.
- Nao ha `getattr`, `dir`, `eval`, enumeracao de membros, busca por nome
  parcial nem cascata de acessores. Reflexao foi o INSTRUMENTO de investigacao
  sobre as DLLs, fora do produto; dentro do probe ela seria a invencao de API
  que este arquivo existe para eliminar.
- Nao escreve, nao salva, nao compila, nao fecha o projeto.

SOMENTE LEITURA. Compatibilidade: IronPython 2.7.12 (sem f-string, sem
anotacao de tipo, sem o modulo de caminhos orientado a objeto do Python 3).
"""
from __future__ import print_function

import os
import re
import sys
import traceback

_FILE_AVAILABLE = True
try:
    _SCRIPT_PATH = os.path.abspath(__file__)
    _SCRIPT_DIR = os.path.dirname(_SCRIPT_PATH)
except NameError:
    _FILE_AVAILABLE = False
    _SCRIPT_PATH = None
    _SCRIPT_DIR = None

_MASTERTOOL_DIR = os.path.dirname(_SCRIPT_DIR) if _SCRIPT_DIR else None
if _MASTERTOOL_DIR and _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None

SCRIPT_NAME = "41_inventory_libraries_readonly.py"
SCHEMA_VERSION = "1.0"

# --- as cadeias, LITERAIS, como constantes do modulo -------------------------
#
# Escritas UMA vez e levadas ao artefato. Um artefato que mostra a lista sem
# mostrar por onde ela veio nao permite auditar a leitura depois -- e a proxima
# pessoa teria de refazer a investigacao para saber se confia nos nomes.
STUB_PATH = ("C:\\Program Files\\Altus\\MT9000 4.1.0\\MT9000\\ScriptLib\\"
             "Stubs\\scriptengine\\ScriptLibManObject.pyi")

MARKER_CHAIN = "projects.primary -> get_children(False) -> node.is_libman"

MARKER_CHAIN_SOURCE = (
    "stub oficial versionado pelo produto '%s' linhas 376-391 "
    "(ScriptLibManObjectMarker.is_libman, bool, 'Every ScriptObject instance "
    "will be extended with this method', version added 3.4.3.0); confirmado "
    "por reflexao estatica (ReflectionOnlyLoadFrom, metadados em disco, "
    "MasterTool nunca aberto) em 'Common\\ScriptEngine3.dll' -- "
    "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptLibManObjectMarker."
    "is_libman. O no e reconhecido por TIPO: o nome 'Library Manager' depende "
    "do idioma do projeto e nao serve de identificador." % (STUB_PATH,)
)

ROUTE_SIMPLE_CHAIN = "libman.get_libraries(recursive=False)"

ROUTE_SIMPLE_SOURCE = (
    "stub oficial '%s' linhas 401-411: 'get_libraries(self, recursive=False)', "
    "':type recursive: bool', ':param recursive: If set to True, sublibraries "
    "are also queried recursively', ':rtype: list [str]', ':returns: The list "
    "of library names'. Nos metadados do 'Common\\ScriptEngine3.dll' o membro "
    "aparece como _3S.CoDeSys.ScriptEngine.BasicFunctionality."
    "IScriptLibManObject.get_libraries(Boolean) -> IList<System.String>, com o "
    "parametro booleano SEM NOME -- o nome e o significado vem do stub."
    % (STUB_PATH,)
)

ROUTE_RICH_CHAIN = (
    "libman.references -> len(references) -> references[i] -> "
    "name / namespace / is_placeholder / is_managed / system_library"
)

ROUTE_RICH_SOURCE = (
    "stub oficial '%s' linhas 464-473 (ScriptLibManObject.references -> "
    "ScriptLibraryReferences, version added 3.5.5.0), 476-506 "
    "(ScriptLibraryReferences.__len__ e __getitem__ por int e por str) e "
    "509-575 (ScriptLibraryReference.name, .namespace, .is_placeholder, "
    ".is_managed, .system_library); nos metadados do "
    "'Common\\ScriptEngine3.dll', _3S.CoDeSys.ScriptEngine.BasicFunctionality."
    "IScriptLibManObject2.references -> IScriptLibraryReferences, com "
    "__len__() e get_Item(Int64)/get_Item(String)." % (STUB_PATH,)
)

# O booleano de `get_libraries`. Nomeado aqui para que a chamada nao carregue
# um `False` nu, que o proximo leitor teria de ir procurar o que significa.
GET_LIBRARIES_RECURSIVE = False

GET_LIBRARIES_RECURSIVE_RATIONALE = (
    "recursive=False: o inventario que interessa e o das referencias DIRETAS "
    "do projeto. Com True, sub-bibliotecas de dependencia entrariam na lista e "
    "a contagem divergiria da rota rica sem que a divergencia significasse "
    "defeito algum."
)

# Padrao de nome documentado no stub, linha 543: item gerenciado se chama
# "Name, Version (Company)". A versao NAO tem acessor proprio em
# `ScriptLibraryReference` -- ela e derivada DESTE padrao, e o artefato diz
# isso em cada item, para ninguem confundir derivacao com leitura direta.
LIBRARY_NAME_PATTERN_SOURCE = (
    "derivada do padrao de nome documentado no stub '%s' linha 543 -- para "
    "item gerenciado, ScriptLibraryReference.name segue 'Name, Version "
    "(Company)'. Nao ha acessor de versao em ScriptLibraryReference; esta "
    "versao e DERIVACAO do nome, nunca leitura direta." % (STUB_PATH,)
)

_MANAGED_NAME_RE = re.compile(
    r"^\s*(?P<libname>.+?)\s*,\s*(?P<version>[0-9][0-9A-Za-z.\-]*)\s*"
    r"\((?P<company>[^()]*)\)\s*$")

# --- limites de varredura ----------------------------------------------------
#
# Limite infinito nao e oferecido: uma arvore ciclica ou um defeito de
# navegacao viraria varredura infinita dentro de uma sessao supervisionada.
MAX_DEPTH = 8
MAX_TOTAL_NODES = 5000
MAX_CHILDREN_PER_NODE = 256
MAX_LIBRARY_REFERENCES = 512

# --- vocabulario fechado -----------------------------------------------------
STATUS_MEASURED = "measured"
STATUS_PARTIAL = "partial"
STATUS_UNRESOLVED = "unresolved"
STATUS_FATAL = "fatal"

ALL_STATUSES = (STATUS_MEASURED, STATUS_PARTIAL, STATUS_UNRESOLVED, STATUS_FATAL)
SUCCESS_STATUSES = (STATUS_MEASURED,)

# `partial` = a rota rica mediu, a rota de conferencia nao. Ha inventario, mas
# ele nao foi conferido por segunda leitura, e isso nao pode sair com 0.
# `unresolved` = a sessao rodou e a grandeza nao foi obtida. Codigos proprios
# para nao se confundirem com falha de infraestrutura (1).
EXIT_BY_STATUS = {
    STATUS_MEASURED: 0,
    STATUS_UNRESOLVED: 2,
    STATUS_FATAL: 1,
    STATUS_PARTIAL: 4,
}

# Razoes fechadas de lacuna. Cada uma diz ONDE a leitura parou -- "nao deu" sem
# o passo culpado obriga a repetir a sessao supervisionada so para descobrir.
REASON_NO_PROJECT = "sem projeto primario"
REASON_NO_LIBMAN_NODE = (
    "nenhum no com is_libman == True foi encontrado na arvore varrida")
REASON_WALK_TRUNCATED = (
    "a varredura atingiu o limite de nos antes de terminar; o no do library "
    "manager pode ter ficado fora")
REASON_RICH_ROUTE_FAILED = "rota rica (references) falhou"
REASON_RICH_ROUTE_EMPTY = (
    "a rota rica devolveu ZERO referencias. Zero biblioteca num projeto "
    "MasterTool e implausivel e repete exatamente o sintoma da run-011 "
    "(docs/36): lista vazia le como 'medido: nenhuma', quando o que se tem e "
    "'nao mensuravel por este caminho'")
REASON_SIMPLE_ROUTE_FAILED = "rota simples (get_libraries) falhou"
REASON_ONLY_SIMPLE_ROUTE = (
    "so a rota simples respondeu. Nomes sozinhos nao preenchem o contrato de "
    "saida (namespace, is_placeholder, is_managed, system_library), e uma rota "
    "nao cobre a outra")
REASON_VERSION_NOT_IN_NAME = (
    "o nome nao segue o padrao 'Name, Version (Company)' -- e o caso normal de "
    "placeholder e de referencia nao gerenciada")

EVIDENCE_MEASURED = "measured"
EVIDENCE_UNRESOLVED = "unresolved"

# IronPython 2.7 dentro do MasterTool tem `basestring`; o CPython 3 dos testes
# nao. `py_compile` NAO pega essa diferenca -- o nome so quebraria em tempo de
# execucao, ou seja, dentro da sessao supervisionada, tarde demais.
try:
    _STRING_TYPES = (basestring,)  # noqa: F821  (Python 2 / IronPython 2.7)
except NameError:
    _STRING_TYPES = (str,)         # Python 3 (testes)


# =============================================================================
# nucleo puro -- nenhuma linha aqui toca o MasterTool
# =============================================================================

def build_evidence(value, source, reason):
    """Evidencia no MESMO formato fechado ja usado para a compiler version.

    Duas formas e nenhuma terceira. `measured` exige valor; `unresolved` exige
    valor None E razao escrita. Um valor ausente marcado como `measured` seria
    pior que a lacuna, porque a lacuna ao menos se anuncia.
    """
    if value is None:
        return {
            "status": EVIDENCE_UNRESOLVED,
            "value": None,
            "source": source,
            "reason": reason or REASON_RICH_ROUTE_FAILED,
        }
    return {
        "status": EVIDENCE_MEASURED,
        "value": value,
        "source": source,
        "reason": None,
    }


def as_text(value):
    """Texto do CLR normalizado para o tipo textual do interpretador.

    Devolve None para vazio: string em branco vinda do produto nao e nome nem
    namespace, e deixa-la passar produziria uma linha de inventario que parece
    medida e nao identifica nada.
    """
    if value is None:
        return None
    if isinstance(value, _STRING_TYPES):
        texto = value.strip()
        return texto or None
    try:
        texto = str(value).strip()
    except Exception:                                              # noqa: BLE001
        return None
    return texto or None


def parse_version_from_name(name):
    """Versao DERIVADA do padrao de nome do stub. Nunca levanta.

    Devolve `(versao, empresa)`; `(None, None)` quando o nome nao segue o
    padrao -- que e o caso normal de placeholder ("#Name") e de referencia nao
    gerenciada, e por isso nao e defeito nenhum.
    """
    texto = as_text(name)
    if texto is None:
        return None, None
    casado = _MANAGED_NAME_RE.match(texto)
    if casado is None:
        return None, None
    return as_text(casado.group("version")), as_text(casado.group("company"))


def build_library_entry(libman_node_id, name, namespace, is_placeholder,
                        is_managed, system_library, field_errors):
    """Uma linha do inventario, no formato do contrato de saida.

    `version` viaja como evidencia propria porque ela e DERIVADA do nome, e nao
    lida de um acessor: quem consome precisa poder distinguir as duas coisas
    sem abrir este arquivo.
    """
    versao, empresa = parse_version_from_name(name)
    return {
        "libman_node_id": libman_node_id,
        "name": as_text(name),
        "namespace": as_text(namespace),
        "is_placeholder": is_placeholder,
        "is_managed": is_managed,
        "system_library": system_library,
        "company": empresa,
        "version": build_evidence(versao, LIBRARY_NAME_PATTERN_SOURCE,
                                  REASON_VERSION_NOT_IN_NAME),
        "field_errors": field_errors or {},
    }


def compare_routes(rich_names, simple_names, rich_ok, simple_ok):
    """Confronto entre as duas leituras independentes.

    A rota simples existe para DISCORDAR quando houver do que discordar. Uma
    leitura unica nunca revela discordancia nenhuma, e por isso nunca prova
    nada sobre si mesma.
    """
    resultado = {
        "rich_route_ok": bool(rich_ok),
        "simple_route_ok": bool(simple_ok),
        "rich_count": len(rich_names or []),
        "simple_count": len(simple_names or []),
        "only_in_rich": [],
        "only_in_simple": [],
        "agree": None,
    }
    if not (rich_ok and simple_ok):
        return resultado
    conjunto_rico = set([n for n in (rich_names or []) if n])
    conjunto_simples = set([n for n in (simple_names or []) if n])
    resultado["only_in_rich"] = sorted(conjunto_rico - conjunto_simples)
    resultado["only_in_simple"] = sorted(conjunto_simples - conjunto_rico)
    resultado["agree"] = (conjunto_rico == conjunto_simples)
    return resultado


def classify(evidence, cross_check):
    """Status do probe DERIVADO da evidencia, nunca declarado a mao."""
    if (evidence or {}).get("status") != EVIDENCE_MEASURED:
        return STATUS_UNRESOLVED
    if not (cross_check or {}).get("simple_route_ok"):
        return STATUS_PARTIAL
    return STATUS_MEASURED


# =============================================================================
# orquestracao -- unica parte que toca o MasterTool
# =============================================================================

def read_is_libman(node):
    """`node.is_libman` -- o marcador de TIPO. Devolve `(bool, erro)`."""
    try:
        marcado = node.is_libman
    except Exception as exc:                                       # noqa: BLE001
        return False, "is_libman falhou: %r" % (exc,)
    return bool(marcado), None


def read_node_name(node):
    """Nome do no, so para o registro. Nunca usado como identificador."""
    try:
        return as_text(node.get_name(False))
    except Exception:                                              # noqa: BLE001
        return None


def read_children(node):
    """`get_children(False)` -> `Count` -> indexador. A MESMA cadeia ja
    confirmada pelos probes 05-10 e usada pelo scanner read-only. Devolve
    `(lista_de_filhos, erro)` e nunca levanta.
    """
    try:
        colecao = node.get_children(False)
    except Exception as exc:                                       # noqa: BLE001
        return [], "get_children falhou: %r" % (exc,)
    if colecao is None:
        return [], "get_children devolveu None"
    try:
        total = colecao.Count
    except Exception as exc:                                       # noqa: BLE001
        return [], "Count falhou: %r" % (exc,)
    if total is None or total < 0 or total > MAX_CHILDREN_PER_NODE:
        return [], "Count fora de faixa: %r" % (total,)
    filhos = []
    for indice in range(total):
        try:
            filhos.append(colecao[indice])
        except Exception as exc:                                   # noqa: BLE001
            return filhos, "indexador falhou em %d: %r" % (indice, exc)
    return filhos, None


def collect_libman_nodes(project):
    """Varredura DFS iterativa com pilha explicita, procurando `is_libman`.

    Nunca por nome: "Library Manager" e rotulo de interface e depende do
    idioma. O acessor de conveniencia do container tambem nao serve -- ele CRIA
    o gerenciador quando nao existe (stub, linha 820), e criar esta fora de um
    probe read-only.

    Devolve `(achados, varredura)`. `achados` carrega o proxy do no; tudo o
    mais e serializavel.
    """
    varredura = {"visited": 0, "truncated": False, "errors": []}
    achados = []
    if project is None:
        varredura["errors"].append(REASON_NO_PROJECT)
        return achados, varredura

    pilha = [(project, "root", 0)]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            varredura["truncated"] = True
            break
        no_atual, node_id, profundidade = pilha.pop()
        visitados += 1

        if node_id != "root":
            marcado, erro_marcador = read_is_libman(no_atual)
            if erro_marcador:
                varredura["errors"].append("%s: %s" % (node_id, erro_marcador))
            elif marcado:
                achados.append({"node_id": node_id,
                                "name": read_node_name(no_atual),
                                "node": no_atual})

        if profundidade >= MAX_DEPTH:
            continue
        filhos, erro_filhos = read_children(no_atual)
        if erro_filhos:
            varredura["errors"].append("%s: %s" % (node_id, erro_filhos))
        # Empilhados em ordem reversa para que o `pop()` os processe na ordem
        # crescente de indice, igual ao scanner read-only.
        indice = len(filhos) - 1
        while indice >= 0:
            pilha.append((filhos[indice], "%s/%d" % (node_id, indice),
                          profundidade + 1))
            indice -= 1

    varredura["visited"] = visitados
    return achados, varredura


def read_route_simple(libman):
    """ROTA DE CONFERENCIA: `get_libraries(recursive=False)` -> nomes.

    UMA chamada. Nenhuma retentativa, nenhum segundo acessor: um fallback aqui
    seria adivinhacao de API disfarcada de robustez.
    """
    resultado = {"ok": False, "names": [], "count": None, "truncated": False,
                 "error": None, "chain": ROUTE_SIMPLE_CHAIN,
                 "source": ROUTE_SIMPLE_SOURCE,
                 "recursive": GET_LIBRARIES_RECURSIVE,
                 "recursive_rationale": GET_LIBRARIES_RECURSIVE_RATIONALE}
    try:
        bruto = libman.get_libraries(GET_LIBRARIES_RECURSIVE)
    except Exception as exc:                                       # noqa: BLE001
        resultado["error"] = "%s: %r" % (REASON_SIMPLE_ROUTE_FAILED, exc)
        return resultado
    if bruto is None:
        resultado["error"] = "%s: devolveu None" % (REASON_SIMPLE_ROUTE_FAILED,)
        return resultado
    try:
        total = len(bruto)
    except Exception as exc:                                       # noqa: BLE001
        resultado["error"] = "%s: len() falhou: %r" % (REASON_SIMPLE_ROUTE_FAILED, exc)
        return resultado
    resultado["count"] = total
    if total > MAX_LIBRARY_REFERENCES:
        resultado["truncated"] = True
        total = MAX_LIBRARY_REFERENCES
    nomes = []
    for indice in range(total):
        try:
            nomes.append(as_text(bruto[indice]))
        except Exception as exc:                                   # noqa: BLE001
            resultado["error"] = ("%s: indexador falhou em %d: %r"
                                  % (REASON_SIMPLE_ROUTE_FAILED, indice, exc))
            resultado["names"] = nomes
            return resultado
    resultado["names"] = nomes
    resultado["ok"] = True
    return resultado


def read_reference_fields(reference, libman_node_id):
    """Os CINCO campos do contrato, cada um no seu proprio `try`.

    Um campo que falha nao pode levar junto os outros quatro: um inventario
    parcial identificado e util, um inventario perdido inteiro por causa de uma
    propriedade nao e.
    """
    erros = {}

    try:
        nome = reference.name
    except Exception as exc:                                       # noqa: BLE001
        nome = None
        erros["name"] = repr(exc)
    try:
        espaco = reference.namespace
    except Exception as exc:                                       # noqa: BLE001
        espaco = None
        erros["namespace"] = repr(exc)
    try:
        placeholder = bool(reference.is_placeholder)
    except Exception as exc:                                       # noqa: BLE001
        placeholder = None
        erros["is_placeholder"] = repr(exc)
    try:
        gerenciada = bool(reference.is_managed)
    except Exception as exc:                                       # noqa: BLE001
        gerenciada = None
        erros["is_managed"] = repr(exc)
    try:
        de_sistema = bool(reference.system_library)
    except Exception as exc:                                       # noqa: BLE001
        de_sistema = None
        erros["system_library"] = repr(exc)

    return build_library_entry(libman_node_id, nome, espaco, placeholder,
                               gerenciada, de_sistema, erros)


def read_route_rich(libman, libman_node_id, nomes_conhecidos=None):
    """ROTA PRIMARIA: `references` -> `len` -> indexador -> os cinco campos.

    E a unica que preenche o contrato de saida. Se ela falhar, o resultado e
    LACUNA -- a rota simples NAO a substitui.

    DUAS FORMAS DE INDEXACAO, e as duas sao CATALOGADAS no stub oficial
    (`ScriptLibManObject.pyi` L476-506: `__getitem__` por `int` E por `str`).
    Isso NAO e cascata de tentativa ate algo funcionar -- a proibicao de
    fallback vale para adivinhar API nao catalogada, e aqui as duas formas
    estao documentadas pelo fabricante. A ordem e fixa e o resultado registra
    QUAL respondeu, para que ninguem precise deduzir depois.

    MEDIDO na run-015, sobre o TemplateExemplo v1: a forma por POSICAO falha no indice 0
    com `SystemError: Referencia de objeto nao definida` (NullReference),
    embora `len()` responda. A forma por NOME existe justamente para esse
    caso, e os nomes vem da rota simples -- que na mesma sessao devolveu 17.
    Por isso a rota simples corre ANTES desta.
    """
    resultado = {"ok": False, "libraries": [], "count": None, "truncated": False,
                 "error": None, "chain": ROUTE_RICH_CHAIN,
                 "source": ROUTE_RICH_SOURCE, "indexing_form": None,
                 "positional_error": None}
    try:
        referencias = libman.references
    except Exception as exc:                                       # noqa: BLE001
        resultado["error"] = "%s: %r" % (REASON_RICH_ROUTE_FAILED, exc)
        return resultado
    if referencias is None:
        resultado["error"] = "%s: devolveu None" % (REASON_RICH_ROUTE_FAILED,)
        return resultado
    try:
        total = len(referencias)
    except Exception as exc:                                       # noqa: BLE001
        resultado["error"] = "%s: len() falhou: %r" % (REASON_RICH_ROUTE_FAILED, exc)
        return resultado
    resultado["count"] = total
    if total > MAX_LIBRARY_REFERENCES:
        resultado["truncated"] = True
        total = MAX_LIBRARY_REFERENCES

    # ZERO REFERENCIAS E CASO PROPRIO, e nao falha de indexacao: e o sintoma da
    # run-011 (docs/36), em que o no foi alcancado e devolveu vazio. Tratar
    # aqui, antes de qualquer forma de indexacao, mantem a razao especifica --
    # cair na mensagem generica de "indexador falhou" trocaria um diagnostico
    # por outro e apagaria o precedente.
    if total == 0:
        resultado["ok"] = True
        resultado["indexing_form"] = "none_needed"
        return resultado

    # --- forma 1: por POSICAO (stub L500-506) --------------------------------
    bibliotecas = []
    erro_posicional = None
    for indice in range(total):
        try:
            referencia = referencias[indice]
        except Exception as exc:                                   # noqa: BLE001
            erro_posicional = ("indexador por posicao falhou em %d: %r"
                               % (indice, exc))
            break
        bibliotecas.append(read_reference_fields(referencia, libman_node_id))
    if erro_posicional is None and bibliotecas:
        resultado["libraries"] = bibliotecas
        resultado["indexing_form"] = "positional"
        resultado["ok"] = True
        return resultado
    resultado["positional_error"] = erro_posicional

    # --- forma 2: por NOME (stub L490-499) -----------------------------------
    nomes = list(nomes_conhecidos or [])
    if not nomes:
        resultado["error"] = ("%s: %s, e nao ha nomes da rota simples para "
                              "tentar a indexacao por nome"
                              % (REASON_RICH_ROUTE_FAILED,
                                 erro_posicional or "sem itens"))
        return resultado

    bibliotecas = []
    for nome in nomes:
        try:
            referencia = referencias[nome]
        except Exception as exc:                                   # noqa: BLE001
            resultado["error"] = ("%s: indexador por nome falhou em %r: %r "
                                  "(por posicao: %s)"
                                  % (REASON_RICH_ROUTE_FAILED, nome, exc,
                                     erro_posicional))
            resultado["libraries"] = bibliotecas
            return resultado
        if referencia is None:
            resultado["error"] = ("%s: indexador por nome devolveu None em %r "
                                  "(por posicao: %s)"
                                  % (REASON_RICH_ROUTE_FAILED, nome,
                                     erro_posicional))
            resultado["libraries"] = bibliotecas
            return resultado
        bibliotecas.append(read_reference_fields(referencia, libman_node_id))
    resultado["libraries"] = bibliotecas
    resultado["indexing_form"] = "by_name"
    resultado["ok"] = True
    return resultado


def read_inventory(project):
    """Orquestra as duas rotas sobre TODOS os nos marcados. Nunca levanta.

    Devolve `(evidencia, cross_check, detalhe)`.
    """
    achados, varredura = collect_libman_nodes(project)
    detalhe = {
        "walk": varredura,
        "libman_nodes": [{"node_id": a["node_id"], "name": a["name"]}
                         for a in achados],
        "routes": [],
        "chain_steps": [],
    }
    passos = detalhe["chain_steps"]

    if project is None:
        passos.append({"step": "projects.primary", "ok": False,
                       "detail": REASON_NO_PROJECT})
        return (build_evidence(None, MARKER_CHAIN_SOURCE, REASON_NO_PROJECT),
                compare_routes([], [], False, False), detalhe)
    passos.append({"step": "projects.primary", "ok": True, "detail": None})

    if not achados:
        razao = REASON_WALK_TRUNCATED if varredura["truncated"] else REASON_NO_LIBMAN_NODE
        passos.append({"step": MARKER_CHAIN, "ok": False, "detail": razao})
        return (build_evidence(None, MARKER_CHAIN_SOURCE, razao),
                compare_routes([], [], False, False), detalhe)
    passos.append({"step": MARKER_CHAIN, "ok": True,
                   "detail": "%d no(s) marcado(s)" % (len(achados),)})

    bibliotecas = []
    nomes_simples = []
    rica_ok = True
    simples_ok = True
    erros = []
    for achado in achados:
        # A SIMPLES CORRE PRIMEIRO, e a ordem tem razao: ela devolve os NOMES,
        # e a rota rica precisa deles para a indexacao por nome -- a unica que
        # respondeu no TemplateExemplo v1, onde a indexacao por posicao levanta
        # NullReference (medido na run-015). Isso nao inverte quem decide: a
        # rica continua sendo a unica que preenche o contrato de saida, e a
        # simples continua sendo conferencia, nunca substituta.
        simples = read_route_simple(achado["node"])
        rica = read_route_rich(achado["node"], achado["node_id"],
                               nomes_conhecidos=simples.get("names"))
        detalhe["routes"].append({"libman_node_id": achado["node_id"],
                                  "rich": rica, "simple": simples})
        passos.append({"step": "%s @ %s" % (ROUTE_RICH_CHAIN, achado["node_id"]),
                       "ok": rica["ok"], "detail": rica["error"]})
        passos.append({"step": "%s @ %s" % (ROUTE_SIMPLE_CHAIN, achado["node_id"]),
                       "ok": simples["ok"], "detail": simples["error"]})
        if rica["ok"]:
            bibliotecas = bibliotecas + rica["libraries"]
        else:
            rica_ok = False
            erros.append("%s: %s" % (achado["node_id"], rica["error"]))
        if simples["ok"]:
            nomes_simples = nomes_simples + simples["names"]
        else:
            simples_ok = False
            erros.append("%s: %s" % (achado["node_id"], simples["error"]))

    nomes_ricos = [b["name"] for b in bibliotecas]
    cross_check = compare_routes(nomes_ricos, nomes_simples, rica_ok, simples_ok)

    if not rica_ok:
        razao = "%s (%s)" % (REASON_RICH_ROUTE_FAILED, "; ".join(erros))
        if simples_ok:
            razao = "%s -- %s" % (razao, REASON_ONLY_SIMPLE_ROUTE)
        return (build_evidence(None, ROUTE_RICH_SOURCE, razao), cross_check,
                detalhe)

    # Contagem ZERO nao vira medida. A run-011 (docs/36) e o precedente: uma
    # lista vazia le como "medido: nenhuma biblioteca", quando o que se tem e
    # "nao mensuravel por este caminho". Sao conclusoes opostas para quem
    # decide, e a diferenca so existe se alguem escrever.
    if not bibliotecas:
        return (build_evidence(None, ROUTE_RICH_SOURCE, REASON_RICH_ROUTE_EMPTY),
                cross_check, detalhe)

    return (build_evidence(bibliotecas, ROUTE_RICH_SOURCE, None), cross_check,
            detalhe)


def run_probe(script_globals, argv, project_access, file_io, probe_cli, now=None):
    """Orquestra. Nunca levanta: toda falha vira status + problema escrito."""
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": "read_only",
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "problems": [],
        "runtime": None,
        "project": {"path": None},
        "marker_chain": MARKER_CHAIN,
        "marker_chain_source": MARKER_CHAIN_SOURCE,
        "route_rich_chain": ROUTE_RICH_CHAIN,
        "route_simple_chain": ROUTE_SIMPLE_CHAIN,
        "libraries": build_evidence(None, MARKER_CHAIN_SOURCE, REASON_NO_PROJECT),
        "cross_check": compare_routes([], [], False, False),
        "walk": {},
        "libman_nodes": [],
        "routes": [],
        "chain_steps": [],
        "artifacts_dir": None,
        "exit_code": EXIT_BY_STATUS[STATUS_FATAL],
        "mutating_calls": [],
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, EXIT_BY_STATUS[STATUS_FATAL])
        return result

    problems = []
    artifacts_dir = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    if problems:
        for problema in problems:
            result["problems"].append(problema)
        return finish(STATUS_FATAL)
    result["artifacts_dir"] = artifacts_dir

    result["runtime"] = probe_cli.runtime_identity()

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        evidencia, cross_check, detalhe = read_inventory(None)
        result["libraries"] = evidencia
        result["cross_check"] = cross_check
        result["walk"] = detalhe["walk"]
        result["libman_nodes"] = detalhe["libman_nodes"]
        result["routes"] = detalhe["routes"]
        result["chain_steps"] = detalhe["chain_steps"]
        return finish(STATUS_FATAL)

    result["project"]["path"] = project_access.get_project_path(project)

    evidencia, cross_check, detalhe = read_inventory(project)
    result["libraries"] = evidencia
    result["cross_check"] = cross_check
    result["walk"] = detalhe["walk"]
    result["libman_nodes"] = detalhe["libman_nodes"]
    result["routes"] = detalhe["routes"]
    result["chain_steps"] = detalhe["chain_steps"]

    if evidencia["status"] != EVIDENCE_MEASURED:
        result["problems"].append(
            "inventario de bibliotecas nao lido pela rota rica %s: %s"
            % (ROUTE_RICH_CHAIN, evidencia["reason"]))
    elif not cross_check["simple_route_ok"]:
        result["problems"].append(
            "rota de conferencia %s falhou: o inventario existe mas NAO foi "
            "conferido por segunda leitura" % (ROUTE_SIMPLE_CHAIN,))
    elif cross_check["agree"] is False:
        result["problems"].append(
            "as duas rotas DISCORDAM -- so na rota rica: %s; so na rota "
            "simples: %s" % (cross_check["only_in_rich"],
                             cross_check["only_in_simple"]))
    return finish(classify(evidencia, cross_check))


# =============================================================================
# artefatos
# =============================================================================

def build_completion(result):
    """Artefato de conclusao. E ELE que o wrapper le para dar veredito, e e ele
    que permite ao probe 35 trocar `resolved_but_empty` por medicao real.

    Carrega as CADEIAS junto do valor: quem le o veredito precisa poder
    conferir de onde veio a lista sem abrir outro arquivo.
    """
    evidencia = result.get("libraries") or {}
    bibliotecas = evidencia.get("value") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "project": result.get("project"),
        "libraries": evidencia,
        "libraries_value": evidencia.get("value"),
        "libraries_count": len(bibliotecas),
        "libraries_names": [biblioteca.get("name") for biblioteca in bibliotecas],
        "cross_check": result.get("cross_check"),
        "libman_nodes": result.get("libman_nodes"),
        "marker_chain": result.get("marker_chain"),
        "marker_chain_source": result.get("marker_chain_source"),
        "route_rich_chain": result.get("route_rich_chain"),
        "route_simple_chain": result.get("route_simple_chain"),
        "chain_steps": result.get("chain_steps"),
        "runtime": result.get("runtime"),
        "errors": result.get("problems"),
        "mutating_calls": result.get("mutating_calls"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    evidencia = result.get("libraries") or {}
    cross_check = result.get("cross_check") or {}
    bibliotecas = evidencia.get("value") or []
    lines = [
        "# Probe 41 - inventario read-only das bibliotecas do projeto",
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- projeto: `%s`" % (result.get("project") or {}).get("path"),
        "- marcador do no: `%s`" % result.get("marker_chain"),
        "- rota primaria: `%s`" % result.get("route_rich_chain"),
        "- rota de conferencia: `%s`" % result.get("route_simple_chain"),
        "- evidencia: `%s` (razao: %s)" % (evidencia.get("status"),
                                           evidencia.get("reason")),
        "- bibliotecas medidas: **%d**" % len(bibliotecas),
        "- conferencia: rica_ok=%s simples_ok=%s concordam=%s"
        % (cross_check.get("rich_route_ok"), cross_check.get("simple_route_ok"),
           cross_check.get("agree")),
        "",
        "## Nos marcados por is_libman",
        "",
    ]
    for no_marcado in result.get("libman_nodes") or []:
        lines.append("- `%s` (%s)"
                     % (no_marcado.get("node_id"), no_marcado.get("name")))
    if not (result.get("libman_nodes") or []):
        lines.append("- nenhum")
    lines.append("")
    lines.append("## Bibliotecas")
    lines.append("")
    for biblioteca in bibliotecas:
        versao = biblioteca.get("version") or {}
        lines.append(
            "- `%s` | namespace=`%s` | version=`%s` (%s) | placeholder=%s | "
            "managed=%s | system=%s"
            % (biblioteca.get("name"), biblioteca.get("namespace"),
               versao.get("value"), versao.get("status"),
               biblioteca.get("is_placeholder"), biblioteca.get("is_managed"),
               biblioteca.get("system_library")))
    if not bibliotecas:
        lines.append("- nenhuma")
    lines.append("")
    lines.append("## Passos")
    lines.append("")
    for passo in result.get("chain_steps") or []:
        lines.append("- `%s` ok=%s %s" % (passo.get("step"), passo.get("ok"),
                                          passo.get("detail") or ""))
    lines.append("")
    lines.append("## Problemas")
    lines.append("")
    for problema in result.get("problems") or []:
        lines.append("- %s" % problema)
    if not (result.get("problems") or []):
        lines.append("- nenhum")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(result, file_io):
    artifacts_dir = result.get("artifacts_dir")
    if not artifacts_dir:
        return None
    file_io.ensure_dir(artifacts_dir)
    written = []
    file_io.write_json(os.path.join(artifacts_dir, "libraries-analysis.json"),
                       result)
    written.append("libraries-analysis.json")
    file_io.write_text(os.path.join(artifacts_dir, "libraries-report.md"),
                       build_report_markdown(result))
    written.append("libraries-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "libraries-completion.json"),
                       build_completion(result))
    written.append("libraries-completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s - SOMENTE LEITURA" % SCRIPT_NAME)
    print("[INFO] marcador   : %s" % MARKER_CHAIN)
    print("[INFO] rota rica  : %s" % ROUTE_RICH_CHAIN)
    print("[INFO] rota simples: %s" % ROUTE_SIMPLE_CHAIN)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access

    try:
        result = run_probe(script_globals, list(sys.argv or []),
                           project_access, file_io, probe_cli)
    except Exception as exc:                                       # noqa: BLE001
        print("[FATAL] %r" % (exc,))
        try:
            traceback.print_exc()
        except Exception:                                          # noqa: BLE001
            pass
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        write_artifacts(result, file_io)
    except Exception as exc:                                       # noqa: BLE001
        print("[ERROR] falha ao gravar artefatos: %r" % (exc,))

    print("[INFO] status=%s" % result.get("status"))
    print("[INFO] bibliotecas=%d"
          % len((result.get("libraries") or {}).get("value") or []))
    for problema in result.get("problems") or []:
        print("[PROBLEM] %s" % problema)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())
