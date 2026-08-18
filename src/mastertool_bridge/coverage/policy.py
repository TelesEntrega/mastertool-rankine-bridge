"""Política de cobertura de análise — as perguntas que se faz SEMPRE.

POR QUE ELA EXISTE
==================
O projeto já tinha o diagnóstico bom sem obrigação, e a obrigação fraca sobre
o diagnóstico ruim.

`analysis/safety_checks.py` faz três checagens — múltiplos escritores, escrito
e nunca lido, lido e nunca escrito — mas na camada HEURÍSTICA, que casa texto
e declara `heuristic: True` em todo achado. A camada resolvida — o indexador
com precedência de escopo, mais a visão unificada ST × Ladder — é confiável e
só responde quando alguém pergunta.

Uma saída física sem nenhum escritor pode existir por anos sem ninguém saber,
porque a consulta que revelaria isso depende de alguém lembrar de rodá-la.

Esta camada torna as perguntas obrigatórias.

RELATAR, NUNCA REPROVAR
=======================
Múltiplos escritores é FATO do projeto — pode ser intertravamento deliberado,
modo manual, comando redundante. `read_never_written` pode ser entrada de
hardware ou variável de comunicação.

Uma política que reprovasse transformaria qualquer CI num alarme falso
permanente, até alguém desligar a verificação inteira. Ela obriga a
**mostrar**; o veredito é de engenharia.

DEGRADAÇÃO HONESTA
==================
Cada pergunta declara de que entrada depende. Sem a entrada, ela sai
`not_applicable` com o motivo — nunca "nenhum achado". Um relatório que
dissesse "0 problemas" porque não olhou é pior que não ter relatório.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MODEL_KIND = "analysis_coverage_report"

# Natureza do achado — o mesmo vocabulário de R4.3, e pela mesma razão:
# agrupar os quatro como "erro" é o jeito mais fácil de um relatório mentir
# sem escrever nenhuma frase falsa.
NATURES = ("fact", "diagnostic", "limitation", "context")

# Estado de cada pergunta.
MEASURED = "measured"
NOT_APPLICABLE = "not_applicable"

# As entradas possíveis. Uma pergunta nomeia de qual depende.
INPUT_CODE = "resolved_code_view"      # UnifiedSymbolView (ST + Ladder)
INPUT_PLANT = "plant_model"            # inventário de pontos (R9.2)
INPUT_REQUIREMENTS = "process_requirements"   # sequências (R9.3)


@dataclass(frozen=True)
class Finding:
    subject: str
    detail: str
    evidence: tuple = ()

    def to_dict(self) -> dict[str, Any]:
        return {"subject": self.subject, "detail": self.detail,
                "evidence": list(self.evidence)}


@dataclass
class Question:
    """Uma pergunta da política, com o que ela mediu."""

    key: str
    text: str
    nature: str
    requires: tuple
    state: str = NOT_APPLICABLE
    reason: str | None = None
    findings: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.nature not in NATURES:
            raise ValueError("natureza %r fora de %s"
                             % (self.nature, list(NATURES)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "question": self.text,
            "nature": self.nature,
            "requires": list(self.requires),
            "state": self.state,
            "reason": self.reason,
            "count": len(self.findings),
            "findings": [f.to_dict() for f in
                         sorted(self.findings, key=lambda f: f.subject)],
        }


# =============================================================================
# as sete perguntas
# =============================================================================

QUESTIONS = (
    ("actuator_without_writer",
     "todo acionamento tem ao menos um escritor?",
     "diagnostic", (INPUT_CODE, INPUT_PLANT)),
    ("multiple_writers",
     "alguma saída tem mais de um escritor?",
     "fact", (INPUT_CODE,)),
    ("written_never_read",
     "alguma variável é escrita e nunca lida?",
     "diagnostic", (INPUT_CODE,)),
    ("read_never_written",
     "alguma variável é lida e nunca escrita?",
     "context", (INPUT_CODE,)),
    ("inventory_point_absent_from_logic",
     "todo ponto do inventário aparece na lógica?",
     "diagnostic", (INPUT_CODE, INPUT_PLANT)),
    ("unresolved_references_categorised",
     "toda referência não resolvida está categorizada?",
     "limitation", (INPUT_CODE,)),
    ("safety_excluded_from_generation",
     "todo símbolo de segurança está fora da geração?",
     "fact", (INPUT_PLANT,)),
)


@dataclass
class CoverageReport:
    project: str
    questions: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)

    @property
    def answered(self) -> int:
        return sum(1 for q in self.questions if q.state == MEASURED)

    @property
    def complete(self) -> bool:
        """Todas as perguntas foram medidas? Derivado, nunca declarado."""
        return self.answered == len(self.questions)

    def summary(self) -> dict[str, Any]:
        por_natureza: dict = {}
        for q in self.questions:
            if q.state != MEASURED or not q.findings:
                continue
            por_natureza[q.nature] = por_natureza.get(q.nature, 0) + len(q.findings)
        return {
            "questions": len(self.questions),
            "answered": self.answered,
            "not_applicable": len(self.questions) - self.answered,
            "complete": self.complete,
            "findings_by_nature": dict(sorted(por_natureza.items())),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "project": self.project,
            "inputs": dict(sorted(self.inputs.items())),
            "questions": [q.to_dict() for q in self.questions],
            "summary": self.summary(),
        }


def analyse_coverage(*, view=None, plant=None, requirements=None,
                     project: str = "projeto") -> CoverageReport:
    """Roda as sete perguntas com o que houver, e nomeia o que faltou.

    `view`          `UnifiedSymbolView` — a camada RESOLVIDA, não a heurística
    `plant`         `PlantModel` de R9.2
    `requirements`  `ProcessRequirements` de R9.3
    """
    disponivel = {
        INPUT_CODE: view is not None,
        INPUT_PLANT: plant is not None,
        INPUT_REQUIREMENTS: requirements is not None,
    }
    relatorio = CoverageReport(project=project, inputs=disponivel)

    for chave, texto, natureza, exige in QUESTIONS:
        pergunta = Question(key=chave, text=texto, nature=natureza,
                            requires=exige)
        faltando = [e for e in exige if not disponivel.get(e)]
        if faltando:
            # NUNCA "nenhum achado". Um relatório que diz zero porque não
            # olhou é pior que não ter relatório.
            pergunta.state = NOT_APPLICABLE
            pergunta.reason = ("entrada ausente: %s. A pergunta não foi "
                               "respondida — e isso não é o mesmo que não ter "
                               "achado nada" % ", ".join(faltando))
        else:
            pergunta.state = MEASURED
            _RESPONDEDORES[chave](pergunta, view, plant, requirements)
        relatorio.questions.append(pergunta)

    return relatorio


# =============================================================================
# os respondedores
# =============================================================================

def _saidas_do_inventario(plant) -> dict:
    """TAG -> ponto, para os pontos que TÊM saída digital utilizável.

    Só saída: um acionamento é o que o programa comanda. Uma entrada sem
    escritor é normal — ela vem do campo.
    """
    saidas = {}
    for ponto in plant.points:
        conta = ponto.io_counts.get("digital_output")
        if conta is not None and conta.usable and conta.value:
            saidas[ponto.tag] = ponto
    return saidas


def _acionamento_sem_escritor(pergunta, view, plant, _req) -> None:
    for tag, ponto in sorted(_saidas_do_inventario(plant).items()):
        if view.writers(tag):
            continue
        pergunta.findings.append(Finding(
            subject=tag,
            detail=("declarado como saída digital no inventário e sem nenhum "
                    "escritor na lógica resolvida"),
            evidence=(ponto.description.value or "",)))


def _multiplos_escritores(pergunta, view, _plant, _req) -> None:
    for simbolo, fatos in sorted(view.multi_writers().items()):
        pergunta.findings.append(Finding(
            subject=simbolo,
            detail=("%d escritores. Isto é FATO do projeto: pode ser "
                    "intertravamento, modo manual ou comando redundante "
                    "deliberado" % len(fatos)),
            evidence=tuple(
                "%s %s" % (f["source_language"],
                           f.get("network_id") or f.get("file") or "?")
                for f in fatos)))


def _escrito_nunca_lido(pergunta, view, _plant, _req) -> None:
    for simbolo in view.symbols():
        if view.writers(simbolo) and not view.readers(simbolo):
            pergunta.findings.append(Finding(
                subject=simbolo,
                detail="escrito e sem nenhuma leitura na lógica resolvida"))


def _lido_nunca_escrito(pergunta, view, _plant, _req) -> None:
    for simbolo in view.symbols():
        if view.readers(simbolo) and not view.writers(simbolo):
            pergunta.findings.append(Finding(
                subject=simbolo,
                detail=("lido e sem nenhuma escrita na lógica. Pode ser "
                        "entrada de hardware ou variável de comunicação — "
                        "por isso é CONTEXTO, e não defeito")))


def _ponto_ausente_da_logica(pergunta, view, plant, _req) -> None:
    conhecidos = set(view.symbols())
    for ponto in sorted(plant.points, key=lambda p: p.tag):
        if ponto.tag in conhecidos:
            continue
        pergunta.findings.append(Finding(
            subject=ponto.tag,
            detail=("consta do inventário e não aparece na lógica "
                    "analisada"),
            evidence=(ponto.equipment.value or "sem equipamento",)))


def _nao_resolvidos_categorizados(pergunta, view, _plant, _req) -> None:
    """A pergunta não é "há não-resolvidos?" — é "eles estão categorizados?".

    Não-resolvido é limitação declarada, e ela é aceitável. O que não é
    aceitável é uma referência aberta sem categoria, porque aí ninguém sabe
    qual ação toma.
    """
    chamadas = getattr(view, "_calls", [])
    for chamada in chamadas:
        estado = getattr(chamada, "resolution_status", None)
        if estado in ("resolved", "not_applicable", None):
            continue
        if not getattr(chamada, "unresolved_category", None):
            pergunta.findings.append(Finding(
                subject=getattr(chamada, "target_text", "?"),
                detail="não resolvido e SEM categoria: a ação de correção "
                       "fica indeterminada"))


def _seguranca_fora_da_geracao(pergunta, _view, plant, _req) -> None:
    gerar = {p.tag for p in plant.generable_points()}
    for ponto in plant.safety_points():
        if ponto.tag in gerar:
            pergunta.findings.append(Finding(
                subject=ponto.tag,
                detail="ponto de segurança presente em `generable_points`"))
    if not pergunta.findings:
        pergunta.findings.append(Finding(
            subject="segregação",
            detail=("%d ponto(s) de segurança, todos fora da geração"
                    % len(plant.safety_points()))))


_RESPONDEDORES = {
    "actuator_without_writer": _acionamento_sem_escritor,
    "multiple_writers": _multiplos_escritores,
    "written_never_read": _escrito_nunca_lido,
    "read_never_written": _lido_nunca_escrito,
    "inventory_point_absent_from_logic": _ponto_ausente_da_logica,
    "unresolved_references_categorised": _nao_resolvidos_categorizados,
    "safety_excluded_from_generation": _seguranca_fora_da_geracao,
}
