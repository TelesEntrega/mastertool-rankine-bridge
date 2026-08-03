"""Preflight do lote de repetibilidade — o que se confere ANTES de abrir o
produto (fase R1, instrumento do piloto).

Módulo puro e injetável: não roda `git`, não lê disco e não abre o MasterTool
por conta própria — recebe tudo por `PreflightEnvironment`. Isso é o que
permite exercer cada recusa offline, que é justamente o ponto de um preflight.

O QUE ELE PROMETE, E O QUE ELE NÃO PROMETE
==========================================
Toda checagem aqui é **host-side**: comparação de hash, de caminho, de estado
de gate e de identidade declarada em JSON. Nenhuma delas abre o `.project`,
percorre árvore ou lê biblioteca. O registro diz isso explicitamente em
`host_side_only` e `reevaluated_in_mastertool`, porque afirmar "inspecionei o
template" tendo comparado um profile JSON seria descrever mal o que foi feito
— e é exatamente o tipo de afirmação que a fase R0 existiu para eliminar.

A IDENTIDADE PRIMÁRIA DA ENTRADA É O SHA-256 DO ARQUIVO
=======================================================
`persistent_tree_sha256`, seletor da Application, versão de compilador e
inventário de bibliotecas continuam sendo propriedades qualificadas do
Template Profile — mas nenhuma delas substitui o hash do `.project`. Duas
árvores podem coincidir em tudo que o perfil mede e ainda serem arquivos
diferentes; o hash é o que amarra a medição ao byte.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

PREFLIGHT_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

STAGE_PLAN = "plan"
STAGE_BUILD = "build"
STAGES = (STAGE_PLAN, STAGE_BUILD)

# Vocabulário FECHADO de recusa. Cada nome corresponde a uma condição do
# contrato do piloto; um caso novo entra como nome novo, e não diluído num
# "erro genérico" que ninguém trata.
REFUSAL_DIRTY_TREE = "git_tree_dirty"
REFUSAL_GATE_OPEN = "controlled_write_phase_not_none"
REFUSAL_SPEC_MISMATCH = "spec_sha256_mismatch"
REFUSAL_TEMPLATE_MISMATCH = "template_sha256_mismatch"
REFUSAL_MASTERTOOL_NOT_FOUND = "mastertool_not_found"
REFUSAL_MASTERTOOL_AMBIGUOUS = "mastertool_ambiguous"
REFUSAL_MASTERTOOL_PATH_DIVERGENT = "mastertool_path_divergent"
REFUSAL_MASTERTOOL_VERSION = "mastertool_version_not_qualified"
REFUSAL_OUTPUT_EXISTS = "output_root_exists"
REFUSAL_PRIOR_BATCH_REUSED = "prior_batch_reused"
REFUSAL_PLAN_OUTPUTS_MISSING = "plan_outputs_missing"
REFUSAL_PLAN_STAGE_VERDICT = "plan_stage_cannot_emit_verdict"
REFUSAL_INVALID_REQUEST = "invalid_request"

REFUSALS = (
    REFUSAL_DIRTY_TREE, REFUSAL_GATE_OPEN, REFUSAL_SPEC_MISMATCH,
    REFUSAL_TEMPLATE_MISMATCH, REFUSAL_MASTERTOOL_NOT_FOUND,
    REFUSAL_MASTERTOOL_AMBIGUOUS, REFUSAL_MASTERTOOL_PATH_DIVERGENT,
    REFUSAL_MASTERTOOL_VERSION, REFUSAL_OUTPUT_EXISTS,
    REFUSAL_PRIOR_BATCH_REUSED, REFUSAL_PLAN_OUTPUTS_MISSING,
    REFUSAL_PLAN_STAGE_VERDICT, REFUSAL_INVALID_REQUEST,
)

# O que este preflight de fato confere, e o que só o produto pode confirmar.
HOST_SIDE_ONLY = (
    "sha256 do arquivo de spec",
    "sha256 do arquivo de template",
    "identidade declarada no Template Profile (JSON)",
    "estado do gate lido do código-fonte",
    "limpeza da árvore de trabalho",
    "existência e unicidade da instalação detectada",
)

REEVALUATED_IN_MASTERTOOL = (
    "árvore do projeto e cardinalidade do seletor da Application",
    "inventário de bibliotecas e versão de compilador do template",
    "persistência real do que for escrito",
    "resultado de build",
)


@dataclass(frozen=True)
class PreflightRequest:
    spec_path: str
    expected_spec_sha256: str
    template_path: str
    expected_template_sha256: str
    template_profile_id: str
    output_root: str
    requested_runs: int
    requested_stage: str
    mastertool_wrapper_path: str
    expected_mastertool_version: str
    timestamp: str


@dataclass(frozen=True)
class PreflightEnvironment:
    """Portas para o mundo, todas injetáveis."""

    git_head: Callable[[], str | None] = lambda: None
    git_tree_clean: Callable[[], bool] = lambda: False
    sha256_of: Callable[[str], str | None] = lambda _p: None
    path_exists: Callable[[str], bool] = lambda _p: False
    list_run_dirs: Callable[[str], list[str]] = lambda _p: []
    plan_output_exists: Callable[[str], bool] = lambda _p: False
    read_controlled_write_phase: Callable[[], Any] = lambda: None
    detect_mastertool: Callable[[], Any] = lambda: None


@dataclass
class PreflightResult:
    record: dict = field(default_factory=dict)
    refusals: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def cleared(self) -> bool:
        """DERIVADO. Um preflight com qualquer recusa não é "aprovado com
        ressalva": ele descreve uma sessão que não deve começar."""
        return not self.refusals

    def to_dict(self) -> dict[str, Any]:
        saida = dict(self.record)
        saida["cleared"] = self.cleared
        saida["refusals"] = list(self.refusals)
        saida["details"] = list(self.details)
        return saida


def _validar_pedido(request: Any) -> list[str]:
    problemas: list[str] = []
    if not isinstance(request, PreflightRequest):
        return ["request: esperado PreflightRequest, recebido %s"
                % type(request).__name__]
    for campo in ("spec_path", "template_path", "template_profile_id",
                  "output_root", "mastertool_wrapper_path",
                  "expected_mastertool_version", "timestamp"):
        valor = getattr(request, campo)
        if not isinstance(valor, str) or not valor.strip():
            problemas.append("%s: string não vazia obrigatória" % campo)
    for campo in ("expected_spec_sha256", "expected_template_sha256"):
        valor = getattr(request, campo)
        if not isinstance(valor, str) or not _SHA256_RE.match(valor):
            problemas.append("%s: esperado hex de 64 caracteres" % campo)
    if isinstance(request.requested_runs, bool) \
            or not isinstance(request.requested_runs, int) \
            or request.requested_runs < 2:
        problemas.append("requested_runs: esperado inteiro >= 2 — "
                         "repetibilidade exige ao menos duas execuções")
    if request.requested_stage not in STAGES:
        problemas.append("requested_stage: esperado 'plan' ou 'build'")
    return problemas


def _normalizar_caminho(caminho: Any) -> str:
    """Compara caminho do Windows sem tropeçar em caixa nem em barra."""
    if not isinstance(caminho, str):
        return ""
    return caminho.replace("/", "\\").rstrip("\\").lower()


def run_preflight(request: Any,
                  env: PreflightEnvironment | None = None) -> PreflightResult:
    """Confere as precondições da sessão. Nunca levanta e nunca abre nada."""
    env = env or PreflightEnvironment()
    resultado = PreflightResult()

    problemas = _validar_pedido(request)
    if problemas:
        resultado.refusals.append(REFUSAL_INVALID_REQUEST)
        resultado.details.extend(problemas)
        resultado.record = {
            "preflight_schema_version": PREFLIGHT_SCHEMA_VERSION,
            "host_side_only": list(HOST_SIDE_ONLY),
            "reevaluated_in_mastertool": list(REEVALUATED_IN_MASTERTOOL),
        }
        return resultado

    spec_sha = env.sha256_of(request.spec_path)
    template_sha = env.sha256_of(request.template_path)
    gate = env.read_controlled_write_phase()
    deteccao = env.detect_mastertool()
    arvore_limpa = bool(env.git_tree_clean())
    saida_existe = bool(env.path_exists(request.output_root))
    runs_existentes = list(env.list_run_dirs(request.output_root) or [])

    detectados = []
    caminho_detectado = None
    versao_detectada = None
    if deteccao is not None:
        detectados = list(getattr(deteccao, "candidates", []) or [])
        instalacao = getattr(deteccao, "install", None)
        if instalacao is not None:
            caminho_detectado = getattr(instalacao, "exe_path", None)
            versao_detectada = getattr(instalacao, "version", None)
    quantidade_detectada = len({_normalizar_caminho(c) for c in detectados if c})
    caminhos_batem = (
        caminho_detectado is not None
        and _normalizar_caminho(caminho_detectado)
        == _normalizar_caminho(request.mastertool_wrapper_path))

    resultado.record = {
        "preflight_schema_version": PREFLIGHT_SCHEMA_VERSION,
        "head": env.git_head(),
        "git_tree_clean": arvore_limpa,
        "spec_path": request.spec_path,
        "spec_sha256": spec_sha,
        "expected_spec_sha256": request.expected_spec_sha256,
        "template_path": request.template_path,
        "template_sha256": template_sha,
        "expected_template_sha256": request.expected_template_sha256,
        "template_profile_id": request.template_profile_id,
        "mastertool_detected_count": quantidade_detectada,
        "mastertool_detected_path": caminho_detectado,
        "mastertool_wrapper_path": request.mastertool_wrapper_path,
        "mastertool_paths_match": caminhos_batem,
        "mastertool_version": versao_detectada,
        "expected_mastertool_version": request.expected_mastertool_version,
        "controlled_write_phase": gate,
        "output_root": request.output_root,
        "output_root_exists": saida_existe,
        "prior_batch_reused": bool(runs_existentes) and request.requested_stage == STAGE_PLAN,
        "existing_run_dirs": runs_existentes,
        "requested_runs": request.requested_runs,
        "requested_stage": request.requested_stage,
        "timestamp": request.timestamp,
        "host_side_only": list(HOST_SIDE_ONLY),
        "reevaluated_in_mastertool": list(REEVALUATED_IN_MASTERTOOL),
    }

    # --- recusas -------------------------------------------------------------
    if not arvore_limpa:
        resultado.refusals.append(REFUSAL_DIRTY_TREE)
        resultado.details.append(
            "árvore de trabalho suja: o lote precisa ser atribuível a um "
            "estado de código identificável, e 'sujo' não é um estado")

    if gate is not None:
        # O gate tem de estar FECHADO no preflight. Ele é aberto depois, em
        # commit isolado — encontrar aberto aqui significa que uma sessão
        # anterior não foi encerrada.
        resultado.refusals.append(REFUSAL_GATE_OPEN)
        resultado.details.append(
            "CONTROLLED_WRITE_PHASE = %r antes da sessão: fase aberta por "
            "engano ou não encerrada da vez anterior" % (gate,))

    if spec_sha is None or spec_sha.lower() != request.expected_spec_sha256.lower():
        resultado.refusals.append(REFUSAL_SPEC_MISMATCH)
        resultado.details.append(
            "spec %s tem sha256 %s, esperado %s — para este gate equivalência "
            "semântica não basta"
            % (request.spec_path, spec_sha, request.expected_spec_sha256))

    if template_sha is None \
            or template_sha.lower() != request.expected_template_sha256.lower():
        resultado.refusals.append(REFUSAL_TEMPLATE_MISMATCH)
        resultado.details.append(
            "template %s tem sha256 %s, esperado %s — o hash do arquivo é a "
            "identidade primária da entrada"
            % (request.template_path, template_sha,
               request.expected_template_sha256))

    if quantidade_detectada == 0 or caminho_detectado is None:
        resultado.refusals.append(REFUSAL_MASTERTOOL_NOT_FOUND)
        # A CAUSA vem junto. "Não encontrada" e "encontrada e recusada por
        # versão" pedem ações opostas — uma manda procurar, a outra manda
        # medir —, e colapsar as duas mandaria o operador para o lado errado.
        motivos = list(getattr(deteccao, "problems", []) or [])
        if motivos:
            resultado.details.append(
                "instalação não resolvida: " + "; ".join(motivos))
        else:
            resultado.details.append(
                "nenhuma instalação do MasterTool foi resolvida")
    elif quantidade_detectada > 1:
        resultado.refusals.append(REFUSAL_MASTERTOOL_AMBIGUOUS)
        resultado.details.append(
            "%d instalações candidatas: %s"
            % (quantidade_detectada, ", ".join(sorted(detectados))))
    elif not caminhos_batem:
        resultado.refusals.append(REFUSAL_MASTERTOOL_PATH_DIVERGENT)
        resultado.details.append(
            "instalação detectada (%s) difere da que o wrapper usa (%s): o "
            "lote mediria um produto e o wrapper abriria outro"
            % (caminho_detectado, request.mastertool_wrapper_path))

    if caminho_detectado is not None:
        if versao_detectada is None:
            resultado.refusals.append(REFUSAL_MASTERTOOL_VERSION)
            resultado.details.append(
                "versão da instalação não pôde ser lida, e %r era exigida — "
                "versão não medida não é a versão certa por omissão"
                % request.expected_mastertool_version)
        elif versao_detectada != request.expected_mastertool_version:
            resultado.refusals.append(REFUSAL_MASTERTOOL_VERSION)
            resultado.details.append(
                "versão detectada %r difere da qualificada %r"
                % (versao_detectada, request.expected_mastertool_version))

    if request.requested_stage == STAGE_PLAN:
        if saida_existe and runs_existentes:
            resultado.refusals.append(REFUSAL_PRIOR_BATCH_REUSED)
            resultado.details.append(
                "%s já contém %d diretório(s) run-*: reaproveitar saída "
                "transformaria N execuções em uma execução e N-1 leituras"
                % (request.output_root, len(runs_existentes)))
        elif saida_existe:
            resultado.refusals.append(REFUSAL_OUTPUT_EXISTS)
            resultado.details.append(
                "%s já existe. O estágio 'plan' exige raiz nova"
                % request.output_root)
    else:
        faltando = [
            run for run in
            ["run-%03d" % i for i in range(1, request.requested_runs + 1)]
            if not env.plan_output_exists("%s\\%s" % (request.output_root, run))
        ]
        if faltando:
            resultado.refusals.append(REFUSAL_PLAN_OUTPUTS_MISSING)
            resultado.details.append(
                "estágio 'build' sem saída válida do estágio 'plan' em: %s"
                % ", ".join(faltando))

    return resultado


def refusal_report(result: PreflightResult) -> str:
    """Texto das recusas, em uma linha por motivo. Vazio quando liberado."""
    if result.cleared:
        return ""
    linhas = ["preflight RECUSOU a sessão (%d motivo(s)):" % len(result.refusals)]
    for nome, detalhe in zip(result.refusals, result.details):
        linhas.append("  [%s] %s" % (nome, detalhe))
    if len(result.details) > len(result.refusals):
        for extra in result.details[len(result.refusals):]:
            linhas.append("  %s" % extra)
    return "\n".join(linhas)
