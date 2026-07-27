# -*- coding: utf-8 -*-
"""ProjectTreeAdapter — snapshot LIMITADO, somente leitura, de profundidade
no maximo 1, dos filhos diretos de um projeto ja resolvido.

Motivo de existir (2026-07-23): os probes 05/06/07
(scripts/mastertool/probes/) confirmaram em runtime, um a um e de forma
isolada, toda a cadeia minima de navegacao (`get_children(False)` ->
`Count` -> indexador nativo -> `is_folder`/`type`/`guid`/`get_name(False)`
por no) contra `ExemploPlanta V1.0.project`. Os 5 criterios de reativacao do
`tree_walker.py` (ver docs/api/mastertool-api-observations.md) estao
atendidos, mas `tree_walker.py` continua SUSPENSO — este modulo e a
alternativa LIMITADA e auditada para o MESMO dado, usando SOMENTE os
membros ja confirmados, nunca por hipotese. `tree_walker.py` podera, no
futuro, passar a consumir este adaptador em vez de acessar diretamente o
ScriptEngine; essa migracao NAO esta implementada aqui.

Regras rigidas (todas garantidas por construcao, nao por parametro):
  - aceita SOMENTE um projeto JA RESOLVIDO (a resolucao de
    `projects.primary` e responsabilidade do chamador, ex.:
    common/project_access.py) — o adaptador nunca busca o projeto sozinho;
  - `get_children(False)` e chamado EXATAMENTE 1 vez;
  - `Count` e lido EXATAMENTE 1 vez;
  - cada indice e acessado EXATAMENTE 1 vez, via o indexador NATIVO
    (`children[i]`), em um loop sobre uma lista/range PYTHON local de
    indices — NUNCA `GetEnumerator()`/`iter()`/`for x in children`/
    compreensao sobre a colecao CLR;
  - `get_name(False)`/`is_folder`/`type`/`guid` sao chamados/lidos
    EXATAMENTE 1 vez por no, sem fallback para outro nome nem para
    `get_name(True)`;
  - NUNCA usa `dir()`/`hasattr()` para decidir se um membro existe;
  - profundidade fixa em, no maximo, `MAX_SUPPORTED_DEPTH` (1) — filhos
    diretos apenas, NUNCA navegacao recursiva. Nao existe parametro
    `recursive`: uma opcao ainda nao autorizada nao deve nem ser
    exposta, mesmo que sempre fosse ignorada internamente;
  - NUNCA toca documentos textuais (`textual_declaration`/
    `textual_implementation`/`has_textual_declaration`);
  - NUNCA escreve, compila, salva ou acessa `online`/`device_repository`;
  - toda serializacao passa por `common.capabilities.build_representation()`
    — nunca `repr()`/`str()`/`.ToString()` em objeto CLR desconhecido;
  - o retorno de `get_root_children()` e 100% dados serializaveis
    (dict/list/str/int/float/bool/None) — NUNCA inclui o proxy do
    ScriptEngine, `ExtendedObject`, a colecao CLR ou qualquer referencia
    viva ao projeto/ScriptEngine. Isto impede que a camada externa invoque
    acidentalmente um metodo nao autorizado sobre um objeto vivo.

Granularidade de falha:
  - falha em `get_children(False)` ou em `Count` -> ABORTA o snapshot
    inteiro (a colecao em si nao pode ser considerada acessivel;
    `children` fica vazio, erro registrado em `errors`);
  - `Count` invalido (negativo, tipo nao inteiro, ou maior que
    `max_children`) -> tambem ABORTA o snapshot (mesma razao: o limite de
    enumeracao nao pode ser confiavelmente estabelecido);
  - falha no acesso a UM indice (`children[i]`) -> interrompe a
    enumeracao NAQUELE ponto (nenhum indice seguinte e tentado) e marca o
    snapshot como incompleto (`complete: false`) — os nos ja lidos com
    sucesso ANTES da falha permanecem no resultado, pois foram
    legitimamente obtidos;
  - falha isolada em `name`/`type`/`guid`/`is_folder` de UM no -> NAO
    aborta nada: o estado da falha fica registrado NAQUELE campo
    (`{"state": ..., "value": None, "error": ...}`) e o processamento
    continua normalmente para os demais campos/nos.

`Count` observado vs `expected_count`: o valor observado de `Count` E
SEMPRE o limite real da enumeracao desta execucao — pertence ao PROJETO,
nao a API do MasterTool. `expected_count` e OPCIONAL e serve apenas para
uma validacao especifica (ex.: um probe de regressao contra um projeto
conhecido); quando fornecido e diferente do observado, fica registrado em
`collection.count_matches_expected` (e um erro informativo e adicionado a
`errors`), mas isto NAO interrompe a enumeracao — adicionar um objeto
legitimo ao projeto nao deve ser interpretado como falha permanente da API.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

from common import capabilities, compatibility

DEFAULT_MAX_CHILDREN = 64
MIN_DEPTH = 0
MAX_SUPPORTED_DEPTH = 1

# Nomes fixos dos membros sondados por no — nunca alterados/estendidos por
# fallback. Qualquer novo membro exige nova evidencia + atualizacao explicita
# deste modulo (nunca descoberta dinamica).
_NODE_PROPERTY_MEMBERS = ("is_folder", "type", "guid")


class DepthNotSupportedError(Exception):
    """`get_root_children(depth=...)` recebeu uma profundidade fora de
    [MIN_DEPTH, MAX_SUPPORTED_DEPTH]. Levantada ANTES de qualquer acesso ao
    projeto — nao ha parametro 'recursive': profundidade > 1 nunca e uma
    opcao aceita, mesmo convertida internamente para False."""
    pass


def _field_result(state, value=None, error=None):
    return {"state": state, "value": value, "error": error}


def _safe_exc_message(exc):
    return compatibility.safe_repr(exc)


def _is_non_negative_int(value):
    if isinstance(value, bool):
        return False
    try:
        is_int_like = isinstance(value, (int, long))  # noqa: F821 (Python 2)
    except NameError:
        is_int_like = isinstance(value, int)
    return is_int_like and value >= 0


def _validate_count(value, max_children):
    """Retorna (count_valido_ou_None, mensagem_de_erro_ou_None)."""
    if not _is_non_negative_int(value):
        return None, ("Count nao e um inteiro nao-negativo valido (tipo "
                      "Python: %s, valor: %s)."
                      % (compatibility.safe_type_name(value), value))
    if value > max_children:
        return None, ("Count (%s) excede max_children (%s) - rejeitado "
                      "por seguranca." % (value, max_children))
    return value, None


def _probe_node_property(node, obj_label, member_name):
    """1 getattr isolado (via capabilities.probe_member) + representacao
    estrita. Retorna _field_result — nunca lanca excecao."""
    record = capabilities.probe_member(
        node, obj_label, member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return _field_result(record["state"], error=record.get("exception_message"))
    value = record["raw_value"]
    python_type = capabilities.python_type_info(value)
    dotnet_type = capabilities.dotnet_type_info(value)
    rep = capabilities.build_representation(value, python_type, dotnet_type)
    if not rep["value_available"]:
        return _field_result(
            "unrepresentable",
            error=("valor obtido com sucesso, mas sem representacao segura "
                  "(tipo .NET nao confirmado como seguro para "
                  "serializacao; nenhuma stringificacao foi tentada)."))
    return _field_result("confirmed", value=rep["value"])


def _probe_node_name(node, obj_label):
    """`get_name(False)`, 1 chamada, SEM fallback para `get_name(True)`."""
    record = capabilities.probe_method_call(
        node, obj_label, "get_name", (False,),
        capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return _field_result(record["state"], error=record.get("exception_message"))
    value = record["raw_value"]
    python_type = capabilities.python_type_info(value)
    dotnet_type = capabilities.dotnet_type_info(value)
    rep = capabilities.build_representation(value, python_type, dotnet_type)
    if not rep["value_available"]:
        return _field_result(
            "unrepresentable",
            error=("nome obtido com sucesso, mas sem representacao segura "
                  "(nao era uma string nativa nem tipo confirmado seguro)."))
    return _field_result("confirmed", value=rep["value"])


def _bool_or_error_state(field_result):
    """`is_folder` deve ser bool; qualquer outro valor vira 'unrepresentable'
    (nao presumimos truthiness de um valor nao-bool)."""
    if field_result["state"] != "confirmed":
        return field_result
    if isinstance(field_result["value"], bool):
        return field_result
    return _field_result(
        "unrepresentable",
        error="valor obtido nao e bool (tipo: %s)."
             % compatibility.safe_type_name(field_result["value"]))


class ProjectTreeAdapter(object):
    """Snapshot LIMITADO (profundidade <= 1) dos filhos diretos de um
    projeto JA RESOLVIDO. Ver docstring do modulo para as regras completas.
    """

    def __init__(self, project, expected_count=None, max_children=DEFAULT_MAX_CHILDREN):
        self._project = project
        self._expected_count = expected_count
        self._max_children = max_children

    def _root_identity(self):
        return {
            "path": _probe_node_property(self._project, "project", "path"),
            "is_root": _bool_or_error_state(
                _probe_node_property(self._project, "project", "is_root")),
        }

    def get_root_children(self, depth=1):
        """Executa o snapshot. `depth` so aceita valores em
        [MIN_DEPTH, MAX_SUPPORTED_DEPTH] (0 ou 1); qualquer outro valor
        levanta DepthNotSupportedError SEM tocar no projeto. `depth=0`
        retorna somente a identidade da raiz, sem acessar `get_children`.
        """
        if depth < MIN_DEPTH or depth > MAX_SUPPORTED_DEPTH:
            raise DepthNotSupportedError(
                "depth=%r nao suportado (permitido: %s..%s). Este "
                "adaptador nao aceita navegacao recursiva."
                % (depth, MIN_DEPTH, MAX_SUPPORTED_DEPTH))

        snapshot = {
            "depth": depth,
            "root": self._root_identity(),
            "collection": {
                "state": None,
                "count": None,
                "expected_count": self._expected_count,
                "count_matches_expected": None,
                "max_children": self._max_children,
            },
            "children": [],
            "errors": [],
            "complete": True,
        }

        if depth == 0:
            return snapshot

        col = snapshot["collection"]

        # --- get_children(False), EXATAMENTE 1 chamada ----------------------
        gc_record = capabilities.probe_method_call(
            self._project, "project", "get_children", (False,),
            capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
        if gc_record["state"] != "confirmed" or "raw_value" not in gc_record:
            col["state"] = gc_record["state"]
            snapshot["errors"].append({
                "where": "get_children",
                "message": gc_record.get("exception_message"),
            })
            snapshot["complete"] = False
            return snapshot
        children = gc_record["raw_value"]

        # --- Count, EXATAMENTE 1 leitura -------------------------------------
        count_record = capabilities.probe_member(
            children, "children", "Count", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
            capture_value=True)
        if count_record["state"] != "confirmed" or "raw_value" not in count_record:
            col["state"] = count_record["state"]
            snapshot["errors"].append({
                "where": "children.Count",
                "message": count_record.get("exception_message"),
            })
            snapshot["complete"] = False
            return snapshot

        count_value, count_error = _validate_count(
            count_record["raw_value"], self._max_children)
        if count_error is not None:
            col["state"] = "invalid_count"
            snapshot["errors"].append({"where": "children.Count", "message": count_error})
            snapshot["complete"] = False
            return snapshot

        col["state"] = "confirmed"
        col["count"] = count_value
        if self._expected_count is not None:
            col["count_matches_expected"] = (count_value == self._expected_count)
            if not col["count_matches_expected"]:
                snapshot["errors"].append({
                    "where": "children.Count",
                    "message": ("Count observado (%s) difere de expected_count "
                               "(%s). Nao interrompe a enumeracao: Count "
                               "pertence ao projeto, nao a API."
                               % (count_value, self._expected_count)),
                })

        # --- children[0..count-1], indices PYTHON locais, SEM iterar a
        # colecao CLR. Falha de indexador aborta a enumeracao NESTE ponto,
        # sem tentar os indices seguintes.
        for index in range(count_value):
            idx_record = capabilities.probe_indexer_access(
                children, "children", index, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
                capture_value=True)
            if idx_record["state"] != "confirmed" or "raw_value" not in idx_record:
                snapshot["errors"].append({
                    "where": "children[%s]" % index,
                    "message": idx_record.get("exception_message"),
                })
                snapshot["complete"] = False
                break

            node = idx_record["raw_value"]
            obj_label = "children[%s]" % index
            node_entry = {"index": index, "element_access_state": "confirmed"}
            node_entry["name"] = _probe_node_name(node, obj_label)
            node_entry["is_folder"] = _bool_or_error_state(
                _probe_node_property(node, obj_label, "is_folder"))
            node_entry["type_guid"] = _probe_node_property(node, obj_label, "type")
            node_entry["object_guid"] = _probe_node_property(node, obj_label, "guid")
            snapshot["children"].append(node_entry)

        return snapshot


def render_simplified_snapshot(snapshot):
    """Visualizacao SIMPLIFICADA (achatada) de um snapshot ja produzido por
    `get_root_children()` — reduz cada campo por-estado a so o valor (ou
    None), para relatorios/consumo rapido. NUNCA usada como fonte de
    verdade: para saber se um campo realmente foi confirmado, use o
    snapshot completo (`state`/`error` por campo)."""
    def _v(field_result):
        return field_result["value"] if field_result["state"] == "confirmed" else None

    root = snapshot["root"]
    simplified = {
        "depth": snapshot["depth"],
        "root": {"path": _v(root["path"]), "is_root": _v(root["is_root"])},
        "collection": dict(snapshot["collection"]),
        "children": [],
        "complete": snapshot["complete"],
    }
    for child in snapshot["children"]:
        simplified["children"].append({
            "index": child["index"],
            "name": _v(child["name"]),
            "is_folder": _v(child["is_folder"]),
            "type_guid": _v(child["type_guid"]),
            "object_guid": _v(child["object_guid"]),
        })
    return simplified
